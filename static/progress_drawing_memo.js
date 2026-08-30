(() => {
  const baseCanvas = document.getElementById('canvas');
  const viewer = document.getElementById('viewer');
  const launch = document.getElementById('drawingMemoLaunch');
  const tools = document.getElementById('drawingMemoTools');
  const pageInput = document.getElementById('page');
  const rotateButton = document.getElementById('rotate');
  const statusLine = document.getElementById('status');
  if (!baseCanvas || !viewer || !launch || !tools || !pageInput) return;

  const SCALE = 1600 / 6000;
  const memoUrl = launch.dataset.memoUrl;
  const overlay = document.createElement('canvas');
  overlay.id = 'drawingMemoCanvas';
  overlay.setAttribute('aria-label', '手書きメモ描画レイヤー');
  overlay.style.pointerEvents = 'none';
  overlay.style.touchAction = 'none';
  overlay.style.visibility = 'visible';
  viewer.style.position = 'relative';
  viewer.insertBefore(overlay, baseCanvas.nextSibling);

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
  let transitioning = false;
  let activePointerId = null;
  let activeStroke = null;
  let eraseSnapshotTaken = false;
  let multiTouch = false;
  let loadToken = 0;

  const clone = value => JSON.parse(JSON.stringify(value));

  function rotation() {
    const match = rotateButton?.textContent?.match(/(0|90|180|270)/);
    return match ? Number(match[1]) : 0;
  }

  function sourceSize() {
    const r = rotation();
    return r === 90 || r === 270
      ? { width: baseCanvas.height, height: baseCanvas.width }
      : { width: baseCanvas.width, height: baseCanvas.height };
  }

  function syncOverlaySize() {
    if (!baseCanvas.width || !baseCanvas.height) return;
    if (overlay.width !== baseCanvas.width) overlay.width = baseCanvas.width;
    if (overlay.height !== baseCanvas.height) overlay.height = baseCanvas.height;
    overlay.style.width = baseCanvas.style.width || '100%';
    overlay.style.height = 'auto';
    overlay.style.left = `${baseCanvas.offsetLeft}px`;
    overlay.style.top = `${baseCanvas.offsetTop}px`;
    render();
  }

  function configureContext() {
    const ctx = overlay.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const r = rotation();
    if (r === 90) {
      ctx.translate(overlay.width, 0);
      ctx.rotate(Math.PI / 2);
    } else if (r === 180) {
      ctx.translate(overlay.width, overlay.height);
      ctx.rotate(Math.PI);
    } else if (r === 270) {
      ctx.translate(0, overlay.height);
      ctx.rotate(-Math.PI / 2);
    }
    return ctx;
  }

  function render() {
    if (!overlay.width || !overlay.height) return;
    const ctx = configureContext();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const stroke of strokes) {
      if (!Array.isArray(stroke.points) || !stroke.points.length) continue;
      ctx.beginPath();
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = stroke.width * SCALE;
      const first = stroke.points[0];
      ctx.moveTo(first[0] * SCALE, first[1] * SCALE);
      for (let i = 1; i < stroke.points.length; i++) {
        const p = stroke.points[i];
        ctx.lineTo(p[0] * SCALE, p[1] * SCALE);
      }
      if (stroke.points.length === 1) {
        ctx.lineTo(first[0] * SCALE + 0.01, first[1] * SCALE + 0.01);
      }
      ctx.stroke();
    }
    overlay.dataset.memoStrokeCount = String(strokes.length);
    overlay.dataset.memoPage = loadedPage === null ? '' : String(loadedPage);
  }

  function eventPoint(e) {
    const rect = overlay.getBoundingClientRect();
    if (!rect.width || !rect.height) return [0, 0];
    const rx = (e.clientX - rect.left) * overlay.width / rect.width;
    const ry = (e.clientY - rect.top) * overlay.height / rect.height;
    const r = rotation();
    const src = sourceSize();
    let x = rx;
    let y = ry;
    if (r === 90) {
      x = ry;
      y = src.height - rx;
    } else if (r === 180) {
      x = src.width - rx;
      y = src.height - ry;
    } else if (r === 270) {
      x = src.width - ry;
      y = rx;
    }
    return [
      Math.max(0, Math.min(10000, x / SCALE)),
      Math.max(0, Math.min(10000, y / SCALE)),
    ];
  }

  function updateUi() {
    launch.classList.toggle('active', displayOn);
    editButton.classList.toggle('active', editMode);
    tools.classList.toggle('open', editMode);
    overlay.style.visibility = displayOn && !transitioning ? 'visible' : 'hidden';
    overlay.style.pointerEvents = editMode && displayOn && !transitioning && !saving ? 'auto' : 'none';
    viewer.classList.toggle('memo-mode', editMode && displayOn && !transitioning);
    eraserButton.classList.toggle('active', eraserMode);
    undoButton.disabled = !undoStack.length || saving;
    redoButton.disabled = !redoStack.length || saving;
    clearButton.disabled = !strokes.length || saving;
    saveButton.disabled = !dirty || saving;
    dirtyLabel.textContent = saving ? '保存中…' : dirty ? '未保存' : '';
  }

  function setDirty(value = true) {
    dirty = value;
    updateUi();
  }

  function pushUndo() {
    undoStack.push(clone(strokes));
    if (undoStack.length > 50) undoStack.shift();
    redoStack = [];
  }

  function pointSegmentDistance(p, a, b) {
    const vx = b[0] - a[0];
    const vy = b[1] - a[1];
    const wx = p[0] - a[0];
    const wy = p[1] - a[1];
    const length = vx * vx + vy * vy;
    let t = length ? (wx * vx + wy * vy) / length : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(
      p[0] - (a[0] + t * vx),
      p[1] - (a[1] + t * vy),
    );
  }

  function eraseAt(point) {
    const tolerance = 38;
    for (let i = strokes.length - 1; i >= 0; i--) {
      const stroke = strokes[i];
      const points = stroke.points || [];
      let hit = points.length === 1
        && Math.hypot(point[0] - points[0][0], point[1] - points[0][1]) <= tolerance + stroke.width / 2;
      for (let j = 1; !hit && j < points.length; j++) {
        hit = pointSegmentDistance(point, points[j - 1], points[j]) <= tolerance + stroke.width / 2;
      }
      if (hit) {
        if (!eraseSnapshotTaken) {
          pushUndo();
          eraseSnapshotTaken = true;
        }
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
    const index = strokes.indexOf(activeStroke);
    if (index >= 0) strokes.splice(index, 1);
    if (undoStack.length) strokes = undoStack.pop();
    redoStack = [];
    activeStroke = null;
    activePointerId = null;
    render();
    updateUi();
  }

  overlay.addEventListener('touchstart', event => {
    if (!editMode) return;
    if (event.touches.length >= 2) {
      multiTouch = true;
      cancelActiveStroke();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
  }, { passive: false });

  overlay.addEventListener('touchmove', event => {
    if (!editMode) return;
    if (event.touches.length >= 2 || multiTouch) return;
    event.preventDefault();
    event.stopPropagation();
  }, { passive: false });

  overlay.addEventListener('touchend', event => {
    if (!editMode) return;
    if (event.touches.length === 0) multiTouch = false;
    if (!multiTouch) {
      event.preventDefault();
      event.stopPropagation();
    }
  }, { passive: false });

  overlay.addEventListener('touchcancel', () => {
    multiTouch = false;
  }, { passive: true });

  overlay.addEventListener('pointerdown', event => {
    if (!editMode || saving || transitioning || multiTouch || activePointerId !== null || event.button > 0) return;
    event.preventDefault();
    event.stopPropagation();
    activePointerId = event.pointerId;
    overlay.setPointerCapture(event.pointerId);
    eraseSnapshotTaken = false;
    const point = eventPoint(event);
    if (eraserMode) {
      eraseAt(point);
      return;
    }
    pushUndo();
    activeStroke = { color, width, points: [point] };
    strokes.push(activeStroke);
    setDirty();
    render();
  });

  overlay.addEventListener('pointermove', event => {
    if (!editMode || event.pointerId !== activePointerId || multiTouch) return;
    event.preventDefault();
    event.stopPropagation();
    const point = eventPoint(event);
    if (eraserMode) {
      eraseAt(point);
      return;
    }
    if (!activeStroke) return;
    const last = activeStroke.points[activeStroke.points.length - 1];
    if (Math.hypot(point[0] - last[0], point[1] - last[1]) < 3) return;
    activeStroke.points.push(point);
    render();
  });

  function finishPointer(event) {
    if (event.pointerId !== activePointerId) return;
    event.preventDefault();
    event.stopPropagation();
    if (overlay.hasPointerCapture(event.pointerId)) {
      overlay.releasePointerCapture(event.pointerId);
    }
    activePointerId = null;
    activeStroke = null;
    eraseSnapshotTaken = false;
    updateUi();
  }

  overlay.addEventListener('pointerup', finishPointer);
  overlay.addEventListener('pointercancel', finishPointer);

  async function fetchMemo(pageNumber) {
    const response = await fetch(`${memoUrl}?page=${pageNumber}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '手書きメモを取得できませんでした。');
    return data;
  }

  function applyMemoData(pageNumber, data) {
    strokes = Array.isArray(data.strokes) ? data.strokes : [];
    undoStack = [];
    redoStack = [];
    dirty = false;
    loadedPage = pageNumber;
    render();
    updateUi();
  }

  async function loadMemo(pageNumber) {
    const token = ++loadToken;
    const data = await fetchMemo(pageNumber);
    if (token !== loadToken) return false;
    applyMemoData(pageNumber, data);
    return true;
  }

  async function saveMemo({ exitEdit = true } = {}) {
    if (saving) return false;
    if (!dirty) {
      if (exitEdit) editMode = false;
      updateUi();
      return true;
    }
    if (!loadedPage) loadedPage = Number(pageInput.value) || 1;
    saving = true;
    updateUi();
    try {
      const response = await fetch(memoUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pageNumber: loadedPage, strokes }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '手書きメモを保存できませんでした。');
      dirty = false;
      if (exitEdit) editMode = false;
      displayOn = true;
      if (statusLine) {
        statusLine.classList.remove('error');
        statusLine.textContent = `P${data.pageNumber} 手書きメモを保存しました（${data.count}本）`;
      }
      return true;
    } catch (error) {
      alert(error.message);
      return false;
    } finally {
      saving = false;
      updateUi();
    }
  }

  launch.addEventListener('click', async () => {
    if (displayOn) {
      if (editMode && dirty) {
        if (!confirm('手書きメモに未保存の変更があります。保存して表示をOFFにしますか？')) return;
        if (!await saveMemo()) return;
      }
      editMode = false;
      displayOn = false;
    } else {
      displayOn = true;
    }
    updateUi();
  });

  editButton.addEventListener('click', async () => {
    if (editMode) {
      if (dirty) {
        if (!confirm('手書きメモに未保存の変更があります。保存して編集を終了しますか？')) return;
        if (!await saveMemo()) return;
      } else {
        editMode = false;
      }
      updateUi();
      return;
    }
    displayOn = true;
    editMode = true;
    updateUi();
  });

  tools.querySelectorAll('[data-memo-color]').forEach(button => {
    button.addEventListener('click', () => {
      color = button.dataset.memoColor;
      eraserMode = false;
      tools.querySelectorAll('[data-memo-color]').forEach(item => item.classList.toggle('active', item === button));
      updateUi();
    });
  });

  tools.querySelectorAll('[data-memo-width]').forEach(button => {
    button.addEventListener('click', () => {
      width = Number(button.dataset.memoWidth);
      eraserMode = false;
      tools.querySelectorAll('[data-memo-width]').forEach(item => item.classList.toggle('active', item === button));
      updateUi();
    });
  });

  eraserButton.addEventListener('click', () => {
    eraserMode = !eraserMode;
    updateUi();
  });

  undoButton.addEventListener('click', () => {
    if (!undoStack.length || saving) return;
    redoStack.push(clone(strokes));
    strokes = undoStack.pop();
    setDirty();
    render();
  });

  redoButton.addEventListener('click', () => {
    if (!redoStack.length || saving) return;
    undoStack.push(clone(strokes));
    strokes = redoStack.pop();
    setDirty();
    render();
  });

  clearButton.addEventListener('click', () => {
    if (!strokes.length || saving) return;
    if (!confirm('このページの手書きメモを全消去しますか？')) return;
    pushUndo();
    strokes = [];
    setDirty();
    render();
  });

  saveButton.addEventListener('click', () => {
    saveMemo();
  });

  window.__drawingMemoBeforePageChange = async (fromPage, toPage) => {
    if (saving) return false;
    if (dirty) {
      if (!confirm('手書きメモに未保存の変更があります。保存してページを移動しますか？')) return false;
      if (!await saveMemo({ exitEdit: true })) return false;
    }
    transitioning = true;
    editMode = false;
    activeStroke = null;
    activePointerId = null;
    overlay.dataset.memoPendingPage = String(toPage);
    updateUi();
    return true;
  };

  window.addEventListener('weld:progress-page-changing', event => {
    transitioning = true;
    editMode = false;
    overlay.dataset.memoPendingPage = String(event.detail?.to || '');
    updateUi();
  });

  window.addEventListener('weld:progress-page-loaded', async event => {
    const pageNumber = Number(event.detail?.page) || Number(pageInput.value) || 1;
    try {
      await loadMemo(pageNumber);
      transitioning = false;
      overlay.dataset.memoPendingPage = '';
      updateUi();
    } catch (error) {
      transitioning = false;
      strokes = [];
      loadedPage = pageNumber;
      render();
      updateUi();
      if (statusLine) {
        statusLine.classList.add('error');
        statusLine.textContent = error.message;
      }
    }
  });

  window.addEventListener('beforeunload', event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });

  const canvasObserver = new MutationObserver(syncOverlaySize);
  canvasObserver.observe(baseCanvas, {
    attributes: true,
    attributeFilter: ['width', 'height', 'style'],
  });
  const canvasResizeObserver = 'ResizeObserver' in window
    ? new ResizeObserver(syncOverlaySize)
    : null;
  if (canvasResizeObserver) {
    canvasResizeObserver.observe(baseCanvas);
    canvasResizeObserver.observe(viewer);
  }
  window.addEventListener('resize', syncOverlaySize);

  if (rotateButton) {
    new MutationObserver(() => {
      syncOverlaySize();
      render();
    }).observe(rotateButton, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  const initialPage = Number(pageInput.value) || 1;
  loadMemo(initialPage)
    .catch(error => {
      loadedPage = initialPage;
      strokes = [];
      render();
      if (statusLine) {
        statusLine.classList.add('error');
        statusLine.textContent = error.message;
      }
    })
    .finally(() => {
      syncOverlaySize();
      updateUi();
    });

  updateUi();
})();
