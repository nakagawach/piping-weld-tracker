(() => {
  const toolbar = document.querySelector('.toolbar');
  const listToggle = document.getElementById('progressListToggle');
  const pageInput = document.getElementById('page');
  const viewer = document.getElementById('viewer');
  const reloadButton = document.getElementById('reload');
  const rotateButton = document.getElementById('rotate');
  if (!toolbar || !listToggle || !pageInput || !viewer || !reloadButton) return;
  if (document.getElementById('progressFieldEntryToggle')) return;

  const style = document.createElement('style');
  style.id = 'progressFieldEntryStyles';
  style.textContent = `
    .progress-field-entry-toggle.active{border-color:#1967d2;background:#e8f0fe;color:#174ea6}
    #progressFieldEntryOverlay{display:none;position:fixed;inset:0;z-index:1000;background:#fff;flex-direction:column}
    body.progress-field-entry-open{overflow:hidden}
    body.progress-field-entry-open #progressFieldEntryOverlay{display:flex}
    .progress-field-entry-head{height:50px;min-height:50px;display:flex;align-items:center;gap:8px;padding:4px 8px;border-bottom:1px solid #dadce0;background:#fff;z-index:2}
    .progress-field-entry-head .button{min-height:40px}
    .progress-field-entry-title{font-weight:900;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .progress-field-entry-page{margin-left:auto;color:#5f6368;font-size:.8rem;font-weight:800;white-space:nowrap}
    #progressFieldEntryFrame{border:0;width:100%;height:100%;min-height:0;flex:1;background:#fff}
    @media(max-width:640px){
      .progress-field-entry-title{font-size:.9rem}
      .progress-field-entry-head{height:48px;min-height:48px;padding:3px 5px;gap:5px}
      .progress-field-entry-head .button{min-height:40px;padding:0 9px}
      #progressFieldEntryToggle{min-width:40px;padding:0 7px}
    }
  `;
  document.head.appendChild(style);

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.id = 'progressFieldEntryToggle';
  toggle.className = 'button icon-button progress-field-entry-toggle';
  toggle.textContent = '🔧';
  toggle.title = '現場エントリーへ切替';
  toggle.setAttribute('aria-label', '現場エントリーへ切替');
  listToggle.insertAdjacentElement('afterend', toggle);

  const overlay = document.createElement('div');
  overlay.id = 'progressFieldEntryOverlay';
  overlay.setAttribute('aria-hidden', 'true');
  overlay.innerHTML = `
    <div class="progress-field-entry-head">
      <button class="button" id="progressFieldEntryBack" type="button">← 進捗入力</button>
      <div class="progress-field-entry-title">🔧 現場エントリー</div>
      <div class="progress-field-entry-page" id="progressFieldEntryPage">P-</div>
    </div>
    <iframe id="progressFieldEntryFrame" title="現場エントリー"></iframe>
  `;
  document.body.appendChild(overlay);

  const frame = document.getElementById('progressFieldEntryFrame');
  const back = document.getElementById('progressFieldEntryBack');
  const pageLabel = document.getElementById('progressFieldEntryPage');
  const smartUrl = window.__progressFieldEntryAssets?.smartUrl;
  const entryUrl = location.pathname.replace(/\/progress\/?$/, '/entry');
  let opening = false;
  let state = null;

  const angleFromText = text => {
    const m = String(text || '').match(/(0|90|180|270)/);
    return m ? Number(m[1]) : 0;
  };
  const waitFor = (test, timeout = 6000, interval = 50) => new Promise((resolve, reject) => {
    const started = Date.now();
    const tick = () => {
      let value = null;
      try { value = test(); } catch (_) {}
      if (value) { resolve(value); return; }
      if (Date.now() - started >= timeout) { reject(new Error('画面準備がタイムアウトしました。')); return; }
      setTimeout(tick, interval);
    };
    tick();
  });

  function childCss(doc) {
    if (doc.getElementById('progressFieldEmbeddedCss')) return;
    const css = doc.createElement('style');
    css.id = 'progressFieldEmbeddedCss';
    css.textContent = `
      body{margin:0!important;background:#fff!important}
      main{max-width:none!important;padding:0!important}
      .top,.note,#thumbs,.summary{display:none!important}
      .card{border:0!important;border-radius:0!important;padding:0!important}
      .controls{position:sticky!important;top:0!important;z-index:30!important;margin:0!important;padding:4px 5px!important;gap:4px!important;flex-wrap:nowrap!important;overflow-x:auto!important;background:#fff!important;border-bottom:1px solid #dadce0!important;align-items:center!important}
      .controls .button{min-height:40px!important;height:40px!important;padding:0 9px!important;white-space:nowrap!important}
      .controls label{display:flex!important;align-items:center!important;gap:3px!important;white-space:nowrap!important;font-size:.8rem!important}
      .controls input[type=number]{min-height:40px!important;height:40px!important;width:48px!important}
      #ocr,#bboxEdit,#reset,#bulkDelete,#back,#areaCreate,#entrySmartFieldHelp{display:none!important}
      #save{order:90!important}
      #entrySmartFieldDraw,#entrySmartUndo,#entrySmartDelete{order:80!important}
      .status{margin:0!important;padding:5px 8px!important;min-height:30px!important;border-bottom:1px solid #eee!important;font-size:.78rem!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
      .viewer{max-height:calc(100dvh - 76px)!important;min-height:calc(100dvh - 76px)!important;border:0!important;border-radius:0!important;background:#e9eaed!important}
      @media(max-width:640px){
        .controls{height:48px!important}
        .controls .button{min-width:40px!important;padding:0 7px!important}
        #entrySmartFieldDraw{font-size:0!important;width:42px!important;min-width:42px!important}
        #entrySmartFieldDraw::after{content:'✏️';font-size:1.05rem!important}
        #save{font-size:0!important;width:42px!important;min-width:42px!important}
        #save::after{content:'💾';font-size:1.05rem!important}
        .viewer{max-height:calc(100dvh - 78px)!important;min-height:calc(100dvh - 78px)!important}
      }
    `;
    doc.head.appendChild(css);
  }

  async function configureFrame(targetPage, targetRotation) {
    const win = frame.contentWindow;
    const doc = win?.document;
    if (!doc) throw new Error('現場エントリー画面を開けませんでした。');
    childCss(doc);

    const childPage = await waitFor(() => {
      const input = doc.getElementById('page');
      const canvas = doc.getElementById('canvas');
      return input && Number(input.max || 0) >= targetPage && canvas?.width ? input : null;
    });
    if (Number(childPage.value) !== targetPage) {
      childPage.value = String(targetPage);
      childPage.dispatchEvent(new Event('change', {bubbles:true}));
      await waitFor(() => Number(doc.getElementById('page')?.value) === targetPage && doc.getElementById('canvas')?.width);
    }

    const childRotate = doc.getElementById('rotate');
    if (childRotate) {
      let guard = 0;
      while (angleFromText(childRotate.textContent) !== targetRotation && guard++ < 4) childRotate.click();
    }

    if (smartUrl && !doc.getElementById('progressEmbeddedSmartScript')) {
      await new Promise((resolve, reject) => {
        const script = doc.createElement('script');
        script.id = 'progressEmbeddedSmartScript';
        script.src = smartUrl;
        script.onload = resolve;
        script.onerror = () => reject(new Error('現場入力ツールを読み込めませんでした。'));
        doc.head.appendChild(script);
      });
    }

    const smartButton = await waitFor(() => doc.getElementById('entrySmartFieldDraw'));
    if (!smartButton.classList.contains('active')) smartButton.click();
    pageLabel.textContent = `P${targetPage}`;
  }

  async function openFieldMode() {
    if (opening || document.body.classList.contains('progress-field-entry-open')) return;
    opening = true;
    const listClose = document.getElementById('progressListClose');
    if (document.body.classList.contains('progress-list-open')) listClose?.click();
    state = {
      page: Math.max(1, Number(pageInput.value) || 1),
      rotation: angleFromText(rotateButton?.textContent),
      scrollLeft: viewer.scrollLeft,
      scrollTop: viewer.scrollTop,
    };
    pageLabel.textContent = `P${state.page}`;
    toggle.classList.add('active');
    document.body.classList.add('progress-field-entry-open');
    overlay.setAttribute('aria-hidden', 'false');
    frame.src = `${entryUrl}?field_embed=1&_=${Date.now()}`;
    try {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('現場エントリー画面を読み込めませんでした。')), 10000);
        frame.onload = () => { clearTimeout(timer); resolve(); };
      });
      await configureFrame(state.page, state.rotation);
    } catch (error) {
      alert(error.message || '現場エントリー画面を開けませんでした。');
      closeFieldMode(false);
    } finally {
      opening = false;
    }
  }

  function restoreViewerAfterReload(saved) {
    const handler = () => {
      window.removeEventListener('weld:progress-page-loaded', handler);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        viewer.scrollLeft = saved.scrollLeft;
        viewer.scrollTop = saved.scrollTop;
      }));
    };
    window.addEventListener('weld:progress-page-loaded', handler);
    setTimeout(() => window.removeEventListener('weld:progress-page-loaded', handler), 5000);
  }

  function closeFieldMode(refresh = true) {
    const doc = frame.contentDocument;
    const pageState = doc?.getElementById('pageState')?.textContent || '';
    if (refresh && /未保存/.test(pageState) && !confirm('現場エントリーに未保存の変更があります。保存せず進捗入力へ戻りますか？')) return;

    const childPage = Math.max(1, Number(doc?.getElementById('page')?.value) || state?.page || Number(pageInput.value) || 1);
    document.body.classList.remove('progress-field-entry-open');
    overlay.setAttribute('aria-hidden', 'true');
    toggle.classList.remove('active');

    if (refresh) {
      const saved = state || {scrollLeft:viewer.scrollLeft, scrollTop:viewer.scrollTop};
      restoreViewerAfterReload(saved);
      if (Number(pageInput.value) !== childPage) {
        pageInput.value = String(childPage);
        pageInput.dispatchEvent(new Event('change', {bubbles:true}));
      } else {
        reloadButton.click();
      }
    }
    setTimeout(() => { frame.src = 'about:blank'; }, 0);
    state = null;
  }

  toggle.addEventListener('click', openFieldMode);
  back.addEventListener('click', () => closeFieldMode(true));
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('progress-field-entry-open')) closeFieldMode(true);
  });
})();
