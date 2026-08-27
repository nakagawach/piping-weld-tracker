import re

from flask import Blueprint, request


def create_responsive_header_blueprint():
    blueprint = Blueprint("responsive_header", __name__)

    @blueprint.after_app_request
    def apply_responsive_header(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-responsive-header-v4" in html:
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
<style data-responsive-header-v4>
:root{--appbar-h:50px}
.weld-mobile-appbar{display:none}
@media(max-width:820px){
  .weld-mobile-appbar{display:flex;align-items:center;gap:8px;min-height:var(--appbar-h);padding:5px max(8px,env(safe-area-inset-right)) 5px max(8px,env(safe-area-inset-left));background:#fff;border-bottom:1px solid #dadce0;position:sticky;top:0;z-index:80}
  .weld-appbar-back{flex:0 0 auto;min-height:40px;padding:0 9px;border:0;border-radius:9px;background:#f1f3f4;color:#202124;font-weight:800;white-space:nowrap}
  .weld-appbar-title{min-width:0;flex:1;text-align:left}
  .weld-appbar-title strong{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .weld-appbar-title small{display:block;margin-top:1px;color:#5f6368;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .weld-mobile-appbar>.more{display:block!important;flex:0 0 auto;position:relative!important}
  .weld-mobile-appbar>.more summary{min-width:40px!important;height:40px!important}
  .weld-mobile-appbar .more-menu{right:0!important;top:44px!important;width:min(240px,calc(100vw - 16px))!important;z-index:100!important}

  body.weld-progress-v4 main{padding:0!important;max-width:none!important}
  body.weld-progress-v4 .top{display:none!important}
  body.weld-progress-v4 .card{border:0!important;border-radius:0!important}
  body.weld-progress-v4 .toolbar{position:sticky!important;top:var(--appbar-h)!important;z-index:60!important;height:auto!important;min-height:48px!important;display:flex!important;flex-wrap:wrap!important;align-items:center!important;gap:4px!important;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left))!important;white-space:normal!important;background:#fff!important}
  body.weld-progress-v4 .toolbar>.spacer,body.weld-progress-v4 .toolbar>.desktop-tools,body.weld-progress-v4 .toolbar>.more{display:none!important}
  body.weld-progress-v4 .weld-page-nav-group{display:flex;align-items:center;gap:3px;flex:0 1 auto;min-width:0}
  body.weld-progress-v4 .weld-action-group{display:flex;align-items:center;justify-content:flex-end;gap:4px;flex:1 1 auto;min-width:0}
  body.weld-progress-v4 .weld-page-nav-group .nav-button{min-width:38px!important;padding:0 6px!important}
  body.weld-progress-v4 .weld-page-nav-group .page-field{gap:2px!important;min-width:0!important}
  body.weld-progress-v4 .weld-page-nav-group .page-field>span:first-child{display:none!important}
  body.weld-progress-v4 .weld-page-nav-group .page-field input{width:38px!important;min-height:40px!important;border:0!important;background:#f1f3f4!important;font-weight:800!important;padding:0 3px!important}
  body.weld-progress-v4 .weld-page-nav-group .page-total{font-size:.78rem!important}
  body.weld-progress-v4 .weld-action-group>.button{min-width:40px!important;min-height:40px!important;padding:0 6px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important}
  body.weld-progress-v4 .weld-action-group>.page-favorite-view{font-size:1.35rem!important}
  body.weld-progress-v4 .weld-action-group>.compact-rotate,body.weld-progress-v4 .weld-action-group>.compact-fullscreen{display:inline-flex!important}
  body.weld-progress-v4 .statusline{display:none!important}
}
@media(max-width:390px) and (orientation:portrait){
  body.weld-progress-v4 .toolbar{align-items:stretch!important}
  body.weld-progress-v4 .weld-page-nav-group{flex:1 1 100%;justify-content:center}
  body.weld-progress-v4 .weld-action-group{flex:1 1 100%;justify-content:space-between}
  body.weld-progress-v4 .weld-action-group>.button{flex:1 1 0;max-width:56px}
  body.weld-progress-v4 .viewer{max-height:calc(100dvh - var(--appbar-h) - 98px - 31px - 62px)!important;min-height:calc(100dvh - var(--appbar-h) - 98px - 31px - 62px)!important}
}
@media(min-width:391px) and (max-width:820px){
  body.weld-progress-v4 .toolbar{flex-wrap:nowrap!important}
  body.weld-progress-v4 .viewer{max-height:calc(100dvh - var(--appbar-h) - 48px - 31px - 62px)!important;min-height:calc(100dvh - var(--appbar-h) - 48px - 31px - 62px)!important}
}
@media(max-width:820px) and (orientation:landscape){
  .weld-appbar-title small{display:none}
  body.weld-progress-v4 .summary{height:31px!important;padding:3px 6px!important}
  body.weld-progress-v4 .progress-thumbs{height:62px!important;padding:3px 5px!important}
  body.weld-progress-v4 .progress-thumb{flex-basis:66px!important}
  body.weld-progress-v4 .progress-thumb img{height:38px!important}
}

/* non-viewer screens: back/navigation stays on the leading side */
@media(max-width:820px){
  body.weld-simple-header-v4 main{padding-top:0!important}
  body.weld-simple-header-v4 .top{display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:8px!important;background:#fff!important;border-bottom:1px solid #dadce0!important;padding:5px max(8px,env(safe-area-inset-right)) 5px max(8px,env(safe-area-inset-left))!important;margin:0 0 8px!important;position:sticky!important;top:0!important;z-index:50!important}
  body.weld-simple-header-v4 .top>#back{order:-10!important;flex:0 0 auto!important;width:auto!important;min-width:40px!important;min-height:40px!important;padding:0 9px!important;border:0!important;background:#f1f3f4!important}
  body.weld-simple-header-v4 .top>#back .weld-back-label{display:none!important}
  body.weld-simple-header-v4 .top>div:first-of-type{min-width:0!important;flex:1 1 auto!important}
  body.weld-simple-header-v4 .top .title{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
  body.weld-simple-header-v4 .top .meta,body.weld-simple-header-v4 .top .sub{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
}
</style>
"""

        if progress_match:
            script = """
<script data-responsive-header-v4>
(() => {
  const toolbar=document.querySelector('.toolbar');
  const top=document.querySelector('.top');
  const back=document.getElementById('back');
  const more=document.getElementById('moreMenu');
  const prev=document.getElementById('prev'),pageField=toolbar?.querySelector('.page-field'),next=document.getElementById('next');
  if(!toolbar||!back||!prev||!pageField||!next)return;
  document.body.classList.add('weld-progress-v4');

  const appbar=document.createElement('div');appbar.className='weld-mobile-appbar';appbar.setAttribute('role','navigation');appbar.setAttribute('aria-label','画面ナビゲーション');
  const appBack=document.createElement('button');appBack.type='button';appBack.className='weld-appbar-back';appBack.innerHTML='‹ <span>工事一覧</span>';appBack.onclick=()=>back.click();
  const title=document.createElement('div');title.className='weld-appbar-title';
  const meta=top?.querySelector('.meta')?.textContent?.trim()||'';title.innerHTML='<strong>進捗入力</strong><small></small>';title.querySelector('small').textContent=meta;
  appbar.append(appBack,title);toolbar.parentNode.insertBefore(appbar,toolbar);

  const pageGroup=document.createElement('div');pageGroup.className='weld-page-nav-group';pageGroup.setAttribute('aria-label','ページ移動');
  toolbar.insertBefore(pageGroup,toolbar.firstChild);pageGroup.append(prev,pageField,next);
  const actionGroup=document.createElement('div');actionGroup.className='weld-action-group';actionGroup.setAttribute('aria-label','図面操作');toolbar.appendChild(actionGroup);
  const morePlaceholder=document.createComment('more-menu-home');if(more)more.parentNode.insertBefore(morePlaceholder,more);

  const moveActions=()=>{
    const candidates=[toolbar.querySelector('.page-favorite-view'),document.getElementById('rotateCompact'),document.getElementById('fullscreenCompact'),toolbar.querySelector('[aria-label="ページ一覧"]'),toolbar.querySelector('[aria-label="進捗一覧"]')];
    for(const el of candidates){if(el&&el.parentNode!==actionGroup)actionGroup.appendChild(el)}
  };
  const closeMoreOutside=e=>{if(more?.open&&!more.contains(e.target))more.removeAttribute('open')};
  const closeMoreEscape=e=>{if(e.key==='Escape'&&more?.open)more.removeAttribute('open')};
  document.addEventListener('pointerdown',closeMoreOutside,true);
  document.addEventListener('keydown',closeMoreEscape);
  window.addEventListener('pagehide',()=>{document.removeEventListener('pointerdown',closeMoreOutside,true);document.removeEventListener('keydown',closeMoreEscape)},{once:true});

  const mq=matchMedia('(max-width:820px)');
  const apply=()=>{
    if(mq.matches){if(more&&more.parentNode!==appbar)appbar.appendChild(more);moveActions()}
    else if(more&&more.parentNode===appbar){morePlaceholder.parentNode.insertBefore(more,morePlaceholder.nextSibling)}
  };
  const observer=new MutationObserver(()=>{moveActions();apply()});observer.observe(toolbar,{childList:true,subtree:false});
  mq.addEventListener?.('change',apply);apply();setTimeout(()=>{moveActions();apply()},0);setTimeout(()=>{moveActions();apply()},250);
})();
</script>
"""
        elif entry_match or grid_match or is_favorites:
            script = """
<script data-responsive-header-v4>
(() => {
  const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;
  document.body.classList.add('weld-simple-header-v4');
  const label=back.textContent.includes('工事')?'工事一覧':'戻る';back.innerHTML=`‹ <span class="weld-back-label">${label}</span>`;
  top.insertBefore(back,top.firstChild);
})();
</script>
"""
        else:
            script = """
<script data-responsive-header-v4>
(() => {document.body.classList.add('weld-simple-header-v4')})();
</script>
"""

        html = html.replace("</head>", common_style + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
