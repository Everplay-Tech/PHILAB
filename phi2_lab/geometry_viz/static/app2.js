const SIDES = { PRIMARY: 'primary', COMPARISON: 'comparison' };

const state = {
  runs: [],
  summaries: {},
  primaryRunId: null,
  comparisonRunId: null,
  focus: SIDES.PRIMARY,
  selectedLayer: { [SIDES.PRIMARY]: null, [SIDES.COMPARISON]: null },
  selectedMode: { [SIDES.PRIMARY]: null, [SIDES.COMPARISON]: null },
  useMock: true,
  dataSource: 'local', // local | remote
  remote: {
    url: '',
    apiKey: '',
    dataset: 'users',
  },
  atlasMode: 'single',  // 'single', 'dual', 'atlas'
  viewMode: 'residual',  // 'residual', 'geodesic', 'sheaf', 'chart'
};

function apiUrl(path) {
  const mockParam = state.useMock ? '?mock=1' : '';
  return `${path}${mockParam}`;
}

function buildRemoteUrl(path, params = {}) {
  const base = state.remote.url.replace(/\/$/, '');
  const query = new URLSearchParams(params);
  return `${base}/api/platform/geometry${path}?${query.toString()}`;
}

function getApiHeaders() {
  const headers = {};
  if (state.remote.apiKey) {
    headers['X-PhiLab-API-Key'] = state.remote.apiKey;
  }
  return headers;
}

async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    throw new Error(`Request failed: ${resp.status}`);
  }
  return resp.json();
}

async function loadRuns() {
  console.log('[PHILAB] loadRuns() called, useMock:', state.useMock);
  try {
    const url = state.dataSource === 'remote'
      ? buildRemoteUrl('/runs', { dataset: state.remote.dataset })
      : apiUrl('/api/geometry/runs');
    console.log('[PHILAB] Fetching:', url);
    const data = await fetchJson(url, state.dataSource === 'remote' ? { headers: getApiHeaders() } : {});
    console.log('[PHILAB] Got runs:', data);
    state.runs = data.runs || [];

  if (!state.runs.length) {
    const legend = document.getElementById('deltaLegend');
    if (legend) {
      legend.textContent = state.dataSource === 'remote'
        ? 'No runs found. Check your API key or switch to mock data.'
        : 'No runs found. Enable mock mode or place telemetry under results/geometry_viz.';
    }
    const primaryList = document.getElementById('layerListPrimary');
    const comparisonList = document.getElementById('layerListComparison');
    if (primaryList) primaryList.innerHTML = '<div class="legend">No telemetry available.</div>';
    if (comparisonList) comparisonList.innerHTML = '<div class="legend">No telemetry available.</div>';
    renderAll();
    return;
  }

  if (!state.primaryRunId || !state.runs.find((r) => r.run_id === state.primaryRunId)) {
    state.primaryRunId = state.runs[0].run_id;
  }

  const defaultComparison = state.runs.find((r) => r.run_id !== state.primaryRunId)?.run_id || null;
  if (state.comparisonRunId && !state.runs.find((r) => r.run_id === state.comparisonRunId)) {
    state.comparisonRunId = defaultComparison;
  } else if (!state.comparisonRunId) {
    state.comparisonRunId = defaultComparison;
  }

  populateRunSelects();
  console.log('[PHILAB] Populated selects, loading summary for:', state.primaryRunId);
  await ensureSummary(SIDES.PRIMARY, state.primaryRunId);
  if (state.comparisonRunId) {
    await ensureSummary(SIDES.COMPARISON, state.comparisonRunId);
  }

  renderAll();
  console.log('[PHILAB] renderAll complete');
  } catch (err) {
    console.error('[PHILAB] Error in loadRuns:', err);
  }
}

function initAtlasModes() {
  document.getElementById('singleModelBtn').addEventListener('click', () => setAtlasMode('single'));
  document.getElementById('dualModelBtn').addEventListener('click', () => setAtlasMode('dual'));
  document.getElementById('atlasModeBtn').addEventListener('click', () => setAtlasMode('atlas'));

  document.getElementById('residualBtn').addEventListener('click', () => setViewMode('residual'));
  document.getElementById('geodesicBtn').addEventListener('click', () => setViewMode('geodesic'));
  document.getElementById('sheafBtn').addEventListener('click', () => setViewMode('sheaf'));
  document.getElementById('chartBtn').addEventListener('click', () => setViewMode('chart'));
}

function setAtlasMode(mode) {
  state.atlasMode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`${mode}ModelBtn`).classList.add('active');
  applyAtlasMode();
  renderAll();
}

function applyAtlasMode() {
  const comparisonSpine = document.getElementById('comparisonSpine');
  const alignmentArcs = document.getElementById('alignmentArcs');
  const comparisonSelect = document.getElementById('comparisonRunSelect');
  const comparisonLabel = document.querySelector('label[for="comparisonRunSelect"]');
  const comparisonDetails = document.getElementById('comparisonDetails');
  const morphismPanel = document.getElementById('morphismInspector')?.closest('.panel');
  const plotArea = document.getElementById('plotArea');
  const spineRow = document.querySelector('.spine-row');
  const primarySpine = document.getElementById('primarySpine');

  // Reset all to visible
  [comparisonSpine, alignmentArcs, comparisonDetails].forEach(el => {
    if (el) el.style.display = '';
  });
  if (comparisonSelect) comparisonSelect.style.display = '';
  if (comparisonLabel) comparisonLabel.style.display = '';
  if (morphismPanel) morphismPanel.style.display = '';
  if (plotArea) plotArea.className = '';
  if (spineRow) spineRow.classList.remove('single-mode');

  switch (state.atlasMode) {
    case 'single':
      // Hide Run B and comparison elements
      if (comparisonSpine) comparisonSpine.style.display = 'none';
      if (alignmentArcs) alignmentArcs.style.display = 'none';
      if (comparisonSelect) comparisonSelect.style.display = 'none';
      if (comparisonLabel) comparisonLabel.style.display = 'none';
      if (comparisonDetails) comparisonDetails.style.display = 'none';
      if (morphismPanel) morphismPanel.style.display = 'none';
      // Expand Run A spine to full width
      if (spineRow) spineRow.classList.add('single-mode');
      break;

    case 'dual':
      // Show everything (default state) - already reset above
      break;

    case 'atlas':
      // Multi-chart mode - show atlas grid in plot area
      if (plotArea) plotArea.className = 'atlas-grid-mode';
      break;
  }
}

function setViewMode(mode) {
  state.viewMode = mode;
  document.querySelectorAll('#objectToolbar .chip').forEach(chip => chip.classList.remove('active'));
  document.getElementById(`${mode}Btn`).classList.add('active');
  renderAll();
}

function populateRunSelects() {
  const primarySelect = document.getElementById('primaryRunSelect');
  const comparisonSelect = document.getElementById('comparisonRunSelect');

  const clearOptions = (select) => {
    while (select.firstChild) select.removeChild(select.firstChild);
  };
  clearOptions(primarySelect);
  clearOptions(comparisonSelect);

  state.runs.forEach((run) => {
    const optionA = document.createElement('option');
    optionA.value = run.run_id;
    optionA.textContent = `${run.run_id} (${run.adapter_ids.join(', ')})`;
    if (run.run_id === state.primaryRunId) optionA.selected = true;
    primarySelect.appendChild(optionA);

    const optionB = document.createElement('option');
    optionB.value = run.run_id;
    optionB.textContent = `${run.run_id} (${run.adapter_ids.join(', ')})`;
    if (run.run_id === state.comparisonRunId) optionB.selected = true;
    comparisonSelect.appendChild(optionB);
  });

  const noneOption = document.createElement('option');
  noneOption.value = '';
  noneOption.textContent = 'None';
  if (!state.comparisonRunId) noneOption.selected = true;
  comparisonSelect.insertBefore(noneOption, comparisonSelect.firstChild);
}

async function ensureSummary(side, runId) {
  if (!runId) return;
  if (!state.summaries[runId]) {
    state.summaries[runId] = await loadRunSummary(runId);
  }
  seedSelection(side);
}

async function loadRunSummary(runId) {
  if (state.dataSource === 'remote') {
    const url = buildRemoteUrl(`/runs/${runId}`, { dataset: state.remote.dataset });
    return fetchJson(url, { headers: getApiHeaders() });
  }
  const resp = await fetch(apiUrl(`/api/geometry/runs/${runId}`));
  return resp.json();
}

function seedSelection(side) {
  const summary = getSummary(side);
  if (!summary) return;
  const firstLayer = summary.layers[0];
  if (firstLayer && state.selectedLayer[side] === null) {
    state.selectedLayer[side] = firstLayer.layer_index;
    state.selectedMode[side] = firstLayer.residual_modes?.[0]
      ? { layerIndex: firstLayer.layer_index, modeIndex: firstLayer.residual_modes[0].mode_index }
      : null;
  }
}

function getSummary(side) {
  const runId = side === SIDES.PRIMARY ? state.primaryRunId : state.comparisonRunId;
  return runId ? state.summaries[runId] : null;
}

function getOpposite(side) {
  return side === SIDES.PRIMARY ? SIDES.COMPARISON : SIDES.PRIMARY;
}

function getModeCorrespondence() {
  const mode = currentMode();
  const layer = currentLayer();
  const otherSummary = getSummary(getOpposite(state.focus));
  if (!mode || !layer || !otherSummary) return { kind: 'single' };

  const otherLayer = otherSummary.layers.find((l) => l.layer_index === layer.layer_index);
  const counterpart = otherLayer?.residual_modes?.find((m) => m.mode_index === mode.mode_index) || null;

  return counterpart ? { kind: 'morphism', counterpart, otherLayer } : { kind: 'residual' };
}

function currentLayer(side = state.focus) {
  const summary = getSummary(side);
  if (!summary) return null;
  const targetLayer = state.selectedLayer[side];
  return summary.layers.find((l) => l.layer_index === targetLayer) || null;
}

function currentMode(side = state.focus) {
  const summary = getSummary(side);
  if (!summary) return null;
  const selection = state.selectedMode[side];
  if (!selection) return null;
  const layer = summary.layers.find((l) => l.layer_index === selection.layerIndex);
  return layer?.residual_modes.find((m) => m.mode_index === selection.modeIndex) || null;
}

function allModes(side = state.focus) {
  const summary = getSummary(side);
  if (!summary) return [];
  return summary.layers.flatMap((layer) =>
    (layer.residual_modes || []).map((mode) => ({ ...mode, layer_index: layer.layer_index })),
  );
}

function setFocus(side) {
  state.focus = side;
  renderFocusChips();
  renderAll();
}

function renderFocusChips() {
  const primaryChip = document.getElementById('primaryFocusChip');
  const comparisonChip = document.getElementById('comparisonFocusChip');
  if (state.focus === SIDES.PRIMARY) {
    primaryChip.classList.remove('ghost');
    primaryChip.classList.add('focus-chip');
    comparisonChip.classList.add('ghost');
    comparisonChip.classList.remove('focus-chip');
  } else {
    comparisonChip.classList.remove('ghost');
    comparisonChip.classList.add('focus-chip');
    primaryChip.classList.add('ghost');
    primaryChip.classList.remove('focus-chip');
  }
}

function modeSpanStrength(side, layerIdx) {
  const mode = currentMode(side);
  if (!mode || !mode.span_across_layers) return 0;
  const match = mode.span_across_layers.find((span) => span.layer_index === layerIdx);
  return match?.strength || 0;
}

function renderRunLabels() {
  const primaryLabel = document.getElementById('primaryRunLabel');
  const comparisonLabel = document.getElementById('comparisonRunLabel');
  const primarySummary = getSummary(SIDES.PRIMARY);
  const comparisonSummary = getSummary(SIDES.COMPARISON);
  primaryLabel.textContent = primarySummary
    ? `${primarySummary.model_name} · ${primarySummary.adapter_ids.join(', ') || 'no adapters'}`
    : 'Select a run to populate the spine.';
  comparisonLabel.textContent = comparisonSummary
    ? `${comparisonSummary.model_name} · ${comparisonSummary.adapter_ids.join(', ') || 'no adapters'}`
    : 'Add a comparison run to enable overlays.';
}

function renderAlignmentArcs() {
  const svg = document.getElementById('alignmentArcs');
  svg.innerHTML = '';
  const primarySummary = getSummary(SIDES.PRIMARY);
  const comparisonSummary = getSummary(SIDES.COMPARISON);
  if (!primarySummary || !comparisonSummary || !primarySummary.alignment_info) return;

  const alignment = primarySummary.alignment_info;
  const width = 100;
  const height = 600;

  // Assume layers are aligned by index for simplicity
  const maxLayers = Math.max(primarySummary.layers.length, comparisonSummary.layers.length);
  const layerHeight = height / maxLayers;

  for (let i = 0; i < maxLayers; i++) {
    const score = alignment.layer_scores[i] || 0.5;
    const color = score > 0.7 ? '#4fd1c5' : score > 0.4 ? '#fbbf24' : '#e53e3e';
    const thickness = Math.max(1, score * 5);

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M 0 ${i * layerHeight + layerHeight / 2} Q 50 ${i * layerHeight + layerHeight / 2} 100 ${i * layerHeight + layerHeight / 2}`);
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', thickness);
    path.setAttribute('fill', 'none');
    path.style.cursor = 'pointer';
    path.addEventListener('click', () => {
      state.selectedLayer[SIDES.PRIMARY] = i;
      state.selectedLayer[SIDES.COMPARISON] = alignment.layer_map[i] || i;
      setFocus(SIDES.PRIMARY);
    });
    svg.appendChild(path);
  }
}

function renderDeltaLegend() {
  const legend = document.getElementById('deltaLegend');
  if (!legend) return;
  const comparisonSummary = getSummary(SIDES.COMPARISON);
  if (!comparisonSummary) {
    legend.textContent = 'Single-run mode: select Run B to unlock dual spines, morphism overlays across spines, and a residual variety call-out for modes unique to the focused run.';
    return;
  }
  legend.textContent = 'Overlay hints: Δnorm chips compare adapter norm vs the paired spine layer; dashed growth lines are morphisms into the other spine; variety clusters highlight shared regions, while residual variety surfaces points missing from the counterpart.';
}

function renderSpine(side) {
  const containerId = side === SIDES.PRIMARY ? 'layerListPrimary' : 'layerListComparison';
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const summary = getSummary(side);
  const otherSummary = getSummary(getOpposite(side));

  if (!summary) {
    container.innerHTML = '<div class="legend">No run selected.</div>';
    return;
  }

  summary.layers.forEach((layer) => {
    const row = document.createElement('div');
    const spanStrength = modeSpanStrength(side, layer.layer_index);
    row.className =
      'layer-row' + (layer.layer_index === state.selectedLayer[side] && state.focus === side ? ' active' : '');

    const spanOverlay = document.createElement('div');
    spanOverlay.className = 'span-indicator' + (spanStrength > 0.05 ? ' visible' : '');
    spanOverlay.style.opacity = Math.min(1, spanStrength + 0.05);

    const label = document.createElement('div');
    label.textContent = `Layer ${layer.layer_index}`;

    const metrics = document.createElement('div');
    metrics.className = 'metric-bars';

    const normBar = document.createElement('div');
    normBar.className = 'metric-bar';
    normBar.style.width = `${Math.min(100, (layer.adapter_weight_norm || 0) * 30)}%`;

    const rankBar = document.createElement('div');
    rankBar.className = 'rank-bar';
    rankBar.style.width = `${Math.min(100, (layer.effective_rank || 0) * 5)}%`;

    // Mini sparkline for delta_loss over time
    const sparkline = document.createElement('div');
    sparkline.className = 'sparkline';
    const layerTimeline = summary.timeline.filter(t => t.layer_index === layer.layer_index && t.delta_loss_estimate !== null);
    if (layerTimeline.length > 1) {
      const minLoss = Math.min(...layerTimeline.map(t => t.delta_loss_estimate));
      const maxLoss = Math.max(...layerTimeline.map(t => t.delta_loss_estimate));
      const range = maxLoss - minLoss || 1;
      const points = layerTimeline.map((t, i) => `${(i / (layerTimeline.length - 1)) * 60},${20 - ((t.delta_loss_estimate - minLoss) / range) * 16}`).join(' ');
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '60');
      svg.setAttribute('height', '20');
      const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      polyline.setAttribute('points', points);
      polyline.setAttribute('fill', 'none');
      polyline.setAttribute('stroke', '#e53e3e');
      polyline.setAttribute('stroke-width', '1');
      svg.appendChild(polyline);
      sparkline.appendChild(svg);
    }

    const lossChip = document.createElement('div');
    lossChip.className = 'loss-chip ' + (layer.delta_loss_estimate >= 0 ? 'loss-positive' : 'loss-negative');
    lossChip.textContent = (layer.delta_loss_estimate || 0).toFixed(3);

    // Mode indicator glyph
    const modeGlyph = document.createElement('div');
    modeGlyph.className = 'mode-glyph';
    const modeCount = layer.residual_modes.length;
    modeGlyph.textContent = modeCount > 0 ? `${modeCount} modes` : '';
    if (layer.residual_modes.some(m => m.semantic_region)) {
      modeGlyph.classList.add('semantic');
    }

    if (otherSummary) {
      const counterpart = otherSummary.layers.find((l) => l.layer_index === layer.layer_index);
      if (counterpart) {
        const diffChip = document.createElement('div');
        const normDelta = (layer.adapter_weight_norm || 0) - (counterpart.adapter_weight_norm || 0);
        diffChip.className = 'diff-chip';
        diffChip.textContent = `Δnorm ${normDelta >= 0 ? '+' : ''}${normDelta.toFixed(2)}`;
        row.appendChild(diffChip);
      }
    }

    row.addEventListener('click', () => {
      const defaultMode = layer.residual_modes?.[0]?.mode_index;
      state.selectedLayer[side] = layer.layer_index;
      state.selectedMode[side] = defaultMode !== undefined ? { layerIndex: layer.layer_index, modeIndex: defaultMode } : null;
      setFocus(side);
    });

    row.appendChild(spanOverlay);
    row.appendChild(label);
    row.appendChild(metrics);
    row.appendChild(sparkline);
    row.appendChild(lossChip);
    row.appendChild(modeGlyph);
    metrics.appendChild(normBar);
    metrics.appendChild(rankBar);
    container.appendChild(row);
  });
}

function renderRunDetails() {
  const container = document.getElementById('runDetails');
  const primarySummary = getSummary(SIDES.PRIMARY);
  const comparisonSummary = getSummary(SIDES.COMPARISON);
  container.innerHTML = '';
  if (!primarySummary) return;
  const detail = document.createElement('div');
  detail.innerHTML = `
    <div><strong>Run A:</strong> ${primarySummary.run_id}</div>
    <div><strong>Model:</strong> ${primarySummary.model_name}</div>
    ${primarySummary.source_model_name ? `<div><strong>Source Model:</strong> ${primarySummary.source_model_name}</div>` : ''}
    ${primarySummary.target_model_name ? `<div><strong>Target Model:</strong> ${primarySummary.target_model_name}</div>` : ''}
    <div><strong>Adapters:</strong> ${primarySummary.adapter_ids.join(', ') || 'none'}</div>
  `;
  container.appendChild(detail);
  if (comparisonSummary) {
    const compare = document.createElement('div');
    compare.innerHTML = `
      <div><strong>Run B:</strong> ${comparisonSummary.run_id}</div>
      <div><strong>Model:</strong> ${comparisonSummary.model_name}</div>
      ${comparisonSummary.source_model_name ? `<div><strong>Source Model:</strong> ${comparisonSummary.source_model_name}</div>` : ''}
      ${comparisonSummary.target_model_name ? `<div><strong>Target Model:</strong> ${comparisonSummary.target_model_name}</div>` : ''}
      <div><strong>Adapters:</strong> ${comparisonSummary.adapter_ids.join(', ') || 'none'}</div>
    `;
    container.appendChild(compare);
  }
}

function renderComparisonDetails() {
  const container = document.getElementById('comparisonDetails');
  const layer = currentLayer();
  const otherLayer = currentLayer(getOpposite(state.focus));
  const summary = getSummary(state.focus);
  const otherSummary = getSummary(getOpposite(state.focus));

  if (!container) return;
  container.innerHTML = '';
  if (!layer || !summary || !otherSummary || !otherLayer) return;

  const diffGrid = document.createElement('div');
  diffGrid.className = 'diff-grid';

  const makeCard = (title, values) => {
    const card = document.createElement('div');
    card.className = 'diff-card';
    card.innerHTML = `<h4>${title}</h4><div>${values}</div>`;
    return card;
  };

  const normDelta = (layer.adapter_weight_norm || 0) - (otherLayer.adapter_weight_norm || 0);
  const rankDelta = (layer.effective_rank || 0) - (otherLayer.effective_rank || 0);
  const lossDelta = (layer.delta_loss_estimate || 0) - (otherLayer.delta_loss_estimate || 0);

  diffGrid.appendChild(
    makeCard(
      'Adapter weight norm',
      `${summary.run_id}: ${layer.adapter_weight_norm?.toFixed(3) ?? '—'} · ${otherSummary.run_id}: ${
        otherLayer.adapter_weight_norm?.toFixed(3) ?? '—'
      } · Δ ${normDelta >= 0 ? '+' : ''}${normDelta.toFixed(3)}`,
    ),
  );
  diffGrid.appendChild(
    makeCard(
      'Effective rank',
      `${summary.run_id}: ${layer.effective_rank?.toFixed(2) ?? '—'} · ${otherSummary.run_id}: ${
        otherLayer.effective_rank?.toFixed(2) ?? '—'
      } · Δ ${rankDelta >= 0 ? '+' : ''}${rankDelta.toFixed(2)}`,
    ),
  );
  diffGrid.appendChild(
    makeCard(
      'Δloss estimate',
      `${summary.run_id}: ${layer.delta_loss_estimate?.toFixed(4) ?? '—'} · ${otherSummary.run_id}: ${
        otherLayer.delta_loss_estimate?.toFixed(4) ?? '—'
      } · Δ ${lossDelta >= 0 ? '+' : ''}${lossDelta.toFixed(4)}`,
    ),
  );

  container.appendChild(diffGrid);
}

function renderLayerDetails() {
  const container = document.getElementById('layerDetails');
  const layer = currentLayer();
  const mode = currentMode();
  if (!layer) {
    container.innerHTML = '';
    return;
  }
  const examples = mode?.token_examples || layer.residual_modes?.[0]?.token_examples || [];
  const exampleList = examples.map((t) => `<span class="badge">${t}</span>`).join('');
  container.innerHTML = `
    <div><strong>Layer:</strong> ${layer.layer_index}</div>
    <div><strong>Adapter:</strong> ${layer.adapter_id || 'n/a'}</div>
    <div class="badge-row"><strong>Top tokens:</strong> ${exampleList}</div>
    <div><strong>Weight norm:</strong> ${layer.adapter_weight_norm?.toFixed(3) ?? '—'}</div>
    <div><strong>Effective rank:</strong> ${layer.effective_rank?.toFixed(2) ?? '—'}</div>
    <div><strong>Δloss estimate:</strong> ${layer.delta_loss_estimate?.toFixed(4) ?? '—'}</div>
    <div><strong>Residual samples:</strong> ${layer.residual_sample_count}</div>
  `;
}

function renderSelectedModeMeta() {
  const meta = document.getElementById('selectedModeMeta');
  const mode = currentMode();
  const layer = currentLayer();
  const summary = getSummary(state.focus);
  const correspondence = getModeCorrespondence();
  if (!mode || !layer || !summary) {
    meta.textContent = '';
    return;
  }
  const statusLabel =
    correspondence.kind === 'morphism'
      ? 'morphism ↔'
      : correspondence.kind === 'residual'
        ? 'residual variety'
        : 'single spine';
  meta.textContent = `${summary.run_id} · Layer ${layer.layer_index} · Mode ${mode.mode_index} · ${(mode.variance_explained * 100).toFixed(1)}% variance · ${statusLabel}`;
}

function renderTimeline() {
  const svg = document.getElementById('timeline');
  svg.innerHTML = '';
  const layer = currentLayer();
  const mode = currentMode();
  const summary = getSummary(state.focus);
  const otherSummary = getSummary(getOpposite(state.focus));
  if ((!layer || !summary?.timeline) && !mode?.growth_curve?.length) return;

  const layerPoints = summary?.timeline?.filter((t) => t.layer_index === layer?.layer_index) || [];
  const modePoints = mode?.growth_curve || [];
  const otherLayerPoints = otherSummary?.timeline?.filter((t) => t.layer_index === layer?.layer_index) || [];

  const points = modePoints.length ? modePoints : layerPoints;
  if (!points.length) return;

  const width = 400;
  const height = 200;
  const maxStep = Math.max(...points.map((p) => p.step), ...(otherLayerPoints.map((p) => p.step) || [1]), 1);
  const maxGrowth = Math.max(
    ...points.map((p) => p.magnitude || p.adapter_weight_norm || 0),
    ...(otherLayerPoints.map((p) => p.adapter_weight_norm || 0) || [1]),
    1,
  );
  const maxRank = Math.max(...layerPoints.map((p) => p.effective_rank || 0), ...(otherLayerPoints.map((p) => p.effective_rank || 0) || [0]), 1);

  const buildLine = (arr, getY) =>
    arr.map((p) => `${(p.step / maxStep) * (width - 20) + 10},${height - 20 - getY(p)}`).join(' ');

  const growthLine = buildLine(modePoints.length ? modePoints : layerPoints, (p) => ((p.magnitude || p.adapter_weight_norm || 0) / maxGrowth) * 140);
  const rankLine = buildLine(layerPoints, (p) => ((p.effective_rank || 0) / maxRank) * 140);
  const compareLine = buildLine(otherLayerPoints, (p) => ((p.adapter_weight_norm || 0) / maxGrowth) * 140);

  const growthPath = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  growthPath.setAttribute('points', growthLine);
  growthPath.setAttribute('fill', 'none');
  growthPath.setAttribute('stroke', '#f6ad55');
  growthPath.setAttribute('stroke-width', '2');
  svg.appendChild(growthPath);

  if (rankLine) {
    const rankPath = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    rankPath.setAttribute('points', rankLine);
    rankPath.setAttribute('fill', 'none');
    rankPath.setAttribute('stroke', '#4fd1c5');
    rankPath.setAttribute('stroke-width', '2');
    svg.appendChild(rankPath);
  }

  if (otherLayerPoints.length) {
    const comparePath = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    comparePath.setAttribute('points', compareLine);
    comparePath.setAttribute('fill', 'none');
    comparePath.setAttribute('stroke', '#94a3b8');
    comparePath.setAttribute('stroke-width', '2');
    comparePath.setAttribute('stroke-dasharray', '4 2');
    svg.appendChild(comparePath);
  }
}

function renderScatter() {
  const plotArea = document.getElementById('plotArea');
  const svg = document.getElementById('scatterPlot');

  // Handle Atlas Mode - multi-chart grid
  if (state.atlasMode === 'atlas') {
    renderAtlasGrid();
    return;
  }

  // Single chart mode - clear any atlas grid elements
  const existingGrid = plotArea.querySelector('.atlas-chart-grid');
  if (existingGrid) existingGrid.remove();
  if (svg) svg.style.display = '';

  svg.innerHTML = '';
  const mode = currentMode();
  const layer = currentLayer();
  const summary = getSummary(state.focus);

  let coords = [];
  let paths = [];
  let sheafPoints = [];

  if (state.viewMode === 'residual') {
    // Original residual mode view
    if (mode && mode.projection_coords?.length) {
      coords = mode.projection_coords;
    } else if (summary?.alignment_info && state.selectedLayer[state.focus] !== null) {
      // Dual manifold
      const alignment = summary.alignment_info;
      coords = alignment.residual_variety_points.concat(alignment.explained_points);
    }
  } else if (state.viewMode === 'geodesic' && layer) {
    // Show geodesic paths
    const geodesics = layer.geodesic_paths || [];
    paths = geodesics.map(g => g.points);
  } else if (state.viewMode === 'sheaf' && layer) {
    // Show sheaf stalks
    const sheaf = layer.attention_sheaf;
    if (sheaf) {
      sheafPoints = sheaf.base_space || [];
    }
  } else if (state.viewMode === 'chart' && layer) {
    // Show chart atlas
    const charts = layer.chart_atlases || [];
    if (charts.length > 0) {
      coords = charts[0].coordinates;  // First chart
    }
  }

  if (!coords.length && !paths.length && !sheafPoints.length) return;

  const allCoords = [...coords, ...sheafPoints, ...paths.flat()];
  const xs = allCoords.map((c) => c[0]);
  const ys = allCoords.map((c) => c[1]);
  const minX = Math.min(...xs, -1);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, -1);
  const maxY = Math.max(...ys, 1);

  function scaleX(x) {
    return ((x - minX) / (maxX - minX || 1)) * 380 + 10;
  }
  function scaleY(y) {
    return 390 - ((y - minY) / (maxY - minY || 1)) * 380;
  }

  // Render coords
  coords.forEach((c) => {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', scaleX(c[0]));
    circle.setAttribute('cy', scaleY(c[1]));
    circle.setAttribute('r', '3');
    circle.setAttribute('fill', '#4fd1c5');
    circle.setAttribute('opacity', '0.45');
    svg.appendChild(circle);
  });

  // Render sheaf points
  sheafPoints.forEach((c) => {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', scaleX(c[0]));
    circle.setAttribute('cy', scaleY(c[1]));
    circle.setAttribute('r', '5');
    circle.setAttribute('fill', '#fbbf24');
    circle.setAttribute('opacity', '0.7');
    svg.appendChild(circle);
  });

  // Render geodesic paths
  paths.forEach((pathPoints) => {
    if (pathPoints.length < 2) return;
    const points = pathPoints.map(p => `${scaleX(p[0])},${scaleY(p[1])}`).join(' ');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    path.setAttribute('points', points);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#e53e3e');
    path.setAttribute('stroke-width', '2');
    svg.appendChild(path);
  });

  if (mode?.semantic_region?.centroid) {
    const [cx, cy] = mode.semantic_region.centroid;
    const region = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    region.setAttribute('cx', scaleX(cx));
    region.setAttribute('cy', scaleY(cy));
    region.setAttribute('r', `${Math.min(120, (mode.semantic_region.spread || 0.5) * 30)}`);
    region.setAttribute('fill', 'rgba(246, 173, 85, 0.08)');
    region.setAttribute('stroke', '#f6ad55');
    region.setAttribute('stroke-width', '1');
    svg.appendChild(region);
  }
}

function renderAtlasGrid() {
  const plotArea = document.getElementById('plotArea');
  const svg = document.getElementById('scatterPlot');
  const layer = currentLayer();

  // Hide main SVG in atlas mode
  if (svg) svg.style.display = 'none';

  // Remove existing grid
  let grid = plotArea.querySelector('.atlas-chart-grid');
  if (!grid) {
    grid = document.createElement('div');
    grid.className = 'atlas-chart-grid';
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: 100%; height: 100%;';
    plotArea.appendChild(grid);
  }
  grid.innerHTML = '';

  if (!layer) {
    grid.innerHTML = '<div style="grid-column: span 3; text-align: center; color: #64748b; padding: 40px;">Select a layer to view chart atlases</div>';
    return;
  }

  const charts = layer.chart_atlases || [];
  if (charts.length === 0) {
    grid.innerHTML = '<div style="grid-column: span 3; text-align: center; color: #64748b; padding: 40px;">No chart data available for this layer</div>';
    return;
  }

  const chartColors = {
    'PoincareDisk': '#4fd1c5',
    'Stereographic': '#f6ad55',
    'AffinePatch': '#a78bfa'
  };

  charts.forEach(chart => {
    const chartDiv = document.createElement('div');
    chartDiv.className = 'atlas-chart-cell';
    chartDiv.style.cssText = 'background: rgba(30,41,59,0.8); border-radius: 8px; padding: 10px; border: 1px solid #334155;';

    const title = document.createElement('div');
    title.style.cssText = 'font-size: 11px; color: #94a3b8; margin-bottom: 8px; text-align: center; font-weight: 600;';
    title.textContent = chart.chart_type;
    chartDiv.appendChild(title);

    const chartSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chartSvg.setAttribute('viewBox', '0 0 150 150');
    chartSvg.style.cssText = 'width: 100%; height: 120px;';

    const coords = chart.coordinates || [];
    if (coords.length > 0) {
      const xs = coords.map(c => c[0]);
      const ys = coords.map(c => c[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);

      const scaleX = (x) => ((x - minX) / (maxX - minX || 1)) * 130 + 10;
      const scaleY = (y) => 140 - ((y - minY) / (maxY - minY || 1)) * 130;

      const color = chartColors[chart.chart_type] || '#4fd1c5';

      coords.forEach(c => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', scaleX(c[0]));
        circle.setAttribute('cy', scaleY(c[1]));
        circle.setAttribute('r', '2');
        circle.setAttribute('fill', color);
        circle.setAttribute('opacity', '0.6');
        chartSvg.appendChild(circle);
      });
    }

    chartDiv.appendChild(chartSvg);

    // Metadata
    const meta = document.createElement('div');
    meta.style.cssText = 'font-size: 10px; color: #64748b; text-align: center; margin-top: 4px;';
    meta.textContent = `κ=${chart.curvature_scalar?.toFixed(3) || 'n/a'} · ${coords.length} pts`;
    chartDiv.appendChild(meta);

    grid.appendChild(chartDiv);
  });
}

function renderModes() {
  const container = document.getElementById('modesList');
  const countEl = document.getElementById('modeCounts');
  container.innerHTML = '';
  const modes = allModes();
  if (!modes.length) {
    countEl.textContent = '';
    return;
  }
  countEl.textContent = `${modes.length} geometric directions (focused on ${state.focus === SIDES.PRIMARY ? 'Run A' : 'Run B'})`;
  modes
    .slice()
    .sort((a, b) => b.variance_explained - a.variance_explained)
    .forEach((mode) => {
      const card = document.createElement('div');
      const isActive =
        state.selectedMode[state.focus] &&
        state.selectedMode[state.focus].layerIndex === mode.layer_index &&
        state.selectedMode[state.focus].modeIndex === mode.mode_index;
      card.className = 'mode-card' + (isActive ? ' active' : '');
      card.innerHTML = `
        <div><strong>Mode ${mode.mode_index}</strong> · Layer ${mode.layer_index}</div>
        <div class="mode-meta">
          <span>${(mode.variance_explained * 100).toFixed(1)}% variance</span>
          <span>${mode.token_examples.slice(0, 3).join(', ')}</span>
        </div>
        <div>${mode.description || ''}</div>
        ${mode.semantic_region ? `<div class="semantic-category">Category: ${mode.semantic_region.label}</div>` : ''}
      `;
      card.addEventListener('click', () => {
        state.selectedLayer[state.focus] = mode.layer_index;
        state.selectedMode[state.focus] = { layerIndex: mode.layer_index, modeIndex: mode.mode_index };
        renderAll();
      });
      container.appendChild(card);
    });
}

function renderMorphismInspector() {
  const container = document.getElementById('morphismInspector');
  const mode = currentMode();
  const layer = currentLayer();
  const summary = getSummary(state.focus);
  const otherSummary = getSummary(getOpposite(state.focus));
  const alignment = summary?.alignment_info;

  // Always show something useful
  let html = '<div class="morphism-content" style="padding: 8px; background: rgba(79,209,197,0.1); border-radius: 4px; margin-top: 8px;">';

  if (!summary) {
    html += '<p style="color: #94a3b8;">Select a run to see morphism data.</p>';
  } else if (!layer) {
    html += '<p style="color: #94a3b8;">Click a layer in the spine to inspect morphisms.</p>';
  } else if (!mode) {
    html += '<p style="color: #94a3b8;">Click a mode card to see its morphism mapping.</p>';
  } else if (!alignment) {
    html += `
      <div style="margin-bottom: 6px;"><strong style="color: #4fd1c5;">Selected:</strong> Layer ${layer.layer_index} · Mode ${mode.mode_index}</div>
      <p style="color: #94a3b8;">No alignment data for this run.</p>
    `;
  } else {
    const modeKey = `${layer.layer_index}:${mode.mode_index}`;
    const score = alignment.mode_scores[modeKey] || 0;
    const mappedTo = alignment.mode_map[modeKey];
    const scoreColor = score > 0.7 ? '#4fd1c5' : score > 0.4 ? '#fbbf24' : '#e53e3e';

    html += `
      <div style="margin-bottom: 8px;">
        <strong style="color: #4fd1c5;">Mode:</strong>
        <span style="font-family: monospace; background: #1a202c; padding: 2px 6px; border-radius: 3px;">L${layer.layer_index}:M${mode.mode_index}</span>
      </div>
      <div style="margin-bottom: 8px;">
        <strong style="color: #4fd1c5;">Alignment:</strong>
        <span style="color: ${scoreColor}; font-weight: bold;">${(score * 100).toFixed(1)}%</span>
      </div>
      <div style="margin-bottom: 8px;">
        <strong style="color: #4fd1c5;">Maps to:</strong>
        ${mappedTo
          ? `<span style="font-family: monospace; background: #1a202c; padding: 2px 6px; border-radius: 3px;">${mappedTo}</span> in ${alignment.target_model}`
          : '<span style="color: #e53e3e;">Residual (unique to this model)</span>'
        }
      </div>
      <div style="font-size: 11px; color: #64748b; margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155;">
        ${alignment.source_model} → ${alignment.target_model}<br>
        ${Object.keys(alignment.mode_map).length} mapped modes ·
        ${alignment.residual_variety_points.length} residual pts
      </div>
    `;
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderModeInspector() {
  const container = document.getElementById('modeInspector');
  const mode = currentMode();
  const layer = currentLayer();
  const correspondence = getModeCorrespondence();
  if (!mode || !layer) {
    container.innerHTML = '';
    return;
  }

  const dominantLayers = (mode.span_across_layers || [])
    .filter((s) => s.strength > 0.4)
    .map((s) => `L${s.layer_index}`)
    .join(', ');

  const regionTokens = mode.semantic_region?.tokens || mode.token_examples || [];
  const tokenBadges = regionTokens.map((t) => `<span class="badge">${t}</span>`).join('');

  let algebraicBadge = '';
  if (correspondence.kind === 'morphism') {
    algebraicBadge = `<span class="badge">Morphism → Run ${getOpposite(state.focus) === SIDES.PRIMARY ? 'A' : 'B'} L${correspondence.otherLayer.layer_index}·Mode ${correspondence.counterpart.mode_index}</span>`;
  } else if (correspondence.kind === 'residual') {
    algebraicBadge = '<span class="badge">Residual variety (no paired mode)</span>';
  } else {
    algebraicBadge = '<span class="badge">Single-spine variety</span>';
  }

  container.innerHTML = `
    <div><strong>Mode ${mode.mode_index}</strong> lives in layer ${layer.layer_index}.</div>
    <div class="badge-row">
      <span class="badge">${(mode.variance_explained * 100).toFixed(1)}% variance</span>
      <span class="badge">Span: ${dominantLayers || 'localized'}</span>
      <span class="badge">Samples: ${layer.residual_sample_count}</span>
      ${algebraicBadge}
    </div>
    <div class="semantic-region">
      <h4>${mode.semantic_region?.label || 'Semantic region'}</h4>
      <div>Centroid: ${mode.semantic_region?.centroid?.map((c) => c.toFixed(2)).join(', ') || 'n/a'}</div>
      <div>Spread: ${(mode.semantic_region?.spread || 0).toFixed(2)}</div>
      <div class="badge-row">${tokenBadges}</div>
    </div>
  `;
}

function renderAll() {
  renderRunLabels();
  renderDeltaLegend();
  renderAlignmentArcs();
  renderFocusChips();
  renderSpine(SIDES.PRIMARY);
  renderSpine(SIDES.COMPARISON);
  renderRunDetails();
  renderComparisonDetails();
  renderLayerDetails();
  renderTimeline();
  renderScatter();
  renderModes();
  renderModeInspector();
  renderMorphismInspector();
  renderSelectedModeMeta();
}

function loadRemoteConfig() {
  state.remote.url = localStorage.getItem('philab_remote_url') || 'https://api.philab.everplay.tech';
  state.remote.apiKey = localStorage.getItem('philab_api_key') || '';
  state.remote.dataset = localStorage.getItem('philab_dataset') || 'users';
  state.dataSource = localStorage.getItem('philab_data_source') || 'local';
  if (state.dataSource === 'remote') {
    state.useMock = false;
  }
}

async function loadRemoteDatasets() {
  const datasetSelect = document.getElementById('datasetSelect');
  if (!datasetSelect || !state.remote.apiKey) return;
  try {
    const url = `${state.remote.url.replace(/\\/$/, '')}/api/platform/datasets`;
    const datasets = await fetchJson(url, { headers: getApiHeaders() });
    const baseOptions = [
      { value: 'users', label: 'My Runs' },
      { value: 'communities', label: 'Community Curated' },
    ];
    datasetSelect.innerHTML = '';
    baseOptions.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      datasetSelect.appendChild(option);
    });
    datasets.forEach((dataset) => {
      const option = document.createElement('option');
      option.value = dataset.slug;
      option.textContent = `${dataset.name} (${dataset.status})`;
      datasetSelect.appendChild(option);
    });
    if ([...datasetSelect.options].some((opt) => opt.value === state.remote.dataset)) {
      datasetSelect.value = state.remote.dataset;
    }
  } catch (err) {
    console.warn('[PHILAB] Failed to load remote datasets:', err);
  }
}

function wireEvents() {
  const primarySelect = document.getElementById('primaryRunSelect');
  const comparisonSelect = document.getElementById('comparisonRunSelect');
  const mockToggle = document.getElementById('mockToggle');
  const dataSourceSelect = document.getElementById('dataSourceSelect');
  const datasetSelect = document.getElementById('datasetSelect');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const remoteUrlInput = document.getElementById('remoteUrlInput');

  primarySelect.addEventListener('change', async (e) => {
    state.primaryRunId = e.target.value;
    await ensureSummary(SIDES.PRIMARY, state.primaryRunId);
    renderAll();
  });

  comparisonSelect.addEventListener('change', async (e) => {
    state.comparisonRunId = e.target.value || null;
    if (state.comparisonRunId) {
      await ensureSummary(SIDES.COMPARISON, state.comparisonRunId);
    }
    renderAll();
  });

  mockToggle.addEventListener('change', async (e) => {
    state.useMock = e.target.checked;
    state.summaries = {};
    await loadRuns();
  });

  if (dataSourceSelect) dataSourceSelect.addEventListener('change', async (e) => {
    state.dataSource = e.target.value;
    localStorage.setItem('philab_data_source', state.dataSource);
    if (state.dataSource === 'remote') {
      state.useMock = false;
      mockToggle.checked = false;
      mockToggle.disabled = true;
      await loadRemoteDatasets();
    } else {
      mockToggle.disabled = false;
    }
    state.summaries = {};
    await loadRuns();
  });

  if (datasetSelect) datasetSelect.addEventListener('change', async (e) => {
    state.remote.dataset = e.target.value;
    localStorage.setItem('philab_dataset', state.remote.dataset);
    if (state.dataSource === 'remote') {
      state.summaries = {};
      await loadRuns();
    }
  });

  if (apiKeyInput) apiKeyInput.addEventListener('change', async (e) => {
    state.remote.apiKey = e.target.value.trim();
    localStorage.setItem('philab_api_key', state.remote.apiKey);
    if (state.dataSource === 'remote') {
      await loadRemoteDatasets();
      state.summaries = {};
      await loadRuns();
    }
  });

  if (remoteUrlInput) remoteUrlInput.addEventListener('change', async (e) => {
    state.remote.url = e.target.value.trim();
    localStorage.setItem('philab_remote_url', state.remote.url);
    if (state.dataSource === 'remote') {
      await loadRemoteDatasets();
      state.summaries = {};
      await loadRuns();
    }
  });
}

// Tooltip system
let tooltipsEnabled = true;

const TOOLTIPS = {
  'spinesColumn': {
    title: 'Model Spines',
    text: 'Each layer shows adapter weight norm (blue bar), effective rank (teal bar), and loss delta. Click a layer to focus and see its residual modes in the atlas.'
  },
  'geometryCanvas': {
    title: 'Algebraic Geometry Atlas',
    text: 'Visualizes the residual manifold. Points are projections of activation vectors. Clusters indicate semantic groupings the adapter has learned.'
  },
  'scatterPlot': {
    title: 'Residual Mode Projection',
    text: '2D PCA projection of residual activations. Each point is a token\'s representation. Nearby points share semantic properties.'
  },
  'timeline': {
    title: 'Mode Growth Timeline',
    text: 'Shows how adapter weight norms (orange) and effective rank (teal) evolve. Dashed lines show comparison run if selected.'
  },
  'modesList': {
    title: 'Residual Mode Atlas',
    text: 'Principal directions in the residual space, sorted by variance explained. Click a mode to see its projection and semantic region.'
  },
  'primaryRunSelect': {
    title: 'Run A Selection',
    text: 'Primary run to analyze. All visualizations focus on this run unless comparing.'
  },
  'comparisonRunSelect': {
    title: 'Run B Selection',
    text: 'Optional comparison run. Enables dual-spine view, morphism overlays, and residual variety analysis.'
  },
  'mockToggle': {
    title: 'Mock Data Toggle',
    text: 'Use synthetic demo data for testing. Uncheck to load real telemetry from captured phi-2 probing runs.'
  },
  'dataSourceSelect': {
    title: 'Data Source',
    text: 'Switch between local telemetry files and the community platform.'
  },
  'datasetSelect': {
    title: 'Dataset View',
    text: 'Choose your own runs or curated community releases to load in the atlas.'
  },
  'apiKeyInput': {
    title: 'API Key',
    text: 'Set your contributor API key to unlock authenticated datasets. Without a key, the platform returns mock data.'
  },
  'remoteUrlInput': {
    title: 'Platform URL',
    text: 'Remote API base URL for the community platform.'
  },
  'residualBtn': {
    title: 'Residual Modes View',
    text: 'Shows PCA projections of adapter residuals — the "directions" the adapter has learned to push activations.'
  },
  'geodesicBtn': {
    title: 'Geodesics View',
    text: 'Traces token trajectories through the curved manifold. Reveals reasoning chains and attention flow.'
  },
  'sheafBtn': {
    title: 'Sheaf Fields View',
    text: 'Visualizes attention head structure as fiber bundles. Shows how information is gathered across positions.'
  },
  'chartBtn': {
    title: 'Chart Atlas View',
    text: 'Multi-chart representation using different coordinate patches (Poincaré, stereographic, affine).'
  }
};

let tooltipEl = null;

function initTooltips() {
  // Create tooltip element
  tooltipEl = document.createElement('div');
  tooltipEl.className = 'info-tooltip';
  document.body.appendChild(tooltipEl);

  // Create help toggle button
  const helpBtn = document.createElement('button');
  helpBtn.className = 'help-toggle';
  helpBtn.textContent = '?';
  helpBtn.title = 'Hover over UI elements for help';
  document.body.appendChild(helpBtn);

  // Wire up tooltip events for known elements
  Object.keys(TOOLTIPS).forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.setAttribute('data-tooltip', id);
      el.addEventListener('mouseenter', showTooltip);
      el.addEventListener('mousemove', moveTooltip);
      el.addEventListener('mouseleave', hideTooltip);
    }
  });

  // Help button shows/hides all tooltips info
  helpBtn.addEventListener('click', () => {
    alert('PHILAB Geometry Atlas Help\n\n' +
      '• Hover over any UI element for contextual help\n' +
      '• Click layers in the spine to focus\n' +
      '• Click modes to see their projection\n' +
      '• Use Run B for comparison analysis\n' +
      '• Toggle mock data to switch between demo and real telemetry\n\n' +
      'For full documentation, see the PHILAB README.');
  });

  // Tooltip toggle button
  const tooltipToggle = document.createElement('button');
  tooltipToggle.className = 'tooltip-toggle';
  tooltipToggle.textContent = 'TIPS ON';
  tooltipToggle.title = 'Toggle tooltips on/off';
  tooltipToggle.style.cssText = 'position: fixed; top: 10px; right: 10px; z-index: 9999; padding: 10px 16px; border-radius: 6px; border: 2px solid #4fd1c5; background: #1a202c; color: #4fd1c5; cursor: pointer; font-size: 14px; font-weight: bold;';
  document.body.appendChild(tooltipToggle);

  tooltipToggle.addEventListener('click', () => {
    tooltipsEnabled = !tooltipsEnabled;
    tooltipToggle.textContent = tooltipsEnabled ? 'TIPS ON' : 'TIPS OFF';
    tooltipToggle.style.opacity = tooltipsEnabled ? '1' : '0.5';
    tooltipToggle.style.borderStyle = tooltipsEnabled ? 'solid' : 'dashed';
    if (!tooltipsEnabled) {
      hideTooltip();
    }
  });
}

function showTooltip(e) {
  if (!tooltipsEnabled) return;
  const id = e.currentTarget.getAttribute('data-tooltip');
  const info = TOOLTIPS[id];
  if (!info) return;

  tooltipEl.innerHTML = `<h4>${info.title}</h4><p>${info.text}</p>`;
  tooltipEl.classList.add('visible');
  moveTooltip(e);
}

function moveTooltip(e) {
  const x = e.clientX + 15;
  const y = e.clientY + 15;

  // Keep tooltip on screen
  const rect = tooltipEl.getBoundingClientRect();
  const maxX = window.innerWidth - rect.width - 20;
  const maxY = window.innerHeight - rect.height - 20;

  tooltipEl.style.left = Math.min(x, maxX) + 'px';
  tooltipEl.style.top = Math.min(y, maxY) + 'px';
}

function hideTooltip() {
  tooltipEl.classList.remove('visible');
}

window.addEventListener('DOMContentLoaded', async () => {
  loadRemoteConfig();
  const dataSourceSelect = document.getElementById('dataSourceSelect');
  const datasetSelect = document.getElementById('datasetSelect');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const remoteUrlInput = document.getElementById('remoteUrlInput');
  const mockToggle = document.getElementById('mockToggle');
  if (dataSourceSelect) dataSourceSelect.value = state.dataSource;
  if (datasetSelect) datasetSelect.value = state.remote.dataset;
  if (apiKeyInput) apiKeyInput.value = state.remote.apiKey;
  if (remoteUrlInput) remoteUrlInput.value = state.remote.url;
  if (state.dataSource === 'remote' && mockToggle) {
    state.useMock = false;
    mockToggle.checked = false;
    mockToggle.disabled = true;
  }
  initAtlasModes();
  initTooltips();
  wireEvents();
  applyAtlasMode();  // Apply initial atlas mode state
  if (state.dataSource === 'remote') {
    await loadRemoteDatasets();
  }
  await loadRuns();
});
