import time
from playwright.sync_api import expect, sync_playwright
from ui_shell_e2e import BASE_URL, PROJECT_ID, run_server, seed_database

def run_context(browser, width, height, mobile=False, touch=False):
    context = browser.new_context(viewport={'width':width,'height':height}, is_mobile=mobile, has_touch=touch)
    page = context.new_page()
    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=1', wait_until='networkidle')
    expect(page.locator('[data-ui3-header="progress"]')).to_be_visible()
    expect(page.locator('[data-ui3-header="progress"] .ui3-switch')).to_have_attribute('href', f'/projects/{PROJECT_ID}/entry?page=1')
    expect(page.locator('#prev')).to_be_disabled()
    before = page.locator('#status').inner_text()
    req=[]
    page.on('request', lambda r: req.append(r.url) if ('progress-data?page=' in r.url or ('pdfium-page?' in r.url and 'format=png' in r.url)) else None)
    page.locator('#prev').click(force=True)
    page.wait_for_timeout(250)
    assert not req, f'P1 prev caused reload: {req}'
    assert page.locator('#status').inner_text() == before
    expect(page.locator('#drawingMemoLaunch')).to_have_count(1)

    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/entry?page=1', wait_until='networkidle')
    expect(page.locator('[data-ui3-header="entry"]')).to_be_visible()
    expect(page.locator('[data-ui3-header="entry"] .ui3-switch')).to_have_attribute('href', f'/projects/{PROJECT_ID}/progress?page=1')
    expect(page.locator('#bboxEdit')).to_have_count(1)
    expect(page.locator('#zoomOut')).to_have_count(1)
    expect(page.locator('#zoomReset')).to_have_count(1)
    expect(page.locator('#zoomIn')).to_have_count(1)
    expect(page.locator('#viewReset')).to_have_count(1)
    expect(page.locator('#fullscreen')).to_have_count(1)
    expect(page.locator('#ocr')).to_be_visible()
    expect(page.locator('#save')).to_be_visible()
    context.close()

def main():
    seed_database(); server, thread = run_server(); time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            run_context(browser, 1440, 900)
            run_context(browser, 390, 844, True, True)
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=2)
    print('Unified Progress/Entry regression: PASS')
if __name__ == '__main__': main()
