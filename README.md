# Job Application Autofiller

An intelligent, cross-portal job application autofiller built with Python, Playwright, and local Ollama AI models. It supports both **deterministic rule-based matching** and **locally hosted LLM-powered autofill** using Playwright's native Accessibility (ARIA) tree.

Works across major applicant tracking systems including **Workday, Greenhouse, Lever, Ashby, Taleo**, and custom job portals.

---

## Key Features

- **Local LLM Engine (`ai_autofiller.py`)**: Uses local models like `qwen2.5:3b` via Ollama for zero data-leakage, offline AI inference.
- **Universal Accessibility (ARIA) Tree**: Reads the page semantically using Playwright's native ARIA snapshot instead of fragile CSS selectors or custom DOM scrapers.
- **Single-Pass Full Page Fill**: Inspects and populates all fields across the entire application form (personal details, address, phone, work authorization, EEO/demographics, and resume upload).
- **Deterministic Engine (`main.py`)**: Rule-based matching engine using fuzzy string matching (`rapidfuzz`) and customizable dictionary rules (`rules.json`).
- **Direct Resume Upload**: Directly attaches local `.pdf` / `.docx` files to file inputs on the page.
- **Phone & Field Sanitization**: Automatically handles phone numbers, stripping invalid prefixes like `+1` where strict national digit formatting is enforced.
- **Anti-AI Detection Guardrails**: Explicitly ignores and skips open-ended essay questions (e.g., *"Why do you want to work here?"*) to prevent applications from being flagged by automated AI detectors.
- **Chrome CDP Integration**: Connects directly to an existing, authenticated Chrome session or launches a fresh Chromium window.

---

## Quick Setup

### 1. Set Up Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Install & Start Ollama (for AI Autofiller)
1. Install Ollama:
   ```bash
   brew install ollama
   ```
   *(Or download from [ollama.com](https://ollama.com/download))*

2. Pull the recommended lightweight model:
   ```bash
   ollama pull qwen2.5:3b
   ```

### 3. Configure Your Profile
Copy the example profile template:
```bash
cp config/profile.example.json config/profile.json
```
Edit [`config/profile.json`](config/profile.json) with your details and verify `documents.resume_path` points to your resume PDF.

> **Note**: `config/profile.json` is ignored by `.gitignore` so your personal information is never committed.

---

## Usage

### Option A: AI Autofiller with Ollama (Recommended)
Reads the live page via the native ARIA tree and matches fields using your locally hosted Ollama model.

```bash
source .venv/bin/activate
python ai_autofiller.py
```

- Launches a browser window (or connects to an active Chrome CDP session).
- Navigate to the application form.
- Press **Enter** in the terminal: the AI will read and autofill the entire page.

#### Optional CLI Flags:
```bash
# Specify target URL directly
python ai_autofiller.py --url "https://job-board-url.com"

# Use a different Ollama model (e.g., llama3.2:3b)
python ai_autofiller.py --model "llama3.2:3b"

# Enable debug mode to see the live ARIA tree and raw model output
python ai_autofiller.py --debug
```

---

### Option B: Deterministic Rule-Based Autofiller
Uses predefined keyword rules in `config/rules.json` and fuzzy matching.

#### 1. Active Chrome Session (via CDP)
Allows you to log into portals, pass CAPTCHA/bot checks, and autofill the active tab:
```bash
./launch_chrome_debug.sh
```
In your terminal:
```bash
python main.py
```

#### 2. Standalone Browser Mode
```bash
python main.py --url "https://boards.greenhouse.io/<company>/jobs/<id>"
```

---

## Project Structure

```
├── ai_autofiller.py           # Local LLM autofiller using Playwright ARIA engine
├── main.py                    # Deterministic rule-based autofiller CLI entrypoint
├── launch_chrome_debug.sh     # Launch script for Chrome with remote debugging (CDP)
├── requirements.txt           # Python dependencies
├── config/
│   ├── profile.example.json   # Template for user profile configuration
│   ├── profile.json           # Your local private profile (git-ignored)
│   └── rules.json             # Fuzzy keyword rules and synonyms
└── src/
    ├── autofiller.py          # Deterministic execution engine
    ├── browser.py             # Playwright & CDP session manager
    ├── classifier.py          # DOM element classification
    ├── config_loader.py       # Pydantic schema validation for profile & rules
    └── matcher.py             # Value matching logic (Rapidfuzz)
```
