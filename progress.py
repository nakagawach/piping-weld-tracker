import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, url_for

from project_render import normalize_label


PROGRESS_STATUSES = {"未着手", "施工中", "完了"}


def create_progress_blueprint(db_path: Path):
    blueprint = Blueprint("progress", __name__)

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

        progress_list_url = url_for("progress.project_progress_list", project_id=project_id)
        list_button = (
            f'<a class="button icon-button" href="{progress_list_url}" '
            'aria-label="進捗一覧" title="進捗一覧" '
            'style="display:inline-flex;align-items:center;justify-content:center;text-decoration:none">☷</a>'
        )
        html = html.replace('<div class="spacer"></div>', f'<div class="spacer"></div>{list_button}', 1)

        thumb_css = """
.progress-thumbs{display:flex;gap:6px;overflow-x:hidden;padding:5px 6px;border-bottom:1px solid #eee;background:#fff;scrollbar-width:thin}.progress-thumbs[data-ready=\"1\"]{overflow-x:auto}
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
            "function updateProgressThumbActive(){progressThumbs.querySelectorAll('.progress-thumb').forEach(b=>{const active=Number(b.dataset.page)===Number(pageInput.value);b.classList.toggle('active',active);b.disabled=active;if(active){b.setAttribute('aria-disabled','true');b.title='現在表示中のページ'}else{b.removeAttribute('aria-disabled');b.removeAttribute('title')}});const activeThumb=progressThumbs.querySelector('.progress-thumb.active');if(activeThumb)activeThumb.scrollIntoView({block:'nearest',inline:'nearest'});}"
            "function setupProgressThumbnails(){progressThumbs.innerHTML='';progressThumbs.dataset.ready='0';const waits=[];for(let p=1;p<=pageCount;p++){const b=document.createElement('button');b.type='button';b.className='progress-thumb';b.dataset.page=String(p);b.innerHTML=`<img alt='P${p} サムネイル' loading='eager' decoding='async' src='${pdfiumPageUrl}?page=${p}&longEdge=500&format=jpeg'><span>P${p}</span>`;const img=b.querySelector('img');waits.push(new Promise(resolve=>{if(img.complete){resolve()}else{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true})}}));b.onclick=()=>loadPage(p);progressThumbs.appendChild(b);}updateProgressThumbActive();Promise.all(waits).then(()=>{progressThumbs.dataset.ready='1'});}"
        )
        html = html.replace("function setBusy(v){", thumb_js + "function setBusy(v){", 1)

        old_load_start = "pageInput.value=n;setBusy(true);drawingZoom=1;rotation=0;zoomReset.textContent='100%';rotateButton.textContent='↻ 0°';canvas.style.width='100%';resetPosition();"
        new_load_start = "pageInput.value=n;updateProgressThumbActive();setBusy(true);drawingZoom=1;zoomReset.textContent='100%';canvas.style.width='100%';resetPosition();"
        html = html.replace(old_load_start, new_load_start, 1)
        html = html.replace(
            "pageCount=data.pageCount;pageTotal.textContent=`/ ${pageCount}`;setBusy(false);await loadPage(1)",
            "pageCount=data.pageCount;pageTotal.textContent=`/ ${pageCount}`;setBusy(false);await loadPage(1);setupProgressThumbnails()",
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

    return blueprint
