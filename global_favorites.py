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
            response.set_data(html.replace("</body>", script + "</body>", 1))
        return response

    return blueprint
