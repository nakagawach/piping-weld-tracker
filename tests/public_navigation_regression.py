import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get('PUBLIC_BASE_URL','https://nakagawach.pythonanywhere.com/weld').rstrip('/')
PROJECT_ID=int(os.environ.get('PUBLIC_PROJECT_ID','7'))

def text(page):
    return page.locator('#status').inner_text() if page.locator('#status').count() else ''

def relevant(url):
    return ('/progress-data?page=' in url) or ('/pdfium-page?' in url)

def activate(locator, touch=False, force=False):
    if touch:
        locator.tap(force=force)
    else:
        locator.click(force=force)

def path_and_query(url):
    p=urlparse(url)
    return p.path + (('?' + p.query) if p.query else '')

def check_progress(page, failures, label, touch=False):
    requests=[]
    page.on('request', lambda req: requests.append(req.url) if relevant(req.url) else None)
    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=1',wait_until='networkidle',timeout=30000)
    page.wait_for_timeout(500)

    current=page.locator('.progress-thumb.active')
    if current.count()!=1:
        failures.append(f'{label}: progress active thumbnail count={current.count()}')
        return
    before=text(page); requests.clear()
    activate(current,touch)
    page.wait_for_timeout(700)
    after=text(page)
    if requests: failures.append(f'{label}: current thumbnail caused requests: {requests}')
    if '読み込み中' in after or after!=before: failures.append(f'{label}: current thumbnail changed status: before={before!r} after={after!r}')

    before=text(page); requests.clear()
    activate(page.locator('#prev'),touch,True)
    page.wait_for_timeout(500)
    after=text(page)
    if requests: failures.append(f'{label}: first-page prev caused requests: {requests}')
    if '読み込み中' in after or after!=before: failures.append(f'{label}: first-page prev changed status: before={before!r} after={after!r}')

    page_count=int(page.locator('#pageTotal').inner_text().replace('/','').strip())
    if page_count>1:
        requests.clear(); activate(page.locator('.progress-thumb').nth(page_count-1),touch); page.wait_for_timeout(1000)
        before=text(page); requests.clear()
        activate(page.locator('#next'),touch,True); page.wait_for_timeout(500)
        after=text(page)
        if requests: failures.append(f'{label}: last-page next caused requests: {requests}')
        if '読み込み中' in after or after!=before: failures.append(f'{label}: last-page next changed status: before={before!r} after={after!r}')

def check_mobile_header_back(page, failures, route, header, expected):
    page.goto(BASE_URL+route,wait_until='networkidle',timeout=30000)
    page.wait_for_timeout(250)
    root=page.locator(f'[data-ui3-header="{header}"]')
    if root.count()!=1:
        failures.append(f'android-touch: {route} header missing')
        return
    back=root.locator('.ui3-back')
    if back.count()!=1:
        failures.append(f'android-touch: {route} back missing')
        return
    href=back.get_attribute('href') or ''
    if '/weld/' not in href and not href.endswith('/weld'):
        failures.append(f'android-touch: {route} back href missing /weld prefix: {href!r}')
    back.tap()
    page.wait_for_load_state('domcontentloaded',timeout=30000)
    page.wait_for_timeout(150)
    actual=path_and_query(page.url)
    if actual!=expected:
        failures.append(f'android-touch: {route} back target {actual!r} expected {expected!r}')

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(); failures=[]
        desktop=browser.new_context(viewport={'width':1280,'height':800},has_touch=False)
        check_progress(desktop.new_page(),failures,'desktop',False); desktop.close()

        mobile=browser.new_context(viewport={'width':390,'height':844},screen={'width':390,'height':844},device_scale_factor=2.75,is_mobile=True,has_touch=True,user_agent='Mozilla/5.0 (Linux; Android 16; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36')
        page=mobile.new_page(); check_progress(page,failures,'android-touch',True)

        check_mobile_header_back(page,failures,f'/projects/{PROJECT_ID}/progress?page=1','progress','/weld/projects-screen')
        check_mobile_header_back(page,failures,f'/projects/{PROJECT_ID}/entry?page=1','entry','/weld/projects-screen')
        check_mobile_header_back(page,failures,f'/projects/{PROJECT_ID}/progress-list','progress-list',f'/weld/projects/{PROJECT_ID}/progress')
        check_mobile_header_back(page,failures,f'/projects/{PROJECT_ID}/thumbnails?source=progress&page=1','thumbnails',f'/weld/projects/{PROJECT_ID}/progress?page=1')
        check_mobile_header_back(page,failures,f'/projects/{PROJECT_ID}/thumbnails?source=entry&page=1','thumbnails',f'/weld/projects/{PROJECT_ID}/entry?page=1')
        check_mobile_header_back(page,failures,'/favorites','favorites','/weld/projects-screen')

        page.goto(BASE_URL+'/projects-screen',wait_until='networkidle',timeout=30000); page.wait_for_timeout(200)
        if page.locator('.header.ui3-root').count()!=1:
            failures.append('android-touch: projects header missing')
        fav=page.locator('[data-ui3-favorites]')
        if fav.count()!=1:
            failures.append('android-touch: projects favorites button missing')
        else:
            fav.tap(); page.wait_for_load_state('domcontentloaded',timeout=30000); page.wait_for_timeout(100)
            if path_and_query(page.url)!='/weld/favorites': failures.append(f'android-touch: projects favorites target={path_and_query(page.url)!r}')

        page.goto(BASE_URL+'/projects-screen',wait_until='networkidle',timeout=30000); page.wait_for_timeout(150)
        plus=page.locator('#new-project')
        if plus.count()!=1:
            failures.append('android-touch: projects new button missing')
        else:
            plus.tap(); page.wait_for_timeout(100)
            if not page.locator('#dialog[open]').count(): failures.append('android-touch: projects new button did not open dialog')

        mobile.close(); browser.close()
        if failures: raise AssertionError('\n'.join(failures))
        print('Public navigation regression: PASS')

if __name__=='__main__': main()
