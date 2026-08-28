import re

from flask import Blueprint, request


def create_desktop_ui_shell_blueprint():
    blueprint = Blueprint("desktop_ui_shell", __name__)

    @blueprint.after_app_request
    def apply_desktop_ui_shell(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "data-weld-desktop-shell-v3" in html:
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
        if progress and request.args.get("viewer") == "1":
            return response

        css = r"""
<style data-weld-desktop-shell-v3>
/* Shared states: disabled means unavailable, never loading. */
body.ui3-progress #prev:disabled,
body.ui3-progress #next:disabled,
body.ui3-entry #prev:disabled,
body.ui3-entry #next:disabled,
body.ui3-progress .progress-thumb:disabled{
  opacity:.42!important;
  color:#9aa0a6!important;
  cursor:default!important;
  box-shadow:none!important;
  pointer-events:none!important;
}
body.ui3-progress #prev:disabled,
body.ui3-progress #next:disabled,
body.ui3-entry #prev:disabled,
body.ui3-entry #next:disabled{background:transparent!important}
body.ui3-progress .progress-thumb:disabled{
  opacity:.62!important;
  border-color:#c7cbd1!important;
  background:#eef0f2!important;
}
body.ui3-progress .progress-thumb:disabled img{filter:grayscale(1);opacity:.68}

@media(min-width:821px){
  :root{--ui3-desktop-header:60px;--ui3-control:42px;--ui3-line:#e4e7eb;--ui3-hover:#f3f4f6;--ui3-text:#202124;--ui3-muted:#6b7280;--ui3-blue:#1967d2}

  html body .ui3-appbar{
    display:flex!important;position:sticky;top:0;z-index:120;
    min-height:var(--ui3-desktop-header);height:var(--ui3-desktop-header);
    align-items:center;gap:8px;padding:6px 14px;
    background:rgba(255,255,255,.98);border-bottom:1px solid var(--ui3-line);
    box-shadow:0 1px 2px #00000008;
  }
  .ui3-back,.ui3-icon{
    height:44px;min-height:44px;border:0;border-radius:9px;background:transparent;
    display:inline-flex;align-items:center;justify-content:center;text-decoration:none;
    font:inherit;font-weight:700;cursor:pointer;white-space:nowrap;
  }
  .ui3-back{min-width:auto;padding:0 10px 0 7px;gap:3px;color:var(--ui3-blue);font-size:.9rem}
  .ui3-back::before{content:'‹';font-size:1.65rem;font-weight:500;line-height:1}
  .ui3-icon{width:44px;min-width:44px;padding:0;color:var(--ui3-text);font-size:1.18rem}
  .ui3-back:hover,.ui3-icon:hover{background:var(--ui3-hover)}
  .ui3-title{min-width:0;flex:1;padding:0 6px}
  .ui3-title strong{display:block;font-size:1rem;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ui3-title small{display:block;margin-top:1px;color:var(--ui3-muted);font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

  body.ui3-progress main,body.ui3-entry main{padding-top:0!important}
  body.ui3-progress main>.top,body.ui3-entry main>.top{display:none!important}
  body.ui3-progress .toolbar,body.ui3-entry .controls{top:var(--ui3-desktop-header)!important}

  /* Second row follows one rule on Progress and Entry:
     page navigation left, document tools right, primary actions stay textual. */
  body.ui3-progress .toolbar,body.ui3-entry .controls{
    min-height:54px!important;padding:5px 10px!important;gap:5px!important;
    align-items:center!important;flex-wrap:nowrap!important;overflow-x:auto!important;
    background:#fff!important;border-bottom:1px solid var(--ui3-line)!important;
    scrollbar-width:thin;
  }
  .ui3-pages,.ui3-drawing{display:flex;align-items:center;gap:2px;flex:0 0 auto}
  .ui3-pages{padding-right:8px;margin-right:3px;border-right:1px solid var(--ui3-line)}
  .ui3-drawing{margin-left:0}

  /* Uniform icon buttons. */
  .ui3-pages .nav-button,
  .ui3-drawing>.button,.ui3-drawing>a.button,
  body.ui3-entry #prev,body.ui3-entry #next,
  body.ui3-entry #rotate,
  body.ui3-entry .page-favorite-view,
  body.ui3-entry [data-thumbnail-grid-launch],
  body.ui3-progress .desktop-tools>.button:not(.zoom-value){
    width:var(--ui3-control)!important;min-width:var(--ui3-control)!important;
    height:var(--ui3-control)!important;min-height:var(--ui3-control)!important;
    padding:0!important;border:0!important;border-radius:8px!important;
    background:transparent!important;display:inline-flex!important;align-items:center!important;
    justify-content:center!important;text-decoration:none!important;color:var(--ui3-text)!important;
  }
  .ui3-pages .nav-button:hover,
  .ui3-drawing>.button:hover,.ui3-drawing>a.button:hover,
  body.ui3-entry #prev:hover,body.ui3-entry #next:hover,body.ui3-entry #rotate:hover,
  body.ui3-entry .page-favorite-view:hover,body.ui3-entry [data-thumbnail-grid-launch]:hover,
  body.ui3-progress .desktop-tools>.button:not(.zoom-value):hover{background:var(--ui3-hover)!important}

  /* Page and zoom values are status values, not action labels. */
  .ui3-pages .page-field{height:var(--ui3-control)!important;gap:4px!important;padding:0 5px!important}
  .ui3-pages .page-field>span:first-child{display:none!important}
  .ui3-pages .page-field input{width:48px!important;min-height:36px!important;padding:0 5px!important;border:1px solid #d6d9de!important;border-radius:7px!important;background:#fff!important;font-weight:750!important;text-align:center!important}
  .ui3-pages .page-total{font-size:.8rem!important;color:var(--ui3-muted)!important}
  body.ui3-progress .desktop-tools{display:flex!important;align-items:center!important;gap:2px!important;margin-left:auto!important;padding-left:7px!important;border-left:1px solid var(--ui3-line)!important}
  body.ui3-progress .desktop-tools>.zoom-value{height:var(--ui3-control)!important;min-height:var(--ui3-control)!important;min-width:58px!important;padding:0 8px!important;border:0!important;border-radius:8px!important;background:transparent!important;color:var(--ui3-text)!important;font-weight:700!important}
  body.ui3-progress .desktop-tools>.zoom-value:hover{background:var(--ui3-hover)!important}
  .ui3-drawing>.compact-rotate{display:none!important}

  /* Hide text on utility controls and give every utility a stable icon.
     title/aria-label from existing markup remains available as tooltip/accessibility name. */
  body.ui3-progress .desktop-tools #zoomOut{font-size:0!important}body.ui3-progress .desktop-tools #zoomOut::before{content:'−';font-size:1.25rem}
  body.ui3-progress .desktop-tools #zoomIn{font-size:0!important}body.ui3-progress .desktop-tools #zoomIn::before{content:'＋';font-size:1.12rem}
  body.ui3-progress .desktop-tools #rotate{font-size:0!important}body.ui3-progress .desktop-tools #rotate::before{content:'↻';font-size:1.1rem}
  body.ui3-progress .desktop-tools #viewReset{font-size:0!important}body.ui3-progress .desktop-tools #viewReset::before{content:'⌖';font-size:1.15rem}
  body.ui3-progress .desktop-tools #reload{font-size:0!important}body.ui3-progress .desktop-tools #reload::before{content:'⟳';font-size:1.08rem}
  body.ui3-progress .desktop-tools #fullscreen{font-size:0!important}body.ui3-progress .desktop-tools #fullscreen::before{content:'⛶';font-size:1.08rem}

  /* Entry keeps OCR / Save textual because they are primary actions; utility controls are icon-only. */
  body.ui3-entry #prev,body.ui3-entry #next,body.ui3-entry #rotate,body.ui3-entry [data-thumbnail-grid-launch]{font-size:0!important}
  body.ui3-entry #prev::before{content:'‹';font-size:1.45rem}
  body.ui3-entry #next::before{content:'›';font-size:1.45rem}
  body.ui3-entry #rotate::before{content:'↻';font-size:1.1rem}
  body.ui3-entry [data-thumbnail-grid-launch]::before{content:'▦';font-size:1.05rem}
  body.ui3-entry #ocr{margin-left:auto!important}
  body.ui3-entry #ocr,body.ui3-entry #save{min-height:42px!important;padding:0 13px!important;border-radius:8px!important;font-weight:750!important;flex:0 0 auto!important}

  body.ui3-grid main,body.ui3-favorites main,body.ui3-list main{padding-top:0!important}
  body.ui3-grid .top,body.ui3-favorites .top,body.ui3-list .topbar{display:none!important}
  body.ui3-grid .toolbar,body.ui3-favorites .toolbar{top:var(--ui3-desktop-header)!important}
  body.ui3-list .filters{top:var(--ui3-desktop-header)!important}

  body.ui3-projects .ui3-root{
    position:sticky!important;top:0!important;z-index:120!important;
    min-height:var(--ui3-desktop-header)!important;margin:0 0 16px!important;padding:6px 14px!important;
    display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px!important;
    background:#fff!important;border-bottom:1px solid var(--ui3-line)!important;
  }
  body.ui3-projects .ui3-root>div:first-child{min-width:0;flex:1}
  body.ui3-projects .ui3-root-actions{display:flex!important;align-items:center!important;gap:4px!important;flex-wrap:nowrap!important}
}

@media(min-width:821px) and (max-width:1100px){
  html body .ui3-appbar{padding-left:8px;padding-right:8px}
  .ui3-back span{display:none}.ui3-back{width:44px;min-width:44px;padding:0}
  body.ui3-progress .toolbar,body.ui3-entry .controls{gap:2px!important;padding-left:6px!important;padding-right:6px!important}
}
</style>
"""
        html = html.replace("</head>", css + "\n</head>", 1)

        script = r"""
<script data-weld-desktop-shell-v3>
(() => {
  const setTitle=(selector,text)=>{const el=document.querySelector(selector);if(el&&!el.title)el.title=text};
  setTitle('#prev','前のページ');setTitle('#next','次のページ');
  setTitle('#zoomOut','縮小');setTitle('#zoomReset','100%に戻す');setTitle('#zoomIn','拡大');
  setTitle('#rotate','90度回転');setTitle('#viewReset','位置リセット');setTitle('#reload','再読込');setTitle('#fullscreen','全画面');
  setTitle('[data-thumbnail-grid-launch]','ページ一覧');setTitle('.page-favorite-view','お気に入り');
  const progressList=document.querySelector('[aria-label="進捗一覧"]');if(progressList&&!progressList.title)progressList.title='進捗一覧';
})();
</script>
"""
        html = html.replace("</body>", script + "\n</body>", 1)

        if progress:
            state_script = r"""
<script data-weld-page-state-v2>
(() => {
  const thumbs=document.getElementById('progressThumbs');
  const pageInput=document.getElementById('page');
  if(!thumbs||!pageInput)return;
  const sync=()=>{
    const current=Number(pageInput.value);
    thumbs.querySelectorAll('.progress-thumb').forEach(button=>{
      const active=Number(button.dataset.page)===current;
      button.disabled=active;
      if(active){button.setAttribute('aria-current','page');button.title=`P${current}（表示中）`}
      else{button.removeAttribute('aria-current');button.title=`P${button.dataset.page}へ移動`}
    });
  };
  const observer=new MutationObserver(sync);
  observer.observe(thumbs,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
  pageInput.addEventListener('change',sync);
  sync();
})();
</script>
"""
            html = html.replace("</body>", state_script + "\n</body>", 1)

        response.set_data(html)
        return response

    return blueprint
