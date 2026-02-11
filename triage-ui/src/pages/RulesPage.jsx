/**
 * RulesPage — Rules Management
 * ==============================
 *
 * Full CRUD interface for triage rules. Rules are atomic conditions
 * that evaluate a single ADO field against an operator and value.
 *
 * Features:
 *   - List all rules with status filter
 *   - Create new rules
 *   - Edit existing rules (with optimistic locking)
 *   - Copy/clone rules
 *   - Delete rules (with confirmation)
 *   - View cross-references (which trees use this rule)
 *   - View Code toggle for raw JSON
 *
 * Follows the blade pattern: list on the left, detail/form panel
 * slides in from the right when an item is selected.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import StatusFilter from '../components/common/StatusFilter';
import StatusBadge from '../components/common/StatusBadge';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import RuleForm from '../components/rules/RuleForm';
import { formatDateTime, truncate } from '../utils/helpers';
import { OPERATORS } from '../utils/constants';
import './RulesPage.css';


export default function RulesPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const [formMode, setFormMode] = useState(null); // 'create' | 'edit' | null
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [references, setReferences] = useState(null);


  // ── Data Loading ─────────────────────────────────────────────

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listRules(statusFilter);
      setRules(data.items || []);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, addToast]);

  useEffect(() => {
    loadRules();
  }, [loadRules]);


  // ── Handlers ─────────────────────────────────────────────────

  /** Open the create form */
  const handleCreate = () => {
    setSelectedRule(null);
    setReferences(null);
    setFormMode('create');
  };

  /** Select a rule to edit */
  const handleEdit = (rule) => {
    setSelectedRule(rule);
    setFormMode('edit');
    // Load references in background
    api.getRuleReferences(rule.id)
      .then(setReferences)
      .catch(() => setReferences(null));
  };

  /** Clone a rule */
  const handleCopy = async (rule) => {
    try {
      await api.copyRule(rule.id);
      addToast?.(`Copied "${rule.name}"`, 'success');
      loadRules();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  /** Initiate delete (shows confirmation dialog) */
  const handleDeleteClick = (rule) => {
    setDeleteTarget(rule);
  };

  /** Confirm delete */
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteRule(deleteTarget.id, { version: deleteTarget.version });
      addToast?.(`Deleted "${deleteTarget.name}"`, 'success');
      setDeleteTarget(null);
      // Close detail panel if the deleted rule was selected
      if (selectedRule?.id === deleteTarget.id) {
        setSelectedRule(null);
        setFormMode(null);
      }
      loadRules();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this rule was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setDeleteTarget(null);
    }
  };

  /** Form submitted (create or update) */
  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createRule(data);
        addToast?.('Rule created', 'success');
      } else {
        await api.updateRule(selectedRule.id, { ...data, version: selectedRule.version });
        addToast?.('Rule updated', 'success');
      }
      setFormMode(null);
      setSelectedRule(null);
      loadRules();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this rule was modified by another user. Reload the page and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  /** Close the detail/form panel */
  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedRule(null);
    setReferences(null);
  };


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    { key: 'name', label: 'Name', width: '25%' },
    {
      key: 'field',
      label: 'Field',
      width: '25%',
      render: (val) => <code className="field-ref">{val}</code>,
    },
    {
      key: 'operator',
      label: 'Operator',
      width: '15%',
      render: (val) => {
        const op = OPERATORS.find((o) => o.value === val);
        return op ? op.label : val;
      },
    },
    {
      key: 'value',
      label: 'Value',
      width: '15%',
      render: (val) => {
        if (val === null || val === undefined) return <span className="text-muted">—</span>;
        if (Array.isArray(val)) return val.join(', ');
        return truncate(String(val), 40);
      },
    },
    { key: 'status', label: 'Status', width: '10%' },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="rules-page">
      {/* Page Header */}
      <div className="page-header">
        <h1>📋 Rules</h1>
        <div className="page-header-actions">
          <StatusFilter value={statusFilter} onChange={setStatusFilter} />
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Rule
          </button>
        </div>
      </div>

      <div className="rules-layout">
        {/* Left: Rules Table */}
        <div className={`rules-list ${formMode ? 'rules-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={rules}
              loading={loading}
              emptyMessage="No rules found. Create your first rule to get started."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onDelete={handleDeleteClick}
            />
          </div>

          <div className="rules-count">
            {rules.length} rule{rules.length !== 1 ? 's' : ''}
            {statusFilter && ` (filtered: ${statusFilter})`}
          </div>
        </div>

        {/* Right: Detail / Form Panel */}
        {formMode && (
          <div className="rules-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Rule' : `Edit: ${selectedRule?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">
                ✕
              </button>
            </div>
            <div className="card-body">
              <RuleForm
                rule={formMode === 'edit' ? selectedRule : null}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Cross-references (edit mode only) */}
              {formMode === 'edit' && references && (
                <div className="panel-section">
                  <h3>Used In</h3>
                  {Object.keys(references.references || {}).length === 0 ? (
                    <p className="text-muted">Not referenced by any trees.</p>
                  ) : (
                    <ul className="reference-list">
                      {Object.entries(references.references).map(([type, ids]) =>
                        ids.map((id) => (
                          <li key={`${type}-${id}`}>
                            <StatusBadge status="active" /> {type}: {id}
                          </li>
                        ))
                      )}
                    </ul>
                  )}
                </div>
              )}

              {/* View Code toggle (edit mode only) */}
              {formMode === 'edit' && selectedRule && (
                <ViewCodeToggle data={selectedRule} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Rule"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete Rule"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
