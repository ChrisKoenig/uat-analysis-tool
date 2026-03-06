/**
 * ServiceTreeTab — Dedicated ServiceTree routing tab for EvaluatePage
 * ====================================================================
 *
 * A rich, card-based layout showing the full ServiceTree routing chain
 * with visual flow, edit capability, and override history.
 *
 * Props:
 *   detail       — the full analysis detail object
 *   workItemId   — the ADO work item ID
 *   onSaved(updatedFields) — callback after successful save
 */

import React, { useState, useCallback } from 'react';
import * as api from '../api/triageApi';
import './ServiceTreeTab.css';

const ROUTING_FIELDS = [
  { key: 'serviceTreeMatch',    label: 'Matched Service',   icon: '🔗', group: 'match' },
  { key: 'serviceTreeOffering', label: 'Offering',          icon: '📦', group: 'match' },
  { key: 'solutionArea',        label: 'Solution Area',     icon: '🎯', group: 'routing' },
  { key: 'csuDri',              label: 'CSU DRI',           icon: '👤', group: 'routing' },
  { key: 'areaPathAdo',         label: 'ADO Area Path',     icon: '📂', group: 'routing' },
  { key: 'releaseManager',      label: 'Release Manager',   icon: '📋', group: 'contacts' },
  { key: 'devContact',          label: 'Dev Contact',       icon: '🛠️', group: 'contacts' },
];

const GROUPS = [
  { key: 'match',    title: 'Service Match',     accent: '#1565c0', description: 'Identified service and offering from the ServiceTree catalog' },
  { key: 'routing',  title: 'Routing Assignment', accent: '#2e7d32', description: 'Where this item should be triaged based on ServiceTree mapping' },
  { key: 'contacts', title: 'Contacts',           accent: '#6a1b9a', description: 'Release and development ownership' },
];

export default function ServiceTreeTab({ detail, workItemId, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const hasData = detail && ROUTING_FIELDS.some(f => detail[f.key]);
  const isOverridden = detail?.routingOverrideBy;

  const handleEdit = useCallback(() => {
    const current = {};
    ROUTING_FIELDS.forEach(f => { current[f.key] = detail?.[f.key] || ''; });
    setDraft(current);
    setEditing(true);
    setError(null);
  }, [detail]);

  const handleCancel = useCallback(() => {
    setEditing(false);
    setDraft({});
    setError(null);
  }, []);

  const handleSave = useCallback(async () => {
    const patch = {};
    ROUTING_FIELDS.forEach(f => {
      const newVal = (draft[f.key] || '').trim();
      const oldVal = (detail?.[f.key] || '').trim();
      if (newVal !== oldVal) patch[f.key] = newVal;
    });

    if (Object.keys(patch).length === 0) {
      setEditing(false);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.patchAnalysisRouting(workItemId, patch);
      setEditing(false);
      onSaved?.(patch);
    } catch (err) {
      setError(err.message || 'Failed to save override');
    } finally {
      setSaving(false);
    }
  }, [draft, detail, workItemId, onSaved]);

  const handleFieldChange = useCallback((key, value) => {
    setDraft(prev => ({ ...prev, [key]: value }));
  }, []);

  /* ── No data state ── */
  if (!hasData && !editing) {
    return (
      <div className="stt-empty">
        <div className="stt-empty-icon">🗂️</div>
        <h3>No ServiceTree Match</h3>
        <p>No ServiceTree routing data was found for the detected services in this work item.</p>
        <button className="stt-btn stt-btn-primary" onClick={handleEdit}>
          ✏️ Add Routing Manually
        </button>
      </div>
    );
  }

  return (
    <div className="stt-container">
      {/* ── Header bar ── */}
      <div className="stt-header">
        <div className="stt-header-left">
          <h3>🗂️ ServiceTree Routing</h3>
          {isOverridden && (
            <span className="stt-override-badge" title={`Overridden by ${detail.routingOverrideBy} at ${detail.routingOverrideAt || '?'}`}>
              ⚡ Admin Override
            </span>
          )}
        </div>
        <div className="stt-header-actions">
          {!editing ? (
            <button className="stt-btn stt-btn-outline" onClick={handleEdit}>
              ✏️ Edit Routing
            </button>
          ) : (
            <>
              <button className="stt-btn stt-btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? '⏳ Saving...' : '💾 Save Override'}
              </button>
              <button className="stt-btn stt-btn-ghost" onClick={handleCancel} disabled={saving}>
                Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="stt-error">{error}</div>}

      {/* ── Visual routing flow ── */}
      {!editing && hasData && (
        <div className="stt-flow">
          {ROUTING_FIELDS.filter(f => detail[f.key]).map((f, i, arr) => (
            <React.Fragment key={f.key}>
              <div className="stt-flow-node">
                <span className="stt-flow-icon">{f.icon}</span>
                <span className="stt-flow-label">{f.label}</span>
                <span className="stt-flow-value">{detail[f.key]}</span>
              </div>
              {i < arr.length - 1 && <div className="stt-flow-arrow">→</div>}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* ── Grouped cards ── */}
      <div className="stt-groups">
        {GROUPS.map(group => {
          const fields = ROUTING_FIELDS.filter(f => f.group === group.key);
          const groupHasData = fields.some(f => detail[f.key] || (editing && draft[f.key]));
          if (!groupHasData && !editing) return null;

          return (
            <div className="stt-card" key={group.key} style={{ '--card-accent': group.accent }}>
              <div className="stt-card-header">
                <span className="stt-card-title">{group.title}</span>
                <span className="stt-card-desc">{group.description}</span>
              </div>
              <div className="stt-card-body">
                {fields.map(f => {
                  const value = editing ? draft[f.key] : detail[f.key];
                  if (!editing && !value) return null;

                  return (
                    <div className="stt-field" key={f.key}>
                      <div className="stt-field-label">
                        <span className="stt-field-icon">{f.icon}</span>
                        {f.label}
                      </div>
                      {editing ? (
                        <input
                          className="stt-field-input"
                          type="text"
                          value={draft[f.key] || ''}
                          onChange={e => handleFieldChange(f.key, e.target.value)}
                          disabled={saving}
                          placeholder={`Enter ${f.label.toLowerCase()}...`}
                        />
                      ) : (
                        <div className={`stt-field-value ${f.key === 'solutionArea' ? 'stt-highlight' : ''}`}>
                          {value}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Override audit info ── */}
      {isOverridden && !editing && (
        <div className="stt-audit">
          <span className="stt-audit-icon">📝</span>
          <span>
            Last overridden by <strong>{detail.routingOverrideBy}</strong>
            {detail.routingOverrideAt && <> on {new Date(detail.routingOverrideAt).toLocaleDateString()}</>}
          </span>
        </div>
      )}
    </div>
  );
}
