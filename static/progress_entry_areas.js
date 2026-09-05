(() => {
  const baseCanvas = document.getElementById('canvas');
  const viewer = document.getElementById('viewer');
  const pageInput = document.getElementById('page');
  const rotateButton = document.getElementById('rotate');
  if (!baseCanvas || !viewer || !pageInput || !rotateButton) return;

  const pathMatch = location.pathname.match(/^(.*\/projects\/\d+)\/progress$/);
  if (!pathMatch) return;
  const numberMapUrl = `${pathMatch[1]}/number-map`;
  const SCALE = 1600 / 6000;

  const overlay = document.createElement('canvas');
  overlay.id = 'progressEntryAreaCanvas';
  overlay.setAttribute('aria-label', 'ポリゴンエリア表示レイヤー');
  overlay.style.position = 'absolute';
  overlay.style.zIndex = '2';
  overlay.style.pointerEvents = 'none';
  overlay.style.background = 'transparent';
  viewer.style.position = 'relative';
  viewer.insertBefore(overlay, baseCanvas.nextSibling);

  let candidates = [];
  let areas = [];
  let selectedKey = '';
  let loadToken = 0;
  let syntheticClick = false;
  let touchStart = null;
  let touchMoved = false;

  const center = item => ({
    x: item.bbox.x + item.bbox.w / 2,
    y: item.bbox.y + item.bbox.h / 2,
  });
  const targetKey = item => {
    const c = center(item);
    return `${Math.round(c.x)}:${Math.round(c.y)}`;
  };

  function rotation() {
    const match = rotateButton.textContent.match(/(0|90|180|270)/);
    return match ? Number(match[1]) : 0;
  }

  function sourceSize() {
    const r = rotation();
    return r === 90 || r === 270
      ? { width: baseCanvas.height, height: baseCanvas.width }
      : { width: baseCanvas.width, height: baseCanvas.height };
  }

  function syncOverlaySize() {
    if (!baseCanvas.width || !baseCanvas.height || baseCanvas.hidden || getComputedStyle(baseCanvas).display === 'none') {
      overlay.style.visibility = 'hidden';
      return;
    }
    overlay.style.visibility = 'visible';
    const rect = baseCanvas.getBoundingClientRect();
    overlay.width = baseCanvas.width;
    overlay.height = baseCanvas.height;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
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

  function nearestPointOnSegment(point, a, b) {
    const vx = b[0] - a[0];
    const vy = b[1] - a[1];
    const len = vx * vx + vy * vy;
    let t = len ? ((point.x - a[0]) * vx + (point.y - a[1]) * vy) / len : 0;
    t = Math.max(0, Math.min(1, t));
    return [a[0] + t * vx, a[1] + t * vy];
  }

  function nearestPolygonPoint(point, points) {
    let best = points[0];
    let bestDistance = Infinity;
    for (let i = 0; i < points.length; i++) {
      const candidate = nearestPointOnSegment(point, points[i], points[(i + 1) % points.length]);
      const distance = Math.hypot(candidate[0] - point.x, candidate[1] - point.y);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = candidate;
      }
    }
    return best;
  }

  function render() {
    if (!overlay.width || !overlay.height) return;
    const ctx = configureContext();
    for (const area of areas) {
      const target = area.target;
      if (!target || area.points.length < 3) continue;
      const c = center(target);
      const end = nearestPolygonPoint(c, area.points);
      ctx.beginPath();
      ctx.moveTo(c.x * SCALE, c.y * SCALE);
      ctx.lineTo(end[0] * SCALE, end[1] * SCALE);
      ctx.strokeStyle = 'rgba(95,99,104,.72)';
      ctx.lineWidth = Math.max(2, overlay.width / 850);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(area.points[0][0] * SCALE, area.points[0][1] * SCALE);
      for (let i = 1; i < area.points.length; i++) {
        ctx.lineTo(area.points[i][0] * SCALE, area.points[i][1] * SCALE);
      }
      ctx.closePath();
      const selected = selectedKey === targetKey(target);
      ctx.fillStyle = selected ? 'rgba(25,103,210,.10)' : 'rgba(245,124,0,.035)';
      ctx.fill();
      ctx.strokeStyle = selected ? '#1967d2' : '#f57c00';
      ctx.lineWidth = selected ? Math.max(4, overlay.width / 520) : Math.max(3, overlay.width / 650);
      ctx.lineJoin = 'round';
      ctx.stroke();
    }
    overlay.dataset.areaCount = String(areas.length);
    overlay.dataset.areaPage = String(pageInput.value || '');
  }

  function eventPoint(event) {
    const rect = baseCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return [0, 0];
    const rx = (event.clientX - rect.left) * baseCanvas.width / rect.width;
    const ry = (event.clientY - rect.top) * baseCanvas.height / rect.height;
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
    return [x / SCALE, y / SCALE];
  }

  function pointInPolygon(point, points) {
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const xi = points[i][0], yi = points[i][1];
      const xj = points[j][0], yj = points[j][1];
      const intersect = ((yi > point[1]) !== (yj > point[1]))
        && point[0] < (xj - xi) * (point[1] - yi) / ((yj - yi) || 1e-9) + xi;
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function pointSegmentDistance(point, a, b) {
    const closest = nearestPointOnSegment({x: point[0], y: point[1]}, a, b);
    return Math.hypot(point[0] - closest[0], point[1] - closest[1]);
  }

  function hitToleranceOcr() {
    const rect = baseCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return 40;
    return 12 * Math.max(baseCanvas.width / rect.width, baseCanvas.height / rect.height) / SCALE;
  }

  function findAreaAt(point) {
    const tolerance = hitToleranceOcr();
    const hits = [];
    for (const area of areas) {
      if (pointInPolygon(point, area.points)) {
        hits.push(area);
        continue;
      }
      for (let i = 0; i < area.points.length; i++) {
        if (pointSegmentDistance(point, area.points[i], area.points[(i + 1) % area.points.length]) <= tolerance) {
          hits.push(area);
          break;
        }
      }
    }
    if (!hits.length) return null;
    hits.sort((a, b) => {
      const ac = center(a.target), bc = center(b.target);
      return Math.hypot(point[0] - ac.x, point[1] - ac.y) - Math.hypot(point[0] - bc.x, point[1] - bc.y);
    });
    return hits[0];
  }

  function ocrToClient(point) {
    const src = sourceSize();
    const r = rotation();
    const sx = point.x * SCALE;
    const sy = point.y * SCALE;
    let dx = sx;
    let dy = sy;
    if (r === 90) {
      dx = src.height - sy;
      dy = sx;
    } else if (r === 180) {
      dx = src.width - sx;
      dy = src.height - sy;
    } else if (r === 270) {
      dx = sy;
      dy = src.width - sx;
    }
    const rect = baseCanvas.getBoundingClientRect();
    return {
      x: rect.left + dx * rect.width / baseCanvas.width,
      y: rect.top + dy * rect.height / baseCanvas.height,
    };
  }

  function openViaBaseTarget(area) {
    if (!area?.target) return;
    const c = center(area.target);
    const client = ocrToClient(c);
    syntheticClick = true;
    try {
      baseCanvas.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        clientX: client.x,
        clientY: client.y,
        button: 0,
      }));
    } finally {
      syntheticClick = false;
    }
  }

  async function loadAreas(pageNumber) {
    const token = ++loadToken;
    const response = await fetch(`${numberMapUrl}?page=${pageNumber}&_areas=${Date.now()}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'エリア情報を取得できませんでした。');
    if (token !== loadToken) return;
    candidates = Array.isArray(data.candidates) ? data.candidates : [];
    areas = [];
    for (const raw of Array.isArray(data.areas) ? data.areas : []) {
      const target = candidates.find(item => {
        const c = center(item);
        return item.number === raw.number
          && Math.abs(c.x - Number(raw.target?.x)) < 2
          && Math.abs(c.y - Number(raw.target?.y)) < 2;
      });
      if (!target || !Array.isArray(raw.points) || raw.points.length < 3) continue;
      areas.push({
        target,
        points: raw.points.map(point => [Number(point[0]), Number(point[1])]),
      });
    }
    selectedKey = '';
    syncOverlaySize();
  }

  baseCanvas.addEventListener('click', event => {
    if (syntheticClick || viewer.classList.contains('memo-mode')) return;
    const hit = findAreaAt(eventPoint(event));
    if (!hit) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openViaBaseTarget(hit);
  }, true);

  viewer.addEventListener('touchstart', event => {
    if (viewer.classList.contains('memo-mode')) return;
    if (event.touches.length !== 1) {
      touchStart = null;
      touchMoved = true;
      return;
    }
    touchStart = { x: event.touches[0].clientX, y: event.touches[0].clientY };
    touchMoved = false;
  }, { capture: true, passive: true });

  viewer.addEventListener('touchmove', event => {
    if (!touchStart || event.touches.length !== 1) {
      touchMoved = true;
      return;
    }
    const dx = event.touches[0].clientX - touchStart.x;
    const dy = event.touches[0].clientY - touchStart.y;
    if (Math.hypot(dx, dy) > 6) touchMoved = true;
  }, { capture: true, passive: true });

  viewer.addEventListener('touchend', event => {
    if (viewer.classList.contains('memo-mode') || touchMoved || !touchStart || event.touches.length || event.changedTouches.length !== 1) {
      touchStart = null;
      return;
    }
    const touch = event.changedTouches[0];
    const hit = findAreaAt(eventPoint(touch));
    touchStart = null;
    if (!hit) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openViaBaseTarget(hit);
  }, { capture: true, passive: false });

  window.addEventListener('weld:progress-page-changing', () => {
    ++loadToken;
    candidates = [];
    areas = [];
    selectedKey = '';
    render();
  });

  window.addEventListener('weld:progress-page-loaded', event => {
    const pageNumber = Number(event.detail?.page) || Number(pageInput.value) || 1;
    loadAreas(pageNumber).catch(() => {
      candidates = [];
      areas = [];
      render();
    });
  });

  window.addEventListener('weld:progress-selection', event => {
    const x = Math.round(Number(event.detail?.x));
    const y = Math.round(Number(event.detail?.y));
    selectedKey = `${x}:${y}`;
    render();
  });

  const canvasObserver = new MutationObserver(syncOverlaySize);
  canvasObserver.observe(baseCanvas, { attributes: true, attributeFilter: ['width', 'height', 'style', 'hidden'] });
  const resizeObserver = 'ResizeObserver' in window ? new ResizeObserver(syncOverlaySize) : null;
  if (resizeObserver) {
    resizeObserver.observe(baseCanvas);
    resizeObserver.observe(viewer);
  }
  new MutationObserver(syncOverlaySize).observe(rotateButton, { childList: true, characterData: true, subtree: true });
  window.addEventListener('resize', syncOverlaySize);

  const initialPage = Number(pageInput.value) || 1;
  loadAreas(initialPage).catch(() => {});
  syncOverlaySize();
})();
