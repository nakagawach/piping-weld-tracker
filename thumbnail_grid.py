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

    def inject_grid_favorites(html, project_id):
        if "data-page-favorites-grid" in html or "</body>" not in html:
            return html
        style = """
<style data-page-favorites-grid-style>
.page-card{position:relative}.page-favorite-star{position:absolute;top:8px;right:8px;z-index:4;width:34px;height:34px;display:flex;align-items:center;justify-content:center;border:1px solid #dadce0;border-radius:50%;background:rgba(255,255,255,.94);color:#5f6368;font-size:1.35rem;line-height:1;box-shadow:0 1px 3px #0002;cursor:pointer}.page-favorite-star.is-favorite{color:#f9ab00;background:#fff8e1;border-color:#f9ab00}.page-favorite-star:focus-visible{outline:3px solid #aecbfa;outline-offset:2px}@media(max-width:640px){.page-favorite-star{top:6px;right:6px;width:32px;height:32px;font-size:1.25rem}}
</style>
"""
        script = f"""
<script data-page-favorites-grid>
(() => {{
  const projectId={project_id};
  const storageKey=`weldFavoritePages:${{projectId}}`;
  const read=()=>{{try{{const v=JSON.parse(localStorage.getItem(storageKey)||'[]');return new Set(Array.isArray(v)?v.map(Number).filter(Number.isFinite):[])}}catch(_e){{return new Set()}}}};
  let favorites=read();
  const save=()=>{{try{{localStorage.setItem(storageKey,JSON.stringify([...favorites].sort((a,b)=>a-b)))}}catch(_e){{}}}};
  const paint=(star,p)=>{{const on=favorites.has(p);star.textContent=on?'★':'☆';star.classList.toggle('is-favorite',on);star.setAttribute('aria-label',on?`P${{p}} お気に入り解除`:`P${{p}} お気に入り登録`);star.title=on?'お気に入り解除':'お気に入り登録'}};
  const enhance=()=>{{document.querySelectorAll('.page-card[data-page]').forEach(card=>{{if(card.querySelector('.page-favorite-star'))return;const p=Number(card.dataset.page);if(!Number.isFinite(p))return;const star=document.createElement('span');star.className='page-favorite-star';star.setAttribute('role','button');star.tabIndex=0;paint(star,p);const toggle=e=>{{e.preventDefault();e.stopPropagation();favorites.has(p)?favorites.delete(p):favorites.add(p);save();paint(star,p)}};star.addEventListener('click',toggle);star.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' ')toggle(e)}});card.appendChild(star)}})}};
  new MutationObserver(enhance).observe(document.getElementById('grid'),{{childList:true,subtree:true}});enhance();
  window.addEventListener('storage',e=>{{if(e.key===storageKey){{favorites=read();document.querySelectorAll('.page-favorite-star').forEach(star=>{{const p=Number(star.closest('.page-card')?.dataset.page);if(Number.isFinite(p))paint(star,p)}})}}}});
}})();
</script>
"""
        return html.replace("</head>", style + "</head>", 1).replace("</body>", script + "</body>", 1)

    def inject_view_favorite(html, project_id, source):
        if "data-page-favorite-view" in html or "</body>" not in html:
            return html
        style = """
<style data-page-favorite-view-style>
.page-favorite-view{min-width:42px!important;padding:0 8px!important;font-size:1.45rem!important;line-height:1!important;color:#5f6368!important}.page-favorite-view.is-favorite{color:#f9ab00!important;background:#fff8e1!important;border-color:#f9ab00!important}
</style>
"""
        script = f"""
<script data-page-favorite-view>
(() => {{
  const projectId={project_id};
  const source={source!r};
  const storageKey=`weldFavoritePages:${{projectId}}`;
  const pageInput=document.getElementById('page');
  if(!pageInput)return;
  const read=()=>{{try{{const v=JSON.parse(localStorage.getItem(storageKey)||'[]');return new Set(Array.isArray(v)?v.map(Number).filter(Number.isFinite):[])}}catch(_e){{return new Set()}}}};
  let favorites=read();
  const save=()=>{{try{{localStorage.setItem(storageKey,JSON.stringify([...favorites].sort((a,b)=>a-b)))}}catch(_e){{}}}};
  const star=document.createElement('button');star.type='button';star.className='button page-favorite-view';star.setAttribute('aria-label','お気に入り登録');
  const current=()=>Math.max(1,Number(pageInput.value)||1);
  const paint=()=>{{const p=current(),on=favorites.has(p);star.textContent=on?'★':'☆';star.classList.toggle('is-favorite',on);star.setAttribute('aria-label',on?`P${{p}} お気に入り解除`:`P${{p}} お気に入り登録`);star.title=on?'お気に入り解除':'お気に入り登録'}};
  star.onclick=e=>{{e.preventDefault();e.stopPropagation();const p=current();favorites.has(p)?favorites.delete(p):favorites.add(p);save();paint()}};
  const controls=document.querySelector('.controls');const toolbar=document.querySelector('.toolbar');
  if(controls){{star.classList.add('icon-button');controls.insertBefore(star,document.getElementById('ocr')||controls.lastChild)}}else if(toolbar){{star.classList.add('icon-button');const anchor=toolbar.querySelector('#thumbnailGridButton, .spacer');toolbar.insertBefore(star,anchor?.nextSibling||toolbar.lastChild)}}
  const deferPaint=()=>{{setTimeout(paint,0);setTimeout(paint,120)}};
  pageInput.addEventListener('change',deferPaint);
  document.addEventListener('click',e=>{{if(e.target.closest('#prev,#next,.progress-thumb,[data-page]'))deferPaint()}},true);
  window.addEventListener('storage',e=>{{if(e.key===storageKey){{favorites=read();paint()}}}});paint();
}})();
</script>
"""
        return html.replace("</head>", style + "</head>", 1).replace("</body>", script + "</body>", 1)

    def patch_progress_empty_state(html):
        if "data-progress-empty-patch" in html:
            return html
        load_start = (
            "pageInput.value=n;updateProgressThumbActive();setBusy(true);drawingZoom=1;"
            "zoomReset.textContent='100%';canvas.style.width='100%';resetPosition();"
        )
        patched_start = (
            load_start
            + "canvas.hidden=true;canvas.style.display='none';empty.hidden=false;empty.style.display='block';empty.textContent='このページを読み込んでいます…';summary.hidden=true;"
        )
        html = html.replace(load_start, patched_start, 1)
        empty_text = (
            "empty.textContent='このページは番号配置がまだ確定保存されていません。\\n"
            "先に図面エントリーで番号配置を保存してください。';"
        )
        empty_html = (
            "canvas.hidden=true;canvas.style.display='none';empty.hidden=false;empty.style.display='block';"
            "empty.innerHTML='このページは番号配置がまだ確定保存されていません。<br>"
            "先に図面エントリーで番号配置を保存してください。<br>"
            "<button type=\"button\" class=\"button\" id=\"goEntryEmpty\" style=\"margin-top:12px\">図面エントリーへ</button>';"
            "const goEntryEmpty=document.getElementById('goEntryEmpty');"
            "if(goEntryEmpty)goEntryEmpty.onclick=()=>location.href=`/weld/projects/${projectId}/entry?page=${n}`;"
        )
        html = html.replace(empty_text, empty_html, 1)
        saved_else = "}else{draw();status.textContent=`${n} / ${pageCount} ページ。ピンチ・移動・回転・全画面が使えます。`}"
        saved_else_new = "}else{canvas.hidden=false;canvas.style.display='block';empty.hidden=true;empty.style.display='none';draw();status.textContent=`${n} / ${pageCount} ページ。ピンチ・移動・回転・全画面が使えます。`}"
        html = html.replace(saved_else, saved_else_new, 1)
        runtime = """
<script data-progress-empty-patch>
(() => {
  const canvas=document.getElementById('canvas'),empty=document.getElementById('empty'),summary=document.getElementById('summary');
  if(!canvas||!empty)return;
  const hideOld=()=>{canvas.hidden=true;canvas.style.display='none';empty.hidden=false;empty.style.display='block';if(summary)summary.hidden=true};
  const navSelector='#prev,#next,.progress-thumb';
  document.addEventListener('pointerdown',e=>{if(e.target.closest(navSelector))hideOld()},true);
  document.getElementById('page')?.addEventListener('change',hideOld,true);
  new MutationObserver(()=>{if(!empty.hidden){canvas.hidden=true;canvas.style.display='none'}}).observe(empty,{attributes:true,attributeFilter:['hidden'],childList:true,subtree:true});
})();
</script>
"""
        return html.replace("</body>", runtime + "</body>", 1)

    @blueprint.after_app_request
    def enhance_drawing_views(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        path = request.path
        grid_match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        if grid_match:
            project_id = grid_match.group(1)
            html = response.get_data(as_text=True)
            html = inject_grid_rotation(html, project_id)
            html = inject_grid_favorites(html, project_id)
            response.set_data(html)
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
  button.type='button';button.id='thumbnailGridButton';button.className='button';button.textContent='▦ ページ一覧';button.title='ページを一覧表示';button.onclick=openGrid;
  const controls=document.querySelector('.controls');
  if(controls){{controls.insertBefore(button,document.getElementById('ocr')||controls.lastChild);}}
  else {{
    const toolbar=document.querySelector('.toolbar');
    if(toolbar){{
      button.classList.add('icon-button');button.textContent='▦';button.setAttribute('aria-label','ページ一覧');
      const actionBar=toolbar.querySelector('.ui2-drawing');
      if(actionBar)actionBar.appendChild(button);else toolbar.insertBefore(button,toolbar.querySelector('.spacer')?.nextSibling||toolbar.lastChild);
    }}
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

        html = inject_view_favorite(html, project_id, source)
        response.set_data(html)
        return response

    return blueprint
