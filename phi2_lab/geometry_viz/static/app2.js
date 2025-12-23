const SIDES = { PRIMARY: 'primary', COMPARISON: 'comparison' };

const RUNTIME_CONFIG = (typeof window !== 'undefined' && window.__PHILAB_CONFIG__)
  ? window.__PHILAB_CONFIG__
  : {};

const DEFAULT_REMOTE_URL = RUNTIME_CONFIG.apiBaseUrl || 'https://api.technopoets.net';
const LOCK_API_BASE_URL = RUNTIME_CONFIG.lockApiBaseUrl === true;
const DEFAULT_DATA_SOURCE = RUNTIME_CONFIG.defaultDataSource || 'remote';
const DEFAULT_DATASET = RUNTIME_CONFIG.defaultDataset || 'communities';
const ALLOW_LOCAL_MODE = RUNTIME_CONFIG.allowLocalMode !== false;
const ALLOW_MOCK_TOGGLE = RUNTIME_CONFIG.allowMockToggle !== false;
const ENABLE_PLOTLY_3D = RUNTIME_CONFIG.enablePlotly3d === true;
const REMEMBER_KEY_DEFAULT = RUNTIME_CONFIG.rememberKeyDefault === true;

const state = {
  runs: [],
  summaries: {},
  primaryRunId: null,
  comparisonRunId: null,
  focus: SIDES.PRIMARY,
  selectedLayer: { [SIDES.PRIMARY]: null, [SIDES.COMPARISON]: null },
  selectedMode: { [SIDES.PRIMARY]: null, [SIDES.COMPARISON]: null },
  useMock: false,
  dataSource: DEFAULT_DATA_SOURCE, // local | remote
  remote: {
    url: '',
    apiKey: '',
    dataset: DEFAULT_DATASET,
  },
  atlasMode: 'single',  // 'single', 'dual', 'atlas'
  viewMode: 'residual',  // 'residual', 'geodesic', 'sheaf', 'chart', 'webgl3d', 'plotly3d'
  adapterGroup: 'all',
  showTrails: true,
  colorMode: 'layer',
  trailColor: '#fbbf24',
  trailColorMode: 'custom',
  csvScope: 'current',
};

let webglScene = null;
let webglRenderer = null;
let webglCamera = null;
let webglPoints = null;
let webglTrails = null;
let webglControls = null;
let webglRaycaster = null;
let webglHoverIndex = null;

function apiUrl(path) {
  const mockParam = state.useMock ? '?mock=1' : '';
  return `${path}${mockParam}`;
}

function _getRememberKeyPreference() {
  const stored = localStorage.getItem('philab_remember_key');
  if (stored === null) return REMEMBER_KEY_DEFAULT;
  return stored === 'true';
}

function _setRememberKeyPreference(enabled) {
  localStorage.setItem('philab_remember_key', enabled ? 'true' : 'false');
}

function _loadApiKey({ rememberKey }) {
  // Back-compat migration: older builds stored the key in localStorage without a remember toggle.
  const legacy = localStorage.getItem('philab_api_key');
  const rememberFlag = localStorage.getItem('philab_remember_key');
  if (legacy && rememberFlag === null) {
    sessionStorage.setItem('philab_api_key', legacy);
    localStorage.removeItem('philab_api_key');
    localStorage.setItem('philab_remember_key', 'false');
  }

  if (rememberKey) {
    return localStorage.getItem('philab_api_key') || sessionStorage.getItem('philab_api_key') || '';
  }
  return sessionStorage.getItem('philab_api_key') || '';
}

function _persistApiKey({ apiKey, rememberKey }) {
  sessionStorage.setItem('philab_api_key', apiKey);
  if (rememberKey) {
    localStorage.setItem('philab_api_key', apiKey);
  } else {
    localStorage.removeItem('philab_api_key');
  }
}

function buildRemoteUrl(path, params = {}) {
  const base = state.remote.url.replace(/\/$/, '');
  const query = new URLSearchParams(params);
  if (!state.remote.apiKey) {
    query.set('public', '1');
  }
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

    populateAdapterGroups();

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
    const legend = document.getElementById('deltaLegend');
    if (legend) {
      legend.textContent = `Error loading runs: ${err.message}`;
      legend.style.color = '#ef4444';
    }
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
  document.getElementById('webgl3dBtn').addEventListener('click', () => setViewMode('webgl3d'));
  const plotlyBtn = document.getElementById('plotly3dBtn');
  if (!ENABLE_PLOTLY_3D) {
    if (plotlyBtn) plotlyBtn.classList.add('hidden');
  } else if (plotlyBtn) {
    plotlyBtn.addEventListener('click', () => setViewMode('plotly3d'));
  }
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
  if (mode === 'plotly3d' && !ENABLE_PLOTLY_3D) {
    mode = 'webgl3d';
  }
  state.viewMode = mode;
  document.querySelectorAll('#objectToolbar .chip').forEach(chip => chip.classList.remove('active'));
  const chip = document.getElementById(`${mode}Btn`);
  if (chip) chip.classList.add('active');
  renderAll();
}

function init3DControls() {
  const adapterSelect = document.getElementById('adapterGroupSelect');
  const trailToggle = document.getElementById('trailToggle');
  const trailColorInput = document.getElementById('trailColorInput');
  const trailColorModeToggle = document.getElementById('trailColorModeToggle');
  const exportBtn = document.getElementById('export3dBtn');
  const resetBtn = document.getElementById('reset3dBtn');
  const exportCsvBtn = document.getElementById('export3dCsvBtn');
  const colorModeSelect = document.getElementById('colorModeSelect');
  const csvScopeSelect = document.getElementById('csvScopeSelect');
  if (adapterSelect) {
    adapterSelect.addEventListener('change', (e) => {
      state.adapterGroup = e.target.value;
      renderAll();
    });
  }
  if (trailToggle) {
    trailToggle.addEventListener('change', (e) => {
      state.showTrails = e.target.checked;
      renderAll();
    });
  }
  if (trailColorInput) {
    trailColorInput.value = state.trailColor;
    trailColorInput.addEventListener('change', (e) => {
      state.trailColor = e.target.value;
      renderAll();
    });
  }
  if (trailColorModeToggle) {
    trailColorModeToggle.checked = state.trailColorMode === 'adapter';
    trailColorModeToggle.addEventListener('change', (e) => {
      state.trailColorMode = e.target.checked ? 'adapter' : 'custom';
      renderAll();
    });
  }
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      export3DImage();
    });
  }
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      reset3DCamera();
    });
  }
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener('click', () => {
      export3DPointsCsv();
    });
  }
  if (colorModeSelect) {
    colorModeSelect.addEventListener('change', (e) => {
      state.colorMode = e.target.value;
      renderAll();
    });
  }
  if (csvScopeSelect) {
    csvScopeSelect.value = state.csvScope;
    csvScopeSelect.addEventListener('change', (e) => {
      state.csvScope = e.target.value;
    });
  }
}

function populateAdapterGroups() {
  const adapterSelect = document.getElementById('adapterGroupSelect');
  if (!adapterSelect) return;
  const adapters = new Set();
  state.runs.forEach((run) => {
    (run.adapter_ids || []).forEach((adapterId) => adapters.add(adapterId));
  });
  const current = state.adapterGroup || 'all';
  adapterSelect.innerHTML = '';
  const allOption = document.createElement('option');
  allOption.value = 'all';
  allOption.textContent = 'All';
  adapterSelect.appendChild(allOption);
  [...adapters].sort().forEach((adapterId) => {
    const option = document.createElement('option');
    option.value = adapterId;
    option.textContent = adapterId;
    adapterSelect.appendChild(option);
  });
  if ([...adapterSelect.options].some((opt) => opt.value === current)) {
    adapterSelect.value = current;
  } else {
    adapterSelect.value = 'all';
    state.adapterGroup = 'all';
  }
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

  if (state.viewMode === 'webgl3d' || state.viewMode === 'plotly3d') {
    render3D();
    return;
  }

  // Single chart mode - clear any atlas grid elements
  const existingGrid = plotArea.querySelector('.atlas-chart-grid');
  if (existingGrid) existingGrid.remove();
  if (svg) svg.style.display = '';
  hide3DContainers();

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

function hide3DContainers() {
  const webglContainer = document.getElementById('webglContainer');
  const plotlyContainer = document.getElementById('plotlyContainer');
  const message = document.getElementById('threeMessage');
  const legend = document.getElementById('threeLegend');
  const scale = document.getElementById('threeLegendScale');
  const tooltip = document.getElementById('threeTooltip');
  if (webglContainer) webglContainer.classList.add('hidden');
  if (plotlyContainer) plotlyContainer.classList.add('hidden');
  if (message) message.classList.add('hidden');
  if (legend) legend.classList.add('hidden');
  if (scale) scale.classList.add('hidden');
  if (tooltip) tooltip.classList.add('hidden');
}

function render3D() {
  const plotArea = document.getElementById('plotArea');
  const existingGrid = plotArea?.querySelector('.atlas-chart-grid');
  if (existingGrid) existingGrid.remove();
  const svg = document.getElementById('scatterPlot');
  if (svg) svg.style.display = 'none';
  if (state.viewMode === 'webgl3d') {
    renderWebGL();
  } else if (state.viewMode === 'plotly3d' && ENABLE_PLOTLY_3D) {
    renderPlotly3D();
  } else {
    renderWebGL();
  }
}

function get3DCoords(mode) {
  if (!mode) return null;
  const coords3d = mode.projection_coords_3d;
  if (!coords3d || !coords3d.length) return null;
  return coords3d;
}

function getAdapterIdForLayer(summary, layer) {
  if (state.adapterGroup && state.adapterGroup !== 'all') {
    return state.adapterGroup;
  }
  if (layer?.adapter_id) return layer.adapter_id;
  const adapters = summary?.adapter_ids || [];
  return adapters.length ? adapters[0] : 'base';
}

function getAdapterLegendIds(summary, layer) {
  const adapters = summary?.adapter_ids || [];
  const ids = [];
  const add = (value) => {
    if (!value || ids.includes(value)) return;
    ids.push(value);
  };
  if (layer?.adapter_id) add(layer.adapter_id);
  if (state.adapterGroup && state.adapterGroup !== 'all') add(state.adapterGroup);
  adapters.forEach((adapterId) => add(adapterId));
  return ids;
}

function getSelectedModeKey() {
  const layer = currentLayer();
  const mode = currentMode();
  if (!layer || !mode) return null;
  return { layerIndex: layer.layer_index, modeIndex: mode.mode_index };
}

async function collectTrajectoryPoints(groupId) {
  const key = getSelectedModeKey();
  if (!key) return [];
  const runs = state.runs.filter((run) => {
    if (groupId === 'all') return true;
    return (run.adapter_ids || []).includes(groupId);
  });
  const points = [];
  for (const run of runs) {
    if (!state.summaries[run.run_id]) {
      try {
        state.summaries[run.run_id] = await loadRunSummary(run.run_id);
      } catch (err) {
        continue;
      }
    }
    const summary = state.summaries[run.run_id];
    const layer = summary?.layers?.find((l) => l.layer_index === key.layerIndex);
    const mode = layer?.residual_modes?.find((m) => m.mode_index === key.modeIndex);
    const coords = get3DCoords(mode);
    if (!coords || !coords.length) continue;
    const centroid = coords.reduce(
      (acc, pt) => [acc[0] + pt[0], acc[1] + pt[1], acc[2] + pt[2]],
      [0, 0, 0]
    ).map((value) => value / coords.length);
    points.push({
      run_id: run.run_id,
      created_at: run.created_at || 0,
      centroid,
    });
  }
  return points.sort((a, b) => a.created_at - b.created_at);
}

function show3DMessage(text) {
  const message = document.getElementById('threeMessage');
  if (!message) return;
  message.textContent = text;
  message.classList.remove('hidden');
}

function update3DLegend() {
  const legend = document.getElementById('threeLegend');
  const scale = document.getElementById('threeLegendScale');
  if (!legend) return;
  const mode = currentMode();
  const layer = currentLayer();
  const coords = get3DCoords(mode);
  if (!coords) {
    legend.classList.add('hidden');
    if (scale) scale.classList.add('hidden');
    return;
  }
  const variance = mode?.variance_explained ? (mode.variance_explained * 100).toFixed(2) : 'n/a';
  const layerIndex = layer?.layer_index ?? 'n/a';
  const adapter = state.adapterGroup === 'all' ? 'all adapters' : state.adapterGroup;
  const trails = state.showTrails ? 'on' : 'off';
  const colorMode = state.colorMode;
  const trailLabel = state.trailColorMode === 'adapter' ? 'adapter' : state.trailColor;
  legend.innerHTML = `<strong>3D Mode View.</strong> Layer ${layerIndex}, Mode ${mode.mode_index}, ` +
    `${coords.length} points, variance ${variance}%. Group: ${adapter}. Trails: ${trails} (${trailLabel}). Color: ${colorMode}.`;
  legend.classList.remove('hidden');
  if (scale) {
    if (colorMode === 'layer') {
      scale.innerHTML = `Layer color gradient (L0 → Lmax). Current layer: ${layerIndex}.<div class="scale-bar"></div>`;
    } else {
      renderAdapterLegend(scale, getAdapterLegendIds(getSummary(state.focus), layer));
    }
    scale.classList.remove('hidden');
  }
}

function renderAdapterLegend(container, adapterIds) {
  container.innerHTML = '';
  const label = document.createElement('div');
  label.textContent = adapterIds.length
    ? 'Adapter color key:'
    : 'Adapter color key: no adapters detected.';
  container.appendChild(label);
  if (!adapterIds.length) return;
  const swatchWrap = document.createElement('div');
  swatchWrap.className = 'adapter-swatches';
  adapterIds.forEach((adapterId) => {
    const row = document.createElement('div');
    row.className = 'adapter-swatch-row';
    const swatch = document.createElement('span');
    swatch.className = 'adapter-swatch';
    swatch.style.backgroundColor = colorForAdapter(adapterId);
    const text = document.createElement('span');
    text.textContent = adapterId;
    row.appendChild(swatch);
    row.appendChild(text);
    swatchWrap.appendChild(row);
  });
  container.appendChild(swatchWrap);
}

function getTrailColor() {
  if (state.trailColorMode === 'adapter' && state.adapterGroup !== 'all') {
    return colorForAdapter(state.adapterGroup);
  }
  return state.trailColor || '#fbbf24';
}

function renderWebGL() {
  const webglContainer = document.getElementById('webglContainer');
  const plotlyContainer = document.getElementById('plotlyContainer');
  if (!webglContainer) return;
  if (typeof THREE === 'undefined') {
    hide3DContainers();
    show3DMessage('Three.js not available for WebGL view.');
    return;
  }
  webglContainer.classList.remove('hidden');
  if (plotlyContainer) plotlyContainer.classList.add('hidden');

  const summary = getSummary(state.focus);
  const mode = currentMode();
  const coords = get3DCoords(mode);
  if (!coords) {
    hide3DContainers();
    show3DMessage('3D data unavailable for this mode.');
    return;
  }
  const message = document.getElementById('threeMessage');
  if (message) message.classList.add('hidden');

  if (!webglRenderer) {
    webglRenderer = new THREE.WebGLRenderer({ antialias: true });
    webglRenderer.setPixelRatio(window.devicePixelRatio || 1);
    webglContainer.innerHTML = '';
    webglContainer.appendChild(webglRenderer.domElement);
  }

  const width = webglContainer.clientWidth || 800;
  const height = webglContainer.clientHeight || 420;
  webglRenderer.setSize(width, height);

  webglScene = new THREE.Scene();
  webglScene.background = new THREE.Color(0x0f1626);
  webglCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100);

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(coords.flat());
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const layer = currentLayer();
  const layerIndex = layer?.layer_index ?? 0;
  const adapterId = getAdapterIdForLayer(summary, layer);
  const pointColor = state.colorMode === 'adapter'
    ? colorForAdapter(adapterId)
    : colorForLayer(layerIndex);
  const material = new THREE.PointsMaterial({ color: pointColor, size: 0.06, transparent: true, opacity: 0.7 });
  webglPoints = new THREE.Points(geometry, material);
  webglScene.add(webglPoints);

  const axesHelper = new THREE.AxesHelper(1.5);
  webglScene.add(axesHelper);
  update3DLegend();

  webglControls = new THREE.OrbitControls(webglCamera, webglRenderer.domElement);
  autoCenterCamera(coords);
  webglRaycaster = new THREE.Raycaster();
  webglRenderer.domElement.onmousemove = handleWebGLHover;

  if (state.showTrails) {
    collectTrajectoryPoints(state.adapterGroup).then((points) => {
      if (!points.length) return;
      const trailGeometry = new THREE.BufferGeometry();
      const trailPositions = new Float32Array(points.flatMap((p) => p.centroid));
      trailGeometry.setAttribute('position', new THREE.BufferAttribute(trailPositions, 3));
      const lineMaterial = new THREE.LineBasicMaterial({ color: getTrailColor() });
      webglTrails = new THREE.Line(trailGeometry, lineMaterial);
      webglScene.add(webglTrails);
      webglRenderer.render(webglScene, webglCamera);
    });
  }

  webglRenderer.render(webglScene, webglCamera);
}

function renderPlotly3D() {
  const plotlyContainer = document.getElementById('plotlyContainer');
  const webglContainer = document.getElementById('webglContainer');
  if (!plotlyContainer) return;
  if (typeof Plotly === 'undefined') {
    hide3DContainers();
    show3DMessage('Plotly not available for 3D view.');
    return;
  }
  plotlyContainer.classList.remove('hidden');
  if (webglContainer) webglContainer.classList.add('hidden');

  const mode = currentMode();
  const coords = get3DCoords(mode);
  if (!coords) {
    hide3DContainers();
    show3DMessage('3D data unavailable for this mode.');
    return;
  }
  const message = document.getElementById('threeMessage');
  if (message) message.classList.add('hidden');

  const xs = coords.map((c) => c[0]);
  const ys = coords.map((c) => c[1]);
  const zs = coords.map((c) => c[2]);
  const summary = getSummary(state.focus);
  const layer = currentLayer();
  const layerIndex = layer?.layer_index ?? 0;
  const adapterId = getAdapterIdForLayer(summary, layer);
  const color = state.colorMode === 'adapter'
    ? colorForAdapter(adapterId)
    : colorForLayer(layerIndex);
  const trace = {
    x: xs,
    y: ys,
    z: zs,
    mode: 'markers',
    type: 'scatter3d',
    marker: { size: 3, color, opacity: 0.7 },
    text: coords.map((c, idx) => `Point ${idx}<br>x=${c[0].toFixed(3)} y=${c[1].toFixed(3)} z=${c[2].toFixed(3)}`),
    hoverinfo: 'text',
    name: 'Residual mode',
  };

  const traces = [trace];
  update3DLegend();
  if (state.showTrails) {
    collectTrajectoryPoints(state.adapterGroup).then((points) => {
      if (!points.length) {
        Plotly.newPlot(plotlyContainer, traces, plotlyLayout(), { displayModeBar: false });
        return;
      }
      const trail = {
        x: points.map((p) => p.centroid[0]),
        y: points.map((p) => p.centroid[1]),
        z: points.map((p) => p.centroid[2]),
        mode: 'lines+markers',
        type: 'scatter3d',
        marker: { size: 4, color: getTrailColor() },
        line: { color: getTrailColor(), width: 3 },
        name: 'Checkpoint trail',
      };
      Plotly.newPlot(plotlyContainer, [...traces, trail], plotlyLayout(), { displayModeBar: false });
    });
  } else {
    Plotly.newPlot(plotlyContainer, traces, plotlyLayout(), { displayModeBar: false });
  }
}

function export3DImage() {
  if (state.viewMode === 'webgl3d') {
    if (!webglRenderer) {
      show3DMessage('WebGL renderer is not initialized.');
      return;
    }
    const dataUrl = webglRenderer.domElement.toDataURL('image/png');
    downloadImage(dataUrl, 'philab_webgl_3d.png');
    return;
  }
  if (state.viewMode === 'plotly3d') {
    const plotlyContainer = document.getElementById('plotlyContainer');
    if (!plotlyContainer || typeof Plotly === 'undefined') {
      show3DMessage('Plotly is not available.');
      return;
    }
    Plotly.toImage(plotlyContainer, { format: 'png', width: 900, height: 600 }).then((dataUrl) => {
      downloadImage(dataUrl, 'philab_plotly_3d.png');
    });
    return;
  }
  show3DMessage('Switch to a 3D view before exporting.');
}

function export3DPointsCsv() {
  const layer = currentLayer();
  const mode = currentMode();
  if (!layer || !mode) {
    show3DMessage('Select a residual mode with 3D data before exporting.');
    return;
  }
  const header = [
    'run_id',
    'run_created_at',
    'run_description',
    'model_name',
    'source_model_name',
    'target_model_name',
    'adapter_ids',
    'alignment_info',
    'timeline',
    'point_index',
    'x',
    'y',
    'z',
    'layer_index',
    'mode_index',
    'adapter_id',
    'adapter_weight_norm',
    'effective_rank',
    'delta_loss_estimate',
    'residual_sample_count',
    'chart_atlases',
    'geodesic_paths',
    'attention_sheaf',
    'mode_eigenvalue',
    'variance_explained',
    'mode_description',
    'token_examples',
    'projection_coords_2d',
    'projection_coords_3d',
    'span_across_layers',
    'growth_curve',
    'semantic_region',
    'spectral_bundle',
  ];
  const selectedLayerIndex = layer.layer_index;
  const selectedModeIndex = mode.mode_index;
  const focusRunId = state.focus === SIDES.COMPARISON ? state.comparisonRunId : state.primaryRunId;
  const runs = state.runs.filter((run) => {
    if (state.csvScope === 'current') return run.run_id === focusRunId;
    if (state.csvScope === 'group') {
      if (state.adapterGroup === 'all') return true;
      return (run.adapter_ids || []).includes(state.adapterGroup);
    }
    return true;
  });
  Promise.all(runs.map(async (run) => {
    if (!state.summaries[run.run_id]) {
      try {
        state.summaries[run.run_id] = await loadRunSummary(run.run_id);
      } catch (err) {
        return null;
      }
    }
    return state.summaries[run.run_id];
  })).then((loaded) => {
    const lines = [];
    loaded.filter(Boolean).forEach((summary) => {
      const targetLayer = summary.layers?.find((l) => l.layer_index === selectedLayerIndex);
      const targetMode = targetLayer?.residual_modes?.find((m) => m.mode_index === selectedModeIndex);
      const coords = get3DCoords(targetMode);
      if (!coords) return;
      const adapterId = getAdapterIdForLayer(summary, targetLayer);
      coords.forEach((c, idx) => {
        lines.push([
          summary.run_id,
          summary.created_at,
          summary.description,
          summary.model_name,
          summary.source_model_name,
          summary.target_model_name,
          summary.adapter_ids,
          summary.alignment_info,
          summary.timeline,
          idx,
          c[0],
          c[1],
          c[2],
          targetLayer.layer_index,
          targetMode.mode_index,
          adapterId || '',
          targetLayer.adapter_weight_norm,
          targetLayer.effective_rank,
          targetLayer.delta_loss_estimate,
          targetLayer.residual_sample_count,
          targetLayer.chart_atlases,
          targetLayer.geodesic_paths,
          targetLayer.attention_sheaf,
          targetMode.eigenvalue,
          targetMode.variance_explained ?? '',
          targetMode.description,
          targetMode.token_examples,
          targetMode.projection_coords,
          targetMode.projection_coords_3d,
          targetMode.span_across_layers,
          targetMode.growth_curve,
          targetMode.semantic_region,
          targetMode.spectral_bundle,
        ].map(csvEscape).join(','));
      });
    });
    if (!lines.length) {
      show3DMessage('No 3D points available for the selected CSV scope.');
      return;
    }
    const csv = [header.join(','), ...lines].join('\n');
    const filename = `philab_3d_points_${state.csvScope}_layer${layer.layer_index}_mode${mode.mode_index}.csv`;
    downloadText(csv, filename);
  });
}

function downloadImage(dataUrl, filename) {
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function downloadText(content, filename) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  if (value === null || value === undefined) return '';
  let text;
  if (typeof value === 'object') {
    try {
      text = JSON.stringify(value);
    } catch (err) {
      text = String(value);
    }
  } else {
    text = String(value);
  }
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function plotlyLayout() {
  return {
    margin: { l: 0, r: 0, t: 10, b: 0 },
    paper_bgcolor: '#0f1626',
    plot_bgcolor: '#0f1626',
    scene: {
      xaxis: { color: '#94a3b8' },
      yaxis: { color: '#94a3b8' },
      zaxis: { color: '#94a3b8' },
    },
    showlegend: false,
  };
}

function colorForLayer(layerIndex) {
  const maxLayer = Math.max(1, ...state.runs.map((run) => run.layer_count || 31));
  const t = Math.min(1, Math.max(0, layerIndex / maxLayer));
  const start = [56, 189, 248]; // blue
  const mid = [34, 197, 94]; // green
  const end = [249, 115, 22]; // orange
  const blend = (a, b, t) => Math.round(a + (b - a) * t);
  const first = [
    blend(start[0], mid[0], t),
    blend(start[1], mid[1], t),
    blend(start[2], mid[2], t),
  ];
  const second = [
    blend(mid[0], end[0], t),
    blend(mid[1], end[1], t),
    blend(mid[2], end[2], t),
  ];
  const color = t < 0.5
    ? first
    : second;
  const hex = color.map((v) => v.toString(16).padStart(2, '0')).join('');
  return `#${hex}`;
}

function colorForAdapter(adapterId) {
  const palette = [
    '#38bdf8',
    '#22c55e',
    '#f97316',
    '#e879f9',
    '#facc15',
    '#fb7185',
    '#a78bfa',
    '#2dd4bf',
    '#60a5fa',
    '#f472b6',
  ];
  const key = adapterId || 'base';
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = ((hash << 5) - hash) + key.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % palette.length;
  return palette[index];
}

function autoCenterCamera(coords) {
  if (!webglCamera || !coords.length) return;
  const box = new THREE.Box3();
  const vector = new THREE.Vector3();
  coords.forEach((pt) => {
    vector.set(pt[0], pt[1], pt[2]);
    box.expandByPoint(vector);
  });
  const size = new THREE.Vector3();
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  const center = new THREE.Vector3();
  box.getCenter(center);
  const distance = maxDim ? maxDim * 2.5 : 6;
  webglCamera.position.set(center.x, center.y, center.z + distance);
  if (webglControls) {
    webglControls.target.copy(center);
    webglControls.update();
  } else {
    webglCamera.lookAt(center);
  }
}

function reset3DCamera() {
  const mode = currentMode();
  const coords = get3DCoords(mode);
  if (coords) {
    autoCenterCamera(coords);
    if (webglRenderer && webglScene && webglCamera) {
      webglRenderer.render(webglScene, webglCamera);
    }
    return;
  }
  show3DMessage('No 3D data to reset.');
}

function handleWebGLHover(event) {
  if (!webglRaycaster || !webglCamera || !webglPoints) return;
  const tooltip = document.getElementById('threeTooltip');
  if (!tooltip) return;
  const rect = webglRenderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1
  );
  webglRaycaster.setFromCamera(mouse, webglCamera);
  webglRaycaster.params.Points.threshold = 0.08;
  const intersects = webglRaycaster.intersectObject(webglPoints);
  if (!intersects.length) {
    tooltip.classList.add('hidden');
    return;
  }
  const index = intersects[0].index;
  if (index === webglHoverIndex) return;
  webglHoverIndex = index;
  const mode = currentMode();
  const coords = get3DCoords(mode);
  const point = coords[index];
  tooltip.innerHTML = `Point ${index}<br>x=${point[0].toFixed(3)} y=${point[1].toFixed(3)} z=${point[2].toFixed(3)}`;
  tooltip.style.left = `${event.clientX + 12}px`;
  tooltip.style.top = `${event.clientY + 12}px`;
  tooltip.classList.remove('hidden');
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
  const rememberKey = _getRememberKeyPreference();
  state.remote.apiKey = _loadApiKey({ rememberKey });
  state.remote.url = LOCK_API_BASE_URL
    ? DEFAULT_REMOTE_URL
    : (localStorage.getItem('philab_remote_url') || DEFAULT_REMOTE_URL);
  state.remote.dataset = localStorage.getItem('philab_dataset') || DEFAULT_DATASET;
  state.dataSource = ALLOW_LOCAL_MODE
    ? (localStorage.getItem('philab_data_source') || DEFAULT_DATA_SOURCE)
    : 'remote';
  if (state.dataSource === 'remote') state.useMock = false;
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
  const rememberKeyToggle = document.getElementById('rememberKeyToggle');

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

  if (mockToggle) {
    if (!ALLOW_MOCK_TOGGLE) {
      mockToggle.checked = false;
      mockToggle.disabled = true;
      mockToggle.closest('label')?.classList.add('hidden');
    } else {
      mockToggle.addEventListener('change', async (e) => {
        state.useMock = e.target.checked;
        state.summaries = {};
        await loadRuns();
      });
    }
  }

  if (dataSourceSelect) dataSourceSelect.addEventListener('change', async (e) => {
    state.dataSource = e.target.value;
    localStorage.setItem('philab_data_source', state.dataSource);
    if (state.dataSource === 'remote') {
      state.useMock = false;
      if (mockToggle) {
        mockToggle.checked = false;
        mockToggle.disabled = true;
      }
      await loadRemoteDatasets();
    } else {
      if (mockToggle) mockToggle.disabled = false;
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

  if (rememberKeyToggle) {
    rememberKeyToggle.addEventListener('change', () => {
      const enabled = !!rememberKeyToggle.checked;
      _setRememberKeyPreference(enabled);
      _persistApiKey({ apiKey: state.remote.apiKey || '', rememberKey: enabled });
    });
  }

  if (apiKeyInput) apiKeyInput.addEventListener('change', async (e) => {
    state.remote.apiKey = e.target.value.trim();
    const rememberKey = rememberKeyToggle ? !!rememberKeyToggle.checked : _getRememberKeyPreference();
    _persistApiKey({ apiKey: state.remote.apiKey, rememberKey });
    if (state.dataSource === 'remote') {
      await loadRemoteDatasets();
      state.summaries = {};
      await loadRuns();
    }
  });

  if (remoteUrlInput) remoteUrlInput.addEventListener('change', async (e) => {
    if (LOCK_API_BASE_URL) return;
    state.remote.url = e.target.value.trim();
    localStorage.setItem('philab_remote_url', state.remote.url);
    if (state.dataSource === 'remote') {
      await loadRemoteDatasets();
      state.summaries = {};
      await loadRuns();
    }
  });
}

function applyDeploymentLocks() {
  const dataSourceSelect = document.getElementById('dataSourceSelect');
  const remoteUrlInput = document.getElementById('remoteUrlInput');
  const mockToggle = document.getElementById('mockToggle');

  if (!ALLOW_LOCAL_MODE && dataSourceSelect) {
    dataSourceSelect.value = 'remote';
    dataSourceSelect.disabled = true;
    dataSourceSelect.title = 'Locked in this deployment';
    const localOption = [...dataSourceSelect.options].find((opt) => opt.value === 'local');
    if (localOption) localOption.disabled = true;
  }

  if (LOCK_API_BASE_URL && remoteUrlInput) {
    remoteUrlInput.value = state.remote.url;
    remoteUrlInput.readOnly = true;
    remoteUrlInput.title = 'Locked in this deployment';
  }

  if (!ALLOW_MOCK_TOGGLE && mockToggle) {
    mockToggle.checked = false;
    mockToggle.disabled = true;
    mockToggle.closest('label')?.classList.add('hidden');
  }
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
  const rememberKeyToggle = document.getElementById('rememberKeyToggle');
  if (dataSourceSelect) dataSourceSelect.value = state.dataSource;
  if (datasetSelect) datasetSelect.value = state.remote.dataset;
  if (apiKeyInput) apiKeyInput.value = state.remote.apiKey;
  if (remoteUrlInput) remoteUrlInput.value = state.remote.url;
  if (rememberKeyToggle) {
    rememberKeyToggle.checked = _getRememberKeyPreference();
  }
  applyDeploymentLocks();
  if (state.dataSource === 'remote' && mockToggle) {
    state.useMock = false;
    mockToggle.checked = false;
    mockToggle.disabled = true;
  }
  initAtlasModes();
  init3DControls();
  initTooltips();
  wireEvents();
  applyAtlasMode();  // Apply initial atlas mode state
  if (state.dataSource === 'remote') {
    await loadRemoteDatasets();
  }
  await loadRuns();
});
