import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

from src.config_loader import load_profile, load_rules
from src.browser import BrowserManager
from src.autofiller import AutofillerEngine

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Deterministic Job Application Autofiller")
    parser.add_argument(
        "--profile", 
        type=str, 
        default="config/profile.json", 
        help="Path to your user profile JSON file (defaults to config/profile.json or config/profile.example.json)"
    )
    parser.add_argument(
        "--rules", 
        type=str, 
        default="config/rules.json", 
        help="Path to field matching rules JSON file"
    )
    parser.add_argument(
        "--url", 
        type=str, 
        default=None, 
        help="Optional URL to navigate to (if not already at the job page in your browser)"
    )
    parser.add_argument(
        "--cdp-url", 
        type=str, 
        default="http://localhost:9222", 
        help="Chrome DevTools Protocol URL (default: http://localhost:9222)"
    )
    parser.add_argument(
        "--headless", 
        action="store_true", 
        help="Run browser in headless mode (only applicable if launching standalone Chromium)"
    )
    return parser.parse_args()

def main():
    args = parse_args()

    # Determine profile path
    profile_path = Path(args.profile)
    if not profile_path.exists():
        fallback_profile = Path("config/profile.example.json")
        if fallback_profile.exists():
            console.print(f"[yellow]Warning: '{profile_path}' not found. Using template '{fallback_profile}'. Please create '{profile_path}' with your real details![/yellow]\n")
            profile_path = fallback_profile
        else:
            console.print(f"[bold red]Error:[/bold red] Profile file not found at {profile_path}")
            sys.exit(1)

    try:
        profile = load_profile(profile_path)
        rules = load_rules(args.rules)
    except Exception as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        sys.exit(1)

    browser_mgr = BrowserManager(cdp_url=args.cdp_url)

    try:
        active_info = browser_mgr.get_cdp_active_page_title_and_url()
        if active_info:
            title, url = active_info
            console.print(f"[bold green]Connected to active Chrome tab:[/bold green] [dim]{title}[/dim] ({url})")
        else:
            console.print("[blue]Connecting or launching browser...[/blue]")

        page = browser_mgr.connect_or_launch(target_url=args.url, headless=args.headless)
        engine = AutofillerEngine(profile, rules)
        results = engine.autofill_page(page)

        # Print results table
        table = Table(title="Autofill Execution Report")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Field / Details", style="magenta")
        table.add_column("Value / Status", style="green")

        for f in results["uploaded_files"]:
            table.add_row("Resume Upload", "Resume File", f)

        for f in results["filled_fields"]:
            table.add_row(f"Field ({f['type']})", f["field"], str(f["value"]))

        for s in results["skipped_fields"]:
            table.add_row("Skipped", s["field"], f"[yellow]{s['reason']}[/yellow]")

        for w in results["warnings"]:
            table.add_row("Warning", "-", f"[red]{w}[/red]")

        console.print("\n")
        console.print(table)
        console.print(f"\n[bold green]Autofill complete![/bold green] Total filled: {len(results['filled_fields']) + len(results['uploaded_files'])} | Skipped: {len(results['skipped_fields'])}\n")

    except Exception as e:
        console.print(f"[bold red]Error during autofill:[/bold red] {e}")
    finally:
        browser_mgr.close()

if __name__ == "__main__":
    main()
