/**
 * Triage API Client
 * ==================
 *
 * Centralized HTTP client for all Triage Management API calls.
 * All methods return parsed JSON or throw an ApiError.
 *
 * In development, requests go through Vite's proxy (see vite.config.js)
 * so we use relative paths like /api/v1/rules.
 *
 * Usage:
 *   import * as api from '../api/triageApi';
 *   const rules = await api.listRules();
 *   const rule  = await api.getRule('rule-1');
 *   await api.createRule({ name: 'New Rule', ... });
 */

import { API_BASE } from '../utils/constants';
import { getApiBaseUrl } from '../auth/authConfig';


// =============================================================================
// Custom Error Class
// =============================================================================

/**
 * API-specific error that includes the HTTP status code and
 * the backend's error detail message.
 */
export class ApiError extends Error {
  constructor(status, message, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}


// =============================================================================
// Core Fetch Wrapper
// =============================================================================

/**
 * Make an API request with standard error handling.
 *
 * @param {string} path - API path (e.g., '/rules')
 * @param {object} [options] - Fetch options
 * @returns {Promise<any>} Parsed JSON response
 * @throws {ApiError} On non-2xx responses
 */
async function request(path, options = {}) {
  const runtimeBase = getApiBaseUrl();  // e.g. 'https://app-triage-api-nonprod.azurewebsites.net'
  const url = `${runtimeBase}${API_BASE}${path}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    throw new ApiError(0, `Network error: ${err.message}`);
  }

  // Handle 204 No Content (e.g., successful delete)
  if (response.status === 204) {
    return null;
  }

  // Try to parse JSON body
  let body;
  try {
    body = await response.json();
  } catch {
    if (response.ok) return null;
    throw new ApiError(response.status, `HTTP ${response.status}: ${response.statusText}`);
  }

  // Handle error responses
  if (!response.ok) {
    const message = body?.detail || body?.error || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, body);
  }

  return body;
}

/**
 * GET request helper.
 */
function get(path) {
  return request(path, { method: 'GET' });
}

/**
 * POST request helper.
 */
function post(path, data) {
  return request(path, { method: 'POST', body: JSON.stringify(data) });
}

/**
 * PUT request helper.
 */
function put(path, data) {
  return request(path, { method: 'PUT', body: JSON.stringify(data) });
}

/**
 * DELETE request helper.
 */
function del(path, params = {}) {
  const query = new URLSearchParams(params).toString();
  const fullPath = query ? `${path}?${query}` : path;
  return request(fullPath, { method: 'DELETE' });
}


// =============================================================================
// Rules API
// =============================================================================

/** List all rules, optionally filtered by status and/or triage team */
export function listRules(status = null, triageTeamId = null) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (triageTeamId) params.set('triage_team_id', triageTeamId);
  const query = params.toString();
  return get(`/rules${query ? '?' + query : ''}`);
}

/** Get a single rule by ID */
export function getRule(id) {
  return get(`/rules/${id}`);
}

/** Create a new rule */
export function createRule(data) {
  return post('/rules', data);
}

/** Update an existing rule (requires version for optimistic locking) */
export function updateRule(id, data) {
  return put(`/rules/${id}`, data);
}

/** Delete a rule (soft delete by default, version for optimistic locking) */
export function deleteRule(id, { hard = false, version = null } = {}) {
  const params = {};
  if (hard) params.hard = 'true';
  if (version != null) params.version = String(version);
  return del(`/rules/${id}`, params);
}

/** Clone/copy a rule */
export function copyRule(id, newName = null) {
  return post(`/rules/${id}/copy`, newName ? { newName } : {});
}

/** Get cross-references for a rule */
export function getRuleReferences(id) {
  return get(`/rules/${id}/references`);
}

/** Update rule status (requires version for optimistic locking) */
export function updateRuleStatus(id, status, version) {
  return put(`/rules/${id}/status`, { status, version });
}


// =============================================================================
// Actions API
// =============================================================================

export function listActions(status = null, triageTeamId = null) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (triageTeamId) params.set('triage_team_id', triageTeamId);
  const query = params.toString();
  return get(`/actions${query ? '?' + query : ''}`);
}

export function getAction(id) {
  return get(`/actions/${id}`);
}

export function createAction(data) {
  return post('/actions', data);
}

export function updateAction(id, data) {
  return put(`/actions/${id}`, data);
}

/** Delete an action (soft delete by default, version for optimistic locking) */
export function deleteAction(id, { hard = false, version = null } = {}) {
  const params = {};
  if (hard) params.hard = 'true';
  if (version != null) params.version = String(version);
  return del(`/actions/${id}`, params);
}

export function copyAction(id, newName = null) {
  return post(`/actions/${id}/copy`, newName ? { newName } : {});
}

export function getActionReferences(id) {
  return get(`/actions/${id}/references`);
}

/** Update action status (requires version for optimistic locking) */
export function updateActionStatus(id, status, version) {
  return put(`/actions/${id}/status`, { status, version });
}


// =============================================================================
// Triggers API
// =============================================================================

export function listTriggers(status = null, triageTeamId = null) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (triageTeamId) params.set('triage_team_id', triageTeamId);
  const query = params.toString();
  return get(`/triggers${query ? '?' + query : ''}`);
}

export function getTrigger(id) {
  return get(`/triggers/${id}`);
}

export function createTrigger(data) {
  return post('/triggers', data);
}

export function updateTrigger(id, data) {
  return put(`/triggers/${id}`, data);
}

/** Delete a trigger (soft delete by default, version for optimistic locking) */
export function deleteTrigger(id, { hard = false, version = null } = {}) {
  const params = {};
  if (hard) params.hard = 'true';
  if (version != null) params.version = String(version);
  return del(`/triggers/${id}`, params);
}

export function copyTrigger(id, newName = null) {
  return post(`/triggers/${id}/copy`, newName ? { newName } : {});
}

export function getTriggerReferences(id) {
  return get(`/triggers/${id}/references`);
}

/** Update trigger status (requires version for optimistic locking) */
export function updateTriggerStatus(id, status, version) {
  return put(`/triggers/${id}/status`, { status, version });
}


// =============================================================================
// Routes API
// =============================================================================

export function listRoutes(status = null, triageTeamId = null) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (triageTeamId) params.set('triage_team_id', triageTeamId);
  const query = params.toString();
  return get(`/routes${query ? '?' + query : ''}`);
}

export function getRoute(id) {
  return get(`/routes/${id}`);
}

export function createRoute(data) {
  return post('/routes', data);
}

export function updateRoute(id, data) {
  return put(`/routes/${id}`, data);
}

/** Delete a route (soft delete by default, version for optimistic locking) */
export function deleteRoute(id, { hard = false, version = null } = {}) {
  const params = {};
  if (hard) params.hard = 'true';
  if (version != null) params.version = String(version);
  return del(`/routes/${id}`, params);
}

export function copyRoute(id, newName = null) {
  return post(`/routes/${id}/copy`, newName ? { newName } : {});
}

export function getRouteReferences(id) {
  return get(`/routes/${id}/references`);
}

/** Update route status (requires version for optimistic locking) */
export function updateRouteStatus(id, status, version) {
  return put(`/routes/${id}/status`, { status, version });
}


// =============================================================================
// Triage Teams API
// =============================================================================

/** List all triage teams, optionally filtered by status */
export function listTriageTeams(status = null) {
  const query = status ? `?status=${status}` : '';
  return get(`/triage-teams${query}`);
}

/** Get a single triage team by ID */
export function getTriageTeam(id) {
  return get(`/triage-teams/${id}`);
}

/** Create a new triage team */
export function createTriageTeam(data) {
  return post('/triage-teams', data);
}

/** Update an existing triage team */
export function updateTriageTeam(id, data) {
  return put(`/triage-teams/${id}`, data);
}

/** Delete a triage team */
export function deleteTriageTeam(id, { hard = false, version = null } = {}) {
  const params = {};
  if (hard) params.hard = 'true';
  if (version != null) params.version = String(version);
  return del(`/triage-teams/${id}`, params);
}

/** Clone/copy a triage team */
export function copyTriageTeam(id, newName = null) {
  return post(`/triage-teams/${id}/copy`, newName ? { newName } : {});
}

/** Update triage team status */
export function updateTriageTeamStatus(id, status, version) {
  return put(`/triage-teams/${id}/status`, { status, version });
}


// =============================================================================
// Field Schema API
// =============================================================================

/**
 * List available ADO field definitions.
 * Used for field autocomplete in rule and action forms.
 *
 * @param {Object} [filters] - Optional filters
 * @param {boolean} [filters.canEvaluate] - Only fields usable in rules
 * @param {boolean} [filters.canSet] - Only fields settable by actions
 * @param {string} [filters.group] - Filter by display group
 */
export function listFields({ canEvaluate, canSet, group } = {}) {
  const params = new URLSearchParams();
  if (canEvaluate != null) params.set('can_evaluate', String(canEvaluate));
  if (canSet != null) params.set('can_set', String(canSet));
  if (group) params.set('group', group);
  const query = params.toString();
  return get(`/fields${query ? '?' + query : ''}`);
}


// =============================================================================
// Evaluation API
// =============================================================================

/**
 * Evaluate work items through the triage pipeline.
 * Returns evaluation results without applying changes to ADO.
 */
export function evaluate(workItemIds, dryRun = false) {
  return post('/evaluate', { workItemIds, dryRun });
}

/**
 * Dry-run evaluation — computes results without ADO writes.
 */
export function evaluateTest(workItemIds) {
  return post('/evaluate/test', { workItemIds, dryRun: true });
}

/**
 * Apply evaluation results to ADO.
 * This writes field changes and comments to the ADO work item.
 */
export function applyEvaluation(evaluationId, workItemId, revision = null) {
  return post('/evaluate/apply', { evaluationId, workItemId, revision });
}

/** Get evaluation history for a work item */
export function getEvaluationHistory(workItemId, limit = 20) {
  return get(`/evaluations/${workItemId}?limit=${limit}`);
}


// =============================================================================
// ADO Integration API
// =============================================================================

/** Check ADO connection health */
export function getAdoStatus() {
  return get('/ado/status');
}

/** Fetch a single work item from ADO */
export function getAdoWorkItem(workItemId) {
  return get(`/ado/workitem/${workItemId}`);
}

/** Query the triage queue from ADO */
export function getTriageQueue(stateFilter = null, areaPath = null, maxResults = 100) {
  const params = new URLSearchParams();
  if (stateFilter) params.set('state', stateFilter);
  if (areaPath) params.set('area_path', areaPath);
  params.set('max_results', maxResults.toString());
  return get(`/ado/queue?${params}`);
}

/**
 * Fetch triage queue with hydrated item details.
 * Returns full item summaries (title, state, area path, assigned to, etc.)
 * in a single API call — no extra round-trips needed.
 */
export function getTriageQueueDetails(stateFilter = null, areaPath = null, maxResults = 100) {
  const params = new URLSearchParams();
  if (stateFilter) params.set('state', stateFilter);
  if (areaPath) params.set('area_path', areaPath);
  params.set('max_results', maxResults.toString());
  return get(`/ado/queue/details?${params}`);
}

/**
 * Run a saved ADO query and return hydrated work items.
 * Default: "Azure Corp Daily Triage" queue.
 */
export function getSavedQueryResults(queryId = null, maxResults = 500) {
  const params = new URLSearchParams();
  if (queryId) params.set('query_id', queryId);
  params.set('max_results', maxResults.toString());
  return get(`/ado/queue/saved?${params}`);
}


// =============================================================================
// Analysis API
// =============================================================================

/**
 * Batch lookup analysis results for multiple work item IDs.
 * Returns { results: { "12345": { category, intent, confidence, ... }, ... } }
 */
export function getAnalysisBatch(workItemIds) {
  if (!workItemIds || workItemIds.length === 0) return Promise.resolve({ results: {} });
  return get(`/analysis/batch?ids=${workItemIds.join(',')}`);
}

/**
 * Get full analysis detail for a single work item.
 */
export function getAnalysisDetail(workItemId) {
  return get(`/analysis/${workItemId}`);
}

/**
 * Check analysis engine status (AI availability).
 * Returns { available, aiAvailable, mode, error? }
 */
export function getAnalysisEngineStatus() {
  return get('/analyze/status');
}

/**
 * Run the analysis engine on selected work items.
 * Fetches from ADO, runs hybrid analyzer, stores in Cosmos.
 */
export function runAnalysis(workItemIds) {
  return post('/analyze', { workItemIds });
}

/**
 * Re-analyze a single work item with user-supplied correction hints.
 * @param {number} workItemId
 * @param {Object} corrections - { correct_category, correct_intent, correct_business_impact, correction_notes }
 */
export function reanalyzeWithCorrections(workItemId, corrections) {
  return post('/analyze/reanalyze', { workItemId, ...corrections });
}


// =============================================================================
// Graph User Lookup  (FR-1998)
// =============================================================================

/**
 * Look up Microsoft Graph user info by email / UPN.
 * Returns { displayName, jobTitle, department, email }.
 */
export function getGraphUser(email) {
  return get(`/graph/user?email=${encodeURIComponent(email)}`);
}

/**
 * Update ROBAnalysisState on one or more ADO work items.
 * @param {number[]} workItemIds
 * @param {string} state - e.g. 'Awaiting Approval', 'Pending', 'Approved'
 */
export function setAnalysisState(workItemIds, state) {
  return post('/ado/analysis-state', { workItemIds, state });
}

/**
 * Update ServiceTree routing fields on a single analysis record.
 * Only non-null fields are applied (PATCH semantics).
 * @param {number} workItemId
 * @param {Object} fields - { solutionArea?, csuDri?, areaPathAdo?, serviceTreeMatch?, ... }
 */
export function patchAnalysisRouting(workItemId, fields) {
  return request(`/analysis/${workItemId}/routing`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });
}


/** Get ADO field definitions */
export function getAdoFields() {
  return get('/ado/fields');
}


// =============================================================================
// Validation API
// =============================================================================

/** Get all validation warnings (orphans, conflicts, duplicates) */
export function getValidationWarnings() {
  return get('/validation/warnings');
}

/** Get cross-references for an entity */
export function getReferences(entityType, entityId) {
  return get(`/validation/references/${entityType}/${entityId}`);
}


// =============================================================================
// Audit API
// =============================================================================

/** List recent audit entries */
export function listAudit({ entity_type, action, actor, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (entity_type) params.set('entity_type', entity_type);
  if (action) params.set('action', action);
  if (actor) params.set('actor', actor);
  params.set('limit', limit.toString());
  return get(`/audit?${params}`);
}

/** Get audit history for a specific entity */
export function getEntityAudit(entityType, entityId, limit = 50) {
  return get(`/audit/${entityType}/${entityId}?limit=${limit}`);
}


// =============================================================================
// Health API
// =============================================================================

/** Service health check */
export function getHealth() {
  // Health endpoint is at /health, not under /api/v1.
  // Must use getApiBaseUrl() so the request reaches the API domain
  // (in App Service, the UI and API are on different hosts).
  const base = getApiBaseUrl();          // '' locally (Vite proxy), full URL in prod
  return fetch(`${base}/health`)
    .then((r) => r.json())
    .catch(() => ({
      status: 'unreachable',
      service: 'triage-api',
    }));
}


// =============================================================================
// Webhook Stats (informational)
// =============================================================================

/** Get webhook processing statistics */
export function getWebhookStats() {
  return get('/webhook/stats');
}


// =============================================================================
// Classify API (standalone classification — no ADO coupling)
// =============================================================================

/**
 * Classify raw text using the hybrid AI + pattern engine.
 * Stateless — no ADO lookups or Cosmos writes.
 *
 * @param {Object} params
 * @param {string} params.title - Item title (required)
 * @param {string} [params.description] - Detailed description
 * @param {string} [params.impact] - Business impact
 * @param {boolean} [params.include_pattern_details] - Include full pattern evidence
 * @returns {Promise<Object>} Classification result
 */
export function classify(params) {
  return post('/classify', params);
}

/**
 * Batch classify up to 20 items at once.
 * @param {Array<Object>} items - Array of { title, description?, impact? }
 */
export function classifyBatch(items) {
  return post('/classify/batch', { items });
}

/** Check AI classification engine status */
export function getClassifyStatus() {
  return get('/classify/status');
}

/** List all known classification categories */
export function getClassifyCategories() {
  return get('/classify/categories');
}


// =============================================================================
// Corrections API (corrective learning management)
// =============================================================================

/** List all corrective learning entries */
export function listCorrections() {
  return get('/admin/corrections');
}

/**
 * Add a new correction.
 * @param {Object} correction
 * @param {string} correction.original_category
 * @param {string} correction.corrected_category
 * @param {string} [correction.original_text]
 * @param {string} [correction.corrected_intent]
 * @param {string} [correction.correction_notes]
 */
export function addCorrection(correction) {
  return post('/admin/corrections', correction);
}

/** Update a correction by document ID */
export function updateCorrection(id, correction) {
  return put(`/admin/corrections/${id}`, correction);
}

/** Delete a correction by document ID */
export function deleteCorrection(id) {
  return del(`/admin/corrections/${id}`);
}


// =============================================================================
// Training Signals API (ENG-003 Active Learning)
// =============================================================================

/**
 * Submit a training signal from a disagreement resolution.
 * @param {Object} signal
 * @param {string} signal.workItemId
 * @param {string} signal.llmCategory
 * @param {string} signal.patternCategory
 * @param {"llm"|"pattern"|"neither"} signal.humanChoice
 * @param {string} [signal.resolvedCategory] - Required when humanChoice is "neither"
 * @param {string} [signal.resolvedIntent]
 * @param {string} [signal.notes]
 */
export function submitTrainingSignal(signal) {
  return post('/admin/training-signals', signal);
}

/** List recent training signals */
export function listTrainingSignals(limit = 50, workItemId = null) {
  let url = `/admin/training-signals?limit=${limit}`;
  if (workItemId) url += `&work_item_id=${workItemId}`;
  return get(url);
}


// =============================================================================
// Pattern Weight Tuning API (ENG-003 Step 3)
// =============================================================================

/**
 * Trigger the pattern weight tuning batch.
 * Reads training signals, computes per-category multipliers, stores in Cosmos.
 */
export function tunePatternWeights() {
  return post('/admin/tune-weights', {});
}

/**
 * Get the current pattern weight adjustments.
 */
export function getPatternWeights() {
  return get('/admin/pattern-weights');
}


// =============================================================================
// Agreement Rate API (ENG-003 Step 5)
// =============================================================================

/**
 * Get agreement rate between pattern engine and LLM classifier,
 * with overall stats and per-period breakdowns.
 */
export function getAgreementRate() {
  return get('/admin/agreement-rate');
}


// =============================================================================
// Health Dashboard API (comprehensive system health)
// =============================================================================

/**
 * Get full health dashboard — checks Cosmos, OpenAI, KV, ADO, cache.
 * Different from getHealth() which is just the lightweight /health ping.
 */
export function getHealthDashboard() {
  return get('/admin/health');
}

/**
 * Lightweight diagnostics for the debug panel.
 * Returns status of Cosmos, AI, ADO without secrets.
 */
export function getDiagnostics() {
  return get('/diagnostics');
}


// =============================================================================
// Data Management API (FR-2005 — Export / Import)
// =============================================================================

/**
 * Export selected entities with auto-included dependencies.
 * @param {Object} selections - e.g. { rules: null, triggers: ['dt-abc'] }
 * @returns {Promise<Object>} Export bundle JSON
 */
export function exportEntities(selections) {
  return post('/data-management/export', { selections });
}

/**
 * Preview an import bundle without executing.
 * @param {Object} bundle - The full export JSON object
 * @returns {Promise<Object>} Preview with per-type create/update counts
 */
export function previewImport(bundle) {
  return post('/data-management/import/preview', { bundle });
}

/**
 * Execute an import with auto-backup.
 * @param {Object} bundle - The full export JSON object
 * @param {Object|null} selected - Optional per-type entity names to import
 * @returns {Promise<Object>} Results with created/updated/failed counts
 */
export function executeImport(bundle, selected = null) {
  return post('/data-management/import/execute', { bundle, selected });
}

/**
 * List persisted pre-import backups (summary info only).
 * @param {number} [limit=20]
 * @returns {Promise<Object>} { backups: [...] }
 */
export function listBackups(limit = 20) {
  return get(`/data-management/backups?limit=${limit}`);
}

/**
 * Retrieve the full backup bundle for a given audit entry.
 * @param {string} auditId - The audit entry ID
 * @returns {Promise<Object>} The backup bundle (same shape as export)
 */
export function getBackup(auditId) {
  return get(`/data-management/backups/${encodeURIComponent(auditId)}`);
}


// =============================================================================
// Classification Config API (dynamic categories / intents / impacts)
// =============================================================================

/**
 * List all classification config items.
 * @param {Object} [filters]
 * @param {string} [filters.configType] - "category" | "intent" | "business_impact"
 * @param {string} [filters.status]     - "official" | "discovered" | "rejected"
 */
export function listClassificationConfig(filters = {}) {
  const params = new URLSearchParams();
  if (filters.configType) params.set('config_type', filters.configType);
  if (filters.status) params.set('status', filters.status);
  const qs = params.toString();
  return get(`/admin/classification-config${qs ? '?' + qs : ''}`);
}

/** List only AI-discovered items pending review */
export function listClassificationDiscoveries() {
  return get('/admin/classification-config/discoveries');
}

/**
 * Update a classification config item (accept / reject / redirect).
 * @param {string} id        - Document ID (e.g. "cat_technical_support")
 * @param {Object} updates
 * @param {string} [updates.status]       - "official" | "rejected"
 * @param {string} [updates.redirectTo]   - Value to redirect to
 * @param {string} [updates.displayName]
 * @param {string} [updates.description]
 * @param {string[]} [updates.keywords]
 */
export function updateClassificationConfig(id, updates) {
  return put(`/admin/classification-config/${encodeURIComponent(id)}`, updates);
}
