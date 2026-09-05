(() => {
  const canvas = document.getElementById('canvas');
  const viewer = canvas?.closest('.viewer');
  const rotateButton = document.getElementById('rotate');
  if (!canvas || !viewer || !rotateButton) return;

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 4;
  const BUTTON_STEP = 0.2;
  const WHEEL_FACTOR = 1.12;

  let zoom = 1;
  let lastIntrinsicWidth = 0;
  let lastIntrinsicHeight = 0;
  let applying = false;

  const minusButton = document.createElement('button');
  minusButton.type = 'button';
  minusButton.id = 'entryZoomOut';
  minusButton.className = 'button';
  minusButton.textContent = '−';
  minusButton.title = '図面を縮小';
  minusButton.setAttribute('aria-label', '図面を縮小');

  const resetButton = document.createElement('button');
  resetButton.type = 'button';
  resetButton.id = 'entryZoomReset';
  resetButton.className = 'button';
  resetButton.textContent = '100%';
  resetButton.title = '図面倍率を100%に戻す';
  resetButton.setAttribute('aria-label', '図面倍率を100%に戻す');

  const plusButton = document.createElement('button');
  plusButton.type = 'button';
  plusButton.id = 'entryZoomIn';
  plusButton.className = 'button';
  plusButton.textContent = '＋';
  plusButton.title = '図面を拡大';
  plusButton.setAttribute('aria-label', '図面を拡大');

  rotateButton.insertAdjacentElement('afterend', plusButton);
  rotateButton.insertAdjacentElement('afterend', resetButton);
  rotateButton.insertAdjacentElement('afterend', minusButton);

  function clampZoom(value) {
    return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value));
  }

  function baseRenderedWidth() {
    if (!canvas.width) return 0;
    return Math.min(canvas.width, Math.max(1, viewer.clientWidth));
  }

  function updateControls() {
    const percent = Math.round(zoom * 100);
    resetButton.textContent = `${percent}%`;
    minusButton.disabled = zoom <= MIN_ZOOM + 0.001;
    plusButton.disabled = zoom >= MAX_ZOOM - 0.001;
    canvas.dataset.entryZoom = zoom.toFixed(3);
  }

  function applyZoom(nextZoom, anchor = null) {
    if (!canvas.width || !canvas.height) return;
    const next = clampZoom(nextZoom);
    const before = canvas.getBoundingClientRect();
    const viewerRect = viewer.getBoundingClientRect();
    const anchorX = anchor?.x ?? (viewerRect.left + viewerRect.width / 2);
    const anchorY = anchor?.y ?? (viewerRect.top + viewerRect.height / 2);
    const relX = before.width ? Math.max(0, Math.min(1, (anchorX - before.left) / before.width)) : 0.5;
    const relY = before.height ? Math.max(0, Math.min(1, (anchorY - before.top) / before.height)) : 0.5;

    zoom = next;
    applying = true;
    canvas.style.maxWidth = 'none';
    canvas.style.width = `${baseRenderedWidth() * zoom}px`;
    canvas.style.height = 'auto';
    updateControls();

    requestAnimationFrame(() => {
      const after = canvas.getBoundingClientRect();
      if (before.width && before.height && after.width && after.height) {
        const desiredX = after.left + after.width * relX;
        const desiredY = after.top + after.height * relY;
        viewer.scrollLeft += desiredX - anchorX;
        viewer.scrollTop += desiredY - anchorY;
      }
      applying = false;
      window.dispatchEvent(new CustomEvent('weld:entry-zoom-changed', { detail: { zoom } }));
    });
  }

  function syncIntrinsicSize() {
    if (!canvas.width || !canvas.height) return;
    if (canvas.width === lastIntrinsicWidth && canvas.height === lastIntrinsicHeight) return;
    lastIntrinsicWidth = canvas.width;
    lastIntrinsicHeight = canvas.height;
    applyZoom(zoom);
  }

  minusButton.addEventListener('click', () => applyZoom(zoom - BUTTON_STEP));
  plusButton.addEventListener('click', () => applyZoom(zoom + BUTTON_STEP));
  resetButton.addEventListener('click', () => applyZoom(1));

  viewer.addEventListener('wheel', event => {
    if (!event.ctrlKey || !canvas.width || !canvas.height) return;
    event.preventDefault();
    event.stopPropagation();
    const factor = event.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR;
    applyZoom(zoom * factor, { x: event.clientX, y: event.clientY });
  }, { passive: false });

  const canvasObserver = new MutationObserver(() => {
    if (!applying) syncIntrinsicSize();
  });
  canvasObserver.observe(canvas, { attributes: true, attributeFilter: ['width', 'height'] });

  const viewerResizeObserver = 'ResizeObserver' in window
    ? new ResizeObserver(() => {
        if (!applying && zoom <= 1.001) applyZoom(zoom);
      })
    : null;
  if (viewerResizeObserver) viewerResizeObserver.observe(viewer);

  window.addEventListener('weld:entry-base-drawn', syncIntrinsicSize);
  window.addEventListener('resize', () => {
    if (!applying && zoom <= 1.001) applyZoom(zoom);
  });

  updateControls();
  syncIntrinsicSize();
})();
