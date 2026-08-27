import json
import re
import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request


def create_global_favorites_blueprint(db_path: Path):
    blueprint = Blueprint("global_favorites", __name__)

    @blueprint.get("/favorites")
    def favorites():
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id, project_name, original_pdf_name FROM projects ORDER BY id DESC"
            ).fetchall()
        projects = [
            {"id": row["id"], "projectName": row["project_name"], "pdfName": row["original_pdf_name"]}
            for row in rows
        ]
        return render_template("global_favorites.html", projects_json=json.dumps(projects, ensure_ascii=False))

    @blueprint.after_app_request
    def add_favorites_navigation(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        html = response.get_data(as_text=True)
        if "</body>" not in html or "data-global-favorites-launch" in html:
            return response
        path = request.path

        style = """
<style data-responsive-ui-polish>
.global-header-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.secondary-favorite-nav{border-color:#f9ab00!important;color:#8a5a00!important;background:#fff8e1!important;font-weight:800!important;white-space:nowrap}
@media(max-width:480px){.global-header-actions{width:100%!important;display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;gap:8px!important}.global-header-actions>.button,.global-header-actions>.primary{width:100%!important;min-width:0!important;padding-left:8px!important;padding-right:8px!important}body[data-ui-page=favorites] .top,body[data-ui-page=thumb-grid] .top{align-items:flex-start;gap:8px}body[data-ui-page=favorites] .top .button,body[data-ui-page=thumb-grid] .top .button{flex:0 0 auto;white-space:nowrap;padding-left:9px;padding-right:9px}body[data-ui-page=favorites] .search{font-size:16px}}
@media(max-width:390px){body[data-ui-page=progress] .toolbar{overflow-x:auto!important;overflow-y:visible!important;scrollbar-width:none!important;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;justify-content:flex-start!important;padding-left:5px!important;padding-right:5px!important}body[data-ui-page=progress] .toolbar::-webkit-scrollbar{display:none}body[data-ui-page=progress] .toolbar>*{flex:0 0 auto!important}body[data-ui-page=progress] .toolbar .spacer{display:none!important}body[data-ui-page=progress] .compact-rotate,body[data-ui-page=progress] .compact-fullscreen{display:none!important}body[data-ui-page=progress] .page-favorite-view{min-width:40px!important}body[data-ui-page=thumb-grid] .toolbar{overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;white-space:nowrap}body[data-ui-page=thumb-grid] .toolbar::-webkit-scrollbar{display:none}body[data-ui-page=thumb-grid] .toolbar>*{flex:0 0 auto}body[data-ui-page=thumb-grid] .columns{margin-left:0!important}}
</style>
"""
        if "</head>" in html:
            html = html.replace("</head>", style + "</head>", 1)

        if re.fullmatch(r"(?:/weld)?/projects-screen", path):
            script = """
<script data-global-favorites-launch>
(() => {
  document.body.dataset.uiPage='projects';
  const header=document.querySelector('.header'),newButton=document.getElementById('new-project');if(!header||!newButton)return;
  const wrap=document.createElement('div');wrap.className='global-header-actions';
  const fav=document.createElement('button');fav.type='button';fav.className='button secondary-favorite-nav';fav.textContent='★ お気に入り';fav.title='工事を横断してお気に入りページを表示';fav.onclick=()=>location.href='favorites';
  newButton.parentNode.insertBefore(wrap,newButton);wrap.appendChild(fav);wrap.appendChild(newButton);
})();
</script>
"""
            response.set_data(html.replace("</body>", script + "</body>", 1));return response

        if re.fullmatch(r"(?:/weld)?/favorites", path):
            response.set_data(html.replace("</body>", "<script data-global-favorites-launch>document.body.dataset.uiPage='favorites';</script></body>", 1));return response

        match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/(entry|progress|thumbnails)", path)
        if not match:
            return response
        project_id, source = match.groups()
        if source == "progress":
            html = html.replace("longEdge=320", "longEdge=500")
        script = f"""
<script data-global-favorites-launch>
(() => {{
  const projectId={project_id},source={source!r};document.body.dataset.uiPage=source==='progress'?'progress':(source==='thumbnails'?'thumb-grid':'entry');
  const goFavorites=()=>location.href='/weld/favorites',pageInput=document.getElementById('page'),currentPage=()=>Math.max(1,Number(pageInput?.value)||1),goEntry=()=>location.href=`/weld/projects/${{projectId}}/entry?page=${{currentPage()}}`;
  const moreMenu=document.querySelector('.more-menu');
  if(moreMenu){{
    if(source==='progress'&&!moreMenu.querySelector('[data-more-rotate]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.moreRotate='1';b.textContent='↻ 90°回転';b.onclick=()=>document.getElementById('rotateCompact')?.click();moreMenu.insertBefore(b,moreMenu.firstChild)}}
    if(source==='progress'&&!moreMenu.querySelector('[data-more-fullscreen]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.moreFullscreen='1';b.textContent='⛶ 全画面';b.onclick=()=>document.getElementById('fullscreenCompact')?.click();moreMenu.insertBefore(b,moreMenu.children[1]||null)}}
    if(source==='progress'&&!moreMenu.querySelector('[data-go-entry]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.goEntry='1';b.textContent='✎ 図面エントリーへ';b.onclick=goEntry;moreMenu.appendChild(b)}}
    if(!moreMenu.querySelector('[data-go-favorites]')){{const b=document.createElement('button');b.type='button';b.className='button';b.dataset.goFavorites='1';b.textContent='★ お気に入り一覧';b.onclick=goFavorites;moreMenu.appendChild(b)}}
  }} else if(source==='thumbnails'){{
    const toolbar=document.querySelector('.toolbar');if(toolbar&&!toolbar.querySelector('[data-go-favorites]')){{const b=document.createElement('button');b.type='button';b.className='button secondary-favorite-nav';b.dataset.goFavorites='1';b.textContent='★ お気に入り';b.onclick=goFavorites;toolbar.appendChild(b)}}
  }} else {{
    const controls=document.querySelector('.controls');if(controls&&!controls.querySelector('[data-go-favorites]')){{const b=document.createElement('button');b.type='button';b.className='button secondary-favorite-nav';b.dataset.goFavorites='1';b.textContent='★ 一覧';b.onclick=goFavorites;controls.appendChild(b)}}
  }}
  if(source==='progress'&&pageInput){{
    const storageKey=`weldFavoritePages:${{projectId}}`;let lastPage=0;
    const read=()=>{{try{{const a=JSON.parse(localStorage.getItem(storageKey)||'[]');return new Set(Array.isArray(a)?a.map(Number).filter(Number.isFinite):[])}}catch(_e){{return new Set()}}}};
    const sync=()=>{{const star=document.querySelector('.page-favorite-view');if(!star)return;const p=currentPage(),on=read().has(p);star.textContent=on?'★':'☆';star.classList.toggle('is-favorite',on);star.title=on?'お気に入り解除':'お気に入り登録';lastPage=p}};
    const timer=setInterval(()=>{{if(currentPage()!==lastPage)sync()}},200);window.addEventListener('pagehide',()=>clearInterval(timer),{{once:true}});window.addEventListener('pageshow',sync);window.addEventListener('focus',sync);document.addEventListener('visibilitychange',()=>{{if(!document.hidden)sync()}});window.addEventListener('storage',e=>{{if(e.key===storageKey)sync()}});setTimeout(sync,0);
  }}
}})();
</script>
"""
        response.set_data(html.replace("</body>", script + "</body>", 1));return response

    return blueprint
