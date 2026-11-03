from pathlib import Path
from typing import Dict, Any, List
from playwright.sync_api import Page, ElementHandle
from rich.console import Console

from src.config_loader import UserProfile
from src.classifier import FieldClassifier
from src.matcher import ValueMatcher

console = Console()

class AutofillerEngine:
    def __init__(self, profile: UserProfile, rules: Dict[str, Any]):
        self.profile = profile
        self.rules = rules
        self.classifier = FieldClassifier(rules)
        self.matcher = ValueMatcher(rules)

    def autofill_page(self, page: Page) -> Dict[str, Any]:
        """
        Scans and autofills inputs on the given page:
        1. Resume / File uploads
        2. Text, Email, Tel, and Textarea inputs
        3. Dropdowns (<select>)
        4. Radio button groups
        """
        results = {
            "uploaded_files": [],
            "filled_fields": [],
            "skipped_fields": [],
            "warnings": []
        }

        console.print("[bold cyan]Scanning page for application fields...[/bold cyan]")

        # 1. Upload Resume
        self._upload_resume(page, results)

        # 2. Fill Text, Email, Tel, and Textarea inputs
        self._fill_text_inputs(page, results)

        # 3. Fill Dropdowns (<select>)
        self._fill_select_dropdowns(page, results)

        # 4. Fill Radio button groups
        self._fill_radio_groups(page, results)

        return results

    def _upload_resume(self, page: Page, results: Dict[str, Any]):
        resume_path = self.profile.documents.resume_path
        if not resume_path:
            return

        file_obj = Path(resume_path).expanduser().resolve()
        if not file_obj.exists():
            results["warnings"].append(f"Resume file does not exist at: {resume_path}")
            return

        try:
            file_inputs = page.query_selector_all('input[type="file"]')
            for finput in file_inputs:
                ctx = self.classifier.extract_element_context(finput)
                # Check if it's meant for resume / cv
                if any(k in ctx for k in ["resume", "cv", "curriculum", "attach", "upload"]):
                    console.print(f"[green]Uploading resume to matching input...[/green]")
                    finput.set_input_files(str(file_obj))
                    results["uploaded_files"].append(str(file_obj))
                    return

            # Fallback: if only one file input is present on the page, assume it's the resume
            if len(file_inputs) == 1:
                console.print(f"[green]Uploading resume to the single file input on page...[/green]")
                file_inputs[0].set_input_files(str(file_obj))
                results["uploaded_files"].append(str(file_obj))
        except Exception as e:
            results["warnings"].append(f"Failed to upload resume: {e}")

    def _fill_text_inputs(self, page: Page, results: Dict[str, Any]):
        selector = 'input:not([type="hidden"]):not([type="file"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]), textarea'
        inputs = page.query_selector_all(selector)

        for el in inputs:
            try:
                # Skip if already filled and not empty
                current_val = el.input_value()
                if current_val and current_val.strip():
                    continue

                ctx = self.classifier.extract_element_context(el)
                match = self.classifier.classify_field(ctx)
                if not match:
                    continue

                field_key, rule = match
                path = rule.get("field_path")
                val = self.profile.get_nested_value(path)

                if val is not None and str(val).strip():
                    # Check if this input is a datepicker (like Tesla / TDS datepicker)
                    if field_key in ["start_date", "anticipated_graduation_date"] or "date" in (el.get_attribute("class") or ""):
                        if self._handle_tesla_datepicker(page, el, str(val)):
                            results["filled_fields"].append({
                                "field": field_key,
                                "type": "datepicker",
                                "value": str(val)
                            })
                            continue

                    el.fill(str(val))
                    # Trigger standard DOM change / input events
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                    results["filled_fields"].append({
                        "field": field_key,
                        "type": "text",
                        "value": str(val)
                    })
            except Exception as e:
                continue

    def _handle_tesla_datepicker(self, page: Page, el: ElementHandle, date_str: str) -> bool:
        """
        Handles interactive calendar datepickers (such as Tesla's TDS design system).
        e.g., date_str: '12/17/2027' or '05/17/2027'
        """
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%m/%d/%Y")
            target_month_str = dt.strftime("%B %Y") # e.g. "December 2027"
            target_day_str = str(dt.day)             # e.g. "17"

            # Open calendar associated with this input
            parent_handle = el.evaluate_handle("el => el.parentElement")
            cal_btn = parent_handle.as_element().query_selector("button:has(svg.tds-icon-calendar), button.tds-icon-btn")
            if cal_btn and cal_btn.is_visible():
                cal_btn.click()
                page.wait_for_timeout(300)

            # Look up open date picker
            picker = page.locator(".tds-date-picker").last
            if not picker.is_visible():
                return False

            month_label = picker.locator(".tds-date-picker-month label")
            next_btn = picker.locator("button:has(svg.tds-icon-chevron-small-90)")

            for _ in range(36):
                if month_label.is_visible() and target_month_str.lower() in month_label.inner_text().lower():
                    break
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(80)

            # Click the matching day in current month
            day_btn = picker.locator(f".tds-date-picker-days-grid button:not(.tds-day--not-this-month):has-text(\"{target_day_str}\")").first
            if day_btn.is_visible():
                day_btn.click()
                page.wait_for_timeout(200)
                return True
        except Exception:
            pass
        return False

    def _fill_select_dropdowns(self, page: Page, results: Dict[str, Any]):
        selects = page.query_selector_all("select")
        for sel in selects:
            try:
                ctx = self.classifier.extract_element_context(sel)
                match = self.classifier.classify_field(ctx)
                if not match:
                    continue

                field_key, rule = match
                path = rule.get("field_path")
                val = self.profile.get_nested_value(path)
                if val is None:
                    continue

                # Extract options from DOM
                options = sel.evaluate("""
                    (s) => Array.from(s.options).map(o => ({
                        value: o.value,
                        text: o.text || o.innerText
                    }))
                """)

                best_opt_val = self.matcher.match_select_option(
                    options, 
                    val, 
                    rule_type=rule.get("type"), 
                    field_key=field_key
                )

                if best_opt_val is not None:
                    sel.select_option(value=best_opt_val)
                    sel.evaluate("""el => {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""")
                    results["filled_fields"].append({
                        "field": field_key,
                        "type": "select",
                        "value": best_opt_val
                    })
                else:
                    results["skipped_fields"].append({
                        "field": field_key,
                        "reason": f"No matching option found for value: '{val}'"
                    })
            except Exception as e:
                continue

    def _fill_radio_groups(self, page: Page, results: Dict[str, Any]):
        radios = page.query_selector_all('input[type="radio"]')
        # Group radios by name attribute or enclosing fieldset/container
        groups: Dict[str, List[ElementHandle]] = {}
        for r in radios:
            try:
                name = r.get_attribute("name") or "unnamed_group"
                groups.setdefault(name, []).append(r)
            except Exception:
                continue

        for group_name, group_radios in groups.items():
            try:
                # Use context of the first radio or fieldset to classify the group
                ctx = self.classifier.extract_element_context(group_radios[0])
                match = self.classifier.classify_field(ctx)
                if not match:
                    continue

                field_key, rule = match
                path = rule.get("field_path")
                val = self.profile.get_nested_value(path)
                if val is None:
                    continue

                # Build radio option data
                radio_options = []
                for r in group_radios:
                    # Look up label text for this specific radio
                    r_text = r.evaluate("""
                        (el) => {
                            const id = el.getAttribute('id');
                            if (id) {
                                const l = document.querySelector(`label[for="${id}"]`);
                                if (l && l.innerText) return l.innerText;
                            }
                            const parentL = el.closest('label');
                            if (parentL && parentL.innerText) return parentL.innerText;
                            const next = el.nextElementSibling;
                            if (next && next.innerText) return next.innerText;
                            return el.value || '';
                        }
                    """)
                    radio_options.append({
                        "handle": r,
                        "text": r_text,
                        "value": r.get_attribute("value") or ""
                    })

                matched_radio = self.matcher.match_radio_option(
                    radio_options,
                    val,
                    rule_type=rule.get("type"),
                    field_key=field_key
                )

                if matched_radio:
                    matched_radio["handle"].check()
                    matched_radio["handle"].dispatch_event("change")
                    results["filled_fields"].append({
                        "field": field_key,
                        "type": "radio",
                        "value": matched_radio["text"] or matched_radio["value"]
                    })
                else:
                    results["skipped_fields"].append({
                        "field": field_key,
                        "reason": f"No matching radio option for value: '{val}'"
                    })
            except Exception:
                continue
