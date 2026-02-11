/**
 * ValidationPage — System Validation Warnings
 * ==============================================
 *
 * Displays all validation warnings detected across the triage
 * system: orphaned rules/actions, missing references, duplicate
 * priorities, etc. Grouped by warning type with links to the
 * affected entities.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api/triageApi';
import './ValidationPage.css';


/** Map warning types to display info */
const WARNING_TYPE_CONFIG = {
  orphaned_rule:      { label: 'Orphaned Rule',     icon: '📋', severity: 'warning',  link: '/rules' },
  orphaned_action:    { label: 'Orphaned Action',   icon: '🎯', severity: 'warning',  link: '/actions' },
  missing_reference:  { label: 'Missing Reference', icon: '🔗', severity: 'error',    link: null },
  duplicate_priority: { label: 'Duplicate Priority', icon: '⚠️', severity: 'error',   link: '/triggers' },
  invalid_expression: { label: 'Invalid Expression', icon: '❌', severity: 'error',   link: '/triggers' },
  empty_route:        { label: 'Empty Route',        icon: '🔀', severity: 'info',    link: '/routes' },
};


export default function ValidationPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [groupBy, setGroupBy] = useState('type');  // 'type' or 'severity'


  // ── Load Warnings ────────────────────────────────────────────

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await api.getValidationWarnings();
        setWarnings(data.warnings || []);
      } catch (err) {
        addToast?.(err.message, 'error');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);


  /**
   * Refresh warnings — called after user acknowledges warnings
   * or navigates back from fixing entities.
   */
  const handleRefresh = async () => {
    setLoading(true);
    try {
      const data = await api.getValidationWarnings();
      setWarnings(data.warnings || []);
      addToast?.('Validation refreshed', 'success');
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };


  // ── Group Warnings ───────────────────────────────────────────

  const groupedWarnings = warnings.reduce((acc, w) => {
    const key = groupBy === 'type' ? w.type : (WARNING_TYPE_CONFIG[w.type]?.severity || 'info');
    if (!acc[key]) acc[key] = [];
    acc[key].push(w);
    return acc;
  }, {});


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="validation-page">
      <div className="page-header">
        <h1>🔍 Validation</h1>
        <div className="page-header-actions">
          <select
            className="form-select"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
            style={{ width: 'auto' }}
          >
            <option value="type">Group by Type</option>
            <option value="severity">Group by Severity</option>
          </select>
          <button className="btn btn-secondary" onClick={handleRefresh} disabled={loading}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Summary Bar */}
      <div className="validation-summary">
        <span className="validation-summary-total">
          {warnings.length} warning{warnings.length !== 1 ? 's' : ''}
        </span>
        {warnings.length === 0 && !loading && (
          <span className="validation-all-clear">✅ All checks passed — no warnings</span>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="validation-loading">Scanning for issues…</div>
      )}

      {/* Grouped Warning Lists */}
      {!loading && Object.entries(groupedWarnings).map(([group, items]) => {
        const config = WARNING_TYPE_CONFIG[group] || {
          label: group.replace(/_/g, ' '),
          icon: '⚠️',
          severity: group,
          link: null,
        };

        return (
          <div key={group} className="card validation-group">
            <div className="card-header">
              <h2>
                <span>{config.icon}</span>{' '}
                {groupBy === 'type'
                  ? config.label
                  : group.charAt(0).toUpperCase() + group.slice(1)}
                {' '}({items.length})
              </h2>
            </div>
            <div className="card-body">
              <table className="validation-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Entity</th>
                    <th>Message</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((w, i) => {
                    const wConf = WARNING_TYPE_CONFIG[w.type] || config;
                    return (
                      <tr key={i} className={`validation-row severity-${wConf.severity}`}>
                        <td>
                          <span className={`validation-type-badge severity-${wConf.severity}`}>
                            {wConf.label}
                          </span>
                        </td>
                        <td>
                          <code className="field-ref">{w.entityId || '—'}</code>
                          {w.entityType && (
                            <span className="text-muted"> ({w.entityType})</span>
                          )}
                        </td>
                        <td>{w.message}</td>
                        <td>
                          {wConf.link && w.entityId && (
                            <Link
                              to={`${wConf.link}?highlight=${w.entityId}`}
                              className="btn btn-ghost btn-sm"
                            >
                              Go to →
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
