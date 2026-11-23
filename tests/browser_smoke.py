"""Exercise the built starter at a project subpath in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import json
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    screenshots = ROOT / "browser-checks"
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT / "dist", Path(temporary) / "example-tool")
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temporary))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/example-tool/")
                config = json.loads((ROOT / 'web/config.json').read_text())
                index = json.loads((ROOT / 'web/data/index.json').read_text())
                data = json.loads((ROOT / 'web/data' / index['captures'][0]['file']).read_text())
                sample = max(data['records'], key=lambda r: float(r['impact-e']))
                page.wait_for_function("document.querySelector('#count').textContent !== '—'")
                assert page.locator("#rows tr").count() == min(max(5,min(100,config["pageSize"])),len(data["records"]))
                page.get_by_role("button",name="Missing coordinates",exact=True).click()
                assert page.locator("#mapped").inner_text() == "0"
                assert page.locator("#points circle").count() == 0
                assert int(page.locator("#count").inner_text().replace(",","")) == sum(r["lat"] is None for r in data["records"])
                page.get_by_role("button",name="Reset filters",exact=True).click()
                page.locator("#search").fill(sample["date"])
                assert page.locator("#count").inner_text() == "1"
                page.locator("#rows button").first.click()
                assert sample["date"] in page.locator("#event-title").inner_text()
                assert sample["impact-e"] in page.locator("#event-raw").text_content()
                with page.expect_download() as download:
                    page.locator("#csv").click()
                assert download.value.suggested_filename.endswith(".csv")
                page.locator("#search").fill("<img src=x>")
                assert page.locator("#count").inner_text() == "0"
                assert page.locator("#empty").is_visible()
                assert page.locator("img").count() == 0
                page.get_by_role("button",name="Reset filters",exact=True).click()
                page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            print("Browser checks passed: project subpath, real catalogue, missing locations, event inspection, CSV, safe filters and mobile layout")
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
