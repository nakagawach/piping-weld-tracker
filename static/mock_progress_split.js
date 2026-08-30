(() => {
  const app=document.getElementById('mockApp'); if(!app)return;
  const SCALE=1600/6000;
  const infoUrl=app.dataset.infoUrl,pageUrl=app.dataset.pageUrl,mapUrl=app.dataset.mapUrl,progressUrl=app.dataset.progressUrl,listUrl=app.dataset.listUrl;
  const viewer=document.getElementById('viewer'),sheet=document.getElementById('sheet'),img=document.getElementById('drawing'),status=document.getElementById('status');
  const pageInput=document.getElementById('page'),pageTotal=document.getElementById('pageTotal'),prev=document.getElementById('prev'),next=document.getElementById('next');
  const zoomValue=document.getElementById('zoomValue'),records=document.getElementById('records'),listState=document.getElementById('listState'),side=document.getElementById('side'),backdrop=document.getElementById('backdrop');
  const dialog=document.getElementById('mockDialog'),dialogTarget=document.getElementById('dialogTarget'),dialogStatus=document.getElementById('dialogStatus'),dialogDate=document.getElementById('dialogDate'),dialogMemo=document.getElementById('dialogMemo');
  let pageCount=0,currentPage=1,zoom=1,baseW=0,baseH=0,candidates=[],progressMap=new Map(),allItems=[],activeFilter='all',selectedKey='';
  const keyXY=(x,y)=>`${Math.round(x)}:${Math.round(y)}`;
  const center=item=>({x:Math.round(item.bbox.x+item.bbox.w/2),y:Math.round(item.bbox.y+item.bbox.h/2)});
  const statusClass=v=>v==='完了'?'done':v==='施工中'?'working':'';
  const statusLabel=v=>v==='施工中'?'施工中':v;
  function setPager(){prev.disabled=currentPage<=1;next.disabled=currentPage>=pageCount;pageInput.value=currentPage;pageTotal.textContent=`/ ${pageCount||'-'}`}
  function applyZoom(next){zoom=Math.max(1,Math.min(3,Math.round(next*4)/4));if(baseW&&baseH){sheet.style.width=`${baseW*zoom}px`;sheet.style.height=`${baseH*zoom}px`}zoomValue.textContent=`${Math.round(zoom*100)}%`}
  function markerProgress(c){return progressMap.get(keyXY(c.x,c.y))||{status:'未着手',completedDate:'',workDetail:''}}
  function renderMarkers(){
    sheet.querySelectorAll('.marker').forEach(el=>el.remove());
    for(const item of candidates){const c=center(item),p=markerProgress(c),m=document.createElement('button');m.type='button';m.className=`marker ${statusClass(p.status)}`;m.textContent=item.number;m.dataset.x=String(c.x);m.dataset.y=String(c.y);m.dataset.number=item.number;m.style.left=`${(c.x*SCALE/baseW)*100}%`;m.style.top=`${(c.y*SCALE/baseH)*100}%`;m.onclick=()=>openMockInput(item,p);sheet.appendChild(m)}
  }
  function openMockInput(item,p){const c=center(item);dialogTarget.textContent=`${item.number} / P${currentPage}`;dialogStatus.value=p.status||'未着手';dialogDate.value=p.completedDate||'';dialogMemo.value=p.workDetail||'';dialog.showModal()}
  function loadImage(n){return new Promise((resolve,reject)=>{img.onload=()=>{baseW=img.naturalWidth;baseH=img.naturalHeight;applyZoom(zoom);resolve()};img.onerror=()=>reject(new Error('図面画像を読み込めませんでした。'));img.src=`${pageUrl}?page=${n}&longEdge=1600&format=jpeg&_=${Date.now()}`})}
  async function loadPage(n,focus=null){
    n=Math.max(1,Math.min(pageCount,Number(n)||1));currentPage=n;setPager();status.textContent=`P${n} を読み込んでいます…`;
    try{
      const [mapRes,progRes]=await Promise.all([fetch(`${mapUrl}?page=${n}`,{cache:'no-store'}),fetch(`${progressUrl}?page=${n}`,{cache:'no-store'})]);
      const [mapData,progData]=await Promise.all([mapRes.json(),progRes.json()]);
      if(!mapRes.ok)throw new Error(mapData.error||'番号配置を取得できませんでした。');if(!progRes.ok)throw new Error(progData.error||'進捗を取得できませんでした。');
      candidates=mapData.candidates||[];progressMap=new Map((progData.items||[]).map(x=>[keyXY(x.x,x.y),x]));
      await loadImage(n);renderMarkers();status.textContent=`P${n} / 番号 ${candidates.length}件 / 現在 ${Math.round(zoom*100)}%`;
      if(focus)setTimeout(()=>focusTarget(focus),80);
    }catch(e){status.textContent=e.message;candidates=[];progressMap.clear();sheet.querySelectorAll('.marker').forEach(el=>el.remove())}
  }
  function focusTarget(item){
    selectedKey=`${item.pageNumber}:${item.x}:${item.y}`;renderList();
    const marker=[...sheet.querySelectorAll('.marker')].find(m=>Math.abs(Number(m.dataset.x)-item.x)<2&&Math.abs(Number(m.dataset.y)-item.y)<2);
    if(!marker)return;
    const left=marker.offsetLeft-viewer.clientWidth/2,top=marker.offsetTop-viewer.clientHeight/2;
    viewer.scrollTo({left:Math.max(0,left),top:Math.max(0,top),behavior:'smooth'});
    marker.classList.remove('focused');void marker.offsetWidth;marker.classList.add('focused');setTimeout(()=>marker.classList.remove('focused'),1900);
  }
  async function chooseRecord(item){if(item.pageNumber!==currentPage)await loadPage(item.pageNumber,item);else focusTarget(item);closeDrawer()}
  function renderList(){
    const q=document.getElementById('search').value.trim().toLowerCase();
    const filtered=allItems.filter(x=>(activeFilter==='all'||x.status===activeFilter)&&(!q||String(x.number).toLowerCase().includes(q)||String(x.workDetail||'').toLowerCase().includes(q)));
    if(!filtered.length){records.innerHTML='<div class="empty">条件に一致する項目がありません。</div>';return}
    records.innerHTML='';
    for(const item of filtered){const b=document.createElement('button');b.type='button';b.className='record';if(selectedKey===`${item.pageNumber}:${item.x}:${item.y}`)b.classList.add('selected');b.innerHTML=`<span class="number"></span><span class="badge ${statusClass(item.status)}"></span><span class="page">P${item.pageNumber}</span><span class="memo"></span>`;b.querySelector('.number').textContent=item.number;b.querySelector('.badge').textContent=statusLabel(item.status);b.querySelector('.memo').textContent=item.workDetail||'—';b.onclick=()=>chooseRecord(item);records.appendChild(b)}
  }
  async function loadList(){
    listState.textContent='読込中…';
    try{const r=await fetch(listUrl,{cache:'no-store'}),data=await r.json();if(!r.ok)throw new Error(data.error||'一覧を取得できませんでした。');allItems=data.items||[];listState.textContent=`${allItems.length}件`;renderList()}catch(e){listState.textContent='取得失敗';records.innerHTML=`<div class="empty">${e.message}</div>`}
  }
  function openDrawer(){side.classList.add('open');backdrop.classList.add('open')}
  function closeDrawer(){side.classList.remove('open');backdrop.classList.remove('open')}
  prev.onclick=()=>loadPage(currentPage-1);next.onclick=()=>loadPage(currentPage+1);pageInput.onchange=()=>loadPage(pageInput.value);
  document.getElementById('zoomOut').onclick=()=>applyZoom(zoom-.25);document.getElementById('zoomIn').onclick=()=>applyZoom(zoom+.25);zoomValue.onclick=()=>applyZoom(1);document.getElementById('resetView').onclick=()=>{applyZoom(1);viewer.scrollTo({left:0,top:0,behavior:'smooth'})};
  document.getElementById('collapseSide').onclick=()=>app.classList.toggle('collapsed');document.getElementById('openSide').onclick=openDrawer;backdrop.onclick=closeDrawer;
  document.getElementById('tabs').onclick=e=>{const b=e.target.closest('[data-filter]');if(!b)return;activeFilter=b.dataset.filter;document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));renderList()};
  document.getElementById('search').oninput=renderList;document.getElementById('clearSearch').onclick=()=>{document.getElementById('search').value='';renderList()};
  document.getElementById('projectSelect').onchange=e=>location.href=`?project=${encodeURIComponent(e.target.value)}`;
  document.getElementById('closeDialog').onclick=()=>dialog.close();document.getElementById('dialogCloseBottom').onclick=()=>dialog.close();
  window.addEventListener('resize',()=>{if(innerWidth>900)closeDrawer()});
  (async()=>{try{const r=await fetch(infoUrl,{cache:'no-store'}),data=await r.json();if(!r.ok)throw new Error(data.error||'PDF情報を取得できませんでした。');pageCount=data.pageCount||1;setPager();await loadPage(1);setTimeout(loadList,0)}catch(e){status.textContent=e.message}})();
})();