/**
 * TriggerForm — Create / Edit Trigger Form
 * ============================================
 *
 * Form for creating or editing a trigger. A trigger has:
 *   - name, description
 *   - priority (lower = evaluated first)
 *   - expression (nested AND/OR/NOT referencing rules)
 *   - onTrue (route ID to execute when the expression is TRUE)
 *
 * The expression is edited via the ExpressionBuilder component.
 * The route is selected from a dropdown of available routes.
 *
 * Props:
 *   trigger   : object | null — existing trigger for edit mode
 *   rules     : Array — available rules (for expression builder)
 *   routes    : Array — available routes (for onTrue dropdown)
 *   onSubmit  : (formData) => void
 *   onCancel  : () => void
 */

import React, { useState, useEffect } from 'react';
import ExpressionBuilder from './ExpressionBuilder';
import TeamScopeSelect from '../common/TeamScopeSelect';
import { deepClone } from '../../utils/helpers';


export default function TriggerForm({ trigger, rules = [], routes = [], teams = [], onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(100);
  const [expression, setExpression] = useState({ and: [] });
  const [onTrue, setOnTrue] = useState('');
  const [status, setStatus] = useState('active');
  const [triageTeamId, setTriageTeamId] = useState('');
  const [submitting, setSubmitting] = useState(false);


  // ── Populate form for edit mode ──────────────────────────────
  useEffect(() => {
    if (trigger) {
      setName(trigger.name || '');
      setDescription(trigger.description || '');
      setPriority(trigger.priority ?? 100);
      setExpression(trigger.expression ? deepClone(trigger.expression) : { and: [] });
      setOnTrue(trigger.onTrue || '');
      setStatus(trigger.status || 'active');
      setTriageTeamId(trigger.triageTeamId || '');
    } else {
      setName('');
      setDescription('');
      setPriority(100);
      setExpression({ and: [] });
      setOnTrue('');
      setStatus('active');
      setTriageTeamId('');
    }
  }, [trigger]);


  // ── Submit ───────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        priority: Number(priority),
        expression,
        onTrue,
        status,
        triageTeamId: triageTeamId || null,
      });
    } finally {
      setSubmitting(false);
    }
  };


  // ── Render ───────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} className="trigger-form">
      {/* Name */}
      <div className="form-group">
        <label htmlFor="trigger-name">Name *</label>
        <input
          id="trigger-name"
          className="form-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., No Milestone Feature Request"
          required
        />
      </div>

      {/* Description */}
      <div className="form-group">
        <label htmlFor="trigger-desc">Description</label>
        <textarea
          id="trigger-desc"
          className="form-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="When does this trigger match?"
          rows={2}
        />
      </div>

      {/* Priority */}
      <div className="form-group">
        <label htmlFor="trigger-priority">Priority *</label>
        <input
          id="trigger-priority"
          className="form-input"
          type="number"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          min={1}
          max={9999}
          required
        />
        <span className="hint">
          Lower number = higher priority. Triggers are evaluated in priority order;
          the first TRUE match wins.
        </span>
      </div>

      {/* Expression Builder */}
      <div className="form-group">
        <label>Expression *</label>
        <span className="hint">
          Build a boolean expression referencing rules. Click the AND/OR toggle
          to switch operators. Use + Add Rule to add conditions.
        </span>
        <ExpressionBuilder
          expression={expression}
          onChange={setExpression}
          rules={rules}
        />
      </div>

      {/* Route (onTrue) */}
      <div className="form-group">
        <label htmlFor="trigger-route">Target Route (onTrue) *</label>
        <select
          id="trigger-route"
          className="form-select"
          value={onTrue}
          onChange={(e) => setOnTrue(e.target.value)}
          required
        >
          <option value="">Select a route…</option>
          {routes
            .filter((r) => r.status === 'active')
            .map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.actions?.length || 0} actions)
              </option>
            ))}
        </select>
        <span className="hint">
          The route to execute when this trigger's expression evaluates to TRUE
        </span>
      </div>

      {/* Triage Team Scope */}
      {teams.length > 0 && (
        <TeamScopeSelect value={triageTeamId} onChange={setTriageTeamId} teams={teams} />
      )}

      {/* Status */}
      <div className="form-group">
        <label htmlFor="trigger-status">Status</label>
        <select
          id="trigger-status"
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
          {submitting ? 'Saving…' : trigger ? 'Update Trigger' : 'Create Trigger'}
        </button>
      </div>
    </form>
  );
}
