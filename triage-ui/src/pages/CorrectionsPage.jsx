/**
 * CorrectionsPage — Corrective Learning Management
 * ====================================================
 *
 * View, add, and delete corrections that bias the AI classifier.
 * Replaces the legacy admin_service.py corrections management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
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


export default function CorrectionsPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [corrections, setCorrections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [form, setForm] = useState({
    original_text: '',
    pattern: '',
    original_category: '',
    corrected_category: '',
    corrected_intent: '',
    correction_notes: '',
  });


  // ── Load ─────────────────────────────────────────────────────
  const loadCorrections = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listCorrections();
      setCorrections(data.corrections || []);
    } catch (err) {
      addToast?.('Failed to load corrections: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { loadCorrections(); }, [loadCorrections]);


  // ── Add ──────────────────────────────────────────────────────
  async function handleAdd(e) {
    e.preventDefault();
    if (!form.original_category || !form.corrected_category) {
      addToast?.('Original and corrected categories are required', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await api.addCorrection(form);
      addToast?.('Correction added', 'success');
      setForm({
        original_text: '',
        pattern: '',
        original_category: '',
        corrected_category: '',
        corrected_intent: '',
        correction_notes: '',
      });
      loadCorrections();
    } catch (err) {
      addToast?.('Failed to add: ' + err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  }


  // ── Delete ───────────────────────────────────────────────────
  async function handleDelete(index) {
    if (!window.confirm(`Delete correction #${index + 1}?`)) return;
    try {
      await api.deleteCorrection(index);
      addToast?.('Correction deleted', 'success');
      loadCorrections();
    } catch (err) {
      addToast?.('Failed to delete: ' + err.message, 'error');
    }
  }

  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }


  // ── Render ───────────────────────────────────────────────────
  return (
    <div className="corrections-page">
      <h1>Corrections</h1>
      <p style={{ color: 'var(--text-light)', marginBottom: 'var(--space-lg)' }}>
        Add corrective learning entries to improve classification accuracy over time.
      </p>

      {/* Add form */}
      <form className="corrections-form-card" onSubmit={handleAdd}>
        <h2>Add Correction</h2>
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
            <label>Pattern (optional)</label>
            <input
              type="text"
              value={form.pattern}
              onChange={(e) => updateForm('pattern', e.target.value)}
              placeholder="e.g., service_availability_query"
            />
          </div>

          <div className="corrections-field">
            <label>Corrected Intent (optional)</label>
            <input
              type="text"
              value={form.corrected_intent}
              onChange={(e) => updateForm('corrected_intent', e.target.value)}
              placeholder="e.g., regional_availability"
            />
          </div>

          <div className="corrections-field full-width">
            <label>Notes</label>
            <input
              type="text"
              value={form.correction_notes}
              onChange={(e) => updateForm('correction_notes', e.target.value)}
              placeholder="Why this is the correct category"
            />
          </div>
        </div>

        <div className="corrections-form-actions">
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Adding…' : 'Add Correction'}
          </button>
        </div>
      </form>

      {/* Corrections list */}
      <div className="corrections-list-card">
        <div className="corrections-list-header">
          <h2>Existing Corrections</h2>
          <span className="corrections-count">{corrections.length} entries</span>
        </div>

        {loading ? (
          <div className="corrections-list-empty">Loading…</div>
        ) : corrections.length === 0 ? (
          <div className="corrections-list-empty">
            No corrections yet. Add one above to improve future classifications.
          </div>
        ) : (
          <table className="corrections-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Original → Corrected</th>
                <th>Intent</th>
                <th>Notes</th>
                <th>Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {corrections.map((c, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>
                    <span>{formatCategory(c.original_category)}</span>
                    <span className="correction-arrow"> → </span>
                    <span style={{ fontWeight: 600 }}>
                      {formatCategory(c.corrected_category)}
                    </span>
                  </td>
                  <td>{formatCategory(c.corrected_intent)}</td>
                  <td className="correction-notes" title={c.correction_notes}>
                    {c.correction_notes || '—'}
                  </td>
                  <td style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-light)' }}>
                    {c.timestamp
                      ? new Date(c.timestamp).toLocaleDateString()
                      : '—'}
                  </td>
                  <td>
                    <button
                      className="correction-delete-btn"
                      onClick={() => handleDelete(i)}
                      title="Delete this correction"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
