# Job Application Autofiller

A deterministic, rule-based job application autofiller built with Python and Playwright. It reads your active browser tab via Chrome DevTools Protocol (CDP) or standalone browser automation, matches input fields with fuzzy keyword recognition, and uploads your resume directly from your local disk without browser sandbox restrictions.

---

## Features
- **Local Resume File Upload**: Direct upload to standard and hidden file input fields (`.pdf`, `.docx`).
- **Contact & Personal Info**: First name, last name, email, phone, location/address fields.
- **Profiles & Links**: LinkedIn, GitHub, portfolio/personal site, Twitter.
- **Work Authorization & Legal**: Deterministic answers to legal eligibility and visa sponsorship.
- **EEO & Demographics**: Accurate matching for Gender, Race/Ethnicity, Veteran Status, and Disability Status using fuzzy keyword & synonym matching.
- **Chrome CDP Integration**: Operates directly on your open, logged-in Chrome tab on macOS.

---

## Quick Setup

### 1. Set Up Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Profile
Copy the example profile to create your own configuration:
```bash
cp config/profile.example.json config/profile.json
```
Edit [`config/profile.json`](config/profile.json) with your real details and set `"resume_path"` to the absolute path of your resume PDF.

---

## Usage Modes

### Mode 1: Active Chrome Tab (Recommended)
This mode lets you browse jobs manually, log into portals, pass any CAPTCHA/bot checks, and autofill the active page with one command.

1. Launch Chrome with remote debugging:
   ```bash
   ./launch_chrome_debug.sh
   ```
2. Navigate to any job application portal in that Chrome window (Workday, Greenhouse, Lever, Ashby, etc.).
3. Run the autofiller:
   ```bash
   source .venv/bin/activate
   python main.py
   ```
   The autofiller will automatically detect the active tab, upload your resume, match inputs, select dropdowns/radios, and print an execution report.

---

### Mode 2: Standalone URL Mode
You can also launch a browser window directly targeting a specific URL:
```bash
python main.py --url "https://boards.greenhouse.io/<company>/jobs/<id>"
```

---

## Configuration & Rules

- **User Profile**: Configured in [`config/profile.json`](config/profile.json).
- **Matching Rules & Synonyms**: Configured in [`config/rules.json`](config/rules.json). You can easily add company-specific phrasing or custom field aliases without modifying python code.
