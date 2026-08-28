import os
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'https://nakagawach.pythonanywhere.com/weld').rstrip('/')
PROJECT_ID = int(os.environ.get('PUBLIC_PROJECT_ID', '7'))


def parsed(url):
    p = urlparse(url)
    return p.path, parse_qs(p.query)


def relevant_progress(url):
    return '/progress-data?page=' in url or ('/pdfium-page?' in url and 'format=png' in url)


def relevant_entry(url):
    return '/number-map?page=' in url or ('/pdfium-page?' in url and 'format=png' in url)


def tap_and_wait(page, locator, ms=450, force=False):
    locator.tap(force=force)
    page.wait_for_timeout(ms)


def assert_url(failures, label, page, path, params=None):
    actual_path, actual_params = parsed(page.url)
    if actual_path != path:
        failures.append(f'{label}: path={actual_path!r} expected={path!r}')
        return
    for key, value in (params or {}).items():
        actual = actual_params.get(key, [None])[0]
        if actual != str(value):
            failures.append(f'{label}: query {key}={actual!r} expected={str(value)!r}')


def check_progress(page, failures):
    requests = []
    page.on('request', lambda req: requests.append(req.url) if relevant_progress(req.url) else None)
    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=1', wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(500)
    page_count = int(page.locator('#pageTotal').inner_text().replace('/', '').strip())

    active = page.locator('.progress-thumb.active')
    if active.count() != 1:
        failures.append(f'progress: active thumbnail count={active.count()}')
    else:
        requests.clear(); tap_and_wait(page, active)
        if requests:
            failures.append(f'progress: current thumbnail reloaded page: {requests}')

    requests.clear(); tap_and_wait(page, page.locator('#prev'), force=True)
    if requests:
        failures.append(f'progress: P1 prev reloaded page: {requests}')

    back = page.locator('[data-ui3-header="progress"] .ui3-back')
    if back.count() != 1:
        failures.append('progress: mobile back missing')
    else:
        href = back.get_attribute('href') or ''
        if not href.startswith('/weld/'):
            failures.append(f'progress: back href invalid {href!r}')

    if page_count > 1:
        tap_and_wait(page, page.locator('#next'), 900)
        if page.locator('#page').input_value() != '2':
            failures.append(f'progress: next did not move to P2, page={page.locator("#page").input_value()!r}')

        list_button = page.locator('#progressListButton')
        if list_button.count() != 1:
            failures.append(f'progress: progress-list button count={list_button.count()}')
        else:
            tap_and_wait(page, list_button, 300)
            page.wait_for_load_state('domcontentloaded', timeout=30000)
            assert_url(failures, 'progress P2 -> progress-list', page, f'/weld/projects/{PROJECT_ID}/progress-list', {'page': 2})
            back = page.locator('[data-ui3-header="progress-list"] .ui3-back')
            if back.count() != 1:
                failures.append('progress-list: back missing')
            else:
                tap_and_wait(page, back, 250)
                page.wait_for_load_state('domcontentloaded', timeout=30000)
                assert_url(failures, 'progress-list -> progress P2', page, f'/weld/projects/{PROJECT_ID}/progress', {'page': 2})

        page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/progress?page=2', wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(300)
        grid_button = page.locator('#thumbnailGridButton')
        if grid_button.count() != 1:
            failures.append(f'progress: page-list button count={grid_button.count()}')
        else:
            tap_and_wait(page, grid_button, 250)
            page.wait_for_load_state('domcontentloaded', timeout=30000)
            assert_url(failures, 'progress P2 -> thumbnails', page, f'/weld/projects/{PROJECT_ID}/thumbnails', {'source': 'progress', 'page': 2})
            back = page.locator('[data-ui3-header="thumbnails"] .ui3-back')
            if back.count() != 1:
                failures.append('progress thumbnails: back missing')
            else:
                tap_and_wait(page, back, 250)
                page.wait_for_load_state('domcontentloaded', timeout=30000)
                assert_url(failures, 'progress thumbnails -> P2', page, f'/weld/projects/{PROJECT_ID}/progress', {'page': 2})


def check_entry(page, failures):
    requests = []
    page.on('request', lambda req: requests.append(req.url) if relevant_entry(req.url) else None)
    page.goto(f'{BASE_URL}/projects/{PROJECT_ID}/entry?page=1', wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(600)
    page_count = int(page.locator('#page').get_attribute('max') or '0')

    active = page.locator('.thumb.active')
    if active.count() != 1:
        failures.append(f'entry: active thumbnail count={active.count()}')
    else:
        requests.clear(); tap_and_wait(page, active)
        if requests:
            failures.append(f'entry: current thumbnail reloaded page: {requests}')

    requests.clear(); tap_and_wait(page, page.locator('#prev'), force=True)
    if requests:
        failures.append(f'entry: P1 prev reloaded page: {requests}')

    if page_count > 1:
        tap_and_wait(page, page.locator('#next'), 900)
        if page.locator('#page').input_value() != '2':
            failures.append(f'entry: next did not move to P2, page={page.locator("#page").input_value()!r}')
        grid_button = page.locator('#thumbnailGridButton')
        if grid_button.count() != 1:
            failures.append(f'entry: page-list button count={grid_button.count()}')
        else:
            tap_and_wait(page, grid_button, 250)
            page.wait_for_load_state('domcontentloaded', timeout=30000)
            assert_url(failures, 'entry P2 -> thumbnails', page, f'/weld/projects/{PROJECT_ID}/thumbnails', {'source': 'entry', 'page': 2})
            back = page.locator('[data-ui3-header="thumbnails"] .ui3-back')
            if back.count() != 1:
                failures.append('entry thumbnails: back missing')
            else:
                tap_and_wait(page, back, 250)
                page.wait_for_load_state('domcontentloaded', timeout=30000)
                assert_url(failures, 'entry thumbnails -> P2', page, f'/weld/projects/{PROJECT_ID}/entry', {'page': 2})


def check_root_navigation(page, failures):
    for route, header in [
        (f'/projects/{PROJECT_ID}/progress?page=1', 'progress'),
        (f'/projects/{PROJECT_ID}/entry?page=1', 'entry'),
        ('/favorites', 'favorites'),
    ]:
        page.goto(BASE_URL + route, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(200)
        back = page.locator(f'[data-ui3-header="{header}"] .ui3-back')
        if back.count() != 1:
            failures.append(f'{header}: back missing')
            continue
        tap_and_wait(page, back, 200)
        page.wait_for_load_state('domcontentloaded', timeout=30000)
        assert_url(failures, f'{header} -> projects', page, '/weld/projects-screen')

    page.goto(BASE_URL + '/projects-screen', wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(200)
    fav = page.locator('[data-ui3-favorites]')
    if fav.count() != 1:
        failures.append('projects: favorites button missing')
    else:
        tap_and_wait(page, fav, 200)
        page.wait_for_load_state('domcontentloaded', timeout=30000)
        assert_url(failures, 'projects -> favorites', page, '/weld/favorites')

    page.goto(BASE_URL + '/projects-screen', wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(200)
    plus = page.locator('#new-project')
    if plus.count() != 1:
        failures.append('projects: new-project button missing')
    else:
        tap_and_wait(page, plus, 120)
        if page.locator('#dialog[open]').count() != 1:
            failures.append('projects: + did not open registration dialog')
        if page.locator('#error').inner_text().strip():
            failures.append(f'projects: + opened with unexpected error {page.locator("#error").inner_text()!r}')


def main():
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={'width': 390, 'height': 844},
            screen={'width': 390, 'height': 844},
            device_scale_factor=2.75,
            is_mobile=True,
            has_touch=True,
            user_agent='Mozilla/5.0 (Linux; Android 16; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36',
        )
        page = context.new_page()
        check_progress(page, failures)
        check_entry(page, failures)
        check_root_navigation(page, failures)
        context.close(); browser.close()
    if failures:
        raise AssertionError('\n'.join(failures))
    print('Public UI navigation regression: PASS')


if __name__ == '__main__':
    main()
