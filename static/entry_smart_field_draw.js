(() => {
  const host = window.__weldEntryAreaHost;
  const baseCanvas = host?.canvas;
  const viewer = baseCanvas?.closest('.viewer');
  const areaButton = document.getElementById('areaCreate');
  const rotateButton = document.getElementById('rotate');
  if (!host || !baseCanvas || !viewer || !areaButton || !rotateButton) return;
  if (document.getElementById('entrySmartFieldDraw')) return;

  const SCALE = 1600 / 6000;
  let enabled = false;
  let drawing = false;
  let activePointerId = null;
  let stroke = [];
  let markerDrag = null;
  let sessionShapes = [];
  let selectedSessionId = null;
  let nextSessionId = 1;
  let undoStack = [];
  let lastPage = host.currentPage();

  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'entrySmartFieldDraw';
  button.className = 'button';
  button.textContent = '✏️ 現場入力';
  button.title = '指・ペンで描いた線を長方形・正方形へ自動補正';
  areaButton.insertAdjacentElement('afterend', button);

  const undoButton = document.createElement('button');
  undoButton.type = 'button';
  undoButton.id = 'entrySmartUndo';
  undoButton.className = 'button';
  undoButton.textContent = '↶';
  undoButton.title = '直前の現場入力操作を元に戻す';
  undoButton.setAttribute('aria-label', '元に戻す');
  undoButton.disabled = true;
  button.insertAdjacentElement('afterend', undoButton);

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.id = 'entrySmartDelete';
  deleteButton.className = 'button danger';
  deleteButton.textContent = '🗑';
  deleteButton.title = '選択した現場入力エリアを削除';
  deleteButton.setAttribute('aria-label', '選択したエリアを削除');
  deleteButton.disabled = true;
  undoButton.insertAdjacentElement('afterend', deleteButton);

  const help = document.createElement('span');
  help.id = 'entrySmartFieldHelp';
  help.textContent = '指/ペンで描く';
  help.style.cssText = 'font-size:12px;font-weight:600;white-space:nowrap;align-self:center';
  deleteButton.insertAdjacentElement('afterend', help);

  const overlay = document.createElement('canvas');
  overlay.id = 'entrySmartFieldCanvas';
  overlay.setAttribute('aria-label', '現場入力フリーハンドレイヤー');
  overlay.style.cssText = 'position:absolute;z-index:5;pointer-events:none;touch-action:none;background:transparent;max-width:none;margin:0';
  viewer.style.position = 'relative';
  viewer.appendChild(overlay);

  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const centerOf = item => ({x:item.bbox.x + item.bbox.w / 2, y:item.bbox.y + item.bbox.h / 2});
  const cloneBox = box => ({x:box.x,y:box.y,w:box.w,h:box.h});
  const cloneCandidate = item => ({...item,bbox:cloneBox(item.bbox)});
  const cloneShape = shape => ({...shape,points:shape.points.map(p=>({...p}))});

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

  function drawMarkerPreview(ctx, drag) {
    if (!drag) return;
    const item = host.getCandidates().find(x => x.id === drag.itemId);
    if (!item) return;
    const b = item.bbox;
    ctx.save();
    ctx.strokeStyle = '#188038';
    ctx.fillStyle = '#188038';
    ctx.lineWidth = Math.max(3, overlay.width / 620);
    ctx.strokeRect(b.x * SCALE, b.y * SCALE, b.w * SCALE, b.h * SCALE);
    const fontPx = Math.max(14, b.h * SCALE * .8);
    ctx.font = `${fontPx}px system-ui`;
    ctx.fillText(item.number, b.x * SCALE, Math.max(fontPx, b.y * SCALE - 4));
    ctx.restore();
  }

  function drawSelectedShape(ctx) {
    const selected = sessionShapes.find(x => x.id === selectedSessionId);
    if (!selected || selected.points.length < 3) return;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(selected.points[0].x * SCALE, selected.points[0].y * SCALE);
    for (let i=1;i<selected.points.length;i++) ctx.lineTo(selected.points[i].x * SCALE, selected.points[i].y * SCALE);
    ctx.closePath();
    ctx.fillStyle = 'rgba(179,38,30,.08)';
    ctx.strokeStyle = '#b3261e';
    ctx.lineWidth = Math.max(4, overlay.width / 520);
    ctx.setLineDash([10,6]);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function renderStroke(points = stroke) {
    if (!overlay.width || !overlay.height) return;
    const ctx = context();
    drawSelectedShape(ctx);
    drawMarkerPreview(ctx, markerDrag);
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

  function pointInPolygon(point, points) {
    let inside = false;
    for (let i=0,j=points.length-1;i<points.length;j=i++) {
      const xi=points[i].x, yi=points[i].y, xj=points[j].x, yj=points[j].y;
      const intersects=((yi>point.y)!==(yj>point.y))
        && point.x < (xj-xi)*(point.y-yi)/((yj-yi)||1e-9)+xi;
      if (intersects) inside=!inside;
    }
    return inside;
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
    const half=Math.max(host.cssPxToOcrX(6),host.cssPxToOcrY(6));
    const nx=-dy/len*half,ny=dx/len*half;
    return [{x:a.x+nx,y:a.y+ny},{x:b.x+nx,y:b.y+ny},{x:b.x-nx,y:b.y-ny},{x:a.x-nx,y:a.y-ny}];
  }

  function edgeLengths(points) {
    return points.map((p,i)=>distance(p,points[(i+1)%points.length]));
  }

  function recognize(points) {
    if (points.length<2) return null;
    const length=pathLength(points);
    if (!length) return null;
    const direct=distance(points[0],points[points.length-1]);
    if (direct/length>=.88) return {kind:'長方形',points:lineStrip(points[0],points[points.length-1])};
    const rect=rotatedRectangle(points);
    const edges=edgeLengths(rect.points);
    const short=Math.min(...edges),long=Math.max(...edges);
    const minimum=Math.max(host.cssPxToOcrX(20),host.cssPxToOcrY(20));
    if (short<minimum) return {kind:'長方形',points:lineStrip(points[0],points[points.length-1])};
    return {kind:long/short<=1.22?'正方形':'長方形',points:rect.points};
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

  function enableNewMarkerNumber(item) {
    const width=Math.max(host.cssPxToOcrX(14),20);
    const height=Math.max(host.cssPxToOcrY(14),20);
    const gap=Math.max(host.cssPxToOcrX(3),4);
    dispatchClick({x:item.bbox.x+item.bbox.w+gap+width/2,y:item.bbox.y+height/2});
  }

  function createCandidate(number,center) {
    const before=new Set(host.getCandidates().map(x=>x.id));
    withPrompt(number,()=>dispatchClick(center));
    const created=host.getCandidates().find(x=>!before.has(x.id))||null;
    if (created) enableNewMarkerNumber(created);
    return created;
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

  function deleteAreaForShape(shape) {
    const areaCanvas=document.getElementById('entryAreaCanvas');
    if (!shape || !areaCanvas) return false;
    const before=Number(areaCanvas.dataset.areaCount||0);
    if (areaButton.classList.contains('active')) areaButton.click();
    areaButton.click();
    dispatchClick(shapeCenter(shape.points));
    const selected=areaCanvas.dataset.selectedArea;
    if (!selected) {
      if (areaButton.classList.contains('active')) areaButton.click();
      return false;
    }
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}));
    if (areaButton.classList.contains('active')) areaButton.click();
    return Number(areaCanvas.dataset.areaCount||0)<before;
  }

  function nextNumber() {
    const nums=host.getCandidates().map(x=>/^\d+$/.test(String(x.number))?Number(x.number):null).filter(Number.isInteger);
    return nums.length?String(Math.max(...nums)+1):'';
  }

  function updateActionButtons() {
    undoButton.disabled = undoStack.length===0;
    deleteButton.disabled = selectedSessionId===null;
  }

  function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length>30) undoStack.shift();
    updateActionButtons();
  }

  function registerSessionShape(target,shape,createdMarker) {
    const record={
      id:nextSessionId++,
      page:host.currentPage(),
      targetId:target.id,
      number:String(target.number),
      points:shape.points.map(p=>({...p})),
      createdMarker:Boolean(createdMarker),
    };
    sessionShapes.push(record);
    selectedSessionId=record.id;
    updateActionButtons();
    renderStroke();
    return record;
  }

  function removeCandidateById(id) {
    const list=host.getCandidates();
    const index=list.findIndex(x=>x.id===id);
    if(index<0)return null;
    const removed=list[index];
    list.splice(index,1);
    return removed;
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

    let target=(nearest && String(nearest.number)===number)?nearest:null;
    let createdMarker=false;
    if (!target) {
      target=createCandidate(number,markerCenter(shape.points));
      createdMarker=Boolean(target);
    }
    if (!target) {
      host.status.className='status error';
      host.status.textContent='丸枠を作成できませんでした。既存データは変更していません。';
      return;
    }
    if (!createArea(target,shape.points)) {
      if(createdMarker) removeCandidateById(target.id);
      host.status.className='status error';
      host.status.textContent=`丸枠 ${number} は確認できましたが、エリア自動作成を確認できませんでした。確定保存はせず内容を確認してください。`;
      return;
    }
    const session=registerSessionShape(target,shape,createdMarker);
    pushUndo({type:'create',sessionId:session.id});
    host.setDirty(true);
    host.status.className='status';
    host.status.textContent=createdMarker
      ? `${shape.kind}を作成し、丸枠 ${number} を余白へ自動配置しました。エリアをタップすると削除できます。`
      : `${shape.kind}を作成し、既存丸枠 ${number} に接続しました。エリアをタップすると削除できます。`;
  }

  function forceEntryRedraw() {
    const edit=host.bboxEditButton;
    if (!edit || host.isBusy()) return;
    const active=edit.classList.contains('active');
    if (active) { edit.click(); edit.click(); return; }
    edit.click(); edit.click();
  }

  function clampMovedBox(box,dx,dy) {
    const page=pageBounds();
    return {
      ...box,
      x:Math.max(0,Math.min(page.w-box.w,box.x+dx)),
      y:Math.max(0,Math.min(page.h-box.h,box.y+dy)),
    };
  }

  function hitSessionShape(point) {
    for(let i=sessionShapes.length-1;i>=0;i--){
      const shape=sessionShapes[i];
      if(shape.page===host.currentPage()&&pointInPolygon(point,shape.points))return shape;
    }
    return null;
  }

  function selectAt(point) {
    const hit=hitSessionShape(point);
    selectedSessionId=hit?.id??null;
    updateActionButtons();
    renderStroke();
    host.status.className='status';
    host.status.textContent=hit
      ? `現場入力エリア ${hit.number} を選択しました。🗑で削除、↶で直前操作を戻せます。`
      : '現場入力エリアの選択を解除しました。';
    return Boolean(hit);
  }

  function deleteSelectedShape(pushHistory=true) {
    const shape=sessionShapes.find(x=>x.id===selectedSessionId);
    if(!shape)return false;
    const target=host.getCandidates().find(x=>x.id===shape.targetId)||null;
    const markerSnapshot=shape.createdMarker&&target?cloneCandidate(target):null;
    const snapshot=cloneShape(shape);
    if(!deleteAreaForShape(shape)){
      host.status.className='status error';
      host.status.textContent='エリア削除を確認できませんでした。保存は行っていません。';
      return false;
    }
    if(shape.createdMarker&&target) removeCandidateById(target.id);
    sessionShapes=sessionShapes.filter(x=>x.id!==shape.id);
    selectedSessionId=null;
    if(pushHistory)pushUndo({type:'delete',shape:snapshot,marker:markerSnapshot});
    forceEntryRedraw();
    host.setDirty(true);
    updateActionButtons();
    renderStroke();
    host.status.className='status';
    host.status.textContent=shape.createdMarker
      ? `エリア ${shape.number}・接続線・現場入力で作った丸枠を削除しました。💾保存までDBには反映されません。`
      : `エリア ${shape.number} と接続線を削除しました。既存丸枠は残しています。💾保存までDBには反映されません。`;
    return true;
  }

  function undoLast() {
    const action=undoStack.pop();
    if(!action){updateActionButtons();return;}
    if(action.type==='create'){
      const shape=sessionShapes.find(x=>x.id===action.sessionId);
      if(shape){selectedSessionId=shape.id;deleteSelectedShape(false);}
    }else if(action.type==='move'){
      const item=host.getCandidates().find(x=>x.id===action.itemId);
      if(item){item.bbox=cloneBox(action.before);forceEntryRedraw();host.setDirty(true);}
      host.status.className='status';
      host.status.textContent='丸枠移動を元に戻しました。';
    }else if(action.type==='delete'){
      let target=host.getCandidates().find(x=>x.id===action.shape.targetId)||null;
      if(!target&&action.marker){
        target=cloneCandidate(action.marker);
        host.getCandidates().push(target);
        forceEntryRedraw();
        enableNewMarkerNumber(target);
      }
      if(target&&createArea(target,action.shape.points)){
        sessionShapes.push(cloneShape(action.shape));
        selectedSessionId=action.shape.id;
        nextSessionId=Math.max(nextSessionId,action.shape.id+1);
        forceEntryRedraw();
        host.setDirty(true);
        host.status.className='status';
        host.status.textContent='削除した現場入力エリアを元に戻しました。';
      }else{
        host.status.className='status error';
        host.status.textContent='削除の取り消しを完了できませんでした。保存せず内容を確認してください。';
      }
    }
    updateActionButtons();
    renderStroke();
  }

  function setEnabled(value) {
    enabled=Boolean(value); drawing=false; activePointerId=null; stroke=[]; markerDrag=null; selectedSessionId=null; renderStroke();
    if (enabled) {
      host.disableBboxEdit(); host.clearSelection();
      if (areaButton.classList.contains('active')) areaButton.click();
      button.classList.add('active'); button.textContent='✏️ 現場入力 ON'; help.textContent='描く/丸枠移動/タップ選択';
      overlay.style.pointerEvents='auto';
      host.status.className='status';
      host.status.textContent='現場入力ON：線や四角を描く→長方形化。手動丸枠はドラッグ、作成済みエリアはタップして🗑削除できます。';
    } else {
      button.classList.remove('active'); button.textContent='✏️ 現場入力'; help.textContent='指/ペンで描く';
      overlay.style.pointerEvents='none';
      host.status.className='status';
      host.status.textContent='現場入力OFF：従来のOCR・枠編集・エリア作成を利用できます。';
    }
    updateActionButtons();
  }

  button.addEventListener('click',()=>{if(!host.isBusy())setEnabled(!enabled);});
  undoButton.addEventListener('click',()=>{if(!host.isBusy())undoLast();});
  deleteButton.addEventListener('click',()=>{if(!host.isBusy())deleteSelectedShape(true);});

  overlay.addEventListener('pointerdown',e=>{
    if(!enabled||host.isBusy()||drawing||markerDrag||(e.pointerType==='mouse'&&e.button!==0))return;
    e.preventDefault();e.stopPropagation();
    const p=host.point(e);
    const hit=host.findAt(p);
    if(hit?.source==='manual'){
      markerDrag={pointerId:e.pointerId,itemId:hit.id,startPoint:p,startBox:{...hit.bbox},moved:false};
      activePointerId=e.pointerId;
      overlay.setPointerCapture(e.pointerId);
      renderStroke();
      return;
    }
    drawing=true;activePointerId=e.pointerId;stroke=[p];overlay.setPointerCapture(e.pointerId);renderStroke();
  },{passive:false});

  overlay.addEventListener('pointermove',e=>{
    if(!enabled||e.pointerId!==activePointerId)return;
    e.preventDefault();e.stopPropagation();
    if(markerDrag){
      const item=host.getCandidates().find(x=>x.id===markerDrag.itemId);
      if(!item)return;
      const p=host.point(e),dx=p.x-markerDrag.startPoint.x,dy=p.y-markerDrag.startPoint.y;
      item.bbox=clampMovedBox(markerDrag.startBox,dx,dy);
      markerDrag.moved=markerDrag.moved||Math.hypot(dx,dy)>Math.max(host.cssPxToOcrX(2),host.cssPxToOcrY(2));
      renderStroke();
      return;
    }
    if(!drawing)return;
    const p=host.point(e),last=stroke[stroke.length-1];
    const min=Math.max(host.cssPxToOcrX(2),host.cssPxToOcrY(2));
    if(!last||distance(last,p)>=min)stroke.push(p);renderStroke();
  },{passive:false});

  function finishMarkerDrag(e,cancelled=false){
    if(!markerDrag||e.pointerId!==markerDrag.pointerId)return false;
    e.preventDefault();e.stopPropagation();
    if(overlay.hasPointerCapture(e.pointerId))overlay.releasePointerCapture(e.pointerId);
    const item=host.getCandidates().find(x=>x.id===markerDrag.itemId);
    const snapshot=markerDrag;
    const changed=markerDrag.moved&&!cancelled;
    if(cancelled&&item)item.bbox={...markerDrag.startBox};
    markerDrag=null;activePointerId=null;renderStroke();
    forceEntryRedraw();
    if(changed&&item){
      pushUndo({type:'move',itemId:item.id,before:cloneBox(snapshot.startBox)});
      host.setDirty(true);
      host.status.className='status';
      host.status.textContent='丸枠を移動しました。接続線・枠内番号表示も追従します。↶で戻せます。';
    }
    return true;
  }

  function finish(e,cancelled=false){
    if(finishMarkerDrag(e,cancelled))return;
    if(!drawing||e.pointerId!==activePointerId)return;
    e.preventDefault();e.stopPropagation();if(overlay.hasPointerCapture(e.pointerId))overlay.releasePointerCapture(e.pointerId);
    drawing=false;activePointerId=null;const points=stroke.slice();stroke=[];renderStroke();
    if(cancelled)return;
    if(points.length<2||pathLength(points)<Math.max(host.cssPxToOcrX(8),host.cssPxToOcrY(8))){
      if(points.length)selectAt(points[0]);
      return;
    }
    const shape=recognize(points);
    if(!shape){host.status.className='status error';host.status.textContent='形を認識できませんでした。もう少し長く描いてください。';return;}
    selectedSessionId=null;updateActionButtons();
    renderStroke(shape.points);
    requestAnimationFrame(()=>{commitShape(shape);stroke=[];renderStroke();});
  }
  overlay.addEventListener('pointerup',e=>finish(e,false),{passive:false});
  overlay.addEventListener('pointercancel',e=>finish(e,true),{passive:false});

  function placeActionButtons(){
    const mobile=window.matchMedia('(max-width: 820px)').matches;
    for(const el of [undoButton,deleteButton]){
      if(mobile){
        el.style.cssText='width:44px;min-width:44px;min-height:44px;padding:0;border-radius:10px;flex:0 0 auto;font-size:1.05rem';
      }else{
        el.style.removeProperty('width');el.style.removeProperty('min-width');el.style.removeProperty('min-height');el.style.removeProperty('padding');el.style.removeProperty('border-radius');el.style.removeProperty('flex');el.style.removeProperty('font-size');
      }
    }
    if(mobile&&button.parentNode){
      button.insertAdjacentElement('afterend',undoButton);
      undoButton.insertAdjacentElement('afterend',deleteButton);
      if(help)help.style.display='none';
    }else if(help){
      help.style.removeProperty('display');
    }
  }

  window.addEventListener('weld:entry-base-drawn',()=>{
    const page=host.currentPage();
    if(page!==lastPage){
      lastPage=page;sessionShapes=[];selectedSessionId=null;undoStack=[];updateActionButtons();
    }
    syncOverlay();
  });
  window.addEventListener('weld:entry-zoom-changed',syncOverlay);
  window.addEventListener('resize',()=>{syncOverlay();placeActionButtons();});
  if('ResizeObserver'in window)new ResizeObserver(syncOverlay).observe(viewer);

  window.__weldSmartFieldDrawTest={recognize,simplify,rotatedRectangle,lineStrip,edgeLengths,pointInPolygon};
  updateActionButtons();
  syncOverlay();
  setTimeout(placeActionButtons,0);
})();
