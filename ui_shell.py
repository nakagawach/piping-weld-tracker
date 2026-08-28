import re

from flask import Blueprint, request


def create_ui_shell_blueprint():
    blueprint = Blueprint("ui_shell", __name__)

    @blueprint.after_app_request
    def apply_ui_shell(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-weld-ui-shell-v3" in html:
            return response

        path = request.path
        progress = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", path)
        entry = re.fullmatch(r"(?:/weld)?/projects/(\d+)/entry", path)
        thumbs = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        progress_list = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress-list", path)
        favorites = re.fullmatch(r"(?:/weld)?/favorites", path)
        projects = re.fullmatch(r"(?:/weld)?/projects-screen", path)

        if not any((progress, entry, thumbs, progress_list, favorites, projects)):
            return response

        # Dedicated viewer mode is intentionally excluded from shared navigation styling.
        if progress and request.args.get("viewer") == "1":
            return response

        prefix = request.script_root.rstrip("/")

        css = r"""
<style data-weld-ui-shell-v3>
:root{--ui3-bg:#f5f6f8;--ui3-bar:#fff;--ui3-line:#e5e7eb;--ui3-text:#202124;--ui3-muted:#6b7280;--ui3-blue:#1967d2;--ui3-blue-bg:#e8f0fe;--ui3-touch:48px;--ui3-header:58px;--ui3-toolbar:54px}
.ui3-appbar{display:flex;position:sticky;top:0;z-index:120;min-height:var(--ui3-header);align-items:center;gap:8px;padding:6px 12px;background:#fff;border-bottom:1px solid var(--ui3-line);box-shadow:0 1px 2px #0000000d}
.ui3-back,.ui3-icon{min-width:44px;height:44px;padding:0 10px;border:0;border-radius:10px;background:transparent;color:var(--ui3-blue);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;font:inherit;font-weight:800;cursor:pointer;white-space:nowrap}
.ui3-back{gap:3px}.ui3-back::before{content:'‹';font-size:1.7rem;font-weight:500;line-height:1}.ui3-title{min-width:0;flex:1;padding:0 4px}.ui3-title strong{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ui3-title small{display:block;margin-top:1px;color:var(--ui3-muted);font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ui3-toolbar{display:flex!important;align-items:center!important;gap:7px!important;flex-wrap:nowrap!important;min-height:var(--ui3-toolbar)!important;padding:6px 10px!important;margin:0!important;background:#fff!important;border-bottom:1px solid var(--ui3-line)!important;position:sticky!important;top:var(--ui3-header)!important;z-index:95!important;white-space:nowrap!important;overflow-x:auto!important;scrollbar-width:thin}
.ui3-group{display:flex;align-items:center;gap:4px;flex:0 0 auto}.ui3-group+.ui3-group{padding-left:9px;border-left:1px solid var(--ui3-line)}
.ui3-page-group button,.ui3-view-group button,.ui3-page-tools button,.ui3-page-tools a{min-width:42px!important;height:42px!important;min-height:42px!important;padding:0 9px!important;border-radius:9px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;text-decoration:none!important}
.ui3-page-group .nav-button{font-size:1.35rem!important}.ui3-page-group .page-field{display:flex!important;align-items:center!important;gap:4px!important}.ui3-page-group .page-field>span:first-child{display:none!important}.ui3-page-group .page-field input{width:46px!important;min-height:40px!important;padding:0 4px!important;text-align:center!important}.ui3-page-total,.ui3-page-group .page-total{font-size:.82rem!important;color:var(--ui3-muted)!important;font-weight:700!important}
.ui3-view-group .ui3-rotate::before{content:'↻';font-size:1.15rem}.ui3-view-group .ui3-fullscreen::before{content:'⛶';font-size:1.05rem}.ui3-view-group .ui3-reset-view{font-size:.82rem!important}.ui3-page-tools [data-thumbnail-grid-launch]{font-size:0!important}.ui3-page-tools [data-thumbnail-grid-launch]::before{content:'▦';font-size:1.15rem}.ui3-page-tools .page-favorite-view{font-size:1.35rem!important}
.ui3-screen-actions{display:flex;align-items:center;gap:5px;flex:0 0 auto}.ui3-screen-actions .button,.ui3-screen-actions a.button{min-height:42px!important;padding:0 10px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;text-decoration:none!important;white-space:nowrap!important}.ui3-screen-actions .primary{font-weight:800!important}.ui3-screen-actions .drawing-memo-launch,.ui3-screen-actions .drawing-memo-edit{gap:5px}.ui3-screen-actions .drawing-memo-launch::after{content:'メモ表示';font-size:.82rem}.ui3-screen-actions .drawing-memo-edit::after{content:'メモ編集';font-size:.82rem}
.ui3-more{position:relative!important;flex:0 0 auto!important}.ui3-more>summary{list-style:none;min-width:74px;height:42px;padding:0 9px;border:1px solid #bdc1c6;border-radius:9px;background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:800}.ui3-more>summary::after{content:'その他';margin-left:5px;font-size:.8rem}.ui3-more>summary::-webkit-details-marker{display:none}.ui3-more .more-menu{right:0!important;left:auto!important;top:46px!important;width:245px!important;z-index:190!important;padding:6px!important;border:1px solid var(--ui3-line)!important;border-radius:12px!important;background:#fff!important;box-shadow:0 10px 30px #0003!important}.ui3-more .more-menu .button,.ui3-more .more-menu a.button{display:flex!important;align-items:center!important;width:100%!important;min-height:44px!important;margin:1px 0!important;padding:0 12px!important;border:0!important;border-radius:8px!important;background:#fff!important;text-align:left!important;text-decoration:none!important;font-size:.9rem!important}
.ui3-page-state{margin-left:auto!important;flex:0 0 auto!important}
.ui3-page-group button:disabled,.ui3-page-tools button:disabled{opacity:1!important;color:#9aa0a6!important;background:#f1f3f4!important;border-color:#e5e7eb!important;cursor:default!important;pointer-events:none!important;box-shadow:none!important}
body.ui3-progress main,body.ui3-entry main{max-width:none!important;padding:0!important}body.ui3-progress main>.top,body.ui3-entry main>.top{display:none!important}body.ui3-progress .card,body.ui3-entry .card{border-left:0!important;border-right:0!important;border-radius:0!important}
body.ui3-progress .toolbar,body.ui3-entry .controls{position:static!important;top:auto!important}
body.ui3-progress .toolbar>.spacer,body.ui3-progress .toolbar>.desktop-tools,body.ui3-progress .toolbar>.compact-rotate,body.ui3-progress .toolbar>.compact-fullscreen,body.ui3-progress .toolbar>.more{display:none!important}
body.ui3-progress .statusline{padding-left:10px!important;padding-right:10px!important}body.ui3-progress .progress-thumbs,body.ui3-entry .thumbs{margin:0!important;border-bottom:1px solid #eee!important}
body.ui3-entry .controls label{display:flex!important;align-items:center!important;gap:4px!important}body.ui3-entry .controls label>input{width:46px!important}body.ui3-entry #pageState{display:inline-block!important}
body.ui3-entry #rotate{font-size:0!important}body.ui3-entry #rotate::before{content:'↻';font-size:1.15rem}body.ui3-entry #fullscreen{font-size:0!important}body.ui3-entry #fullscreen::before{content:'⛶';font-size:1.05rem}body.ui3-entry #viewReset{font-size:.82rem!important}
body.ui3-entry .thumb.active:disabled{opacity:1!important;border-color:#1967d2!important;background:#e8f0fe!important;color:#174ea6!important;cursor:default!important;pointer-events:none!important;box-shadow:inset 0 0 0 1px #1967d2!important}body.ui3-entry .thumb.active:disabled img{opacity:.86!important}
body.ui3-grid main,body.ui3-favorites main,body.ui3-list main{padding-top:0!important}body.ui3-grid .top,body.ui3-favorites .top,body.ui3-list .topbar{display:none!important}body.ui3-grid .toolbar,body.ui3-favorites .toolbar{position:sticky!important;top:var(--ui3-header)!important;z-index:90!important}body.ui3-list .filters{top:var(--ui3-header)!important}
body.ui3-projects main{padding-top:0!important}.ui3-root{position:sticky;top:0;z-index:120;margin:0 -16px 16px!important;padding:6px max(10px,env(safe-area-inset-right))!important;min-height:62px;display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px!important;background:#fff!important;border-bottom:1px solid var(--ui3-line)!important}.ui3-root>div:first-child{min-width:0;flex:1}.ui3-root-actions{display:flex!important;gap:4px!important;flex-wrap:nowrap!important}
@media(hover:hover) and (pointer:fine){.ui3-back:hover,.ui3-icon:hover,.ui3-toolbar button:hover:not(:disabled),.ui3-toolbar a:hover{background:#f1f3f4}}
@media(min-width:821px) and (max-width:1199px){.ui3-appbar{padding-left:8px;padding-right:8px}.ui3-back span{display:none}.ui3-back{width:44px;padding:0}.ui3-toolbar{padding-left:6px!important;padding-right:6px!important;gap:5px!important}.ui3-group+.ui3-group{padding-left:6px}.ui3-screen-actions .drawing-memo-launch::after,.ui3-screen-actions .drawing-memo-edit::after{display:none}.ui3-screen-actions .button,.ui3-screen-actions a.button{padding-left:8px!important;padding-right:8px!important}}
@media(max-width:820px){
  body{overscroll-behavior-y:none}.ui3-appbar{min-height:56px;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left));gap:4px}.ui3-back,.ui3-icon{min-width:48px;height:48px;padding:0 8px;border-radius:12px;touch-action:manipulation}.ui3-back{font-size:.84rem}.ui3-back::before{font-size:1.8rem}.ui3-title{padding:0 2px}.ui3-title strong{font-size:.95rem}.ui3-title small{font-size:.69rem}
  .ui3-toolbar{top:56px!important;min-height:52px!important;padding:4px 5px!important;gap:4px!important;scrollbar-width:none}.ui3-toolbar::-webkit-scrollbar{display:none}.ui3-group{gap:2px}.ui3-group+.ui3-group{padding-left:4px}.ui3-page-group button,.ui3-view-group button,.ui3-page-tools button,.ui3-page-tools a{min-width:44px!important;width:44px!important;height:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important}.ui3-page-group .page-field input{width:40px!important;border:0!important;background:#f3f4f6!important}.ui3-page-total,.ui3-page-group .page-total{font-size:.75rem!important}.ui3-view-group #viewReset,.ui3-view-group .ui3-reset-view{display:none!important}
  .ui3-screen-actions{width:100%;padding:5px 6px;border-bottom:1px solid var(--ui3-line);background:#fff;overflow-x:auto;scrollbar-width:none}.ui3-screen-actions::-webkit-scrollbar{display:none}.ui3-screen-actions .button,.ui3-screen-actions a.button{min-height:44px!important;padding:0 10px!important}.ui3-screen-actions .drawing-memo-launch::after,.ui3-screen-actions .drawing-memo-edit::after{display:none}.ui3-screen-actions .drawing-memo-launch,.ui3-screen-actions .drawing-memo-edit{width:44px!important;min-width:44px!important;padding:0!important;font-size:1.1rem!important}.ui3-screen-actions #bboxEdit{display:none!important}.ui3-screen-actions #ocr,.ui3-screen-actions #save{font-weight:800!important}.ui3-screen-actions #save{min-width:max-content!important}
  .ui3-more{margin-left:auto!important}.ui3-more>summary{width:48px!important;min-width:48px!important;height:48px!important;padding:0!important;border:0!important;background:transparent!important;font-size:1.25rem!important}.ui3-more>summary::after{display:none}.ui3-more .more-menu{top:50px!important;width:min(270px,calc(100vw - 16px))!important}.ui3-page-state{margin-left:0!important}
  body.ui3-progress .statusline{display:none!important}body.ui3-entry .status{margin:6px 8px!important}.drawing-memo-tools{overflow-x:auto!important}
}
@media(max-width:370px){.ui3-back span{display:none}.ui3-back{width:48px;padding:0}.ui3-title small{display:none}}
</style>
"""

        if progress:
            project_id = progress.group(1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{
  document.body.classList.add('ui3-progress');
  const toolbar=document.querySelector('.toolbar'),top=document.querySelector('.top');
  const prev=document.getElementById('prev'),next=document.getElementById('next'),pageField=toolbar?.querySelector('.page-field');
  const zoomOut=document.getElementById('zoomOut'),zoomReset=document.getElementById('zoomReset'),zoomIn=document.getElementById('zoomIn'),rotate=document.getElementById('rotate'),viewReset=document.getElementById('viewReset'),fullscreen=document.getElementById('fullscreen'),reload=document.getElementById('reload');
  const more=document.getElementById('moreMenu');
  const preservedProgressActions=[document.getElementById('drawingMemoLaunch'),document.getElementById('drawingMemoEdit'),document.querySelector('a[aria-label=\"進捗一覧\"]')].filter(Boolean);
  if(!toolbar||!top||!prev||!next||!pageField||!more)return;

  const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='progress';
  const back=document.createElement('a');back.className='ui3-back';back.href='{prefix}/projects-screen';back.setAttribute('aria-label','工事一覧へ');back.innerHTML='<span>工事一覧</span>';
  const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong></strong><small>進捗入力</small>';title.querySelector('strong').textContent=(top.querySelector('.meta')?.textContent||'').split('/')[0].trim()||'進捗入力';
  app.append(back,title);
  toolbar.parentNode.insertBefore(app,toolbar);

  toolbar.classList.add('ui3-toolbar');
  const pageGroup=document.createElement('div');pageGroup.className='ui3-group ui3-page-group';pageGroup.append(prev,pageField,next);
  const viewGroup=document.createElement('div');viewGroup.className='ui3-group ui3-view-group';
  for(const el of [zoomOut,zoomReset,zoomIn,rotate,viewReset,fullscreen])if(el) viewGroup.append(el);
  rotate?.classList.add('ui3-rotate');fullscreen?.classList.add('ui3-fullscreen');viewReset?.classList.add('ui3-reset-view');
  const pageTools=document.createElement('div');pageTools.className='ui3-group ui3-page-tools';
  const screenActions=document.createElement('div');screenActions.className='ui3-screen-actions';screenActions.dataset.ui3ScreenActions='progress';
  const entryLink=document.createElement('a');entryLink.className='button';entryLink.textContent='図面エントリーへ';entryLink.title='現在ページを図面エントリーで開く';entryLink.addEventListener('click',e=>{{e.preventDefault();location.href=`{prefix}/projects/{project_id}/entry?page=${{Number(document.getElementById('page')?.value)||1}}`;}});
  const moreMenu=more.querySelector('.more-menu');more.classList.add('ui3-more');
  document.getElementById('backCompact')?.remove();
  if(reload){{reload.textContent='再読込';moreMenu?.append(reload)}}
  toolbar.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);
  for(const el of preservedProgressActions)screenActions.append(el);

  const collect=()=>{{
    const grid=document.querySelector('[data-thumbnail-grid-launch]')||toolbar.querySelector('[aria-label="ページ一覧"]');if(grid&&grid.parentNode!==pageTools){{grid.title='ページ一覧';pageTools.append(grid)}}
    const fav=document.querySelector('.page-favorite-view');if(fav&&fav.parentNode!==pageTools){{fav.title='お気に入り';pageTools.append(fav)}}
    const memoShow=document.getElementById('drawingMemoLaunch');if(memoShow&&memoShow.parentNode!==screenActions)screenActions.append(memoShow);
    const memoEdit=document.getElementById('drawingMemoEdit');if(memoEdit&&memoEdit.parentNode!==screenActions)screenActions.append(memoEdit);
    const list=[...document.querySelectorAll('a[aria-label="進捗一覧"]')][0];if(list&&list.parentNode!==screenActions){{list.textContent='進捗一覧';list.title='進捗一覧';screenActions.append(list)}}
    if(!entryLink.isConnected)screenActions.append(entryLink);
  }};
  const obs=new MutationObserver(collect);obs.observe(document.body,{{childList:true,subtree:true}});collect();setTimeout(collect,100);setTimeout(collect,400);

  const place=()=>{{
    if(innerWidth<=820){{if(more.parentNode!==app)app.append(more);if(screenActions.previousElementSibling!==toolbar)toolbar.insertAdjacentElement('afterend',screenActions);if(viewReset&&viewReset.parentNode!==moreMenu)moreMenu?.prepend(viewReset)}}
    else{{if(more.parentNode!==toolbar)toolbar.append(more);if(screenActions.parentNode!==toolbar)toolbar.insertBefore(screenActions,more);if(viewReset&&viewReset.parentNode!==viewGroup)viewGroup.append(viewReset)}}
  }};
  addEventListener('resize',place,{{passive:true}});place();
  document.getElementById('rotateCompact')?.remove();document.getElementById('fullscreenCompact')?.remove();
  document.addEventListener('pointerdown',e=>{{if(more.open&&!more.contains(e.target))more.removeAttribute('open')}},true);
}})();
</script>
"""
        elif entry:
            project_id = entry.group(1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{
  document.body.classList.add('ui3-entry');
  const top=document.querySelector('.top'),controls=document.querySelector('.controls');
  const prev=document.getElementById('prev'),next=document.getElementById('next'),pageInput=document.getElementById('page');
  const zoomOut=document.getElementById('zoomOut'),zoomReset=document.getElementById('zoomReset'),zoomIn=document.getElementById('zoomIn'),rotate=document.getElementById('rotate'),viewReset=document.getElementById('viewReset'),fullscreen=document.getElementById('fullscreen');
  const ocr=document.getElementById('ocr'),bbox=document.getElementById('bboxEdit'),save=document.getElementById('save'),reset=document.getElementById('reset'),bulkDelete=document.getElementById('bulkDelete'),pageState=document.getElementById('pageState');
  const preservedEntryPageTools=[document.querySelector('[data-thumbnail-grid-launch]'),document.querySelector('.page-favorite-view')].filter(Boolean);
  if(!top||!controls||!prev||!next||!pageInput||!ocr||!save)return;

  const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='entry';
  const back=document.createElement('a');back.className='ui3-back';back.href='{prefix}/projects-screen';back.setAttribute('aria-label','工事一覧へ');back.innerHTML='<span>工事一覧</span>';
  const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong></strong><small>図面エントリー</small>';title.querySelector('strong').textContent=(top.querySelector('.meta')?.textContent||'').split('/')[0].trim()||'図面エントリー';
  app.append(back,title);controls.parentNode.insertBefore(app,controls);

  controls.classList.add('ui3-toolbar');
  const pageGroup=document.createElement('div');pageGroup.className='ui3-group ui3-page-group';
  const pageLabel=document.createElement('label');pageLabel.setAttribute('aria-label','ページ');pageLabel.append(pageInput);const total=document.createElement('span');total.className='ui3-page-total';total.textContent='/ -';pageLabel.append(total);pageGroup.append(prev,pageLabel,next);
  prev.textContent='‹';prev.setAttribute('aria-label','前のページ');prev.title='前のページ';next.textContent='›';next.setAttribute('aria-label','次のページ');next.title='次のページ';
  const viewGroup=document.createElement('div');viewGroup.className='ui3-group ui3-view-group';for(const el of [zoomOut,zoomReset,zoomIn,rotate,viewReset,fullscreen])if(el)viewGroup.append(el);rotate?.classList.add('ui3-rotate');fullscreen?.classList.add('ui3-fullscreen');viewReset?.classList.add('ui3-reset-view');
  const pageTools=document.createElement('div');pageTools.className='ui3-group ui3-page-tools';
  const screenActions=document.createElement('div');screenActions.className='ui3-screen-actions';screenActions.dataset.ui3ScreenActions='entry';for(const el of [ocr,bbox,save])if(el)screenActions.append(el);if(pageState){{pageState.classList.add('ui3-page-state');screenActions.append(pageState)}}
  const more=document.createElement('details');more.className='ui3-more';more.innerHTML='<summary aria-label="その他の操作">⋯</summary><div class="more-menu"></div>';const menu=more.querySelector('.more-menu');for(const el of [reset,bulkDelete])if(el){{el.classList.add('button');menu.append(el)}}
  controls.replaceChildren(pageGroup,viewGroup,pageTools,screenActions,more);
  for(const el of preservedEntryPageTools)pageTools.append(el);

  const updateTotal=()=>{{const count=document.querySelectorAll('#thumbs .thumb').length;if(count)total.textContent=`/ ${{count}}`;}};
  const collect=()=>{{
    const grid=document.querySelector('[data-thumbnail-grid-launch]');if(grid&&grid.parentNode!==pageTools){{grid.title='ページ一覧';pageTools.append(grid)}}
    const fav=document.querySelector('.page-favorite-view');if(fav&&fav.parentNode!==pageTools){{fav.title='お気に入り';pageTools.append(fav)}}
    updateTotal();
  }};
  new MutationObserver(collect).observe(document.body,{{childList:true,subtree:true}});collect();setTimeout(collect,100);setTimeout(collect,400);

  const place=()=>{{
    if(innerWidth<=820){{if(more.parentNode!==app)app.append(more);if(screenActions.previousElementSibling!==controls)controls.insertAdjacentElement('afterend',screenActions);if(viewReset&&viewReset.parentNode!==menu)menu.prepend(viewReset)}}
    else{{if(more.parentNode!==controls)controls.append(more);if(screenActions.parentNode!==controls)controls.insertBefore(screenActions,more);if(viewReset&&viewReset.parentNode!==viewGroup)viewGroup.append(viewReset)}}
  }};
  addEventListener('resize',place,{{passive:true}});place();
  document.addEventListener('pointerdown',e=>{{if(more.open&&!more.contains(e.target))more.removeAttribute('open')}},true);
}})();
</script>
"""
        elif thumbs:
            project_id = thumbs.group(1)
            source = "progress" if request.args.get("source") == "progress" else "entry"
            page = max(1, request.args.get("page", default=1, type=int) or 1)
            parent_label = "進捗" if source == "progress" else "エントリー"
            parent_path = "progress" if source == "progress" else "entry"
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-grid');const top=document.querySelector('.top');if(!top)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='thumbnails';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects/{project_id}/{parent_path}?page={page}';b.setAttribute('aria-label','{parent_label}へ');b.innerHTML='<span>{parent_label}</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>ページ一覧</strong><small></small>';title.querySelector('small').textContent=top.querySelector('.meta')?.textContent?.trim()||'';app.append(b,title);document.querySelector('main')?.prepend(app)}})();
</script>
"""
        elif progress_list:
            project_id = progress_list.group(1)
            page = max(1, request.args.get("page", default=1, type=int) or 1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-list');const old=document.querySelector('.topbar');if(!old)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='progress-list';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects/{project_id}/progress?page={page}';b.setAttribute('aria-label','進捗へ');b.innerHTML='<span>進捗</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>進捗一覧</strong><small></small>';title.querySelector('small').textContent=old.querySelector('.meta')?.textContent?.trim()||'';app.append(b,title);document.querySelector('main')?.prepend(app)}})();
</script>
"""
        elif favorites:
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-favorites');const top=document.querySelector('.top');if(!top)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='favorites';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects-screen';b.setAttribute('aria-label','工事一覧へ');b.innerHTML='<span>工事一覧</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>お気に入り</strong><small>工事横断</small>';app.append(b,title);document.querySelector('main')?.prepend(app)}})();
</script>
"""
        else:
            script = r"""
<script data-weld-ui-shell-v3>
(() => {document.body.classList.add('ui3-projects');const header=document.querySelector('.header'),newButton=document.getElementById('new-project');if(!header||!newButton)return;header.classList.add('ui3-root');const wrap=newButton.parentElement;wrap.classList.add('ui3-root-actions');const fav=[...wrap.querySelectorAll('button')].find(x=>x!==newButton&&/お気に入り/.test(x.textContent||''));if(fav){fav.dataset.ui3Favorites='1';fav.title='お気に入りページ一覧'}})();
</script>
"""

        html = html.replace("</head>", css + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint