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
import { OPERATORS, VALUELESS_OPERATORS, MULTI_FIELD_OPERATORS } from '../../utils/constants';
import FieldCombobox from '../common/FieldCombobox';
import MultiFieldCombobox from '../common/MultiFieldCombobox';
import TeamScopeSelect from '../common/TeamScopeSelect';


export default function RuleForm({ rule, teams = [], onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [field, setField] = useState('');
  const [fields, setFields] = useState([]);          // multi-field for containsAny
  const [operator, setOperator] = useState('equals');
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('active');
  const [triageTeamId, setTriageTeamId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [adoFields, setAdoFields] = useState([]);
  const [fieldsLoading, setFieldsLoading] = useState(true);

  // ── Load ADO field list once ─────────────────────────────────
  useEffect(() => {
    api.listFields({ canEvaluate: true })
      .then((data) => setAdoFields(data.items || []))
      .catch(() => setAdoFields([]))
      .finally(() => setFieldsLoading(false));
  }, []);

  // Track whether the operator requires no value
  const isValueless = VALUELESS_OPERATORS.includes(operator);
  // Track whether the operator expects a list value
  const isListOperator = ['in', 'notIn'].includes(operator);
  // Track whether the operator uses multiple fields (containsAny)
  const isMultiField = MULTI_FIELD_OPERATORS.includes(operator);


  // ── Populate form when editing ───────────────────────────────
  useEffect(() => {
    if (rule) {
      setName(rule.name || '');
      setDescription(rule.description || '');
      setField(rule.field || '');
      setFields(Array.isArray(rule.fields) ? rule.fields : []);
      setOperator(rule.operator || 'equals');
      // Array values → comma-separated string for editing
      setValue(
        Array.isArray(rule.value)
          ? rule.value.join(', ')
          : (rule.value ?? '').toString()
      );
      setStatus(rule.status || 'active');
      setTriageTeamId(rule.triageTeamId || '');
    } else {
      // Reset for create mode
      setName('');
      setDescription('');
      setField('');
      setFields([]);
      setOperator('equals');
      setValue('');
      setStatus('active');
      setTriageTeamId('');
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
        if (isListOperator || isMultiField) {
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
        field: isMultiField ? '' : field,
        fields: isMultiField ? fields : [],
        operator,
        value: parsedValue,
        status,
        triageTeamId: triageTeamId || null,
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

      {/* Analysis/ADO Field(s) */}
      <div className="form-group">
        <label htmlFor="rule-field">
          {isMultiField ? 'Analysis/ADO Fields *' : 'Analysis/ADO Field *'}
        </label>
        {isMultiField ? (
          <>
            <MultiFieldCombobox
              id="rule-field"
              values={fields}
              onChange={setFields}
              fields={adoFields}
              placeholder="Search and select multiple fields…"
              required
              loading={fieldsLoading}
            />
            <span className="hint">
              Select one or more fields to search across.
              {operator === 'regexMatchAny'
                ? <> The rule matches if <strong>any</strong> selected field matches <strong>any</strong> regex pattern.</>
                : <> The rule matches if <strong>any</strong> selected field contains <strong>any</strong> keyword.</>}
            </span>
          </>
        ) : (
          <>
            <FieldCombobox
              id="rule-field"
              value={field}
              onChange={setField}
              fields={adoFields}
              placeholder="Click here and type to search fields…"
              required
              loading={fieldsLoading}
            />
            <span className="hint">
              Click the field above to browse available fields, or type to search by name.
            </span>
          </>
        )}
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
          <label htmlFor="rule-value">
            {isMultiField
              ? (operator === 'regexMatchAny' ? 'Regex Patterns *' : 'Keywords *')
              : 'Value *'}
          </label>
          {(isListOperator || isMultiField) ? (
            <>
              <textarea
                id="rule-value"
                className="form-textarea"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={
                  operator === 'regexMatchAny'
                    ? 'Comma-separated regex patterns, e.g.:\nSR\\d+, ICM\\d+, INC-[A-Z]+-\\d+'
                    : isMultiField
                      ? 'Comma-separated keywords, e.g.:\nCapacity, Quota, Increase, Allocation'
                      : 'Comma-separated values, e.g.:\nAI Apps, Cloud Infrastructure, Security'
                }
                rows={3}
                required
              />
              <span className="hint">
                {operator === 'regexMatchAny'
                  ? 'Enter regex patterns separated by commas — matches if any field matches any pattern (case-insensitive)'
                  : isMultiField
                    ? 'Enter keywords separated by commas — matches if any field contains any keyword'
                    : 'Enter values separated by commas'}
              </span>
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

      {/* Triage Team Scope */}
      {teams.length > 0 && (
        <TeamScopeSelect value={triageTeamId} onChange={setTriageTeamId} teams={teams} />
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
