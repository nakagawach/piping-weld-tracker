import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, url_for

from project_render import normalize_label


PROGRESS_STATUSES = {"未着手", "施工中", "完了"}
DRAWING_MEMO_COLORS = {"#d93025", "#1967d2", "#188038", "#f9ab00", "#202124"}
DRAWING_MEMO_WIDTHS = {12, 24, 48}
MAX_MEMO_STROKES = 500
MAX_MEMO_POINTS = 50000


def normalize_drawing_memo(body):
    page_number = body.get("pageNumber")
    strokes = body.get("strokes")
    if not isinstance(page_number, int) or page_number < 1:
        raise ValueError("ページ番号が不正です。")
    if not isinstance(strokes, list):
        raise ValueError("手書きメモの形式が不正です。")
    if len(strokes) > MAX_MEMO_STROKES:
        raise ValueError("手書きメモの線が多すぎます。")

    normalized = []
    total_points = 0
    for raw in strokes:
        if not isinstance(raw, dict):
            raise ValueError("手書きメモの線データが不正です。")
        color = str(raw.get("color", "")).lower()
        if color not in DRAWING_MEMO_COLORS:
            raise ValueError("手書きメモの色が不正です。")
        try:
            width = int(raw.get("width"))
        except (TypeError, ValueError) as exc:
            raise ValueError("手書きメモの太さが不正です。") from exc
        if width not in DRAWING_MEMO_WIDTHS:
            raise ValueError("手書きメモの太さが不正です。")
        points = raw.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("手書きメモの座標が不正です。")
        total_points += len(points)
        if total_points > MAX_MEMO_POINTS:
            raise ValueError("手書きメモの点が多すぎます。")
        normalized_points = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("手書きメモの座標が不正です。")
            try:
                x = float(point[0])
                y = float(point[1])
            except (TypeError, ValueError) as exc:
                raise ValueError("手書きメモの座標が不正です。") from exc
            if not (0 <= x <= 10000 and 0 <= y <= 10000):
                raise ValueError("手書きメモの座標が範囲外です。")
            normalized_points.append([round(x, 2), round(y, 2)])
        normalized.append({"color": color, "width": width, "points": normalized_points})
    return {"pageNumber": page_number, "strokes": normalized}


def create_progress_blueprint(db_path: Path):
    blueprint = Blueprint("progress", __name__)
    memo_dir = db_path.parent / "drawing_memos"

    def memo_file(project_id, page_number):
        return memo_dir / f"project-{project_id}-page-{page_number}.json"

    def read_drawing_memo(project_id, page_number):
        path = memo_file(project_id, page_number)
        if not path.exists():
            return {"pageNumber": page_number, "strokes": [], "updatedAt": None}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("手書きメモの保存データを読み込めませんでした。") from exc
        memo = normalize_drawing_memo({
            "pageNumber": page_number,
            "strokes": data.get("strokes", []),
        })
        return {
            "pageNumber": page_number,
            "strokes": memo["strokes"],
            "updatedAt": data.get("updatedAt"),
        }

    def write_drawing_memo(project_id, memo, updated_at):
        memo_dir.mkdir(parents=True, exist_ok=True)
        path = memo_file(project_id, memo["pageNumber"])
        payload = json.dumps(
            {
                "pageNumber": memo["pageNumber"],
                "strokes": memo["strokes"],
                "updatedAt": updated_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=memo_dir,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                temp_path = Path(handle.name)
            temp_path.replace(path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def connect():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def drawing_key(project_id):
        return f"project:{project_id}"

    def get_project(connection, project_id):
        return connection.execute(
            """
            SELECT id, project_name, original_pdf_name
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()

    def normalize_progress(body):
        page_number = body.get("pageNumber")
        number_text = normalize_label(body.get("number", ""))
        status = str(body.get("status", "")).strip()
        completed_date = str(body.get("completedDate", "")).strip()
        work_detail = str(body.get("workDetail", "")).strip()

        if not isinstance(page_number, int) or page_number < 1:
            raise ValueError("ページ番号が不正です。")
        if not number_text:
            raise ValueError("対象番号が不正です。")
        if status not in PROGRESS_STATUSES:
            raise ValueError("状態が不正です。")
        if len(work_detail) > 1000:
            raise ValueError("メモ・作業内容は1000文字以内で入力してください。")
        if completed_date:
            try:
                datetime.strptime(completed_date, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("完了日の形式が不正です。") from exc

        try:
            position_x = int(round(float(body.get("x"))))
            position_y = int(round(float(body.get("y"))))
        except (TypeError, ValueError) as exc:
            raise ValueError("座標が不正です。") from exc

        return {
            "pageNumber": page_number,
            "number": number_text,
            "status": status,
            "completedDate": completed_date,
            "workDetail": work_detail,
            "x": position_x,
            "y": position_y,
        }

    @blueprint.get("/projects/<int:project_id>/progress")
    def project_progress(project_id):
        with connect() as connection:
            project = get_project(connection, project_id)
        if project is None:
            return "工事が見つかりません。", 404

        html = render_template(
            "project_progress.html",
            project_id=project_id,
            project_name=project["project_name"],
            pdf_name=project["original_pdf_name"],
        )

        memo_css = """
.drawing-memo-launch.active,.drawing-memo-edit.active{border-color:#1967d2;background:#e8f0fe;color:#174ea6}
.drawing-memo-tools{display:none;gap:6px;align-items:center;padding:6px;border-bottom:1px solid #eee;background:#fff;overflow-x:auto;white-space:nowrap}
.drawing-memo-tools.open{display:flex}.memo-color{width:34px;height:34px;min-width:34px;border:2px solid #fff;border-radius:50%;box-shadow:0 0 0 1px #bdc1c6;cursor:pointer}.memo-color.active{box-shadow:0 0 0 3px #1967d2}.memo-width.active,.memo-eraser.active{border-color:#1967d2;background:#e8f0fe;color:#174ea6}.memo-spacer{flex:1}.memo-save{border-color:#1967d2;background:#1967d2;color:#fff}.memo-dirty{color:#b06000;font-size:.78rem;font-weight:800}
#drawingMemoCanvas{position:absolute;left:0;top:0;margin:0;background:transparent;z-index:3}
.viewer.memo-mode #drawingMemoCanvas{cursor:crosshair}
body.progress-fullscreen .drawing-memo-tools.open{display:flex}
@media(max-width:640px){.drawing-memo-tools{padding:4px;gap:4px}.drawing-memo-tools .button{min-height:38px;padding:0 9px}.memo-color{width:30px;height:30px;min-width:30px}}
"""
        html = html.replace('</style>', f'{memo_css}</style>', 1)
        memo_url = url_for("progress.get_drawing_memo", project_id=project_id)
        memo_button = (
            f'<button class="button icon-button drawing-memo-launch" id="drawingMemoLaunch" '
            f'type="button" data-memo-url="{memo_url}" aria-label="手書きメモ表示切替" '
            'title="手書きメモ表示切替">👁</button>'
        )
        html = html.replace('<div class="spacer"></div>', f'<div class="spacer"></div>{memo_button}', 1)
        memo_tools = """<div class="drawing-memo-tools" id="drawingMemoTools" aria-label="手書きメモツール">
<button class="memo-color active" type="button" data-memo-color="#d93025" style="background:#d93025" aria-label="赤"></button>
<button class="memo-color" type="button" data-memo-color="#1967d2" style="background:#1967d2" aria-label="青"></button>
<button class="memo-color" type="button" data-memo-color="#188038" style="background:#188038" aria-label="緑"></button>
<button class="memo-color" type="button" data-memo-color="#f9ab00" style="background:#f9ab00" aria-label="黄"></button>
<button class="memo-color" type="button" data-memo-color="#202124" style="background:#202124" aria-label="黒"></button>
<button class="button memo-width" type="button" data-memo-width="12">細</button><button class="button memo-width active" type="button" data-memo-width="24">中</button><button class="button memo-width" type="button" data-memo-width="48">太</button>
<button class="button memo-eraser" id="memoEraser" type="button">消しゴム</button><button class="button" id="memoUndo" type="button" disabled>↶</button><button class="button" id="memoRedo" type="button" disabled>↷</button><button class="button" id="memoClear" type="button">全消去</button><span class="memo-dirty" id="memoDirty"></span><span class="memo-spacer"></span><button class="button memo-save" id="memoSave" type="button">メモ保存</button>
</div>"""
        html = html.replace(
            '<div class="statusline" id="status">図面を読み込んでいます…</div>',
            memo_tools + '<div class="statusline" id="status">図面を読み込んでいます…</div>',
            1,
        )
        memo_script_url = url_for("static", filename="progress_drawing_memo.js")
        html = html.replace('</body>', f'<script src="{memo_script_url}"></script></body>', 1)

        thumb_css = """
.progress-thumbs{display:flex;gap:6px;overflow-x:auto;padding:5px 6px;border-bottom:1px solid #eee;background:#fff;scrollbar-width:thin}
.progress-thumb{flex:0 0 74px;border:2px solid transparent;border-radius:8px;background:#fff;padding:3px;cursor:pointer}
.progress-thumb.active{border-color:#1967d2;background:#e8f0fe}
.progress-thumb:disabled{opacity:.42;cursor:default;pointer-events:none;box-shadow:none}
.progress-thumb img{display:block;width:100%;height:46px;object-fit:contain;background:#f1f3f4;border-radius:4px}
.progress-thumb span{display:block;margin-top:2px;font-size:.7rem;font-weight:800;text-align:center}
body.progress-fullscreen .progress-thumbs{display:none}
@media(max-width:640px){.progress-thumbs{height:62px;padding:3px 5px}.progress-thumb{flex-basis:66px}.progress-thumb img{height:38px}.viewer{max-height:calc(100dvh - 141px);min-height:calc(100dvh - 141px)}body.progress-fullscreen .viewer{max-height:none;min-height:0}}
"""
        html = html.replace('</style>', f'{thumb_css}</style>', 1)
        html = html.replace(
            '<div class="statusline" id="status">図面を読み込んでいます…</div><div class="summary" id="summary" hidden></div>',
            '<div class="statusline" id="status">図面を読み込んでいます…</div><div class="summary" id="summary" hidden></div><div class="progress-thumbs" id="progressThumbs" aria-label="ページサムネイル"></div>',
            1,
        )

        html = html.replace(
            "const goBack=()=>location.href=projectsScreenUrl;",
            "const progressThumbs=document.getElementById('progressThumbs');let progressThumbObserver=null;"
            "const goBack=()=>location.href=projectsScreenUrl;",
            1,
        )
        thumb_js = (
            "function ensureProgressThumbLoaded(p){const img=progressThumbs.querySelector(`.progress-thumb[data-page=\"${p}\"] img`);if(img&&img.dataset.src&&!img.src)img.src=img.dataset.src;}"
            "function updateProgressThumbActive(){progressThumbs.querySelectorAll('.progress-thumb').forEach(b=>{const active=Number(b.dataset.page)===Number(pageInput.value);b.classList.toggle('active',active);b.disabled=active;if(active){b.setAttribute('aria-disabled','true');b.title='現在表示中のページ'}else{b.removeAttribute('aria-disabled');b.removeAttribute('title')}});const n=Number(pageInput.value);ensureProgressThumbLoaded(n);if(n>1)ensureProgressThumbLoaded(n-1);if(n<pageCount)ensureProgressThumbLoaded(n+1);const activeThumb=progressThumbs.querySelector('.progress-thumb.active');if(activeThumb)activeThumb.scrollIntoView({block:'nearest',inline:'nearest'});}"
            "function setupProgressThumbnails(){progressThumbs.innerHTML='';if(progressThumbObserver)progressThumbObserver.disconnect();progressThumbObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){const img=entry.target.querySelector('img');if(img&&img.dataset.src&&!img.src)img.src=img.dataset.src;}}},{root:progressThumbs,rootMargin:'0px 100px'}):null;for(let p=1;p<=pageCount;p++){const b=document.createElement('button');b.type='button';b.className='progress-thumb';b.dataset.page=String(p);b.innerHTML=`<img alt=\"P${p} サムネイル\" data-src=\"${pdfiumPageUrl}?page=${p}&longEdge=320&format=jpeg\"><span>P${p}</span>`;b.onclick=()=>loadPage(p);progressThumbs.appendChild(b);if(progressThumbObserver)progressThumbObserver.observe(b);}if(!progressThumbObserver){ensureProgressThumbLoaded(1);if(pageCount>1)ensureProgressThumbLoaded(2);}updateProgressThumbActive();}"
        )
        html = html.replace("function setBusy(v){", thumb_js + "function setBusy(v){", 1)
        html = html.replace(
            "async function loadPage(n){if(!pageCount)return;n=Math.max(1,Math.min(pageCount,Number(n)||1));if(busy){pendingPage=n;return}pageInput.value=n;setBusy(true);",
            "async function loadPage(n){if(!pageCount)return;n=Math.max(1,Math.min(pageCount,Number(n)||1));if(busy){pendingPage=n;return}const previousPage=Number(pageInput.value)||1;if(n!==previousPage&&window.__drawingMemoBeforePageChange&&!await window.__drawingMemoBeforePageChange(previousPage,n))return;if(n!==previousPage)window.dispatchEvent(new CustomEvent('weld:progress-page-changing',{detail:{from:previousPage,to:n}}));pageInput.value=n;setBusy(true);",
            1,
        )
        html = html.replace(
            "}catch(e){status.className='statusline error';status.textContent=e.message}finally{setBusy(false);const queued=pendingPage;pendingPage=null;if(queued!==null&&queued!==n)loadPage(queued)}}",
            "}catch(e){status.className='statusline error';status.textContent=e.message}finally{setBusy(false);window.dispatchEvent(new CustomEvent('weld:progress-page-loaded',{detail:{page:n}}));const queued=pendingPage;pendingPage=null;if(queued!==null&&queued!==n)loadPage(queued)}}",
            1,
        )

        old_load_start = "pageInput.value=n;setBusy(true);drawingZoom=1;rotation=0;zoomReset.textContent='100%';rotateButton.textContent='↻ 0°';canvas.style.width='100%';resetPosition();"
        new_load_start = "pageInput.value=n;selectedTarget=null;selectionPulse=false;delete canvas.dataset.selectedTarget;updateProgressThumbActive();setBusy(true);drawingZoom=1;zoomReset.textContent='100%';canvas.style.width='100%';resetPosition();"
        html = html.replace(old_load_start, new_load_start, 1)
        html = html.replace(
            "pageCount=data.pageCount;pageTotal.textContent=`/ ${pageCount}`;setBusy(false);await loadPage(1)",
            "pageCount=data.pageCount;pageTotal.textContent=`/ ${pageCount}`;setupProgressThumbnails();setBusy(false);await loadPage(1)",
            1,
        )

        html = html.replace(
            "await loadPage(1)",
            "const params=new URLSearchParams(location.search);"
            "await loadPage(Math.max(1,Number(params.get('page'))||1));"
            "if(params.has('x')&&params.has('y')){"
            "const targetX=Number(params.get('x')),targetY=Number(params.get('y'));"
            "if(Number.isFinite(targetX)&&Number.isFinite(targetY)){"
            "const target=candidates.find(item=>{const c=center(item);return Math.abs(c.x-targetX)<2&&Math.abs(c.y-targetY)<2});"
            "if(target)openEditor(target)}}",
            1,
        )
        layout_v5_css = """
<style data-progress-fixed-workspace>
/* Production progress workspace only. Shared ui_shell remains untouched. */
html:has(body.ui3-progress){height:100%;overflow:hidden!important;overscroll-behavior:none}
body.ui3-progress{
  --pw-header:44px;--pw-toolbar:44px;--pw-summary:24px;--pw-thumbs:52px;--pw-panel:312px;
  height:100dvh!important;max-height:100dvh!important;margin:0!important;overflow:hidden!important;overscroll-behavior:none;background:#eef2f7!important
}
body.ui3-progress main{width:100%!important;max-width:none!important;height:100dvh!important;max-height:100dvh!important;margin:0!important;padding:0!important;display:grid!important;grid-template-rows:var(--pw-header) minmax(0,1fr)!important;overflow:hidden!important}
body.ui3-progress main>.top{display:flex!important;min-height:var(--pw-header)!important;height:var(--pw-header)!important;margin:0!important;padding:3px 7px!important;align-items:center!important;gap:7px!important;border-bottom:1px solid #e5e7eb!important;background:#fff!important}
body.ui3-progress main>.top>div{min-width:0;flex:1}
body.ui3-progress main>.top .title{margin:0!important;font-size:.96rem!important;line-height:1.1!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
body.ui3-progress main>.top .meta{display:none!important}
body.ui3-progress main>.top #back{order:-1!important;min-height:36px!important;height:36px!important;padding:0 8px!important;border:0!important;background:transparent!important;color:#1967d2!important}
body.ui3-progress .card{
  min-width:0!important;min-height:0!important;width:100%!important;height:100%!important;margin:0!important;padding:0!important;
  display:grid!important;grid-template-columns:minmax(0,1fr)!important;
  grid-template-rows:var(--pw-toolbar) var(--pw-summary) var(--pw-thumbs) minmax(0,1fr)!important;
  overflow:hidden!important;border:0!important;border-radius:0!important;background:#fff!important
}
body.ui3-progress .toolbar{
  position:relative!important;top:auto!important;grid-column:1!important;grid-row:1!important;
  min-width:0!important;min-height:var(--pw-toolbar)!important;height:var(--pw-toolbar)!important;
  margin:0!important;padding:3px 5px!important;display:flex!important;align-items:center!important;gap:3px!important;
  overflow-x:auto!important;overflow-y:hidden!important;white-space:nowrap!important;background:#fff!important;border-bottom:1px solid #e5e7eb!important;scrollbar-width:none
}
body.ui3-progress .toolbar::-webkit-scrollbar{display:none}
body.ui3-progress .toolbar .button{min-height:36px!important;height:36px!important}
body.ui3-progress .statusline{display:none!important}
body.ui3-progress .summary{grid-column:1!important;grid-row:2!important;min-height:var(--pw-summary)!important;height:var(--pw-summary)!important;margin:0!important;padding:2px 6px!important;gap:4px!important;overflow:hidden!important;background:#fff!important;border-bottom:1px solid #eef1f4!important}
body.ui3-progress .summary .chip{padding:2px 7px!important;font-size:.7rem!important}
body.ui3-progress .progress-thumbs{
  grid-column:1!important;grid-row:3!important;min-width:0!important;min-height:var(--pw-thumbs)!important;height:var(--pw-thumbs)!important;
  margin:0!important;padding:2px 4px!important;display:flex!important;gap:4px!important;overflow-x:auto!important;overflow-y:hidden!important;touch-action:pan-x!important;overscroll-behavior-x:contain!important;background:#fff!important;border-bottom:1px solid #e5e7eb!important
}
body.ui3-progress .progress-thumb{position:relative!important;flex:0 0 60px!important;height:48px!important;padding:2px!important;border-radius:7px!important}
body.ui3-progress .progress-thumb img{height:42px!important;border-radius:4px!important}
body.ui3-progress .progress-thumb span{position:absolute!important;left:4px!important;bottom:3px!important;margin:0!important;padding:1px 4px!important;border-radius:5px!important;background:rgba(255,255,255,.88)!important;font-size:.62rem!important;line-height:1.2!important}
body.ui3-progress .viewer{
  grid-column:1!important;grid-row:4!important;min-width:0!important;min-height:0!important;width:100%!important;height:100%!important;
  max-height:none!important;margin:0!important;overflow:auto!important;overscroll-behavior:contain!important;background:#e5e9ef!important
}
body.ui3-progress .viewer>#canvas{display:block}
body.ui3-progress .progress-list-panel{
  min-width:0!important;min-height:0!important;height:auto!important;max-height:none!important;position:static!important;inset:auto!important;
  margin:0!important;border:0!important;border-left:1px solid #dfe3e8!important;border-radius:0!important;box-shadow:none!important;overflow:hidden!important;background:#fff!important
}
body.ui3-progress.progress-list-open .progress-list-panel{display:flex!important;flex-direction:column!important}
body.ui3-progress .progress-list-records{min-height:0!important;overflow-y:auto!important;overflow-x:hidden!important;overscroll-behavior:contain!important;touch-action:pan-y!important}
body.ui3-progress .progress-list-panel .panel-head{height:42px!important;min-height:42px!important;padding:4px 7px!important}
body.ui3-progress .progress-list-panel .panel-close{min-width:36px!important;height:34px!important;min-height:34px!important}
body.ui3-progress .progress-list-panel .panel-filters{padding:6px!important}
body.ui3-progress .progress-list-panel .panel-tab{min-height:32px!important;height:32px!important;padding:0 9px!important}
body.ui3-progress .progress-list-panel .panel-search{margin-top:5px!important}
body.ui3-progress .progress-list-panel .panel-search input{height:36px!important}
body.ui3-progress .progress-list-panel .panel-search .button{min-height:36px!important;height:36px!important}
body.ui3-progress .progress-list-focus{padding-top:8px!important;padding-bottom:8px!important}
body.ui3-progress .progress-list-input{min-height:34px!important;height:34px!important}

@media(min-width:821px){
  body.ui3-progress.progress-list-open .card{grid-template-columns:minmax(0,1fr) var(--pw-panel)!important}
  body.ui3-progress.progress-list-open .toolbar,
  body.ui3-progress.progress-list-open .summary,
  body.ui3-progress.progress-list-open .progress-thumbs,
  body.ui3-progress.progress-list-open .viewer{grid-column:1!important}
  body.ui3-progress.progress-list-open .progress-list-panel{grid-column:2!important;grid-row:1 / -1!important}
  body.ui3-progress.progress-list-open .toolbar .desktop-tools{display:flex!important;align-items:center!important;gap:3px!important}
  body.ui3-progress.progress-list-open .toolbar .desktop-tools>button{display:none!important}
  body.ui3-progress.progress-list-open .toolbar .desktop-tools>#rotate,
  body.ui3-progress.progress-list-open .toolbar .desktop-tools>#fullscreen{display:inline-flex!important}
}
@media(min-width:1201px){
  body.ui3-progress{--pw-panel:340px}
}
@media(max-width:820px){
  body.ui3-progress{--pw-header:44px;--pw-toolbar:44px;--pw-summary:24px;--pw-thumbs:52px}
  body.ui3-progress .ui3-appbar{
    position:relative!important;top:auto!important;z-index:120!important;min-height:var(--pw-header)!important;height:var(--pw-header)!important;
    padding:2px max(5px,env(safe-area-inset-right)) 2px max(5px,env(safe-area-inset-left))!important
  }
  body.ui3-progress .ui3-back,body.ui3-progress .ui3-icon{min-width:40px!important;width:auto!important;height:40px!important;min-height:40px!important}
  body.ui3-progress .ui3-title strong{font-size:.92rem!important}
  body.ui3-progress .ui3-title small{display:none!important}
  body.ui3-progress .ui3-appbar details.more>summary{width:40px!important;height:40px!important;min-width:40px!important;min-height:40px!important}
  body.ui3-progress main{height:calc(100dvh - var(--pw-header))!important;max-height:calc(100dvh - var(--pw-header))!important;grid-template-rows:minmax(0,1fr)!important}
  body.ui3-progress main>.top{display:none!important}
  body.ui3-progress .toolbar{grid-row:1!important}
  body.ui3-progress .summary{grid-row:2!important}
  body.ui3-progress .progress-thumbs{grid-row:3!important}
  body.ui3-progress .viewer{grid-row:4!important}
  body.ui3-progress .progress-thumb{flex-basis:58px!important}
  body.ui3-progress.progress-list-open .card{
    grid-template-columns:minmax(0,1fr)!important;
    grid-template-rows:var(--pw-toolbar) var(--pw-summary) var(--pw-thumbs) minmax(0,3fr) minmax(230px,2fr)!important
  }
  body.ui3-progress.progress-list-open .progress-list-panel{grid-column:1!important;grid-row:5!important;border-left:0!important;border-top:1px solid #dfe3e8!important}
  body.ui3-progress.progress-list-open .viewer{grid-row:4!important}
}
@media(min-width:821px) and (max-width:1200px) and (orientation:portrait){
  body.ui3-progress .ui3-appbar{display:flex!important;position:relative!important;min-height:44px!important;height:44px!important;padding:2px 6px!important;background:#fff!important;border-bottom:1px solid #e5e7eb!important}
  body.ui3-progress main{height:calc(100dvh - 44px)!important;max-height:calc(100dvh - 44px)!important;grid-template-rows:minmax(0,1fr)!important}
  body.ui3-progress main>.top{display:none!important}
  body.ui3-progress .card{grid-template-columns:minmax(0,1fr)!important}
  body.ui3-progress.progress-list-open .card{grid-template-rows:var(--pw-toolbar) var(--pw-summary) var(--pw-thumbs) minmax(0,3fr) minmax(230px,2fr)!important}
  body.ui3-progress.progress-list-open .progress-list-panel{grid-column:1!important;grid-row:5!important;border-left:0!important;border-top:1px solid #dfe3e8!important}
}
body.ui3-progress.progress-fullscreen{overflow:hidden!important}
body.ui3-progress.progress-fullscreen main{height:100dvh!important;max-height:100dvh!important}
body.ui3-progress .progress-minimap{position:absolute;left:10px;bottom:10px;width:118px;height:84px;border:1px solid rgba(15,23,42,.35);border-radius:7px;background:rgba(255,255,255,.9);box-shadow:0 2px 10px rgba(15,23,42,.16);overflow:hidden;pointer-events:none;opacity:0;transition:opacity .12s;z-index:12}
body.ui3-progress .progress-minimap.show{opacity:1}
body.ui3-progress .progress-minimap>canvas{position:absolute;inset:0;width:100%;height:100%;margin:0!important}
body.ui3-progress .progress-minimap-viewport{position:absolute;border:2px solid #ff4fa3;background:rgba(255,79,163,.22);border-radius:2px}
</style>
"""
        html = html.replace("</body>", layout_v5_css + "</body>", 1)

        return html

    @blueprint.get("/projects/<int:project_id>/progress-list")
    def project_progress_list(project_id):
        with connect() as connection:
            project = get_project(connection, project_id)
        if project is None:
            return "工事が見つかりません。", 404

        return render_template(
            "project_progress_list.html",
            project_id=project_id,
            project_name=project["project_name"],
            pdf_name=project["original_pdf_name"],
        )

    @blueprint.get("/projects/<int:project_id>/progress-list-data")
    def get_project_progress_list(project_id):
        key = drawing_key(project_id)
        with connect() as connection:
            if get_project(connection, project_id) is None:
                return jsonify({"error": "工事が見つかりません。"}), 404

            rows = connection.execute(
                """
                SELECT
                    nm.page_number,
                    nm.item_order,
                    nm.number_text,
                    nm.x,
                    nm.y,
                    nm.width,
                    nm.height,
                    COALESCE(wp.status, '未着手') AS status,
                    COALESCE(wp.completed_date, '') AS completed_date,
                    COALESCE(wp.work_detail, '') AS work_detail,
                    wp.updated_at
                FROM number_map AS nm
                LEFT JOIN weld_progress AS wp
                  ON wp.drawing_key = nm.drawing_key
                 AND wp.page_number = nm.page_number
                 AND ABS(wp.position_x - (nm.x + nm.width / 2.0)) < 2
                 AND ABS(wp.position_y - (nm.y + nm.height / 2.0)) < 2
                WHERE nm.drawing_key = ?
                ORDER BY nm.page_number, nm.item_order
                """,
                (key,),
            ).fetchall()

        items = []
        counts = {"total": 0, "untouched": 0, "working": 0, "done": 0}
        for row in rows:
            status = row["status"]
            if status not in PROGRESS_STATUSES:
                status = "未着手"
            counts["total"] += 1
            if status == "完了":
                counts["done"] += 1
            elif status == "施工中":
                counts["working"] += 1
            else:
                counts["untouched"] += 1

            items.append({
                "pageNumber": row["page_number"],
                "order": row["item_order"],
                "number": row["number_text"],
                "status": status,
                "completedDate": row["completed_date"],
                "workDetail": row["work_detail"],
                "updatedAt": row["updated_at"],
                "x": round(row["x"] + row["width"] / 2.0),
                "y": round(row["y"] + row["height"] / 2.0),
            })

        return jsonify({
            "drawingKey": key,
            "counts": counts,
            "completionRate": round((counts["done"] / counts["total"] * 100), 1) if counts["total"] else 0,
            "items": items,
        })

    @blueprint.get("/projects/<int:project_id>/progress-data")
    def get_project_progress(project_id):
        page_number = request.args.get("page", type=int)
        if page_number is None or page_number < 1:
            return jsonify({"error": "ページ番号が不正です。"}), 400

        key = drawing_key(project_id)
        with connect() as connection:
            if get_project(connection, project_id) is None:
                return jsonify({"error": "工事が見つかりません。"}), 404

            number_rows = connection.execute(
                """
                SELECT number_text, source, x, y, width, height, saved_at
                FROM number_map
                WHERE drawing_key = ? AND page_number = ?
                ORDER BY item_order
                """,
                (key, page_number),
            ).fetchall()
            progress_rows = connection.execute(
                """
                SELECT position_x, position_y, number_text, status,
                       completed_date, work_detail, updated_at
                FROM weld_progress
                WHERE drawing_key = ? AND page_number = ?
                ORDER BY id
                """,
                (key, page_number),
            ).fetchall()

        return jsonify({
            "drawingKey": key,
            "pageNumber": page_number,
            "saved": bool(number_rows),
            "savedAt": number_rows[0]["saved_at"] if number_rows else None,
            "candidates": [
                {
                    "number": row["number_text"],
                    "source": row["source"],
                    "bbox": {
                        "x": row["x"],
                        "y": row["y"],
                        "w": row["width"],
                        "h": row["height"],
                    },
                }
                for row in number_rows
            ],
            "items": [
                {
                    "x": row["position_x"],
                    "y": row["position_y"],
                    "number": row["number_text"],
                    "status": row["status"],
                    "completedDate": row["completed_date"],
                    "workDetail": row["work_detail"],
                    "updatedAt": row["updated_at"],
                }
                for row in progress_rows
            ],
        })

    @blueprint.post("/projects/<int:project_id>/progress-data")
    def save_project_progress(project_id):
        body = request.get_json(silent=True) or {}
        try:
            item = normalize_progress(body)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        key = drawing_key(project_id)
        updated_at = datetime.now(timezone.utc).isoformat()

        with connect() as connection:
            if get_project(connection, project_id) is None:
                return jsonify({"error": "工事が見つかりません。"}), 404

            number_exists = connection.execute(
                """
                SELECT 1
                FROM number_map
                WHERE drawing_key = ? AND page_number = ?
                  AND ABS((x + width / 2.0) - ?) < 2
                  AND ABS((y + height / 2.0) - ?) < 2
                LIMIT 1
                """,
                (key, item["pageNumber"], item["x"], item["y"]),
            ).fetchone()
            if number_exists is None:
                return jsonify({"error": "保存済み番号配置と一致しません。ページを再読み込みしてください。"}), 409

            connection.execute(
                """
                INSERT INTO weld_progress (
                    drawing_key, page_number, position_x, position_y, number_text,
                    status, completed_date, work_detail, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(drawing_key, page_number, position_x, position_y)
                DO UPDATE SET
                    number_text = excluded.number_text,
                    status = excluded.status,
                    completed_date = excluded.completed_date,
                    work_detail = excluded.work_detail,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    item["pageNumber"], item["x"], item["y"], item["number"],
                    item["status"], item["completedDate"], item["workDetail"], updated_at,
                ),
            )

        return jsonify({**item, "updatedAt": updated_at})

    @blueprint.get("/projects/<int:project_id>/drawing-memo")
    def get_drawing_memo(project_id):
        page_number = request.args.get("page", type=int)
        if page_number is None or page_number < 1:
            return jsonify({"error": "ページ番号が不正です。"}), 400
        with connect() as connection:
            if get_project(connection, project_id) is None:
                return jsonify({"error": "工事が見つかりません。"}), 404
        try:
            memo = read_drawing_memo(project_id, page_number)
        except (RuntimeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify({"drawingKey": drawing_key(project_id), **memo})

    @blueprint.post("/projects/<int:project_id>/drawing-memo")
    def save_drawing_memo(project_id):
        body = request.get_json(silent=True) or {}
        try:
            memo = normalize_drawing_memo(body)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        with connect() as connection:
            if get_project(connection, project_id) is None:
                return jsonify({"error": "工事が見つかりません。"}), 404
        updated_at = datetime.now(timezone.utc).isoformat()
        try:
            write_drawing_memo(project_id, memo, updated_at)
        except OSError:
            return jsonify({"error": "手書きメモを保存できませんでした。"}), 500
        return jsonify({
            "drawingKey": drawing_key(project_id),
            "pageNumber": memo["pageNumber"],
            "count": len(memo["strokes"]),
            "updatedAt": updated_at,
        })


    return blueprint
