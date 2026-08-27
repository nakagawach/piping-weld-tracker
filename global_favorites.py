import json
import re
import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request

from navigation_ui import apply_navigation_ui


def create_global_favorites_blueprint(db_path: Path):
    blueprint = Blueprint("global_favorites", __name__)

    @blueprint.get("/favorites")
    def favorites():
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, project_name, original_pdf_name
                FROM projects
                ORDER BY id DESC
                """
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
        html = apply_navigation_ui(html, request.path)
        response.set_data(html)
        if "</body>" not in html or "data-global-favorites-launch" in html:
            return response
        path = request.path

        if re.fullmatch(r"(?:/weld)?/projects-screen", path):
            script = """
<script data-global-favorites-launch>
(() => {
  const header=document.querySelector('.header');
  const newButton=document.getElementById('new-project');
  if(!header||!newButton)return;
  const wrap=document.createElement('div');
  wrap.style.cssText='display:flex;gap:8px;align-items:center;flex-wrap:wrap';
  const fav=document.createElement('button');
  fav.type='button';fav.className='button';fav.textContent='★ お気に入り';fav.title='工事を横断してお気に入りページを表示';
  fav.style.cssText='border-color:#f9ab00;color:#8a5a00;font-weight:800;background:#fff8e1';
  fav.onclick=()=>location.href='favorites';
  newButton.parentNode.insertBefore(wrap,newButton);wrap.appendChild(fav);wrap.appendChild(newButton);
})();
</script>
"""
            response.set_data(html.replace("</body>", script + "</body>", 1))
            return response

        match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/(entry|progress|thumbnails)", path)
        if match:
            project_id, source = match.groups()

            if source == "progress" and "data-iphone-se-toolbar-v3" not in html:
                responsive_style = """
<style data-iphone-se-toolbar-v3>
@media(max-width:820px){
  .toolbar{gap:4px!important;padding-left:max(5px,env(safe-area-inset-left))!important;padding-right:max(5px,env(safe-area-inset-right))!important}
  .toolbar .desktop-tools{display:none!important}
  .toolbar .compact-rotate{display:inline-flex!important;align-items:center;justify-content:center}
  .toolbar .compact-fullscreen{display:none!important}
  .toolbar .more{display:block!important;flex:0 0 auto}
  .toolbar .more summary{min-width:42px;height:40px}
  .toolbar .nav-button{min-width:38px!important;padding-left:6px!important;padding-right:6px!important}
  .toolbar .page-field{gap:2px!important;flex:0 0 auto}
  .toolbar .page-field>span:first-child{display:none!important}
  .toolbar .page-field input{width:38px!important;min-height:40px!important;border:0!important;background:#f1f3f4!important;font-weight:800!important;padding:0 3px!important}
  .toolbar .page-total{font-size:.78rem!important}
  .toolbar .page-favorite-view{min-width:42px!important;padding:0 6px!important}
  .toolbar>[aria-label="ページ一覧"],.toolbar>[aria-label="進捗一覧"]{min-width:42px!important;padding:0 6px!important;display:inline-flex!important;align-items:center;justify-content:center}
  .more-menu{right:0!important;z-index:50!important;width:min(220px,calc(100vw - 16px))!important}
}
@media(max-width:480px) and (orientation:portrait){
  .toolbar{height:auto!important;min-height:90px!important;display:grid!important;grid-template-columns:40px minmax(72px,1fr) 40px 42px 42px 42px!important;grid-template-rows:42px 42px!important;gap:4px!important;align-items:center!important}
  .toolbar>#prev{grid-column:1;grid-row:1}.toolbar>.page-field{grid-column:2;grid-row:1;justify-self:center}.toolbar>#next{grid-column:3;grid-row:1}
  .toolbar>.page-favorite-view{grid-column:4;grid-row:1}.toolbar>.compact-rotate{grid-column:5;grid-row:1}.toolbar>.more{grid-column:6;grid-row:1}
  .toolbar>.spacer,.toolbar>.desktop-tools,.toolbar>.compact-fullscreen{display:none!important}
  .toolbar>[aria-label="ページ一覧"]{grid-column:1/4!important;grid-row:2!important;width:100%!important}
  .toolbar>[aria-label="進捗一覧"]{grid-column:4/7!important;grid-row:2!important;width:100%!important}
  body:not(.progress-fullscreen) .viewer{max-height:calc(100dvh - 183px)!important;min-height:calc(100dvh - 183px)!important}
}
@media(min-width:481px) and (max-width:820px){
  .toolbar{height:48px!important;display:flex!important;flex-wrap:nowrap!important;align-items:center!important}
  .toolbar>.spacer{display:none!important}
  .toolbar>*{flex:0 0 auto}
}
@media(max-width:820px) and (orientation:landscape){
  main{padding:0!important;max-width:none!important}
  .top,.statusline{display:none!important}
  .card{border:0!important;border-radius:0!important}
  .summary{height:31px!important;padding:3px 6px!important;gap:4px!important}
  .chip{padding:3px 7px!important;font-size:.73rem!important}
  .progress-thumbs{height:62px!important;padding:3px 5px!important}
  .progress-thumb{flex-basis:66px!important}.progress-thumb img{height:38px!important}
  body:not(.progress-fullscreen) .viewer{max-height:calc(100dvh - 141px)!important;min-height:calc(100dvh - 141px)!important}
}
</style>
"""
                html = html.replace("</head>", responsive_style + "</head>", 1)

            script = f"""
<script data-global-favorites-launch>
(() => {{
  const projectId={project_id};
  const source={source!r};
  const goFavorites=()=>location.href='/weld/favorites';
  const pageInput=document.getElementById('page');
  const currentPage=()=>Math.max(1,Number(pageInput?.value)||1);
  const goEntry=()=>location.href=`/weld/projects/${{projectId}}/entry?page=${{currentPage()}}`;

  const moreMenu=document.querySelector('.more-menu');
  if(moreMenu){{
    if(source==='progress'&&!moreMenu.querySelector('[data-go-fullscreen]')){{
      const full=document.createElement('button');full.type='button';full.className='button';full.dataset.goFullscreen='1';full.textContent='⛶ 全画面';full.title='全画面表示';full.onclick=()=>{{document.getElementById('fullscreenCompact')?.click();document.getElementById('moreMenu')?.removeAttribute('open')}};moreMenu.insertBefore(full,moreMenu.firstChild);
    }}
    if(source==='progress'&&!moreMenu.querySelector('[data-go-entry]')){{const entry=document.createElement('button');entry.type='button';entry.className='button';entry.dataset.goEntry='1';entry.textContent='✎ 図面エントリーへ';entry.title='現在ページを図面エントリーで開く';entry.onclick=goEntry;moreMenu.appendChild(entry);}}
    if(!moreMenu.querySelector('[data-go-favorites]')){{const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ お気に入り一覧';fav.title='工事横断のお気に入り一覧';fav.onclick=goFavorites;moreMenu.appendChild(fav);}}
  }} else {{
    const controls=document.querySelector('.controls');
    if(controls&&!controls.querySelector('[data-go-favorites]')){{const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ 一覧';fav.title='工事横断のお気に入り一覧';fav.onclick=goFavorites;controls.appendChild(fav);}}
    else if(!controls){{const top=document.querySelector('.top');if(top&&!top.querySelector('[data-go-favorites]')){{const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ お気に入り';fav.title='工事横断のお気に入り一覧';fav.style.cssText='border-color:#f9ab00;color:#8a5a00;font-weight:800;background:#fff8e1';fav.onclick=goFavorites;top.appendChild(fav);}}}}
  }}

  if(source==='progress'&&pageInput){{
    const storageKey=`weldFavoritePages:${{projectId}}`;let lastPage=0;
    const readFavorites=()=>{{try{{const raw=JSON.parse(localStorage.getItem(storageKey)||'[]');return new Set(Array.isArray(raw)?raw.map(Number).filter(Number.isFinite):[])}}catch(_e){{return new Set()}}}};
    const syncStar=()=>{{const star=document.querySelector('.page-favorite-view');if(!star)return;const p=currentPage(),favorites=readFavorites(),on=favorites.has(p);star.textContent=on?'★':'☆';star.classList.toggle('is-favorite',on);star.setAttribute('aria-label',on?`P${{p}} お気に入り解除`:`P${{p}} お気に入り登録`);star.title=on?'お気に入り解除':'お気に入り登録';lastPage=p;}};
    const checkPage=()=>{{const p=currentPage();if(p!==lastPage)syncStar()}};const timer=setInterval(checkPage,200);
    window.addEventListener('pagehide',()=>clearInterval(timer),{{once:true}});window.addEventListener('pageshow',syncStar);window.addEventListener('focus',syncStar);document.addEventListener('visibilitychange',()=>{{if(!document.hidden)syncStar()}});window.addEventListener('storage',e=>{{if(e.key===storageKey)syncStar()}});setTimeout(syncStar,0);
  }}
}})();
</script>
"""
            response.set_data(html.replace("</body>", script + "</body>", 1))
        return response

    return blueprint
