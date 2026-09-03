(() => {
  const toggle=document.getElementById('progressListToggle');
  const panel=document.getElementById('progressListPanel');
  const close=document.getElementById('progressListClose');
  const headerToggle=document.getElementById('progressListHeaderToggle');
  const fullscreenButton=document.getElementById('progressListFullscreen');
  const records=document.getElementById('progressListRecords');
  const state=document.getElementById('progressListState');
  const tabs=document.getElementById('progressListTabs');
  const search=document.getElementById('progressListSearch');
  const clear=document.getElementById('progressListSearchClear');
  const pageInput=document.getElementById('page');
  const viewer=document.getElementById('viewer');
  if(!toggle||!panel||!close||!headerToggle||!fullscreenButton||!records||!state||!tabs||!search||!clear||!pageInput||!viewer)return;
  const bottomPaneMedia=window.matchMedia('(max-width:640px), (min-width:641px) and (max-width:1200px) and (orientation:portrait)');
  const listUrl=panel.dataset.listUrl;
  let allItems=[],filter='all',selectedKey='',currentPage=Math.max(1,Number(pageInput.value)||1),loaded=false,loading=false,pendingSelection=null,bottomPaneFrame=0;
  const itemKey=item=>`${item.pageNumber}:${Math.round(item.x)}:${Math.round(item.y)}`;
  const statusClass=status=>status==='完了'?'done':status==='施工中'?'working':'';
  function matchListItem(detail){
    if(!detail)return null;
    const page=Number(detail.pageNumber)||currentPage,x=Number(detail.x),y=Number(detail.y),number=detail.number==null?'':String(detail.number);
    const candidates=allItems.filter(item=>Number(item.pageNumber)===page&&(!number||String(item.number)===number));
    if(Number.isFinite(x)&&Number.isFinite(y)){
      const close=candidates.find(item=>Math.abs(Number(item.x)-x)<=2&&Math.abs(Number(item.y)-y)<=2);
      if(close)return close;
    }
    return candidates.length===1?candidates[0]:null;
  }
  function applySelectionDetail(detail){
    currentPage=Number(detail?.pageNumber)||currentPage;
    const matched=matchListItem(detail);
    selectedKey=matched?itemKey(matched):'';
    if(loaded){render();if(selectedKey)scrollSelected();else scrollCurrentPage()}
  }
  function syncBottomPaneViewer(){
    if(bottomPaneFrame){cancelAnimationFrame(bottomPaneFrame);bottomPaneFrame=0}
    viewer.style.removeProperty('height');
    viewer.style.removeProperty('min-height');
    viewer.style.removeProperty('max-height');
  }
  function syncOpenPosition(){
    if(!loaded)return;
    render();
    requestAnimationFrame(()=>requestAnimationFrame(()=>{if(selectedKey)scrollSelected();else scrollCurrentPage()}));
  }
  const fullscreenStyleProps=['position','left','right','top','bottom','width','height','max-width','max-height','margin','border','border-radius','box-shadow','z-index','grid-column','grid-row','display'];
  function setListFullscreen(on){
    const enabled=!!on&&document.body.classList.contains('progress-list-open');
    document.body.classList.toggle('progress-list-fullscreen',enabled);
    fullscreenButton.setAttribute('aria-pressed',enabled?'true':'false');
    fullscreenButton.setAttribute('aria-label',enabled?'進捗一覧の全画面表示を終了':'進捗一覧を全画面表示');
    fullscreenButton.textContent=enabled?'×':'⛶';
    if(enabled){
      panel.style.setProperty('position','fixed','important');
      panel.style.setProperty('left','0','important');
      panel.style.setProperty('right','0','important');
      panel.style.setProperty('top','0','important');
      panel.style.setProperty('bottom','0','important');
      panel.style.setProperty('width','100vw','important');
      panel.style.setProperty('height','100dvh','important');
      panel.style.setProperty('max-width','none','important');
      panel.style.setProperty('max-height','none','important');
      panel.style.setProperty('margin','0','important');
      panel.style.setProperty('border','0','important');
      panel.style.setProperty('border-radius','0','important');
      panel.style.setProperty('box-shadow','none','important');
      panel.style.setProperty('z-index','500','important');
      panel.style.setProperty('grid-column','1 / -1','important');
      panel.style.setProperty('grid-row','1 / -1','important');
      panel.style.setProperty('display','flex','important');
    }else{
      for(const prop of fullscreenStyleProps)panel.style.removeProperty(prop);
    }
    window.dispatchEvent(new CustomEvent('weld:progress-list-fullscreen-changed',{detail:{fullscreen:enabled}}));
    if(!enabled&&document.body.classList.contains('progress-list-open')){
      requestAnimationFrame(()=>requestAnimationFrame(()=>window.dispatchEvent(new CustomEvent('weld:progress-fit-request'))));
    }
  }
  function setOpen(open){
    if(!open&&document.body.classList.contains('progress-list-fullscreen'))setListFullscreen(false);
    document.body.classList.toggle('progress-list-open',open);
    toggle.classList.toggle('active',open);
    toggle.setAttribute('aria-expanded',open?'true':'false');
    syncBottomPaneViewer();
    window.dispatchEvent(new CustomEvent('weld:progress-list-open-changed',{detail:{open}}));
    if(open){
      if(!loaded)loadList();
      else syncOpenPosition();
      requestAnimationFrame(()=>requestAnimationFrame(()=>window.dispatchEvent(new CustomEvent('weld:progress-fit-request'))));
    }
  }
  function setFiltersExpanded(expanded){
    panel.classList.toggle('filters-collapsed',!expanded);
    headerToggle.textContent=expanded?'∧':'∨';
    headerToggle.setAttribute('aria-expanded',expanded?'true':'false');
    headerToggle.setAttribute('aria-label',expanded?'絞り込みを閉じる':'絞り込みを開く');
  }
  function revealRow(selector){
    requestAnimationFrame(()=>{
      const row=records.querySelector(selector);
      if(!row)return;
      const rr=records.getBoundingClientRect(),er=row.getBoundingClientRect();
      if(er.top>=rr.top&&er.bottom<=rr.bottom)return;
      row.scrollIntoView({block:'nearest',behavior:'auto'});
    });
  }
  function scrollSelected(){revealRow('.progress-list-record.selected')}
  function scrollCurrentPage(){revealRow('.progress-list-record.current-page')}
  function render(){
    const q=search.value.trim().toLowerCase();
    const filtered=allItems.filter(item=>(filter==='all'||item.status===filter)&&(!q||String(item.number).toLowerCase().includes(q)||String(item.workDetail||'').toLowerCase().includes(q)));
    records.innerHTML='';
    if(!filtered.length){records.innerHTML='<div class="progress-list-empty">条件に一致する項目がありません。</div>';return}
    for(const item of filtered){
      const row=document.createElement('div');row.className='progress-list-record';
      if(item.pageNumber===currentPage)row.classList.add('current-page');
      if(selectedKey===itemKey(item))row.classList.add('selected');
      const focus=document.createElement('button');focus.type='button';focus.className='progress-list-focus';
      focus.innerHTML=`<span class="progress-list-number"></span><span class="progress-list-badge ${statusClass(item.status)}"></span><span class="progress-list-page"></span><span class="progress-list-memo"></span>`;
      focus.querySelector('.progress-list-number').textContent=item.number;
      focus.querySelector('.progress-list-badge').textContent=item.status;
      focus.querySelector('.progress-list-page').textContent=`P${item.pageNumber}`;
      focus.querySelector('.progress-list-memo').textContent=item.workDetail||'—';
      focus.onclick=()=>{selectedKey=itemKey(item);render();scrollSelected();window.dispatchEvent(new CustomEvent('weld:progress-panel-target',{detail:{...item,openEditor:false}}))};
      const input=document.createElement('button');input.type='button';input.className='progress-list-input';input.textContent='進捗入力';
      input.onclick=event=>{event.stopPropagation();selectedKey=itemKey(item);render();scrollSelected();window.dispatchEvent(new CustomEvent('weld:progress-panel-target',{detail:{...item,openEditor:true}}))};
      row.append(focus,input);records.appendChild(row);
    }
  }
  async function loadList(){
    if(loading||loaded)return;loading=true;state.textContent='読込中…';
    try{
      const response=await fetch(listUrl,{cache:'no-store'}),data=await response.json();
      if(!response.ok)throw new Error(data.error||'進捗一覧を取得できませんでした。');
      allItems=Array.isArray(data.items)?data.items:[];loaded=true;state.textContent=`${allItems.length}件`;if(pendingSelection){const detail=pendingSelection;pendingSelection=null;applySelectionDetail(detail)}else{render();scrollCurrentPage()};
    }catch(error){state.textContent='取得失敗';records.innerHTML=`<div class="progress-list-empty">${error.message}</div>`}finally{loading=false}
  }
  toggle.setAttribute('aria-expanded','false');
  toggle.onclick=()=>setOpen(!document.body.classList.contains('progress-list-open'));
  close.onclick=()=>setOpen(false);
  fullscreenButton.onclick=()=>setListFullscreen(!document.body.classList.contains('progress-list-fullscreen'));
  headerToggle.onclick=()=>setFiltersExpanded(headerToggle.getAttribute('aria-expanded')!=='true');
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('progress-list-fullscreen')){event.preventDefault();setListFullscreen(false)}});
  tabs.onclick=event=>{const button=event.target.closest('[data-filter]');if(!button)return;filter=button.dataset.filter;tabs.querySelectorAll('[data-filter]').forEach(item=>item.classList.toggle('active',item===button));render()};
  search.oninput=render;clear.onclick=()=>{search.value='';render();search.focus()};
  window.addEventListener('weld:progress-selection',event=>{const detail=event.detail||{};if(!loaded){pendingSelection=detail;currentPage=Number(detail.pageNumber)||currentPage;return}applySelectionDetail(detail)});
  window.addEventListener('weld:progress-page-loaded',event=>{currentPage=Number(event.detail?.page)||Number(pageInput.value)||1;if(selectedKey&&!selectedKey.startsWith(`${currentPage}:`))selectedKey='';if(!loaded)loadList();else{render();if(selectedKey)scrollSelected();else scrollCurrentPage()}if(document.body.classList.contains('progress-list-open'))requestAnimationFrame(()=>window.dispatchEvent(new CustomEvent('weld:progress-fit-request')))});
  window.addEventListener('weld:progress-saved',event=>{const saved=event.detail||{},matched=matchListItem(saved);if(matched){const key=itemKey(matched),index=allItems.findIndex(item=>itemKey(item)===key);if(index>=0)allItems[index]={...allItems[index],...saved};selectedKey=key}else{selectedKey=''}if(loaded){render();if(selectedKey)scrollSelected();else scrollCurrentPage()}});
  window.addEventListener('resize',syncBottomPaneViewer);
  if(bottomPaneMedia.addEventListener)bottomPaneMedia.addEventListener('change',syncBottomPaneViewer);
  new MutationObserver(syncBottomPaneViewer).observe(document.body,{attributes:true,attributeFilter:['class']});
  setFiltersExpanded(false);
  setOpen(true);
  setTimeout(()=>{currentPage=Number(pageInput.value)||1;if(!loaded)loadList();syncBottomPaneViewer()},0);
})();