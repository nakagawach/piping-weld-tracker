import re

from flask import Blueprint, request


def create_desktop_ui_shell_blueprint():
    blueprint = Blueprint("desktop_ui_shell", __name__)

    @blueprint.after_app_request
    def apply_desktop_ui_shell(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "data-weld-desktop-shell-v2" in html:
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
<style data-weld-desktop-shell-v2>
/* Navigation state is shared across mouse and touch. Native disabled buttons must
   look inactive and must never show the page-loading cursor. */
body.ui3-progress #prev:disabled,
body.ui3-progress #next:disabled,
body.ui3-entry #prev:disabled,
body.ui3-entry #next:disabled{
  opacity:.38!important;
  color:#9aa0a6!important;
  background:transparent!important;
  cursor:not-allowed!important;
  box-shadow:none!important;
}
body.ui3-progress .progress-thumb:disabled{
  opacity:.58!important;
  border-color:#9aa0a6!important;
  background:#eef0f2!important;
  color:#6b7280!important;
  cursor:not-allowed!important;
  box-shadow:none!important;
}
body.ui3-progress .progress-thumb:disabled img{filter:grayscale(1);opacity:.72}

@media(min-width:821px){
  html body .ui3-appbar{
    display:flex!important;
    position:sticky;
    top:0;
    z-index:120;
    min-height:60px;
    align-items:center;
    gap:8px;
    padding:5px 16px;
    background:rgba(255,255,255,.98);
    border-bottom:1px solid #e5e7eb;
    box-shadow:0 1px 2px #0000000a;
  }
  .ui3-back,.ui3-icon{
    min-width:48px;
    height:48px;
    padding:0 10px;
    border:0;
    border-radius:10px;
    background:transparent;
    color:#1967d2;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    text-decoration:none;
    font:inherit;
    font-weight:800;
    cursor:pointer;
    white-space:nowrap;
  }
  .ui3-back{gap:3px}.ui3-back::before{content:'‹';font-size:1.7rem;font-weight:500;line-height:1}
  .ui3-icon{width:48px;padding:0;color:#202124;font-size:1.2rem}
  .ui3-back:hover,.ui3-icon:hover{background:#f1f3f4}
  .ui3-title{min-width:0;flex:1;padding:0 6px}
  .ui3-title strong{display:block;font-size:1.02rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ui3-title small{display:block;margin-top:1px;color:#6b7280;font-size:.74rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

  body.ui3-progress main,body.ui3-entry main{padding-top:0!important}
  body.ui3-progress main>.top,body.ui3-entry main>.top{display:none!important}
  body.ui3-progress .toolbar,body.ui3-entry .controls{top:60px!important}
  body.ui3-progress .toolbar{
    min-height:54px!important;
    padding:6px 10px!important;
    gap:8px!important;
    overflow-x:auto!important;
    scrollbar-width:thin;
  }
  .ui3-pages,.ui3-drawing{display:flex;align-items:center;gap:4px;flex:0 0 auto}
  .ui3-pages{padding-right:8px;border-right:1px solid #e5e7eb}
  .ui3-drawing{margin-left:4px}
  .ui3-pages .nav-button{min-width:44px!important;height:44px!important;padding:0 8px!important}
  .ui3-pages .page-field input{min-height:42px!important}
  .ui3-drawing>.compact-rotate{display:none!important}
  .ui3-drawing>.button,.ui3-drawing>a.button{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:42px;
    padding:0 10px;
    text-decoration:none;
  }
  body.ui3-progress .desktop-tools{margin-left:auto}

  body.ui3-entry .controls{
    min-height:54px!important;
    padding:6px 10px!important;
    gap:6px!important;
    overflow-x:auto!important;
    scrollbar-width:thin;
  }

  body.ui3-grid main,body.ui3-favorites main,body.ui3-list main{padding-top:0!important}
  body.ui3-grid .top,body.ui3-favorites .top,body.ui3-list .topbar{display:none!important}
  body.ui3-grid .toolbar,body.ui3-favorites .toolbar{top:60px!important}
  body.ui3-list .filters{top:60px!important}

  body.ui3-projects .ui3-root{
    position:sticky!important;
    top:0!important;
    z-index:120!important;
    min-height:60px!important;
    margin:0 0 16px!important;
    padding:6px 16px!important;
    display:flex!important;
    flex-direction:row!important;
    align-items:center!important;
    gap:10px!important;
    background:#fff!important;
    border-bottom:1px solid #e5e7eb!important;
  }
  body.ui3-projects .ui3-root>div:first-child{min-width:0;flex:1}
  body.ui3-projects .ui3-root-actions{display:flex!important;align-items:center!important;gap:6px!important;flex-wrap:nowrap!important}
}

/* Tablet / narrow desktop: preserve all actions but allow the second row to
   scroll instead of squeezing the title or making tiny hit targets. */
@media(min-width:821px) and (max-width:1100px){
  html body .ui3-appbar{padding-left:10px;padding-right:10px}
  .ui3-back span{display:none}.ui3-back{width:48px;padding:0}
  body.ui3-progress .toolbar,body.ui3-entry .controls{gap:4px!important}
  body.ui3-progress .desktop-tools{gap:4px!important}
  body.ui3-progress .desktop-tools .button{padding-left:8px!important;padding-right:8px!important}
}
</style>
"""
        html = html.replace("</head>", css + "\n</head>", 1)

        if progress:
            script = r"""
<script data-weld-page-state-v1>
(() => {
  const thumbs=document.getElementById('progressThumbs');
  const pageInput=document.getElementById('page');
  if(!thumbs||!pageInput)return;
  const sync=()=>{
    const current=Number(pageInput.value);
    thumbs.querySelectorAll('.progress-thumb').forEach(button=>{
      const active=Number(button.dataset.page)===current;
      button.disabled=active;
      if(active)button.setAttribute('aria-current','page');
      else button.removeAttribute('aria-current');
    });
  };
  const observer=new MutationObserver(sync);
  observer.observe(thumbs,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
  pageInput.addEventListener('change',sync);
  sync();
})();
</script>
"""
            html = html.replace("</body>", script + "\n</body>", 1)

        response.set_data(html)
        return response

    return blueprint
