/**
 * RuleForm — Create / Edit Rule Form
 * =====================================
 *
 * Form component for creating or editing a triage rule.
 *
 * A rule evaluates a single ADO field using an operator and value:
 *   field: "Custom.SolutionArea"
 *   operator: "equals"
 *   value: "AI Apps and Agents"
 *
 * The form dynamically shows/hides the value input based on
 * the selected operator (e.g., isNull/isNotNull need no value).
 *
 * For 'in' and 'notIn' operators, the value is entered as a
 * comma-separated list and stored as an array.
 *
 * Props:
 *   rule     : object | null — existing rule data for edit mode
 *   onSubmit : (formData) => void
 *   onCancel : () => void
 */

import React, { useState, useEffect } from 'react';
import * as api from '../../api/triageApi';
import { OPERATORS, VALUELESS_OPERATORS } from '../../utils/constants';
import FieldCombobox from '../common/FieldCombobox';


export default function RuleForm({ rule, onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [field, setField] = useState('');
  const [operator, setOperator] = useState('equals');
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('active');
  const [submitting, setSubmitting] = useState(false);
  const [adoFields, setAdoFields] = useState([]);

  // ── Load ADO field list once ─────────────────────────────────
  useEffect(() => {
    api.listFields({ canEvaluate: true })
      .then((data) => setAdoFields(data.items || []))
      .catch(() => setAdoFields([]));
  }, []);

  // Track whether the operator requires no value
  const isValueless = VALUELESS_OPERATORS.includes(operator);
  // Track whether the operator expects a list value
  const isListOperator = ['in', 'notIn'].includes(operator);


  // ── Populate form when editing ───────────────────────────────
  useEffect(() => {
    if (rule) {
      setName(rule.name || '');
      setDescription(rule.description || '');
      setField(rule.field || '');
      setOperator(rule.operator || 'equals');
      // Array values → comma-separated string for editing
      setValue(
        Array.isArray(rule.value)
          ? rule.value.join(', ')
          : (rule.value ?? '').toString()
      );
      setStatus(rule.status || 'active');
    } else {
      // Reset for create mode
      setName('');
      setDescription('');
      setField('');
      setOperator('equals');
      setValue('');
      setStatus('active');
    }
  }, [rule]);


  // ── Submit Handler ───────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      // Parse the value based on operator type
      let parsedValue = null;
      if (!isValueless) {
        if (isListOperator) {
          // Convert comma-separated string → array
          parsedValue = value
            .split(',')
            .map((v) => v.trim())
            .filter(Boolean);
        } else {
          parsedValue = value;
        }
      }

      await onSubmit({
        name,
        description,
        field,
        operator,
        value: parsedValue,
        status,
      });
    } finally {
      setSubmitting(false);
    }
  };


  // ── Render ───────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} className="rule-form">
      {/* Name */}
      <div className="form-group">
        <label htmlFor="rule-name">Name *</label>
        <input
          id="rule-name"
          className="form-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Is Feature Request"
          required
        />
      </div>

      {/* Description */}
      <div className="form-group">
        <label htmlFor="rule-desc">Description</label>
        <textarea
          id="rule-desc"
          className="form-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this rule check?"
          rows={2}
        />
      </div>

      {/* ADO Field */}
      <div className="form-group">
        <label htmlFor="rule-field">ADO Field *</label>
        <FieldCombobox
          id="rule-field"
          value={field}
          onChange={setField}
          fields={adoFields}
          placeholder="Click here and type to search fields…"
          required
        />
        <span className="hint">
          Click the field above to browse available ADO fields, or type to search by name.
        </span>
      </div>

      {/* Operator */}
      <div className="form-group">
        <label htmlFor="rule-operator">Operator *</label>
        <select
          id="rule-operator"
          className="form-select"
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
        >
          {/* Group operators by category */}
          {['String / All', 'String', 'Hierarchical', 'Numeric / Date'].map((group) => (
            <optgroup key={group} label={group}>
              {OPERATORS
                .filter((op) => op.group === group)
                .map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* Value (hidden for isNull/isNotNull) */}
      {!isValueless && (
        <div className="form-group">
          <label htmlFor="rule-value">Value *</label>
          {isListOperator ? (
            <>
              <textarea
                id="rule-value"
                className="form-textarea"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Comma-separated values, e.g.:&#10;AI Apps, Cloud Infrastructure, Security"
                rows={3}
                required
              />
              <span className="hint">Enter values separated by commas</span>
            </>
          ) : (
            <input
              id="rule-value"
              className="form-input"
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Comparison value"
              required
            />
          )}
        </div>
      )}

      {/* Status */}
      <div className="form-group">
        <label htmlFor="rule-status">Status</label>
        <select
          id="rule-status"
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
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={submitting}
        >
          {submitting ? 'Saving…' : rule ? 'Update Rule' : 'Create Rule'}
        </button>
      </div>
    </form>
  );
}
