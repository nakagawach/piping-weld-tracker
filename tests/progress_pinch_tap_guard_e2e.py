import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from entry_polygon_area_link_e2e import (  # noqa: E402
    BASE_URL,
    PROJECT_ID,
    run_server,
    save_initial_area,
    seed_database,
    white_png,
)


def dispatch_touch_sequence(page, script):
    page.evaluate(
        """
        ({ script }) => {
          const viewer = document.getElementById('viewer');
          const canvas = document.getElementById('canvas');
          const scale = 1600 / 6000;
          const clientPoint = (ocrX, ocrY) => {
            const rect = canvas.getBoundingClientRect();
            return {
              x: rect.left + (ocrX * scale) * rect.width / canvas.width,
              y: rect.top + (ocrY * scale) * rect.height / canvas.height,
            };
          };
          const makeTouch = (identifier, x, y) => new Touch({
            identifier,
            target: viewer,
            clientX: x,
            clientY: y,
            screenX: x,
            screenY: y,
            pageX: x + window.scrollX,
            pageY: y + window.scrollY,
            radiusX: 2,
            radiusY: 2,
            rotationAngle: 0,
            force: 1,
          });
          const fire = (type, touches, changedTouches) => viewer.dispatchEvent(new TouchEvent(type, {
            bubbles: true,
            cancelable: true,
            touches,
            targetTouches: touches,
            changedTouches,
          }));
          const api = { viewer, canvas, clientPoint, makeTouch, fire };
          Function('api', script)(api);
        }
        """,
        {"script": script},
    )


def main():
    seed_database()
    save_initial_area()
    png = white_png()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                has_touch=True,
                is_mobile=True,
            )
            page = context.new_page()
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-info",
                lambda route: route.fulfill(status=200, content_type="application/json", body='{"pageCount":1}'),
            )
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-page**",
                lambda route: route.fulfill(status=200, content_type="image/png", body=png),
            )

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function("!document.getElementById('canvas').hidden")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '1'"
            )
            expect(page.locator("#progressDialog")).not_to_be_visible()

            # Pinch starts with the first finger on marker 34, zooms, then ends there.
            # This used to reclassify the remaining finger as a fresh single tap and open the dialog.
            dispatch_touch_sequence(
                page,
                """
                const { clientPoint, makeTouch, fire } = api;
                const p = clientPoint(1000, 1000);
                const first = makeTouch(1, p.x, p.y);
                const second = makeTouch(2, p.x + 70, p.y);
                fire('touchstart', [first], [first]);
                fire('touchstart', [first, second], [second]);
                const secondMoved = makeTouch(2, p.x + 120, p.y);
                fire('touchmove', [first, secondMoved], [secondMoved]);
                fire('touchend', [first], [secondMoved]);
                fire('touchend', [], [first]);
                """,
            )
            page.wait_for_timeout(120)
            expect(page.locator("#progressDialog")).not_to_be_visible()
            assert page.locator("#zoomReset").inner_text() != "100%"

            # A normal one-finger tap on the same marker must still open the editor.
            dispatch_touch_sequence(
                page,
                """
                const { clientPoint, makeTouch, fire } = api;
                const p = clientPoint(1000, 1000);
                const touch = makeTouch(3, p.x, p.y);
                fire('touchstart', [touch], [touch]);
                fire('touchend', [], [touch]);
                """,
            )
            expect(page.locator("#progressDialog")).to_be_visible(timeout=3000)
            expect(page.locator("#dialogTarget")).to_contain_text("34")
            page.locator("#closeDialog").click()
            expect(page.locator("#progressDialog")).not_to_be_visible()

            # A one-finger pan beginning on a marker must remain a pan, not a tap.
            dispatch_touch_sequence(
                page,
                """
                const { clientPoint, makeTouch, fire } = api;
                const p = clientPoint(1000, 1000);
                const start = makeTouch(4, p.x, p.y);
                const moved = makeTouch(4, p.x + 30, p.y + 15);
                fire('touchstart', [start], [start]);
                fire('touchmove', [moved], [moved]);
                fire('touchend', [], [moved]);
                """,
            )
            page.wait_for_timeout(120)
            expect(page.locator("#progressDialog")).not_to_be_visible()

            context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_PINCH_ZOOM_RETAINED", True)
    print("PROGRESS_PINCH_END_DOES_NOT_OPEN_MARKER", True)
    print("PROGRESS_SINGLE_TAP_STILL_OPENS_MARKER", True)
    print("PROGRESS_SINGLE_PAN_DOES_NOT_OPEN_MARKER", True)
    print("PROGRESS_PINCH_TAP_GUARD_E2E: PASS")


if __name__ == "__main__":
    main()
