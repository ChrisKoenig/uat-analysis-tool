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
  const url = `${API_BASE}${path}`;
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

/** List all rules, optionally filtered by status */
export function listRules(status = null) {
  const query = status ? `?status=${status}` : '';
  return get(`/rules${query}`);
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

export function listActions(status = null) {
  const query = status ? `?status=${status}` : '';
  return get(`/actions${query}`);
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

export function listTriggers(status = null) {
  const query = status ? `?status=${status}` : '';
  return get(`/triggers${query}`);
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

export function listRoutes(status = null) {
  const query = status ? `?status=${status}` : '';
  return get(`/routes${query}`);
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
export function listAudit(entityType = null, actor = null, limit = 50) {
  const params = new URLSearchParams();
  if (entityType) params.set('entity_type', entityType);
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
  return request('/health', { method: 'GET' }).catch(() => ({
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
