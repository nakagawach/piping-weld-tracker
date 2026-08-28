import os
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get('PUBLIC_BASE_URL','https://nakagawach.pythonanywhere.com/weld').rstrip('/')
PROJECT_ID=int(os.environ.get('PUBLIC_PROJECT_ID','7'))

def text(page):
    return page.locator('#status').inner_text() if page.locator('#status').count() else ''

def relevant(url):
    return ('/progress-data?page=' in url) or ('/pdfium-page?' in url)

def check_progress(page, failures, label):
    requests=[]
    page.on('request', lambda req: requests.append(req.url) if relevant(req.url) else None)
    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=1',wait_until='networkidle',timeout=30000)
    page.wait_for_timeout(500)

    current=page.locator('.progress-thumb.active')
    if current.count()!=1:
        failures.append(f'{label}: progress active thumbnail count={current.count()}')
        return
    before=text(page); requests.clear()
    current.tap()
    page.wait_for_timeout(700)
    after=text(page)
    if requests:
        failures.append(f'{label}: current thumbnail caused requests: {requests}')
    if '読み込み中' in after or after!=before:
        failures.append(f'{label}: current thumbnail changed status: before={before!r} after={after!r}')

    before=text(page); requests.clear()
    page.locator('#prev').tap(force=True)
    page.wait_for_timeout(500)
    after=text(page)
    if requests:
        failures.append(f'{label}: first-page prev caused requests: {requests}')
    if '読み込み中' in after or after!=before:
        failures.append(f'{label}: first-page prev changed status: before={before!r} after={after!r}')

    page_count=int(page.locator('#pageTotal').inner_text().replace('/','').strip())
    if page_count>1:
        requests.clear(); page.locator('.progress-thumb').nth(page_count-1).tap(); page.wait_for_timeout(1000)
        before=text(page); requests.clear()
        page.locator('#next').tap(force=True); page.wait_for_timeout(500)
        after=text(page)
        if requests:
            failures.append(f'{label}: last-page next caused requests: {requests}')
        if '読み込み中' in after or after!=before:
            failures.append(f'{label}: last-page next changed status: before={before!r} after={after!r}')

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        failures=[]

        desktop=browser.new_context(viewport={'width':1280,'height':800},has_touch=False)
        desktop_page=desktop.new_page()
        check_progress(desktop_page,failures,'desktop')
        desktop.close()

        mobile=browser.new_context(
            viewport={'width':390,'height':844},
            screen={'width':390,'height':844},
            device_scale_factor=2.75,
            is_mobile=True,
            has_touch=True,
            user_agent='Mozilla/5.0 (Linux; Android 16; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36'
        )
        page=mobile.new_page()
        check_progress(page,failures,'android-touch')

        for route, header in [
            (f'/projects/{PROJECT_ID}/entry?page=1','entry'),
            (f'/projects/{PROJECT_ID}/progress-list','progress-list'),
            (f'/projects/{PROJECT_ID}/thumbnails?source=progress&page=1','thumbnails'),
            (f'/projects/{PROJECT_ID}/thumbnails?source=entry&page=1','thumbnails'),
            ('/favorites','favorites'),
            ('/projects-screen','projects'),
        ]:
            page.goto(BASE_URL+route,wait_until='domcontentloaded',timeout=30000)
            page.wait_for_timeout(300)
            if header=='projects':
                if page.locator('.header.ui3-root').count()!=1: failures.append('android-touch: projects header missing')
            else:
                if page.locator(f'[data-ui3-header="{header}"]').count()!=1: failures.append(f'android-touch: {route} header missing')

        mobile.close(); browser.close()
        if failures:
            raise AssertionError('\n'.join(failures))
        print('Public navigation regression: PASS')

if __name__=='__main__':
    main()
