import re
from typing import Dict, Any, Optional, Tuple, List
from playwright.sync_api import ElementHandle, Page

class FieldClassifier:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules.get("rules", {})
        self.eeo_synonyms = rules.get("eeo_synonyms", {})

    def extract_element_context(self, element: ElementHandle) -> str:
        """
        Gathers text context for an input element:
        - associated <label> text (by for attribute or wrapping label)
        - name, id, placeholder, aria-label, aria-labelledby, title attributes
        - preceding text or parent header text
        """
        js_code = """
        (el) => {
            const contextPieces = [];
            
            // 1. Direct attributes
            ['name', 'id', 'placeholder', 'aria-label', 'title', 'autocomplete'].forEach(attr => {
                const val = el.getAttribute(attr);
                if (val) contextPieces.push(val);
            });

            // 2. Associated label by 'for'
            const id = el.getAttribute('id');
            if (id) {
                const label = document.querySelector(`label[for="${id}"]`);
                if (label && label.innerText) {
                    contextPieces.push(label.innerText);
                }
            }

            // 3. Closest wrapping label or fieldset legend
            const parentLabel = el.closest('label');
            if (parentLabel && parentLabel.innerText) {
                contextPieces.push(parentLabel.innerText);
            }
            const fieldset = el.closest('fieldset');
            if (fieldset) {
                const legend = fieldset.querySelector('legend');
                if (legend && legend.innerText) {
                    contextPieces.push(legend.innerText);
                }
            }

            // 4. Preceding sibling or parent container label text (common in custom Workday/Greenhouse/Tesla react inputs)
            const parent = el.parentElement;
            if (parent) {
                const prev = el.previousElementSibling;
                if (prev && prev.innerText && prev.innerText.length < 100) {
                    contextPieces.push(prev.innerText);
                }
                const labelInParent = parent.querySelector('label, [class*="label"], [data-automation-id*="label"]');
                if (labelInParent && labelInParent !== el && labelInParent.innerText) {
                    contextPieces.push(labelInParent.innerText);
                }
            }

            // 5. Container / Fieldset group label (e.g. for radio button groups or nested form-item cards)
            const itemContainer = el.closest('[class*="form-item"], [class*="form-group"], [class*="formField"], fieldset, [role="group"]');
            if (itemContainer) {
                const groupLabel = itemContainer.querySelector('label:not([for]), [class*="label"], legend, h3, h4, [class*="header"]');
                if (groupLabel && groupLabel.innerText) {
                    contextPieces.push(groupLabel.innerText);
                } else if (itemContainer.innerText && itemContainer.innerText.length < 250) {
                    contextPieces.push(itemContainer.innerText);
                }
            }

            return contextPieces.join(' ').toLowerCase();
        }
        """
        try:
            return element.evaluate(js_code)
        except Exception:
            return ""

    def classify_field(self, context_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Evaluates the aggregated context text against rules to determine the field key.
        Returns (field_key, rule_data) or None if no match.
        """
        norm_text = " " + re.sub(r"[^a-z0-9]", " ", context_text.lower()) + " "

        best_match = None
        longest_pattern_len = 0

        for field_key, rule in self.rules.items():
            patterns = rule.get("patterns", [])
            exclude_patterns = rule.get("exclude_patterns", [])

            # Check exclusions first
            excluded = False
            for excl in exclude_patterns:
                if f" {excl.lower()} " in norm_text or re.search(r"\b" + re.escape(excl.lower()) + r"\b", norm_text):
                    excluded = True
                    break
            if excluded:
                continue

            # Check matches
            for pattern in patterns:
                pat_lower = pattern.lower()
                if re.search(r"\b" + re.escape(pat_lower) + r"\b", norm_text):
                    # Prioritize more specific (longer) pattern matches
                    if len(pat_lower) > longest_pattern_len:
                        longest_pattern_len = len(pat_lower)
                        best_match = (field_key, rule)

        return best_match
