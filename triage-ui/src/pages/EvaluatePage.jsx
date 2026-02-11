/**
 * EvaluatePage — Triage Evaluation Interface
 * ============================================
 *
 * Allows users to enter work item IDs and run them through
 * the triage evaluation pipeline. Shows results including
 * matched tree, applied route, rule results, and field changes.
 *
 * Features:
 *   - Enter work item IDs (comma-separated)
 *   - Dry run mode (default) vs. live mode
 *   - Results cards with expandable details
 *   - ADO deep links for each work item
 *   - Apply results to ADO after review
 */

import React, { useState } from 'react';
import * as api from '../api/triageApi';
import StatusBadge from '../components/common/StatusBadge';
import { formatDateTime } from '../utils/helpers';
import './EvaluatePage.css';


export default function EvaluatePage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [inputIds, setInputIds] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [results, setResults] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [applying, setApplying] = useState(null);


  // ── Run Evaluation ───────────────────────────────────────────

  const handleEvaluate = async (e) => {
    e.preventDefault();

    // Parse comma/space separated IDs
    const ids = inputIds
      .split(/[,\s]+/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0);

    if (ids.length === 0) {
      addToast?.('Please enter valid work item IDs', 'warning');
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


  // ── Apply Results to ADO ─────────────────────────────────────

  const handleApply = async (evaluation) => {
    setApplying(evaluation.id);
    try {
      const result = await api.applyEvaluation(
        evaluation.id,
        evaluation.workItemId
      );
      if (result.success) {
        addToast?.(
          `Applied ${result.fieldsUpdated} changes to work item ${evaluation.workItemId}`,
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


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="evaluate-page">
      <div className="page-header">
        <h1>⚡ Evaluate</h1>
      </div>

      {/* Input Form */}
      <div className="card evaluate-input-card">
        <div className="card-body">
          <form onSubmit={handleEvaluate} className="evaluate-form">
            <div className="form-group">
              <label htmlFor="eval-ids">Work Item IDs</label>
              <input
                id="eval-ids"
                className="form-input"
                type="text"
                value={inputIds}
                onChange={(e) => setInputIds(e.target.value)}
                placeholder="Enter IDs separated by commas, e.g.: 12345, 12346, 12347"
                required
              />
              <span className="hint">
                Enter one or more ADO work item IDs to evaluate through the triage pipeline
              </span>
            </div>

            <div className="evaluate-form-actions">
              <label className="evaluate-dryrun-toggle">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                />
                <span>Dry Run</span>
                <span className="hint">(compute results without writing to ADO)</span>
              </label>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={evaluating}
              >
                {evaluating ? 'Evaluating…' : '⚡ Evaluate'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Results */}
      {results && (
        <div className="evaluate-results">
          <h2>
            Results — {results.evaluations?.length || 0} item(s)
            {results.evaluations?.[0]?.isDryRun && (
              <span className="evaluate-dryrun-badge">DRY RUN</span>
            )}
          </h2>

          {results.errors?.length > 0 && (
            <div className="evaluate-errors">
              {results.errors.map((err, i) => (
                <div key={i} className="toast toast-error">{err}</div>
              ))}
            </div>
          )}

          {results.evaluations?.map((evalResult) => (
            <div key={evalResult.id} className="card evaluate-result-card">
              <div
                className="evaluate-result-header"
                onClick={() => setExpandedId(
                  expandedId === evalResult.id ? null : evalResult.id
                )}
              >
                <div className="evaluate-result-summary">
                  <strong>#{evalResult.workItemId}</strong>
                  <span className={`evaluate-state evaluate-state-${evalResult.analysisState?.replace(/\s/g, '-').toLowerCase()}`}>
                    {evalResult.analysisState}
                  </span>
                  {evalResult.matchedTree && (
                    <span className="evaluate-matched">
                      🌳 {evalResult.matchedTree}
                    </span>
                  )}
                  {evalResult.appliedRoute && (
                    <span className="evaluate-route">
                      🔀 {evalResult.appliedRoute}
                    </span>
                  )}
                </div>
                <div className="evaluate-result-actions">
                  {evalResult.adoLink && (
                    <a
                      href={evalResult.adoLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open in ADO ↗
                    </a>
                  )}
                  {!evalResult.isDryRun && (
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={applying === evalResult.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleApply(evalResult);
                      }}
                    >
                      {applying === evalResult.id ? 'Applying…' : 'Apply to ADO'}
                    </button>
                  )}
                  <span className="evaluate-expand-icon">
                    {expandedId === evalResult.id ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedId === evalResult.id && (
                <div className="evaluate-result-details">
                  {/* Rule Results */}
                  <div className="evaluate-detail-section">
                    <h4>Rule Results ({Object.keys(evalResult.ruleResults || {}).length})</h4>
                    <div className="evaluate-rule-results">
                      {Object.entries(evalResult.ruleResults || {}).map(([ruleId, result]) => (
                        <span
                          key={ruleId}
                          className={`evaluate-rule-chip ${result ? 'rule-true' : 'rule-false'}`}
                        >
                          {result ? '✓' : '✗'} {ruleId}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Field Changes */}
                  {Object.keys(evalResult.fieldsChanged || {}).length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Field Changes</h4>
                      <table className="evaluate-changes-table">
                        <thead>
                          <tr>
                            <th>Field</th>
                            <th>From</th>
                            <th>To</th>
                          </tr>
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
                    </div>
                  )}

                  {/* Actions Executed */}
                  {evalResult.actionsExecuted?.length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Actions Executed</h4>
                      <ol className="evaluate-actions-list">
                        {evalResult.actionsExecuted.map((actionId, i) => (
                          <li key={i}>{actionId}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* Errors */}
                  {evalResult.errors?.length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Errors</h4>
                      {evalResult.errors.map((err, i) => (
                        <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
