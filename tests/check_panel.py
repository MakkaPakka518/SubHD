"""Start the real panel and verify desktop/mobile interactions in Chromium."""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from patchright.sync_api import sync_playwright

TOKEN = "test6!"
BASE = "http://127.0.0.1:8767"


def main(output):
    root = Path(__file__).resolve().parents[1]
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8767"],
                              cwd=root, env={**os.environ, "API_TOKEN": TOKEN})
    try:
        for attempt in range(50):
            try:
                urllib.request.urlopen(BASE + "/health", timeout=1).close()
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Panel did not start")
        if output:
            output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for name, width, height in [("desktop", 1440, 960), ("mobile", 390, 844), ("narrow", 320, 760)]:
                    context = browser.new_context(viewport={"width": width, "height": height},
                                                  permissions=["clipboard-read", "clipboard-write"],
                                                  is_mobile=width < 640, has_touch=width < 640)
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(BASE)
                    assert page.locator("#admin-token").get_attribute("minlength") == "6"
                    page.locator("#admin-token").fill("incorrect-token-long-enough-123")
                    page.locator("#login-submit").click()
                    page.locator("#login-error").wait_for(state="visible")
                    assert "不正确" in page.locator("#login-error").inner_text()
                    page.locator("#admin-token").fill(TOKEN)
                    page.locator("#show-token").click()
                    assert page.locator("#admin-token").get_attribute("type") == "text"
                    page.locator("#show-token").click()
                    page.locator("#login-submit").click()
                    page.locator("#workspace").wait_for(state="visible")
                    module_url = page.locator("#module-url").input_value()
                    assert module_url.startswith(BASE + "/widget.js?key=") and TOKEN not in module_url
                    page.locator("#copy-link").click()
                    assert page.evaluate("navigator.clipboard.readText()") == module_url
                    assert page.locator("#toast").inner_text() == "模块链接已复制"
                    module = context.request.get(module_url)
                    assert module.ok and TOKEN not in module.text() and "__MODULE_TOKEN__" not in module.text()
                    page.locator("#refresh").click()
                    page.locator("#refresh:not([disabled])").wait_for(state="attached")
                    page.locator("#help summary").click()
                    assert page.locator("#help").get_attribute("open") is not None
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    if width < 640:
                        for selector in ["#copy-link", "#refresh", "#logout", "#help summary", "#download-module", ".footer a"]:
                            box = page.locator(selector).bounding_box()
                            assert box["height"] >= 48, (selector, box)
                    page.evaluate("scrollTo(0, 0)")
                    if output:
                        page.screenshot(path=str(output / (name + ".png")), full_page=True)
                    page.locator("#logout").click()
                    page.locator("#login").wait_for(state="visible")
                    assert not page.locator("#workspace").is_visible()
                    assert not errors, errors
                    context.close()
                print("Panel checks passed: desktop 1440, mobile 390, narrow 320")
            finally:
                browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    main(parser.parse_args().screenshots)
