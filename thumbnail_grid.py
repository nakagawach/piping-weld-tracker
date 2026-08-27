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

    def inject_grid_rotation(html, project_id):
        if "data-thumbnail-rotation-patch" in html or "</body>" not in html:
            return html
        script = f"""
<script data-thumbnail-rotation-patch>
(() => {{
  const projectId={project_id};
  let rotation=0;
  try{{rotation=Number(localStorage.getItem(`weldDrawingRotation:${{projectId}}`)||0)}}catch(_e){{}}
  if(![0,90,180,270].includes(rotation)||rotation===0)return;
  const fit=(img)=>{{
    if(!img||!img.complete||!img.naturalWidth)return;
    const wrap=img.closest('.thumb-wrap');if(!wrap)return;
    const cw=wrap.clientWidth,ch=wrap.clientHeight;if(!cw||!ch)return;
    const base=Math.min(cw/img.naturalWidth,ch/img.naturalHeight);
    const bw=img.naturalWidth*base,bh=img.naturalHeight*base;
    let extra=1;
    if(rotation===90||rotation===270)extra=Math.min(cw/bh,ch/bw);
    img.style.width=`${{bw}}px`;img.style.height=`${{bh}}px`;img.style.objectFit='fill';
    img.style.transformOrigin='center center';img.style.transform=`rotate(${{rotation}}deg) scale(${{extra}})`;
  }};
  const applyAll=()=>document.querySelectorAll('.thumb').forEach(fit);
  document.addEventListener('load',e=>{{if(e.target?.classList?.contains('thumb'))requestAnimationFrame(()=>fit(e.target))}},true);
  document.querySelector('.columns')?.addEventListener('click',()=>requestAnimationFrame(applyAll));
  if('ResizeObserver' in window){{const ro=new ResizeObserver(applyAll);ro.observe(document.getElementById('grid'));}}
  applyAll();setTimeout(applyAll,150);setTimeout(applyAll,600);
}})();
</script>
"""
        return html.replace("</body>", script + "</body>", 1)

    def patch_progress_empty_state(html):
        if "data-progress-empty-patch" in html:
            return html
        load_start = (
            "pageInput.value=n;updateProgressThumbActive();setBusy(true);drawingZoom=1;"
            "zoomReset.textContent='100%';canvas.style.width='100%';resetPosition();"
        )
        patched_start = (
            load_start
            + "canvas.hidden=true;empty.hidden=false;empty.textContent='このページを読み込んでいます…';summary.hidden=true;"
        )
        html = html.replace(load_start, patched_start, 1)
        empty_text = (
            "empty.textContent='このページは番号配置がまだ確定保存されていません。\\n"
            "先に図面エントリーで番号配置を保存してください。';"
        )
        empty_html = (
            "empty.innerHTML='このページは番号配置がまだ確定保存されていません。<br>"
            "先に図面エントリーで番号配置を保存してください。<br>"
            "<button type=\"button\" class=\"button\" id=\"goEntryEmpty\" style=\"margin-top:12px\">図面エントリーへ</button>';"
            "const goEntryEmpty=document.getElementById('goEntryEmpty');"
            "if(goEntryEmpty)goEntryEmpty.onclick=()=>location.href=`/weld/projects/${projectId}/entry?page=${n}`;"
        )
        html = html.replace(empty_text, empty_html, 1)
        saved_else = "}else{draw();status.textContent=`${n} / ${pageCount} ページ。ピンチ・移動・回転・全画面が使えます。`}"
        saved_else_new = "}else{canvas.hidden=false;empty.hidden=true;draw();status.textContent=`${n} / ${pageCount} ページ。ピンチ・移動・回転・全画面が使えます。`}"
        html = html.replace(saved_else, saved_else_new, 1)
        marker = "<script data-progress-empty-patch>/* empty-state patch applied */</script>"
        return html.replace("</body>", marker + "</body>", 1)

    @blueprint.after_app_request
    def enhance_drawing_views(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        path = request.path
        grid_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        if grid_match:
            html = response.get_data(as_text=True)
            response.set_data(inject_grid_rotation(html, grid_match.group(1)))
            return response

        match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/(entry|progress)", path)
        if not match:
            return response
        project_id, source = match.groups()
        html = response.get_data(as_text=True)

        if source == "progress":
            html = patch_progress_empty_state(html)

        if "data-thumbnail-grid-launch" not in html and "</body>" in html:
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
            html = html.replace("</body>", script + "</body>", 1)

        response.set_data(html)
        return response

    return blueprint
