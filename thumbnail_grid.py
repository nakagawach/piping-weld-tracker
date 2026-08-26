import re
import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request


def create_thumbnail_grid_blueprint(db_path: Path):
    blueprint = Blueprint("thumbnail_grid", __name__)

    @blueprint.get("/projects/<int:project_id>/thumbnails")
    def project_thumbnail_grid(project_id):
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            project = connection.execute(
                "SELECT project_name, original_pdf_name FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if project is None:
            return "工事が見つかりません。", 404
        source = "progress" if request.args.get("source") == "progress" else "entry"
        current_page = max(1, request.args.get("page", default=1, type=int) or 1)
        return render_template(
            "project_thumbnail_grid_v2.html",
            project_id=project_id,
            project_name=project["project_name"],
            pdf_name=project["original_pdf_name"],
            source=source,
            current_page=current_page,
        )

    @blueprint.after_app_request
    def add_thumbnail_grid_button(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        match = re.fullmatch(r"/weld/projects/(\d+)/(entry|progress)", request.path)
        if not match:
            return response
        project_id, source = match.groups()
        html = response.get_data(as_text=True)
        if "data-thumbnail-grid-launch" in html or "</body>" not in html:
            return response
        script = f"""
<script data-thumbnail-grid-launch>
(() => {{
  const projectId={project_id};
  const source={source!r};
  const pageInput=document.getElementById('page');
  const openGrid=()=>{{
    const page=Math.max(1,Number(pageInput?.value)||1);
    location.href=`/weld/projects/${{projectId}}/thumbnails?source=${{source}}&page=${{page}}`;
  }};
  const button=document.createElement('button');
  button.type='button';button.className='button';button.textContent='▦ ページ一覧';button.title='ページを一覧表示';button.onclick=openGrid;
  const controls=document.querySelector('.controls');
  if(controls){{controls.insertBefore(button,document.getElementById('ocr')||controls.lastChild);}}
  else {{
    const toolbar=document.querySelector('.toolbar');
    if(toolbar){{button.classList.add('icon-button');button.textContent='▦';button.setAttribute('aria-label','ページ一覧');toolbar.insertBefore(button,toolbar.querySelector('.spacer')?.nextSibling||toolbar.lastChild);}}
  }}
  if(source==='entry'){{
    const requested=Math.max(1,Number(new URLSearchParams(location.search).get('page'))||1);
    if(requested>1){{
      const move=()=>{{if(!pageInput||pageInput.disabled||!Number(pageInput.max))return false;pageInput.value=String(Math.min(requested,Number(pageInput.max)));pageInput.dispatchEvent(new Event('change',{{bubbles:true}}));return true;}};
      if(!move()){{const timer=setInterval(()=>{{if(move())clearInterval(timer);}},60);setTimeout(()=>clearInterval(timer),5000);}}
    }}
  }}
}})();
</script>
"""
        response.set_data(html.replace("</body>", script + "</body>", 1))
        return response

    return blueprint
