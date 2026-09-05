(() => {
  const host = window.__weldEntryAreaHost;
  if (!host) return;
  const baseCanvas = host.canvas;
  const viewer = baseCanvas.closest('.viewer');
  const rotateButton = document.getElementById('rotate');
  if (!viewer || !rotateButton) return;

  const SCALE = 1600 / 6000;
  const overlay = document.createElement('canvas');
  overlay.id = 'entryAreaCanvas';
  overlay.setAttribute('aria-label', 'ポリゴンエリア表示レイヤー');
  overlay.style.position = 'absolute';
  overlay.style.zIndex = '3';
  overlay.style.pointerEvents = 'none';
  overlay.style.background = 'transparent';
  viewer.style.position = 'relative';
  viewer.insertBefore(overlay, baseCanvas.nextSibling);

  const areaButton = document.createElement('button');
  areaButton.type = 'button';
  areaButton.id = 'areaCreate';
  areaButton.className = 'button';
  areaButton.textContent = 'エリア作成';
  areaButton.title = '丸枠を選択してポリゴンエリアを作成・編集';
  host.bboxEditButton.insertAdjacentElement('afterend', areaButton);

  const numberLabelControl = document.createElement('label');
  numberLabelControl.id = 'entryMarkerNumberControl';
  numberLabelControl.className = 'button';
  numberLabelControl.style.display = 'inline-flex';
  numberLabelControl.style.alignItems = 'center';
  numberLabelControl.style.gap = '7px';
  numberLabelControl.style.cursor = 'pointer';
  numberLabelControl.style.fontWeight = '600';
  numberLabelControl.title = '進捗画面の丸枠内に番号を表示します';

  const numberLabelCheckbox = document.createElement('input');
  numberLabelCheckbox.type = 'checkbox';
  numberLabelCheckbox.id = 'entryShowNumberInMarker';
  numberLabelCheckbox.checked = false;
  numberLabelCheckbox.setAttribute('aria-label', '進捗画面の枠内に番号を表示');

  const numberLabelText = document.createElement('span');
  numberLabelText.textContent = '枠内番号';
  numberLabelControl.append(numberLabelCheckbox, numberLabelText);
  areaButton.insertAdjacentElement('afterend', numberLabelControl);

  let areas = [];
  let originalAreas = [];
  let originalShowNumberInMarker = false;
  let nextAreaId = 1;
  let mode = false;
  let targetId = null;
  let draft = [];
  let preview = null;
  let selectedAreaId = null;
  let vertexDrag = null;
  let suppressClick = false;
  let lastMapRef = null;

  const cloneAreas = list => list.map(area => ({
    ...area,
    points: area.points.map(point => [...point]),
  }));
  const center = item => ({
    x: item.bbox.x + item.bbox.w / 2,
    y: item.bbox.y + item.bbox.h / 2,
  });
  const candidateById = id => host.getCandidates().find(item => item.id === id) || null;

  function rotation() {
    const match = rotateButton.textContent.match(/(0|90|180|270)/);
    return match ? Number(match[1]) : 0;
  }

  function syncOverlaySize() {
    if (!baseCanvas.width || !baseCanvas.height) return;
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

  function drawPolygon(ctx, points, selected = false) {
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0][0] * SCALE, points[0][1] * SCALE);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0] * SCALE, points[i][1] * SCALE);
    ctx.closePath();
    ctx.fillStyle = selected ? 'rgba(245,124,0,.10)' : 'rgba(245,124,0,.045)';
    ctx.fill();
    ctx.strokeStyle = '#f57c00';
    ctx.lineWidth = Math.max(3, overlay.width / 620);
    ctx.lineJoin = 'round';
    ctx.stroke();
    if (selected) {
      const size = Math.max(8, overlay.width / 190);
      for (const point of points) {
        const x = point[0] * SCALE;
        const y = point[1] * SCALE;
        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#1967d2';
        ctx.lineWidth = Math.max(2, overlay.width / 900);
        ctx.fillRect(x - size / 2, y - size / 2, size, size);
        ctx.strokeRect(x - size / 2, y - size / 2, size, size);
      }
    }
  }

  function reconcileAreas(markDirty = true) {
    const ids = new Set(host.getCandidates().map(item => item.id));
    const before = areas.length;
    areas = areas.filter(area => ids.has(area.targetId));
    if (markDirty && areas.length !== before) host.setDirty(true);
  }

  function render() {
    if (!overlay.width || !overlay.height) return;
    reconcileAreas(false);
    const ctx = configureContext();
    for (const area of areas) {
      const target = candidateById(area.targetId);
      if (!target || area.points.length < 3) continue;
      const c = center(target);
      const end = nearestPolygonPoint(c, area.points);
      ctx.beginPath();
      ctx.moveTo(c.x * SCALE, c.y * SCALE);
      ctx.lineTo(end[0] * SCALE, end[1] * SCALE);
      ctx.strokeStyle = 'rgba(95,99,104,.78)';
      ctx.lineWidth = Math.max(2, overlay.width / 850);
      ctx.stroke();
      drawPolygon(ctx, area.points, area.id === selectedAreaId);
    }

    if (mode && targetId !== null && draft.length) {
      const target = candidateById(targetId);
      if (target) {
        const c = center(target);
        const end = draft.length >= 2 ? nearestPolygonPoint(c, draft) : draft[0];
        ctx.beginPath();
        ctx.moveTo(c.x * SCALE, c.y * SCALE);
        ctx.lineTo(end[0] * SCALE, end[1] * SCALE);
        ctx.strokeStyle = 'rgba(95,99,104,.55)';
        ctx.lineWidth = Math.max(2, overlay.width / 850);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.setLineDash([9, 6]);
      ctx.moveTo(draft[0][0] * SCALE, draft[0][1] * SCALE);
      for (let i = 1; i < draft.length; i++) ctx.lineTo(draft[i][0] * SCALE, draft[i][1] * SCALE);
      if (preview) ctx.lineTo(preview[0] * SCALE, preview[1] * SCALE);
      ctx.strokeStyle = '#f57c00';
      ctx.lineWidth = Math.max(3, overlay.width / 620);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    overlay.dataset.areaCount = String(areas.length);
    overlay.dataset.selectedArea = selectedAreaId === null ? '' : String(selectedAreaId);
  }

  function pointSegmentDistance(point, a, b) {
    const closest = nearestPointOnSegment({x: point[0], y: point[1]}, a, b);
    return Math.hypot(point[0] - closest[0], point[1] - closest[1]);
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

  function findAreaAt(point) {
    const tolerance = Math.max(host.cssPxToOcrX(9), host.cssPxToOcrY(9));
    for (let i = areas.length - 1; i >= 0; i--) {
      const area = areas[i];
      if (pointInPolygon([point.x, point.y], area.points)) return area;
      for (let j = 0; j < area.points.length; j++) {
        if (pointSegmentDistance([point.x, point.y], area.points[j], area.points[(j + 1) % area.points.length]) <= tolerance) return area;
      }
    }
    return null;
  }

  function findVertex(point) {
    if (selectedAreaId === null) return null;
    const area = areas.find(item => item.id === selectedAreaId);
    if (!area) return null;
    const toleranceX = host.cssPxToOcrX(11);
    const toleranceY = host.cssPxToOcrY(11);
    for (let index = 0; index < area.points.length; index++) {
      const vertex = area.points[index];
      if (Math.abs(point.x - vertex[0]) <= toleranceX && Math.abs(point.y - vertex[1]) <= toleranceY) {
        return { area, index };
      }
    }
    return null;
  }

  function setMode(value) {
    mode = Boolean(value);
    targetId = null;
    draft = [];
    preview = null;
    vertexDrag = null;
    selectedAreaId = null;
    if (mode) {
      host.disableBboxEdit();
      host.clearSelection();
      areaButton.classList.add('active');
      baseCanvas.style.cursor = 'crosshair';
      host.status.className = 'status';
      host.status.textContent = 'エリア作成ON：対象の丸枠をクリックし、続けてポリゴン頂点をクリックしてください。始点クリックまたはダブルクリックで確定します。';
    } else {
      areaButton.classList.remove('active');
      baseCanvas.style.removeProperty('cursor');
      host.status.className = 'status';
      host.status.textContent = 'エリア作成OFF：通常の番号変更・手動追加に戻りました。';
    }
    render();
  }

  function applyMapData() {
    const record = host.getLastMapData();
    if (!record || record === lastMapRef) return;
    lastMapRef = record;
    const candidates = host.getCandidates();
    areas = [];
    for (const raw of Array.isArray(record.data?.areas) ? record.data.areas : []) {
      const target = candidates.find(item => {
        const c = center(item);
        return item.number === raw.number
          && Math.abs(c.x - Number(raw.target?.x)) < 2
          && Math.abs(c.y - Number(raw.target?.y)) < 2;
      });
      if (!target || !Array.isArray(raw.points) || raw.points.length < 3) continue;
      areas.push({
        id: nextAreaId++,
        targetId: target.id,
        points: raw.points.map(point => [Number(point[0]), Number(point[1])]),
      });
    }
    originalAreas = cloneAreas(areas);
    originalShowNumberInMarker = record.data?.showNumberInMarker === true;
    numberLabelCheckbox.checked = originalShowNumberInMarker;
    setMode(false);
    syncOverlaySize();
  }

  function serializeAreas() {
    reconcileAreas(false);
    return areas.map(area => {
      const target = candidateById(area.targetId);
      const c = center(target);
      return {
        number: target.number,
        target: { x: c.x, y: c.y },
        points: area.points.map(point => [...point]),
      };
    });
  }

  function completeDraft() {
    if (targetId === null || draft.length < 3) return;
    const target = candidateById(targetId);
    if (!target) return;
    const existing = areas.find(area => area.targetId === targetId);
    if (existing) {
      existing.points = draft.map(point => [...point]);
      selectedAreaId = existing.id;
    } else {
      const area = { id: nextAreaId++, targetId, points: draft.map(point => [...point]) };
      areas.push(area);
      selectedAreaId = area.id;
    }
    const number = target.number;
    targetId = null;
    draft = [];
    preview = null;
    host.setDirty(true);
    host.status.className = 'status';
    host.status.textContent = `${number} のポリゴンエリアを作成しました。頂点をドラッグして調整できます。確定保存するまでDBには反映されません。`;
    render();
  }

  areaButton.addEventListener('click', () => {
    if (host.isBusy()) return;
    setMode(!mode);
  });

  numberLabelCheckbox.addEventListener('change', () => {
    if (host.isBusy()) {
      numberLabelCheckbox.checked = !numberLabelCheckbox.checked;
      return;
    }
    host.setDirty(true);
    host.status.className = 'status';
    host.status.textContent = numberLabelCheckbox.checked
      ? '進捗画面の丸枠内に番号を表示します。確定保存すると反映されます。'
      : '進捗画面の丸枠内番号を非表示にします。確定保存すると反映されます。';
  });

  baseCanvas.addEventListener('pointerdown', event => {
    if (!mode || event.pointerType !== 'mouse' || event.button !== 0 || host.isBusy()) return;
    const p = host.point(event);
    const vertex = findVertex(p);
    if (vertex) {
      event.preventDefault();
      event.stopImmediatePropagation();
      vertexDrag = { areaId: vertex.area.id, index: vertex.index, pointerId: event.pointerId, moved: false };
      baseCanvas.setPointerCapture(event.pointerId);
      return;
    }
    event.stopImmediatePropagation();
  }, true);

  baseCanvas.addEventListener('pointermove', event => {
    if (!mode || event.pointerType !== 'mouse') return;
    const p = host.point(event);
    if (vertexDrag && vertexDrag.pointerId === event.pointerId) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const area = areas.find(item => item.id === vertexDrag.areaId);
      if (!area) return;
      area.points[vertexDrag.index] = [p.x, p.y];
      vertexDrag.moved = true;
      render();
      return;
    }
    if (targetId !== null && draft.length) {
      preview = [p.x, p.y];
      render();
    }
  }, true);

  baseCanvas.addEventListener('pointerup', event => {
    if (!mode || !vertexDrag || vertexDrag.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (baseCanvas.hasPointerCapture(event.pointerId)) baseCanvas.releasePointerCapture(event.pointerId);
    const changed = vertexDrag.moved;
    vertexDrag = null;
    suppressClick = true;
    if (changed) {
      host.setDirty(true);
      host.status.className = 'status';
      host.status.textContent = 'ポリゴン頂点を移動しました。確定保存するまでDBには反映されません。';
    }
    render();
  }, true);

  baseCanvas.addEventListener('pointercancel', event => {
    if (!vertexDrag || vertexDrag.pointerId !== event.pointerId) return;
    vertexDrag = null;
    suppressClick = true;
    render();
  }, true);

  baseCanvas.addEventListener('click', event => {
    if (!mode || host.isBusy()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (suppressClick) {
      suppressClick = false;
      return;
    }
    const p = host.point(event);
    if (targetId === null) {
      const areaHit = findAreaAt(p);
      if (areaHit) {
        selectedAreaId = areaHit.id;
        const target = candidateById(areaHit.targetId);
        host.status.className = 'status';
        host.status.textContent = `${target?.number || ''} のポリゴンを選択しました。頂点をドラッグで編集、Deleteキーで削除できます。`;
        render();
        return;
      }
      const target = host.findAt(p);
      if (!target) {
        selectedAreaId = null;
        host.status.className = 'status';
        host.status.textContent = '先にエリアを紐づける丸枠をクリックしてください。';
        render();
        return;
      }
      const existing = areas.find(area => area.targetId === target.id);
      if (existing) {
        selectedAreaId = existing.id;
        host.status.className = 'status';
        host.status.textContent = `${target.number} には既にエリアがあります。頂点をドラッグして編集するかDeleteキーで削除してください。`;
        render();
        return;
      }
      targetId = target.id;
      selectedAreaId = null;
      draft = [];
      preview = null;
      host.status.className = 'status';
      host.status.textContent = `${target.number} を選択しました。ポリゴン頂点を順番にクリックしてください。`;
      render();
      return;
    }

    const closeTolerance = Math.max(host.cssPxToOcrX(11), host.cssPxToOcrY(11));
    if (event.detail >= 2 && draft.length >= 3) {
      completeDraft();
      return;
    }
    if (draft.length >= 3 && Math.hypot(p.x - draft[0][0], p.y - draft[0][1]) <= closeTolerance) {
      completeDraft();
      return;
    }
    draft.push([p.x, p.y]);
    preview = [p.x, p.y];
    host.status.className = 'status';
    host.status.textContent = `ポリゴン作成中：${draft.length}点。3点以上で始点クリックまたはダブルクリックすると確定します。`;
    render();
  }, true);

  baseCanvas.addEventListener('dblclick', event => {
    if (!mode) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);

  document.addEventListener('keydown', event => {
    if (!mode) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      targetId = null;
      draft = [];
      preview = null;
      selectedAreaId = null;
      host.status.className = 'status';
      host.status.textContent = 'エリア作成をキャンセルしました。';
      render();
      return;
    }
    if (event.key === 'Backspace' && targetId !== null && draft.length) {
      event.preventDefault();
      event.stopImmediatePropagation();
      draft.pop();
      render();
      return;
    }
    if (event.key === 'Delete' && selectedAreaId !== null) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const area = areas.find(item => item.id === selectedAreaId);
      const target = area ? candidateById(area.targetId) : null;
      areas = areas.filter(item => item.id !== selectedAreaId);
      selectedAreaId = null;
      host.setDirty(true);
      host.status.className = 'status';
      host.status.textContent = `${target?.number || ''} のポリゴンエリアを削除しました。確定保存するまでDBには反映されません。`;
      render();
    }
  }, true);

  host.saveButton.addEventListener('click', async event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const candidates = host.getCandidates();
    if (host.isBusy() || !candidates.length) return;
    reconcileAreas(true);
    host.setBusy(true);
    host.status.className = 'status';
    host.status.textContent = '番号配置とエリアを保存中…';
    try {
      const response = await fetch(host.numberMapUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pageNumber: host.currentPage(),
          candidates: host.serializeCandidates(),
          areas: serializeAreas(),
          showNumberInMarker: numberLabelCheckbox.checked,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '保存に失敗しました。');
      originalAreas = cloneAreas(areas);
      originalShowNumberInMarker = numberLabelCheckbox.checked;
      host.afterSave(data);
    } catch (error) {
      host.status.className = 'status error';
      host.status.textContent = error.message;
    } finally {
      host.setBusy(false);
    }
  }, true);

  host.resetButton.addEventListener('click', () => {
    areas = cloneAreas(originalAreas);
    numberLabelCheckbox.checked = originalShowNumberInMarker;
    targetId = null;
    draft = [];
    preview = null;
    selectedAreaId = null;
    render();
  }, true);

  window.addEventListener('weld:entry-base-drawn', () => {
    applyMapData();
    reconcileAreas(true);
    syncOverlaySize();
  });

  const canvasObserver = new MutationObserver(syncOverlaySize);
  canvasObserver.observe(baseCanvas, { attributes: true, attributeFilter: ['width', 'height', 'style'] });
  const resizeObserver = 'ResizeObserver' in window ? new ResizeObserver(syncOverlaySize) : null;
  if (resizeObserver) {
    resizeObserver.observe(baseCanvas);
    resizeObserver.observe(viewer);
  }
  new MutationObserver(syncOverlaySize).observe(rotateButton, { childList: true, characterData: true, subtree: true });
  window.addEventListener('resize', syncOverlaySize);

  applyMapData();
  syncOverlaySize();
})();

(() => {
  const current = document.currentScript?.src;
  if (!current || document.getElementById('entryViewerZoomScript')) return;
  const script = document.createElement('script');
  script.id = 'entryViewerZoomScript';
  script.src = new URL('entry_viewer_zoom.js', current).href;
  document.head.appendChild(script);
})();