from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process
import re

class ValueMatcher:
    def __init__(self, rules: Dict[str, Any]):
        self.eeo_synonyms = rules.get("eeo_synonyms", {})

    def match_select_option(self, options: List[Dict[str, str]], target_value: Any, rule_type: Optional[str] = None, field_key: Optional[str] = None) -> Optional[str]:
        """
        Given a list of select options: [{'value': '1', 'text': 'Male'}, ...]
        Finds the best matching option value for target_value.
        """
        if not options:
            return None

        # Filter out empty or placeholder options
        valid_options = [
            opt for opt in options 
            if opt["text"].strip() and not any(p in opt["text"].lower() for p in ["select", "choose", "please pick", "--"])
        ]
        if not valid_options:
            valid_options = options

        # 1. Boolean field matching (Yes / No)
        if isinstance(target_value, bool) or rule_type == "boolean":
            is_true = bool(target_value)
            for opt in valid_options:
                text = opt["text"].strip().lower()
                val = opt["value"].strip().lower()
                if is_true and (text in ["yes", "y", "true", "1"] or val in ["yes", "true", "1"]):
                    return opt["value"]
                elif not is_true and (text in ["no", "n", "false", "0"] or val in ["no", "false", "0"]):
                    return opt["value"]

        # 2. EEO Synonyms matching
        if field_key and field_key in self.eeo_synonyms:
            synonym_dict = self.eeo_synonyms[field_key]
            # Check user target in synonyms
            target_str = str(target_value).strip()
            synonyms_to_match = synonym_dict.get(target_str, [target_str.lower()])

            best_score = 0
            best_opt_val = None

            for opt in valid_options:
                opt_text = opt["text"].lower()
                for syn in synonyms_to_match:
                    score = fuzz.partial_ratio(syn.lower(), opt_text)
                    if syn.lower() in opt_text:
                        score = max(score, 90)
                    if score > best_score:
                        best_score = score
                        best_opt_val = opt["value"]

            if best_score >= 70:
                return best_opt_val

        # 3. Standard fuzzy matching on string
        target_str = str(target_value).strip().lower()
        best_score = 0
        best_opt_val = None

        # Check for integer/number matches like '3' in '3 months' or '3_months'
        if isinstance(target_value, int) or (isinstance(target_value, str) and target_value.isdigit()):
            num_str = str(target_value)
            for opt in valid_options:
                opt_text = opt["text"].strip().lower()
                opt_val = opt["value"].strip().lower()
                if opt_val == f"{num_str}_months" or f"{num_str} month" in opt_text:
                    return opt["value"]

        for opt in valid_options:
            opt_text = opt["text"].strip().lower()
            # Exact or substring match gets high priority
            if target_str == opt_text or target_str == opt["value"].strip().lower():
                return opt["value"]
            if target_str in opt_text:
                score = 85
            else:
                score = fuzz.ratio(target_str, opt_text)

            if score > best_score:
                best_score = score
                best_opt_val = opt["value"]

        if best_score >= 70:
            return best_opt_val

        return None

    def match_radio_option(self, radio_options: List[Dict[str, Any]], target_value: Any, rule_type: Optional[str] = None, field_key: Optional[str] = None) -> Optional[Any]:
        """
        Given a list of radio options: [{'handle': ElementHandle, 'text': 'Male', 'value': '...'}, ...]
        Returns the matching radio option dictionary.
        """
        if not radio_options:
            return None

        # Boolean handling
        if isinstance(target_value, bool) or rule_type == "boolean":
            is_true = bool(target_value)
            for radio in radio_options:
                text = (radio.get("text") or "").strip().lower()
                val = (radio.get("value") or "").strip().lower()
                if is_true and (text in ["yes", "y", "true", "1"] or val in ["yes", "true", "1"]):
                    return radio
                elif not is_true and (text in ["no", "n", "false", "0"] or val in ["no", "false", "0"]):
                    return radio

        # EEO Synonyms handling
        if field_key and field_key in self.eeo_synonyms:
            synonym_dict = self.eeo_synonyms[field_key]
            target_str = str(target_value).strip()
            synonyms_to_match = synonym_dict.get(target_str, [target_str.lower()])

            best_score = 0
            best_radio = None

            for radio in radio_options:
                r_text = (radio.get("text") or "").lower()
                for syn in synonyms_to_match:
                    score = fuzz.partial_ratio(syn.lower(), r_text)
                    if syn.lower() in r_text:
                        score = max(score, 90)
                    if score > best_score:
                        best_score = score
                        best_radio = radio

            if best_score >= 70:
                return best_radio

        # Fuzzy string match
        target_str = str(target_value).strip().lower()
        best_score = 0
        best_radio = None

        for radio in radio_options:
            r_text = (radio.get("text") or "").strip().lower()
            if target_str == r_text:
                return radio
            if target_str in r_text:
                score = 85
            else:
                score = fuzz.ratio(target_str, r_text)
            if score > best_score:
                best_score = score
                best_radio = radio

        if best_score >= 70:
            return best_radio

        return None
