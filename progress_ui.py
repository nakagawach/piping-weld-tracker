import re

from flask import Blueprint, request


def create_progress_ui_blueprint():
    blueprint = Blueprint("progress_ui", __name__)

    @blueprint.after_app_request
    def apply_progress_ui(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-progress-ui-v9" in html:
            return response

        path = request.path
        progress_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", path)
        simple_screen = bool(
            re.fullmatch(r"(?:/weld)?/projects/\d+/(?:entry|thumbnails|progress-list)", path)
            or re.fullmatch(r"(?:/weld)?/favorites", path)
        )

        if not progress_match and not simple_screen:
            return response

        viewer_mode = bool(progress_match and request.args.get("viewer") == "1")
        head_boot = "<script data-progress-ui-v9>document.documentElement.classList.add('weld-viewer-v9')</script>" if viewer_mode else ""

        css = r"""
<style data-progress-ui-v9>
:root{--weld-bar:#fff;--weld-line:#e5e7eb;--weld-blue:#1967d2;--weld-muted:#6b7280}
.weld-nav-v9{display:none}.weld-viewer-controls-v9{display:none}
@media(max-width:820px){
 body.weld-progress-page-v9{background:#fff}body.weld-progress-page-v9 main{padding:0!important;max-width:none!important}body.weld-progress-page-v9 .top{display:none!important}body.weld-progress-page-v9 .card{border:0!important;border-radius:0!important}
 .weld-nav-v9{display:flex;position:sticky;top:0;z-index:90;min-height:50px;align-items:center;gap:5px;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left));background:var(--weld-bar);border-bottom:1px solid var(--weld-line)}
 .weld-nav-v9 button,.weld-nav-v9 summary{border:0!important;background:transparent!important;color:#202124!important;border-radius:10px!important;min-width:44px!important;width:44px!important;height:44px!important;min-height:44px!important;padding:0!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;font-size:1.18rem!important;cursor:pointer!important}
 .weld-nav-v9 .weld-back-v9{color:var(--weld-blue)!important;font-size:1.55rem!important}.weld-title-v9{min-width:0;flex:1;padding:0 4px}.weld-title-v9 strong{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.weld-title-v9 small{display:block;margin-top:1px;color:var(--weld-muted);font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .weld-nav-v9 .more{display:block!important;position:relative!important;flex:0 0 auto!important}.weld-nav-v9 .more-menu{right:0!important;top:46px!important;width:min(240px,calc(100vw - 16px))!important;padding:6px!important;border-radius:12px!important;box-shadow:0 10px 30px #0003!important;z-index:120!important}.weld-nav-v9 .more-menu .button{display:block!important;width:100%!important;min-height:44px!important;height:auto!important;text-align:left!important;padding:0 12px!important;border:0!important;background:#fff!important;border-radius:8px!important;font-size:.95rem!important}
 body.weld-progress-page-v9 .toolbar{position:sticky!important;top:50px!important;z-index:70!important;display:flex!important;flex-wrap:wrap!important;align-items:center!important;justify-content:space-between!important;gap:4px 8px!important;height:auto!important;min-height:48px!important;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left))!important;white-space:normal!important;background:#fff!important;border-bottom:1px solid var(--weld-line)!important}
 body.weld-progress-page-v9 .toolbar>.spacer,body.weld-progress-page-v9 .toolbar>.desktop-tools,body.weld-progress-page-v9 .toolbar>.compact-rotate,body.weld-progress-page-v9 .toolbar>.compact-fullscreen,body.weld-progress-page-v9 .toolbar>.more{display:none!important}
 .weld-pages-v9,.weld-actions-v9{display:flex;align-items:center;gap:2px;flex:0 0 auto}.weld-pages-v9 .nav-button{min-width:42px!important;width:42px!important;min-height:42px!important;padding:0!important;border:0!important;background:transparent!important;font-size:1.4rem!important}.weld-pages-v9 .page-field{gap:2px!important}.weld-pages-v9 .page-field>span:first-child{display:none!important}.weld-pages-v9 .page-field input{width:42px!important;min-height:38px!important;padding:0 3px!important;border:0!important;border-radius:9px!important;background:#f3f4f6!important;font-weight:800!important}.weld-pages-v9 .page-total{font-size:.78rem!important;color:var(--weld-muted)!important}
 .weld-actions-v9>.button{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:44px!important;width:44px!important;min-height:42px!important;padding:0!important;border:0!important;border-radius:10px!important;background:transparent!important;font-size:1.12rem!important}.weld-actions-v9>.page-favorite-view{font-size:1.4rem!important}body.weld-progress-page-v9 .statusline{display:none!important}
 body.weld-simple-v9 main{padding-top:0!important}body.weld-simple-v9 .top{display:flex!important;align-items:center!important;gap:8px!important;justify-content:flex-start!important;position:sticky!important;top:0!important;z-index:60!important;min-height:50px!important;margin:0 0 8px!important;padding:4px max(8px,env(safe-area-inset-right)) 4px max(8px,env(safe-area-inset-left))!important;background:#fff!important;border-bottom:1px solid var(--weld-line)!important}body.weld-simple-v9 .top>#back{order:-20!important;flex:0 0 auto!important;min-width:44px!important;width:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important;color:var(--weld-blue)!important;font-size:0!important}body.weld-simple-v9 .top>#back::before{content:'‹';font-size:1.55rem}body.weld-simple-v9 .top>div:first-of-type{min-width:0!important;flex:1!important}body.weld-simple-v9 .top .title{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
}
@media(max-width:350px) and (orientation:portrait){body.weld-progress-page-v9 .toolbar{justify-content:center!important}.weld-pages-v9{flex:1 1 100%;justify-content:center}.weld-actions-v9{flex:1 1 100%;justify-content:center;gap:10px}}
html.weld-viewer-v9,html.weld-viewer-v9 body{margin:0!important;width:100%!important;min-height:100%!important;background:#e9eaed!important}html.weld-viewer-v9 body{overflow:hidden!important}html.weld-viewer-v9 main{margin:0!important;padding:0!important;max-width:none!important;width:100%!important;height:100dvh!important;min-height:100dvh!important}html.weld-viewer-v9 .top,html.weld-viewer-v9 .toolbar,html.weld-viewer-v9 .statusline,html.weld-viewer-v9 .summary,html.weld-viewer-v9 .progress-thumbs,html.weld-viewer-v9 .weld-nav-v9{display:none!important}html.weld-viewer-v9 .card{margin:0!important;padding:0!important;border:0!important;border-radius:0!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;overflow:hidden!important;background:#e9eaed!important}html.weld-viewer-v9 .viewer{display:block!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;max-height:none!important;overflow:auto!important;background:#e9eaed!important}html.weld-viewer-v9 #canvas{margin:0 auto!important}html.weld-viewer-v9 .weld-viewer-controls-v9{display:flex!important;position:absolute!important;z-index:150;top:max(8px,env(safe-area-inset-top));right:max(8px,env(safe-area-inset-right));gap:8px}html.weld-viewer-v9 .weld-viewer-controls-v9 button{width:44px;height:44px;min-height:44px;border:0;border-radius:22px;background:rgba(32,33,36,.76);color:#fff;font-size:1.35rem;font-weight:800;box-shadow:0 2px 8px #0004}
</style>
"""
        if progress_match:
            project_id = progress_match.group(1)
            script = f"""
<script data-progress-ui-v9>
(() => {{
 const projectId={project_id},viewerMode={str(viewer_mode).lower()};
 const toolbar=document.querySelector('.toolbar'),top=document.querySelector('.top'),back=document.getElementById('back'),prev=document.getElementById('prev'),next=document.getElementById('next'),pageField=toolbar?.querySelector('.page-field'),more=document.getElementById('moreMenu'),fullscreen=document.getElementById('fullscreenCompact'),viewer=document.getElementById('viewer'),canvas=document.getElementById('canvas'),zoomIn=document.getElementById('zoomIn'),zoomReset=document.getElementById('zoomReset'),rotateCompact=document.getElementById('rotateCompact');
 if(!toolbar||!back||!prev||!next||!pageField||!viewer||!canvas)return;
 const isIOS=/iP(?:hone|ad|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const pageNumber=()=>Math.max(1,Number(document.getElementById('page')?.value)||1);
 if(viewerMode){{
  const controls=document.createElement('div');controls.className='weld-viewer-controls-v9';const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','全画面表示を終了');const rotate=document.createElement('button');rotate.type='button';rotate.textContent='↻';rotate.setAttribute('aria-label','90度回転');controls.append(rotate,close);document.body.appendChild(controls);close.onclick=()=>location.href=`/weld/projects/${{projectId}}/progress?page=${{pageNumber()}}`;
  let fitting=false;const fitCover=()=>{{if(fitting||canvas.hidden||!canvas.width||!viewer.clientHeight||!zoomIn||!zoomReset)return;fitting=true;zoomReset.click();requestAnimationFrame(()=>{{let guard=0;while(canvas.getBoundingClientRect().height<viewer.clientHeight-1&&guard<8){{const before=canvas.getBoundingClientRect().height;zoomIn.click();guard++;if(canvas.getBoundingClientRect().height<=before+.5)break}}viewer.scrollLeft=Math.max(0,(viewer.scrollWidth-viewer.clientWidth)/2);viewer.scrollTop=Math.max(0,(viewer.scrollHeight-viewer.clientHeight)/2);fitting=false}})}};const scheduleCover=()=>requestAnimationFrame(()=>requestAnimationFrame(fitCover));rotate.onclick=()=>{{rotateCompact?.click();scheduleCover()}};const ro='ResizeObserver' in window?new ResizeObserver(()=>{{if(!fitting)scheduleCover()}}):null;ro?.observe(viewer);const mo=new MutationObserver(scheduleCover);mo.observe(canvas,{{attributes:true,attributeFilter:['width','height','hidden']}});window.addEventListener('orientationchange',scheduleCover);window.addEventListener('resize',scheduleCover);scheduleCover();setTimeout(scheduleCover,0);window.addEventListener('pagehide',()=>{{ro?.disconnect();mo.disconnect()}},{{once:true}});return;
 }}
 document.body.classList.add('weld-progress-page-v9');
 const nav=document.createElement('div');nav.className='weld-nav-v9';nav.setAttribute('role','navigation');const navBack=document.createElement('button');navBack.type='button';navBack.className='weld-back-v9';navBack.textContent='‹';navBack.setAttribute('aria-label','工事一覧へ戻る');navBack.onclick=()=>back.click();const title=document.createElement('div');title.className='weld-title-v9';const meta=top?.querySelector('.meta')?.textContent?.trim()||'';title.innerHTML='<strong>進捗入力</strong><small></small>';title.querySelector('small').textContent=meta;fullscreen.textContent='⛶';fullscreen.setAttribute('aria-label','図面を全画面表示');fullscreen.title='図面を全画面表示';nav.append(navBack,title,fullscreen);toolbar.parentNode.insertBefore(nav,toolbar);
 const pages=document.createElement('div');pages.className='weld-pages-v9';pages.append(prev,pageField,next);toolbar.prepend(pages);const actions=document.createElement('div');actions.className='weld-actions-v9';toolbar.appendChild(actions);const moreHome=document.createComment('more-home-v9');if(more)more.parentNode.insertBefore(moreHome,more);
 const moveActions=()=>{{const items=[toolbar.querySelector('.page-favorite-view'),document.getElementById('rotateCompact'),toolbar.querySelector('[aria-label="ページ一覧"]'),toolbar.querySelector('[aria-label="進捗一覧"]')];for(const el of items)if(el&&el.parentNode!==actions)actions.appendChild(el)}};
 const cleanMenu=()=>{{if(!more)return;more.querySelectorAll('[data-go-fullscreen],#backCompact').forEach(el=>el.remove());const menu=more.querySelector('.more-menu');if(!menu)return;if(!menu.querySelector('[data-go-entry-v9]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.goEntryV9='1';b.textContent='✎ 図面エントリーへ';b.onclick=()=>location.href=`/weld/projects/${{projectId}}/entry?page=${{pageNumber()}}`;menu.appendChild(b)}}if(!menu.querySelector('[data-go-favorites-v9]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.goFavoritesV9='1';b.textContent='★ お気に入り一覧';b.onclick=()=>location.href='/weld/favorites';menu.appendChild(b)}}}};
 const apply=()=>{{if(matchMedia('(max-width:820px)').matches){{if(more&&more.parentNode!==nav)nav.appendChild(more);moveActions();cleanMenu()}}else if(more&&more.parentNode===nav)moreHome.parentNode.insertBefore(more,moreHome.nextSibling)}};const obs=new MutationObserver(()=>{{moveActions();cleanMenu();apply()}});obs.observe(toolbar,{{childList:true,subtree:false}});if(more)obs.observe(more,{{childList:true,subtree:true}});apply();setTimeout(apply,0);setTimeout(apply,250);
 if(isIOS)fullscreen.onclick=e=>{{e.preventDefault();e.stopPropagation();location.href=`/weld/projects/${{projectId}}/progress?page=${{pageNumber()}}&viewer=1`}};
 const closeOutside=e=>{{if(more?.open&&!more.contains(e.target))more.removeAttribute('open')}};document.addEventListener('pointerdown',closeOutside,true);document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&more?.open)more.removeAttribute('open')}});
}})();
</script>
"""
        else:
            script = r"""
<script data-progress-ui-v9>
(() => {const top=document.querySelector('.top'),back=document.getElementById('back');if(!top)return;document.body.classList.add('weld-simple-v9');if(back)top.insertBefore(back,top.firstChild)})();
</script>
"""
        html = html.replace("</head>", head_boot + css + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
