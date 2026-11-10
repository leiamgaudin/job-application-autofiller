import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import ollama
from playwright.sync_api import sync_playwright, Page
from rich.console import Console
from rich.table import Table

console = Console()

DEFAULT_MODEL = "qwen2.5:3b"

PROMPT_TEMPLATE = """You are an autofill assistant. Match ALL form fields from the webpage to the candidate profile.

Candidate Profile:
{profile_json}

Accessible Webpage Form Elements:
{aria_tree}

CRITICAL RULES:
1. Examine the ENTIRE list of webpage elements.
2. Generate an action for EVERY field that can be filled from the profile.
   - Do NOT stop after the first few fields. Cover personal details, address, links, education, work authorization, EEO questions, and resume upload.
   - For textboxes: {{"role": "textbox", "name": "<name from tree>", "val": "<value>"}}
   - For phone: 10 digits without formatting (e.g. 3175560084).
   - For combobox/dropdown: {{"role": "combobox", "name": "<name from tree>", "val": "<option>"}}
   - For radio buttons (multiple choice questions): {{"role": "radio", "name": "<choice name like Yes or No>"}}
   - For checkboxes: {{"role": "checkbox", "name": "<name from tree>"}}
   - For resume/CV upload: {{"role": "file", "name": "<name from tree>", "val": "{resume_path}"}}
   - NEVER fill open-ended essay questions (e.g. "Why do you want to work here").
3. DO NOT output a button action. Only output form input fields to fill.

Return valid JSON with ALL matched fields:
{{
  "actions": [
    {{"role": "textbox", "name": "First Name *", "val": "Leiam"}},
    {{"role": "textbox", "name": "Last Name *", "val": "Gaudin"}},
    {{"role": "textbox", "name": "Email *", "val": "leiamgaudin@gmail.com"}},
    {{"role": "textbox", "name": "Phone", "val": "3175560084"}},
    {{"role": "combobox", "name": "Country", "val": "United States"}},
    {{"role": "radio", "name": "Yes"}}
  ]
}}
"""


def load_profile(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_aria_tree(raw_tree: str) -> str:
    """Filter out non-interactive static paragraphs while preserving ALL interactive fields across the entire page."""
    lines = []
    for line in raw_tree.splitlines():
        trimmed = line.strip()
        if any(trimmed.startswith(prefix) for prefix in [
            "- textbox", "- combobox", "- radio", "- checkbox", "- button", "- group", "  - radio", "  - option", "- link"
        ]):
            lines.append(line)
    return "\n".join(lines)


def ask_model(profile: Dict[str, Any], aria_tree: str, model: str, debug: bool = False) -> Dict[str, Any]:
    resume_path = profile.get("documents", {}).get("resume_path", "")
    prompt = PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile, indent=2),
        aria_tree=aria_tree,
        resume_path=resume_path
    )

    if debug:
        console.print(f"[dim yellow]DEBUG - Tree sent to model ({len(aria_tree.splitlines())} lines):[/dim yellow]\n{aria_tree}\n")

    console.print(f"[dim]Analyzing entire page with {model}...[/dim]")
    t0 = time.time()
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={
                "temperature": 0.0,
                "num_predict": 1024  # Large output limit so all fields fit in JSON
            }
        )
        content = response["message"]["content"]
        elapsed = time.time() - t0
        console.print(f"[dim]Model responded in {elapsed:.1f}s[/dim]")

        if debug:
            console.print(f"[dim yellow]DEBUG - Raw Model Output:[/dim yellow]\n{content}\n")

        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(content)
    except Exception as e:
        console.print(f"[bold red]Ollama query error:[/bold red] {e}")
        return {"actions": []}


def execute_playwright_action(page: Page, action: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[str, str, str]:
    role = (action.get("role") or "").lower()
    name = action.get("name") or ""
    val = action.get("val") or action.get("value") or ""

    if not role or not name:
        return name, str(val), "Skipped (Invalid action)"

    # Clean phone digits if entering into phone textbox
    if role == "textbox" and any(k in name.lower() for k in ["phone", "mobile", "tel"]):
        digits = re.sub(r'\D', '', str(val))
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            val = digits

    try:
        # 1. TEXTBOX
        if role == "textbox":
            loc = page.get_by_role("textbox", name=name)
            if not loc.count():
                loc = page.get_by_label(name)
            if not loc.count():
                # Try partial match without asterisk
                clean_name = name.replace("*", "").strip()
                loc = page.get_by_label(clean_name)

            if loc.count():
                target = loc.first
                target.scroll_into_view_if_needed()
                target.click()
                target.fill(str(val))
                return f'textbox "{name}"', str(val), "Filled"
            return f'textbox "{name}"', str(val), "Not found on page"

        # 2. COMBOBOX / DROPDOWN
        elif role == "combobox":
            loc = page.get_by_role("combobox", name=name)
            if not loc.count():
                loc = page.get_by_label(name)
            if not loc.count():
                clean_name = name.replace("*", "").strip()
                loc = page.get_by_label(clean_name)

            if loc.count():
                target = loc.first
                target.scroll_into_view_if_needed()
                try:
                    target.select_option(label=str(val))
                    return f'combobox "{name}"', str(val), "Selected Option"
                except Exception:
                    # Click dropdown and select matching option text
                    target.click()
                    page.wait_for_timeout(300)
                    opt = page.get_by_role("option", name=str(val)).first
                    if opt.count() and opt.is_visible():
                        opt.click()
                        return f'combobox "{name}"', str(val), "Selected Option"
            return f'combobox "{name}"', str(val), "Not found on page"

        # 3. RADIO BUBBLE
        elif role == "radio":
            loc = page.get_by_role("radio", name=name)
            if loc.count():
                target = loc.first
                target.scroll_into_view_if_needed()
                target.check(force=True)
                return f'radio "{name}"', "Checked", "Selected Bubble"
            return f'radio "{name}"', "", "Not found on page"

        # 4. CHECKBOX
        elif role == "checkbox":
            loc = page.get_by_role("checkbox", name=name)
            if not loc.count():
                loc = page.get_by_label(name)
            if loc.count():
                target = loc.first
                target.scroll_into_view_if_needed()
                target.check(force=True)
                return f'checkbox "{name}"', "Checked", "Checked"
            return f'checkbox "{name}"', "", "Not found on page"

        # 5. FILE UPLOAD
        elif role in ("file", "upload") or "resume" in name.lower() or "cv" in name.lower():
            file_path = str(val).strip()
            if not Path(file_path).exists():
                file_path = profile.get("documents", {}).get("resume_path", "")
            if Path(file_path).exists():
                f_loc = page.locator('input[type="file"]')
                if f_loc.count():
                    f_loc.first.set_input_files(file_path)
                    return f'upload "{name}"', Path(file_path).name, "Uploaded Resume"
            return f'upload "{name}"', file_path, "File Not Found"

    except Exception as e:
        return f'{role} "{name}"', str(val), f"Error: {e}"

    return f'{role} "{name}"', str(val), "Unhandled"


def run_single_page_autofill(page: Page, profile: Dict[str, Any], model: str, debug: bool = False):
    console.print(f"\n[bold green]Inspecting entire page with Native ARIA Engine ({model})...[/bold green]")

    # Scroll down to ensure lazy-loaded elements on long single-page applications are rendered
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(800)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)

    # 1. Native accessibility snapshot covering the whole page
    raw_aria = page.aria_snapshot()
    clean_tree = clean_aria_tree(raw_aria)

    total_elements = len(clean_tree.splitlines())
    console.print(f"[green]Captured full page accessibility tree ({total_elements} interactive elements).[/green]")

    if not clean_tree:
        console.print("[yellow]No accessible interactive elements found on page.[/yellow]")
        return

    # 2. Ask model to match all fields across the entire page
    decision = ask_model(profile, clean_tree, model, debug=debug)
    actions = decision.get("actions", [])

    # 3. Execute all matched fields
    if actions:
        table = Table(title="Autofill Results (Entire Page)")
        table.add_column("Form Element Target", style="magenta")
        table.add_column("Value / Choice", style="green")
        table.add_column("Status", style="cyan")

        for act in actions:
            target, val, status = execute_playwright_action(page, act, profile)
            table.add_row(target, val, status)

        console.print(table)
    else:
        console.print("[yellow]No fields were matched by the model.[/yellow]")

    console.print("\n[bold green]Done filling the page![/bold green] Please review in your browser.")


def main():
    parser = argparse.ArgumentParser(description="Universal Single-Page Full Job Application Autofiller with Ollama")
    parser.add_argument("--url", type=str, default=None, help="Target application URL")
    parser.add_argument("--profile", type=str, default="config/profile.json", help="Path to profile JSON")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model name (default: qwen2.5:3b)")
    parser.add_argument("--cdp-url", type=str, default="http://localhost:9222", help="Chrome DevTools URL if connecting to existing Chrome")
    parser.add_argument("--debug", action="store_true", help="Print full ARIA tree and raw model output")
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.exists():
        console.print(f"[bold red]Profile not found:[/bold red] {profile_path}")
        sys.exit(1)

    profile = load_profile(profile_path)
    console.print(f"[green]Loaded profile for:[/green] [bold]{profile.get('personal', {}).get('full_name', 'Unknown')}[/bold]")

    with sync_playwright() as p:
        browser = None
        context = None
        page = None

        try:
            import urllib.request
            req = urllib.request.Request(f"{args.cdp_url}/json/version")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    console.print(f"[bold green]Connected to existing Chrome session at {args.cdp_url}...[/bold green]")
                    browser = p.chromium.connect_over_cdp(args.cdp_url)
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    page = context.pages[-1] if context.pages else context.new_page()
                    if args.url and page.url != args.url:
                        page.goto(args.url)
        except Exception:
            pass

        if not page:
            console.print("[bold blue]Launching fresh Chromium browser...[/bold blue]")
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            if args.url:
                page.goto(args.url)
            else:
                page.goto("about:blank")
                console.print("[yellow]Navigate to the job application page in the opened browser.[/yellow]")

        console.print("\n[bold]Instructions:[/bold]")
        console.print("1. Ensure the job application page is open in the Chromium window.")
        input("2. Press [Enter] here in the terminal to autofill the ENTIRE page...")

        run_single_page_autofill(page, profile, args.model, debug=args.debug)

        input("\nPress [Enter] in the terminal when done to exit...")


if __name__ == "__main__":
    main()
