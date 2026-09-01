/**
 * Frontend Configuration & Dynamic API Client
 */
const Config = {
  getApiUrl() {
    const saved = localStorage.getItem('pm_api_url');
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, '');
    }
    if (window.VITE_API_URL && window.VITE_API_URL !== 'undefined') {
      return window.VITE_API_URL.replace(/\/+$/, '');
    }
    // Default fallback for local dev
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000';
    }
    // Default cloud placeholder
    return 'https://ai-predictive-maintainance-system.onrender.com';
  },

  setApiUrl(url) {
    if (!url) {
      localStorage.removeItem('pm_api_url');
    } else {
      localStorage.setItem('pm_api_url', url.trim().replace(/\/+$/, ''));
    }
  },

  async testConnection(customUrl = null) {
    const baseUrl = customUrl || this.getApiUrl();
    const start = performance.now();
    try {
      // Use /api/status to avoid adblocker filters blocking /health
      const response = await fetch(`${baseUrl}/api/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(20000)
      });
      const duration = Math.round(performance.now() - start);
      if (response.ok) {
        const data = await response.json();
        return { ok: true, latency: duration, data, url: baseUrl };
      }
      return { ok: false, error: `HTTP ${response.status}: ${response.statusText}`, url: baseUrl };
    } catch (err) {
      // Try fallback /health endpoint
      try {
        const res2 = await fetch(`${baseUrl}/health`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          signal: AbortSignal.timeout(4000)
        });
        if (res2.ok) {
          const data = await res2.json();
          return { ok: true, latency: Math.round(performance.now() - start), data, url: baseUrl };
        }
      } catch (_) {}

      // If localhost failed, try 127.0.0.1 fallback
      if (!customUrl && baseUrl.includes('localhost:8000')) {
        const fallbackUrl = baseUrl.replace('localhost:8000', '127.0.0.1:8000');
        try {
          const res = await fetch(`${fallbackUrl}/api/status`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            signal: AbortSignal.timeout(3000)
          });
          if (res.ok) {
            this.setApiUrl(fallbackUrl);
            const data = await res.json();
            return { ok: true, latency: Math.round(performance.now() - start), data, url: fallbackUrl };
          }
        } catch (_) {}
      }
      return { ok: false, error: err.message || 'Could not connect to backend server', url: baseUrl };
    }
  }
};

window.Config = Config;
