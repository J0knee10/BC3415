"""Small Playwright helpers used to capture the evidence screenshots (Edge, no browser download)."""
import os
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = os.environ.get("N8N_URL", "http://localhost:5678").rstrip("/")
SHOTS = Path(__file__).resolve().parent.parent / "screenshots"


def login_cookie():
    s = requests.Session()
    r = s.post(f"{URL}/rest/login", json={"emailOrLdapLoginId": os.environ["N8N_OWNER_EMAIL"],
                                         "password": os.environ["N8N_OWNER_PASSWORD"]})
    r.raise_for_status()
    return s, [{"name": c.name, "value": c.value, "domain": "localhost", "path": "/"} for c in s.cookies]


class Browser:
    def __init__(self, width=1600, height=900):
        self.pw = sync_playwright().start()
        self.pw.selectors.set_test_id_attribute("data-test-id")  # n8n's attribute name
        self.browser = self.pw.chromium.launch(channel="msedge", headless=True)
        self.session, cookies = login_cookie()
        self.ctx = self.browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        self.ctx.add_cookies(cookies)
        self.page = self.ctx.new_page()

    def redact(self):
        """Mask personal Telegram identifiers (recipient chat id, names, username) wherever they
        appear as a whole text token, e.g. in a Telegram node's output panel. Values come from
        REDACT_TOKENS (comma-separated, set locally), so they are never written into this file."""
        tokens = [t.strip() for t in os.environ.get("REDACT_TOKENS", "").split(",") if t.strip()]
        if not tokens:
            return
        js = """(tokens) => {
            const want = new Set(tokens.flatMap(t => [t, '"' + t + '"']).map(t => t.toLowerCase()));
            const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let n; while ((n = walk.nextNode())) {
                const t = n.textContent.trim().replace(/,$/, '');
                if (want.has(t.toLowerCase())) n.textContent = n.textContent.replace(t, '"<redacted>"');
            }
        }"""
        for frame in self.page.frames:
            try:
                frame.evaluate(js, tokens)
            except Exception:
                pass

    def shot(self, name, full=False, locator=None):
        SHOTS.mkdir(exist_ok=True)
        self.redact()
        path = SHOTS / name
        (locator.screenshot(path=path) if locator else self.page.screenshot(path=path, full_page=full))
        print("saved", path.name)
        return path

    def close(self):
        self.ctx.close()
        self.browser.close()
        self.pw.stop()
