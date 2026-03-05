/**
 * Dashboard — Unified System Overview & Health
 * ===============================================
 *
 * Single home page combining the previous Dashboard (entity counts,
 * validation warnings) with the Health dashboard (per-component
 * status, latency, errors). Provides a complete at-a-glance view.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api/triageApi';
import './Dashboard.css';


// ── Helpers for health component cards ─────────────────────────
const ACRONYMS = { ado: 'ADO', db: 'DB', api: 'API', kv: 'KV' };

function formatName(name) {
  return (name || '')
    .replace(/_/g, ' ')
    .split(' ')
    .map(w => ACRONYMS[w.toLowerCase()] || w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function statusIcon(s) {
  if (s === 'healthy') return '✅';
  if (s === 'degraded') return '⚠️';
  return '❌';
}

// ── Health Detail Modal ────────────────────────────────────────
function HealthDetailModal({ component, onClose }) {
  if (!component) return null;

  const renderDetailValue = (val) => {
    if (val == null) return <span className="text-muted">null</span>;
    if (typeof val === 'boolean') return <span className={val ? 'detail-bool-true' : 'detail-bool-false'}>{String(val)}</span>;
    if (typeof val === 'object') return <pre className="detail-json">{JSON.stringify(val, null, 2)}</pre>;
    return String(val);
  };

  return (
    <div className="health-modal-overlay" onClick={onClose}>
      <div className="health-modal" onClick={e => e.stopPropagation()}>
        <div className={`health-modal-header ${component.status}`}>
          <div className="health-modal-title">
            <span className="health-modal-icon">{statusIcon(component.status)}</span>
            <h2>{formatName(component.name)}</h2>
            <span className={`health-status-badge ${component.status}`}>{component.status}</span>
          </div>
          <button className="health-modal-close" onClick={onClose} title="Close">✕</button>
        </div>

        <div className="health-modal-body">
          {/* Latency */}
          {component.latency_ms != null && (
            <div className="health-modal-section">
              <h3>⏱ Response Time</h3>
              <div className={`health-modal-latency ${component.latency_ms > 2000 ? 'slow' : component.latency_ms > 500 ? 'moderate' : 'fast'}`}>
                {component.latency_ms}ms
                <span className="latency-label">
                  {component.latency_ms > 2000 ? ' — Slow' : component.latency_ms > 500 ? ' — Moderate' : ' — Fast'}
                </span>
              </div>
            </div>
          )}

          {/* Error */}
          {component.error && (
            <div className="health-modal-section">
              <h3>🚨 Error</h3>
              <div className="health-modal-error">{component.error}</div>
            </div>
          )}

          {/* Diagnostics / Suggestions */}
          {component.diagnostics && component.diagnostics.length > 0 && (
            <div className="health-modal-section">
              <h3>💡 Diagnostic Suggestions</h3>
              <ul className="health-modal-diagnostics">
                {component.diagnostics.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Full Details */}
          {component.detail && Object.keys(component.detail).length > 0 && (
            <div className="health-modal-section">
              <h3>📋 Details</h3>
              <table className="health-modal-detail-table">
                <tbody>
                  {Object.entries(component.detail).map(([key, val]) => (
                    <tr key={key}>
                      <td className="detail-key">{formatName(key)}</td>
                      <td className="detail-value">{renderDetailValue(val)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* All-clear message for healthy components */}
          {component.status === 'healthy' && !component.error && (
            <div className="health-modal-section">
              <div className="health-modal-allclear">
                ✅ This component is operating normally. No issues detected.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


export default function Dashboard({ addToast }) {
  // ── State — individual loading flags per section ─────────────
  const [health, setHealth] = useState(undefined);        // undefined = loading
  const [counts, setCounts] = useState({ rules: undefined, actions: undefined, triggers: undefined, routes: undefined });
  const [warnings, setWarnings] = useState(undefined);

  // Health dashboard (detailed component status)
  const [healthDashboard, setHealthDashboard] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedComponent, setSelectedComponent] = useState(null);

  // Agreement rate metric (ENG-003 Step 5)
  const [agreementRate, setAgreementRate] = useState(undefined);
  const [showAgreementDetail, setShowAgreementDetail] = useState(false);

  // ── Load Health Dashboard ────────────────────────────────────
  const loadHealth = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const result = await api.getHealthDashboard();
      setHealthDashboard(result);
    } catch (err) {
      addToast?.('Failed to load health: ' + err.message, 'error');
    } finally {
      setHealthLoading(false);
      setRefreshing(false);
    }
  }, [addToast]);

  // ── Load Dashboard Data (progressive — each section fills in as it resolves) ──

  useEffect(() => {
    // Fire all requests in parallel; update state as each resolves
    api.getHealth()
      .then(d => setHealth(d))
      .catch(() => setHealth(null));

    api.listRules()
      .then(d => setCounts(prev => ({ ...prev, rules: d.items?.length || 0 })))
      .catch(() => setCounts(prev => ({ ...prev, rules: '?' })));

    api.listActions()
      .then(d => setCounts(prev => ({ ...prev, actions: d.items?.length || 0 })))
      .catch(() => setCounts(prev => ({ ...prev, actions: '?' })));

    api.listTriggers()
      .then(d => setCounts(prev => ({ ...prev, triggers: d.items?.length || 0 })))
      .catch(() => setCounts(prev => ({ ...prev, triggers: '?' })));

    api.listRoutes()
      .then(d => setCounts(prev => ({ ...prev, routes: d.items?.length || 0 })))
      .catch(() => setCounts(prev => ({ ...prev, routes: '?' })));

    api.getValidationWarnings()
      .then(d => setWarnings(d.warnings || []))
      .catch(() => setWarnings([]));

    // Agreement rate metric
    api.getAgreementRate()
      .then(d => setAgreementRate(d))
      .catch(() => setAgreementRate(null));

    // Detailed health dashboard
    loadHealth();
  }, [loadHealth]);


  // ── Helpers ──────────────────────────────────────────────────

  /** Inline skeleton pulse for a value that hasn't arrived yet */
  const Skeleton = ({ width = '3rem' }) => (
    <span className="dashboard-skeleton" style={{ width }} />
  );

  const isLoading = (val) => val === undefined;


  // ── Render (always shows the full layout; cards fill in progressively) ──

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>📊 Dashboard</h1>
      </div>

      {/* Status Cards Row */}
      <div className="dashboard-status-row">
        {/* API Status */}
        <div className={`dashboard-status-card ${isLoading(health) ? 'status-loading' : (health && health.status !== 'unreachable') ? 'status-ok' : 'status-error'}`}>
          <div className="dashboard-status-icon">
            {isLoading(health) ? <Skeleton width="1.5rem" /> : (health && health.status !== 'unreachable') ? '✅' : '❌'}
          </div>
          <div className="dashboard-status-info">
            <span className="dashboard-status-label">Triage API</span>
            <span className="dashboard-status-value">
              {isLoading(health)
                ? <Skeleton width="5rem" />
                : (health && health.status !== 'unreachable')
                  ? (health.status === 'degraded' ? 'Running (Degraded)' : 'Healthy')
                  : 'Offline'}
            </span>
          </div>
        </div>

        {/* Agreement Rate Card (ENG-003 Step 5) — click to expand detail */}
        {(() => {
          const loading = agreementRate === undefined;
          const pct = agreementRate?.rate != null ? Math.round(agreementRate.rate * 100) : null;
          const color = pct == null ? '' : pct >= 80 ? 'status-ok' : pct >= 60 ? 'status-degraded' : 'status-error';
          return (
            <div
              className={`dashboard-status-card clickable ${loading ? 'status-loading' : color} ${showAgreementDetail ? 'expanded' : ''}`}
              onClick={() => !loading && agreementRate && setShowAgreementDetail(prev => !prev)}
              title={loading ? '' : 'Click for period breakdown'}
            >
              <div className="dashboard-status-icon">
                {loading ? <Skeleton width="1.5rem" /> : pct >= 80 ? '🤝' : pct >= 60 ? '⚠️' : '⚡'}
              </div>
              <div className="dashboard-status-info">
                <span className="dashboard-status-label">LLM / Pattern Agreement</span>
                <span className="dashboard-status-value">
                  {loading
                    ? <Skeleton width="5rem" />
                    : agreementRate
                      ? <>{pct}% <small className="text-muted">({agreementRate.total} analyses{agreementRate.trainingSignals > 0 ? `, ${agreementRate.trainingSignals} signals` : ''})</small></>
                      : 'N/A'}
                </span>
              </div>
              {!loading && agreementRate && (
                <span className="dashboard-expand-chevron">{showAgreementDetail ? '▲' : '▼'}</span>
              )}
            </div>
          );
        })()}

      </div>

      {/* Agreement Rate Detail Panel (expandable) */}
      {showAgreementDetail && agreementRate && (() => {
        const periods = agreementRate.periods || {};
        const rows = [
          { label: 'Last 7 Days',  data: periods.last7days },
          { label: 'Last 30 Days', data: periods.last30days },
          { label: 'Last 90 Days', data: periods.last90days },
        ];
        const pctBar = (rate) => {
          const pct = rate != null ? Math.round(rate * 100) : 0;
          const cls = pct >= 80 ? 'bar-ok' : pct >= 60 ? 'bar-warn' : 'bar-error';
          return (
            <div className="agreement-bar-track">
              <div className={`agreement-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
              <span className="agreement-bar-label">{pct}%</span>
            </div>
          );
        };
        return (
          <div className="agreement-detail-panel">
            <div className="agreement-detail-grid">
              {/* Period breakdown table */}
              <div className="agreement-detail-section">
                <h3>📈 Agreement by Period</h3>
                <table className="agreement-detail-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th>Rate</th>
                      <th>Agree</th>
                      <th>Disagree</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ label, data }) => (
                      <tr key={label}>
                        <td className="agreement-period-label">{label}</td>
                        <td>{data ? pctBar(data.rate) : <span className="text-muted">—</span>}</td>
                        <td className="text-center">{data?.agreements ?? '—'}</td>
                        <td className="text-center">{data?.disagreements ?? '—'}</td>
                        <td className="text-center">{data?.total ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Summary stats */}
              <div className="agreement-detail-section">
                <h3>🧠 Active Learning</h3>
                <div className="agreement-stats-grid">
                  <div className="agreement-stat">
                    <span className="agreement-stat-value">{agreementRate.total}</span>
                    <span className="agreement-stat-label">Total Analyses</span>
                  </div>
                  <div className="agreement-stat">
                    <span className="agreement-stat-value">{agreementRate.agreements}</span>
                    <span className="agreement-stat-label">Agreements</span>
                  </div>
                  <div className="agreement-stat">
                    <span className="agreement-stat-value">{agreementRate.disagreements}</span>
                    <span className="agreement-stat-label">Disagreements</span>
                  </div>
                  <div className="agreement-stat">
                    <span className="agreement-stat-value">{agreementRate.trainingSignals}</span>
                    <span className="agreement-stat-label">Training Signals</span>
                  </div>
                </div>
                <p className="agreement-detail-note">
                  Training signals are generated when human corrections disagree with
                  AI predictions. The weight tuner uses these to improve pattern matching over time.
                </p>
                <Link to="/corrections" className="btn btn-ghost btn-sm" style={{ marginTop: 'var(--space-sm)' }}>
                  View Corrections →
                </Link>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Entity Count Cards */}
      <div className="dashboard-counts-row">
        <Link to="/rules" className="dashboard-count-card">
          <span className="dashboard-count-icon">📋</span>
          <span className="dashboard-count-value">{isLoading(counts.rules) ? <Skeleton width="2rem" /> : counts.rules}</span>
          <span className="dashboard-count-label">Rules</span>
        </Link>
        <Link to="/actions" className="dashboard-count-card">
          <span className="dashboard-count-icon">🎯</span>
          <span className="dashboard-count-value">{isLoading(counts.actions) ? <Skeleton width="2rem" /> : counts.actions}</span>
          <span className="dashboard-count-label">Actions</span>
        </Link>
        <Link to="/triggers" className="dashboard-count-card">
          <span className="dashboard-count-icon">⚡</span>
          <span className="dashboard-count-value">{isLoading(counts.triggers) ? <Skeleton width="2rem" /> : counts.triggers}</span>
          <span className="dashboard-count-label">Triggers</span>
        </Link>
        <Link to="/routes" className="dashboard-count-card">
          <span className="dashboard-count-icon">🔀</span>
          <span className="dashboard-count-value">{isLoading(counts.routes) ? <Skeleton width="2rem" /> : counts.routes}</span>
          <span className="dashboard-count-label">Routes</span>
        </Link>
      </div>

      {/* Validation Warnings */}
      <div className="card dashboard-warnings-card">
        <div className="card-header">
          <h2>⚠️ Validation Warnings ({isLoading(warnings) ? '…' : warnings.length})</h2>
          <Link to="/validation" className="btn btn-ghost btn-sm">View All</Link>
        </div>
        <div className="card-body">
          {isLoading(warnings) ? (
            <div className="dashboard-skeleton-block">
              <Skeleton width="80%" /><br/>
              <Skeleton width="60%" />
            </div>
          ) : warnings.length === 0 ? (
            <p className="text-muted">No warnings — everything looks good!</p>
          ) : (
            <ul className="dashboard-warnings-list">
              {warnings.slice(0, 5).map((w, i) => (
                <li key={i} className="dashboard-warning-item">
                  <span className={`dashboard-warning-type warning-${w.type}`}>
                    {w.type.replace(/_/g, ' ')}
                  </span>
                  <span>{w.message}</span>
                </li>
              ))}
              {warnings.length > 5 && (
                <li className="text-muted">
                  …and {warnings.length - 5} more.{' '}
                  <Link to="/validation">View all →</Link>
                </li>
              )}
            </ul>
          )}
        </div>
      </div>

      {/* ── Component Health ─────────────────────────────────────── */}
      <div className="dashboard-health-section">
        <div className="dashboard-health-header">
          <h2>🩺 Component Health</h2>
          <button
            className="btn btn-default btn-sm"
            onClick={() => loadHealth(true)}
            disabled={refreshing}
          >
            {refreshing ? 'Checking…' : '↻ Refresh'}
          </button>
        </div>

        {healthLoading ? (
          <div className="dashboard-skeleton-block" style={{ padding: 'var(--space-lg)' }}>
            <Skeleton width="100%" /><br/>
            <Skeleton width="80%" /><br/>
            <Skeleton width="60%" />
          </div>
        ) : healthDashboard ? (
          <>
            {/* Overall banner */}
            <div className={`health-overall ${healthDashboard.overall}`}>
              <span>{statusIcon(healthDashboard.overall)}</span>
              <span>System {healthDashboard.overall}</span>
              <span className="health-overall-time">
                {healthDashboard.timestamp
                  ? new Date(healthDashboard.timestamp).toLocaleString()
                  : ''}
              </span>
            </div>

            {/* Component cards */}
            <div className="health-grid">
              {(healthDashboard.components || []).map((comp, i) => (
                <div
                  key={i}
                  className={`health-component-card ${comp.status} clickable`}
                  onClick={() => setSelectedComponent(comp)}
                  title="Click for details"
                >
                  <div className="health-component-name">
                    <span>{formatName(comp.name)}</span>
                    <span className={`health-status-badge ${comp.status}`}>
                      {comp.status}
                    </span>
                  </div>

                  {comp.latency_ms != null && (
                    <div className="health-latency">
                      Latency: {comp.latency_ms}ms
                    </div>
                  )}

                  {comp.error && (
                    <div className="health-error">
                      {comp.error}
                    </div>
                  )}

                  {comp.detail && Object.keys(comp.detail).length > 0 && (
                    <div className="health-detail">
                      {Object.entries(comp.detail).map(([key, val]) => {
                        // Skip nested objects (e.g. cache stats) — too noisy for dashboard
                        if (val != null && typeof val === 'object') return null;
                        return (
                          <div key={key}>
                            <span className="health-detail-key">{formatName(key)}:</span>
                            {String(val)}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Click hint for non-healthy components */}
                  {comp.status !== 'healthy' && (
                    <div className="health-click-hint">Click for diagnostics →</div>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-muted" style={{ padding: 'var(--space-md)' }}>
            Health data unavailable.
          </p>
        )}
      </div>

      {/* Health Detail Modal */}
      <HealthDetailModal
        component={selectedComponent}
        onClose={() => setSelectedComponent(null)}
      />
    </div>
  );
}
