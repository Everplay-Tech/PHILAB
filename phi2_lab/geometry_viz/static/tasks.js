/**
 * Tasks Panel - Community Task Board UI
 * Integrates with PHILAB platform API to display and browse tasks
 */

(function() {
  'use strict';

  const RUNTIME_CONFIG = (typeof window !== 'undefined' && window.__PHILAB_CONFIG__)
    ? window.__PHILAB_CONFIG__
    : {};

  const API_BASE = RUNTIME_CONFIG.apiBaseUrl || 'https://api.technopoets.net';

  // DOM elements
  const tasksBtn = document.getElementById('tasksBtn');
  const tasksOverlay = document.getElementById('tasksOverlay');
  const closeTasksBtn = document.getElementById('closeTasksBtn');
  const tasksList = document.getElementById('tasksList');
  const taskDetail = document.getElementById('taskDetail');
  const taskDetailContent = document.getElementById('taskDetailContent');
  const backToListBtn = document.getElementById('backToListBtn');
  const refreshTasksBtn = document.getElementById('refreshTasksBtn');
  const taskStatusFilter = document.getElementById('taskStatusFilter');
  const taskPriorityFilter = document.getElementById('taskPriorityFilter');

  // State
  let cachedTasks = [];

  // API helpers
  function getApiKey() {
    // Try to get API key from the main app's state
    const apiKeyInput = document.getElementById('apiKeyInput');
    return apiKeyInput ? apiKeyInput.value : '';
  }

  function getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const apiKey = getApiKey();
    if (apiKey) {
      headers['X-PhiLab-API-Key'] = apiKey;
    }
    return headers;
  }

  async function fetchTasks(status, priority) {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (priority) params.set('priority', priority);
    params.set('limit', '50');

    const apiKey = getApiKey();
    if (!apiKey) {
      // Show message that API key is needed
      return { error: 'auth_required' };
    }

    try {
      const resp = await fetch(`${API_BASE}/api/platform/tasks?${params.toString()}`, {
        headers: getHeaders()
      });

      if (resp.status === 401 || resp.status === 403) {
        return { error: 'auth_required' };
      }

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      return await resp.json();
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
      return { error: 'network' };
    }
  }

  async function fetchTaskDetail(taskId) {
    const apiKey = getApiKey();
    if (!apiKey) {
      return { error: 'auth_required' };
    }

    try {
      const resp = await fetch(`${API_BASE}/api/platform/tasks/${taskId}`, {
        headers: getHeaders()
      });

      if (resp.status === 401 || resp.status === 403) {
        return { error: 'auth_required' };
      }

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      return await resp.json();
    } catch (err) {
      console.error('Failed to fetch task detail:', err);
      return { error: 'network' };
    }
  }

  // Rendering
  function getPriorityClass(priority) {
    if (priority >= 3) return 'high';
    if (priority >= 2) return 'medium';
    return 'low';
  }

  function getPriorityLabel(priority) {
    if (priority >= 3) return 'High';
    if (priority >= 2) return 'Medium';
    return 'Low';
  }

  function renderTaskCard(task) {
    const priorityClass = getPriorityClass(task.priority);
    const description = task.description
      ? (task.description.length > 120 ? task.description.slice(0, 120) + '...' : task.description)
      : 'No description';

    return `
      <div class="task-card" data-task-id="${task.id}">
        <div class="task-card-header">
          <h3>${escapeHtml(task.name)}</h3>
          <span class="task-priority ${priorityClass}">${getPriorityLabel(task.priority)}</span>
        </div>
        <p class="task-card-desc">${escapeHtml(description)}</p>
        <div class="task-card-meta">
          <span class="task-status ${task.status}">${task.status}</span>
          <span>Runs: ${task.runs_completed}/${task.runs_needed}</span>
          ${task.dataset_name ? `<span>Dataset: ${escapeHtml(task.dataset_name)}</span>` : ''}
        </div>
      </div>
    `;
  }

  function renderTasksList(tasks) {
    if (!tasks || tasks.length === 0) {
      tasksList.innerHTML = `
        <div class="no-tasks">
          <p>No tasks found matching your filters.</p>
          <p>Try adjusting the status or priority filters.</p>
        </div>
      `;
      return;
    }

    tasksList.innerHTML = tasks.map(renderTaskCard).join('');

    // Add click handlers
    tasksList.querySelectorAll('.task-card').forEach(card => {
      card.addEventListener('click', () => {
        const taskId = card.dataset.taskId;
        showTaskDetail(taskId);
      });
    });
  }

  function renderAuthRequired() {
    tasksList.innerHTML = `
      <div class="no-tasks">
        <p>API key required to view tasks.</p>
        <p>Enter your API key in the header controls and try again.</p>
      </div>
    `;
  }

  function renderNetworkError() {
    tasksList.innerHTML = `
      <div class="no-tasks">
        <p>Failed to load tasks.</p>
        <p>Check your network connection and try again.</p>
      </div>
    `;
  }

  function renderTaskDetail(task) {
    taskDetailContent.innerHTML = `
      <h2>${escapeHtml(task.name)}</h2>
      <div class="task-card-meta" style="margin-bottom: 16px;">
        <span class="task-status ${task.status}">${task.status}</span>
        <span class="task-priority ${getPriorityClass(task.priority)}">${getPriorityLabel(task.priority)} Priority</span>
        <span>Runs: ${task.runs_completed}/${task.runs_needed}</span>
      </div>

      ${task.description ? `
        <h3>Description</h3>
        <p>${escapeHtml(task.description)}</p>
      ` : ''}

      ${task.hypothesis ? `
        <h3>Hypothesis</h3>
        <div class="task-hypothesis">${escapeHtml(task.hypothesis)}</div>
      ` : ''}

      <h3>Experiment Specification</h3>
      <pre class="task-spec">${escapeHtml(task.spec_yaml)}</pre>

      <div class="task-card-meta" style="margin-top: 16px;">
        <span>Spec Hash: ${task.spec_hash}</span>
        ${task.dataset_name ? `<span>Dataset: ${escapeHtml(task.dataset_name)}</span>` : ''}
      </div>

      <div style="margin-top: 24px; padding: 16px; background: #0f1628; border-radius: 8px; border: 1px solid #1f2a3d;">
        <h4 style="margin: 0 0 8px; color: #4fd1c5;">How to Contribute</h4>
        <p style="margin: 0; font-size: 13px; color: #94a3b8;">
          Use the CLI tool to run this task locally:<br>
          <code style="color: #f59e0b;">philab-contribute run --task-id ${task.id}</code>
        </p>
      </div>
    `;
  }

  async function showTaskDetail(taskId) {
    tasksList.classList.add('hidden');
    taskDetail.classList.remove('hidden');
    taskDetailContent.innerHTML = '<p class="tasks-loading">Loading task details...</p>';

    const result = await fetchTaskDetail(taskId);

    if (result.error === 'auth_required') {
      taskDetailContent.innerHTML = '<p>Authentication required.</p>';
      return;
    }

    if (result.error) {
      taskDetailContent.innerHTML = '<p>Failed to load task details.</p>';
      return;
    }

    renderTaskDetail(result);
  }

  function showTasksList() {
    taskDetail.classList.add('hidden');
    tasksList.classList.remove('hidden');
  }

  async function loadTasks() {
    tasksList.innerHTML = '<p class="tasks-loading">Loading tasks...</p>';

    const status = taskStatusFilter.value;
    const priority = taskPriorityFilter.value;

    const result = await fetchTasks(status, priority);

    if (result.error === 'auth_required') {
      renderAuthRequired();
      return;
    }

    if (result.error) {
      renderNetworkError();
      return;
    }

    cachedTasks = result;
    renderTasksList(result);
  }

  function openTasksPanel() {
    tasksOverlay.classList.remove('hidden');
    showTasksList();
    loadTasks();
  }

  function closeTasksPanel() {
    tasksOverlay.classList.add('hidden');
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Event listeners
  if (tasksBtn) {
    tasksBtn.addEventListener('click', openTasksPanel);
  }

  if (closeTasksBtn) {
    closeTasksBtn.addEventListener('click', closeTasksPanel);
  }

  if (backToListBtn) {
    backToListBtn.addEventListener('click', showTasksList);
  }

  if (refreshTasksBtn) {
    refreshTasksBtn.addEventListener('click', loadTasks);
  }

  if (taskStatusFilter) {
    taskStatusFilter.addEventListener('change', loadTasks);
  }

  if (taskPriorityFilter) {
    taskPriorityFilter.addEventListener('change', loadTasks);
  }

  // Close on overlay click (but not panel click)
  if (tasksOverlay) {
    tasksOverlay.addEventListener('click', (e) => {
      if (e.target === tasksOverlay) {
        closeTasksPanel();
      }
    });
  }

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !tasksOverlay.classList.contains('hidden')) {
      closeTasksPanel();
    }
  });

})();
