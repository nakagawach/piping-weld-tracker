import re

from flask import Blueprint, request


def create_ui_shell_blueprint():
    blueprint = Blueprint("ui_shell", __name__)

    @blueprint.after_app_request
    def apply_ui_shell(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-weld-ui-shell-v3" in html:
            return response

        path = request.path
        progress = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", path)
        entry = re.fullmatch(r"(?:/weld)?/projects/(\d+)/entry", path)
        thumbs = re.fullmatch(r"(?:/weld)?/projects/(\d+)/thumbnails", path)
        progress_list = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress-list", path)
        favorites = re.fullmatch(r"(?:/weld)?/favorites", path)
        projects = re.fullmatch(r"(?:/weld)?/projects-screen", path)

        if not any((progress, entry, thumbs, progress_list, favorites, projects)):
            return response

        # Dedicated viewer mode is intentionally excluded from shared navigation styling.
        if progress and request.args.get("viewer") == "1":
            return response

        prefix = request.script_root.rstrip("/")

        css = r"""
<style data-weld-ui-shell-v3>
:root{--ui3-bg:#f5f6f8;--ui3-bar:#fff;--ui3-line:#e5e7eb;--ui3-text:#202124;--ui3-muted:#6b7280;--ui3-blue:#1967d2;--ui3-touch:48px;--ui3-header:56px;--ui3-toolbar:52px}
.ui3-appbar{display:none}
body.ui3-progress .ui3-pages{display:flex;flex-direction:row;align-items:center;gap:6px;flex:0 0 auto}
body.ui3-progress .ui3-pages .page-field{display:flex;flex-direction:row;align-items:center;gap:4px;flex:0 0 auto}
body.ui3-progress button:disabled{cursor:not-allowed!important}
body.ui3-grid .page-card:disabled{cursor:not-allowed!important;opacity:.62!important}
@media(max-width:820px){
  body{overscroll-behavior-y:none}
  .ui3-appbar{display:flex;position:sticky;top:0;z-index:120;min-height:var(--ui3-header);align-items:center;gap:4px;padding:4px max(6px,env(safe-area-inset-right)) 4px max(6px,env(safe-area-inset-left));background:rgba(255,255,255,.98);border-bottom:1px solid var(--ui3-line);backdrop-filter:saturate(180%) blur(12px)}
  .ui3-back,.ui3-icon{min-width:var(--ui3-touch);height:var(--ui3-touch);padding:0 8px;border:0;border-radius:12px;background:transparent;color:var(--ui3-blue);display:inline-flex;align-items:center;justify-content:center;text-decoration:none;font:inherit;font-weight:800;touch-action:manipulation;cursor:pointer;white-space:nowrap}
  .ui3-back{font-size:.86rem;gap:2px}.ui3-back::before{content:'‹';font-size:1.9rem;font-weight:500;line-height:1}.ui3-icon{width:var(--ui3-touch);padding:0;color:var(--ui3-text);font-size:1.2rem}.ui3-back:active,.ui3-icon:active{background:#f1f3f4}
  .ui3-title{min-width:0;flex:1;padding:0 3px}.ui3-title strong{display:block;font-size:.98rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ui3-title small{display:block;margin-top:1px;color:var(--ui3-muted);font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ui3-appbar details.more,.ui3-entry-more{display:block!important;position:relative!important;flex:0 0 auto!important}.ui3-appbar details.more>summary,.ui3-entry-more>summary{list-style:none;width:48px!important;height:48px!important;min-width:48px!important;min-height:48px!important;padding:0!important;border:0!important;border-radius:12px!important;background:transparent!important;display:flex!important;align-items:center!important;justify-content:center!important;font-size:1.25rem!important}.ui3-appbar details.more>summary::-webkit-details-marker,.ui3-entry-more>summary::-webkit-details-marker{display:none}.ui3-appbar .more-menu,.ui3-entry-more .more-menu{right:0!important;top:50px!important;width:min(260px,calc(100vw - 16px))!important;z-index:180!important;border-radius:13px!important;padding:6px!important;box-shadow:0 10px 32px #0003!important}.ui3-appbar .more-menu .button,.ui3-entry-more .more-menu .button{display:block!important;width:100%!important;min-height:46px!important;margin:1px 0!important;padding:0 12px!important;border:0!important;border-radius:9px!important;background:#fff!important;text-align:left!important;font-size:.95rem!important}

  body.ui3-progress main,body.ui3-entry main{padding:0!important;max-width:none!important}body.ui3-progress main>.top,body.ui3-entry main>.top{display:none!important}body.ui3-progress .card,body.ui3-entry .card{border-left:0!important;border-right:0!important;border-radius:0!important}
  body.ui3-progress .toolbar{position:sticky!important;top:var(--ui3-header)!important;z-index:90!important;display:flex!important;flex-wrap:nowrap!important;align-items:center!important;gap:3px!important;min-height:var(--ui3-toolbar)!important;height:var(--ui3-toolbar)!important;padding:4px max(5px,env(safe-area-inset-right))!important;background:#fff!important;border-bottom:1px solid var(--ui3-line)!important;white-space:nowrap!important;overflow-x:auto!important;scrollbar-width:none}body.ui3-progress .toolbar::-webkit-scrollbar{display:none}
  body.ui3-progress .toolbar>.spacer,body.ui3-progress .toolbar>.desktop-tools,body.ui3-progress .toolbar>.compact-fullscreen,body.ui3-progress .toolbar>.more{display:none!important}.ui3-pages,.ui3-drawing{display:flex;align-items:center;gap:2px;flex:0 0 auto}.ui3-drawing{margin-left:auto}.ui3-pages .nav-button{width:44px!important;min-width:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important;font-size:1.4rem!important}.ui3-pages .page-field{gap:2px!important}.ui3-pages .page-field>span:first-child{display:none!important}.ui3-pages .page-field input{width:42px!important;min-height:40px!important;padding:0 3px!important;border:0!important;border-radius:10px!important;background:#f3f4f6!important;font-weight:800!important}.ui3-pages .page-total{font-size:.75rem!important;color:var(--ui3-muted)!important}
  .ui3-drawing>.button,.ui3-drawing>a.button{display:inline-flex!important;align-items:center!important;justify-content:center!important;width:44px!important;min-width:44px!important;min-height:44px!important;padding:0!important;border:0!important;border-radius:10px!important;background:transparent!important;text-decoration:none!important;font-size:1.15rem!important}.ui3-drawing>.page-favorite-view{font-size:1.4rem!important}
  body.ui3-progress .statusline{display:none!important}

  body.ui3-entry .controls{position:sticky!important;top:var(--ui3-header)!important;z-index:90!important;margin:0!important;padding:4px max(5px,env(safe-area-inset-right))!important;background:#fff!important;border-bottom:1px solid var(--ui3-line)!important;display:flex!important;align-items:center!important;gap:3px!important;flex-wrap:nowrap!important;overflow-x:auto!important;scrollbar-width:none}body.ui3-entry .controls::-webkit-scrollbar{display:none}body.ui3-entry .controls label{display:flex!important;align-items:center!important;gap:2px!important;font-size:0!important;flex:0 0 auto}body.ui3-entry .controls label::before{content:'P';font-size:.78rem;font-weight:800;color:var(--ui3-muted)}body.ui3-entry #page{width:42px!important;min-height:40px!important;border:0!important;border-radius:10px!important;background:#f3f4f6!important;padding:0 3px!important;text-align:center!important;font-weight:800!important}
  body.ui3-entry #prev,body.ui3-entry #next,body.ui3-entry #rotate,body.ui3-entry .page-favorite-view,body.ui3-entry [data-thumbnail-grid-launch]{width:44px!important;min-width:44px!important;min-height:44px!important;padding:0!important;border:0!important;background:transparent!important;border-radius:10px!important;flex:0 0 auto!important}body.ui3-entry #prev,body.ui3-entry #next,body.ui3-entry #rotate,body.ui3-entry [data-thumbnail-grid-launch]{font-size:0!important}body.ui3-entry #prev::before{content:'‹';font-size:1.4rem}body.ui3-entry #next::before{content:'›';font-size:1.4rem}body.ui3-entry #rotate::before{content:'↻';font-size:1.15rem}body.ui3-entry [data-thumbnail-grid-launch]::before{content:'▦';font-size:1.15rem}body.ui3-entry #ocr{margin-left:auto!important}body.ui3-entry #ocr,body.ui3-entry #save{min-height:42px!important;padding:0 9px!important;flex:0 0 auto!important;font-weight:800!important}body.ui3-entry #pageState{display:none!important}

  body.ui3-grid main,body.ui3-favorites main,body.ui3-list main{padding-top:0!important}body.ui3-grid .top,body.ui3-favorites .top,body.ui3-list .topbar{display:none!important}body.ui3-grid .toolbar,body.ui3-favorites .toolbar{position:sticky!important;top:var(--ui3-header)!important;z-index:90!important;margin:0 0 9px!important;border:0!important;border-bottom:1px solid var(--ui3-line)!important;border-radius:0!important;background:#fff!important;padding:6px max(8px,env(safe-area-inset-right))!important;box-shadow:0 1px 2px #0000000d!important}body.ui3-favorites .toolbar{flex-wrap:wrap!important}body.ui3-list .filters{top:var(--ui3-header)!important}

  body.ui3-projects main{padding-top:0!important}.ui3-root{position:sticky;top:0;z-index:120;margin:0 -16px 16px!important;padding:6px max(10px,env(safe-area-inset-right))!important;min-height:62px;display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px!important;background:#fff!important;border-bottom:1px solid var(--ui3-line)!important}.ui3-root>div:first-child{min-width:0;flex:1}.ui3-root h1{font-size:1.15rem!important}.ui3-root-actions{display:flex!important;gap:4px!important;flex-wrap:nowrap!important}.ui3-root-actions button{width:48px!important;min-width:48px!important;height:48px!important;min-height:48px!important;padding:0!important;border-radius:12px!important;font-size:0!important}.ui3-root-actions [data-ui3-favorites]::before{content:'★';font-size:1.3rem;color:#f9ab00}.ui3-root-actions #new-project::before{content:'＋';font-size:1.5rem;color:#fff}.ui3-root-actions #new-project{background:var(--ui3-blue)!important;border-color:var(--ui3-blue)!important}
}
@media(max-width:370px){.ui3-back span{display:none}.ui3-back{width:48px;padding:0}.ui3-title small{display:none}}
</style>
"""

        if progress:
            project_id = progress.group(1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{
  const projectId={project_id};
  document.body.classList.add('ui3-progress');
  const toolbar=document.querySelector('.toolbar'),top=document.querySelector('.top'),back=document.getElementById('back'),prev=document.getElementById('prev'),next=document.getElementById('next'),pageField=toolbar?.querySelector('.page-field'),more=document.getElementById('moreMenu'),full=document.getElementById('fullscreenCompact');
  if(!toolbar||!top||!back||!prev||!next||!pageField)return;
  const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='progress';
  const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects-screen';b.setAttribute('aria-label','工事一覧へ');b.innerHTML='<span>工事一覧</span>';
  const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong></strong><small>進捗入力</small>';title.querySelector('strong').textContent=(top.querySelector('.meta')?.textContent||'').split('/')[0].trim()||'進捗入力';
  app.append(b,title);
  if(full){{full.className='ui3-icon';full.textContent='⛶';full.setAttribute('aria-label','全画面');app.append(full)}}
  if(more){{document.getElementById('backCompact')?.remove();app.append(more)}}
  toolbar.parentNode.insertBefore(app,toolbar);
  const pages=document.createElement('div');pages.className='ui3-pages';pages.append(prev,pageField,next);toolbar.prepend(pages);
  const actions=document.createElement('div');actions.className='ui3-drawing';toolbar.append(actions);
  const move=()=>{{for(const el of [document.querySelector('.page-favorite-view'),document.getElementById('rotateCompact'),toolbar.querySelector('[aria-label="ページ一覧"]'),toolbar.querySelector('[aria-label="進捗一覧"]')])if(el&&el.parentNode!==actions)actions.append(el)}};
  const obs=new MutationObserver(move);obs.observe(toolbar,{{childList:true,subtree:true}});move();setTimeout(move,120);setTimeout(move,450);
  document.addEventListener('pointerdown',e=>{{if(more?.open&&!more.contains(e.target))more.removeAttribute('open')}},true);
}})();
</script>
"""
        elif entry:
            project_id = entry.group(1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{
  document.body.classList.add('ui3-entry');
  const top=document.querySelector('.top'),controls=document.querySelector('.controls'),back=document.getElementById('back');if(!top||!controls||!back)return;
  const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='entry';
  const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects-screen';b.setAttribute('aria-label','工事一覧へ');b.innerHTML='<span>工事一覧</span>';
  const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong></strong><small>図面エントリー</small>';title.querySelector('strong').textContent=(top.querySelector('.meta')?.textContent||'').split('/')[0].trim()||'図面エントリー';
  const more=document.createElement('details');more.className='more ui3-entry-more';more.innerHTML='<summary aria-label="その他の操作">⋯</summary><div class="more-menu"></div>';const menu=more.querySelector('.more-menu');app.append(b,title,more);controls.parentNode.insertBefore(app,controls);
  const collect=()=>{{for(const id of ['reset','bulkDelete']){{const el=document.getElementById(id);if(el&&el.parentNode!==menu){{el.classList.add('button');menu.append(el)}}}}const fav=document.querySelector('[data-go-favorites]');if(fav&&fav.parentNode!==menu){{fav.textContent='★ お気に入りページ一覧';fav.classList.add('button');menu.append(fav)}}}};
  new MutationObserver(collect).observe(document.body,{{childList:true,subtree:true}});collect();setTimeout(collect,120);setTimeout(collect,450);
  document.addEventListener('pointerdown',e=>{{if(more.open&&!more.contains(e.target))more.removeAttribute('open')}},true);
}})();
</script>
"""
        elif thumbs:
            project_id = thumbs.group(1)
            source = "progress" if request.args.get("source") == "progress" else "entry"
            page = max(1, request.args.get("page", default=1, type=int) or 1)
            parent_label = "進捗" if source == "progress" else "エントリー"
            parent_path = "progress" if source == "progress" else "entry"
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-grid');const top=document.querySelector('.top');if(!top)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='thumbnails';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects/{project_id}/{parent_path}?page={page}';b.setAttribute('aria-label','{parent_label}へ');b.innerHTML='<span>{parent_label}</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>ページ一覧</strong><small></small>';title.querySelector('small').textContent=top.querySelector('.meta')?.textContent?.trim()||'';app.append(b,title);document.querySelector('main')?.prepend(app);const disable=()=>{{const active=document.querySelector('.page-card.active');if(!active)return false;active.disabled=true;active.setAttribute('aria-disabled','true');active.title='現在表示中のページ';return true}};if(!disable()){{const ob=new MutationObserver(()=>{{if(disable())ob.disconnect()}});ob.observe(document.getElementById('grid')||document.body,{{childList:true,subtree:true}});setTimeout(()=>ob.disconnect(),5000)}}}})();
</script>
"""
        elif progress_list:
            project_id = progress_list.group(1)
            page = max(1, request.args.get("page", default=1, type=int) or 1)
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-list');const old=document.querySelector('.topbar');if(!old)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='progress-list';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects/{project_id}/progress?page={page}';b.setAttribute('aria-label','進捗へ');b.innerHTML='<span>進捗</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>進捗一覧</strong><small></small>';title.querySelector('small').textContent=old.querySelector('.meta')?.textContent?.trim()||'';app.append(b,title);document.querySelector('main')?.prepend(app)}})();
</script>
"""
        elif favorites:
            script = f"""
<script data-weld-ui-shell-v3>
(() => {{document.body.classList.add('ui3-favorites');const top=document.querySelector('.top');if(!top)return;const app=document.createElement('div');app.className='ui3-appbar';app.dataset.ui3Header='favorites';const b=document.createElement('a');b.className='ui3-back';b.href='{prefix}/projects-screen';b.setAttribute('aria-label','工事一覧へ');b.innerHTML='<span>工事一覧</span>';const title=document.createElement('div');title.className='ui3-title';title.innerHTML='<strong>お気に入り</strong><small>工事横断</small>';app.append(b,title);document.querySelector('main')?.prepend(app)}})();
</script>
"""
        else:
            script = r"""
<script data-weld-ui-shell-v3>
(() => {document.body.classList.add('ui3-projects');const header=document.querySelector('.header'),newButton=document.getElementById('new-project');if(!header||!newButton)return;header.classList.add('ui3-root');const wrap=newButton.parentElement;wrap.classList.add('ui3-root-actions');const fav=[...wrap.querySelectorAll('button')].find(x=>x!==newButton&&/お気に入り/.test(x.textContent||''));if(fav){fav.dataset.ui3Favorites='1';fav.title='お気に入りページ一覧'}})();
</script>
"""

        html = html.replace("</head>", css + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint