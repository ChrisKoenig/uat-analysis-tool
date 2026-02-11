/**
 * TreeForm — Create / Edit Decision Tree Form
 * ==============================================
 *
 * Form for creating or editing a decision tree. A tree has:
 *   - name, description
 *   - priority (lower = evaluated first)
 *   - expression (nested AND/OR/NOT referencing rules)
 *   - onTrue (route ID to execute when the expression is TRUE)
 *
 * The expression is edited via the ExpressionBuilder component.
 * The route is selected from a dropdown of available routes.
 *
 * Props:
 *   tree      : object | null — existing tree for edit mode
 *   rules     : Array — available rules (for expression builder)
 *   routes    : Array — available routes (for onTrue dropdown)
 *   onSubmit  : (formData) => void
 *   onCancel  : () => void
 */

import React, { useState, useEffect } from 'react';
import ExpressionBuilder from './ExpressionBuilder';
import { deepClone } from '../../utils/helpers';


export default function TreeForm({ tree, rules = [], routes = [], onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(100);
  const [expression, setExpression] = useState({ and: [] });
  const [onTrue, setOnTrue] = useState('');
  const [status, setStatus] = useState('active');
  const [submitting, setSubmitting] = useState(false);


  // ── Populate form for edit mode ──────────────────────────────
  useEffect(() => {
    if (tree) {
      setName(tree.name || '');
      setDescription(tree.description || '');
      setPriority(tree.priority ?? 100);
      setExpression(tree.expression ? deepClone(tree.expression) : { and: [] });
      setOnTrue(tree.onTrue || '');
      setStatus(tree.status || 'active');
    } else {
      setName('');
      setDescription('');
      setPriority(100);
      setExpression({ and: [] });
      setOnTrue('');
      setStatus('active');
    }
  }, [tree]);


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
      });
    } finally {
      setSubmitting(false);
    }
  };


  // ── Render ───────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} className="tree-form">
      {/* Name */}
      <div className="form-group">
        <label htmlFor="tree-name">Name *</label>
        <input
          id="tree-name"
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
        <label htmlFor="tree-desc">Description</label>
        <textarea
          id="tree-desc"
          className="form-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="When does this tree match?"
          rows={2}
        />
      </div>

      {/* Priority */}
      <div className="form-group">
        <label htmlFor="tree-priority">Priority *</label>
        <input
          id="tree-priority"
          className="form-input"
          type="number"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          min={1}
          max={9999}
          required
        />
        <span className="hint">
          Lower number = higher priority. Trees are evaluated in priority order;
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
        <label htmlFor="tree-route">Target Route (onTrue) *</label>
        <select
          id="tree-route"
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
          The route to execute when this tree's expression evaluates to TRUE
        </span>
      </div>

      {/* Status */}
      <div className="form-group">
        <label htmlFor="tree-status">Status</label>
        <select
          id="tree-status"
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
          {submitting ? 'Saving…' : tree ? 'Update Tree' : 'Create Tree'}
        </button>
      </div>
    </form>
  );
}
