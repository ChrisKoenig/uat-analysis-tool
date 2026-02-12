/**
 * AuditPage — Audit Log Viewer
 * ==============================
 *
 * Displays the audit trail of all changes made to triage
 * entities. Supports filtering by entity type, action, and
 * actor with paginated results.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import { formatDateTime, capitalize } from '../utils/helpers';
import './AuditPage.css';


/** Entity types available for filtering */
const ENTITY_TYPES = ['all', 'rule', 'action', 'trigger', 'route'];

/** Audit actions for filtering (matches operation suffix in stored "entity.operation" format) */
const AUDIT_ACTIONS = [
  { value: 'all',      label: 'All Actions' },
  { value: 'create',   label: 'Created' },
  { value: 'update',   label: 'Updated' },
  { value: 'delete',   label: 'Deleted' },
  { value: 'activate', label: 'Activated' },
  { value: 'disable',  label: 'Disabled' },
  { value: 'copy',     label: 'Copied' },
  { value: 'evaluate', label: 'Evaluated' },
];


export default function AuditPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    entityType: 'all',
    action: 'all',
    limit: 50,
  });
  const [expandedId, setExpandedId] = useState(null);


  // ── Load Audit Entries ───────────────────────────────────────

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.entityType !== 'all') params.entity_type = filters.entityType;
      if (filters.action !== 'all') params.action = filters.action;
      params.limit = filters.limit;

      const data = await api.listAudit(params);
      setEntries(data.items || data.entries || []);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [filters, addToast]);


  useEffect(() => {
    loadEntries();
  }, [loadEntries]);


  // ── Filter Handlers ──────────────────────────────────────────

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };


  // ── Action Color ─────────────────────────────────────────────

  /** Extract the operation part from "entity.operation" format */
  const getOperation = (action) => (action || '').split('.').pop();

  const actionColor = (action) => {
    const op = getOperation(action);
    switch (op) {
      case 'create':   return 'audit-created';
      case 'delete':   return 'audit-deleted';
      case 'update':   return 'audit-updated';
      case 'activate':
      case 'disable':
      case 'stage':    return 'audit-status';
      case 'copy':     return 'audit-copied';
      case 'evaluate': return 'audit-evaluate';
      default:         return '';
    }
  };


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="audit-page">
      <div className="page-header">
        <h1>📜 Audit Log</h1>
      </div>

      {/* Filters */}
      <div className="card audit-filters-card">
        <div className="card-body audit-filters">
          <div className="form-group">
            <label>Entity Type</label>
            <select
              className="form-select"
              value={filters.entityType}
              onChange={(e) => updateFilter('entityType', e.target.value)}
            >
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t === 'all' ? 'All Types' : capitalize(t) + 's'}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Action</label>
            <select
              className="form-select"
              value={filters.action}
              onChange={(e) => updateFilter('action', e.target.value)}
            >
              {AUDIT_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Limit</label>
            <select
              className="form-select"
              value={filters.limit}
              onChange={(e) => updateFilter('limit', parseInt(e.target.value, 10))}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>

          <button
            className="btn btn-secondary audit-refresh-btn"
            onClick={loadEntries}
            disabled={loading}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Results Count */}
      <div className="audit-count">
        {loading ? 'Loading…' : `${entries.length} entries`}
      </div>

      {/* Audit Timeline */}
      <div className="audit-timeline">
        {entries.map((entry, idx) => (
          <div
            key={entry.id || idx}
            className={`audit-entry ${actionColor(entry.action)}`}
            onClick={() => setExpandedId(expandedId === (entry.id || idx) ? null : (entry.id || idx))}
          >
            <div className="audit-entry-header">
              <div className="audit-entry-summary">
                <span className={`audit-action-badge ${actionColor(entry.action)}`}>
                  {capitalize(getOperation(entry.action))}
                </span>
                <span className="audit-entity-type">
                  {capitalize(entry.entityType || entry.entity_type || '')}
                </span>
                <code className="field-ref">{entry.entityId || entry.entity_id}</code>
                {entry.entityName && (
                  <span className="audit-entity-name">"{entry.entityName}"</span>
                )}
              </div>
              <div className="audit-entry-meta">
                <span className="audit-timestamp">{formatDateTime(entry.timestamp)}</span>
                {entry.actor && (
                  <span className="audit-actor">by {entry.actor}</span>
                )}
                <span className="audit-expand-icon">
                  {expandedId === (entry.id || idx) ? '▼' : '▶'}
                </span>
              </div>
            </div>

            {/* Expanded Details */}
            {expandedId === (entry.id || idx) && entry.changes && (
              <div className="audit-entry-details">
                <h4>Changes</h4>
                <table className="audit-changes-table">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Before</th>
                      <th>After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(entry.changes).map(([field, change]) => (
                      <tr key={field}>
                        <td><code className="field-ref">{field}</code></td>
                        <td className="text-muted">
                          {typeof change.from === 'object'
                            ? JSON.stringify(change.from, null, 2)
                            : String(change.from ?? '—')}
                        </td>
                        <td>
                          <strong>
                            {typeof change.to === 'object'
                              ? JSON.stringify(change.to, null, 2)
                              : String(change.to ?? '—')}
                          </strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}

        {/* Empty State */}
        {!loading && entries.length === 0 && (
          <div className="audit-empty">
            No audit entries match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}
