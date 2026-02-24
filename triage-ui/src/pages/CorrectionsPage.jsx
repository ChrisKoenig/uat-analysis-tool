/**
 * CorrectionsPage — Corrective Learning Management
 * ====================================================
 *
 * View, add, and delete corrections that bias the AI classifier.
 * Follows the same blade pattern as Rules, Triggers, Actions, Routes.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import ConfirmDialog from '../components/common/ConfirmDialog';
import './CorrectionsPage.css';


const CATEGORIES = [
  'technical_support',
  'feature_request',
  'service_availability',
  'capacity_management',
  'cost_billing',
  'training_documentation',
  'seeking_guidance',
  'product_retirement',
  'security_compliance',
  'migration',
  'performance',
];

function formatCategory(cat) {
  return (cat || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

function toSnakeCase(str) {
  return (str || '').trim().toLowerCase().replace(/\s+/g, '_');
}

const EMPTY_FORM = {
  original_text: '',
  pattern: '',
  original_category: '',
  corrected_category: '',
  corrected_intent: '',
  correction_notes: '',
};


export default function CorrectionsPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [corrections, setCorrections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formMode, setFormMode] = useState(null);  // 'create' | 'edit' | null
  const [selected, setSelected] = useState(null);  // clicked row
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Form state
  const [form, setForm] = useState({ ...EMPTY_FORM });


  // ── Load ─────────────────────────────────────────────────────
  const loadCorrections = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listCorrections();
      setCorrections(
        (data.corrections || []).map((c, i) => ({ ...c, _index: i }))
      );
    } catch (err) {
      addToast?.('Failed to load corrections: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { loadCorrections(); }, [loadCorrections]);


  // ── Handlers ─────────────────────────────────────────────────

  const handleCreate = () => {
    setSelected(null);
    setForm({ ...EMPTY_FORM });
    setFormMode('create');
  };

  const handleRowClick = (item) => {
    setSelected(item);
    setForm({
      original_text: item.original_text || '',
      pattern: formatCategory(item.pattern),
      original_category: item.original_category || '',
      corrected_category: item.corrected_category || '',
      corrected_intent: formatCategory(item.corrected_intent),
      correction_notes: item.correction_notes || '',
    });
    setFormMode('edit');
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelected(null);
    setForm({ ...EMPTY_FORM });
  };

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.original_category || !form.corrected_category) {
      addToast?.('Original and corrected categories are required', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        pattern: toSnakeCase(form.pattern),
        corrected_intent: toSnakeCase(form.corrected_intent),
      };
      if (formMode === 'edit' && selected != null) {
        await api.updateCorrection(selected._index, payload);
        addToast?.('Correction updated', 'success');
      } else {
        await api.addCorrection(payload);
        addToast?.('Correction added', 'success');
      }
      setFormMode(null);
      setSelected(null);
      setForm({ ...EMPTY_FORM });
      loadCorrections();
    } catch (err) {
      addToast?.('Failed to save: ' + err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  }

  const handleDeleteClick = (item) => {
    setDeleteTarget(item);
  };

  async function handleDeleteConfirm() {
    if (deleteTarget == null) return;
    try {
      await api.deleteCorrection(deleteTarget._index);
      addToast?.('Correction deleted', 'success');
      if (selected?._index === deleteTarget._index) handleClosePanel();
      loadCorrections();
    } catch (err) {
      addToast?.('Failed to delete: ' + err.message, 'error');
    } finally {
      setDeleteTarget(null);
    }
  }

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    {
      key: 'original_category',
      label: 'Original Category',
      width: '22%',
      render: (val) => formatCategory(val),
    },
    {
      key: 'corrected_category',
      label: 'Corrected Category',
      width: '22%',
      render: (val) => <strong>{formatCategory(val)}</strong>,
    },
    {
      key: 'corrected_intent',
      label: 'Intent',
      width: '18%',
      render: (val) => val ? formatCategory(val) : <span className="text-muted">—</span>,
    },
    {
      key: 'correction_notes',
      label: 'Notes',
      width: '28%',
      render: (val) => val
        ? <span className="correction-notes-cell" title={val}>{val}</span>
        : <span className="text-muted">—</span>,
    },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="corrections-page">
      {/* Page Header */}
      <div className="page-header">
        <h1>✏️ Corrections</h1>
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Correction
          </button>
        </div>
      </div>

      <div className="corrections-layout">
        {/* Left: Corrections Table */}
        <div className={`corrections-list ${formMode ? 'corrections-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={corrections}
              loading={loading}
              emptyMessage="No corrections yet. Add one to improve future classifications."
              onRowClick={handleRowClick}
              onDelete={handleDeleteClick}
            />
          </div>
          <div className="corrections-count">
            {corrections.length} correction{corrections.length !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Right: Detail / Form Panel */}
        {formMode && (
          <div className="corrections-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Correction' : `Edit: ${formatCategory(selected?.original_category)} → ${formatCategory(selected?.corrected_category)}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">
                ✕
              </button>
            </div>
            <div className="card-body">
              <form onSubmit={handleSubmit}>
                <div className="corrections-form-grid">
                  <div className="corrections-field full-width">
                    <label>Misclassified Text</label>
                    <input
                      type="text"
                      value={form.original_text}
                      onChange={(e) => updateForm('original_text', e.target.value)}
                      placeholder="The text that was misclassified"
                    />
                  </div>

                  <div className="corrections-field">
                    <label>Original Category *</label>
                    <select
                      value={form.original_category}
                      onChange={(e) => updateForm('original_category', e.target.value)}
                    >
                      <option value="">Select...</option>
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{formatCategory(c)}</option>
                      ))}
                    </select>
                  </div>

                  <div className="corrections-field">
                    <label>Corrected Category *</label>
                    <select
                      value={form.corrected_category}
                      onChange={(e) => updateForm('corrected_category', e.target.value)}
                    >
                      <option value="">Select...</option>
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{formatCategory(c)}</option>
                      ))}
                    </select>
                  </div>

                  <div className="corrections-field">
                    <label>Pattern</label>
                    <input
                      type="text"
                      value={form.pattern}
                      onChange={(e) => updateForm('pattern', e.target.value)}
                      placeholder="e.g., Service Availability Query"
                    />
                  </div>

                  <div className="corrections-field">
                    <label>Corrected Intent</label>
                    <input
                      type="text"
                      value={form.corrected_intent}
                      onChange={(e) => updateForm('corrected_intent', e.target.value)}
                      placeholder="e.g., Regional Availability"
                    />
                  </div>

                  <div className="corrections-field full-width">
                    <label>Notes</label>
                    <textarea
                      value={form.correction_notes}
                      onChange={(e) => updateForm('correction_notes', e.target.value)}
                      placeholder="Why this is the correct category"
                      rows={3}
                    />
                  </div>
                </div>

                <div className="corrections-form-actions">
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting
                      ? 'Saving…'
                      : formMode === 'edit' ? 'Save Changes' : 'Add Correction'}
                  </button>
                  {formMode === 'edit' && selected && (
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => handleDeleteClick(selected)}
                    >
                      Delete
                    </button>
                  )}
                  <button type="button" className="btn btn-secondary" onClick={handleClosePanel}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Correction"
        message={`Delete this correction (${formatCategory(deleteTarget?.original_category)} → ${formatCategory(deleteTarget?.corrected_category)})?`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
