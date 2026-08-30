(() => {
  const app=document.getElementById('mockApp'); if(!app)return;
  const SCALE=1600/6000;
  const infoUrl=app.dataset.infoUrl,pageUrl=app.dataset.pageUrl,mapUrl=app.dataset.mapUrl,progressUrl=app.dataset.progressUrl,listUrl=app.dataset.listUrl;
  const viewer=document.getElementById('viewer'),sheet=document.getElementById('sheet'),surface=document.getElementById('surface'),img=document.getElementById('drawing'),status=document.getElementById('status');
  const pageInput=document.getElementById('page'),pageTotal=document.getElementById('pageTotal'),prev=document.getElementById('prev'),next=document.getElementById('next');
  const zoomValue=document.getElementById('zoomValue'),rotateButton=document.getElementById('rotate'),records=document.getElementById('records'),listState=document.getElementById('listState'),side=document.getElementById('side'),backdrop=document.getElementById('backdrop');
  const dialog=document.getElementById('mockDialog'),dialogTarget=document.getElementById('dialogTarget'),dialogStatus=document.getElementById('dialogStatus'),dialogDate=document.getElementById('dialogDate'),dialogMemo=document.getElementById('dialogMemo');
  let pageCount=0,currentPage=1,zoom=1,rotation=0,baseW=0,baseH=0,candidates=[],progressMap=new Map(),allItems=[],activeFilter='all',selectedKey='',activeDialogItem=null;
  let highlightTimer=0,loadGeneration=0;
  const keyXY=(x,y)=>`${Math.round(x)}:${Math.round(y)}`;
  const itemKey=item=>`${item.pageNumber}:${item.x}:${item.y}`;
  const center=item=>({x:Math.round(item.bbox.x+item.bbox.w/2),y:Math.round(item.bbox.y+item.bbox.h/2)});
  const statusClass=v=>v==='完了'?'done':v==='施工中'?'working':'';
  function setPager(){prev.disabled=currentPage<=1;next.disabled=currentPage>=pageCount;pageInput.value=currentPage;pageTotal.textContent=`/ ${pageCount||'-'}`}
  function layoutSurface(){
    if(!baseW||!baseH)return;
    const w=baseW*zoom,h=baseH*zoom,sw=(rotation===90||rotation===270)?h:w,sh=(rotation===90||rotation===270)?w:h;
    sheet.style.width=`${sw}px`;sheet.style.height=`${sh}px`;
    surface.style.width=`${w}px`;surface.style.height=`${h}px`;
    surface.style.left=`${(sw-w)/2}px`;surface.style.top=`${(sh-h)/2}px`;
    surface.style.transform=`rotate(${rotation}deg)`;
    surface.querySelectorAll('.marker span').forEach(span=>span.style.transform=`rotate(${-rotation}deg)`);
    zoomValue.textContent=`${Math.round(zoom*100)}%`;rotateButton.textContent=`↻ ${rotation}°`;
  }
  function applyZoom(next){const minZoom=window.innerWidth<=600?.5:1;zoom=Math.max(minZoom,Math.min(3,Math.round(next*4)/4));layoutSurface()}
  function clearFocus(){
    if(highlightTimer){clearTimeout(highlightTimer);highlightTimer=0}
    surface.querySelectorAll('.marker.focused').forEach(m=>m.classList.remove('focused'));
  }
  function clearSelectedTarget(){surface.querySelectorAll('.marker.selected-target').forEach(m=>m.classList.remove('selected-target'))}
  function markerProgress(c){return progressMap.get(keyXY(c.x,c.y))||{status:'未着手',completedDate:'',workDetail:''}}
  function renderMarkers(){
    surface.querySelectorAll('.marker').forEach(el=>el.remove());
    for(const item of candidates){
      const c=center(item),p=markerProgress(c),m=document.createElement('button');
      m.type='button';m.className=`marker ${statusClass(p.status)}`;if(selectedKey===`${currentPage}:${c.x}:${c.y}`)m.classList.add('selected-target');m.dataset.x=String(c.x);m.dataset.y=String(c.y);m.dataset.number=item.number;
      m.style.left=`${(c.x*SCALE/baseW)*100}%`;m.style.top=`${(c.y*SCALE/baseH)*100}%`;
      const label=document.createElement('span');label.textContent=item.number;label.style.display='inline-block';label.style.transform=`rotate(${-rotation}deg)`;m.appendChild(label);
      m.onclick=()=>selectFromDrawing({pageNumber:currentPage,number:item.number,x:c.x,y:c.y,status:p.status||'未着手',completedDate:p.completedDate||'',workDetail:p.workDetail||''});
      surface.appendChild(m);
    }
  }
  function scrollSelectedRecordIntoView(){
    requestAnimationFrame(()=>records.querySelector('.record.selected')?.scrollIntoView({block:'nearest',behavior:'auto'}));
  }
  function selectFromDrawing(item){
    const existing=allItems.find(x=>itemKey(x)===itemKey(item));
    const selected=existing||item;
    selectedKey=itemKey(selected);renderList();scrollSelectedRecordIntoView();openMockInput(selected);
  }
  function openMockInput(item){
    activeDialogItem=item;
    dialogTarget.textContent=`${item.number} / P${item.pageNumber}`;
    dialogStatus.value=item.status||'未着手';dialogDate.value=item.completedDate||'';dialogMemo.value=item.workDetail||'';
    dialog.showModal();
  }
  function loadImage(n,generation){
    return new Promise((resolve,reject)=>{
      const preload=new Image();
      preload.onload=()=>{
        if(generation!==loadGeneration)return resolve(false);
        baseW=preload.naturalWidth;baseH=preload.naturalHeight;img.src=preload.src;layoutSurface();resolve(true);
      };
      preload.onerror=()=>reject(new Error('図面画像を読み込めませんでした。'));
      preload.src=`${pageUrl}?page=${n}&longEdge=1600&format=jpeg&_=${Date.now()}`;
    });
  }
  async function loadPage(n,focus=null){
    const generation=++loadGeneration;
    clearFocus();
    n=Math.max(1,Math.min(pageCount,Number(n)||1));currentPage=n;setPager();status.textContent=`P${n} を読み込んでいます…`;
    try{
      const [mapRes,progRes]=await Promise.all([fetch(`${mapUrl}?page=${n}`,{cache:'no-store'}),fetch(`${progressUrl}?page=${n}`,{cache:'no-store'})]);
      if(generation!==loadGeneration)return;
      const [mapData,progData]=await Promise.all([mapRes.json(),progRes.json()]);
      if(generation!==loadGeneration)return;
      if(!mapRes.ok)throw new Error(mapData.error||'番号配置を取得できませんでした。');if(!progRes.ok)throw new Error(progData.error||'進捗を取得できませんでした。');
      candidates=mapData.candidates||[];progressMap=new Map((progData.items||[]).map(x=>[keyXY(x.x,x.y),x]));
      const latest=await loadImage(n,generation);if(!latest||generation!==loadGeneration)return;
      renderMarkers();status.textContent=`P${n} / 番号 ${candidates.length}件 / 現在 ${Math.round(zoom*100)}% / 回転 ${rotation}°`;
      if(focus)focusTarget(focus);
    }catch(e){if(generation!==loadGeneration)return;status.textContent=e.message;candidates=[];progressMap.clear();surface.querySelectorAll('.marker').forEach(el=>el.remove())}
  }
  function focusTarget(item){
    clearFocus();clearSelectedTarget();selectedKey=itemKey(item);renderList();
    const marker=[...surface.querySelectorAll('.marker')].find(m=>Math.abs(Number(m.dataset.x)-item.x)<2&&Math.abs(Number(m.dataset.y)-item.y)<2);
    if(!marker)return;
    const mr=marker.getBoundingClientRect(),vr=viewer.getBoundingClientRect();
    const targetX=viewer.scrollLeft+(mr.left-vr.left)+mr.width/2,targetY=viewer.scrollTop+(mr.top-vr.top)+mr.height/2;
    viewer.scrollTo({left:Math.max(0,targetX-viewer.clientWidth/2),top:Math.max(0,targetY-viewer.clientHeight/2),behavior:'auto'});
    marker.classList.add('selected-target','focused');
    highlightTimer=setTimeout(()=>{marker.classList.remove('focused');highlightTimer=0},1500);
  }
  function chooseRecord(item){
    clearFocus();selectedKey=itemKey(item);renderList();
    if(item.pageNumber!==currentPage){status.textContent=`P${item.pageNumber} の ${item.number} へ移動中…`;void loadPage(item.pageNumber,item)}
    else focusTarget(item);
    if(window.innerWidth>600)closeDrawer();
  }
  function renderList(){
    const q=document.getElementById('search').value.trim().toLowerCase();
    const filtered=allItems.filter(x=>(activeFilter==='all'||x.status===activeFilter)&&(!q||String(x.number).toLowerCase().includes(q)||String(x.workDetail||'').toLowerCase().includes(q)));
    if(!filtered.length){records.innerHTML='<div class="empty">条件に一致する項目がありません。</div>';return}
    records.innerHTML='';
    for(const item of filtered){
      const row=document.createElement('div');row.className='record';if(selectedKey===itemKey(item))row.classList.add('selected');
      const focus=document.createElement('button');focus.type='button';focus.className='record-focus';focus.innerHTML=`<span class="number"></span><span class="badge ${statusClass(item.status)}"></span><span class="page">P${item.pageNumber}</span><span class="memo"></span>`;
      focus.querySelector('.number').textContent=item.number;focus.querySelector('.badge').textContent=item.status;focus.querySelector('.memo').textContent=item.workDetail||'—';focus.onclick=()=>chooseRecord(item);
      const input=document.createElement('button');input.type='button';input.className='record-input';input.textContent='進捗入力';input.onclick=e=>{e.stopPropagation();openMockInput(item)};
      row.append(focus,input);records.appendChild(row);
    }
  }
  async function loadList(){
    listState.textContent='読込中…';
    try{const r=await fetch(listUrl,{cache:'no-store'}),data=await r.json();if(!r.ok)throw new Error(data.error||'一覧を取得できませんでした。');allItems=data.items||[];listState.textContent=`${allItems.length}件`;renderList()}catch(e){listState.textContent='取得失敗';records.innerHTML=`<div class="empty">${e.message}</div>`}
  }
  function applyMockEdit(){
    if(!activeDialogItem)return;
    const key=itemKey(activeDialogItem),updated={...activeDialogItem,status:dialogStatus.value,completedDate:dialogDate.value,workDetail:dialogMemo.value};
    const index=allItems.findIndex(x=>itemKey(x)===key);if(index>=0)allItems[index]=updated;
    if(updated.pageNumber===currentPage){progressMap.set(keyXY(updated.x,updated.y),updated);renderMarkers()}
    activeDialogItem=updated;selectedKey=key;renderList();dialog.close();status.textContent=`${updated.number} をモック上で「${updated.status}」に変更しました（未保存）`;
  }
  function openDrawer(){
    if(window.innerWidth<=600){app.classList.remove('mobile-side-closed');return}
    side.classList.add('open');backdrop.classList.add('open')
  }
  function closeDrawer(){
    if(window.innerWidth<=600){app.classList.add('mobile-side-closed');return}
    side.classList.remove('open');backdrop.classList.remove('open')
  }
  prev.onclick=()=>void loadPage(currentPage-1);next.onclick=()=>void loadPage(currentPage+1);pageInput.onchange=()=>void loadPage(pageInput.value);
  document.getElementById('zoomOut').onclick=()=>applyZoom(zoom-.25);document.getElementById('zoomIn').onclick=()=>applyZoom(zoom+.25);zoomValue.onclick=()=>applyZoom(1);
  rotateButton.onclick=()=>{clearFocus();rotation=(rotation+90)%360;layoutSurface();viewer.scrollTo({left:0,top:0,behavior:'auto'});status.textContent=`P${currentPage} / 回転 ${rotation}°`};
  document.getElementById('resetView').onclick=()=>{clearFocus();applyZoom(1);viewer.scrollTo({left:0,top:0,behavior:'auto'})};
  document.getElementById('collapseSide').onclick=()=>app.classList.toggle('collapsed');document.getElementById('openSide').onclick=openDrawer;document.getElementById('mobileCloseSide').onclick=closeDrawer;backdrop.onclick=closeDrawer;
  document.getElementById('tabs').onclick=e=>{const b=e.target.closest('[data-filter]');if(!b)return;activeFilter=b.dataset.filter;document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));renderList()};
  document.getElementById('search').oninput=renderList;document.getElementById('clearSearch').onclick=()=>{document.getElementById('search').value='';renderList()};
  document.getElementById('projectSelect').onchange=e=>location.href=`?project=${encodeURIComponent(e.target.value)}`;
  document.getElementById('closeDialog').onclick=()=>dialog.close();document.getElementById('dialogCloseBottom').onclick=()=>dialog.close();document.getElementById('mockSave').onclick=applyMockEdit;
  dialogStatus.onchange=()=>{if(dialogStatus.value==='完了'&&!dialogDate.value)dialogDate.value=new Date().toISOString().slice(0,10)};
  window.addEventListener('resize',()=>{if(innerWidth>900){side.classList.remove('open');backdrop.classList.remove('open')}if(innerWidth>600){app.classList.remove('mobile-side-closed');if(zoom<1)applyZoom(1)}});
  (async()=>{try{const r=await fetch(infoUrl,{cache:'no-store'}),data=await r.json();if(!r.ok)throw new Error(data.error||'PDF情報を取得できませんでした。');pageCount=data.pageCount||1;setPager();await loadPage(1);setTimeout(loadList,0)}catch(e){status.textContent=e.message}})();
})();