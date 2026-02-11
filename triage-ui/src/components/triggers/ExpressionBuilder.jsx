/**
 * ExpressionBuilder — Visual Trigger Expression Editor
 * ======================================================
 *
 * Interactive nested editor for building boolean expressions
 * that reference triage rules. Expressions combine rules with
 * AND / OR / NOT logic, nested to any depth.
 *
 * Expression format (matches backend Trigger.expression):
 *   { "and": ["rule-1", "rule-3"] }
 *   { "or": [{ "and": ["rule-1", "rule-2"] }, "rule-5"] }
 *   { "and": ["rule-1", { "not": "rule-3" }] }
 *
 * Features:
 *   - Visual nested groups (AND/OR containers)
 *   - Add rules from a dropdown of available rules
 *   - Toggle AND ↔ OR on any group
 *   - Wrap any item in NOT
 *   - Remove items or groups
 *   - Drag handles (visual hint — reorder by remove/re-add)
 *   - Color-coded nesting depth
 *
 * Props:
 *   expression : object — current expression
 *   onChange   : (newExpression) => void
 *   rules      : Array — list of available rules [{id, name, status}]
 */

import React from 'react';
import { deepClone, tempId } from '../../utils/helpers';
import './ExpressionBuilder.css';


// ---------------------------------------------------------------------------
// Helper: Extract operator from expression node
// ---------------------------------------------------------------------------
function getOperator(node) {
  if (typeof node === 'string') return 'rule';
  if (node.not !== undefined) return 'not';
  if (node.and) return 'and';
  if (node.or) return 'or';
  return 'unknown';
}

function getChildren(node) {
  if (node.and) return node.and;
  if (node.or) return node.or;
  return [];
}


// ---------------------------------------------------------------------------
// ExpressionBuilder Component
// ---------------------------------------------------------------------------

export default function ExpressionBuilder({ expression, onChange, rules = [] }) {
  /**
   * Replace a node at a specific path in the expression.
   * Path is an array of indices navigating into and/or children.
   */
  const updateAtPath = (path, updater) => {
    const newExpr = deepClone(expression);

    if (path.length === 0) {
      // Replace root
      onChange(updater(newExpr));
      return;
    }

    // Navigate to parent
    let current = newExpr;
    for (let i = 0; i < path.length - 1; i++) {
      const children = current.and || current.or;
      const child = children[path[i]];
      // Unwrap NOT to get to the group inside
      if (child.not && typeof child.not !== 'string') {
        current = child.not;
      } else {
        current = child;
      }
    }

    const children = current.and || current.or;
    const lastIndex = path[path.length - 1];
    const result = updater(children[lastIndex]);

    if (result === null) {
      // Remove the item
      children.splice(lastIndex, 1);
    } else {
      children[lastIndex] = result;
    }

    onChange(newExpr);
  };

  /** Add a rule to a group at the given path */
  const addRule = (groupPath, ruleId) => {
    const newExpr = deepClone(expression);
    let current = newExpr;

    for (const idx of groupPath) {
      const children = current.and || current.or;
      current = children[idx];
      if (current.not && typeof current.not !== 'string') {
        current = current.not;
      }
    }

    const children = current.and || current.or;
    children.push(ruleId);
    onChange(newExpr);
  };

  /** Add a nested group (AND/OR) to a group at the given path */
  const addGroup = (groupPath, type = 'and') => {
    const newExpr = deepClone(expression);
    let current = newExpr;

    for (const idx of groupPath) {
      const children = current.and || current.or;
      current = children[idx];
      if (current.not && typeof current.not !== 'string') {
        current = current.not;
      }
    }

    const children = current.and || current.or;
    children.push({ [type]: [] });
    onChange(newExpr);
  };

  /** Toggle the root or a group between AND ↔ OR */
  const toggleOperator = (path) => {
    updateAtPath(path, (node) => {
      if (node.and) return { or: node.and };
      if (node.or) return { and: node.or };
      return node;
    });
  };

  /** Wrap a node in NOT, or unwrap it */
  const toggleNot = (path) => {
    updateAtPath(path, (node) => {
      if (typeof node === 'object' && node.not !== undefined) {
        // Unwrap NOT
        return node.not;
      }
      // Wrap in NOT
      return { not: node };
    });
  };

  /** Remove a node at path */
  const removeNode = (path) => {
    updateAtPath(path, () => null);
  };


  // ── Render a single node recursively ─────────────────────────

  function renderNode(node, path, depth = 0) {
    const op = getOperator(node);

    // Leaf: rule reference
    if (op === 'rule') {
      const ruleId = node;
      const rule = rules.find((r) => r.id === ruleId);
      const ruleName = rule ? rule.name : ruleId;
      const isDisabled = rule?.status === 'disabled';

      return (
        <div className={`expr-leaf ${isDisabled ? 'expr-leaf-disabled' : ''}`} key={tempId()}>
          <span className="expr-leaf-icon">📋</span>
          <span className="expr-leaf-name" title={ruleId}>
            {ruleName}
          </span>
          {isDisabled && <span className="expr-leaf-badge">disabled</span>}
          <div className="expr-node-actions">
            <button
              className="btn-not"
              title="Wrap in NOT (negate this rule)"
              onClick={() => toggleNot(path)}
            >
              NOT
            </button>
            <button
              className="btn-icon btn-sm"
              title="Remove"
              onClick={() => removeNode(path)}
            >
              ✕
            </button>
          </div>
        </div>
      );
    }

    // NOT wrapper
    if (op === 'not') {
      return (
        <div className="expr-not-wrapper" key={tempId()}>
          <div className="expr-not-label">
            <span>NOT</span>
            <button
              className="btn-icon btn-sm"
              title="Remove NOT (un-negate)"
              onClick={() => toggleNot(path)}
            >
              ✕
            </button>
          </div>
          <div className="expr-not-content">
            {renderNode(node.not, path, depth)}
          </div>
        </div>
      );
    }

    // AND/OR group
    const children = getChildren(node);
    const groupOp = op.toUpperCase();
    const depthClass = `expr-group-depth-${depth % 4}`;

    return (
      <div className={`expr-group ${depthClass}`} key={tempId()}>
        {/* Group header with toggle */}
        <div className="expr-group-header">
          <button
            className="expr-group-toggle"
            onClick={() => toggleOperator(path)}
            title={`Click to switch to ${op === 'and' ? 'OR' : 'AND'}`}
          >
            {groupOp}
          </button>

          {path.length > 0 && (
            <div className="expr-node-actions">
              <button
                className="btn-not"
                title="Wrap this group in NOT (negate entire group)"
                onClick={() => toggleNot(path)}
              >
                NOT
              </button>
              <button
                className="btn-icon btn-sm"
                title="Remove group"
                onClick={() => removeNode(path)}
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* Children */}
        <div className="expr-group-children">
          {children.length === 0 && (
            <div className="expr-empty">
              <em>Empty group — add rules or sub-groups below</em>
            </div>
          )}

          {children.map((child, i) => (
            <div key={i} className="expr-child-row">
              {/* Separator between items */}
              {i > 0 && (
                <div className="expr-separator">
                  <span className="expr-separator-label">{groupOp}</span>
                </div>
              )}
              {renderNode(child, [...path, i], depth + 1)}
            </div>
          ))}
        </div>

        {/* Add buttons at bottom of group */}
        <div className="expr-group-footer">
          <AddRuleDropdown
            rules={rules}
            existingIds={children.filter((c) => typeof c === 'string')}
            onSelect={(ruleId) => addRule(path, ruleId)}
          />
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => addGroup(path, 'and')}
          >
            + AND Group
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => addGroup(path, 'or')}
          >
            + OR Group
          </button>
        </div>
      </div>
    );
  }


  // ── Main Render ──────────────────────────────────────────────

  // If no expression yet, start with an empty AND group
  if (!expression || Object.keys(expression).length === 0) {
    return (
      <div className="expression-builder">
        <div className="expr-empty-state">
          <p>No expression defined yet.</p>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onChange({ and: [] })}
          >
            Start with AND group
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => onChange({ or: [] })}
          >
            Start with OR group
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="expression-builder">
      {renderNode(expression, [], 0)}
    </div>
  );
}


// ---------------------------------------------------------------------------
// AddRuleDropdown — Mini dropdown for selecting a rule to add
// ---------------------------------------------------------------------------

function AddRuleDropdown({ rules, existingIds = [], onSelect }) {
  const [open, setOpen] = React.useState(false);

  // Filter to only active rules not already in this group
  const available = rules.filter(
    (r) => r.status === 'active' && !existingIds.includes(r.id)
  );

  if (!open) {
    return (
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => setOpen(true)}
      >
        + Add Rule
      </button>
    );
  }

  return (
    <div className="add-rule-dropdown">
      <select
        className="form-select"
        autoFocus
        defaultValue=""
        onChange={(e) => {
          if (e.target.value) {
            onSelect(e.target.value);
            setOpen(false);
          }
        }}
        onBlur={() => setOpen(false)}
      >
        <option value="">Select a rule…</option>
        {available.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name} ({r.field} {r.operator})
          </option>
        ))}
        {available.length === 0 && (
          <option disabled>No available rules</option>
        )}
      </select>
    </div>
  );
}
