/**
 * DiagnosticsPanel — Tiny debug icon (lower-right corner)
 * =========================================================
 *
 * Shows a small 🛈 button fixed in the bottom-right corner.
 * Clicking it opens a flyout with live system diagnostics
 * (Cosmos, AI/OpenAI, ADO connectivity) fetched from
 * /api/v1/diagnostics.
 *
 * Users can copy the diagnostics JSON to clipboard so they
 * can paste it into a support request.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getDiagnostics } from '../../api/triageApi';
import './DiagnosticsPanel.css';

const STATUS_ICONS = {
  healthy: '🟢',
  degraded: '🟡',
  timeout: '🟠',
  initializing: '🟡',
  offline: '🔴',
  error: '🔴',
  unknown: '⚪',
};

function statusIcon(status) {
  return STATUS_ICONS[status] || STATUS_ICONS.unknown;
}

export default function DiagnosticsPanel() {
  const [open, setOpen] = useState(false);
  const [diag, setDiag] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const panelRef = useRef(null);

  // Debug: confirm mount
  useEffect(() => {
    console.log('[DiagnosticsPanel] mounted — icon should be visible bottom-right');
  }, []);

  const fetchDiag = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDiagnostics();
      setDiag(data);
    } catch (err) {
      setDiag({ _fetchError: err.message || 'Failed to reach API' });
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on open, refresh every 30s while open
  useEffect(() => {
    if (!open) return;
    fetchDiag();
    const iv = setInterval(fetchDiag, 30000);
    return () => clearInterval(iv);
  }, [open, fetchDiag]);

  // Close on click-outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const handleCopy = () => {
    const text = JSON.stringify(diag, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const statuses = diag ? [diag.cosmos?.status, diag.ai?.status, diag.ado?.status] : [];
  const overallStatus = diag
    ? diag._fetchError
      ? 'error'
      : statuses.includes('error')
        ? 'error'
        : statuses.includes('offline') || statuses.includes('timeout')
          ? 'offline'
          : 'healthy'
    : 'unknown';

  return (
    <div className="diag-root" ref={panelRef}>
      {/* ── The tiny icon ── */}
      <button
        className={`diag-trigger diag-trigger--${overallStatus}`}
        onClick={() => setOpen((v) => !v)}
        title="System diagnostics"
        aria-label="System diagnostics"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
          <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm.75 10.5h-1.5v-1.5h1.5v1.5Zm0-3h-1.5V4h1.5v4.5Z"/>
        </svg>
      </button>

      {/* ── Flyout panel ── */}
      {open && (
        <div className="diag-panel">
          <div className="diag-header">
            <strong>System Diagnostics</strong>
            <button className="diag-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>

          {loading && !diag && <div className="diag-loading">Loading…</div>}

          {diag && diag._fetchError && (
            <div className="diag-row diag-row--error">
              <span>🔴 API Unreachable</span>
              <span className="diag-detail">{diag._fetchError}</span>
            </div>
          )}

          {diag && !diag._fetchError && (
            <>
              <div className="diag-section">Services</div>

              {/* API */}
              <div className="diag-row">
                <span>{statusIcon(diag.api?.status)} Triage API</span>
                <span className="diag-tag diag-tag--healthy">OK</span>
              </div>

              {/* Cosmos DB */}
              <div className="diag-row">
                <span>{statusIcon(diag.cosmos?.status)} Cosmos DB</span>
                <span className={`diag-tag diag-tag--${diag.cosmos?.status}`}>
                  {diag.cosmos?.status || '?'}
                  {diag.cosmos?.inMemory && ' (in-memory)'}
                  {diag.cosmos?.latencyMs != null && ` (${diag.cosmos.latencyMs}ms)`}
                </span>
              </div>
              {diag.cosmos?.error && <div className="diag-detail">{diag.cosmos.error}</div>}

              {/* AI / Azure OpenAI */}
              <div className="diag-row">
                <span>{statusIcon(diag.ai?.status)} Azure OpenAI</span>
                <span className={`diag-tag diag-tag--${diag.ai?.status}`}>
                  {diag.ai?.status || '?'}
                </span>
              </div>
              {diag.ai?.reason && <div className="diag-detail">Reason: {diag.ai.reason}</div>}
              {diag.ai?.endpoint && <div className="diag-detail">Endpoint: {diag.ai.endpoint}</div>}
              {diag.ai?.initError && <div className="diag-detail diag-detail--error">Init: {diag.ai.initError}</div>}

              {/* ADO */}
              <div className="diag-row">
                <span>{statusIcon(diag.ado?.status)} Azure DevOps</span>
                <span className={`diag-tag diag-tag--${diag.ado?.status}`}>
                  {diag.ado?.status || '?'}
                  {diag.ado?.latencyMs != null && ` (${diag.ado.latencyMs}ms)`}
                </span>
              </div>
              {diag.ado?.error && <div className="diag-detail">{diag.ado.error}</div>}

              <div className="diag-ts">
                Checked: {diag.timestamp ? new Date(diag.timestamp).toLocaleTimeString() : '—'}
              </div>
            </>
          )}

          <div className="diag-actions">
            <button className="diag-copy" onClick={handleCopy} disabled={!diag}>
              {copied ? '✓ Copied!' : '📋 Copy for Support'}
            </button>
            <button className="diag-refresh" onClick={fetchDiag} disabled={loading}>
              {loading ? '⏳' : '🔄'} Refresh
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
