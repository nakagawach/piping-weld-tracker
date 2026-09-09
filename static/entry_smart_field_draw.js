(() => {
  const host = window.__weldEntryAreaHost;
  const baseCanvas = host?.canvas;
  const viewer = baseCanvas?.closest('.viewer');
  const areaButton = document.getElementById('areaCreate');
  const rotateButton = document.getElementById('rotate');
  if (!host || !baseCanvas || !viewer || !areaButton || !rotateButton) return;
  if (document.getElementById('entrySmartFieldDraw')) return;

  const SCALE = 1600 / 6000;
  const MAX_POINTS = 32;
  let enabled = false;
  let drawing = false;
  let activePointerId = null;
  let stroke = [];

  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'entrySmartFieldDraw';
  button.className = 'button';
  button.textContent = '✏️ 現場入力';
  button.title = '指・ペンで描いて直線・長方形・ポリゴンへ自動補正';
  areaButton.insertAdjacentElement('afterend', button);

  const help = document.createElement('span');
  help.id = 'entrySmartFieldHelp';
  help.textContent = '指/ペンで囲む';
  help.style.cssText = 'font-size:12px;font-weight:600;white-space:nowrap;align-self:center';
  button.insertAdjacentElement('afterend', help);

  const overlay = document.createElement('canvas');
  overlay.id = 'entrySmartFieldCanvas';
  overlay.setAttribute('aria-label', '現場入力フリーハンドレイヤー');
  overlay.style.cssText = 'position:absolute;z-index:5;pointer-events:none;touch-action:none;background:transparent;max-width:none;margin:0';
  viewer.style.position = 'relative';
  viewer.appendChild(overlay);

  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const centerOf = item => ({x:item.bbox.x + item.bbox.w / 2, y:item.bbox.y + item.bbox.h / 2});

  function rotation() {
    const m = rotateButton.textContent.match(/(0|90|180|270)/);
    return m ? Number(m[1]) : 0;
  }

  function sourceSize() {
    const r = rotation();
    return r === 90 || r === 270
      ? {w:baseCanvas.height, h:baseCanvas.width}
      : {w:baseCanvas.width, h:baseCanvas.height};
  }

  function pageBounds() {
    const s = sourceSize();
    return {w:s.w / SCALE, h:s.h / SCALE};
  }

  function syncOverlay() {
    if (!baseCanvas.width || !baseCanvas.height) return;
    const rect = baseCanvas.getBoundingClientRect();
    overlay.width = baseCanvas.width;
    overlay.height = baseCanvas.height;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
    overlay.style.left = `${baseCanvas.offsetLeft}px`;
    overlay.style.top = `${baseCanvas.offsetTop}px`;
    renderStroke();
  }

  function context() {
    const ctx = overlay.getContext('2d');
    ctx.setTransform(1,0,0,1,0,0);
    ctx.clearRect(0,0,overlay.width,overlay.height);
    const r = rotation();
    if (r === 90) { ctx.translate(overlay.width,0); ctx.rotate(Math.PI/2); }
    else if (r === 180) { ctx.translate(overlay.width,overlay.height); ctx.rotate(Math.PI); }
    else if (r === 270) { ctx.translate(0,overlay.height); ctx.rotate(-Math.PI/2); }
    return ctx;
  }

  function renderStroke(points = stroke) {
    if (!overlay.width || !overlay.height) return;
    const ctx = context();
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0].x * SCALE, points[0].y * SCALE);
    for (let i=1;i<points.length;i++) ctx.lineTo(points[i].x * SCALE, points[i].y * SCALE);
    ctx.strokeStyle = '#1967d2';
    ctx.lineWidth = Math.max(4, overlay.width / 420);
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  }

  function pathLength(points) {
    let total = 0;
    for (let i=1;i<points.length;i++) total += distance(points[i-1], points[i]);
    return total;
  }

  function pointSegmentDistance(p,a,b) {
    const vx=b.x-a.x, vy=b.y-a.y, len=vx*vx+vy*vy;
    const t=len ? Math.max(0,Math.min(1,((p.x-a.x)*vx+(p.y-a.y)*vy)/len)) : 0;
    return Math.hypot(p.x-(a.x+t*vx), p.y-(a.y+t*vy));
  }

  function simplify(points,tolerance) {
    if (points.length <= 2) return points.slice();
    let max=0,index=0;
    for (let i=1;i<points.length-1;i++) {
      const d=pointSegmentDistance(points[i],points[0],points[points.length-1]);
      if (d>max) { max=d; index=i; }
    }
    if (max<=tolerance) return [points[0],points[points.length-1]];
    const left=simplify(points.slice(0,index+1),tolerance);
    const right=simplify(points.slice(index),tolerance);
    return left.slice(0,-1).concat(right);
  }

  function polygonArea(points) {
    let sum=0;
    for (let i=0;i<points.length;i++) {
      const a=points[i], b=points[(i+1)%points.length];
      sum += a.x*b.y-b.x*a.y;
    }
    return Math.abs(sum)/2;
  }

  function rotatedRectangle(points) {
    const c=points.reduce((a,p)=>({x:a.x+p.x,y:a.y+p.y}),{x:0,y:0});
    c.x/=points.length; c.y/=points.length;
    let xx=0,yy=0,xy=0;
    for (const p of points) {
      const dx=p.x-c.x,dy=p.y-c.y;
      xx+=dx*dx; yy+=dy*dy; xy+=dx*dy;
    }
    const angle=.5*Math.atan2(2*xy,xx-yy), ux=Math.cos(angle),uy=Math.sin(angle),vx=-uy,vy=ux;
    let minU=Infinity,maxU=-Infinity,minV=Infinity,maxV=-Infinity;
    for (const p of points) {
      const dx=p.x-c.x,dy=p.y-c.y,u=dx*ux+dy*uy,v=dx*vx+dy*vy;
      minU=Math.min(minU,u); maxU=Math.max(maxU,u); minV=Math.min(minV,v); maxV=Math.max(maxV,v);
    }
    const make=(u,v)=>({x:c.x+u*ux+v*vx,y:c.y+u*uy+v*vy});
    return {points:[make(minU,minV),make(maxU,minV),make(maxU,maxV),make(minU,maxV)],area:Math.max(1,(maxU-minU)*(maxV-minV))};
  }

  function lineStrip(a,b) {
    const dx=b.x-a.x,dy=b.y-a.y,len=Math.max(1,Math.hypot(dx,dy));
    const half=Math.max(host.cssPxToOcrX(8),host.cssPxToOcrY(8));
    const nx=-dy/len*half,ny=dx/len*half;
    return [{x:a.x+nx,y:a.y+ny},{x:b.x+nx,y:b.y+ny},{x:b.x-nx,y:b.y-ny},{x:a.x-nx,y:a.y-ny}];
  }

  function cap(points) {
    if (points.length<=MAX_POINTS) return points;
    return Array.from({length:MAX_POINTS},(_,i)=>points[Math.floor(i*points.length/MAX_POINTS)]);
  }

  function recognize(points) {
    if (points.length<2) return null;
    const length=pathLength(points),direct=distance(points[0],points[points.length-1]);
    if (!length) return null;
    if (direct/length>=.92) return {kind:'直線',points:lineStrip(points[0],points[points.length-1])};

    const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
    const diagonal=Math.hypot(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys));
    const closeTolerance=Math.max(host.cssPxToOcrX(24),host.cssPxToOcrY(24),diagonal*.16);
    if (direct>closeTolerance) return null;

    const closed=points.slice();
    closed[closed.length-1]={...closed[0]};
    const tolerance=Math.max(host.cssPxToOcrX(6),host.cssPxToOcrY(6),diagonal*.012);
    let simple=simplify(closed,tolerance);
    if (simple.length>1 && distance(simple[0],simple[simple.length-1])<=closeTolerance) simple.pop();
    simple=cap(simple);
    if (simple.length<3) return null;

    const rect=rotatedRectangle(closed);
    if (polygonArea(closed)/rect.area>=.68 && simple.length<=10) return {kind:'長方形',points:rect.points};
    return {kind:'ポリゴン',points:simple};
  }

  function shapeCenter(points) {
    return points.reduce((a,p)=>({x:a.x+p.x/points.length,y:a.y+p.y/points.length}),{x:0,y:0});
  }

  function nearestCandidate(points) {
    const c=shapeCenter(points),page=pageBounds(),limit=Math.hypot(page.w,page.h)*.24;
    let best=null,bestDistance=Infinity;
    for (const item of host.getCandidates()) {
      const d=distance(c,centerOf(item));
      if (d<bestDistance) {best=item;bestDistance=d;}
    }
    return bestDistance<=limit ? best : null;
  }

  function median(values) {
    if (!values.length) return null;
    const a=values.slice().sort((x,y)=>x-y),m=Math.floor(a.length/2);
    return a.length%2?a[m]:(a[m-1]+a[m])/2;
  }

  function overlap(a,b,pad=0) {
    return !(a.x+a.w+pad<b.x || b.x+b.w+pad<a.x || a.y+a.h+pad<b.y || b.y+b.h+pad<a.y);
  }

  function markerCenter(points) {
    const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
    const shape={minX:Math.min(...xs),minY:Math.min(...ys),maxX:Math.max(...xs),maxY:Math.max(...ys)};
    const candidates=host.getCandidates();
    const markerW=Math.max(median(candidates.map(x=>x.bbox.w).filter(Boolean))||0,host.cssPxToOcrX(22));
    const markerH=Math.max(median(candidates.map(x=>x.bbox.h).filter(Boolean))||0,host.cssPxToOcrY(22));
    const gap=Math.max(host.cssPxToOcrX(28),host.cssPxToOcrY(28));
    const midX=(shape.minX+shape.maxX)/2,midY=(shape.minY+shape.maxY)/2;
    const choices=[
      {x:shape.maxX+gap+markerW/2,y:midY},{x:shape.minX-gap-markerW/2,y:midY},
      {x:midX,y:shape.minY-gap-markerH/2},{x:midX,y:shape.maxY+gap+markerH/2},
      {x:shape.maxX+gap+markerW/2,y:shape.minY-gap-markerH/2},{x:shape.maxX+gap+markerW/2,y:shape.maxY+gap+markerH/2},
      {x:shape.minX-gap-markerW/2,y:shape.minY-gap-markerH/2},{x:shape.minX-gap-markerW/2,y:shape.maxY+gap+markerH/2}
    ];
    const page=pageBounds(),shapeBox={x:shape.minX,y:shape.minY,w:shape.maxX-shape.minX,h:shape.maxY-shape.minY};
    let best=choices[0],bestScore=Infinity;
    for (const p of choices) {
      const box={x:p.x-markerW/2,y:p.y-markerH/2,w:markerW,h:markerH};
      let score=distance(p,{x:midX,y:midY});
      if (box.x<0||box.y<0||box.x+box.w>page.w||box.y+box.h>page.h) score+=1e9;
      if (overlap(box,shapeBox,gap*.25)) score+=1e7;
      for (const item of candidates) if (overlap(box,item.bbox,gap*.18)) score+=1e6;
      if (score<bestScore) {bestScore=score;best=p;}
    }
    return best;
  }

  function ocrToCanvas(point) {
    const s=sourceSize(),x=point.x*SCALE,y=point.y*SCALE,r=rotation();
    if (r===90) return {x:s.h-y,y:x};
    if (r===180) return {x:s.w-x,y:s.h-y};
    if (r===270) return {x:y,y:s.w-x};
    return {x,y};
  }

  function dispatchClick(point) {
    const p=ocrToCanvas(point),rect=baseCanvas.getBoundingClientRect();
    baseCanvas.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,button:0,detail:1,
      clientX:rect.left+p.x*rect.width/baseCanvas.width,clientY:rect.top+p.y*rect.height/baseCanvas.height}));
  }

  function withPrompt(value,fn) {
    const original=window.prompt;
    window.prompt=()=>value;
    try { fn(); } finally { window.prompt=original; }
  }

  function normalizeNumber(value) {
    const t=String(value??'').normalize('NFKC').toUpperCase().replace(/\s+/g,'').trim();
    if (/^\d{1,3}$/.test(t) && Number(t)>=1) return String(Number(t));
    return /^(?:[A-Z]{1,4}[-/]?\d{1,4}(?:[-/][A-Z0-9]{1,4})?|\d{1,4}[-/]?[A-Z]{1,3})$/.test(t)?t:null;
  }

  function createCandidate(number,center) {
    const before=new Set(host.getCandidates().map(x=>x.id));
    withPrompt(number,()=>dispatchClick(center));
    return host.getCandidates().find(x=>!before.has(x.id))||null;
  }

  function createArea(candidate,points) {
    if (!candidate || points.length<3) return false;
    const areaCanvas=document.getElementById('entryAreaCanvas');
    const before=Number(areaCanvas?.dataset.areaCount||0);
    if (areaButton.classList.contains('active')) areaButton.click();
    areaButton.click();
    dispatchClick(centerOf(candidate));
    for (const p of points) dispatchClick(p);
    dispatchClick(points[0]);
    if (areaButton.classList.contains('active')) areaButton.click();
    return Number(areaCanvas?.dataset.areaCount||0)>before;
  }

  function nextNumber() {
    const nums=host.getCandidates().map(x=>/^\d+$/.test(String(x.number))?Number(x.number):null).filter(Number.isInteger);
    return nums.length?String(Math.max(...nums)+1):'';
  }

  function commitShape(shape) {
    const nearest=nearestCandidate(shape.points);
    const raw=window.prompt(`${shape.kind}に補正しました。丸枠番号を確認してください。\n近くのOCR番号を候補にしています。`,nearest?.number||nextNumber());
    if (raw===null) return;
    const number=normalizeNumber(raw);
    if (!number) {
      host.status.className='status error';
      host.status.textContent='番号は1〜999、F1、S2、A-12等で入力してください。';
      return;
    }
    if (!window.confirm(`${shape.kind} + 丸枠 ${number} + 接続線として追加しますか？`)) return;

    // 既存丸枠は移動・削除しない。既存エリア紐付けを保護する。
    let target=(nearest && String(nearest.number)===number)?nearest:null;
    if (!target) target=createCandidate(number,markerCenter(shape.points));
    if (!target) {
      host.status.className='status error';
      host.status.textContent='丸枠を作成できませんでした。既存データは変更していません。';
      return;
    }
    if (!createArea(target,shape.points)) {
      host.status.className='status error';
      host.status.textContent=`丸枠 ${number} は確認できましたが、エリア自動作成を確認できませんでした。確定保存はせず内容を確認してください。`;
      return;
    }
    host.setDirty(true);
    host.status.className='status';
    host.status.textContent=target===nearest
      ? `${shape.kind}を補正し、既存丸枠 ${number} に接続しました。既存丸枠位置は変更していません。`
      : `${shape.kind}を補正し、丸枠 ${number} を余白へ自動配置して接続しました。`;
  }

  function setEnabled(value) {
    enabled=Boolean(value); drawing=false; activePointerId=null; stroke=[]; renderStroke();
    if (enabled) {
      host.disableBboxEdit(); host.clearSelection();
      if (areaButton.classList.contains('active')) areaButton.click();
      button.classList.add('active'); button.textContent='✏️ 現場入力 ON'; help.textContent='指/ペンで描く';
      overlay.style.pointerEvents='auto';
      host.status.className='status';
      host.status.textContent='現場入力ON：直線はなぞり、エリアは一周して始点付近まで戻ってください。';
    } else {
      button.classList.remove('active'); button.textContent='✏️ 現場入力'; help.textContent='指/ペンで囲む';
      overlay.style.pointerEvents='none';
      host.status.className='status';
      host.status.textContent='現場入力OFF：従来のOCR・枠編集・エリア作成を利用できます。';
    }
  }

  button.addEventListener('click',()=>{if(!host.isBusy())setEnabled(!enabled);});

  overlay.addEventListener('pointerdown',e=>{
    if(!enabled||host.isBusy()||drawing||(e.pointerType==='mouse'&&e.button!==0))return;
    e.preventDefault();e.stopPropagation();drawing=true;activePointerId=e.pointerId;stroke=[host.point(e)];overlay.setPointerCapture(e.pointerId);renderStroke();
  },{passive:false});

  overlay.addEventListener('pointermove',e=>{
    if(!enabled||!drawing||e.pointerId!==activePointerId)return;
    e.preventDefault();e.stopPropagation();const p=host.point(e),last=stroke[stroke.length-1];
    const min=Math.max(host.cssPxToOcrX(2),host.cssPxToOcrY(2));
    if(!last||distance(last,p)>=min)stroke.push(p);renderStroke();
  },{passive:false});

  function finish(e,cancelled=false){
    if(!drawing||e.pointerId!==activePointerId)return;
    e.preventDefault();e.stopPropagation();if(overlay.hasPointerCapture(e.pointerId))overlay.releasePointerCapture(e.pointerId);
    drawing=false;activePointerId=null;const points=stroke.slice();stroke=[];renderStroke();
    if(cancelled||points.length<2)return;
    const shape=recognize(points);
    if(!shape){host.status.className='status error';host.status.textContent='形を認識できませんでした。直線はまっすぐ、エリアは始点付近まで閉じて描いてください。';return;}
    renderStroke(shape.points);
    requestAnimationFrame(()=>{commitShape(shape);stroke=[];renderStroke();});
  }
  overlay.addEventListener('pointerup',e=>finish(e,false),{passive:false});
  overlay.addEventListener('pointercancel',e=>finish(e,true),{passive:false});

  window.addEventListener('weld:entry-base-drawn',syncOverlay);
  window.addEventListener('weld:entry-zoom-changed',syncOverlay);
  window.addEventListener('resize',syncOverlay);
  if('ResizeObserver'in window)new ResizeObserver(syncOverlay).observe(viewer);

  window.__weldSmartFieldDrawTest={recognize,simplify,rotatedRectangle,lineStrip};
  syncOverlay();
})();
