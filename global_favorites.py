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
                """
                SELECT id, project_name, original_pdf_name
                FROM projects
                ORDER BY id DESC
                """
            ).fetchall()
        projects = [
            {
                "id": row["id"],
                "projectName": row["project_name"],
                "pdfName": row["original_pdf_name"],
            }
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

        if re.fullmatch(r"(?:/weld)?/projects-screen", path):
            style = """
<style data-global-favorites-layout>
@media(max-width:480px){
  .global-header-actions{width:100%;display:grid!important;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px!important}
  .global-header-actions>.button,.global-header-actions>#new-project{width:100%;min-width:0;padding-left:8px;padding-right:8px;white-space:nowrap}
}
</style>
"""
            script = """
<script data-global-favorites-launch>
(() => {
  const header=document.querySelector('.header');
  const newButton=document.getElementById('new-project');
  if(!header||!newButton)return;
  const wrap=document.createElement('div');
  wrap.className='global-header-actions';
  wrap.style.cssText='display:flex;gap:8px;align-items:center;flex-wrap:wrap';
  const fav=document.createElement('button');
  fav.type='button';fav.className='button';fav.textContent='★ お気に入り';fav.title='工事を横断してお気に入りページを表示';
  fav.style.cssText='border-color:#f9ab00;color:#8a5a00;font-weight:800;background:#fff8e1';
  fav.onclick=()=>location.href='favorites';
  newButton.parentNode.insertBefore(wrap,newButton);wrap.appendChild(fav);wrap.appendChild(newButton);
})();
</script>
"""
            html = html.replace("</head>", style + "</head>", 1)
            response.set_data(html.replace("</body>", script + "</body>", 1))
            return response

        match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/(entry|progress|thumbnails)", path)
        if match:
            project_id, source = match.groups()
            responsive_style = ""
            if source == "progress":
                responsive_style = """
<style data-progress-se-toolbar>
@media(max-width:390px) and (orientation:portrait){
  .toolbar{height:auto!important;min-height:88px!important;display:grid!important;grid-template-columns:38px minmax(66px,1fr) 38px 42px 42px 42px!important;grid-template-rows:40px 38px!important;gap:4px!important;align-items:center!important;overflow:visible!important;white-space:normal!important;padding:4px max(5px,env(safe-area-inset-right)) 4px max(5px,env(safe-area-inset-left))!important}
  .toolbar>.spacer{display:none!important}
  .toolbar>#prev{grid-column:1;grid-row:1}.toolbar>.page-field{grid-column:2;grid-row:1;min-width:0}.toolbar>#next{grid-column:3;grid-row:1}
  .toolbar>.page-favorite-view{grid-column:4;grid-row:1;min-width:42px!important}.toolbar>#rotateCompact{grid-column:5;grid-row:1;display:inline-flex!important}.toolbar>.more{grid-column:6;grid-row:1;display:block!important}
  .toolbar>#fullscreenCompact{display:none!important}
  .toolbar>button[title="ページを一覧表示"]{grid-column:1 / span 3;grid-row:2;width:100%!important;min-width:0!important;font-size:.86rem!important}
  .toolbar>a[href*="/progress-list"]{grid-column:4 / span 3;grid-row:2;width:100%!important;min-width:0!important;font-size:.86rem!important}
  .viewer{max-height:calc(100dvh - 181px)!important;min-height:calc(100dvh - 181px)!important}
  body.progress-fullscreen .viewer{max-height:none!important;min-height:0!important}
}
@media(max-width:640px) and (orientation:landscape){
  .toolbar{padding-left:max(5px,env(safe-area-inset-left))!important;padding-right:max(5px,env(safe-area-inset-right))!important;gap:3px!important}
  .toolbar>#fullscreenCompact{display:none!important}
  .toolbar .icon-button,.toolbar .nav-button{min-width:38px!important;padding-left:5px!important;padding-right:5px!important}
  .toolbar .page-field input{width:36px!important}
}
</style>
"""
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
    if(source==='progress'&&!moreMenu.querySelector('[data-go-entry]')){{
      const entry=document.createElement('button');entry.type='button';entry.className='button';entry.dataset.goEntry='1';entry.textContent='✎ 図面エントリーへ';entry.title='現在ページを図面エントリーで開く';entry.onclick=goEntry;moreMenu.appendChild(entry);
    }}
    if(source==='progress'&&!moreMenu.querySelector('[data-go-fullscreen]')){{
      const full=document.createElement('button');full.type='button';full.className='button';full.dataset.goFullscreen='1';full.textContent='⛶ 全画面';full.onclick=()=>{{document.getElementById('fullscreenCompact')?.click();document.getElementById('moreMenu')?.removeAttribute('open')}};moreMenu.appendChild(full);
    }}
    if(!moreMenu.querySelector('[data-go-favorites]')){{
      const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ お気に入り一覧';fav.title='工事横断のお気に入り一覧';fav.onclick=goFavorites;moreMenu.appendChild(fav);
    }}
  }} else {{
    const controls=document.querySelector('.controls');
    if(controls&&!controls.querySelector('[data-go-favorites]')){{
      const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ 一覧';fav.title='工事横断のお気に入り一覧';fav.onclick=goFavorites;controls.appendChild(fav);
    }} else if(!controls){{
      const top=document.querySelector('.top');
      if(top&&!top.querySelector('[data-go-favorites]')){{
        const fav=document.createElement('button');fav.type='button';fav.className='button';fav.dataset.goFavorites='1';fav.textContent='★ お気に入り';fav.title='工事横断のお気に入り一覧';
        fav.style.cssText='border-color:#f9ab00;color:#8a5a00;font-weight:800;background:#fff8e1';fav.onclick=goFavorites;top.appendChild(fav);
      }}
    }}
  }}

  if(source==='progress'){{
    const pageGridButton=document.querySelector('.toolbar>button[title="ページを一覧表示"]');
    const progressListButton=document.querySelector('.toolbar>a[href*="/progress-list"]');
    const mq=matchMedia('(max-width:390px) and (orientation:portrait)');
    const labelNarrow=()=>{{if(pageGridButton)pageGridButton.textContent=mq.matches?'▦ ページ':'▦';if(progressListButton)progressListButton.textContent=mq.matches?'☷ 進捗':'☷'}};
    labelNarrow();mq.addEventListener?.('change',labelNarrow);window.addEventListener('orientationchange',()=>setTimeout(labelNarrow,80));
  }}

  if(source==='progress'&&pageInput){{
    const storageKey=`weldFavoritePages:${{projectId}}`;
    let lastPage=0;
    const readFavorites=()=>{{try{{const raw=JSON.parse(localStorage.getItem(storageKey)||'[]');return new Set(Array.isArray(raw)?raw.map(Number).filter(Number.isFinite):[])}}catch(_e){{return new Set()}}}};
    const syncStar=()=>{{
      const star=document.querySelector('.page-favorite-view');if(!star)return;
      const p=currentPage(),favorites=readFavorites(),on=favorites.has(p);
      star.textContent=on?'★':'☆';star.classList.toggle('is-favorite',on);
      star.setAttribute('aria-label',on?`P${{p}} お気に入り解除`:`P${{p}} お気に入り登録`);star.title=on?'お気に入り解除':'お気に入り登録';lastPage=p;
    }};
    const checkPage=()=>{{const p=currentPage();if(p!==lastPage)syncStar()}};
    const timer=setInterval(checkPage,200);
    window.addEventListener('pagehide',()=>clearInterval(timer),{{once:true}});
    window.addEventListener('pageshow',syncStar);window.addEventListener('focus',syncStar);
    document.addEventListener('visibilitychange',()=>{{if(!document.hidden)syncStar()}});
    window.addEventListener('storage',e=>{{if(e.key===storageKey)syncStar()}});
    setTimeout(syncStar,0);
  }}
}})();
</script>
"""
            if responsive_style:
                html = html.replace("</head>", responsive_style + "</head>", 1)
            response.set_data(html.replace("</body>", script + "</body>", 1))
        return response

    return blueprint
