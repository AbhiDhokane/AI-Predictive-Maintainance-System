/**
 * Frontend Configuration & Dynamic API Client
 */
const DEFAULT_CLOUD_API = 'https://ai-predictive-maintainance-system.onrender.com';

const Config = {
  getApiUrl() {
    const saved = localStorage.getItem('pm_api_url');
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, '');
    }

    // Check Vite environment variable
    try {
      if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL.trim().replace(/\/+$/, '');
      }
    } catch (_) {}

    // Check global window override
    if (typeof window !== 'undefined' && window.VITE_API_URL && window.VITE_API_URL !== 'undefined') {
      return window.VITE_API_URL.trim().replace(/\/+$/, '');
    }

    // Default fallback for local dev
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
      return 'http://127.0.0.1:8000';
    }

    // Default cloud backend
    return DEFAULT_CLOUD_API;
  },

  setApiUrl(url) {
    if (!url || !url.trim()) {
      localStorage.removeItem('pm_api_url');
    } else {
      localStorage.setItem('pm_api_url', url.trim().replace(/\/+$/, ''));
    }
  },

  resetToDefault() {
    localStorage.removeItem('pm_api_url');
    return this.getApiUrl();
  },

  async testConnection(customUrl = null) {
    const baseUrl = (customUrl || this.getApiUrl()).trim().replace(/\/+$/, '');
    const start = performance.now();

    // Check mixed content: HTTPS frontend attempting insecure HTTP connection
    if (typeof window !== 'undefined' && 
        window.location.protocol === 'https:' && 
        baseUrl.startsWith('http://') && 
        !baseUrl.includes('localhost') && 
        !baseUrl.includes('127.0.0.1')) {
      return { 
        ok: false, 
        error: 'Mixed Content Error: HTTPS sites cannot connect to insecure HTTP APIs. Please use https:// for your backend URL.',
        url: baseUrl 
      };
    }

    try {
      // Primary health check: /api/status
      const response = await fetch(`${baseUrl}/api/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(15000)
      });
      const duration = Math.round(performance.now() - start);
      if (response.ok) {
        const data = await response.json();
        return { ok: true, latency: duration, data, url: baseUrl };
      }
      return { ok: false, error: `HTTP ${response.status}: ${response.statusText}`, url: baseUrl };
    } catch (err) {
      // Fallback 1: Try /health endpoint
      try {
        const res2 = await fetch(`${baseUrl}/health`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' },
          signal: AbortSignal.timeout(8000)
        });
        if (res2.ok) {
          const data = await res2.json();
          return { ok: true, latency: Math.round(performance.now() - start), data, url: baseUrl };
        }
      } catch (_) {}

      // Fallback 2: If localhost failed, try 127.0.0.1
      if (!customUrl && baseUrl.includes('localhost:8000')) {
        const fallbackUrl = baseUrl.replace('localhost:8000', '127.0.0.1:8000');
        try {
          const res = await fetch(`${fallbackUrl}/api/status`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            signal: AbortSignal.timeout(4000)
          });
          if (res.ok) {
            this.setApiUrl(fallbackUrl);
            const data = await res.json();
            return { ok: true, latency: Math.round(performance.now() - start), data, url: fallbackUrl };
          }
        } catch (_) {}
      }

      const isTimeout = err.name === 'TimeoutError' || err.message?.toLowerCase().includes('timeout');
      const errorMsg = isTimeout 
        ? 'Connection timed out (backend server may be waking up from sleep, please wait a moment)'
        : (err.message || 'Could not reach backend server');

      return { ok: false, error: errorMsg, url: baseUrl };
    }
  }
};

window.Config = Config;
