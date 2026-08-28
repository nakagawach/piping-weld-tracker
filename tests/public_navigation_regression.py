import os
from playwright.sync_api import sync_playwright

BASE_URL=os.environ.get('PUBLIC_BASE_URL','https://nakagawach.pythonanywhere.com/weld').rstrip('/')
PROJECT_ID=int(os.environ.get('PUBLIC_PROJECT_ID','7'))

def text(page):
    return page.locator('#status').inner_text() if page.locator('#status').count() else ''

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':390,'height':844})
        failures=[]

        page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=1',wait_until='networkidle',timeout=30000)
        page.wait_for_timeout(500)
        before=text(page)
        current=page.locator('.progress-thumb.active')
        if current.count():
            current.click()
            page.wait_for_timeout(600)
            after=text(page)
            if '読み込み中' in after or after!=before:
                failures.append(f'progress current thumbnail reloads: before={before!r} after={after!r}')
        else:
            failures.append('progress active thumbnail not found')

        prev=page.locator('#prev')
        if prev.count():
            before=text(page); prev.click(force=True); page.wait_for_timeout(500); after=text(page)
            if '読み込み中' in after or after!=before:
                failures.append(f'progress first-page prev changes state: before={before!r} after={after!r}')

        page_count=int(page.locator('#pageTotal').inner_text().replace('/','').strip())
        if page_count>1:
            page.locator('.progress-thumb').nth(page_count-1).click(); page.wait_for_timeout(1000)
            before=text(page); page.locator('#next').click(force=True); page.wait_for_timeout(500); after=text(page)
            if '読み込み中' in after or after!=before:
                failures.append(f'progress last-page next changes state: before={before!r} after={after!r}')

        for route, header in [
            (f'/projects/{PROJECT_ID}/entry?page=1','entry'),
            (f'/projects/{PROJECT_ID}/progress-list','progress-list'),
            (f'/projects/{PROJECT_ID}/thumbnails?source=progress&page=1','thumbnails'),
            ('/favorites','favorites'),
            ('/projects-screen','projects'),
        ]:
            page.goto(BASE_URL+route,wait_until='domcontentloaded',timeout=30000)
            page.wait_for_timeout(300)
            if header=='projects':
                if page.locator('.header.ui3-root').count()!=1: failures.append('projects header missing')
            else:
                if page.locator(f'[data-ui3-header="{header}"]').count()!=1: failures.append(f'{header} header missing')

        browser.close()
        if failures:
            raise AssertionError('\n'.join(failures))
        print('Public navigation regression: PASS')

if __name__=='__main__':
    main()
