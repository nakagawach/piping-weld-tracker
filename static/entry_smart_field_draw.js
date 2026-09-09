(() => {
  const host = window.__weldEntryAreaHost;
  const baseCanvas = host?.canvas;
  const viewer = baseCanvas?.closest('.viewer');
  const areaButton = document.getElementById('areaCreate');
  const rotateButton = document.getElementById('rotate');
  if (!host || !baseCanvas || !viewer || !areaButton || !rotateButton) return;
  if (document.getElementById('entrySmartFieldDraw')) return;

  const SCALE = 1600 / 6000;
  const MAX_POLYGON_POINTS = 32;
  let enabled = false;
  let drawing = false;
  let pointerId = null;
  let rawPoints = [];

  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'entrySmartFieldDraw';
  button.className = 'button';
  button.textContent = '✏️ 現場入力';
  button.title = '指・ペンでざっくり描き、直線・長方形・ポリゴンに自動補正';
  areaButton.insertAdjacentElement('afterend', button);

  const help = document.createElement('span');
  help.id = 'entrySmartFieldHelp';
  help.textContent = '指/ペンで囲む';
  help.style.fontSize = '12px';
  help.style.fontWeight = '600';
  help.style.whiteSpace = 'nowrap';
  help.style.alignSelf = 'center';
  button.insertAdjacentElement('afterend', help);

  const overlay = document.createElement('canvas');
  overlay.id = 'entrySmartFieldCanvas';
  overlay.setAttribute('aria-label', '現場入力フリーハンドレイヤー');
  overlay.style.position = 'absolute';
  overlay.style.zIndex = '5';
  overlay.style.pointerEvents = 'none';
  overlay.style.touchAction = 'none';
  overlay.style.background = 'transparent';
  overlay.style.maxWidth = 'none';
  overlay.style.margin = '0';
  viewer.style.position = 'relative';
  viewer.appendChild(overlay);

  const centerOf = item => ({
    x: item.bbox.x + item.bbox.w / 2,
    y: item.bbox.y + item.bbox.h / 2,
  });

  function rotation() {
    const match = rotateButton.textContent.match(/(0|90|180|270)/);
    return match ? Number(match[1]) : 0;
  }

  function sourceSize() {
    const r = rotation();
    if (r === 90 || r === 270) {
      return { w: baseCanvas.height, h: baseCanvas.width };
    }
    return { w: baseCanvas.width, h: baseCanvas.height };
  }

  function pageBounds() {
    const size = sourceSize();
    return { w: size.w / SCALE, h: size.h / SCALE };
  }

  function syncOverlay() {
    if (!baseCanvas.width || !baseCanvas.height) return;
    const rect = baseCanvas.getBoundingClientRect();
    overlay.width = baseCanvas.width;
    overlay.height = baseCanvas.height;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
    overlay.style.left = `${baseCanvas.offsetLeft}px`;
    overlay.style.top = `${baseCanvas.offsetTop}px`;
    renderStroke();
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

  function renderStroke(points = rawPoints) {
    if (!overlay.width || !overlay.height) return;
    const ctx = configureContext();
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0].x * SCALE, points[0].y * SCALE);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x * SCALE, points[i].y * SCALE);
    }
    ctx.strokeStyle = '#1967d2';
    ctx.lineWidth = Math.max(4, overlay.width / 420);
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  }

  function distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function pathLength(points) {
    let length = 0;
    for (let i = 1; i < points.length; i++) length += distance(points[i - 1], points[i]);
    return length;
  }

  function pointSegmentDistance(p, a, b) {
    const vx = b.x - a.x;
    const vy = b.y - a.y;
    const len = vx * vx + vy * vy;
    const t = len ? Math.max(0, Math.min(1, ((p.x - a.x) * vx + (p.y - a.y) * vy) / len)) : 0;
    const x = a.x + t * vx;
    const y = a.y + t * vy;
    return Math.hypot(p.x - x, p.y - y);
  }

  function simplify(points, tolerance) {
    if (points.length <= 2) return points.slice();
    let maxDistance = 0;
    let maxIndex = 0;
    const first = points[0];
    const last = points[points.length - 1];
    for (let i = 1; i < points.length - 1; i++) {
      const d = pointSegmentDistance(points[i], first, last);
      if (d > maxDistance) {
        maxDistance = d;
        maxIndex = i;
      }
    }
    if (maxDistance <= tolerance) return [first, last];
    const left = simplify(points.slice(0, maxIndex + 1), tolerance);
    const right = simplify(points.slice(maxIndex), tolerance);
    return left.slice(0, -1).concat(right);
  }

  function polygonArea(points) {
    let sum = 0;
    for (let i = 0; i < points.length; i++) {
      const a = points[i];
      const b = points[(i + 1) % points.length];
      sum += a.x * b.y - b.x * a.y;
    }
    return Math.abs(sum) / 2;
  }

  function rotatedRectangle(points) {
    const c = points.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), { x: 0, y: 0 });
    c.x /= points.length;
    c.y /= points.length;
    let xx = 0;
    let yy = 0;
    let xy = 0;
    for (const p of points) {
      const dx = p.x - c.x;
      const dy = p.y - c.y;
      xx += dx * dx;
      yy += dy * dy;
      xy += dx * dy;
    }
    const angle = 0.5 * Math.atan2(2 * xy, xx - yy);
    const ux = Math.cos(angle);
    const uy = Math.sin(angle);
    const vx = -uy;
    const vy = ux;
    let minU = Infinity;
    let maxU = -Infinity;
    let minV = Infinity;
    let maxV = -Infinity;
    for (const p of points) {
      const dx = p.x - c.x;
      const dy = p.y - c.y;
      const u = dx * ux + dy * uy;
      const v = dx * vx + dy * vy;
      minU = Math.min(minU, u);
      maxU = Math.max(maxU, u);
      minV = Math.min(minV, v);
      maxV = Math.max(maxV, v);
    }
    const make = (u, v) => ({
      x: c.x + u * ux + v * vx,
      y: c.y + u * uy + v * vy,
    });
    return {
      points: [make(minU, minV), make(maxU, minV), make(maxU, maxV), make(minU, maxV)],
      area: Math.max(1, (maxU - minU) * (maxV - minV)),
    };
  }

  function lineStrip(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const length = Math.max(1, Math.hypot(dx, dy));
    const half = Math.max(host.cssPxToOcrX(8), host.cssPxToOcrY(8));
    const nx = -dy / length * half;
    const ny = dx / length * half;
    return [
      { x: a.x + nx, y: a.y + ny },
      { x: b.x + nx, y: b.y + ny },
      { x: b.x - nx, y: b.y - ny },
      { x: a.x - nx, y: a.y - ny },
    ];
  }

  function capPoints(points) {
    if (points.length <= MAX_POLYGON_POINTS) return points;
    const result = [];
    for (let i = 0; i < MAX_POLYGON_POINTS; i++) {
      result.push(points[Math.floor(i * points.length / MAX_POLYGON_POINTS)]);
    }
    return result;
  }

  function recognizeShape(points) {
    if (points.length < 2) return null;
    const length = pathLength(points);
    if (!length) return null;
    const direct = distance(points[0], points[points.length - 1]);
    if (direct / length >= 0.92) {
      return { kind: '直線', points: lineStrip(points[0], points[points.length - 1]) };
    }

    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);
    const diagonal = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    const closeTolerance = Math.max(host.cssPxToOcrX(24), host.cssPxToOcrY(24), diagonal * 0.16);
    if (direct > closeTolerance) return null;

    const closed = points.slice();
    if (distance(closed[0], closed[closed.length - 1]) <= closeTolerance) closed[closed.length - 1] = { ...closed[0] };
    const tolerance = Math.max(host.cssPxToOcrX(6), host.cssPxToOcrY(6), diagonal * 0.012);
    let simplified = simplify(closed, tolerance);
    if (simplified.length > 1 && distance(simplified[0], simplified[simplified.length - 1]) <= closeTolerance) simplified.pop();
    simplified = capPoints(simplified);
    if (simplified.length < 3) return null;

    const rect = rotatedRectangle(closed);
    const fillRatio = polygonArea(closed) / rect.area;
    if (fillRatio >= 0.68 && simplified.length <= 10) {
      return { kind: '長方形', points: rect.points };
    }
    return { kind: 'ポリゴン', points: simplified };
  }

  function boundsOf(points) {
    return {
      minX: Math.min(...points.map(p => p.x)),
      minY: Math.min(...points.map(p => p.y)),
      maxX: Math.max(...points.map(p => p.x)),
      maxY: Math.max(...points.map(p => p.y)),
    };
  }

  function shapeCenter(points) {
    return points.reduce((acc, p) => ({ x: acc.x + p.x / points.length, y: acc.y + p.y / points.length }), { x: 0, y: 0 });
  }

  function nearestCandidate(points) {
    const c = shapeCenter(points);
    const bounds = pageBounds();
    const limit = Math.hypot(bounds.w, bounds.h) * 0.24;
    let best = null;
    let bestDistance = Infinity;
    for (const item of host.getCandidates()) {
      const d = distance(c, centerOf(item));
      if (d < bestDistance) {
        best = item;
        bestDistance = d;
      }
    }
    return bestDistance <= limit ? best : null;
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = values.slice().sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  function rectsOverlap(a, b, pad = 0) {
    return !(a.x + a.w + pad < b.x || b.x + b.w + pad < a.x || a.y + a.h + pad < b.y || b.y + b.h + pad < a.y);
  }

  function chooseMarkerCenter(points, ignoreId = null) {
    const shape = boundsOf(points);
    const candidates = host.getCandidates();
    const widths = candidates.map(item => item.bbox.w).filter(v => v > 0);
    const heights = candidates.map(item => item.bbox.h).filter(v => v > 0);
    const markerW = Math.max(median(widths) || 0, host.cssPxToOcrX(22));
    const markerH = Math.max(median(heights) || 0, host.cssPxToOcrY(22));
    const gap = Math.max(host.cssPxToOcrX(28), host.cssPxToOcrY(28));
    const midX = (shape.minX + shape.maxX) / 2;
    const midY = (shape.minY + shape.maxY) / 2;
    const positions = [
      { x: shape.maxX + gap + markerW / 2, y: midY },
      { x: shape.minX - gap - markerW / 2, y: midY },
      { x: midX, y: shape.minY - gap - markerH / 2 },
      { x: midX, y: shape.maxY + gap + markerH / 2 },
      { x: shape.maxX + gap + markerW / 2, y: shape.minY - gap - markerH / 2 },
      { x: shape.maxX + gap + markerW / 2, y: shape.maxY + gap + markerH / 2 },
      { x: shape.minX - gap - markerW / 2, y: shape.minY - gap - markerH / 2 },
      { x: shape.minX - gap - markerW / 2, y: shape.maxY + gap + markerH / 2 },
    ];
    const page = pageBounds();
    const shapeRect = { x: shape.minX, y: shape.minY, w: shape.maxX - shape.minX, h: shape.maxY - shape.minY };
    let best = null;
    let bestScore = Infinity;
    for (const p of positions) {
      const box = { x: p.x - markerW / 2, y: p.y - markerH / 2, w: markerW, h: markerH };
      let score = distance(p, { x: midX, y: midY });
      if (box.x < 0 || box.y < 0 || box.x + box.w > page.w || box.y + box.h > page.h) score += 1e9;
      if (rectsOverlap(box, shapeRect, gap * 0.25)) score += 1e7;
      for (const item of candidates) {
        if (item.id === ignoreId) continue;
        if (rectsOverlap(box, item.bbox, gap * 0.18)) score += 1e6;
      }
      if (score < bestScore) {
        bestScore = score;
        best = p;
      }
    }
    if (best && bestScore < 1e9) return best;
    return {
      x: Math.max(markerW / 2, Math.min(page.w - markerW / 2, shape.maxX + gap + markerW / 2)),
      y: Math.max(markerH / 2, Math.min(page.h - markerH / 2, midY)),
    };
  }

  function ocrToCanvasPoint(point) {
    const size = sourceSize();
    const x = point.x * SCALE;
    const y = point.y * SCALE;
    const r = rotation();
    if (r === 90) return { x: size.h - y, y: x };
    if (r === 180) return { x: size.w - x, y: size.h - y };
    if (r === 270) return { x: y, y: size.w - x };
    return { x, y };
  }

  function clientPoint(point) {
    const p = ocrToCanvasPoint(point);
    const rect = baseCanvas.getBoundingClientRect();
    return {
      x: rect.left + p.x * rect.width / baseCanvas.width,
      y: rect.top + p.y * rect.height / baseCanvas.height,
    };
  }

  function dispatchCanvasClick(point, detail = 1) {
    const client = clientPoint(point);
    baseCanvas.dispatchEvent(new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      clientX: client.x,
      clientY: client.y,
      detail,
      button: 0,
    }));
  }

  function withPromptValue(value, action) {
    const originalPrompt = window.prompt;
    window.prompt = () => value;
    try {
      action();
    } finally {
      window.prompt = originalPrompt;
    }
  }

  function normalizeNumber(value) {
    const text = String(value ?? '').normalize('NFKC').toUpperCase().replace(/\s+/g, '').trim();
    if (!text || text.length > 12) return null;
    if (/^\d{1,3}$/.test(text) && Number(text) >= 1) return String(Number(text));
    return /^(?:[A-Z]{1,4}[-/]?\d{1,4}(?:[-/][A-Z0-9]{1,4})?|\d{1,4}[-/]?[A-Z]{1,3})$/.test(text) ? text : null;
  }

  function removeCandidate(candidate) {
    if (!candidate) return false;
    const before = host.getCandidates().some(item => item.id === candidate.id);
    if (!before) return false;
    withPromptValue('', () => dispatchCanvasClick(centerOf(candidate)));
    return !host.getCandidates().some(item => item.id === candidate.id);
  }

  function createCandidate(number, center) {
    const beforeIds = new Set(host.getCandidates().map(item => item.id));
    withPromptValue(number, () => dispatchCanvasClick(center));
    return host.getCandidates().find(item => !beforeIds.has(item.id)) || null;
  }

  function createArea(candidate, points) {
    if (!candidate || points.length < 3) return false;
    const before = Number(document.getElementById('entryAreaCanvas')?.dataset.areaCount || 0);
    if (areaButton.classList.contains('active')) areaButton.click();
    areaButton.click();
    dispatchCanvasClick(centerOf(candidate));
    for (const point of points) dispatchCanvasClick(point);
    dispatchCanvasClick(points[0]);
    if (areaButton.classList.contains('active')) areaButton.click();
    const after = Number(document.getElementById('entryAreaCanvas')?.dataset.areaCount || 0);
    return after > before;
  }

  function suggestedNextNumber() {
    const numeric = host.getCandidates()
      .map(item => /^\d+$/.test(String(item.number)) ? Number(item.number) : null)
      .filter(value => Number.isInteger(value));
    return numeric.length ? String(Math.max(...numeric) + 1) : '';
  }

  function commitShape(shape) {
    const nearest = nearestCandidate(shape.points);
    const defaultNumber = nearest?.number || suggestedNextNumber();
    const raw = window.prompt(
      `${shape.kind}に補正しました。丸枠の番号を確認してください。\n` +
      '近くのOCR番号を初期値にしています。キャンセルで破棄します。',
      defaultNumber,
    );
    if (raw === null) return;
    const number = normalizeNumber(raw);
    if (!number) {
      host.status.className = 'status error';
      host.status.textContent = '番号は1〜999、F1、S2、A-12等で入力してください。描画は保存していません。';
      return;
    }
    if (!window.confirm(`${shape.kind} + 丸枠 ${number} + 接続線として追加しますか？`)) return;

    const markerCenter = chooseMarkerCenter(shape.points, nearest?.id ?? null);
    let target = null;
    if (nearest && String(nearest.number) === number) {
      const removed = removeCandidate(nearest);
      if (!removed) {
        target = nearest;
      }
    }
    if (!target) target = createCandidate(number, markerCenter);
    if (!target) {
      host.status.className = 'status error';
      host.status.textContent = '丸枠の自動配置に失敗しました。既存データは保存していません。';
      return;
    }

    const created = createArea(target, shape.points);
    if (!created) {
      host.status.className = 'status error';
      host.status.textContent = `丸枠 ${number} は追加しましたが、エリア自動作成を確認できませんでした。読込時に戻すで取り消せます。`;
      return;
    }
    host.setDirty(true);
    host.status.className = 'status';
    host.status.textContent = `${shape.kind}を自動補正し、丸枠 ${number} を余白へ配置して接続しました。続けて描けます。確定保存するまではDBへ反映されません。`;
  }

  function setEnabled(value) {
    enabled = Boolean(value);
    drawing = false;
    pointerId = null;
    rawPoints = [];
    renderStroke();
    if (enabled) {
      host.disableBboxEdit();
      host.clearSelection();
      if (areaButton.classList.contains('active')) areaButton.click();
      button.classList.add('active');
      button.textContent = '✏️ 現場入力 ON';
      help.textContent = '指/ペンで描く';
      overlay.style.pointerEvents = 'auto';
      host.status.className = 'status';
      host.status.textContent = '現場入力ON：直線はなぞる、エリアは一周して閉じるように描いてください。指を離すと自動補正します。';
    } else {
      button.classList.remove('active');
      button.textContent = '✏️ 現場入力';
      help.textContent = '指/ペンで囲む';
      overlay.style.pointerEvents = 'none';
      host.status.className = 'status';
      host.status.textContent = '現場入力OFF：従来のOCR・枠編集・エリア作成をそのまま利用できます。';
    }
  }

  button.addEventListener('click', () => {
    if (host.isBusy()) return;
    setEnabled(!enabled);
  });

  overlay.addEventListener('pointerdown', event => {
    if (!enabled || host.isBusy() || drawing) return;
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    drawing = true;
    pointerId = event.pointerId;
    rawPoints = [host.point(event)];
    overlay.setPointerCapture(event.pointerId);
    renderStroke();
  }, { passive: false });

  overlay.addEventListener('pointermove', event => {
    if (!enabled || !drawing || event.pointerId !== pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    const point = host.point(event);
    const last = rawPoints[rawPoints.length - 1];
    const minimum = Math.max(host.cssPxToOcrX(2), host.cssPxToOcrY(2));
    if (!last || distance(last, point) >= minimum) rawPoints.push(point);
    renderStroke();
  }, { passive: false });

  function finishPointer(event, cancelled = false) {
    if (!drawing || event.pointerId !== pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    if (overlay.hasPointerCapture(event.pointerId)) overlay.releasePointerCapture(event.pointerId);
    drawing = false;
    pointerId = null;
    const points = rawPoints.slice();
    rawPoints = [];
    renderStroke();
    if (cancelled || points.length < 2) return;
    const shape = recognizeShape(points);
    if (!shape) {
      host.status.className = 'status error';
      host.status.textContent = '形を認識できませんでした。直線はまっすぐ、エリアは始点付近まで一周して描いてください。';
      return;
    }
    renderStroke(shape.points);
    requestAnimationFrame(() => {
      commitShape(shape);
      rawPoints = [];
      renderStroke();
    });
  }

  overlay.addEventListener('pointerup', event => finishPointer(event, false), { passive: false });
  overlay.addEventListener('pointercancel', event => finishPointer(event, true), { passive: false });

  window.addEventListener('weld:entry-base-drawn', syncOverlay);
  window.addEventListener('weld:entry-zoom-changed', syncOverlay);
  window.addEventListener('resize', syncOverlay);
  if ('ResizeObserver' in window) new ResizeObserver(syncOverlay).observe(viewer);

  window.__weldSmartFieldDrawTest = { recognizeShape, simplify, rotatedRectangle, lineStrip };
  syncOverlay();
})();
