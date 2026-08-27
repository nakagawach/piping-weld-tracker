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

        match = re.fullmatch(r"(?:/weld)?/projects/\d+/(entry|progress|thumbnails)", path)
        if match:
            source = match.group(1)
            script = f"""
<script data-global-favorites-launch>
(() => {{
  const go=()=>location.href='/weld/favorites';
  const source={source!r};
  const moreMenu=document.querySelector('.more-menu');
  if(moreMenu){{
    const b=document.createElement('button');b.type='button';b.className='button';b.textContent='★ お気に入り一覧';b.title='工事横断のお気に入り一覧';b.onclick=go;
    moreMenu.appendChild(b);return;
  }}
  const controls=document.querySelector('.controls');
  if(controls){{
    const b=document.createElement('button');b.type='button';b.className='button';b.textContent='★ 一覧';b.title='工事横断のお気に入り一覧';b.onclick=go;
    controls.appendChild(b);return;
  }}
  const top=document.querySelector('.top');
  if(top){{
    const b=document.createElement('button');b.type='button';b.className='button';b.textContent='★ お気に入り';b.title='工事横断のお気に入り一覧';
    b.style.cssText='border-color:#f9ab00;color:#8a5a00;font-weight:800;background:#fff8e1';b.onclick=go;top.appendChild(b);
  }}
}})();
</script>
"""
            response.set_data(html.replace("</body>", script + "</body>", 1))
        return response

    return blueprint
