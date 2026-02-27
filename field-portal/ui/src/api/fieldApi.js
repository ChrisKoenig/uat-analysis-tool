/**
 * Field Portal API Client
 *
 * Typed functions for each step of the 9-step flow.
 * Uses runtime config from /config.json for the API base URL so the
 * same build works in local dev (Vite proxy) and App Service (cross-origin).
 *
 * Auth: call setTokenGetter(fn) once at app init so every request
 * includes an Authorization: Bearer <token> header.
 */

/**
 * Resolve the API base URL.
 * In production the React build is served from a DIFFERENT domain than the
 * API, so we read the base from /config.json (written by the build script).
 * Falls back to '' (relative, works with Vite proxy in dev).
 */
let _apiBase = null;

async function getApiBaseUrl() {
  if (_apiBase !== null) return _apiBase;
  try {
    const resp = await fetch('/config.json');
    if (resp.ok) {
      const cfg = await resp.json();
      _apiBase = cfg?.api?.baseUrl ?? '';
    } else {
      _apiBase = '';
    }
  } catch {
    _apiBase = '';
  }
  return _apiBase;
}

const API_PATH = '/api/field';

/** Stores the async function that returns a bearer token. */
let _getToken = null;

/**
 * Register a token-getter function (from MSAL).
 * Call this once from the authenticated app shell.
 */
export function setTokenGetter(fn) {
  _getToken = fn;
}

async function request(endpoint, options = {}) {
  const base = await getApiBaseUrl();
  const url = `${base}${API_PATH}${endpoint}`;
  const headers = { 'Content-Type': 'application/json', ...options.headers };

  // Attach bearer token if available
  if (_getToken) {
    try {
      const token = await _getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch (e) {
      console.warn('[fieldApi] token acquisition skipped', e);
    }
  }

  const config = { ...options, headers };

  const resp = await fetch(url, config);

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }

  return resp.json();
}

// ── Step 1-2: Submit + Quality Review ──
export async function submitIssue(title, description, impact = '') {
  return request('/submit', {
    method: 'POST',
    body: JSON.stringify({ title, description, impact }),
  });
}

// ── Step 3: Context Analysis ──
export async function analyzeContext(sessionId) {
  return request(`/analyze/${sessionId}`, { method: 'POST' });
}

// ── Step 3b: Analysis Detail (full raw data) ──
export async function getAnalysisDetail(sessionId) {
  return request(`/analysis-detail/${sessionId}`);
}

// ── Step 4: Correction ──
export async function submitCorrection(correctionData) {
  return request('/correct', {
    method: 'POST',
    body: JSON.stringify(correctionData),
  });
}

// ── Step 5: Resource Search ──
export async function searchResources(sessionId, deepSearch = false) {
  const qs = deepSearch ? '?deep_search=true' : '';
  return request(`/search/${sessionId}${qs}`, { method: 'POST' });
}

// ── Step 5b: Toggle Feature Selection ──
export async function toggleFeature(sessionId, featureId) {
  return request('/features/toggle', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, feature_id: featureId }),
  });
}

// ── Step 6: UAT Input ──
export async function saveUATInput(sessionId, opportunityId, milestoneId) {
  return request('/uat-input', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      opportunity_id: opportunityId,
      milestone_id: milestoneId,
    }),
  });
}

// ── Step 7: Related UATs Search ──
export async function searchRelatedUATs(sessionId) {
  return request(`/related-uats/${sessionId}`, { method: 'POST' });
}

// ── Step 8: Toggle UAT Selection ──
export async function toggleUAT(sessionId, uatId) {
  return request('/uats/toggle', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, uat_id: uatId }),
  });
}

// ── Step 9: Create UAT ──
export async function createUAT(sessionId) {
  return request('/create-uat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ── Session State ──
export async function getSession(sessionId) {
  return request(`/session/${sessionId}`);
}

// ── Health ──
export async function checkHealth() {
  return request('/health');
}
