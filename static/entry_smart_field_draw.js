(() => {
  const host=window.__weldEntryAreaHost;
  const baseCanvas=host?.canvas;
  const viewer=baseCanvas?.closest('.viewer');
  const areaButton=document.getElementById('areaCreate');
  const rotateButton=document.getElementById('rotate');
  if(!host||!baseCanvas||!viewer||!areaButton||!rotateButton)return;
  if(document.getElementById('entrySmartFieldDraw'))return;

  const SCALE=1600/6000;
  let enabled=false,drawing=false,activePointerId=null,stroke=[],markerDrag=null;
  let sessions=[],selectedId=null,nextId=1,undoStack=[];

  const button=document.createElement('button');button.type='button';button.id='entrySmartFieldDraw';button.className='button';button.textContent='✏️ 現場入力';button.title='指・ペンで描いた線を細長い長方形、囲みを長方形/正方形へ補正';areaButton.insertAdjacentElement('afterend',button);
  const undoButton=document.createElement('button');undoButton.type='button';undoButton.id='entrySmartUndo';undoButton.className='button';undoButton.textContent='↶';undoButton.title='元に戻す';undoButton.disabled=true;button.insertAdjacentElement('afterend',undoButton);
  const deleteButton=document.createElement('button');deleteButton.type='button';deleteButton.id='entrySmartDelete';deleteButton.className='button danger';deleteButton.textContent='🗑';deleteButton.title='選択した現場入力エリアを削除';deleteButton.disabled=true;undoButton.insertAdjacentElement('afterend',deleteButton);
  const help=document.createElement('span');help.id='entrySmartFieldHelp';help.textContent='指/ペンで描く';help.style.cssText='font-size:12px;font-weight:600;white-space:nowrap;align-self:center';deleteButton.insertAdjacentElement('afterend',help);

  const overlay=document.createElement('canvas');overlay.id='entrySmartFieldCanvas';overlay.setAttribute('aria-label','現場入力フリーハンドレイヤー');overlay.style.cssText='position:absolute;z-index:5;pointer-events:none;touch-action:none;background:transparent;max-width:none;margin:0';viewer.style.position='relative';viewer.appendChild(overlay);

  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  const centerOf=item=>({x:item.bbox.x+item.bbox.w/2,y:item.bbox.y+item.bbox.h/2});
  const cloneBox=b=>({x:b.x,y:b.y,w:b.w,h:b.h});
  const clonePoints=pts=>pts.map(p=>({x:p.x,y:p.y}));
  const rotation=()=>{const m=rotateButton.textContent.match(/(0|90|180|270)/);return m?Number(m[1]):0};
  const sourceSize=()=>{const r=rotation();return r===90||r===270?{w:baseCanvas.height,h:baseCanvas.width}:{w:baseCanvas.width,h:baseCanvas.height}};
  const pageBounds=()=>{const s=sourceSize();return{w:s.w/SCALE,h:s.h/SCALE}};

  function context(){const ctx=overlay.getContext('2d');ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,overlay.width,overlay.height);const r=rotation();if(r===90){ctx.translate(overlay.width,0);ctx.rotate(Math.PI/2)}else if(r===180){ctx.translate(overlay.width,overlay.height);ctx.rotate(Math.PI)}else if(r===270){ctx.translate(0,overlay.height);ctx.rotate(-Math.PI/2)}return ctx}
  function syncOverlay(){if(!baseCanvas.width||!baseCanvas.height)return;const rect=baseCanvas.getBoundingClientRect();overlay.width=baseCanvas.width;overlay.height=baseCanvas.height;overlay.style.width=`${rect.width}px`;overlay.style.height=`${rect.height}px`;overlay.style.left=`${baseCanvas.offsetLeft}px`;overlay.style.top=`${baseCanvas.offsetTop}px`;render()}
  function drawSelected(ctx){const s=sessions.find(x=>x.id===selectedId);if(!s)return;ctx.save();ctx.beginPath();ctx.moveTo(s.points[0].x*SCALE,s.points[0].y*SCALE);for(let i=1;i<s.points.length;i++)ctx.lineTo(s.points[i].x*SCALE,s.points[i].y*SCALE);ctx.closePath();ctx.strokeStyle='#b3261e';ctx.lineWidth=Math.max(1.25,overlay.width/1300);ctx.setLineDash([7,5]);ctx.stroke();ctx.restore()}
  function drawMarkerPreview(ctx){if(!markerDrag)return;const item=host.getCandidates().find(x=>x.id===markerDrag.itemId);if(!item)return;const b=item.bbox;ctx.save();ctx.strokeStyle='#188038';ctx.lineWidth=Math.max(1.25,overlay.width/1300);ctx.strokeRect(b.x*SCALE,b.y*SCALE,b.w*SCALE,b.h*SCALE);ctx.restore()}
  function render(points=stroke){if(!overlay.width||!overlay.height)return;const ctx=context();drawSelected(ctx);drawMarkerPreview(ctx);if(!points.length)return;ctx.beginPath();ctx.moveTo(points[0].x*SCALE,points[0].y*SCALE);for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x*SCALE,points[i].y*SCALE);ctx.strokeStyle='#1967d2';ctx.lineWidth=Math.max(1.4,overlay.width/1100);ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke()}

  function pathLength(points){let n=0;for(let i=1;i<points.length;i++)n+=distance(points[i-1],points[i]);return n}
  function rotatedRectangle(points){const c=points.reduce((a,p)=>({x:a.x+p.x,y:a.y+p.y}),{x:0,y:0});c.x/=points.length;c.y/=points.length;let xx=0,yy=0,xy=0;for(const p of points){const dx=p.x-c.x,dy=p.y-c.y;xx+=dx*dx;yy+=dy*dy;xy+=dx*dy}const angle=.5*Math.atan2(2*xy,xx-yy),ux=Math.cos(angle),uy=Math.sin(angle),vx=-uy,vy=ux;let minU=Infinity,maxU=-Infinity,minV=Infinity,maxV=-Infinity;for(const p of points){const dx=p.x-c.x,dy=p.y-c.y,u=dx*ux+dy*uy,v=dx*vx+dy*vy;minU=Math.min(minU,u);maxU=Math.max(maxU,u);minV=Math.min(minV,v);maxV=Math.max(maxV,v)}const make=(u,v)=>({x:c.x+u*ux+v*vx,y:c.y+u*uy+v*vy});return[make(minU,minV),make(maxU,minV),make(maxU,maxV),make(minU,maxV)]}
  function lineStrip(a,b){const dx=b.x-a.x,dy=b.y-a.y,len=Math.max(1,Math.hypot(dx,dy));const half=Math.max(host.cssPxToOcrX(3),host.cssPxToOcrY(3));const nx=-dy/len*half,ny=dx/len*half;return[{x:a.x+nx,y:a.y+ny},{x:b.x+nx,y:b.y+ny},{x:b.x-nx,y:b.y-ny},{x:a.x-nx,y:a.y-ny}]}
  function recognize(points){if(points.length<2)return null;const length=pathLength(points);if(!length)return null;const direct=distance(points[0],points[points.length-1]);if(direct/length>=.88)return{kind:'細長い長方形',points:lineStrip(points[0],points[points.length-1])};const rect=rotatedRectangle(points);const edges=rect.map((p,i)=>distance(p,rect[(i+1)%4]));const short=Math.min(...edges),long=Math.max(...edges);if(short<Math.max(host.cssPxToOcrX(10),host.cssPxToOcrY(10)))return{kind:'細長い長方形',points:lineStrip(points[0],points[points.length-1])};return{kind:long/short<=1.20?'正方形':'長方形',points:rect}}
  function pointInPolygon(p,pts){let inside=false;for(let i=0,j=pts.length-1;i<pts.length;j=i++){const a=pts[i],b=pts[j];if(((a.y>p.y)!==(b.y>p.y))&&p.x<(b.x-a.x)*(p.y-a.y)/((b.y-a.y)||1e-9)+a.x)inside=!inside}return inside}
  function shapeCenter(points){return points.reduce((a,p)=>({x:a.x+p.x/points.length,y:a.y+p.y/points.length}),{x:0,y:0})}
  function nearestCandidate(points){const c=shapeCenter(points),page=pageBounds(),limit=Math.hypot(page.w,page.h)*.24;let best=null,bd=Infinity;for(const item of host.getCandidates()){const d=distance(c,centerOf(item));if(d<bd){best=item;bd=d}}return bd<=limit?best:null}
  function median(values){if(!values.length)return null;const a=values.slice().sort((x,y)=>x-y),m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2}
  function overlap(a,b,pad=0){return!(a.x+a.w+pad<b.x||b.x+b.w+pad<a.x||a.y+a.h+pad<b.y||b.y+b.h+pad<a.y)}
  function markerCenter(points){
    const xs=points.map(p=>p.x),ys=points.map(p=>p.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),midX=(minX+maxX)/2,midY=(minY+maxY)/2;
    const items=host.getCandidates(),page=pageBounds();
    const mw=Math.max(median(items.map(x=>x.bbox.w).filter(Boolean))||0,host.cssPxToOcrX(22)),mh=Math.max(median(items.map(x=>x.bbox.h).filter(Boolean))||0,host.cssPxToOcrY(22));
    const shapeBox={x:minX,y:minY,w:maxX-minX,h:maxY-minY};
    const baseGap=Math.max(host.cssPxToOcrX(14),host.cssPxToOcrY(14));
    const dirs=[[1,0],[-1,0],[0,-1],[0,1],[1,-1],[1,1],[-1,-1],[-1,1]];
    let fallback=null,fallbackScore=Infinity;
    for(let ring=1;ring<=6;ring++){
      const gap=baseGap*ring;
      for(const [dx,dy] of dirs){
        const x=dx>0?maxX+gap+mw/2:dx<0?minX-gap-mw/2:midX;
        const y=dy>0?maxY+gap+mh/2:dy<0?minY-gap-mh/2:midY;
        const box={x:x-mw/2,y:y-mh/2,w:mw,h:mh};
        let penalty=distance({x,y},{x:midX,y:midY});
        const out=box.x<0||box.y<0||box.x+box.w>page.w||box.y+box.h>page.h;
        const shapeHit=overlap(box,shapeBox,baseGap*.2);
        const markerHits=items.filter(item=>overlap(box,item.bbox,baseGap*.35)).length;
        if(out)penalty+=1e9;if(shapeHit)penalty+=1e7;if(markerHits)penalty+=markerHits*1e8;
        if(!out&&!shapeHit&&!markerHits)return{x,y};
        if(penalty<fallbackScore){fallbackScore=penalty;fallback={x,y}}
      }
    }
    return fallback||{x:midX,y:midY};
  }

  function ocrToCanvas(point){const s=sourceSize(),x=point.x*SCALE,y=point.y*SCALE,r=rotation();if(r===90)return{x:s.h-y,y:x};if(r===180)return{x:s.w-x,y:s.h-y};if(r===270)return{x:y,y:s.w-x};return{x,y}}
  function dispatchClick(point){const p=ocrToCanvas(point),rect=baseCanvas.getBoundingClientRect();baseCanvas.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,button:0,detail:1,clientX:rect.left+p.x*rect.width/baseCanvas.width,clientY:rect.top+p.y*rect.height/baseCanvas.height}))}
  function withPrompt(value,fn){const original=window.prompt;window.prompt=()=>value;try{fn()}finally{window.prompt=original}}
  function normalizeNumber(value){const t=String(value??'').normalize('NFKC').toUpperCase().replace(/\s+/g,'').trim();if(/^\d{1,3}$/.test(t)&&Number(t)>=1)return String(Number(t));return/^(?:[A-Z]{1,4}[-/]?\d{1,4}(?:[-/][A-Z0-9]{1,4})?|\d{1,4}[-/]?[A-Z]{1,3})$/.test(t)?t:null}
  function enableMarkerNumber(item){const w=Math.max(host.cssPxToOcrX(14),20),h=Math.max(host.cssPxToOcrY(14),20),gap=Math.max(host.cssPxToOcrX(3),4);dispatchClick({x:item.bbox.x+item.bbox.w+gap+w/2,y:item.bbox.y+h/2})}
  function createCandidate(number,center){const before=new Set(host.getCandidates().map(x=>x.id));withPrompt(number,()=>dispatchClick(center));const item=host.getCandidates().find(x=>!before.has(x.id))||null;if(item)enableMarkerNumber(item);return item}
  function createArea(candidate,points){const areaCanvas=document.getElementById('entryAreaCanvas');const before=Number(areaCanvas?.dataset.areaCount||0);if(areaButton.classList.contains('active'))areaButton.click();areaButton.click();dispatchClick(centerOf(candidate));for(const p of points)dispatchClick(p);dispatchClick(points[0]);if(areaButton.classList.contains('active'))areaButton.click();return Number(areaCanvas?.dataset.areaCount||0)>before}
  function removeCandidate(id){const list=host.getCandidates(),i=list.findIndex(x=>x.id===id);if(i<0)return null;return list.splice(i,1)[0]}
  function forceRedraw(){const edit=host.bboxEditButton;if(!edit||host.isBusy())return;const active=edit.classList.contains('active');if(active){edit.click();edit.click()}else{edit.click();edit.click()}}
  function deleteArea(shape){if(!shape)return false;if(areaButton.classList.contains('active'))areaButton.click();areaButton.click();dispatchClick(shapeCenter(shape.points));document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}));if(areaButton.classList.contains('active'))areaButton.click();return true}
  function updateButtons(){undoButton.disabled=!undoStack.length;deleteButton.disabled=selectedId===null}
  function pushUndo(action){undoStack.push(action);if(undoStack.length>30)undoStack.shift();updateButtons()}
  function registerSession(target,shape){const rec={id:nextId++,targetId:target.id,number:target.number,points:clonePoints(shape.points),markerBox:cloneBox(target.bbox)};sessions.push(rec);selectedId=rec.id;updateButtons();return rec}
  function nextNumber(){const nums=host.getCandidates().map(x=>/^\d+$/.test(String(x.number))?Number(x.number):null).filter(Number.isInteger);return nums.length?String(Math.max(...nums)+1):''}

  function commitShape(shape){
    const near=nearestCandidate(shape.points);
    const raw=window.prompt(`${shape.kind}に補正しました。丸枠番号を確認してください。\n番号候補だけ近くのOCRから取得します。丸枠は空き余白へ新規配置します。`,near?.number||nextNumber());
    if(raw===null)return;const number=normalizeNumber(raw);if(!number){host.status.className='status error';host.status.textContent='番号は1〜999、F1、S2、A-12等で入力してください。';return}
    if(!window.confirm(`${shape.kind} + 丸枠 ${number} + 接続線として追加しますか？`))return;
    const target=createCandidate(number,markerCenter(shape.points));
    if(!target){host.status.className='status error';host.status.textContent='丸枠を作成できませんでした。既存データは変更していません。';return}
    if(!createArea(target,shape.points)){removeCandidate(target.id);forceRedraw();host.status.className='status error';host.status.textContent='エリアを作成できませんでした。追加した丸枠は取り消しました。';return}
    const rec=registerSession(target,shape);pushUndo({type:'create',sessionId:rec.id});host.setDirty(true);host.status.className='status';host.status.textContent=`${shape.kind}を作成し、丸枠 ${number} を最寄りの空き余白へ配置しました。`;forceRedraw();render();
  }

  function selectSession(p){for(let i=sessions.length-1;i>=0;i--)if(pointInPolygon(p,sessions[i].points))return sessions[i];return null}
  function deleteSession(rec,push=true){if(!rec)return;const target=host.getCandidates().find(x=>x.id===rec.targetId);const snap={...rec,points:clonePoints(rec.points),markerBox:target?cloneBox(target.bbox):cloneBox(rec.markerBox)};deleteArea(rec);if(target)removeCandidate(target.id);sessions=sessions.filter(x=>x.id!==rec.id);selectedId=null;if(push)pushUndo({type:'delete',session:snap});host.setDirty(true);forceRedraw();render();updateButtons()}
  function undo(){const a=undoStack.pop();if(!a)return;if(a.type==='create'){const rec=sessions.find(x=>x.id===a.sessionId);if(rec)deleteSession(rec,false)}else if(a.type==='move'){const item=host.getCandidates().find(x=>x.id===a.itemId);if(item){item.bbox=cloneBox(a.before);host.setDirty(true);forceRedraw()}}else if(a.type==='delete'){const s=a.session;const target=createCandidate(s.number,{x:s.markerBox.x+s.markerBox.w/2,y:s.markerBox.y+s.markerBox.h/2});if(target&&createArea(target,s.points)){s.targetId=target.id;s.markerBox=cloneBox(target.bbox);sessions.push(s);selectedId=s.id;host.setDirty(true);forceRedraw()}}updateButtons();render()}

  function setEnabled(on){enabled=!!on;drawing=false;activePointerId=null;stroke=[];markerDrag=null;selectedId=null;if(enabled){host.disableBboxEdit();host.clearSelection();if(areaButton.classList.contains('active'))areaButton.click();button.classList.add('active');button.textContent='✏️ 現場入力 ON';help.textContent='描く/丸枠ドラッグ';overlay.style.pointerEvents='auto';host.status.className='status';host.status.textContent='現場入力ON：線は細長い長方形、囲みは長方形/正方形へ補正します。丸枠は空き余白へ配置します。'}else{button.classList.remove('active');button.textContent='✏️ 現場入力';help.textContent='指/ペンで描く';overlay.style.pointerEvents='none';host.status.className='status';host.status.textContent='現場入力OFF：従来のOCR・枠編集・エリア作成を利用できます。'}updateButtons();render()}
  button.addEventListener('click',()=>{if(!host.isBusy())setEnabled(!enabled)});undoButton.addEventListener('click',undo);deleteButton.addEventListener('click',()=>deleteSession(sessions.find(x=>x.id===selectedId)));

  overlay.addEventListener('pointerdown',e=>{if(!enabled||host.isBusy()||drawing||markerDrag||(e.pointerType==='mouse'&&e.button!==0))return;e.preventDefault();e.stopPropagation();const p=host.point(e),hit=host.findAt(p);if(hit?.source==='manual'){markerDrag={pointerId:e.pointerId,itemId:hit.id,startPoint:p,startBox:cloneBox(hit.bbox),moved:false};activePointerId=e.pointerId;overlay.setPointerCapture(e.pointerId);render();return}const ses=selectSession(p);if(ses){selectedId=ses.id;updateButtons();render();return}selectedId=null;updateButtons();drawing=true;activePointerId=e.pointerId;stroke=[p];overlay.setPointerCapture(e.pointerId);render()},{passive:false});
  overlay.addEventListener('pointermove',e=>{if(!enabled||e.pointerId!==activePointerId)return;e.preventDefault();e.stopPropagation();if(markerDrag){const item=host.getCandidates().find(x=>x.id===markerDrag.itemId);if(!item)return;const p=host.point(e),dx=p.x-markerDrag.startPoint.x,dy=p.y-markerDrag.startPoint.y,page=pageBounds();item.bbox={...markerDrag.startBox,x:Math.max(0,Math.min(page.w-markerDrag.startBox.w,markerDrag.startBox.x+dx)),y:Math.max(0,Math.min(page.h-markerDrag.startBox.h,markerDrag.startBox.y+dy))};markerDrag.moved=markerDrag.moved||Math.hypot(dx,dy)>Math.max(host.cssPxToOcrX(2),host.cssPxToOcrY(2));render();return}if(!drawing)return;const p=host.point(e),last=stroke[stroke.length-1],min=Math.max(host.cssPxToOcrX(2),host.cssPxToOcrY(2));if(!last||distance(last,p)>=min)stroke.push(p);render()},{passive:false});
  function finishMarker(e,cancelled=false){if(!markerDrag||e.pointerId!==markerDrag.pointerId)return false;e.preventDefault();e.stopPropagation();if(overlay.hasPointerCapture(e.pointerId))overlay.releasePointerCapture(e.pointerId);const item=host.getCandidates().find(x=>x.id===markerDrag.itemId),before=cloneBox(markerDrag.startBox),changed=markerDrag.moved&&!cancelled;if(cancelled&&item)item.bbox=before;if(changed&&item){pushUndo({type:'move',itemId:item.id,before});host.setDirty(true);forceRedraw();host.status.className='status';host.status.textContent='丸枠を移動しました。接続線も追従します。'}markerDrag=null;activePointerId=null;render();return true}
  function finish(e,cancelled=false){if(finishMarker(e,cancelled))return;if(!drawing||e.pointerId!==activePointerId)return;e.preventDefault();e.stopPropagation();if(overlay.hasPointerCapture(e.pointerId))overlay.releasePointerCapture(e.pointerId);drawing=false;activePointerId=null;const pts=stroke.slice();stroke=[];render();if(cancelled||pts.length<2)return;const shape=recognize(pts);if(!shape){host.status.className='status error';host.status.textContent='形を認識できませんでした。';return}render(shape.points);requestAnimationFrame(()=>{commitShape(shape);stroke=[];render()})}
  overlay.addEventListener('pointerup',e=>finish(e,false),{passive:false});overlay.addEventListener('pointercancel',e=>finish(e,true),{passive:false});
  window.addEventListener('weld:entry-base-drawn',()=>{sessions=[];selectedId=null;undoStack=[];updateButtons();syncOverlay()});window.addEventListener('weld:entry-zoom-changed',syncOverlay);window.addEventListener('resize',syncOverlay);if('ResizeObserver'in window)new ResizeObserver(syncOverlay).observe(viewer);
  window.__weldSmartFieldDrawTest={recognize,lineStrip,rotatedRectangle,markerCenter};
  syncOverlay();
})();
