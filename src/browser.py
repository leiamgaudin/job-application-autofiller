from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import urllib.request
import json
from typing import Optional, Tuple

CDP_DEFAULT_URL = "http://localhost:9222"

class BrowserManager:
    def __init__(self, cdp_url: str = CDP_DEFAULT_URL):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser = None
        self._context = None
        self.is_cdp = False

    def is_cdp_available(self) -> bool:
        """Check if Chrome is running with remote debugging port active."""
        try:
            req = urllib.request.Request(f"{self.cdp_url}/json/version")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_cdp_active_page_title_and_url(self) -> Optional[Tuple[str, str]]:
        """Get the title and URL of the active tab from CDP endpoint."""
        try:
            req = urllib.request.Request(f"{self.cdp_url}/json/list")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                tabs = json.loads(resp.read().decode())
                # Find the first page type tab
                for tab in tabs:
                    if tab.get("type") == "page":
                        return tab.get("title", ""), tab.get("url", "")
        except Exception:
            pass
        return None

    def connect_or_launch(self, target_url: Optional[str] = None, headless: bool = False) -> Page:
        """
        Connects to an existing Chrome instance via CDP if available.
        Otherwise launches a new Chromium browser window.
        """
        self._playwright = sync_playwright().start()

        if self.is_cdp_available():
            print(f"Connecting to active Chrome session at {self.cdp_url}...")
            self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
            self.is_cdp = True
            
            # Use the existing context and active page
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                if pages:
                    # Pick the last focused / active page
                    page = pages[-1]
                    if target_url and page.url != target_url:
                        page.goto(target_url)
                    return page
            
            # If no existing pages, create one
            page = self._browser.new_page()
            if target_url:
                page.goto(target_url)
            return page
        else:
            print("Chrome CDP not detected. Launching managed Chromium browser...")
            self._browser = self._playwright.chromium.launch(headless=headless)
            self._context = self._browser.new_context()
            page = self._context.new_page()
            if target_url:
                page.goto(target_url)
            return page

    def close(self):
        # If we connected over CDP, we disconnect rather than terminating the user's Chrome!
        if self._browser:
            if self.is_cdp:
                self._browser.close() # Playwright disconnects from CDP session
            else:
                self._browser.close()
        if self._playwright:
            self._playwright.stop()
