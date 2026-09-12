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

  const expandIcon='<svg class="panel-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/><path d="M3 8l6-6M21 8l-6-6M3 16l6 6M21 16l-6 6"/></svg>';
  const restoreIcon='<svg class="panel-icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3v6H3M15 3v6h6M9 21v-6H3M15 21v-6h6"/><path d="M9 9L3 3M15 9l6-6M9 15l-6 6M15 15l6 6"/></svg>';
  const MEMO_ROW=48;

  function installUiPolish(){
    const style=document.createElement('style');
    style.id='progressUiPolishStyles';
    style.textContent=`
      .progress-list-panel .panel-head{gap:2px;padding:6px 7px 6px 12px}
      .progress-list-panel .panel-head strong{min-width:0}
      .progress-list-panel .panel-state{margin-right:4px;white-space:nowrap}
      .progress-list-panel .panel-collapse,.progress-list-panel .panel-fullscreen,.progress-list-panel .panel-close{width:40px;min-width:40px;height:40px;min-height:40px;padding:0;border:0;border-radius:999px;background:transparent;display:inline-flex;align-items:center;justify-content:center;color:#3c4043}
      .progress-list-panel .panel-collapse:hover,.progress-list-panel .panel-fullscreen:hover,.progress-list-panel .panel-close:hover{background:#f1f3f4}
      .progress-list-panel .panel-collapse:active,.progress-list-panel .panel-fullscreen:active,.progress-list-panel .panel-close:active{background:#e8eaed}
      .progress-list-panel .panel-close{font-size:1.25rem}
      .progress-list-panel .panel-icon-svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
      body.progress-list-fullscreen .progress-list-panel .panel-head{position:sticky;top:0;z-index:2;background:#fff}
      .drawing-memo-tools{gap:7px!important;padding:3px 8px!important;min-height:${MEMO_ROW}px!important;height:${MEMO_ROW}px!important;align-items:center!important;overflow-y:hidden!important;scrollbar-width:thin;overscroll-behavior-x:contain}
      .drawing-memo-tools>*{flex:0 0 auto}
      .drawing-memo-tools .memo-color{width:36px!important;height:36px!important;min-width:36px!important}
      .drawing-memo-tools .button{min-height:42px!important;height:42px!important}
      .drawing-memo-tools .memo-width{min-width:48px!important;padding:0 12px!important}
      .drawing-memo-tools .memo-eraser{min-width:82px!important;padding:0 13px!important}
      .drawing-memo-tools #memoUndo,.drawing-memo-tools #memoRedo{min-width:46px!important;padding:0 11px!important;font-size:1.12rem}
      .drawing-memo-tools #memoClear{min-width:72px!important;padding:0 12px!important}
      .drawing-memo-tools .memo-save{min-width:86px!important;padding:0 14px!important}
    `;
    document.head.appendChild(style);
    fullscreenButton.innerHTML=expandIcon;
    fullscreenButton.title='進捗一覧を全画面表示';
    close.title='進捗一覧を閉じる';
    headerToggle.title='絞り込みを開く';
    const memoTools=document.getElementById('drawingMemoTools');
    if(memoTools){
      memoTools.setAttribute('aria-label','手書きメモツール（横にスクロールできます）');
      memoTools.querySelectorAll('[data-memo-width]').forEach(button=>button.title=`線の太さ：${button.textContent.trim()}`);
      const eraser=document.getElementById('memoEraser');if(eraser)eraser.title='消しゴム';
      const undo=document.getElementById('memoUndo');if(undo){undo.title='元に戻す';undo.setAttribute('aria-label','元に戻す')}
      const redo=document.getElementById('memoRedo');if(redo){redo.title='やり直す';redo.setAttribute('aria-label','やり直す')}
      const memoClear=document.getElementById('memoClear');if(memoClear)memoClear.title='このページの手書きメモを全消去';
    }
  }
  installUiPolish();

  const card=document.querySelector('.card');
  const memoTools=document.getElementById('drawingMemoTools');
  const summary=document.querySelector('.summary');
  const thumbs=document.querySelector('.progress-thumbs');
  const toolbar=document.querySelector('.toolbar');
  const appbar=document.querySelector('.ui3-appbar');
  const splitter=document.getElementById('progressSplitter');
  const portraitMedia=window.matchMedia('(orientation: portrait)');
  let memoFrame=0,memoFitFrame=0,memoWasOpen=false,memoSnapshot=null;
  const important=(el,prop,value)=>{if(!el)return;if(value===null)el.style.removeProperty(prop);else if(el.style.getPropertyValue(prop)!==value||el.style.getPropertyPriority(prop)!=='important')el.style.setProperty(prop,value,'important')};
  const minPanel=p=>p?(window.innerWidth<=520?170:190):(window.innerWidth>=1201?340:window.innerWidth>=821?312:280);
  const snapshotTargets=()=>[
    [card,['grid-template-rows','--pw-bottom-viewer','--pw-panel']],
    [appbar,['grid-row']],[toolbar,['grid-row']],[memoTools,['grid-column','grid-row']],
    [summary,['grid-row']],[thumbs,['grid-row']],[viewer,['grid-row']],[panel,['grid-row']],[splitter,['display']]
  ];
  function captureMemoSnapshot(){
    if(memoSnapshot)return;
    memoSnapshot=snapshotTargets().map(([el,props])=>[el,props.map(prop=>[prop,el?.style.getPropertyValue(prop)||'',el?.style.getPropertyPriority(prop)||''])]);
  }
  function restoreMemoSnapshot(){
    if(!memoSnapshot)return;
    for(const [el,props] of memoSnapshot){
      if(!el)continue;
      for(const [prop,value,priority] of props){if(value)el.style.setProperty(prop,value,priority);else el.style.removeProperty(prop)}
    }
    memoSnapshot=null;
  }

  function memoGridSpec(){
    if(!card||!memoTools||!memoTools.classList.contains('open')||document.body.classList.contains('progress-list-fullscreen'))return null;
    const p=portraitMedia.matches,full=document.body.classList.contains('progress-fullscreen'),listOpen=document.body.classList.contains('progress-list-open'),w=window.innerWidth;
    if(listOpen&&p){
      if(w<=1200)return {rows:full?`0 var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) 0 var(--pw-bottom-viewer) minmax(0,1fr)`:`${w<=820?'var(--pw-header)':'44px'} var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) var(--pw-thumbs) var(--pw-bottom-viewer) minmax(0,1fr)`,app:1,tb:2,memo:3,sm:4,th:5,v:6,panel:7,portrait:true};
      return {rows:`var(--pw-thumbs) ${MEMO_ROW}px var(--pw-summary) var(--pw-bottom-viewer) minmax(0,1fr)`,th:1,memo:2,sm:3,v:4,panel:5,portrait:true};
    }
    if(listOpen&&!p){
      if(w<=820)return {rows:full?`var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) 0 minmax(0,1fr)`:`var(--pw-header) var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) var(--pw-thumbs) minmax(0,1fr)`,app:full?null:1,tb:full?1:2,memo:full?2:3,sm:full?3:4,th:full?4:5,v:full?5:6,panel:'1 / -1',portrait:false};
      if(w<=1200)return {rows:full?`var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) 0 minmax(0,1fr)`:`var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) var(--pw-thumbs) minmax(0,1fr)`,tb:1,memo:2,sm:3,th:4,v:5,panel:'1 / -1',portrait:false};
      return {rows:full?`0 ${MEMO_ROW}px var(--pw-summary) minmax(0,1fr)`:`var(--pw-thumbs) ${MEMO_ROW}px var(--pw-summary) minmax(0,1fr)`,th:1,memo:2,sm:3,v:4,panel:'2 / 5',portrait:false};
    }
    if(!listOpen&&full&&!p&&w<=1200)return {rows:`var(--pw-toolbar) ${MEMO_ROW}px var(--pw-summary) 0 minmax(0,1fr)`,tb:1,memo:2,sm:3,th:4,v:5,panel:null,portrait:false,closed:true};
    return null;
  }

  function applyMemoFit(spec){
    if(memoFitFrame)cancelAnimationFrame(memoFitFrame);
    memoFitFrame=requestAnimationFrame(()=>{
      memoFitFrame=0;
      const fitState=window.__progressFitState;
      if(!fitState||!viewer.clientWidth||!viewer.clientHeight)return;
      const canvas=document.getElementById('canvas');
      if(!canvas||!canvas.width||!canvas.height)return;
      const ratio=canvas.height/canvas.width,z=Math.max(1,Number(fitState.getZoom?.())||1);
      if(document.body.classList.contains('progress-list-open')&&spec.portrait){
        const mp=minPanel(true),available=Math.max(1,viewer.clientHeight+panel.clientHeight),maxViewer=Math.max(1,available-mp),base=Math.max(1,Math.min(viewer.clientWidth,maxViewer/ratio)),height=Math.min(maxViewer,base*ratio*z);
        card.style.setProperty('--pw-bottom-viewer',Math.round(height)+'px');
        fitState.setFitBaseWidth(base);
      }else if(document.body.classList.contains('progress-list-open')&&!spec.portrait){
        const mp=minPanel(false),cw=Math.max(1,card.clientWidth),maxViewer=Math.max(1,cw-mp),base=Math.max(1,Math.min(maxViewer,viewer.clientHeight/ratio)),viewerWidth=Math.min(maxViewer,base*z),panelWidth=Math.max(mp,cw-viewerWidth);
        card.style.setProperty('--pw-panel',Math.round(panelWidth)+'px');
        fitState.setFitBaseWidth(base);
      }else{
        const base=Math.max(1,Math.min(viewer.clientWidth,viewer.clientHeight/ratio));
        fitState.setFitBaseWidth(base);
      }
    });
  }
  function applyMemoGrid(){
    memoFrame=0;
    if(!card||!memoTools)return;
    const isOpen=memoTools.classList.contains('open');
    if(!isOpen){
      if(memoFitFrame){cancelAnimationFrame(memoFitFrame);memoFitFrame=0}
      restoreMemoSnapshot();
      if(memoWasOpen)window.dispatchEvent(new CustomEvent('weld:progress-layout-request'));
      memoWasOpen=false;
      return;
    }
    captureMemoSnapshot();
    memoWasOpen=true;
    const spec=memoGridSpec();
    if(!spec)return;
    important(card,'grid-template-rows',spec.rows);
    if(spec.app!=null)important(appbar,'grid-row',String(spec.app));
    if(spec.tb!=null)important(toolbar,'grid-row',String(spec.tb));
    important(memoTools,'grid-column','1');important(memoTools,'grid-row',String(spec.memo));
    if(spec.sm!=null)important(summary,'grid-row',String(spec.sm));
    if(spec.th!=null)important(thumbs,'grid-row',String(spec.th));
    if(spec.v!=null)important(viewer,'grid-row',String(spec.v));
    if(spec.panel!=null)important(panel,'grid-row',String(spec.panel));
    important(splitter,'display','none');
    applyMemoFit(spec);
  }
  function scheduleMemoGrid(){if(memoFrame)cancelAnimationFrame(memoFrame);memoFrame=requestAnimationFrame(applyMemoGrid)}
  if(card&&memoTools){
    document.addEventListener('click',event=>{if(event.target.closest?.('#drawingMemoEdit')&&!memoTools.classList.contains('open'))captureMemoSnapshot()},true);
    document.addEventListener('click',event=>{if(event.target.closest?.('#drawingMemoEdit'))applyMemoGrid()});
    new MutationObserver(scheduleMemoGrid).observe(memoTools,{attributes:true,attributeFilter:['class']});
    new MutationObserver(()=>{if(memoTools.classList.contains('open'))scheduleMemoGrid()}).observe(card,{attributes:true,attributeFilter:['style']});
    new MutationObserver(scheduleMemoGrid).observe(document.body,{attributes:true,attributeFilter:['class']});
    window.addEventListener('resize',scheduleMemoGrid);
    portraitMedia.addEventListener?.('change',scheduleMemoGrid);
  }

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
    fullscreenButton.setAttribute('aria-label',enabled?'進捗一覧を元のサイズに戻す':'進捗一覧を全画面表示');
    fullscreenButton.title=enabled?'進捗一覧を元のサイズに戻す':'進捗一覧を全画面表示';
    fullscreenButton.innerHTML=enabled?restoreIcon:expandIcon;
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
    headerToggle.title=expanded?'絞り込みを閉じる':'絞り込みを開く';
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