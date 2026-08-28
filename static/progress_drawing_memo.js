(() => {
  const baseCanvas = document.getElementById('canvas');
  const viewer = document.getElementById('viewer');
  const launch = document.getElementById('drawingMemoLaunch');
  const tools = document.getElementById('drawingMemoTools');
  const pageInput = document.getElementById('page');
  const pageTotal = document.getElementById('pageTotal');
  const prevButton = document.getElementById('prev');
  const nextButton = document.getElementById('next');
  const statusLine = document.getElementById('status');
  if (!baseCanvas || !viewer || !launch || !tools || !pageInput) return;

  const SCALE = 1600 / 6000;
  const memoUrl = launch.dataset.memoUrl;
  const overlay = document.createElement('canvas');
  overlay.id = 'drawingMemoCanvas';
  overlay.setAttribute('aria-label', '手書きメモ描画レイヤー');
  Object.assign(overlay.style, {
    position: 'absolute', left: '0', top: '0', margin: '0', background: 'transparent',
    pointerEvents: 'none', touchAction: 'none', zIndex: '3'
  });
  viewer.style.position = 'relative';
  viewer.insertBefore(overlay, baseCanvas.nextSibling);

  launch.textContent = '👁';
  launch.setAttribute('aria-label', '手書きメモ表示切替');
  launch.title = '手書きメモ表示切替';
  const editButton = document.createElement('button');
  editButton.type = 'button';
  editButton.id = 'drawingMemoEdit';
  editButton.className = 'button icon-button drawing-memo-edit';
  editButton.textContent = '✎';
  editButton.setAttribute('aria-label', '手書きメモ編集');
  editButton.title = '手書きメモ編集';
  launch.insertAdjacentElement('afterend', editButton);

  const dirtyLabel = document.getElementById('memoDirty');
  const saveButton = document.getElementById('memoSave');
  const undoButton = document.getElementById('memoUndo');
  const redoButton = document.getElementById('memoRedo');
  const clearButton = document.getElementById('memoClear');
  const eraserButton = document.getElementById('memoEraser');
  let displayOn = true;
  let editMode = false;
  let eraserMode = false;
  let color = '#d93025';
  let width = 24;
  let strokes = [];
  let undoStack = [];
  let redoStack = [];
  let dirty = false;
  let saving = false;
  let loadedPage = null;
  let activePointerId = null;
  let activeStroke = null;
  let eraseSnapshotTaken = false;
  let multiTouch = false;
  let pendingTargetPage = null;
  let transitionToken = 0;
  let transitionPage = null;
  let transitionPromise = null;

  const clone = value => JSON.parse(JSON.stringify(value));
  const rotation = () => {
    const match = document.getElementById('rotate')?.textContent?.match(/(0|90|180|270)/);
    return match ? Number(match[1]) : 0;
  };
  const sourceSize = () => {
    const r = rotation();
    return r === 90 || r === 270
      ? { width: baseCanvas.height, height: baseCanvas.width }
      : { width: baseCanvas.width, height: baseCanvas.height };
  };
  const getPageCount = () => {
    const match = pageTotal?.textContent?.match(/(\d+)/);
    return match ? Number(match[1]) : 0;
  };

  function syncOverlaySize() {
    if (!baseCanvas.width || !baseCanvas.height) return;
    if (overlay.width !== baseCanvas.width) overlay.width = baseCanvas.width;
    if (overlay.height !== baseCanvas.height) overlay.height = baseCanvas.height;
    overlay.style.width = baseCanvas.style.width || '100%';
    overlay.style.height = 'auto';
    render();
  }

  function configureContext() {
    const ctx = overlay.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const r = rotation();
    if (r === 90) { ctx.translate(overlay.width, 0); ctx.rotate(Math.PI / 2); }
    else if (r === 180) { ctx.translate(overlay.width, overlay.height); ctx.rotate(Math.PI); }
    else if (r === 270) { ctx.translate(0, overlay.height); ctx.rotate(-Math.PI / 2); }
    return ctx;
  }

  function render() {
    if (!overlay.width || !overlay.height) return;
    const ctx = configureContext();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const stroke of strokes) {
      if (!stroke.points?.length) continue;
      ctx.beginPath();
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = stroke.width * SCALE;
      const first = stroke.points[0];
      ctx.moveTo(first[0] * SCALE, first[1] * SCALE);
      for (let i = 1; i < stroke.points.length; i++) {
        const p = stroke.points[i];
        ctx.lineTo(p[0] * SCALE, p[1] * SCALE);
      }
      if (stroke.points.length === 1) ctx.lineTo(first[0] * SCALE + 0.01, first[1] * SCALE + 0.01);
      ctx.stroke();
    }
  }

  function eventPoint(e) {
    const rect = overlay.getBoundingClientRect();
    const rx = (e.clientX - rect.left) * overlay.width / rect.width;
    const ry = (e.clientY - rect.top) * overlay.height / rect.height;
    const r = rotation();
    const src = sourceSize();
    let x = rx, y = ry;
    if (r === 90) { x = ry; y = src.height - rx; }
    else if (r === 180) { x = src.width - rx; y = src.height - ry; }
    else if (r === 270) { x = src.width - ry; y = rx; }
    return [Math.max(0, x / SCALE), Math.max(0, y / SCALE)];
  }

  function updateUi() {
    launch.classList.toggle('active', displayOn);
    editButton.classList.toggle('active', editMode);
    tools.classList.toggle('open', editMode);
    overlay.style.visibility = displayOn && transitionPage === null ? 'visible' : 'hidden';
    overlay.style.pointerEvents = editMode && displayOn && transitionPage === null ? 'auto' : 'none';
    viewer.classList.toggle('memo-mode', editMode);
    eraserButton.classList.toggle('active', eraserMode);
    undoButton.disabled = !undoStack.length || saving;
    redoButton.disabled = !redoStack.length || saving;
    saveButton.disabled = !dirty || saving;
    dirtyLabel.textContent = saving ? '保存中…' : dirty ? '未保存' : '';
  }

  function setDirty(value = true) { dirty = value; updateUi(); }
  function pushUndo() {
    undoStack.push(clone(strokes));
    if (undoStack.length > 50) undoStack.shift();
    redoStack = [];
  }

  function pointSegmentDistance(p, a, b) {
    const vx = b[0] - a[0], vy = b[1] - a[1], wx = p[0] - a[0], wy = p[1] - a[1];
    const len = vx * vx + vy * vy;
    let t = len ? (wx * vx + wy * vy) / len : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy));
  }

  function eraseAt(point) {
    const tolerance = 38;
    for (let i = strokes.length - 1; i >= 0; i--) {
      const stroke = strokes[i], pts = stroke.points || [];
      let hit = pts.length === 1 && Math.hypot(point[0] - pts[0][0], point[1] - pts[0][1]) <= tolerance + stroke.width / 2;
      for (let j = 1; !hit && j < pts.length; j++) {
        hit = pointSegmentDistance(point, pts[j - 1], pts[j]) <= tolerance + stroke.width / 2;
      }
      if (hit) {
        if (!eraseSnapshotTaken) { pushUndo(); eraseSnapshotTaken = true; }
        strokes.splice(i, 1);
        setDirty();
        render();
        return true;
      }
    }
    return false;
  }

  function cancelActiveStroke() {
    if (!activeStroke) return;
    const idx = strokes.indexOf(activeStroke);
    if (idx >= 0) strokes.splice(idx, 1);
    if (undoStack.length) strokes = undoStack.pop();
    activeStroke = null;
    activePointerId = null;
    redoStack = [];
    render();
    updateUi();
  }

  overlay.addEventListener('touchstart', e => {
    if (!editMode) return;
    if (e.touches.length >= 2) {
      multiTouch = true;
      cancelActiveStroke();
      return;
    }
    e.preventDefault();
    e.stopPropagation();
  }, { passive: false });
  overlay.addEventListener('touchmove', e => {
    if (!editMode || e.touches.length >= 2 || multiTouch) return;
    e.preventDefault(); e.stopPropagation();
  }, { passive: false });
  overlay.addEventListener('touchend', e => {
    if (!editMode) return;
    if (e.touches.length === 0) multiTouch = false;
    if (!multiTouch) { e.preventDefault(); e.stopPropagation(); }
  }, { passive: false });

  overlay.addEventListener('pointerdown', e => {
    if (!editMode || saving || multiTouch || activePointerId !== null || e.button > 0) return;
    e.preventDefault(); e.stopPropagation();
    activePointerId = e.pointerId;
    overlay.setPointerCapture(e.pointerId);
    eraseSnapshotTaken = false;
    const p = eventPoint(e);
    if (eraserMode) { eraseAt(p); return; }
    pushUndo();
    activeStroke = { color, width, points: [p] };
    strokes.push(activeStroke);
    setDirty();
    render();
  });
  overlay.addEventListener('pointermove', e => {
    if (!editMode || e.pointerId !== activePointerId || multiTouch) return;
    e.preventDefault(); e.stopPropagation();
    const p = eventPoint(e);
    if (eraserMode) { eraseAt(p); return; }
    if (!activeStroke) return;
    const last = activeStroke.points[activeStroke.points.length - 1];
    if (Math.hypot(p[0] - last[0], p[1] - last[1]) < 3) return;
    activeStroke.points.push(p);
    render();
  });
  const finishPointer = e => {
    if (e.pointerId !== activePointerId) return;
    e.preventDefault(); e.stopPropagation();
    if (overlay.hasPointerCapture(e.pointerId)) overlay.releasePointerCapture(e.pointerId);
    activePointerId = null;
    activeStroke = null;
    eraseSnapshotTaken = false;
    updateUi();
  };
  overlay.addEventListener('pointerup', finishPointer);
  overlay.addEventListener('pointercancel', finishPointer);

  async function requestEditOff() {
    if (!editMode) return true;
    if (dirty) {
      if (!confirm('手書きメモに未保存の変更があります。保存して編集を終了しますか？')) return false;
      if (!await saveMemo()) return false;
    }
    editMode = false;
    updateUi();
    return true;
  }

  launch.addEventListener('click', async () => {
    if (displayOn) {
      if (!await requestEditOff()) return;
      displayOn = false;
    } else {
      displayOn = true;
    }
    updateUi();
  });
  editButton.addEventListener('click', async () => {
    if (editMode) {
      await requestEditOff();
      return;
    }
    displayOn = true;
    editMode = true;
    updateUi();
  });
  tools.querySelectorAll('[data-memo-color]').forEach(button => button.addEventListener('click', () => {
    color = button.dataset.memoColor;
    eraserMode = false;
    tools.querySelectorAll('[data-memo-color]').forEach(b => b.classList.toggle('active', b === button));
    updateUi();
  }));
  tools.querySelectorAll('[data-memo-width]').forEach(button => button.addEventListener('click', () => {
    width = Number(button.dataset.memoWidth);
    eraserMode = false;
    tools.querySelectorAll('[data-memo-width]').forEach(b => b.classList.toggle('active', b === button));
    updateUi();
  }));
  eraserButton.addEventListener('click', () => { eraserMode = !eraserMode; updateUi(); });
  undoButton.addEventListener('click', () => {
    if (!undoStack.length || saving) return;
    redoStack.push(clone(strokes)); strokes = undoStack.pop(); setDirty(); render();
  });
  redoButton.addEventListener('click', () => {
    if (!redoStack.length || saving) return;
    undoStack.push(clone(strokes)); strokes = redoStack.pop(); setDirty(); render();
  });
  clearButton.addEventListener('click', () => {
    if (!strokes.length || saving || !confirm('このページの手書きメモを全消去しますか？')) return;
    pushUndo(); strokes = []; setDirty(); render();
  });

  async function fetchMemo(page) {
    if (!memoUrl || !page) return { pageNumber: page, strokes: [] };
    const response = await fetch(`${memoUrl}?page=${page}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '手書きメモを取得できませんでした。');
    return data;
  }

  function applyMemoData(page, data) {
    strokes = Array.isArray(data.strokes) ? data.strokes : [];
    undoStack = [];
    redoStack = [];
    dirty = false;
    loadedPage = page;
    render();
    updateUi();
  }

  async function loadMemo(page) {
    const data = await fetchMemo(page);
    applyMemoData(page, data);
  }

  async function saveMemo() {
    if (!dirty || saving) {
      if (!saving) { editMode = false; displayOn = true; updateUi(); }
      return !saving;
    }
    saving = true; updateUi();
    try {
      const response = await fetch(memoUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageNumber: loadedPage || Number(pageInput.value), strokes })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '手書きメモを保存できませんでした。');
      dirty = false;
      editMode = false;
      displayOn = true;
      if (statusLine) statusLine.textContent = `P${data.pageNumber} 手書きメモを保存しました（${data.count}本）`;
      return true;
    } catch (error) {
      alert(error.message);
      return false;
    } finally {
      saving = false;
      updateUi();
    }
  }
  saveButton.addEventListener('click', saveMemo);

  function showMemoLoadError(error) {
    if (statusLine) {
      statusLine.classList.add('error');
      statusLine.textContent = error.message;
    }
  }

  function beginPageTransition(page) {
    if (!page || page === loadedPage) return;
    transitionToken += 1;
    const token = transitionToken;
    transitionPage = page;
    editMode = false;
    activeStroke = null;
    activePointerId = null;
    updateUi();
    transitionPromise = fetchMemo(page)
      .then(data => ({ token, page, data }))
      .catch(error => ({ token, page, error }));
  }

  async function finishPageTransitionIfReady() {
    if (transitionPage === null || pageInput.disabled) return;
    const page = Number(pageInput.value) || 1;
    if (page !== transitionPage || !transitionPromise) return;
    const result = await transitionPromise;
    if (result.token !== transitionToken || result.page !== transitionPage) return;
    if (result.error) {
      transitionPage = null;
      transitionPromise = null;
      strokes = [];
      loadedPage = page;
      render();
      updateUi();
      showMemoLoadError(result.error);
      return;
    }
    applyMemoData(page, result.data);
    transitionPage = null;
    transitionPromise = null;
    updateUi();
  }

  window.__drawingMemoBeforePageChange = async () => {
    if (dirty) {
      if (!confirm('手書きメモに未保存の変更があります。保存してページを移動しますか？')) return false;
      if (!await saveMemo()) return false;
    }
    if (pendingTargetPage && pendingTargetPage !== Number(pageInput.value)) beginPageTransition(pendingTargetPage);
    return true;
  };

  function prepareTargetFromClick(target) {
    const current = Number(pageInput.value) || 1;
    const count = getPageCount();
    if (!target || target === current || target < 1 || (count && target > count)) return false;
    pendingTargetPage = target;
    return true;
  }

  prevButton?.addEventListener('click', e => {
    const current = Number(pageInput.value) || 1;
    if (current <= 1) {
      e.preventDefault();
      e.stopImmediatePropagation();
      pendingTargetPage = null;
      return;
    }
    prepareTargetFromClick(current - 1);
  }, true);
  nextButton?.addEventListener('click', e => {
    const current = Number(pageInput.value) || 1;
    const count = getPageCount();
    if (count && current >= count) {
      e.preventDefault();
      e.stopImmediatePropagation();
      pendingTargetPage = null;
      return;
    }
    prepareTargetFromClick(current + 1);
  }, true);
  document.addEventListener('click', e => {
    const thumb = e.target.closest?.('.progress-thumb[data-page]');
    if (!thumb) return;
    const target = Number(thumb.dataset.page);
    const current = Number(pageInput.value) || 1;
    if (target === current) {
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    prepareTargetFromClick(target);
  }, true);
  pageInput.addEventListener('change', e => {
    const target = Math.max(1, Math.min(getPageCount() || Number(e.target.value) || 1, Number(e.target.value) || 1));
    const currentLoaded = loadedPage || Number(pageInput.value) || 1;
    if (target === currentLoaded) return;
    pendingTargetPage = target;
  }, true);

  window.addEventListener('beforeunload', e => {
    if (!dirty) return;
    e.preventDefault(); e.returnValue = '';
  });

  const canvasObserver = new MutationObserver(() => {
    syncOverlaySize();
    finishPageTransitionIfReady();
  });
  canvasObserver.observe(baseCanvas, { attributes: true, attributeFilter: ['width', 'height', 'style'] });
  new MutationObserver(syncOverlaySize).observe(document.getElementById('rotate'), { childList: true, characterData: true, subtree: true });

  let lastObservedPage = Number(pageInput.value) || 1;
  loadMemo(lastObservedPage).catch(showMemoLoadError);
  setInterval(() => {
    const page = Number(pageInput.value) || 1;
    syncOverlaySize();
    finishPageTransitionIfReady();
    if (page === lastObservedPage) return;
    lastObservedPage = page;
    pendingTargetPage = null;
    if (transitionPage === page) return;
    transitionPage = page;
    updateUi();
    loadMemo(page)
      .then(() => { if (Number(pageInput.value) === page) { transitionPage = null; updateUi(); } })
      .catch(error => { transitionPage = null; updateUi(); showMemoLoadError(error); });
  }, 100);
  syncOverlaySize();
  updateUi();
})();
