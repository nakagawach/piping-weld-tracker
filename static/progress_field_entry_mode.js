(() => {
  const toolbar=document.querySelector('.toolbar');
  const listToggle=document.getElementById('progressListToggle');
  const pageInput=document.getElementById('page');
  const viewer=document.getElementById('viewer');
  const reloadButton=document.getElementById('reload');
  const rotateButton=document.getElementById('rotate');
  if(!toolbar||!listToggle||!pageInput||!viewer||!reloadButton)return;
  if(document.getElementById('progressFieldEntryToggle'))return;

  const style=document.createElement('style');
  style.id='progressFieldEntryStyles';
  style.textContent=`
    .progress-field-entry-toggle.active{border-color:#1967d2!important;background:#e8f0fe!important;color:#174ea6!important}
    #progressFieldEntryOverlay{display:none;position:fixed;inset:0;z-index:1000;background:#fff}
    body.progress-field-entry-open{overflow:hidden!important}
    body.progress-field-entry-open #progressFieldEntryOverlay{display:block}
    #progressFieldEntryFrame{display:block;border:0;width:100%;height:100dvh;background:#fff}
    @media(max-width:820px){#progressFieldEntryToggle{width:44px!important;min-width:44px!important;height:44px!important;padding:0!important}}
  `;
  document.head.appendChild(style);

  const toggle=document.createElement('button');
  toggle.type='button';toggle.id='progressFieldEntryToggle';toggle.className='button icon-button progress-field-entry-toggle';toggle.textContent='🔧';toggle.title='現場エントリーへ切替';toggle.setAttribute('aria-label','現場エントリーへ切替');
  listToggle.insertAdjacentElement('afterend',toggle);

  const overlay=document.createElement('div');
  overlay.id='progressFieldEntryOverlay';overlay.setAttribute('aria-hidden','true');
  overlay.innerHTML='<iframe id="progressFieldEntryFrame" title="現場エントリー"></iframe>';
  document.body.appendChild(overlay);
  const frame=document.getElementById('progressFieldEntryFrame');
  const entryUrl=location.pathname.replace(/\/progress\/?$/,'/entry');
  let opening=false,state=null;

  const angleFromText=text=>{const m=String(text||'').match(/(0|90|180|270)/);return m?Number(m[1]):0};
  const waitFor=(test,timeout=8000,interval=50)=>new Promise((resolve,reject)=>{const started=Date.now();const tick=()=>{let v=null;try{v=test()}catch(_){ }if(v){resolve(v);return}if(Date.now()-started>=timeout){reject(new Error('現場エントリー画面の準備がタイムアウトしました。'));return}setTimeout(tick,interval)};tick()});

  function installEmbeddedUi(doc){
    if(doc.getElementById('progressFieldEmbeddedCss'))return;
    const css=doc.createElement('style');css.id='progressFieldEmbeddedCss';css.textContent=`
      html,body{margin:0!important;width:100%!important;height:100%!important;background:#fff!important;overflow:hidden!important}
      body.ui3-entry{--ui3-header:0px!important}
      body.ui3-entry .ui3-appbar,body.ui3-entry main>.top,.note,#thumbs,.summary{display:none!important}
      main{max-width:none!important;height:100dvh!important;padding:0!important;display:flex!important;flex-direction:column!important}
      .card{border:0!important;border-radius:0!important;padding:0!important;display:flex!important;flex:1!important;min-height:0!important;flex-direction:column!important}
      .controls{position:relative!important;top:0!important;z-index:90!important;margin:0!important;min-height:48px!important;height:48px!important;padding:3px 5px!important;gap:4px!important;flex:0 0 48px!important;flex-wrap:nowrap!important;overflow-x:auto!important;background:#fff!important;border-bottom:1px solid #dadce0!important;align-items:center!important;scrollbar-width:none!important}
      .controls::-webkit-scrollbar{display:none!important}
      .controls .button{min-height:40px!important;height:40px!important;padding:0 8px!important;white-space:nowrap!important}
      .controls label{display:flex!important;align-items:center!important;gap:3px!important;white-space:nowrap!important;font-size:.8rem!important}
      .controls input[type=number]{min-height:40px!important;height:40px!important;width:46px!important}
      #progressEmbeddedBack{order:-100!important;border-color:#1967d2!important;color:#174ea6!important;background:#e8f0fe!important}
      #ocr,#bboxEdit,#reset,#bulkDelete,#back,#areaCreate,#entrySmartFieldHelp,.ui3-entry-more{display:none!important}
      #entrySmartFieldDraw,#entrySmartUndo,#entrySmartDelete{order:70!important}
      #save{order:90!important}
      .status{margin:0!important;padding:4px 8px!important;min-height:28px!important;flex:0 0 28px!important;border-bottom:1px solid #eee!important;font-size:.76rem!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
      .viewer{flex:1!important;min-height:0!important;max-height:none!important;border:0!important;border-radius:0!important;background:#e9eaed!important}
      #entrySmartFieldCanvas{z-index:5!important}
      @media(max-width:640px){
        #progressEmbeddedBack{width:44px!important;min-width:44px!important;padding:0!important;font-size:0!important}#progressEmbeddedBack::before{content:'←';font-size:1.15rem!important}
        #entrySmartFieldDraw,#entrySmartUndo,#entrySmartDelete,#save{width:42px!important;min-width:42px!important;padding:0!important;flex:0 0 42px!important}
        #entrySmartFieldDraw{font-size:0!important}#entrySmartFieldDraw::after{content:'✏️';font-size:1.05rem!important}
        #save{font-size:0!important}#save::after{content:'💾';font-size:1.05rem!important}
      }
    `;doc.head.appendChild(css);
    doc.body.classList.add('progress-field-embedded');
    const controls=doc.querySelector('.controls');
    if(controls&&!doc.getElementById('progressEmbeddedBack')){
      const back=doc.createElement('button');back.type='button';back.id='progressEmbeddedBack';back.className='button';back.textContent='← 進捗入力';back.title='進捗入力へ戻る';back.addEventListener('click',()=>window.parent.__closeProgressFieldEntry?.(true));controls.prepend(back);
    }
  }

  async function configureFrame(targetPage,targetRotation){
    const win=frame.contentWindow,doc=win?.document;if(!doc)throw new Error('現場エントリー画面を開けませんでした。');
    await waitFor(()=>doc.body&&doc.querySelector('.controls'));
    installEmbeddedUi(doc);
    const childPage=await waitFor(()=>{const input=doc.getElementById('page'),canvas=doc.getElementById('canvas');return input&&Number(input.max||0)>=targetPage&&canvas?.width?input:null});
    if(Number(childPage.value)!==targetPage){childPage.value=String(targetPage);childPage.dispatchEvent(new Event('change',{bubbles:true}));await waitFor(()=>Number(doc.getElementById('page')?.value)===targetPage&&doc.getElementById('canvas')?.width)}
    const childRotate=doc.getElementById('rotate');if(childRotate){let guard=0;while(angleFromText(childRotate.textContent)!==targetRotation&&guard++<4)childRotate.click()}
    const smart=await waitFor(()=>{const b=doc.getElementById('entrySmartFieldDraw'),h=win.__weldEntryAreaHost;return b&&h&&!h.isBusy()?b:null});
    if(!smart.classList.contains('active'))smart.click();
    await waitFor(()=>smart.classList.contains('active')?smart:null,3000,30);
    installEmbeddedUi(doc);
  }

  async function openFieldMode(){
    if(opening||document.body.classList.contains('progress-field-entry-open'))return;opening=true;
    if(document.body.classList.contains('progress-list-open'))document.getElementById('progressListClose')?.click();
    state={page:Math.max(1,Number(pageInput.value)||1),rotation:angleFromText(rotateButton?.textContent),scrollLeft:viewer.scrollLeft,scrollTop:viewer.scrollTop};
    toggle.classList.add('active');document.body.classList.add('progress-field-entry-open');overlay.setAttribute('aria-hidden','false');
    frame.src=`${entryUrl}?field_embed=1&_=${Date.now()}`;
    try{await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('現場エントリー画面を読み込めませんでした。')),12000);frame.onload=()=>{clearTimeout(timer);resolve()}});await configureFrame(state.page,state.rotation)}catch(error){alert(error.message||'現場エントリー画面を開けませんでした。');closeFieldMode(false)}finally{opening=false}
  }

  function restoreScroll(saved){const handler=()=>{window.removeEventListener('weld:progress-page-loaded',handler);requestAnimationFrame(()=>requestAnimationFrame(()=>{viewer.scrollLeft=saved.scrollLeft;viewer.scrollTop=saved.scrollTop}))};window.addEventListener('weld:progress-page-loaded',handler);setTimeout(()=>window.removeEventListener('weld:progress-page-loaded',handler),5000)}
  function closeFieldMode(refresh=true){
    if(!document.body.classList.contains('progress-field-entry-open'))return;
    const doc=frame.contentDocument,pageState=doc?.getElementById('pageState')?.textContent||'';
    if(refresh&&/未保存/.test(pageState)&&!confirm('現場エントリーに未保存の変更があります。保存せず進捗入力へ戻りますか？'))return;
    const childPage=Math.max(1,Number(doc?.getElementById('page')?.value)||state?.page||Number(pageInput.value)||1);
    document.body.classList.remove('progress-field-entry-open');overlay.setAttribute('aria-hidden','true');toggle.classList.remove('active');
    if(refresh){const saved=state||{scrollLeft:viewer.scrollLeft,scrollTop:viewer.scrollTop};restoreScroll(saved);if(Number(pageInput.value)!==childPage){pageInput.value=String(childPage);pageInput.dispatchEvent(new Event('change',{bubbles:true}))}else reloadButton.click()}
    frame.onload=null;frame.src='about:blank';state=null;
  }

  window.__closeProgressFieldEntry=closeFieldMode;
  toggle.addEventListener('click',openFieldMode);
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('progress-field-entry-open'))closeFieldMode(true)});
})();
