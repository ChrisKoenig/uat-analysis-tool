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


export default function Dashboard({ addToast }) {
  // ── State — individual loading flags per section ─────────────
  const [health, setHealth] = useState(undefined);        // undefined = loading
  const [counts, setCounts] = useState({ rules: undefined, actions: undefined, triggers: undefined, routes: undefined });
  const [warnings, setWarnings] = useState(undefined);

  // Health dashboard (detailed component status)
  const [healthDashboard, setHealthDashboard] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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
        <div className={`dashboard-status-card ${isLoading(health) ? 'status-loading' : health ? 'status-ok' : 'status-error'}`}>
          <div className="dashboard-status-icon">
            {isLoading(health) ? <Skeleton width="1.5rem" /> : health ? '✅' : '❌'}
          </div>
          <div className="dashboard-status-info">
            <span className="dashboard-status-label">Triage API</span>
            <span className="dashboard-status-value">
              {isLoading(health)
                ? <Skeleton width="5rem" />
                : health
                  ? (health.status === 'degraded' ? 'Running (Degraded)' : 'Healthy')
                  : 'Offline'}
            </span>
          </div>
        </div>

      </div>

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
                <div key={i} className={`health-component-card ${comp.status}`}>
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
    </div>
  );
}
