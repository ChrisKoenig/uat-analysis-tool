/**
 * HealthPage — Comprehensive System Health Dashboard
 * =====================================================
 *
 * Shows real-time status of every platform component:
 * Cosmos DB, Azure OpenAI, Key Vault, ADO, cache, corrections.
 *
 * Replaces the legacy health-dashboard in admin_service.py.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import './HealthPage.css';


function formatName(name) {
  return (name || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

function statusIcon(s) {
  if (s === 'healthy') return '✅';
  if (s === 'degraded') return '⚠️';
  return '❌';
}


export default function HealthPage({ addToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const result = await api.getHealthDashboard();
      setData(result);
    } catch (err) {
      addToast?.('Failed to load health: ' + err.message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [addToast]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="health-page">
        <h1>System Health</h1>
        <div className="health-loading">Loading health status…</div>
      </div>
    );
  }

  return (
    <div className="health-page">
      <h1>System Health</h1>
      <p style={{ color: 'var(--text-light)', marginBottom: 'var(--space-lg)' }}>
        Real-time status of every platform component.
      </p>

      <div className="health-actions">
        <button
          className="btn btn-default"
          onClick={() => load(true)}
          disabled={refreshing}
        >
          {refreshing ? 'Checking…' : '↻ Refresh'}
        </button>
      </div>

      {data && (
        <>
          {/* Overall banner */}
          <div className={`health-overall ${data.overall}`}>
            <span>{statusIcon(data.overall)}</span>
            <span>System {data.overall}</span>
            <span className="health-overall-time">
              {data.timestamp
                ? new Date(data.timestamp).toLocaleString()
                : ''}
            </span>
          </div>

          {/* Component cards */}
          <div className="health-grid">
            {(data.components || []).map((comp, i) => (
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
                    {Object.entries(comp.detail).map(([key, val]) => (
                      <div key={key}>
                        <span className="health-detail-key">{formatName(key)}:</span>
                        {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
