import re

from flask import Blueprint, request


def create_ui_baseline_blueprint():
    blueprint = Blueprint("ui_baseline", __name__)

    @blueprint.after_app_request
    def apply_ui_baseline(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-weld-ui-baseline" in html:
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

        viewer_mode = bool(progress and request.args.get("viewer") == "1")
        if progress:
            # Reuse the stable 500px thumbnail cache everywhere.
            html = html.replace("longEdge=320&format=jpeg", "longEdge=500&format=jpeg")
            # Saving progress redraws the canvas. Preserve the user's pan position across that redraw.
            old = "progressMap.set(key(active),data);draw();dialog.close();"
            new = (
                "const weldKeepLeft=viewer.scrollLeft,weldKeepTop=viewer.scrollTop;"
                "progressMap.set(key(active),data);draw();"
                "requestAnimationFrame(()=>{viewer.scrollLeft=weldKeepLeft;viewer.scrollTop=weldKeepTop});"
                "dialog.close();"
            )
            html = html.replace(old, new, 1)

        boot = (
            "<script data-weld-ui-baseline>document.documentElement.classList.add('weld-viewer-mode')</script>"
            if viewer_mode
            else ""
        )
        css = r"""
<style data-weld-ui-baseline>
:root{--ui-bar:#fff;--ui-line:#e5e7eb;--ui-blue:#1967d2;--ui-muted:#6b7280;--ui-bg:#f5f6f8;--ui-appbar-h:54px;--ui-touch:48px}
.ui-appbar{display:none}.ui-context{display:none}
@media(max-width:820px){
  body{overscroll-behavior-y:none}
  .ui-appbar{display:flex;position:sticky;top:0;z-index:100;min-height:var(--ui-appbar-h);align-items:center;gap:4px;padding:3px max(6px,env(safe-area-inset-right)) 3px max(6px,env(safe-area-inset-left));background:rgba(255,255,255,.97);border-bottom:1px solid var(--ui-line);backdrop-filter:saturate(180%) blur(12px)}
  .ui-icon{width:var(--ui-touch);height:var(--ui-touch);min-width:var(--ui-touch);min-height:var(--ui-touch);padding:0;border:0;border-radius:12px;background:transparent;color:#202124;display:inline-flex;align-items:center;justify-content:center;font:inherit;font-size:1.2rem;font-weight:800;touch-action:manipulation;cursor:pointer}
  .ui-icon:active{background:#f1f3f4}.ui-back{color:var(--ui-blue);font-size:1.9rem;font-weight:500}
  .ui-title{min-width:0;flex:1;padding:0 4px}.ui-title strong{display:block;font-size:1rem;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ui-title small{display:block;margin-top:2px;color:var(--ui-muted);font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ui-appbar details.more{display:block!important;position:relative!important;flex:0 0 auto!important}.ui-appbar details.more>summary{width:var(--ui-touch)!important;height:var(--ui-touch)!important;min-width:var(--ui-touch)!important;min-height:var(--ui-touch)!important;padding:0!important;border:0!important;background:transparent!important;border-radius:12px!important;font-size:1.25rem!important}.ui-appbar .more-menu{right:0!important;top:50px!important;width:min(250px,calc(100vw - 16px))!important;z-index:140!important;border-radius:13px!important;padding:6px!important;box-shadow:0 10px 32px #0003!important}.ui-appbar .more-menu .button{display:block!important;width:100%!important;min-height:46px!important;margin:1px 0!important;padding:0 12px!important;border:0!important;border-radius:9px!important;background:#fff!important;text-align:left!important;font-size:.95rem!important}

  body.ui-progress main,body.ui-entry main{padding:0!important;max-width:none!important}body.ui-progress>.top,body.ui-entry>.top{display:none!important}body.ui-progress main>.top,body.ui-entry main>.top{display:none!important}body.ui-progress .card,body.ui-entry .card{border-left:0!important;border-right:0!important;border-radius:0!important}
  body.ui-progress .toolbar{position:sticky!important;top:var(--ui-appbar-h)!important;z-index:80!important;display:flex!important;flex-wrap:wrap!important;justify-content:space-between!important;align-items:center!important;gap:4px 8px!important;height:auto!important;min-height:50px!important;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left))!important;background:#fff!important;border-bottom:1px solid var(--ui-line)!important;white-space:normal!important}
  body.ui-progress .toolbar>.spacer,body.ui-progress .toolbar>.desktop-tools,body.ui-progress .toolbar>.compact-rotate,body.ui-progress .toolbar>.compact-fullscreen,body.ui-progress .toolbar>.more{display:none!important}
  .ui-page-group,.ui-drawing-actions{display:flex;align-items:center;gap:2px;flex:0 0 auto}.ui-page-group .nav-button{width:44px!important;min-width:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important;font-size:1.45rem!important}.ui-page-group .page-field{gap:2px!important}.ui-page-group .page-field>span:first-child{display:none!important}.ui-page-group .page-field input{width:44px!important;min-height:38px!important;padding:0 3px!important;border:0!important;border-radius:10px!important;background:#f3f4f6!important;font-weight:800!important}.ui-page-group .page-total{font-size:.78rem!important;color:var(--ui-muted)!important}
  .ui-drawing-actions>.button,.ui-drawing-actions>a.button{display:inline-flex!important;align-items:center!important;justify-content:center!important;width:44px!important;min-width:44px!important;min-height:44px!important;padding:0!important;border:0!important;border-radius:10px!important;background:transparent!important;text-decoration:none!important;font-size:1.15rem!important}.ui-drawing-actions>.page-favorite-view{font-size:1.45rem!important}.ui-drawing-actions>*:active{background:#f1f3f4!important}
  body.ui-progress .statusline{display:none!important}

  body.ui-entry .controls{position:sticky!important;top:var(--ui-appbar-h)!important;z-index:80!important;margin:0!important;padding:5px max(6px,env(safe-area-inset-right)) 5px max(6px,env(safe-area-inset-left))!important;background:#fff!important;border-bottom:1px solid var(--ui-line)!important;display:flex!important;align-items:center!important;gap:5px!important;flex-wrap:wrap!important}
  body.ui-entry .controls label{display:flex!important;align-items:center!important;gap:3px!important;font-size:0!important}body.ui-entry .controls label::before{content:'P';font-size:.85rem;font-weight:800;color:var(--ui-muted)}body.ui-entry #page{width:48px!important;min-height:40px!important;border:0!important;border-radius:10px!important;background:#f3f4f6!important;padding:0 4px!important;text-align:center!important;font-weight:800!important}
  body.ui-entry #prev,body.ui-entry #next,body.ui-entry #rotate,body.ui-entry .page-favorite-view,body.ui-entry [data-thumbnail-grid-launch]{min-width:44px!important;width:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important;font-size:0!important;border-radius:10px!important}body.ui-entry #prev::before{content:'‹';font-size:1.45rem}body.ui-entry #next::before{content:'›';font-size:1.45rem}body.ui-entry #rotate::before{content:'↻';font-size:1.2rem}body.ui-entry [data-thumbnail-grid-launch]::before{content:'▦';font-size:1.15rem}
  body.ui-entry #ocr{margin-left:auto!important}body.ui-entry #ocr,body.ui-entry #save{min-height:42px!important;padding:0 10px!important}body.ui-entry #reset,body.ui-entry #bulkDelete{display:none!important}body.ui-entry .page-state{order:20}.ui-entry-more .more-menu{width:min(260px,calc(100vw - 16px))}

  body.ui-grid main,body.ui-favorites main,body.ui-list main{padding-top:0!important}body.ui-grid .top,body.ui-favorites .top{display:none!important}
  body.ui-grid .toolbar,body.ui-favorites .toolbar{position:sticky!important;top:var(--ui-appbar-h)!important;z-index:80!important;margin:0 0 9px!important;border:0!important;border-bottom:1px solid var(--ui-line)!important;border-radius:0!important;background:rgba(255,255,255,.98)!important;padding:6px max(8px,env(safe-area-inset-right)) 6px max(8px,env(safe-area-inset-left))!important;box-shadow:0 1px 2px #0000000d!important}
  body.ui-grid .columns button{min-width:42px!important;height:40px!important;border-radius:9px!important}body.ui-favorites .toolbar{flex-wrap:wrap!important}.ui-favorite-columns{display:flex;gap:4px;margin-left:auto}.ui-favorite-columns button{width:40px;height:38px;border:1px solid #bdc1c6;border-radius:9px;background:#fff;font-weight:800}.ui-favorite-columns button.active{border-color:var(--ui-blue);background:#e8f0fe;color:#174ea6}
  body.ui-list .topbar{position:sticky!important;top:0!important;z-index:100!important;height:var(--ui-appbar-h)!important;margin:0 -8px 8px!important;padding:3px max(6px,env(safe-area-inset-right)) 3px max(6px,env(safe-area-inset-left))!important;background:#fff!important;border-bottom:1px solid var(--ui-line)!important}body.ui-list .back{width:var(--ui-touch)!important;min-width:var(--ui-touch)!important;height:var(--ui-touch)!important;min-height:var(--ui-touch)!important;padding:0!important;border:0!important;background:transparent!important;font-size:0!important;color:var(--ui-blue)!important}body.ui-list .back::before{content:'‹';font-size:1.9rem;font-weight:500}body.ui-list .filters{top:var(--ui-appbar-h)!important;background:var(--ui-bg)!important}

  body.ui-projects main{padding-top:0!important}.ui-rootbar{position:sticky;top:0;z-index:100;margin:0 -16px 16px!important;padding:6px max(10px,env(safe-area-inset-right)) 6px max(10px,env(safe-area-inset-left))!important;min-height:62px;display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px!important;background:rgba(255,255,255,.97)!important;border-bottom:1px solid var(--ui-line)!important;backdrop-filter:saturate(180%) blur(12px)}.ui-rootbar>div:first-child{min-width:0;flex:1}.ui-rootbar h1{font-size:1.15rem!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ui-rootbar .sub{font-size:.72rem}.ui-rootbar>div:last-child{display:flex!important;gap:4px!important;flex-wrap:nowrap!important}.ui-rootbar button{width:48px!important;min-width:48px!important;height:48px!important;min-height:48px!important;padding:0!important;border-radius:12px!important;font-size:0!important}.ui-rootbar [data-ui-favorites]::before{content:'★';font-size:1.35rem;color:#f9ab00}.ui-rootbar #new-project::before{content:'＋';font-size:1.5rem;color:#fff}.ui-rootbar #new-project{background:var(--ui-blue)!important;border-color:var(--ui-blue)!important}
}
@media(max-width:360px) and (orientation:portrait){body.ui-progress .toolbar{justify-content:center!important}.ui-page-group{flex:1 1 100%;justify-content:center}.ui-drawing-actions{flex:1 1 100%;justify-content:center;gap:8px}.ui-title small{display:none}}

/* Dedicated iPhone/iPad viewer. It is a separate page mode, not a fixed overlay. */
html.weld-viewer-mode,html.weld-viewer-mode body{margin:0!important;width:100%!important;height:100%!important;min-height:100%!important;background:#e9eaed!important;overflow:hidden!important}
html.weld-viewer-mode main{margin:0!important;padding:0!important;max-width:none!important;width:100%!important;height:100dvh!important;min-height:100dvh!important}
html.weld-viewer-mode .top,html.weld-viewer-mode .toolbar,html.weld-viewer-mode .statusline,html.weld-viewer-mode .summary,html.weld-viewer-mode .progress-thumbs,html.weld-viewer-mode .ui-appbar{display:none!important}
html.weld-viewer-mode .card{margin:0!important;padding:0!important;border:0!important;border-radius:0!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;overflow:hidden!important;background:#e9eaed!important}
html.weld-viewer-mode .viewer{display:block!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;max-height:none!important;overflow:auto!important;background:#e9eaed!important}
.ui-viewer-controls{display:none}html.weld-viewer-mode .ui-viewer-controls{display:flex;position:absolute;z-index:160;top:max(8px,env(safe-area-inset-top));right:max(8px,env(safe-area-inset-right));gap:8px}html.weld-viewer-mode .ui-viewer-controls button{width:48px;height:48px;min-height:48px;border:0;border-radius:24px;background:rgba(32,33,36,.78);color:#fff;font-size:1.35rem;font-weight:800;box-shadow:0 2px 10px #0004;touch-action:manipulation}
</style>
"""

        if progress:
            project_id = progress.group(1)
            script = f"""
<script data-weld-ui-baseline>
(() => {{
  const projectId={project_id};
  const viewerMode={str(viewer_mode).lower()};
  const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  const toolbar=document.querySelector('.toolbar'),top=document.querySelector('.top'),back=document.getElementById('back'),prev=document.getElementById('prev'),next=document.getElementById('next'),pageField=toolbar?.querySelector('.page-field'),more=document.getElementById('moreMenu'),fullscreenCompact=document.getElementById('fullscreenCompact'),canvas=document.getElementById('canvas'),viewer=document.getElementById('viewer'),rotateCompact=document.getElementById('rotateCompact'),zoomIn=document.getElementById('zoomIn'),zoomReset=document.getElementById('zoomReset');
  if(!toolbar||!back||!prev||!next||!pageField||!viewer||!canvas)return;
  const page=()=>Math.max(1,Number(document.getElementById('page')?.value)||1);
  if(viewerMode){{
    const controls=document.createElement('div');controls.className='ui-viewer-controls';
    const rotate=document.createElement('button');rotate.type='button';rotate.textContent='↻';rotate.setAttribute('aria-label','90度回転');
    const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','図面集中表示を終了');controls.append(rotate,close);document.body.appendChild(controls);
    close.onclick=()=>location.href=`/weld/projects/${{projectId}}/progress?page=${{page()}}`;
    let fitting=false,initialFitted=false;
    const fitCover=()=>{{if(fitting||canvas.hidden||!canvas.width||!viewer.clientHeight||!zoomIn||!zoomReset)return;fitting=true;zoomReset.click();requestAnimationFrame(()=>{{let guard=0;while(canvas.getBoundingClientRect().height<viewer.clientHeight-1&&guard<8){{const before=canvas.getBoundingClientRect().height;zoomIn.click();guard++;if(canvas.getBoundingClientRect().height<=before+.5)break}}viewer.scrollLeft=Math.max(0,(viewer.scrollWidth-viewer.clientWidth)/2);viewer.scrollTop=Math.max(0,(viewer.scrollHeight-viewer.clientHeight)/2);initialFitted=true;fitting=false}})}};
    rotate.onclick=()=>{{rotateCompact?.click();requestAnimationFrame(()=>requestAnimationFrame(fitCover))}};
    const firstPaint=new MutationObserver(()=>{{if(!initialFitted&&canvas.width&&!canvas.hidden){{requestAnimationFrame(()=>requestAnimationFrame(fitCover));firstPaint.disconnect()}}}});firstPaint.observe(canvas,{{attributes:true,attributeFilter:['width','height','hidden']}});
    window.addEventListener('orientationchange',()=>setTimeout(fitCover,100));window.addEventListener('resize',()=>{{if(initialFitted)setTimeout(fitCover,80)}});setTimeout(fitCover,80);
    window.addEventListener('pagehide',()=>firstPaint.disconnect(),{{once:true}});return;
  }}
  document.body.classList.add('ui-progress');
  const app=document.createElement('div');app.className='ui-appbar';
  const b=document.createElement('button');b.className='ui-icon ui-back';b.type='button';b.textContent='‹';b.setAttribute('aria-label','戻る');b.onclick=()=>{{const r=document.referrer;try{{const u=new URL(r);if(u.origin===location.origin&&u.pathname.startsWith('/weld/')){{history.back();return}}}}catch(_e){{}}back.click()}};
  const title=document.createElement('div');title.className='ui-title';title.innerHTML='<strong>進捗入力</strong><small></small>';title.querySelector('small').textContent=top?.querySelector('.meta')?.textContent?.trim()||'';
  if(fullscreenCompact){{fullscreenCompact.className='ui-icon';fullscreenCompact.textContent='⛶';fullscreenCompact.title='図面集中表示';fullscreenCompact.setAttribute('aria-label','図面集中表示');if(isIOS)fullscreenCompact.onclick=e=>{{e.preventDefault();e.stopPropagation();location.href=`/weld/projects/${{projectId}}/progress?page=${{page()}}&viewer=1`}}}}
  app.append(b,title);if(fullscreenCompact)app.append(fullscreenCompact);if(more)app.append(more);toolbar.parentNode.insertBefore(app,toolbar);
  const pages=document.createElement('div');pages.className='ui-page-group';pages.append(prev,pageField,next);toolbar.prepend(pages);const actions=document.createElement('div');actions.className='ui-drawing-actions';toolbar.append(actions);
  const move=()=>{{for(const el of [document.querySelector('.page-favorite-view'),document.getElementById('rotateCompact'),toolbar.querySelector('[aria-label="ページ一覧"]'),toolbar.querySelector('[aria-label="進捗一覧"]')])if(el&&el.parentNode!==actions)actions.append(el)}};
  const clean=()=>{{if(!more)return;more.querySelectorAll('[data-go-fullscreen],#backCompact').forEach(x=>x.remove());const menu=more.querySelector('.more-menu');if(!menu)return;if(!menu.querySelector('[data-ui-entry]')){{const x=document.createElement('button');x.type='button';x.className='button';x.dataset.uiEntry='1';x.textContent='✎ 図面エントリーへ';x.onclick=()=>location.href=`/weld/projects/${{projectId}}/entry?page=${{page()}}`;menu.append(x)}}if(!menu.querySelector('[data-ui-favs]')){{const x=document.createElement('button');x.type='button';x.className='button';x.dataset.uiFavs='1';x.textContent='★ お気に入り一覧';x.onclick=()=>location.href='/weld/favorites';menu.append(x)}}}};
  const obs=new MutationObserver(()=>{{move();clean()}});obs.observe(toolbar,{{childList:true,subtree:true}});move();clean();setTimeout(move,100);setTimeout(move,350);
  document.addEventListener('pointerdown',e=>{{if(more?.open&&!more.contains(e.target))more.removeAttribute('open')}},true);document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&more?.open)more.removeAttribute('open')}});
}})();
</script>
"""
        elif entry:
            project_id = entry.group(1)
            script = f"""
<script data-weld-ui-baseline>
(() => {{
  document.body.classList.add('ui-entry');const top=document.querySelector('.top'),controls=document.querySelector('.controls'),back=document.getElementById('back');if(!top||!controls||!back)return;
  const app=document.createElement('div');app.className='ui-appbar';const b=document.createElement('button');b.className='ui-icon ui-back';b.type='button';b.textContent='‹';b.setAttribute('aria-label','戻る');b.onclick=()=>{{try{{const u=new URL(document.referrer);if(u.origin===location.origin&&u.pathname.startsWith('/weld/')){{history.back();return}}}}catch(_e){{}}back.click()}};const title=document.createElement('div');title.className='ui-title';title.innerHTML='<strong>図面エントリー</strong><small></small>';title.querySelector('small').textContent=top.querySelector('.meta')?.textContent?.trim()||'';
  const more=document.createElement('details');more.className='more ui-entry-more';more.innerHTML='<summary class="ui-icon" aria-label="その他の操作">⋯</summary><div class="more-menu"></div>';const menu=more.querySelector('.more-menu');
  for(const [id,label] of [['reset','読込時に戻す'],['bulkDelete','選択削除']]){{const src=document.getElementById(id);if(!src)continue;const x=document.createElement('button');x.type='button';x.className='button';x.textContent=label;x.onclick=()=>{{src.click();more.removeAttribute('open')}};menu.append(x)}}const fav=document.createElement('button');fav.type='button';fav.className='button';fav.textContent='★ お気に入り一覧';fav.onclick=()=>location.href='/weld/favorites';menu.append(fav);app.append(b,title,more);controls.parentNode.insertBefore(app,controls);
  document.addEventListener('pointerdown',e=>{{if(more.open&&!more.contains(e.target))more.removeAttribute('open')}},true);
}})();
</script>
"""
        elif thumbs:
            script = r"""
<script data-weld-ui-baseline>
(() => {document.body.classList.add('ui-grid');const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;const app=document.createElement('div');app.className='ui-appbar';const b=document.createElement('button');b.type='button';b.className='ui-icon ui-back';b.textContent='‹';b.setAttribute('aria-label','戻る');b.onclick=()=>back.click();const title=document.createElement('div');title.className='ui-title';title.innerHTML='<strong>ページ一覧</strong><small></small>';title.querySelector('small').textContent=top.querySelector('.meta')?.textContent?.trim()||'';app.append(b,title);document.querySelector('main').prepend(app)})();
</script>
"""
        elif favorites:
            script = r"""
<script data-weld-ui-baseline>
(() => {document.body.classList.add('ui-favorites');const top=document.querySelector('.top'),back=document.getElementById('back'),toolbar=document.querySelector('.toolbar'),grid=document.getElementById('grid'),search=document.getElementById('search');if(!top||!back||!toolbar||!grid)return;const app=document.createElement('div');app.className='ui-appbar';const b=document.createElement('button');b.type='button';b.className='ui-icon ui-back';b.textContent='‹';b.setAttribute('aria-label','工事一覧へ戻る');b.onclick=()=>back.click();const title=document.createElement('div');title.className='ui-title';title.innerHTML='<strong>お気に入り</strong><small>工事横断</small>';app.append(b,title);document.querySelector('main').prepend(app);
  const key='weldFavoriteGridCols';let cols=matchMedia('(max-width:640px)').matches?2:3;try{const n=Number(localStorage.getItem(key));if([1,2,3,4].includes(n))cols=n}catch(_e){}const wrap=document.createElement('div');wrap.className='ui-favorite-columns';for(const n of [1,2,3,4]){const x=document.createElement('button');x.type='button';x.textContent=String(n);x.title=`${n}列`;x.onclick=()=>apply(n);wrap.append(x)}toolbar.append(wrap);function apply(n){cols=n;grid.style.gridTemplateColumns=`repeat(${n},minmax(0,1fr))`;[...wrap.children].forEach((x,i)=>x.classList.toggle('active',i+1===n));try{localStorage.setItem(key,String(n))}catch(_e){}}apply(cols);
  const stateKey='weldUi:favorites';try{const s=JSON.parse(sessionStorage.getItem(stateKey)||'{}');if(search&&s.q){search.value=s.q;search.dispatchEvent(new Event('input',{bubbles:true}))}if(Number.isFinite(s.y))setTimeout(()=>scrollTo(0,s.y),120)}catch(_e){}window.addEventListener('pagehide',()=>{try{sessionStorage.setItem(stateKey,JSON.stringify({q:search?.value||'',y:scrollY}))}catch(_e){}});
})();
</script>
"""
        elif progress_list:
            script = r"""
<script data-weld-ui-baseline>
(() => {document.body.classList.add('ui-list');const key='weldUi:progressList:'+location.pathname;const search=document.getElementById('search'),page=document.getElementById('pageFilter');try{const s=JSON.parse(sessionStorage.getItem(key)||'{}');setTimeout(()=>{if(search&&s.q){search.value=s.q;search.dispatchEvent(new Event('input',{bubbles:true}))}if(page&&s.p){page.value=s.p;page.dispatchEvent(new Event('change',{bubbles:true}))}if(s.f){document.querySelector(`[data-filter="${s.f}"]`)?.click()}if(Number.isFinite(s.y))scrollTo(0,s.y)},180)}catch(_e){}window.addEventListener('pagehide',()=>{const active=document.querySelector('.tab.active')?.dataset.filter||'all';try{sessionStorage.setItem(key,JSON.stringify({q:search?.value||'',p:page?.value||'all',f:active,y:scrollY}))}catch(_e){}})})();
</script>
"""
        else:
            script = r"""
<script data-weld-ui-baseline>
(() => {document.body.classList.add('ui-projects');const header=document.querySelector('.header'),newButton=document.getElementById('new-project');if(!header||!newButton)return;header.classList.add('ui-rootbar');const enhance=()=>{const candidate=[...header.querySelectorAll('button')].find(x=>x!==newButton&&/お気に入り/.test(x.textContent||''));if(candidate&&!candidate.dataset.uiFavorites){candidate.dataset.uiFavorites='1';candidate.title='お気に入り'}};new MutationObserver(enhance).observe(header,{childList:true,subtree:true});enhance()})();
</script>
"""

        html = html.replace("</head>", boot + css + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
