(() => {
  const toggle=document.getElementById('progressListToggle');
  const panel=document.getElementById('progressListPanel');
  const close=document.getElementById('progressListClose');
  const records=document.getElementById('progressListRecords');
  const state=document.getElementById('progressListState');
  const tabs=document.getElementById('progressListTabs');
  const search=document.getElementById('progressListSearch');
  const clear=document.getElementById('progressListSearchClear');
  const pageInput=document.getElementById('page');
  if(!toggle||!panel||!records||!state||!tabs||!search||!clear||!pageInput)return;
  const listUrl=panel.dataset.listUrl;
  let allItems=[],filter='all',selectedKey='',currentPage=Math.max(1,Number(pageInput.value)||1),loaded=false,loading=false;
  const itemKey=item=>`${item.pageNumber}:${Math.round(item.x)}:${Math.round(item.y)}`;
  const statusClass=status=>status==='完了'?'done':status==='施工中'?'working':'';
  function setOpen(open){
    document.body.classList.toggle('progress-list-open',open);
    toggle.classList.toggle('active',open);
    toggle.setAttribute('aria-expanded',open?'true':'false');
    if(open&&!loaded)loadList();
  }
  function scrollSelected(){requestAnimationFrame(()=>records.querySelector('.progress-list-record.selected')?.scrollIntoView({block:'nearest',behavior:'auto'}))}
  function scrollCurrentPage(){requestAnimationFrame(()=>records.querySelector('.progress-list-record.current-page')?.scrollIntoView({block:'nearest',behavior:'auto'}))}
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
      allItems=Array.isArray(data.items)?data.items:[];loaded=true;state.textContent=`${allItems.length}件`;render();scrollCurrentPage();
    }catch(error){state.textContent='取得失敗';records.innerHTML=`<div class="progress-list-empty">${error.message}</div>`}finally{loading=false}
  }
  toggle.setAttribute('aria-expanded','false');
  toggle.onclick=()=>setOpen(!document.body.classList.contains('progress-list-open'));
  close.onclick=()=>setOpen(false);
  tabs.onclick=event=>{const button=event.target.closest('[data-filter]');if(!button)return;filter=button.dataset.filter;tabs.querySelectorAll('[data-filter]').forEach(item=>item.classList.toggle('active',item===button));render()};
  search.oninput=render;clear.onclick=()=>{search.value='';render();search.focus()};
  window.addEventListener('weld:progress-selection',event=>{const detail=event.detail||{};selectedKey=`${Number(detail.pageNumber)||currentPage}:${Math.round(Number(detail.x))}:${Math.round(Number(detail.y))}`;currentPage=Number(detail.pageNumber)||currentPage;if(loaded){render();scrollSelected()}});
  window.addEventListener('weld:progress-page-loaded',event=>{currentPage=Number(event.detail?.page)||Number(pageInput.value)||1;if(selectedKey&&!selectedKey.startsWith(`${currentPage}:`))selectedKey='';if(!loaded)loadList();else{render();scrollCurrentPage()}});
  window.addEventListener('weld:progress-saved',event=>{const saved=event.detail||{},key=itemKey(saved),index=allItems.findIndex(item=>itemKey(item)===key);if(index>=0)allItems[index]={...allItems[index],...saved};selectedKey=key;if(loaded){render();scrollSelected()}});
  setTimeout(()=>{currentPage=Number(pageInput.value)||1;if(!loaded)loadList()},0);
})();