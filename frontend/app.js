/**
 * AI Predictive Maintenance Dashboard Controller
 */

// State
const state = {
  activeMachine: 'M01',
  activeMetric: 'temperature',
  autoRefresh: true,
  refreshInterval: 5, // seconds
  timerId: null,
  chart: null,
  lastData: null,
};

// Metric Configurations (units, color schemes, chart ranges)
const METRIC_CONFIG = {
  risk: {
    label: 'AI Failure Risk',
    unit: '%',
    color: '#f43f5e',
    bgColor: 'rgba(244, 63, 94, 0.20)',
    normalMax: 30,
    warningMax: 60,
  },
  temperature: {
    label: 'Temperature',
    unit: '°C',
    color: '#fb7185',
    bgColor: 'rgba(251, 113, 133, 0.15)',
    normalMax: 75,
    warningMax: 85,
  },
  vibration: {
    label: 'Vibration',
    unit: 'mm/s',
    color: '#eab308',
    bgColor: 'rgba(234, 179, 8, 0.15)',
    normalMax: 3.0,
    warningMax: 4.5,
  },
  current: {
    label: 'Current',
    unit: 'A',
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.15)',
    normalMax: 7.5,
    warningMax: 9.0,
  },
  rpm: {
    label: 'Speed (RPM)',
    unit: 'RPM',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)',
    normalMin: 1350,
  }
};

// Clean Timezone Formatter - converts UTC database timestamps to user's exact local time
function formatLocalTime(ts) {
  if (!ts) return 'Just now';
  try {
    let dStr = String(ts);
    if (!dStr.endsWith('Z') && !dStr.includes('+') && !dStr.includes('GMT')) {
      if (dStr.includes('T')) dStr = dStr + 'Z';
      else if (dStr.includes(' ')) dStr = dStr.replace(' ', 'T') + 'Z';
    }
    const d = new Date(dStr);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (_) {
    return String(ts);
  }
}

function formatLocalDateTime(ts) {
  if (!ts) return 'Just now';
  try {
    let dStr = String(ts);
    if (!dStr.endsWith('Z') && !dStr.includes('+') && !dStr.includes('GMT')) {
      if (dStr.includes('T')) dStr = dStr + 'Z';
      else if (dStr.includes(' ')) dStr = dStr.replace(' ', 'T') + 'Z';
    }
    const d = new Date(dStr);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleString([], {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch (_) {
    return String(ts);
  }
}

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
  initLucide();
  initEventListeners();
  initChart();
  
  // Initial Data Fetch
  checkApiAndFetch();
  startRefreshTimer();
});

function initLucide() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    try {
      window.lucide.createIcons();
    } catch (_) {}
  }
}

function initEventListeners() {
  // Refresh Button
  document.getElementById('btn-refresh-now')?.addEventListener('click', () => {
    spinRefreshIcon();
    fetchDashboardData();
  });

  // Toggle Auto-Refresh
  document.getElementById('btn-toggle-refresh')?.addEventListener('click', () => {
    state.autoRefresh = !state.autoRefresh;
    updateRefreshToggleButton();
    if (state.autoRefresh) {
      fetchDashboardData();
      startRefreshTimer();
    } else {
      stopRefreshTimer();
    }
  });

  // Interval Selector
  document.getElementById('select-interval')?.addEventListener('change', (e) => {
    state.refreshInterval = parseInt(e.target.value, 10) || 5;
    if (state.autoRefresh) {
      startRefreshTimer();
    }
  });
}

function updateRefreshToggleButton() {
  const btn = document.getElementById('btn-toggle-refresh');
  const icon = document.getElementById('icon-refresh-toggle');
  if (!btn || !icon) return;

  if (state.autoRefresh) {
    btn.classList.add('text-teal-400');
    btn.classList.remove('text-slate-500');
    icon.setAttribute('data-lucide', 'pause');
  } else {
    btn.classList.remove('text-teal-400');
    btn.classList.add('text-slate-500');
    icon.setAttribute('data-lucide', 'play');
  }
  initLucide();
}

function spinRefreshIcon() {
  const icon = document.getElementById('icon-refresh-spin');
  if (icon) {
    icon.classList.add('animate-spin');
    setTimeout(() => icon.classList.remove('animate-spin'), 700);
  }
}

function startRefreshTimer() {
  stopRefreshTimer();
  state.timerId = setInterval(() => {
    if (state.autoRefresh) {
      fetchDashboardData(true);
    }
  }, state.refreshInterval * 1000);
}

function stopRefreshTimer() {
  if (state.timerId) {
    clearInterval(state.timerId);
    state.timerId = null;
  }
}

// ---------------------------------------------------------------------------
// Data Fetching & API Communication
// ---------------------------------------------------------------------------

async function checkApiAndFetch() {
  const conn = await Config.testConnection();
  updateApiStatusBadge(conn);
  await fetchDashboardData();
}

function updateApiStatusBadge(conn) {
  const dot = document.getElementById('api-status-dot');
  const text = document.getElementById('api-status-text');
  const latency = document.getElementById('api-latency');

  if (!dot || !text || !latency) return;

  if (conn.ok) {
    dot.className = 'w-2 h-2 rounded-full bg-emerald-400';
    text.textContent = 'API Connected';
    text.className = 'text-emerald-400 font-medium';
    latency.textContent = conn.latency ? `${conn.latency}ms` : 'Online';
  } else {
    dot.className = 'w-2 h-2 rounded-full bg-rose-500 animate-pulse';
    text.textContent = 'API Disconnected';
    text.className = 'text-rose-400 font-medium';
    latency.textContent = 'Offline';
  }
}

async function fetchDashboardData(silent = false) {
  const baseUrl = Config.getApiUrl();
  let hasAnySuccess = false;
  const start = performance.now();

  try {
    // 1. Fetch Overview (contains high level KPIs + machine statuses)
    try {
      const overviewRes = await fetch(`${baseUrl}/api/overview`, { signal: AbortSignal.timeout(8000) });
      if (overviewRes.ok) {
        const overview = await overviewRes.json();
        hasAnySuccess = true;
        renderOverviewStats(overview);
        if (overview.machines && overview.machines.length > 0) {
          renderMachineCards(overview.machines);
        }
      }
    } catch (e) {
      console.warn('Overview fetch warning:', e);
    }

    // 2. Fetch Latest Readings
    try {
      const latestRes = await fetch(`${baseUrl}/api/readings/latest`, { signal: AbortSignal.timeout(8000) });
      if (latestRes.ok) {
        const machines = await latestRes.json();
        hasAnySuccess = true;
        if (machines && machines.length > 0) {
          renderMachineCards(machines);
        }
      }
    } catch (e) {
      console.warn('Latest readings fetch warning:', e);
    }

    // 3. Fetch Historical Data for Active Machine
    try {
      const historyRes = await fetch(`${baseUrl}/api/readings/history?machine_id=${state.activeMachine}&limit=30`, { signal: AbortSignal.timeout(8000) });
      if (historyRes.ok) {
        const history = await historyRes.json();
        hasAnySuccess = true;
        renderChartData(history);
      }
    } catch (e) {
      console.warn('History fetch warning:', e);
    }

    // 4. Fetch Recent Alert Audit Log
    try {
      const alertsRes = await fetch(`${baseUrl}/api/alerts/recent?limit=10`, { signal: AbortSignal.timeout(8000) });
      if (alertsRes.ok) {
        const alerts = await alertsRes.json();
        hasAnySuccess = true;
        renderAlertsTable(alerts);
      }
    } catch (e) {
      console.warn('Alerts fetch warning:', e);
    }

    const duration = Math.round(performance.now() - start);

    if (hasAnySuccess) {
      updateApiStatusBadge({ ok: true, latency: duration });
    } else {
      updateApiStatusBadge({ ok: false });
      if (!silent) {
        showToast('Connection Error', `Failed to connect to backend at ${baseUrl}`, 'error');
      }
    }

    initLucide();
  } catch (err) {
    if (!silent) {
      showToast('Connection Error', `Failed to connect to backend at ${baseUrl}`, 'error');
    }
    updateApiStatusBadge({ ok: false });
  }
}

// ---------------------------------------------------------------------------
// Render Overview Stats KPI
// ---------------------------------------------------------------------------
function renderOverviewStats(overview) {
  if (!overview) return;

  const unitsEl = document.getElementById('stat-units');
  const maxRiskEl = document.getElementById('stat-max-risk');
  const maxRiskMachineEl = document.getElementById('stat-max-risk-machine');
  const totalReadingsEl = document.getElementById('stat-total-readings');
  const totalAlertsEl = document.getElementById('stat-total-alerts');
  const fleetStatusEl = document.getElementById('stat-fleet-status');
  const statusIconEl = document.getElementById('stat-status-icon');
  const alertConfigEl = document.getElementById('stat-alert-config');

  if (unitsEl) unitsEl.textContent = overview.monitored_machines?.length || (overview.machines?.length || 0);
  if (totalReadingsEl) totalReadingsEl.textContent = Number(overview.total_readings || 0).toLocaleString();
  if (totalAlertsEl) totalAlertsEl.textContent = Number(overview.total_alerts_sent || 0).toLocaleString();
  if (alertConfigEl) alertConfigEl.textContent = `Threshold: ${overview.alert_threshold || 60}%`;

  let maxRisk = 0;
  let maxRiskMid = 'None';
  let hasWarning = false;
  let hasCritical = false;

  if (overview.machines && overview.machines.length > 0) {
    overview.machines.forEach(m => {
      const risk = Number(m.risk_percent || 0);
      if (risk > maxRisk) {
        maxRisk = risk;
        maxRiskMid = m.machine_id;
      }
      if (m.status === 'WARNING') hasWarning = true;
      if (m.status === 'HIGH FAILURE RISK' || risk >= 60) hasCritical = true;
    });
  }

  if (maxRiskEl) {
    maxRiskEl.textContent = `${maxRisk.toFixed(1)}%`;
    maxRiskEl.className = maxRisk >= 60 ? 'text-2xl font-bold text-rose-400 telemetry-val' : (maxRisk >= 30 ? 'text-2xl font-bold text-amber-400 telemetry-val' : 'text-2xl font-bold text-emerald-400 telemetry-val');
  }

  if (maxRiskMachineEl) {
    maxRiskMachineEl.textContent = maxRisk > 0 ? `Max on Machine ${maxRiskMid}` : 'All Nominal';
  }

  if (fleetStatusEl) {
    if (hasCritical) {
      fleetStatusEl.textContent = 'Critical Risk';
      fleetStatusEl.className = 'text-sm font-bold text-rose-400 mt-1';
      if (statusIconEl) statusIconEl.setAttribute('class', 'w-4 h-4 text-rose-400');
    } else if (hasWarning) {
      fleetStatusEl.textContent = 'Attention Needed';
      fleetStatusEl.className = 'text-sm font-bold text-amber-400 mt-1';
      if (statusIconEl) statusIconEl.setAttribute('class', 'w-4 h-4 text-amber-400');
    } else {
      fleetStatusEl.textContent = 'Nominal (Healthy)';
      fleetStatusEl.className = 'text-sm font-bold text-emerald-400 mt-1';
      if (statusIconEl) statusIconEl.setAttribute('class', 'w-4 h-4 text-emerald-400');
    }
  }
}

// ---------------------------------------------------------------------------
// Render Machine Cards
// ---------------------------------------------------------------------------
function renderMachineCards(machines) {
  const container = document.getElementById('machines-grid');
  if (!container) return;

  if (!machines || machines.length === 0) {
    container.innerHTML = `
      <div class="col-span-3 glass-panel p-8 rounded-2xl text-center text-slate-400">
        <i data-lucide="alert-circle" class="w-8 h-8 mx-auto mb-2 text-slate-500"></i>
        <p class="font-medium">No sensor telemetry detected yet.</p>
        <p class="text-xs text-slate-500 mt-1">Click "Simulate Step" above to generate machine readings.</p>
      </div>
    `;
    initLucide();
    return;
  }

  container.innerHTML = machines.map(m => {
    const risk = Number(m.risk_percent || 0);
    const isStopped = m.operational_state === 'TRIPPED_STOPPED' || m.status === 'EMERGENCY STOPPED' || (risk >= 60 && m.rpm === 0);
    const isCritical = isStopped || m.status === 'HIGH FAILURE RISK' || risk >= 60;
    const isWarning = m.status === 'WARNING';
    
    // Theme Colors & Badges
    let statusText = isStopped ? 'EMERGENCY SHUTDOWN' : (m.status || 'NORMAL');
    let statusBg = isStopped 
      ? 'bg-rose-500/20 border-rose-500/50 text-rose-300'
      : (isCritical 
        ? 'bg-rose-500/15 border-rose-500/30 text-rose-400' 
        : (isWarning ? 'bg-amber-500/15 border-amber-500/30 text-amber-400' : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'));

    const glowClass = isStopped ? 'glow-rose border-rose-500/60 bg-rose-950/10' : (isCritical ? 'glow-rose border-rose-500/40' : (isWarning ? 'glow-amber border-amber-500/30' : 'border-slate-800'));
    const riskMeterColor = isCritical ? '#f43f5e' : (isWarning ? '#f59e0b' : '#10b981');
    const timeFormatted = formatLocalTime(m.recorded_at);

    const temp = Number(m.temperature || 0).toFixed(1);
    const vib = Number(m.vibration || 0).toFixed(2);
    const cur = Number(m.current || 0).toFixed(2);
    const rpm = Math.round(Number(m.rpm || 0));

    return `
      <div class="glass-panel glass-panel-hover p-6 rounded-2xl ${glowClass} relative overflow-hidden transition-all flex flex-col justify-between">
        
        <div>
          <!-- Header -->
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2.5">
              <div class="w-9 h-9 rounded-lg ${isStopped ? 'bg-rose-900/60 border-rose-500/60 text-rose-300' : 'bg-slate-800 border-slate-700 text-teal-400'} border flex items-center justify-center font-bold text-sm font-mono">
                ${m.machine_id}
              </div>
              <div>
                <h3 class="text-sm font-bold text-white tracking-wide">Machine ${m.machine_id}</h3>
                <div class="text-[11px] text-slate-400 flex items-center gap-1">
                  <i data-lucide="clock" class="w-3 h-3 text-slate-500"></i>
                  <span>${timeFormatted}</span>
                </div>
              </div>
            </div>

            <!-- Status Badge -->
            <div class="px-2.5 py-1 rounded-full text-[10px] font-bold border uppercase tracking-wider flex items-center gap-1.5 ${statusBg}">
              <span class="w-1.5 h-1.5 rounded-full ${isStopped ? 'bg-rose-400 animate-ping' : (isWarning ? 'bg-amber-400' : 'bg-emerald-400')}"></span>
              <span>${statusText}</span>
            </div>
          </div>

          <!-- Failure Risk Meter -->
          <div class="bg-slate-900/80 border border-slate-800/80 rounded-xl p-3.5 mb-4">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-xs font-semibold text-slate-300">AI Failure Risk</span>
              <span class="text-sm font-bold telemetry-val" style="color: ${riskMeterColor};">${risk.toFixed(1)}%</span>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div class="h-full rounded-full transition-all duration-700" style="width: ${Math.min(risk, 100)}%; background-color: ${riskMeterColor};"></div>
            </div>
          </div>

          <!-- 4 Telemetry Metrics Grid -->
          <div class="grid grid-cols-2 gap-2.5 text-xs mb-3">
            
            <div class="bg-slate-900/60 border border-slate-800/60 p-2.5 rounded-lg">
              <div class="text-slate-400 text-[11px] flex items-center gap-1">
                <i data-lucide="thermometer" class="w-3.5 h-3.5 text-rose-400"></i>
                <span>Temperature</span>
              </div>
              <div class="text-sm font-bold text-slate-100 telemetry-val mt-0.5">${temp} <span class="text-[10px] text-slate-400">°C</span></div>
            </div>

            <div class="bg-slate-900/60 border border-slate-800/60 p-2.5 rounded-lg">
              <div class="text-slate-400 text-[11px] flex items-center gap-1">
                <i data-lucide="activity" class="w-3.5 h-3.5 text-amber-400"></i>
                <span>Vibration</span>
              </div>
              <div class="text-sm font-bold text-slate-100 telemetry-val mt-0.5">${vib} <span class="text-[10px] text-slate-400">mm/s</span></div>
            </div>

            <div class="bg-slate-900/60 border border-slate-800/60 p-2.5 rounded-lg">
              <div class="text-slate-400 text-[11px] flex items-center gap-1">
                <i data-lucide="zap" class="w-3.5 h-3.5 text-cyan-400"></i>
                <span>Current</span>
              </div>
              <div class="text-sm font-bold text-slate-100 telemetry-val mt-0.5">${cur} <span class="text-[10px] text-slate-400">A</span></div>
            </div>

            <div class="bg-slate-900/60 border border-slate-800/60 p-2.5 rounded-lg">
              <div class="text-slate-400 text-[11px] flex items-center gap-1">
                <i data-lucide="gauge" class="w-3.5 h-3.5 text-emerald-400"></i>
                <span>Speed (RPM)</span>
              </div>
              <div class="text-sm font-bold text-slate-100 telemetry-val mt-0.5">${rpm} <span class="text-[10px] text-slate-400">rpm</span></div>
            </div>

          </div>

          ${isStopped ? `
            <div class="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-[11px] text-rose-300 flex items-start gap-2 mb-3">
              <i data-lucide="shield-alert" class="w-4 h-4 text-rose-400 shrink-0 mt-0.5"></i>
              <span><strong>Safety Lockout:</strong> High failure risk detected. Machine automatically tripped and halted to prevent mechanical breakdown.</span>
            </div>
          ` : ''}
        </div>

        <!-- Action Bar on Card -->
        <div class="mt-2 pt-3 border-t border-slate-800/60">
          ${isStopped ? `
            <button onclick="restoreNormal('${m.machine_id}')" class="w-full py-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-1.5 transition active:scale-95 cursor-pointer">
              <i data-lucide="wrench" class="w-3.5 h-3.5"></i>
              <span>Fix / Heal & Restart Machine</span>
            </button>
          ` : `
            <div class="flex items-center justify-between">
              <button onclick="setChartMachine('${m.machine_id}')" class="text-[11px] text-teal-400 hover:text-teal-300 font-medium flex items-center gap-1 transition cursor-pointer">
                <span>View Graph</span>
                <i data-lucide="chevron-right" class="w-3 h-3"></i>
              </button>
              <button onclick="restoreNormal('${m.machine_id}')" class="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold rounded-md flex items-center gap-1 transition cursor-pointer" title="Service / inspect machine">
                <i data-lucide="check" class="w-3 h-3"></i>
                <span>Heal / Service</span>
              </button>
            </div>
          `}
        </div>

      </div>
    `;
  }).join('');

  initLucide();
}

// ---------------------------------------------------------------------------
// Chart.js Telemetry Graph
// ---------------------------------------------------------------------------
function initChart() {
  const canvas = document.getElementById('telemetryChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const metricCfg = METRIC_CONFIG[state.activeMetric];

  try {
    state.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: `${metricCfg.label} (${metricCfg.unit})`,
          data: [],
          borderColor: metricCfg.color,
          backgroundColor: metricCfg.bgColor,
          borderWidth: 2,
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointBackgroundColor: metricCfg.color,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: '#94a3b8',
              font: { family: 'Plus Jakarta Sans', size: 12 }
            }
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleColor: '#f8fafc',
            bodyColor: '#38bdf8',
            borderColor: '#334155',
            borderWidth: 1,
            padding: 10,
            boxPadding: 4,
            usePointStyle: true,
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 10 } }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
          }
        }
      }
    });
  } catch (err) {
    console.warn('Chart initialization warning:', err);
  }
}

function renderChartData(history) {
  if (!state.chart || !history || !Array.isArray(history)) return;

  const metricKey = state.activeMetric;
  const metricCfg = METRIC_CONFIG[metricKey];
  if (!metricCfg) return;

  const labels = history.map(item => formatLocalTime(item.recorded_at));
  const data = history.map(item => {
    if (metricKey === 'risk') {
      return Number(item.risk_percent !== undefined ? item.risk_percent : (item.risk !== undefined ? item.risk : 0));
    }
    return Number(item[metricKey] || 0);
  });

  state.chart.data.labels = labels;
  state.chart.data.datasets[0].label = `${state.activeMachine} - ${metricCfg.label} (${metricCfg.unit})`;
  state.chart.data.datasets[0].data = data;
  state.chart.data.datasets[0].borderColor = metricCfg.color;
  state.chart.data.datasets[0].backgroundColor = metricCfg.bgColor;
  state.chart.data.datasets[0].pointBackgroundColor = metricCfg.color;

  state.chart.update('none');
}

function setChartMachine(machineId) {
  state.activeMachine = machineId;
  document.querySelectorAll('.chart-machine-btn').forEach(btn => {
    if (btn.dataset.machine === machineId) {
      btn.className = 'chart-machine-btn px-3 py-1 text-xs font-semibold rounded bg-teal-600 text-white transition';
    } else {
      btn.className = 'chart-machine-btn px-3 py-1 text-xs font-semibold rounded text-slate-400 hover:text-white transition';
    }
  });
  fetchDashboardData();
}

function setChartMetric(metric) {
  state.activeMetric = metric;
  document.querySelectorAll('.chart-metric-btn').forEach(btn => {
    if (btn.dataset.metric === metric) {
      btn.className = 'chart-metric-btn px-2.5 py-1 text-xs font-medium rounded bg-slate-700 text-teal-300 transition';
    } else {
      btn.className = 'chart-metric-btn px-2.5 py-1 text-xs font-medium rounded text-slate-400 hover:text-white transition';
    }
  });
  fetchDashboardData();
}

// ---------------------------------------------------------------------------
// Render Alerts Log Table
// ---------------------------------------------------------------------------
function renderAlertsTable(alerts) {
  const tbody = document.getElementById('alerts-table-body');
  const countEl = document.getElementById('alert-table-count');
  if (!tbody) return;

  if (!alerts || !Array.isArray(alerts) || alerts.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="py-6 text-center text-slate-500">No alert logs recorded yet.</td>
      </tr>
    `;
    return;
  }

  if (countEl) countEl.textContent = `Showing last ${alerts.length}`;

  tbody.innerHTML = alerts.map(a => {
    const isSent = a.email_status === 'sent';
    const isFailed = a.email_status === 'failed';
    const statusBadge = isSent 
      ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-semibold">Sent</span>'
      : (isFailed 
        ? '<span class="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 text-[10px] font-semibold" title="' + (a.error_message || '') + '">Failed</span>'
        : '<span class="px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-400 text-[10px] font-semibold">' + (a.email_status || 'logged') + '</span>');

    const dateStr = formatLocalDateTime(a.sent_at);
    const recipientsList = Array.isArray(a.recipients) ? a.recipients.join(', ') : (a.recipients || '(none)');
    const risk = Number(a.risk_percent || 0).toFixed(1);

    return `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-3 font-mono text-[11px] text-slate-400">${dateStr}</td>
        <td class="py-2.5 px-3 font-bold text-teal-400 font-mono">${a.machine_id}</td>
        <td class="py-2.5 px-3 font-semibold text-rose-400">${a.status}</td>
        <td class="py-2.5 px-3 font-mono font-bold text-slate-100">${risk}%</td>
        <td class="py-2.5 px-3 text-slate-400 truncate max-w-[200px]" title="${recipientsList}">${recipientsList}</td>
        <td class="py-2.5 px-3">${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

// ---------------------------------------------------------------------------
// Simulation Actions & Triggers
// ---------------------------------------------------------------------------
async function triggerSimTick() {
  const baseUrl = Config.getApiUrl();
  try {
    const res = await fetch(`${baseUrl}/api/simulator/tick`, { method: 'POST' });
    if (res.ok) {
      showToast('Simulation Tick', 'Generated 1 telemetry cycle across all units.', 'info');
      await fetchDashboardData();
    } else {
      showToast('Simulation Error', 'Failed to generate simulation tick.', 'error');
    }
  } catch (err) {
    showToast('Error', err.message, 'error');
  }
}

async function triggerHazard(machineId) {
  const baseUrl = Config.getApiUrl();
  try {
    const res = await fetch(`${baseUrl}/api/simulator/hazard?machine_id=${machineId}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      showToast('Hazard Injected', `Machine ${machineId} failure risk spiked to ${data.reading?.risk_percent?.toFixed(1)}%!`, 'warning');
      await fetchDashboardData();
    } else {
      showToast('Error', `Could not inject hazard on ${machineId}`, 'error');
    }
  } catch (err) {
    showToast('Error', err.message, 'error');
  }
}

async function restoreNormal(machineId) {
  const baseUrl = Config.getApiUrl();
  try {
    const res = await fetch(`${baseUrl}/api/simulator/normalize?machine_id=${machineId}`, { method: 'POST' });
    if (res.ok) {
      showToast('Machine Restored', `Machine ${machineId} returned to healthy nominal range.`, 'info');
      await fetchDashboardData();
    } else {
      showToast('Error', `Could not restore normal state on ${machineId}`, 'error');
    }
  } catch (err) {
    showToast('Error', err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Modals & Settings
// ---------------------------------------------------------------------------
function openConfigModal() {
  const modal = document.getElementById('modal-config');
  const input = document.getElementById('input-api-url');
  if (input) input.value = Config.getApiUrl();
  const res = document.getElementById('config-test-result');
  if (res) res.classList.add('hidden');
  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
}

function closeConfigModal() {
  const modal = document.getElementById('modal-config');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
}

async function testConfigUrl() {
  const input = document.getElementById('input-api-url');
  const resDiv = document.getElementById('config-test-result');
  if (!input || !resDiv) return;

  resDiv.classList.remove('hidden');
  resDiv.className = 'p-3 rounded-lg text-xs bg-slate-800 text-slate-300';
  resDiv.textContent = 'Testing connection...';

  const test = await Config.testConnection(input.value.trim());
  if (test.ok) {
    resDiv.className = 'p-3 rounded-lg text-xs bg-emerald-500/20 border border-emerald-500/30 text-emerald-300';
    resDiv.textContent = `✅ Connected successfully! (${test.latency}ms latency). Service: ${test.data?.service || 'FastAPI'}`;
  } else {
    resDiv.className = 'p-3 rounded-lg text-xs bg-rose-500/20 border border-rose-500/30 text-rose-300';
    resDiv.textContent = `❌ Connection failed: ${test.error}`;
  }
}

function saveConfigUrl() {
  const input = document.getElementById('input-api-url');
  if (input) {
    Config.setApiUrl(input.value.trim());
    showToast('Settings Saved', `API URL set to: ${Config.getApiUrl()}`, 'info');
    closeConfigModal();
    checkApiAndFetch();
  }
}

function openTestAlertModal() {
  const modal = document.getElementById('modal-test-email');
  const res = document.getElementById('test-email-result');
  if (res) res.classList.add('hidden');
  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
}

function closeTestAlertModal() {
  const modal = document.getElementById('modal-test-email');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
}

async function submitTestEmail() {
  const recipientInput = document.getElementById('input-test-recipient');
  const resDiv = document.getElementById('test-email-result');
  const btn = document.getElementById('btn-submit-test-email');
  const baseUrl = Config.getApiUrl();

  if (btn) btn.disabled = true;
  if (resDiv) {
    resDiv.classList.remove('hidden');
    resDiv.className = 'p-3 rounded-lg text-xs bg-slate-800 text-slate-300';
    resDiv.textContent = 'Sending email via SMTP...';
  }

  try {
    const payload = recipientInput && recipientInput.value.trim() 
      ? { recipient: recipientInput.value.trim() } 
      : {};

    const res = await fetch(`${baseUrl}/api/alerts/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok && data.sent) {
      resDiv.className = 'p-3 rounded-lg text-xs bg-emerald-500/20 border border-emerald-500/30 text-emerald-300';
      resDiv.textContent = `✅ ${data.message || 'Test email dispatched successfully!'}`;
      showToast('Email Sent', 'Test alert delivered to recipient inbox.', 'info');
      fetchDashboardData();
    } else {
      resDiv.className = 'p-3 rounded-lg text-xs bg-rose-500/20 border border-rose-500/30 text-rose-300';
      resDiv.textContent = `❌ Failed: ${data.error || data.reason || 'Unknown error'}`;
    }
  } catch (err) {
    if (resDiv) {
      resDiv.className = 'p-3 rounded-lg text-xs bg-rose-500/20 border border-rose-500/30 text-rose-300';
      resDiv.textContent = `❌ Network Error: ${err.message}`;
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Toast Notification Engine
// ---------------------------------------------------------------------------
function showToast(title, message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const bgBorder = type === 'error' ? 'bg-slate-900 border-rose-500/50 text-rose-400' 
    : (type === 'warning' ? 'bg-slate-900 border-amber-500/50 text-amber-400' 
    : 'bg-slate-900 border-teal-500/50 text-teal-400');

  const toast = document.createElement('div');
  toast.className = `p-4 rounded-xl border shadow-2xl transition-all duration-300 pointer-events-auto flex items-start gap-3 ${bgBorder}`;
  toast.innerHTML = `
    <div class="flex-1">
      <div class="text-xs font-bold text-white">${title}</div>
      <div class="text-[11px] text-slate-300 mt-0.5">${message}</div>
    </div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Expose globals for HTML onclick attributes
window.setChartMachine = setChartMachine;
window.setChartMetric = setChartMetric;
window.triggerSimTick = triggerSimTick;
window.triggerHazard = triggerHazard;
window.restoreNormal = restoreNormal;
window.openConfigModal = openConfigModal;
window.closeConfigModal = closeConfigModal;
window.testConfigUrl = testConfigUrl;
window.saveConfigUrl = saveConfigUrl;
window.openTestAlertModal = openTestAlertModal;
window.closeTestAlertModal = closeTestAlertModal;
window.submitTestEmail = submitTestEmail;
