import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

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


def assert_canvas_overlay_aligned(page, tolerance=1.5):
    base = page.locator('#canvas').bounding_box()
    overlay = page.locator('#entryAreaCanvas').bounding_box()
    assert base and overlay
    for key in ('x', 'y', 'width', 'height'):
        delta = abs(base[key] - overlay[key])
        assert delta <= tolerance, (key, base, overlay, delta)


def main():
    seed_database()
    save_initial_area()
    png = white_png()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.route(
                f'**/projects/{PROJECT_ID}/pdfium-info',
                lambda route: route.fulfill(status=200, content_type='application/json', body='{"pageCount":1}'),
            )
            page.route(
                f'**/projects/{PROJECT_ID}/pdfium-page**',
                lambda route: route.fulfill(status=200, content_type='image/png', body=png),
            )

            page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/entry?page=1', wait_until='domcontentloaded')
            page.wait_for_function("document.getElementById('entryAreaCanvas')?.dataset.areaCount === '1'")
            assert_canvas_overlay_aligned(page)

            page.locator('#entryZoomIn').click()
            page.wait_for_function("parseFloat(document.getElementById('canvas').dataset.entryZoom || '1') >= 1.19")
            page.wait_for_timeout(100)
            assert_canvas_overlay_aligned(page)

            viewer = page.locator('.viewer').bounding_box()
            assert viewer
            page.mouse.move(viewer['x'] + viewer['width'] / 2, viewer['y'] + viewer['height'] / 2)
            page.keyboard.down('Control')
            page.mouse.wheel(0, -120)
            page.keyboard.up('Control')
            page.wait_for_function("parseFloat(document.getElementById('canvas').dataset.entryZoom || '1') > 1.2")
            page.wait_for_timeout(100)
            assert_canvas_overlay_aligned(page)

            page.locator('#entryZoomReset').click()
            page.wait_for_function("Math.abs(parseFloat(document.getElementById('canvas').dataset.entryZoom || '0') - 1) < 0.01")
            page.wait_for_timeout(100)
            assert_canvas_overlay_aligned(page)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print('ENTRY_ZOOM_OVERLAY_ALIGNMENT: PASS')


if __name__ == '__main__':
    main()
