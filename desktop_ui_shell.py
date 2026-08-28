import re

from flask import Blueprint, request


def create_desktop_ui_shell_blueprint():
    blueprint = Blueprint("desktop_ui_shell", __name__)

    @blueprint.after_app_request
    def apply_desktop_ui_shell(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "data-weld-desktop-shell-v1" in html:
            return response

        path = request.path
        progress = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", path)
        entry = re.fullmatch(r"(?:/weld)?/projects/(\d+)/entry", path)
        thumbs = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        progress_list = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress-list", path)
        favorites = re.fullmatch(r"(?:/weld)?/favorites", path)

        if not any((progress, entry, thumbs, progress_list, favorites)):
            return response
        if progress and request.args.get("viewer") == "1":
            return response

        css = r"""
<style data-weld-desktop-shell-v1>
@media(min-width:821px){
  html body .ui3-appbar{display:flex!important;position:sticky;top:0;z-index:120;min-height:56px;align-items:center;gap:6px;padding:4px 12px;background:#fff;border-bottom:1px solid #e5e7eb}
  .ui3-back,.ui3-icon{min-width:48px;height:48px;padding:0 10px;border:0;border-radius:10px;background:transparent;color:#1967d2;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;font:inherit;font-weight:800;cursor:pointer;white-space:nowrap}
  .ui3-back{gap:3px}.ui3-back::before{content:'‹';font-size:1.7rem;font-weight:500;line-height:1}.ui3-icon{width:48px;padding:0;color:#202124;font-size:1.2rem}.ui3-back:hover,.ui3-icon:hover{background:#f1f3f4}
  .ui3-title{min-width:0;flex:1;padding:0 4px}.ui3-title strong{display:block;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ui3-title small{display:block;margin-top:1px;color:#6b7280;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.ui3-progress main,body.ui3-entry main{padding-top:0!important}body.ui3-progress main>.top,body.ui3-entry main>.top{display:none!important}
  body.ui3-progress .toolbar,body.ui3-entry .controls{top:56px!important}
  .ui3-pages,.ui3-drawing{display:flex;align-items:center;gap:6px}.ui3-drawing{margin-left:6px}
  .ui3-drawing>.compact-rotate{display:none!important}
  .ui3-drawing>.button,.ui3-drawing>a.button{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 10px;text-decoration:none}
  body.ui3-grid main,body.ui3-favorites main,body.ui3-list main{padding-top:0!important}body.ui3-grid .top,body.ui3-favorites .top,body.ui3-list .topbar{display:none!important}
  body.ui3-grid .toolbar,body.ui3-favorites .toolbar{top:56px!important}body.ui3-list .filters{top:56px!important}
}
</style>
"""
        html = html.replace("</head>", css + "\n</head>", 1)
        response.set_data(html)
        return response

    return blueprint
