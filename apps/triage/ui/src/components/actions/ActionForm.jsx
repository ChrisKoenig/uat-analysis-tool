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
import * as api from '../../api/triageApi';
import { OPERATIONS, TEMPLATE_VARIABLES } from '../../utils/constants';
import FieldCombobox from '../common/FieldCombobox';
import TeamScopeSelect from '../common/TeamScopeSelect';


export default function ActionForm({ action, teams = [], onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [field, setField] = useState('');
  const [operation, setOperation] = useState('set');
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('active');
  const [triageTeamId, setTriageTeamId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [adoFields, setAdoFields] = useState([]);
  const [readableFields, setReadableFields] = useState([]);
  const [fieldsLoading, setFieldsLoading] = useState(true);

  // ── Load ADO field lists ─────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.listFields({ canSet: true })
        .then((data) => setAdoFields(data.items || []))
        .catch(() => setAdoFields([])),
      api.listFields({ canEvaluate: true })
        .then((data) => setReadableFields(data.items || []))
        .catch(() => setReadableFields([])),
    ]).finally(() => setFieldsLoading(false));
  }, []);


  // ── Populate form when editing ───────────────────────────────
  useEffect(() => {
    if (action) {
      setName(action.name || '');
      setDescription(action.description || '');
      setField(action.field || '');
      setOperation(action.operation || 'set');
      setValue(action.value ?? '');
      setStatus(action.status || 'active');
      setTriageTeamId(action.triageTeamId || '');
    } else {
      setName('');
      setDescription('');
      setField('');
      setOperation('set');
      setValue('');
      setStatus('active');
      setTriageTeamId('');
    }
  }, [action]);


  // ── Submit ───────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    // Auto-derive valueType from the selected operation
    const OP_TO_VALUE_TYPE = {
      set: 'static',
      set_computed: 'computed',
      copy: 'field_ref',
      append: 'static',
      template: 'template',
    };
    // If append contains template variables, mark as template
    let derivedType = OP_TO_VALUE_TYPE[operation] || 'static';
    if (operation === 'append' && value && /\{[^}]+\}/.test(value)) {
      derivedType = 'template';
    }
    try {
      await onSubmit({
        name,
        description,
        field,
        operation,
        value: value || null,
        valueType: derivedType,
        status,
        triageTeamId: triageTeamId || null,
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
        <FieldCombobox
          id="action-field"
          value={field}
          onChange={setField}
          fields={adoFields}
          placeholder="Click here and type to search fields…"
          required
          loading={fieldsLoading}
        />
        <span className="hint">
          Click the field above to browse available ADO fields, or type to search by name.
        </span>
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
          /* Copy: source field picker */
          <>
            <FieldCombobox
              id="action-value"
              value={value}
              onChange={setValue}
              fields={readableFields}
              placeholder="Click to browse source fields…"
              loading={fieldsLoading}
            />
            <span className="hint">Select the field whose value will be copied into the target field</span>
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
          /* Append: text with variable insertion */
          <>
            <textarea
              id="action-value"
              className="form-textarea"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Text to append — can include variables like {SubmitterAlias}"
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

      {/* Triage Team Scope */}
      {teams.length > 0 && (
        <TeamScopeSelect value={triageTeamId} onChange={setTriageTeamId} teams={teams} />
      )}

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
