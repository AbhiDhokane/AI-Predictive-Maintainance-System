/**
 * Frontend Configuration & Dynamic API Client
 */
const Config = {
  getApiUrl() {
    const saved = localStorage.getItem('pm_api_url');
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, '');
    }
    if (window.VITE_API_URL) {
      return window.VITE_API_URL.replace(/\/+$/, '');
    }
    // Default fallback
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000';
    }
    return 'https://ai-predictive-maintenance-api.onrender.com';
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
      const response = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(5000)
      });
      const duration = Math.round(performance.now() - start);
      if (response.ok) {
        const data = await response.json();
        return { ok: true, latency: duration, data, url: baseUrl };
      }
      return { ok: false, error: `HTTP ${response.status}: ${response.statusText}`, url: baseUrl };
    } catch (err) {
      // If localhost failed, try 127.0.0.1 fallback
      if (!customUrl && baseUrl.includes('localhost:8000')) {
        const fallbackUrl = baseUrl.replace('localhost:8000', '127.0.0.1:8000');
        try {
          const res = await fetch(`${fallbackUrl}/health`, {
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
      return { ok: false, error: err.message || 'Backend server is not running on port 8000', url: baseUrl };
    }
  }
};

window.Config = Config;
