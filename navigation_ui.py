import re

from flask import Blueprint, request


def create_navigation_ui_blueprint():
    blueprint = Blueprint("navigation_ui", __name__)

    @blueprint.after_app_request
    def unify_navigation(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-navigation-ui" in html:
            return response

        path = request.path
        project_view = re.fullmatch(r"(?:/weld)?/projects/(\d+)/(entry|progress|thumbnails)", path)
        is_favorites = bool(re.fullmatch(r"(?:/weld)?/favorites", path))
        is_progress_list = bool(re.fullmatch(r"(?:/weld)?/projects/\d+/progress-list", path))
        if not (project_view or is_favorites or is_progress_list):
            return response

        style = """
<style data-navigation-ui>
.nav-unified{display:flex!important;align-items:center!important;justify-content:flex-start!important;gap:9px!important}
.nav-unified>.nav-title-area{min-width:0;flex:1 1 auto}
.nav-back-unified{flex:0 0 auto!important;min-width:44px!important;min-height:42px!important;padding:0 10px!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important;text-decoration:none!important}
.nav-back-unified .nav-back-icon{font-size:1.35rem;line-height:1;margin-right:3px}
.mobile-project-back{display:none!important}
@media(max-width:640px){
  .nav-unified{position:sticky!important;top:0!important;z-index:40!important;background:#fff!important;border-bottom:1px solid #dadce0!important;padding:5px max(8px,env(safe-area-inset-right)) 5px max(8px,env(safe-area-inset-left))!important;margin-bottom:8px!important}
  .nav-back-unified{width:auto!important;min-width:40px!important;min-height:40px!important;padding:0 8px!important;border-radius:9px!important}
  .nav-back-unified .nav-back-label{display:none!important}
  .nav-back-unified .nav-back-icon{margin-right:0!important}
  .nav-unified .title{font-size:1.05rem!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
  .nav-unified .meta,.nav-unified .sub{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
}
@media(max-width:820px){
  body[data-nav-page="progress"] .mobile-project-back{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:34px!important;width:34px!important;height:40px!important;padding:0!important;font-size:1.25rem!important}
}
@media(max-width:480px) and (orientation:portrait){
  body[data-nav-page="progress"] .toolbar{grid-template-columns:34px 34px minmax(60px,1fr) 34px 38px 38px 38px!important;gap:3px!important}
  body[data-nav-page="progress"] .toolbar>.mobile-project-back{grid-column:1!important;grid-row:1!important}
  body[data-nav-page="progress"] .toolbar>#prev{grid-column:2!important;grid-row:1!important;min-width:34px!important}
  body[data-nav-page="progress"] .toolbar>.page-field{grid-column:3!important;grid-row:1!important}
  body[data-nav-page="progress"] .toolbar>#next{grid-column:4!important;grid-row:1!important;min-width:34px!important}
  body[data-nav-page="progress"] .toolbar>.page-favorite-view{grid-column:5!important;grid-row:1!important;min-width:38px!important}
  body[data-nav-page="progress"] .toolbar>.compact-rotate{grid-column:6!important;grid-row:1!important;min-width:38px!important}
  body[data-nav-page="progress"] .toolbar>.more{grid-column:7!important;grid-row:1!important}
  body[data-nav-page="progress"] .toolbar>[aria-label="ページ一覧"]{grid-column:1/4!important;grid-row:2!important;width:100%!important}
  body[data-nav-page="progress"] .toolbar>[aria-label="進捗一覧"]{grid-column:4/8!important;grid-row:2!important;width:100%!important}
}
@media(min-width:481px) and (max-width:820px){
  body[data-nav-page="progress"] .toolbar>.mobile-project-back{order:-20!important}
  body[data-nav-page="progress"] .toolbar>#prev{order:-19!important}
  body[data-nav-page="progress"] .toolbar>.page-field{order:-18!important}
  body[data-nav-page="progress"] .toolbar>#next{order:-17!important}
}
</style>
"""

        if project_view:
            _, source = project_view.groups()
            if source == "progress":
                script = """
<script data-navigation-ui>
(() => {
  document.body.dataset.navPage='progress';
  const top=document.querySelector('.top');
  const back=document.getElementById('back');
  if(top&&back){
    top.classList.add('nav-unified');
    back.classList.add('nav-back-unified');
    back.innerHTML='<span class="nav-back-icon" aria-hidden="true">‹</span><span class="nav-back-label">工事一覧</span>';
    const titleArea=[...top.children].find(x=>x!==back);if(titleArea)titleArea.classList.add('nav-title-area');
    top.insertBefore(back,top.firstChild);
  }
  const toolbar=document.querySelector('.toolbar');
  if(toolbar&&!toolbar.querySelector('.mobile-project-back')){
    const mobileBack=document.createElement('button');mobileBack.type='button';mobileBack.className='button mobile-project-back';mobileBack.setAttribute('aria-label','工事一覧へ戻る');mobileBack.title='工事一覧へ戻る';mobileBack.textContent='‹';
    mobileBack.onclick=()=>back?.click();toolbar.insertBefore(mobileBack,toolbar.firstChild);
  }
})();
</script>
"""
            elif source == "entry":
                script = """
<script data-navigation-ui>
(() => {
  document.body.dataset.navPage='entry';
  const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;
  top.classList.add('nav-unified');back.classList.add('nav-back-unified');back.innerHTML='<span class="nav-back-icon" aria-hidden="true">‹</span><span class="nav-back-label">工事一覧</span>';
  const titleArea=[...top.children].find(x=>x!==back);if(titleArea)titleArea.classList.add('nav-title-area');top.insertBefore(back,top.firstChild);
})();
</script>
"""
            else:
                script = """
<script data-navigation-ui>
(() => {
  document.body.dataset.navPage='thumbnails';
  const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;
  top.classList.add('nav-unified');back.classList.add('nav-back-unified');back.innerHTML='<span class="nav-back-icon" aria-hidden="true">‹</span><span class="nav-back-label">戻る</span>';
  const titleArea=[...top.children].find(x=>x!==back);if(titleArea)titleArea.classList.add('nav-title-area');top.insertBefore(back,top.firstChild);
})();
</script>
"""
        elif is_favorites:
            script = """
<script data-navigation-ui>
(() => {
  document.body.dataset.navPage='favorites';
  const top=document.querySelector('.top'),back=document.getElementById('back');if(!top||!back)return;
  top.classList.add('nav-unified');back.classList.add('nav-back-unified');back.innerHTML='<span class="nav-back-icon" aria-hidden="true">‹</span><span class="nav-back-label">工事一覧</span>';
  const titleArea=[...top.children].find(x=>x!==back);if(titleArea)titleArea.classList.add('nav-title-area');top.insertBefore(back,top.firstChild);
})();
</script>
"""
        else:
            script = """
<script data-navigation-ui>
(() => {
  document.body.dataset.navPage='progress-list';
  const bar=document.querySelector('.topbar'),back=bar?.querySelector('.back');if(!bar||!back)return;
  bar.classList.add('nav-unified');back.classList.add('nav-back-unified');
  const titleArea=bar.querySelector('.titlebox');if(titleArea)titleArea.classList.add('nav-title-area');
})();
</script>
"""

        html = html.replace("</head>", style + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
