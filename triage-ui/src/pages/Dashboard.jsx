/**
 * Dashboard — System Overview
 * =============================
 *
 * Home page showing system health, entity counts, validation
 * warnings, and quick links. Provides an at-a-glance view of
 * the triage system's state.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api/triageApi';
import './Dashboard.css';


export default function Dashboard({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [health, setHealth] = useState(null);
  const [adoStatus, setAdoStatus] = useState(null);
  const [counts, setCounts] = useState({ rules: 0, actions: 0, triggers: 0, routes: 0 });
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);


  // ── Load Dashboard Data ──────────────────────────────────────

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [healthData, rulesData, actionsData, triggersData, routesData, warningsData, adoData] =
          await Promise.allSettled([
            api.getHealth(),
            api.listRules(),
            api.listActions(),
            api.listTriggers(),
            api.listRoutes(),
            api.getValidationWarnings(),
            api.getAdoStatus(),
          ]);

        setHealth(healthData.status === 'fulfilled' ? healthData.value : null);
        setCounts({
          rules: rulesData.status === 'fulfilled' ? (rulesData.value.items?.length || 0) : '?',
          actions: actionsData.status === 'fulfilled' ? (actionsData.value.items?.length || 0) : '?',
          triggers: triggersData.status === 'fulfilled' ? (triggersData.value.items?.length || 0) : '?',
          routes: routesData.status === 'fulfilled' ? (routesData.value.items?.length || 0) : '?',
        });
        setWarnings(
          warningsData.status === 'fulfilled'
            ? (warningsData.value.warnings || [])
            : []
        );
        setAdoStatus(adoData.status === 'fulfilled' ? adoData.value : null);
      } catch (err) {
        addToast?.(err.message, 'error');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [addToast]);


  // ── Render ───────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="dashboard">
        <div className="page-header"><h1>📊 Dashboard</h1></div>
        <div className="dashboard-loading">Loading dashboard…</div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>📊 Dashboard</h1>
      </div>

      {/* Status Cards Row */}
      <div className="dashboard-status-row">
        {/* API Status */}
        <div className={`dashboard-status-card ${health ? 'status-ok' : 'status-error'}`}>
          <div className="dashboard-status-icon">
            {health ? '✅' : '❌'}
          </div>
          <div className="dashboard-status-info">
            <span className="dashboard-status-label">Triage API</span>
            <span className="dashboard-status-value">
              {health
                ? (health.status === 'degraded' ? 'Running (Degraded)' : 'Healthy')
                : 'Offline'}
            </span>
          </div>
        </div>

        {/* ADO Status */}
        <div className={`dashboard-status-card ${adoStatus?.connected ? 'status-ok' : 'status-error'}`}>
          <div className="dashboard-status-icon">
            {adoStatus?.connected ? '✅' : '❌'}
          </div>
          <div className="dashboard-status-info">
            <span className="dashboard-status-label">Azure DevOps</span>
            <span className="dashboard-status-value">
              {adoStatus?.connected
                ? `${adoStatus.organization} / ${adoStatus.project}`
                : (adoStatus?.error || 'Not Connected')}
            </span>
          </div>
        </div>

        {/* Cosmos DB Status */}
        <div className={`dashboard-status-card ${health?.database?.status === 'healthy' ? 'status-ok' : 'status-warn'}`}>
          <div className="dashboard-status-icon">
            {health?.database?.status === 'healthy' ? '✅' : '⚠️'}
          </div>
          <div className="dashboard-status-info">
            <span className="dashboard-status-label">Cosmos DB</span>
            <span className="dashboard-status-value">
              {health?.database?.status === 'healthy'
                ? 'Connected'
                : (health?.database?.error
                    ? 'Not Configured'
                    : 'Unknown')}
            </span>
          </div>
        </div>
      </div>

      {/* Entity Count Cards */}
      <div className="dashboard-counts-row">
        <Link to="/rules" className="dashboard-count-card">
          <span className="dashboard-count-icon">📋</span>
          <span className="dashboard-count-value">{counts.rules}</span>
          <span className="dashboard-count-label">Rules</span>
        </Link>
        <Link to="/actions" className="dashboard-count-card">
          <span className="dashboard-count-icon">🎯</span>
          <span className="dashboard-count-value">{counts.actions}</span>
          <span className="dashboard-count-label">Actions</span>
        </Link>
        <Link to="/triggers" className="dashboard-count-card">
          <span className="dashboard-count-icon">⚡</span>
          <span className="dashboard-count-value">{counts.triggers}</span>
          <span className="dashboard-count-label">Triggers</span>
        </Link>
        <Link to="/routes" className="dashboard-count-card">
          <span className="dashboard-count-icon">🔀</span>
          <span className="dashboard-count-value">{counts.routes}</span>
          <span className="dashboard-count-label">Routes</span>
        </Link>
      </div>

      {/* Validation Warnings */}
      <div className="card dashboard-warnings-card">
        <div className="card-header">
          <h2>⚠️ Validation Warnings ({warnings.length})</h2>
          <Link to="/validation" className="btn btn-ghost btn-sm">View All</Link>
        </div>
        <div className="card-body">
          {warnings.length === 0 ? (
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
    </div>
  );
}
