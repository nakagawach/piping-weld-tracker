import re

from flask import Blueprint, request


def create_ios_fullscreen_v8_blueprint():
    blueprint = Blueprint("ios_fullscreen_v8", __name__)

    @blueprint.after_app_request
    def apply_ios_fullscreen(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        if not re.fullmatch(r"(?:/weld)?/projects/\d+/progress", request.path):
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-ios-fullscreen-v8" in html:
            return response

        style = r'''
<style data-ios-fullscreen-v8>
body.ios-fullscreen-v8{overflow:hidden!important;background:#fff!important}
body.ios-fullscreen-v8 main{padding:0!important;margin:0!important;max-width:none!important;width:100%!important}
body.ios-fullscreen-v8 .top,
body.ios-fullscreen-v8 .weld-mobile-appbar,
body.ios-fullscreen-v8 .toolbar,
body.ios-fullscreen-v8 .statusline,
body.ios-fullscreen-v8 .summary,
body.ios-fullscreen-v8 .progress-thumbs{display:none!important}
body.ios-fullscreen-v8 .card{position:absolute!important;top:0!important;left:0!important;width:100%!important;height:100lvh!important;min-height:100lvh!important;border:0!important;border-radius:0!important;display:flex!important;flex-direction:column!important;overflow:hidden!important;background:#fff!important;z-index:240!important}
body.ios-fullscreen-v8 .viewer{flex:1 1 auto!important;width:100%!important;height:auto!important;min-height:0!important;max-height:none!important;overflow:auto!important;background:#fff!important}
body.ios-fullscreen-v8 #canvas{background:#fff!important}
.ios-fullscreen-v8-exit{display:none}
body.ios-fullscreen-v8 .ios-fullscreen-v8-exit{display:inline-flex!important;position:absolute!important;top:max(8px,env(safe-area-inset-top))!important;right:max(8px,env(safe-area-inset-right))!important;z-index:280!important;width:44px!important;height:44px!important;align-items:center!important;justify-content:center!important;border:0!important;border-radius:50%!important;background:rgba(32,33,36,.78)!important;color:#fff!important;font-size:1.45rem!important;font-weight:700!important;box-shadow:0 2px 8px #0004!important}
</style>
'''

        script = r'''
<script data-ios-fullscreen-v8>
(() => {
  const isIOS=/iP(?:hone|ad|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  if(!isIOS)return;

  const compact=document.getElementById('fullscreenCompact');
  const desktop=document.getElementById('fullscreen');
  const viewer=document.getElementById('viewer');
  const canvas=document.getElementById('canvas');
  const zoomIn=document.getElementById('zoomIn');
  const zoomReset=document.getElementById('zoomReset');
  const card=document.querySelector('.card');
  const more=document.getElementById('moreMenu');
  if(!compact||!viewer||!canvas||!zoomIn||!zoomReset||!card)return;

  let active=false;
  const exit=document.createElement('button');
  exit.type='button';exit.className='ios-fullscreen-v8-exit';exit.textContent='×';exit.setAttribute('aria-label','全画面表示を終了');
  card.appendChild(exit);

  const center=()=>{
    viewer.scrollLeft=Math.max(0,(viewer.scrollWidth-viewer.clientWidth)/2);
    viewer.scrollTop=Math.max(0,(viewer.scrollHeight-viewer.clientHeight)/2);
  };
  const fill=()=>{
    if(!active||canvas.hidden||!canvas.width)return;
    let guard=0;
    while(canvas.getBoundingClientRect().height < viewer.clientHeight-1 && guard<8){
      const before=canvas.getBoundingClientRect().height;
      zoomIn.click();
      const after=canvas.getBoundingClientRect().height;
      guard++;
      if(after<=before+0.5)break;
    }
    requestAnimationFrame(center);
  };
  const scheduleFill=()=>requestAnimationFrame(()=>requestAnimationFrame(fill));

  const enter=()=>{
    if(active)return;
    active=true;
    if(more?.open)more.removeAttribute('open');
    zoomReset.click();
    document.documentElement.style.height='100lvh';
    document.body.style.height='100lvh';
    document.body.classList.add('ios-fullscreen-v8');
    window.scrollTo(0,0);
    scheduleFill();
  };
  const leave=()=>{
    if(!active)return;
    active=false;
    document.body.classList.remove('ios-fullscreen-v8');
    document.documentElement.style.removeProperty('height');
    document.body.style.removeProperty('height');
    zoomReset.click();
    requestAnimationFrame(()=>{viewer.scrollLeft=0;viewer.scrollTop=0});
  };
  const intercept=e=>{
    e.preventDefault();
    e.stopImmediatePropagation();
    active?leave():enter();
  };

  compact.addEventListener('click',intercept,true);
  desktop?.addEventListener('click',intercept,true);
  exit.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();leave()});

  const refit=()=>{
    if(!active)return;
    zoomReset.click();
    scheduleFill();
  };
  window.addEventListener('orientationchange',refit);
  window.addEventListener('resize',refit);
  window.addEventListener('pagehide',()=>{
    window.removeEventListener('orientationchange',refit);
    window.removeEventListener('resize',refit);
  },{once:true});
})();
</script>
'''

        html = html.replace("</head>", style + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
