/**
 * QueuePage — Triage Queue Viewer
 * =================================
 *
 * Displays work items from the ADO triage queue with filters for
 * analysis state and area path. Users can select items and send them
 * to the evaluation pipeline.
 *
 * Features:
 *   - Fetches hydrated queue data (title, state, area path, etc.)
 *   - State filter (Pending, Awaiting Approval, Needs Info, All)
 *   - Checkbox multi-select with "Select All"
 *   - "Evaluate Selected" → pipes to evaluate API
 *   - ADO deep links per item
 *   - Inline evaluation results after run
 *   - Refresh button
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../api/triageApi';
import { formatDateTime, truncate } from '../utils/helpers';
import { ANALYSIS_STATES } from '../utils/constants';
import './QueuePage.css';


/** Available state filters for the queue */
const STATE_FILTERS = [
  { value: '',                   label: 'All States' },
  { value: 'Pending',           label: 'Pending' },
  { value: 'Awaiting Approval', label: 'Awaiting Approval' },
  { value: 'Needs Info',        label: 'Needs Info' },
];


export default function QueuePage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stateFilter, setStateFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [evaluating, setEvaluating] = useState(false);
  const [results, setResults] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [applying, setApplying] = useState(null);

  const navigate = useNavigate();


  // ── Load Queue ───────────────────────────────────────────────

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setSelectedIds(new Set());
    setResults(null);
    try {
      const data = await api.getTriageQueueDetails(
        stateFilter || null,
        null,  // area_path — could be made filterable later
        200
      );
      setItems(data.items || []);
      if (data.failedIds?.length > 0) {
        addToast?.(`${data.failedIds.length} items failed to load`, 'warning');
      }
    } catch (err) {
      addToast?.(err.message, 'error');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [stateFilter, addToast]);


  useEffect(() => {
    loadQueue();
  }, [loadQueue]);


  // ── Selection ────────────────────────────────────────────────

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  };


  // ── Evaluate Selected ────────────────────────────────────────

  const handleEvaluate = async (dryRun = true) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      addToast?.('Select at least one work item', 'warning');
      return;
    }

    setEvaluating(true);
    setResults(null);
    try {
      const data = dryRun
        ? await api.evaluateTest(ids)
        : await api.evaluate(ids, false);

      setResults(data);
      addToast?.(
        `Evaluated ${data.evaluations?.length || 0} item(s)${dryRun ? ' (dry run)' : ''}`,
        'success'
      );
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setEvaluating(false);
    }
  };


  // ── Apply Single Result ──────────────────────────────────────

  const handleApply = async (evalResult) => {
    setApplying(evalResult.id);
    try {
      const result = await api.applyEvaluation(evalResult.id, evalResult.workItemId);
      if (result.success) {
        addToast?.(
          `Applied ${result.fieldsUpdated} changes to #${evalResult.workItemId}`,
          'success'
        );
      } else {
        addToast?.(result.error || 'Apply failed', 'error');
      }
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setApplying(null);
    }
  };


  // ── Find result for a queue item ─────────────────────────────

  const getResultForItem = (workItemId) => {
    return results?.evaluations?.find((e) => e.workItemId === workItemId);
  };


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="queue-page">
      <div className="page-header">
        <h1>📥 Triage Queue</h1>
        <div className="page-header-actions">
          <select
            className="form-select"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            style={{ width: 'auto' }}
          >
            {STATE_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <button
            className="btn btn-secondary"
            onClick={loadQueue}
            disabled={loading}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Action Bar */}
      <div className="queue-action-bar">
        <span className="queue-count">
          {loading ? 'Loading…' : `${items.length} items`}
          {selectedIds.size > 0 && ` · ${selectedIds.size} selected`}
        </span>
        <div className="queue-action-buttons">
          <button
            className="btn btn-secondary"
            disabled={selectedIds.size === 0 || evaluating}
            onClick={() => handleEvaluate(true)}
          >
            {evaluating ? 'Evaluating…' : '🧪 Dry Run Selected'}
          </button>
          <button
            className="btn btn-primary"
            disabled={selectedIds.size === 0 || evaluating}
            onClick={() => handleEvaluate(false)}
          >
            {evaluating ? 'Evaluating…' : '⚡ Evaluate Selected'}
          </button>
        </div>
      </div>

      {/* Queue Table */}
      <div className="card queue-table-card">
        <table className="queue-table">
          <thead>
            <tr>
              <th className="queue-col-check">
                <input
                  type="checkbox"
                  checked={items.length > 0 && selectedIds.size === items.length}
                  onChange={toggleSelectAll}
                  disabled={items.length === 0}
                />
              </th>
              <th className="queue-col-id">ID</th>
              <th className="queue-col-title">Title</th>
              <th className="queue-col-type">Type</th>
              <th className="queue-col-state">State</th>
              <th className="queue-col-analysis">Analysis</th>
              <th className="queue-col-area">Area Path</th>
              <th className="queue-col-assigned">Assigned To</th>
              <th className="queue-col-changed">Changed</th>
              <th className="queue-col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="queue-loading">Loading triage queue…</td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="queue-empty">
                  No items in the triage queue
                  {stateFilter && ` with state "${stateFilter}"`}.
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const evalResult = getResultForItem(item.id);
                return (
                  <React.Fragment key={item.id}>
                    <tr
                      className={`queue-row ${selectedIds.has(item.id) ? 'selected' : ''} ${evalResult ? 'has-result' : ''}`}
                      onClick={() => toggleSelect(item.id)}
                    >
                      <td className="queue-col-check" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={() => toggleSelect(item.id)}
                        />
                      </td>
                      <td className="queue-col-id">
                        <a
                          href={item.adoLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="queue-id-link"
                        >
                          {item.id}
                        </a>
                      </td>
                      <td className="queue-col-title" title={item.title}>
                        {truncate(item.title, 60)}
                      </td>
                      <td className="queue-col-type">{item.workItemType}</td>
                      <td className="queue-col-state">
                        <span className="queue-state-badge">{item.state}</span>
                      </td>
                      <td className="queue-col-analysis">
                        <span className={`queue-analysis-badge analysis-${item.analysisState?.replace(/\s/g, '-').toLowerCase()}`}>
                          {item.analysisState || '—'}
                        </span>
                      </td>
                      <td className="queue-col-area" title={item.areaPath}>
                        {truncate(item.areaPath, 30)}
                      </td>
                      <td className="queue-col-assigned" title={item.assignedTo}>
                        {truncate(item.assignedTo, 20)}
                      </td>
                      <td className="queue-col-changed">
                        {formatDateTime(item.changedDate)}
                      </td>
                      <td className="queue-col-actions" onClick={(e) => e.stopPropagation()}>
                        {evalResult && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setExpandedId(
                              expandedId === item.id ? null : item.id
                            )}
                          >
                            {expandedId === item.id ? '▼' : '▶'} Results
                          </button>
                        )}
                        <a
                          href={item.adoLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-ghost btn-sm"
                        >
                          ADO ↗
                        </a>
                      </td>
                    </tr>

                    {/* Inline Evaluation Result (expandable) */}
                    {evalResult && expandedId === item.id && (
                      <tr className="queue-result-row">
                        <td colSpan={10}>
                          <div className="queue-result-detail">
                            <div className="queue-result-summary">
                              <span className={`queue-analysis-badge analysis-${evalResult.analysisState?.replace(/\s/g, '-').toLowerCase()}`}>
                                {evalResult.analysisState}
                              </span>
                              {evalResult.matchedTree && (
                                <span className="queue-result-tag">🌳 {evalResult.matchedTree}</span>
                              )}
                              {evalResult.appliedRoute && (
                                <span className="queue-result-tag">🔀 {evalResult.appliedRoute}</span>
                              )}
                            </div>

                            {/* Rule Results */}
                            <div className="queue-result-rules">
                              {Object.entries(evalResult.ruleResults || {}).map(([ruleId, passed]) => (
                                <span
                                  key={ruleId}
                                  className={`queue-rule-chip ${passed ? 'rule-true' : 'rule-false'}`}
                                >
                                  {passed ? '✓' : '✗'} {ruleId}
                                </span>
                              ))}
                            </div>

                            {/* Field Changes */}
                            {Object.keys(evalResult.fieldsChanged || {}).length > 0 && (
                              <table className="queue-changes-table">
                                <thead>
                                  <tr><th>Field</th><th>From</th><th>To</th></tr>
                                </thead>
                                <tbody>
                                  {Object.entries(evalResult.fieldsChanged).map(([field, change]) => (
                                    <tr key={field}>
                                      <td><code className="field-ref">{field}</code></td>
                                      <td className="text-muted">{change.from ?? '—'}</td>
                                      <td><strong>{change.to ?? '—'}</strong></td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            {/* Apply Button */}
                            {!evalResult.isDryRun && (
                              <div className="queue-result-actions">
                                <button
                                  className="btn btn-primary btn-sm"
                                  disabled={applying === evalResult.id}
                                  onClick={() => handleApply(evalResult)}
                                >
                                  {applying === evalResult.id ? 'Applying…' : 'Apply to ADO'}
                                </button>
                              </div>
                            )}

                            {/* Errors */}
                            {evalResult.errors?.length > 0 && (
                              <div className="queue-result-errors">
                                {evalResult.errors.map((err, i) => (
                                  <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Bulk Results Summary */}
      {results && (
        <div className="queue-bulk-summary">
          <h3>
            Evaluation Complete — {results.evaluations?.length || 0} items
            {results.evaluations?.[0]?.isDryRun && (
              <span className="queue-dryrun-badge">DRY RUN</span>
            )}
          </h3>
          {results.errors?.length > 0 && (
            <div className="queue-bulk-errors">
              {results.errors.map((err, i) => (
                <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
              ))}
            </div>
          )}
          <p className="text-muted">
            Expand individual rows above to see details and apply changes.
          </p>
        </div>
      )}
    </div>
  );
}
