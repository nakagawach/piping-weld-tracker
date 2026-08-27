import re

from flask import Blueprint, request


def create_responsive_header_blueprint():
    blueprint = Blueprint("responsive_header", __name__)

    @blueprint.after_app_request
    def apply_responsive_header(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-responsive-header-v7" in html:
            return response

        path = request.path
        progress_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", path)
        entry_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/entry", path)
        grid_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        is_favorites = bool(re.fullmatch(r"(?:/weld)?/favorites", path))
        is_progress_list = bool(re.fullmatch(r"(?:/weld)?/projects/\d+/progress-list", path))

        if not (progress_match or entry_match or grid_match or is_favorites or is_progress_list):
            return response

        common_style = """
<style data-responsive-header-v7>
:root{--weld-appbar-h:50px;--weld-focus-h:100dvh;--weld-focus-w:100vw}
.weld-mobile-appbar,.weld-focus-exit{display:none}

@media(max-width:820px){
  .weld-mobile-appbar{display:flex;align-items:center;gap:4px;min-height:var(--weld-appbar-h);padding:5px max(7px,env(safe-area-inset-right)) 5px max(7px,env(safe-area-inset-left));background:#fff;border-bottom:1px solid #e5e5e5;position:sticky;top:0;z-index:80}
  .weld-appbar-back{flex:0 0 auto;min-height:40px;padding:0 7px;border:0;background:transparent;color:#174ea6;font-weight:800;font-size:.95rem;white-space:nowrap}
  .weld-appbar-back .chev{font-size:1.35rem;vertical-align:-1px;margin-right:1px}
  .weld-appbar-title{min-width:0;flex:1;text-align:left;padding-left:2px}
  .weld-appbar-title strong{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .weld-appbar-title small{display:block;margin-top:1px;color:#6b7280;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .weld-appbar-fullscreen{display:inline-flex!important;align-items:center!important;justify-content:center!important;flex:0 0 40px!important;width:40px!important;height:40px!important;min-height:40px!important;padding:0!important;border:0!important;border-radius:10px!important;background:transparent!important;font-size:1.2rem!important}
  .weld-mobile-appbar>.more{display:block!important;flex:0 0 auto;position:relative!important}
  .weld-mobile-appbar>.more summary{min-width:40px!important;width:40px!important;height:40px!important;border:0!important;background:transparent!important;border-radius:10px!important;font-size:1.15rem!important}
  .weld-mobile-appbar .more-menu{right:0!important;top:43px!important;width:min(228px,calc(100vw - 16px))!important;z-index:100!important;padding:6px!important;border-radius:12px!important;box-shadow:0 10px 32px #0003!important}
  .weld-mobile-appbar .more-menu .button{min-height:44px!important;border:0!important;background:#fff!important;border-radius:8px!important;margin:1px 0!important}

  body.weld-progress-v7 main{padding:0!important;max-width:none!important}
  body.weld-progress-v7 .top{display:none!important}
  body.weld-progress-v7 .card{border:0!important;border-radius:0!important}
  body.weld-progress-v7 .toolbar{position:sticky!important;top:var(--weld-appbar-h)!important;z-index:60!important;height:auto!important;min-height:48px!important;display:flex!important;flex-wrap:wrap!important;align-items:center!important;gap:3px!important;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left))!important;white-space:normal!important;background:#fff!important;border-bottom:1px solid #eee!important}
  body.weld-progress-v7 .toolbar>.spacer,body.weld-progress-v7 .toolbar>.desktop-tools,body.weld-progress-v7 .toolbar>.compact-fullscreen,body.weld-progress-v7 .toolbar>.more{display:none!important}
  body.weld-progress-v7 .weld-page-nav-group{display:flex;align-items:center;gap:2px;flex:0 1 auto;min-width:0}
  body.weld-progress-v7 .weld-action-group{display:flex;align-items:center;justify-content:flex-end;gap:2px;flex:1 1 auto;min-width:0}
  body.weld-progress-v7 .weld-page-nav-group .nav-button{min-width:38px!important;min-height:40px!important;padding:0 5px!important;border:0!important;background:transparent!important;font-size:1.35rem!important}
  body.weld-progress-v7 .weld-page-nav-group .page-field{gap:2px!important;min-width:0!important}
  body.weld-progress-v7 .weld-page-nav-group .page-field>span:first-child{display:none!important}
  body.weld-progress-v7 .weld-page-nav-group .page-field input{width:40px!important;min-height:38px!important;border:0!important;border-radius:9px!important;background:#f3f4f6!important;font-weight:800!important;padding:0 3px!important}
  body.weld-progress-v7 .weld-page-nav-group .page-total{font-size:.78rem!important;color:#6b7280!important}
  body.weld-progress-v7 .weld-action-group>.button{min-width:40px!important;width:40px!important;min-height:40px!important;padding:0!important;border:0!important;border-radius:10px!important;background:transparent!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;font-size:1.1rem!important}
  body.weld-progress-v7 .weld-action-group>.page-favorite-view{font-size:1.4rem!important}
  body.weld-progress-v7 .weld-action-group>.compact-rotate{display:inline-flex!important}
  body.weld-progress-v7 .statusline{display:none!important}
}

@media(max-width:390px) and (orientation:portrait){
  body.weld-progress-v7 .toolbar{align-items:stretch!important;row-gap:2px!important}
  body.weld-progress-v7 .weld-page-nav-group{flex:1 1 100%;justify-content:center}
  body.weld-progress-v7 .weld-action-group{flex:1 1 100%;justify-content:center;gap:14px}
  body.weld-progress-v7 .viewer{max-height:calc(100dvh - var(--weld-appbar-h) - 92px - 31px - 62px)!important;min-height:calc(100dvh - var(--weld-appbar-h) - 92px - 31px - 62px)!important}
}

@media(min-width:391px) and (max-width:820px){
  body.weld-progress-v7 .toolbar{flex-wrap:nowrap!important}
  body.weld-progress-v7 .viewer{max-height:calc(100dvh - var(--weld-appbar-h) - 48px - 31px - 62px)!important;min-height:calc(100dvh - var(--weld-appbar-h) - 48px - 31px - 62px)!important}
}

@media(max-width:820px) and (orientation:landscape){
  .weld-appbar-title small{display:none}
  body.weld-progress-v7 .summary{height:31px!important;padding:3px 6px!important}
  body.weld-progress-v7 .progress-thumbs{height:62px!important;padding:3px 5px!important}
  body.weld-progress-v7 .progress-thumb{flex-basis:66px!important}
  body.weld-progress-v7 .progress-thumb img{height:38px!important}
}

body.weld-focus-mode{overflow:hidden!important;background:#fff!important}
body.weld-focus-mode .weld-mobile-appbar,body.weld-focus-mode .toolbar,body.weld-focus-mode .summary,body.weld-focus-mode .progress-thumbs,body.weld-focus-mode .statusline{display:none!important}
body.weld-focus-mode main{padding:0!important;margin:0!important;max-width:none!important}
body.weld-focus-mode .card{position:fixed!important;inset:auto!important;left:0!important;top:0!important;z-index:200!important;width:var(--weld-focus-w)!important;height:var(--weld-focus-h)!important;border:0!important;border-radius:0!important;background:#fff!important;display:flex!important;flex-direction:column!important}
body.weld-focus-mode .viewer{flex:1 1 auto!important;min-height:var(--weld-focus-h)!important;max-height:var(--weld-focus-h)!important;height:var(--weld-focus-h)!important;background:#fff!important}
body.weld-focus-mode #canvas{background:#fff!important}
body.weld-focus-mode .weld-focus-exit{display:inline-flex!important;position:fixed!important;top:max(8px,env(safe-area-inset-top))!important;right:max(8px,env(safe-area-inset-right))!important;z-index:260!important;width:44px!important;height:44px!important;align-items:center!important;justify-content:center!important;border:0!important;border-radius:22px!important;background:rgba(32,33,36,.78)!important;color:#fff!important;font-size:1.45rem!important;font-weight:700!important;box-shadow:0 2px 8px #0004!important}

@media(max-width:820px){
  body.weld-simple-header-v7 main{padding-top:0!important}
  body.weld-simple-header-v7 .top{display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:8px!important;background:#fff!important;border-bottom:1px solid #e5e5e5!important;padding:5px max(8px,env(safe-area-inset-right)) 5px max(8px,env(safe-area-inset-left))!important;margin:0 0 8px!important;position:sticky!important;top:0!important;z-index:50!important}
  body.weld-simple-header-v7 .top>#back{order:-10!important;flex:0 0 auto!important;width:auto!important;min-width:40px!important;min-height:40px!important;padding:0 8px!important;border:0!important;background:transparent!important;color:#174ea6!important}
  body.weld-simple-header-v7 .top>#back .weld-back-label{display:none!important}
  body.weld-simple-header-v7 .top>div:first-of-type{min-width:0!important;flex:1 1 auto!important}
  body.weld-simple-header-v7 .top .title{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
  body.weld-simple-header-v7 .top .meta,body.weld-simple-header-v7 .top .sub{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
}
</style>
"""

        if progress_match:
            script = """
<script data-responsive-header-v7>
(() => {
  const toolbar=document.querySelector('.toolbar');
  const top=document.querySelector('.top');
  const back=document.getElementById('back');
  const more=document.getElementById('moreMenu');
  const fullscreen=document.getElementById('fullscreenCompact');
  const viewer=document.getElementById('viewer');
  const canvas=document.getElementById('canvas');
  const zoomIn=document.getElementById('zoomIn');
  const zoomReset=document.getElementById('zoomReset');
  const prev=document.getElementById('prev'),pageField=toolbar?.querySelector('.page-field'),next=document.getElementById('next');
  if(!toolbar||!back||!prev||!pageField||!next||!fullscreen||!viewer||!canvas||!zoomIn||!zoomReset)return;
  document.body.classList.add('weld-progress-v7');

  const isIOS=/iP(?:hone|ad|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  const root=document.documentElement;
  const appbar=document.createElement('div');appbar.className='weld-mobile-appbar';appbar.setAttribute('role','navigation');appbar.setAttribute('aria-label','画面ナビゲーション');
  const appBack=document.createElement('button');appBack.type='button';appBack.className='weld-appbar-back';appBack.innerHTML='<span class="chev">‹</span><span>工事一覧</span>';appBack.onclick=()=>back.click();
  const title=document.createElement('div');title.className='weld-appbar-title';
  const meta=top?.querySelector('.meta')?.textContent?.trim()||'';title.innerHTML='<strong>進捗入力</strong><small></small>';title.querySelector('small').textContent=meta;
  fullscreen.classList.add('weld-appbar-fullscreen');fullscreen.textContent='⛶';fullscreen.setAttribute('aria-label','図面を全画面表示');fullscreen.title='図面を全画面表示';
  appbar.append(appBack,title,fullscreen);toolbar.parentNode.insertBefore(appbar,toolbar);

  const pageGroup=document.createElement('div');pageGroup.className='weld-page-nav-group';pageGroup.setAttribute('aria-label','ページ移動');
  toolbar.insertBefore(pageGroup,toolbar.firstChild);pageGroup.append(prev,pageField,next);
  const actionGroup=document.createElement('div');actionGroup.className='weld-action-group';actionGroup.setAttribute('aria-label','図面操作');toolbar.appendChild(actionGroup);
  const morePlaceholder=document.createComment('more-menu-home');if(more)more.parentNode.insertBefore(morePlaceholder,more);

  const moveActions=()=>{
    const candidates=[toolbar.querySelector('.page-favorite-view'),document.getElementById('rotateCompact'),toolbar.querySelector('[aria-label="ページ一覧"]'),toolbar.querySelector('[aria-label="進捗一覧"]')];
    for(const el of candidates){if(el&&el.parentNode!==actionGroup)actionGroup.appendChild(el)}
  };
  const cleanMenu=()=>{if(more)more.querySelectorAll('[data-go-fullscreen],#backCompact').forEach(el=>el.remove())};
  cleanMenu();
  const closeMoreOutside=e=>{if(more?.open&&!more.contains(e.target))more.removeAttribute('open')};
  const closeMoreEscape=e=>{if(e.key==='Escape'&&more?.open)more.removeAttribute('open')};
  document.addEventListener('pointerdown',closeMoreOutside,true);document.addEventListener('keydown',closeMoreEscape);

  const exitFocus=document.createElement('button');exitFocus.type='button';exitFocus.className='weld-focus-exit';exitFocus.textContent='×';exitFocus.setAttribute('aria-label','全画面表示を終了');exitFocus.hidden=true;document.body.appendChild(exitFocus);

  const syncFocusViewport=()=>{
    if(!document.body.classList.contains('weld-focus-mode'))return;
    if(isIOS){
      const vv=window.visualViewport;
      const h=Math.max(1,Math.round(vv?.height||window.innerHeight));
      const w=Math.max(1,Math.round(vv?.width||window.innerWidth));
      root.style.setProperty('--weld-focus-h',`${h}px`);
      root.style.setProperty('--weld-focus-w',`${w}px`);
    }else{
      root.style.setProperty('--weld-focus-h','100dvh');
      root.style.setProperty('--weld-focus-w','100vw');
    }
  };
  const centerViewer=()=>{
    viewer.scrollLeft=Math.max(0,(viewer.scrollWidth-viewer.clientWidth)/2);
    viewer.scrollTop=Math.max(0,(viewer.scrollHeight-viewer.clientHeight)/2);
  };
  const fillViewer=()=>{
    if(!document.body.classList.contains('weld-focus-mode')||canvas.hidden||!canvas.width)return;
    syncFocusViewport();
    let guard=0;
    while(canvas.getBoundingClientRect().height < viewer.clientHeight-1 && guard<8){
      const before=canvas.getBoundingClientRect().height;
      zoomIn.click();
      const after=canvas.getBoundingClientRect().height;
      guard++;
      if(after<=before+0.5)break;
    }
    requestAnimationFrame(centerViewer);
  };
  const scheduleFill=()=>requestAnimationFrame(()=>requestAnimationFrame(fillViewer));
  const leaveFocus=()=>{
    document.body.classList.remove('weld-focus-mode');exitFocus.hidden=true;
    root.style.removeProperty('--weld-focus-h');root.style.removeProperty('--weld-focus-w');
    zoomReset.click();
    requestAnimationFrame(()=>{viewer.scrollLeft=0;viewer.scrollTop=0});
  };
  const enterFocus=()=>{
    if(more?.open)more.removeAttribute('open');
    zoomReset.click();
    document.body.classList.add('weld-focus-mode');exitFocus.hidden=false;
    syncFocusViewport();
    scheduleFill();
  };
  fullscreen.onclick=e=>{e.preventDefault();e.stopPropagation();document.body.classList.contains('weld-focus-mode')?leaveFocus():enterFocus()};
  exitFocus.onclick=leaveFocus;
  const refit=()=>{
    if(!document.body.classList.contains('weld-focus-mode'))return;
    syncFocusViewport();
    zoomReset.click();
    scheduleFill();
  };
  window.addEventListener('orientationchange',refit);
  window.addEventListener('resize',refit);
  window.visualViewport?.addEventListener('resize',refit);

  const mq=matchMedia('(max-width:820px)');
  const apply=()=>{
    if(mq.matches){if(more&&more.parentNode!==appbar)appbar.appendChild(more);moveActions();cleanMenu()}
    else if(more&&more.parentNode===appbar){morePlaceholder.parentNode.insertBefore(more,morePlaceholder.nextSibling)}
  };
  const observer=new MutationObserver(()=>{moveActions();cleanMenu();apply()});observer.observe(toolbar,{childList:true,subtree:false});
  mq.addEventListener?.('change',apply);apply();setTimeout(()=>{moveActions();cleanMenu();apply()},0);setTimeout(()=>{moveActions();cleanMenu();apply()},250);
  window.addEventListener('pagehide',()=>{
    document.removeEventListener('pointerdown',closeMoreOutside,true);document.removeEventListener('keydown',closeMoreEscape);
    window.removeEventListener('orientationchange',refit);window.removeEventListener('resize',refit);window.visualViewport?.removeEventListener('resize',refit);observer.disconnect();
  },{once:true});
})();
</script>
"""
        elif entry_match or grid_match or is_favorites:
            script = """
<script data-responsive-header-v7>
(() => {
  const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;
  document.body.classList.add('weld-simple-header-v7');
  const label=back.textContent.includes('工事')?'工事一覧':'戻る';back.innerHTML=`‹ <span class="weld-back-label">${label}</span>`;
  top.insertBefore(back,top.firstChild);
})();
</script>
"""
        else:
            script = """
<script data-responsive-header-v7>
(() => {document.body.classList.add('weld-simple-header-v7')})();
</script>
"""

        html = html.replace("</head>", common_style + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint