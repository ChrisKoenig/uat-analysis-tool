/**
 * ServiceTreeRouting — Inline-editable ServiceTree routing section
 * =================================================================
 *
 * Displays ServiceTree routing fields on an analysis record.
 * Admin can click the edit icon to override any field, then save
 * via PATCH /analysis/{workItemId}/routing.
 *
 * Props:
 *   detail       — the full analysis detail object
 *   workItemId   — the ADO work item ID
 *   onSaved(updatedFields) — callback after successful save
 *   compact      — if true, renders a compact card (for EvaluatePage)
 */

import React, { useState, useCallback } from 'react';
import * as api from '../api/triageApi';
import './ServiceTreeRouting.css';

const ROUTING_FIELDS = [
  { key: 'serviceTreeMatch',    label: 'Matched Service' },
  { key: 'serviceTreeOffering', label: 'Offering' },
  { key: 'solutionArea',        label: 'Solution Area' },
  { key: 'csuDri',              label: 'CSU DRI' },
  { key: 'areaPathAdo',         label: 'ADO Area Path' },
  { key: 'releaseManager',      label: 'Release Manager' },
  { key: 'devContact',          label: 'Dev Contact' },
];

export default function ServiceTreeRouting({ detail, workItemId, onSaved, compact = false }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Check if any ServiceTree data exists
  const hasData = detail && ROUTING_FIELDS.some(f => detail[f.key]);

  const handleEdit = useCallback(() => {
    // Seed draft with current values
    const current = {};
    ROUTING_FIELDS.forEach(f => {
      current[f.key] = detail?.[f.key] || '';
    });
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
    // Build patch with only changed fields
    const patch = {};
    ROUTING_FIELDS.forEach(f => {
      const newVal = (draft[f.key] || '').trim();
      const oldVal = (detail?.[f.key] || '').trim();
      if (newVal !== oldVal) {
        patch[f.key] = newVal;
      }
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

  const isOverridden = detail?.routingOverrideBy;

  if (compact) {
    // Compact version for EvaluatePage cards
    return (
      <div className="st-routing-compact">
        <strong>🗂️ ServiceTree Routing</strong>
        {hasData ? (
          <div className="st-routing-compact-grid">
            {ROUTING_FIELDS.filter(f => detail[f.key]).map(f => (
              <div key={f.key} className="st-routing-compact-item">
                <span className="st-label">{f.label}:</span>
                <span className="st-value">{detail[f.key]}</span>
              </div>
            ))}
          </div>
        ) : (
          <span className="no-data">No ServiceTree match</span>
        )}
      </div>
    );
  }

  return (
    <section className="analysis-section st-routing-section">
      <div className="st-routing-header">
        <h4>🗂️ ServiceTree Routing</h4>
        {hasData && !editing && (
          <button
            className="btn btn-ghost btn-xs st-edit-btn"
            onClick={handleEdit}
            title="Override routing fields"
          >
            ✏️ Edit
          </button>
        )}
        {isOverridden && !editing && (
          <span className="st-override-badge" title={`Overridden by ${detail.routingOverrideBy} at ${detail.routingOverrideAt || '?'}`}>
            Admin Override
          </span>
        )}
      </div>

      {error && (
        <div className="st-routing-error">{error}</div>
      )}

      {editing ? (
        /* ── Edit mode ── */
        <div className="st-routing-edit-grid">
          {ROUTING_FIELDS.map(f => (
            <div key={f.key} className="st-routing-edit-field">
              <label>{f.label}</label>
              <input
                type="text"
                value={draft[f.key] || ''}
                onChange={e => handleFieldChange(f.key, e.target.value)}
                disabled={saving}
                placeholder={`Enter ${f.label.toLowerCase()}...`}
              />
            </div>
          ))}
          <div className="st-routing-edit-actions">
            <button
              className="btn btn-sm btn-primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Override'}
            </button>
            <button
              className="btn btn-sm btn-ghost"
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : hasData ? (
        /* ── Display mode ── */
        <div className="analysis-field-grid st-routing-grid">
          {ROUTING_FIELDS.map(f => (
            detail[f.key] ? (
              <div key={f.key} className="analysis-field">
                <label>{f.label}</label>
                <span className={`st-routing-value ${f.key === 'solutionArea' ? 'st-solution-area' : ''}`}>
                  {detail[f.key]}
                </span>
              </div>
            ) : null
          ))}
        </div>
      ) : (
        /* ── No data ── */
        <p className="no-data">No ServiceTree match found for detected services</p>
      )}
    </section>
  );
}
