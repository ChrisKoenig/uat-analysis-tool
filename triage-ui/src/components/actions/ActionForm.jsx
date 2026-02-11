/**
 * ActionForm — Create / Edit Action Form
 * ========================================
 *
 * Form component for creating or editing a triage action.
 *
 * An action defines a field modification:
 *   field     : "System.AssignedTo"
 *   operation : "set"
 *   value     : "@AI Triage"
 *   valueType : "static"
 *
 * The form adapts its UI based on the selected operation:
 *   - "set"          → simple text input
 *   - "set_computed" → dropdown for computed expressions
 *   - "copy"         → field reference input
 *   - "append"       → text with newline explanation
 *   - "template"     → template string with variable chips
 *
 * Props:
 *   action   : object | null — existing action data for edit mode
 *   onSubmit : (formData) => void
 *   onCancel : () => void
 */

import React, { useState, useEffect } from 'react';
import { OPERATIONS, TEMPLATE_VARIABLES, VALUE_TYPES } from '../../utils/constants';


export default function ActionForm({ action, onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [field, setField] = useState('');
  const [operation, setOperation] = useState('set');
  const [value, setValue] = useState('');
  const [valueType, setValueType] = useState('static');
  const [status, setStatus] = useState('active');
  const [submitting, setSubmitting] = useState(false);


  // ── Populate form when editing ───────────────────────────────
  useEffect(() => {
    if (action) {
      setName(action.name || '');
      setDescription(action.description || '');
      setField(action.field || '');
      setOperation(action.operation || 'set');
      setValue(action.value ?? '');
      setValueType(action.valueType || 'static');
      setStatus(action.status || 'active');
    } else {
      setName('');
      setDescription('');
      setField('');
      setOperation('set');
      setValue('');
      setValueType('static');
      setStatus('active');
    }
  }, [action]);


  // ── Submit ───────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        field,
        operation,
        value: value || null,
        valueType,
        status,
      });
    } finally {
      setSubmitting(false);
    }
  };

  /** Insert a template variable at cursor position */
  const insertTemplateVar = (varName) => {
    setValue((prev) => prev + varName);
  };


  // ── Render ───────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} className="action-form">
      {/* Name */}
      <div className="form-group">
        <label htmlFor="action-name">Name *</label>
        <input
          id="action-name"
          className="form-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Assign to AI Triage Team"
          required
        />
      </div>

      {/* Description */}
      <div className="form-group">
        <label htmlFor="action-desc">Description</label>
        <textarea
          id="action-desc"
          className="form-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What field change does this action make?"
          rows={2}
        />
      </div>

      {/* Target Field */}
      <div className="form-group">
        <label htmlFor="action-field">Target Field *</label>
        <input
          id="action-field"
          className="form-input"
          type="text"
          value={field}
          onChange={(e) => setField(e.target.value)}
          placeholder="e.g., System.AssignedTo"
          required
        />
        <span className="hint">ADO field reference name to modify</span>
      </div>

      {/* Operation */}
      <div className="form-group">
        <label htmlFor="action-op">Operation *</label>
        <select
          id="action-op"
          className="form-select"
          value={operation}
          onChange={(e) => setOperation(e.target.value)}
        >
          {OPERATIONS.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label} — {op.description}
            </option>
          ))}
        </select>
      </div>

      {/* Value — adapts based on operation */}
      <div className="form-group">
        <label htmlFor="action-value">Value</label>

        {operation === 'set_computed' ? (
          /* Computed: dropdown of known expressions */
          <select
            id="action-value"
            className="form-select"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          >
            <option value="">Select computed value…</option>
            <option value="today()">today() — Current date</option>
            <option value="currentUser()">currentUser() — Logged-in user</option>
          </select>
        ) : operation === 'copy' ? (
          /* Copy: source field reference */
          <>
            <input
              id="action-value"
              className="form-input"
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Source field, e.g., System.CreatedBy"
            />
            <span className="hint">Field reference name to copy from</span>
          </>
        ) : operation === 'template' ? (
          /* Template: text with variable insertion */
          <>
            <textarea
              id="action-value"
              className="form-textarea"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Template with variables, e.g.:&#10;Triaged by {currentUser()} on {today()}"
              rows={3}
            />
            <div className="template-vars">
              <span className="hint">Insert variable:</span>
              {TEMPLATE_VARIABLES.map((v) => (
                <button
                  key={v}
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => insertTemplateVar(v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </>
        ) : operation === 'append' ? (
          /* Append: text with newline note */
          <>
            <textarea
              id="action-value"
              className="form-textarea"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Text to append"
              rows={3}
            />
            <span className="hint">
              Appended with a newline separator to the existing field value
            </span>
          </>
        ) : (
          /* Default set: simple text */
          <input
            id="action-value"
            className="form-input"
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Value to set"
          />
        )}
      </div>

      {/* Value Type */}
      <div className="form-group">
        <label htmlFor="action-vtype">Value Type</label>
        <select
          id="action-vtype"
          className="form-select"
          value={valueType}
          onChange={(e) => setValueType(e.target.value)}
        >
          {VALUE_TYPES.map((vt) => (
            <option key={vt.value} value={vt.value}>{vt.label}</option>
          ))}
        </select>
      </div>

      {/* Status */}
      <div className="form-group">
        <label htmlFor="action-status">Status</label>
        <select
          id="action-status"
          className="form-select"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
          <option value="staged">Staged (test only)</option>
        </select>
      </div>

      {/* Form Actions */}
      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : action ? 'Update Action' : 'Create Action'}
        </button>
      </div>
    </form>
  );
}
