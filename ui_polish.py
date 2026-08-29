import re

from flask import Blueprint, request


def create_ui_polish_blueprint():
    blueprint = Blueprint("ui_polish", __name__)

    @blueprint.after_app_request
    def polish_ui(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-responsive-ui-polish" in html:
            return response

        path = request.path
        styles = """
<style data-responsive-ui-polish>
:root{--favorite:#f9ab00;--favorite-bg:#fff8e1}
body[data-ui-page="progress"] .ui3-pages,body[data-ui-page="progress"] .ui3-drawing{display:flex;align-items:center;gap:6px}
@media(min-width:821px){
  body[data-ui-page="progress"] .toolbar{display:flex!important;flex-wrap:nowrap!important;align-items:center!important;gap:6px!important}
  body[data-ui-page="progress"] .ui3-pages{display:flex!important;flex:0 0 auto!important;align-items:center!important;gap:6px!important}
  body[data-ui-page="progress"] .ui3-pages .nav-button{flex:0 0 auto!important;margin:0!important}
  body[data-ui-page="progress"] .ui3-pages .page-field{display:flex!important;flex:0 0 auto!important;align-items:center!important;margin:0!important}
  body[data-ui-page="progress"] .ui3-drawing{display:flex!important;flex:0 0 auto!important;align-items:center!important;gap:6px!important}
}
@media(max-width:480px){
  .global-header-actions{width:100%!important;display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;gap:8px!important}
  .global-header-actions>.button,.global-header-actions>.primary{width:100%!important;min-width:0!important;padding-left:8px!important;padding-right:8px!important}
  body[data-ui-page="favorites"] .top,body[data-ui-page="thumb-grid"] .top{align-items:flex-start;gap:8px}
  body[data-ui-page="favorites"] .top .button,body[data-ui-page="thumb-grid"] .top .button{flex:0 0 auto;white-space:nowrap;padding-left:9px;padding-right:9px}
  body[data-ui-page="favorites"] .toolbar{gap:6px}
  body[data-ui-page="favorites"] .search{font-size:16px}
}
@media(max-width:390px){
  body[data-ui-page="progress"] .toolbar{overflow-x:auto!important;overflow-y:visible!important;scrollbar-width:none!important;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;justify-content:flex-start!important;padding-left:max(5px,env(safe-area-inset-left))!important;padding-right:max(5px,env(safe-area-inset-right))!important}
  body[data-ui-page="progress"] .toolbar::-webkit-scrollbar{display:none}
  body[data-ui-page="progress"] .toolbar>*{flex:0 0 auto!important}
  body[data-ui-page="progress"] .toolbar .spacer{display:none!important}
  body[data-ui-page="progress"] .compact-rotate,body[data-ui-page="progress"] .compact-fullscreen{display:none!important}
  body[data-ui-page="progress"] .page-favorite-view{min-width:40px!important}
  body[data-ui-page="progress"] .more{margin-left:0!important}
  body[data-ui-page="thumb-grid"] .toolbar{overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;white-space:nowrap}
  body[data-ui-page="thumb-grid"] .toolbar::-webkit-scrollbar{display:none}
  body[data-ui-page="thumb-grid"] .toolbar>*{flex:0 0 auto}
  body[data-ui-page="thumb-grid"] .columns{margin-left:0!important}
}
</style>
"""
        scripts = []

        if re.fullmatch(r"(?:/weld)?/projects/\d+/progress", path):
            scripts.append("""
<script data-responsive-ui-polish>
(() => {
  document.body.dataset.uiPage='progress';
  const menu=document.querySelector('.more-menu');
  const rotate=document.getElementById('rotateCompact');
  const fullscreen=document.getElementById('fullscreenCompact');
  if(menu){
    if(!menu.querySelector('[data-more-rotate]')){const b=document.createElement('button');b.type='button';b.className='button';b.dataset.moreRotate='1';b.textContent='↻ 90°回転';b.onclick=()=>{rotate?.click();document.getElementById('moreMenu')?.removeAttribute('open')};menu.insertBefore(b,menu.firstChild)}
    if(!menu.querySelector('[data-more-fullscreen]')){const b=document.createElement('button');b.type='button';b.className='button';b.dataset.moreFullscreen='1';b.textContent='⛶ 全画面';b.onclick=()=>{fullscreen?.click();document.getElementById('moreMenu')?.removeAttribute('open')};menu.insertBefore(b,menu.children[1]||null)}
  }
  const toolbar=document.querySelector('.toolbar');
  if(toolbar){toolbar.setAttribute('aria-label','進捗画面ツールバー')}
})();
</script>
""")
        elif re.fullmatch(r"(?:/weld)?/projects-screen", path):
            scripts.append("<script data-responsive-ui-polish>document.body.dataset.uiPage='projects';</script>")
        elif re.fullmatch(r"(?:/weld)?/projects/\d+/thumbnails", path):
            scripts.append("<script data-responsive-ui-polish>document.body.dataset.uiPage='thumb-grid';</script>")
        elif re.fullmatch(r"(?:/weld)?/favorites", path):
            scripts.append("<script data-responsive-ui-polish>document.body.dataset.uiPage='favorites';</script>")
        else:
            return response

        html = html.replace("</head>", styles + "</head>", 1)
        html = html.replace("</body>", "".join(scripts) + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint