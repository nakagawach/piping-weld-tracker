import base64
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE_URL = "http://127.0.0.1:8767"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


def memo_path(page_number):
    return DB_PATH.parent / "drawing_memos" / f"project-{PROJECT_ID}-page-{page_number}.json"


def cleanup():
    for page_number in (1, 2, 3):
        path = memo_path(page_number)
        if path.exists():
            path.unlink()


def run_server():
    server = make_server("127.0.0.1", 8767, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def install_pdf_routes(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"pageCount":3}',
        ),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda route: route.fulfill(
            status=200,
            content_type="image/png",
            body=PNG_1X1,
        ),
    )


def draw_stroke(page, start_ratio=0.35, end_ratio=0.65):
    overlay = page.locator("#drawingMemoCanvas")
    box = overlay.bounding_box()
    assert box and box["width"] > 20 and box["height"] > 20, box
    y = box["y"] + box["height"] * 0.5
    page.mouse.move(box["x"] + box["width"] * start_ratio, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * end_ratio, y, steps=8)
    page.mouse.up()


def alpha_sum(page):
    return page.locator("#drawingMemoCanvas").evaluate(
        """canvas => {
            const ctx=canvas.getContext('2d');
            const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;
            let total=0;
            for(let i=3;i<data.length;i+=4) total+=data[i];
            return total;
        }"""
    )


def memo_json(page, page_number):
    response = page.request.get(f"{BASE_URL}/projects/{PROJECT_ID}/drawing-memo?page={page_number}")
    assert response.ok, response.text()
    return response.json()


def main():
    seed_database()
    cleanup()
    server, thread = run_server()
    time.sleep(0.2)
    artifacts = ROOT / "test-artifacts"
    artifacts.mkdir(exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            desktop = browser.new_page(viewport={"width": 1440, "height": 900})
            install_pdf_routes(desktop)
            desktop.goto(
                f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
                wait_until="domcontentloaded",
            )
            desktop.wait_for_selector("#drawingMemoCanvas")
            desktop.wait_for_function(
                "document.querySelector('#drawingMemoCanvas').dataset.memoPage === '1'"
            )

            launch = desktop.locator("#drawingMemoLaunch")
            edit = desktop.locator("#drawingMemoEdit")
            overlay = desktop.locator("#drawingMemoCanvas")
            expect(launch).to_be_visible()
            expect(edit).to_be_visible()
            assert overlay.evaluate("el => getComputedStyle(el).pointerEvents") == "none"
            expect(desktop.locator("#drawingMemoTools")).not_to_have_class("open")

            edit.click()
            expect(desktop.locator("#drawingMemoTools")).to_have_class("drawing-memo-tools open")
            assert overlay.evaluate("el => getComputedStyle(el).pointerEvents") == "auto"
            draw_stroke(desktop)
            assert overlay.get_attribute("data-memo-stroke-count") == "1"
            expect(desktop.locator("#memoDirty")).to_have_text("未保存")
            assert not desktop.locator("#memoUndo").is_disabled()
            assert not desktop.locator("#memoSave").is_disabled()

            desktop.locator("#memoUndo").click()
            assert overlay.get_attribute("data-memo-stroke-count") == "0"
            assert not desktop.locator("#memoRedo").is_disabled()
            desktop.locator("#memoRedo").click()
            assert overlay.get_attribute("data-memo-stroke-count") == "1"

            desktop.locator("#memoSave").click()
            desktop.wait_for_function(
                "document.querySelector('#memoDirty').textContent === '' && "
                "getComputedStyle(document.querySelector('#drawingMemoCanvas')).pointerEvents === 'none'"
            )
            saved = memo_json(desktop, 1)
            assert len(saved["strokes"]) == 1, saved
            assert alpha_sum(desktop) > 0

            launch.click()
            assert overlay.evaluate("el => getComputedStyle(el).visibility") == "hidden"
            launch.click()
            assert overlay.evaluate("el => getComputedStyle(el).visibility") == "visible"

            edit.click()
            draw_stroke(desktop, 0.25, 0.75)
            assert overlay.get_attribute("data-memo-stroke-count") == "2"
            desktop.once("dialog", lambda dialog: dialog.accept())
            desktop.locator("#next").click()
            desktop.wait_for_function(
                "document.getElementById('page').value === '2' && "
                "document.querySelector('#drawingMemoCanvas').dataset.memoPage === '2'"
            )
            assert overlay.get_attribute("data-memo-stroke-count") == "0"
            saved = memo_json(desktop, 1)
            assert len(saved["strokes"]) == 2, saved
            assert memo_json(desktop, 2)["strokes"] == []

            desktop.locator("#prev").click()
            desktop.wait_for_function(
                "document.getElementById('page').value === '1' && "
                "document.querySelector('#drawingMemoCanvas').dataset.memoPage === '1'"
            )
            assert overlay.get_attribute("data-memo-stroke-count") == "2"
            assert alpha_sum(desktop) > 0

            edit.click()
            desktop.screenshot(path=str(artifacts / "drawing-memo-desktop.png"), full_page=True)
            edit.click()

            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                screen={"width": 390, "height": 844},
                device_scale_factor=2.75,
                is_mobile=True,
                has_touch=True,
                user_agent=(
                    "Mozilla/5.0 (Linux; Android 16; Pixel 7 Pro) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
                ),
            ).new_page()
            install_pdf_routes(mobile)
            mobile.goto(
                f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
                wait_until="domcontentloaded",
            )
            mobile.wait_for_selector("#drawingMemoCanvas")
            mobile.wait_for_function(
                "document.querySelector('#drawingMemoCanvas').dataset.memoPage === '1'"
            )
            mobile.locator("#drawingMemoEdit").tap()
            assert mobile.locator("#drawingMemoCanvas").evaluate(
                "el => getComputedStyle(el).pointerEvents"
            ) == "auto"
            expect(mobile.locator("#drawingMemoTools")).to_have_class("drawing-memo-tools open")
            mobile.locator("#drawingMemoEdit").tap()
            assert mobile.locator("#drawingMemoCanvas").evaluate(
                "el => getComputedStyle(el).pointerEvents"
            ) == "none"
            expect(mobile.locator("[data-ui3-header='progress']")).to_be_visible()
            mobile.screenshot(path=str(artifacts / "drawing-memo-mobile.png"), full_page=True)

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        cleanup()

    print("DRAWING_MEMO_BROWSER_E2E: PASS")


if __name__ == "__main__":
    main()
