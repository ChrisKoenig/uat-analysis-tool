/**
 * EvalHistoryPage — Evaluation History Browser
 * ===============================================
 *
 * Allows operators to look up past evaluation results for any
 * work item by ID.  Displays a timeline of evaluations with
 * expandable detail panels showing rule results, routing,
 * field changes, and Analysis.State transitions.
 *
 * Data flows:
 *   1. User enters work item ID → calls getEvaluationHistory()
 *   2. API returns list of evaluation records (newest first)
 *   3. Each record expands to show full evaluation detail
 *
 * Also supports deep-link via query param: /history?id=12345
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams }  from 'react-router-dom';
import * as api             from '../api/triageApi';
import { formatDateTime }   from '../utils/helpers';
import { ADO_BASE_URL }     from '../utils/constants';
import './EvalHistoryPage.css';


/**
 * Analysis state → display badge CSS class mapping.
 * Keeps badge coloring consistent with QueuePage.
 */
const STATE_CLASSES = {
  Pending:             'badge-pending',
  Evaluated:           'badge-evaluated',
  'Awaiting Approval': 'badge-awaiting',
  Approved:            'badge-approved',
  Applied:             'badge-applied',
  'Needs Info':        'badge-needsinfo',
  Error:               'badge-error',
};


// =============================================================================
// Component
// =============================================================================

export default function EvalHistoryPage({ addToast }) {

  // ── URL Search Params (supports /history?id=12345) ─────────
  const [searchParams, setSearchParams] = useSearchParams();

  // ── State ──────────────────────────────────────────────────
  const [workItemId, setWorkItemId] = useState(
    searchParams.get('id') || ''
  );
  const [evaluations, setEvaluations] = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [searched,    setSearched]    = useState(false);
  const [expandedId,  setExpandedId]  = useState(null);
  const [limit,       setLimit]       = useState(20);


  // ── Fetch Evaluation History ───────────────────────────────

  const fetchHistory = useCallback(async (id) => {
    const numericId = parseInt(id, 10);
    if (isNaN(numericId) || numericId <= 0) {
      addToast?.('Enter a valid work item ID (positive integer)', 'error');
      return;
    }

    setLoading(true);
    setSearched(true);
    setExpandedId(null);

    try {
      const data = await api.getEvaluationHistory(numericId, limit);
      setEvaluations(data.evaluations || []);

      // Update URL so the lookup is bookmark-able
      setSearchParams({ id: numericId.toString() });

      if ((data.evaluations || []).length === 0) {
        addToast?.(`No evaluations found for work item ${numericId}`, 'info');
      }
    } catch (err) {
      addToast?.(err.message, 'error');
      setEvaluations([]);
    } finally {
      setLoading(false);
    }
  }, [limit, addToast, setSearchParams]);


  // ── Auto-search if URL has ?id= on mount ──────────────────

  useEffect(() => {
    const idParam = searchParams.get('id');
    if (idParam && !searched) {
      setWorkItemId(idParam);
      fetchHistory(idParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // ── Handlers ───────────────────────────────────────────────

  /** Submit search on Enter key */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') fetchHistory(workItemId);
  };

  /** Toggle expand/collapse for an evaluation row */
  const toggleExpand = (evalId) => {
    setExpandedId((prev) => (prev === evalId ? null : evalId));
  };


  // ── Render Helpers ─────────────────────────────────────────

  /**
   * Render the badge for an analysis state value.
   */
  const renderStateBadge = (state) => {
    const cls = STATE_CLASSES[state] || 'badge-pending';
    return <span className={`eval-badge ${cls}`}>{state}</span>;
  };

  /**
   * Render rule results as a row of pass/fail chips.
   */
  const renderRuleResults = (ruleResults) => {
    if (!ruleResults || Object.keys(ruleResults).length === 0) {
      return <span className="eval-muted">No rules evaluated</span>;
    }
    return (
      <div className="eval-rule-chips">
        {Object.entries(ruleResults).map(([ruleId, passed]) => (
          <span
            key={ruleId}
            className={`eval-rule-chip ${passed ? 'chip-pass' : 'chip-fail'}`}
            title={`${ruleId}: ${passed ? 'PASS' : 'FAIL'}`}
          >
            {passed ? '✓' : '✗'} {ruleId}
          </span>
        ))}
      </div>
    );
  };

  /**
   * Render field changes table.
   */
  const renderFieldChanges = (fieldsChanged) => {
    if (!fieldsChanged || Object.keys(fieldsChanged).length === 0) {
      return <span className="eval-muted">No field changes</span>;
    }
    return (
      <table className="eval-changes-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>From</th>
            <th>To</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(fieldsChanged).map(([field, change]) => (
            <tr key={field}>
              <td className="eval-field-name">{field}</td>
              <td className="eval-field-from">{change.from ?? '—'}</td>
              <td className="eval-field-to">{change.to ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  /**
   * Render errors (if any).
   */
  const renderErrors = (errors) => {
    if (!errors || errors.length === 0) return null;
    return (
      <div className="eval-errors">
        <strong>⚠ Errors:</strong>
        <ul>
          {errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
      </div>
    );
  };


  // ── Main Render ────────────────────────────────────────────

  return (
    <div className="eval-history-page">
      <h1>Evaluation History</h1>
      <p className="eval-subtitle">
        Look up past evaluation results for any ADO work item.
      </p>

      {/* ── Search Bar ──────────────────────────────────────── */}
      <div className="eval-search-bar">
        <label htmlFor="eval-wid">Work Item ID</label>
        <input
          id="eval-wid"
          type="number"
          min="1"
          placeholder="e.g. 123456"
          value={workItemId}
          onChange={(e) => setWorkItemId(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <select
          className="eval-limit-select"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          title="Max results to return"
        >
          <option value={10}>Last 10</option>
          <option value={20}>Last 20</option>
          <option value={50}>Last 50</option>
          <option value={100}>Last 100</option>
        </select>
        <button
          className="eval-search-btn"
          onClick={() => fetchHistory(workItemId)}
          disabled={loading}
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {/* ── Results ─────────────────────────────────────────── */}

      {loading && (
        <div className="eval-loading">Loading evaluation history…</div>
      )}

      {!loading && searched && evaluations.length === 0 && (
        <div className="eval-empty">
          No evaluations found for work item <strong>{workItemId}</strong>.
        </div>
      )}

      {!loading && evaluations.length > 0 && (
        <>
          <div className="eval-result-header">
            <span>
              Showing <strong>{evaluations.length}</strong> evaluation
              {evaluations.length !== 1 ? 's' : ''} for work item{' '}
              <a
                href={`${ADO_BASE_URL}/_workitems/edit/${workItemId}`}
                target="_blank"
                rel="noopener noreferrer"
                title="Open in ADO"
              >
                #{workItemId} ↗
              </a>
            </span>
          </div>

          <div className="eval-timeline">
            {evaluations.map((ev, idx) => {
              const isExpanded = expandedId === ev.id;
              return (
                <div
                  key={ev.id || idx}
                  className={`eval-card ${isExpanded ? 'expanded' : ''} ${
                    ev.isDryRun ? 'dry-run' : ''
                  }`}
                >
                  {/* ── Card Header (click to expand) ───────── */}
                  <div
                    className="eval-card-header"
                    onClick={() => toggleExpand(ev.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) =>
                      e.key === 'Enter' && toggleExpand(ev.id)
                    }
                  >
                    <span className="eval-card-arrow">
                      {isExpanded ? '▼' : '▶'}
                    </span>

                    <span className="eval-card-date">
                      {formatDateTime(ev.date)}
                    </span>

                    {renderStateBadge(ev.analysisState)}

                    {ev.isDryRun && (
                      <span className="eval-dryrun-badge">DRY RUN</span>
                    )}

                    <span className="eval-card-meta">
                      {ev.matchedTree && (
                        <span title="Matched tree">
                          🌳 {ev.matchedTree}
                        </span>
                      )}
                      {ev.appliedRoute && (
                        <span title="Applied route">
                          🔀 {ev.appliedRoute}
                        </span>
                      )}
                      <span title="Evaluated by">
                        👤 {ev.evaluatedBy || 'system'}
                      </span>
                    </span>
                  </div>

                  {/* ── Expanded Detail Panel ───────────────── */}
                  {isExpanded && (
                    <div className="eval-card-detail">

                      {/* Evaluation ID */}
                      <div className="eval-detail-row">
                        <span className="eval-detail-label">ID</span>
                        <code className="eval-detail-value">{ev.id}</code>
                      </div>

                      {/* Analysis State */}
                      <div className="eval-detail-row">
                        <span className="eval-detail-label">
                          Analysis State
                        </span>
                        <span className="eval-detail-value">
                          {renderStateBadge(ev.analysisState)}
                        </span>
                      </div>

                      {/* Matched Tree & Route */}
                      <div className="eval-detail-row">
                        <span className="eval-detail-label">
                          Matched Tree
                        </span>
                        <span className="eval-detail-value">
                          {ev.matchedTree || '—'}
                        </span>
                      </div>
                      <div className="eval-detail-row">
                        <span className="eval-detail-label">
                          Applied Route
                        </span>
                        <span className="eval-detail-value">
                          {ev.appliedRoute || '—'}
                        </span>
                      </div>

                      {/* Actions Executed */}
                      <div className="eval-detail-row">
                        <span className="eval-detail-label">
                          Actions Executed
                        </span>
                        <span className="eval-detail-value">
                          {(ev.actionsExecuted || []).length > 0
                            ? ev.actionsExecuted.join(', ')
                            : '—'}
                        </span>
                      </div>

                      {/* Rule Results */}
                      <div className="eval-detail-section">
                        <h4>Rule Results</h4>
                        {renderRuleResults(ev.ruleResults)}
                      </div>

                      {/* Field Changes */}
                      <div className="eval-detail-section">
                        <h4>Field Changes</h4>
                        {renderFieldChanges(ev.fieldsChanged)}
                      </div>

                      {/* Skipped Rules */}
                      {(ev.skippedRules || []).length > 0 && (
                        <div className="eval-detail-section">
                          <h4>Skipped Rules</h4>
                          <ul className="eval-skipped-list">
                            {ev.skippedRules.map((r) => (
                              <li key={r}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Errors */}
                      {renderErrors(ev.errors)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
