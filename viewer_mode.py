import re

from flask import Blueprint, request


def create_viewer_mode_blueprint():
    blueprint = Blueprint("viewer_mode", __name__)

    @blueprint.after_app_request
    def apply_viewer_mode(response):
        if response.status_code != 200 or response.mimetype != "text/html":
            return response
        if request.args.get("viewer") != "1":
            return response
        match = re.fullmatch(r"(?:/weld)?/projects/(\d+)/progress", request.path)
        if not match:
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html or "</body>" not in html or "data-weld-viewer-v3" in html:
            return response

        project_id = match.group(1)
        prefix = request.script_root.rstrip("/")
        css = r"""
<style data-weld-viewer-v3>
html.weld-viewer-v3,html.weld-viewer-v3 body{margin:0!important;width:100%!important;height:100%!important;min-height:100%!important;background:#e9eaed!important;overflow:hidden!important}
html.weld-viewer-v3 main{margin:0!important;padding:0!important;max-width:none!important;width:100%!important;height:100dvh!important;min-height:100dvh!important}
html.weld-viewer-v3 .top,html.weld-viewer-v3 .toolbar,html.weld-viewer-v3 .statusline,html.weld-viewer-v3 .summary,html.weld-viewer-v3 .progress-thumbs{display:none!important}
html.weld-viewer-v3 .card{margin:0!important;padding:0!important;border:0!important;border-radius:0!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;overflow:hidden!important}
html.weld-viewer-v3 .viewer{display:block!important;width:100%!important;height:100dvh!important;min-height:100dvh!important;max-height:none!important;overflow:auto!important}
.weld-viewer-controls{position:fixed;z-index:180;top:max(8px,env(safe-area-inset-top));right:max(8px,env(safe-area-inset-right));display:flex;gap:8px}
.weld-viewer-controls button{width:48px;height:48px;border:0;border-radius:24px;background:rgba(32,33,36,.78);color:#fff;font:inherit;font-size:1.35rem;font-weight:800;touch-action:manipulation;cursor:pointer}
</style>
"""
        boot = "<script data-weld-viewer-v3>document.documentElement.classList.add('weld-viewer-v3')</script>"
        script = f"""
<script data-weld-viewer-v3>
(() => {{
  const projectId={project_id};
  const pageInput=document.getElementById('page');
  const viewer=document.getElementById('viewer');
  const canvas=document.getElementById('canvas');
  const rotate=document.getElementById('rotateCompact')||document.getElementById('rotate');
  const zoomIn=document.getElementById('zoomIn');
  const zoomReset=document.getElementById('zoomReset');
  if(!viewer||!canvas)return;
  const currentPage=()=>Math.max(1,Number(pageInput?.value)||1);
  const controls=document.createElement('div');controls.className='weld-viewer-controls';controls.setAttribute('aria-label','図面集中表示操作');
  const rotateButton=document.createElement('button');rotateButton.type='button';rotateButton.textContent='↻';rotateButton.setAttribute('aria-label','90度回転');
  const closeButton=document.createElement('button');closeButton.type='button';closeButton.textContent='×';closeButton.setAttribute('aria-label','図面集中表示を終了');
  controls.append(rotateButton,closeButton);document.body.append(controls);
  closeButton.onclick=()=>location.href=`{prefix}/projects/${{projectId}}/progress?page=${{currentPage()}}`;
  let fitting=false,fitted=false;
  const fit=()=>{{
    if(fitting||canvas.hidden||!canvas.width||!viewer.clientHeight||!zoomIn||!zoomReset)return;
    fitting=true;zoomReset.click();
    requestAnimationFrame(()=>{{
      let guard=0;
      while(canvas.getBoundingClientRect().height<viewer.clientHeight-1&&guard<8){{
        const before=canvas.getBoundingClientRect().height;zoomIn.click();guard++;
        if(canvas.getBoundingClientRect().height<=before+.5)break;
      }}
      viewer.scrollLeft=Math.max(0,(viewer.scrollWidth-viewer.clientWidth)/2);
      viewer.scrollTop=Math.max(0,(viewer.scrollHeight-viewer.clientHeight)/2);
      fitted=true;fitting=false;
    }});
  }};
  rotateButton.onclick=()=>{{rotate?.click();requestAnimationFrame(()=>requestAnimationFrame(fit))}};
  const observer=new MutationObserver(()=>{{if(!fitted&&canvas.width&&!canvas.hidden){{requestAnimationFrame(()=>requestAnimationFrame(fit));observer.disconnect()}}}});
  observer.observe(canvas,{{attributes:true,attributeFilter:['width','height','hidden']}});
  setTimeout(fit,80);
}})();
</script>
"""
        html = html.replace("</head>", boot + css + "</head>", 1)
        html = html.replace("</body>", script + "</body>", 1)
        response.set_data(html)
        return response

    return blueprint
