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
 *   - View cross-references (which triggers use this rule)
 *   - View Code toggle for raw JSON
 *
 * Follows the blade pattern: list on the left, detail/form panel
 * slides in from the right when an item is selected.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import Pagination from '../components/common/Pagination';
import ExpandableValue from '../components/common/ExpandableValue';
import StatusFilter from '../components/common/StatusFilter';
import StatusBadge from '../components/common/StatusBadge';
import TeamFilter from '../components/common/TeamFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import RuleForm from '../components/rules/RuleForm';
import { formatDateTime, truncate } from '../utils/helpers';
import { OPERATORS } from '../utils/constants';
import '../components/common/EntitySearch.css';
import './RulesPage.css';


export default function RulesPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [teamFilter, setTeamFilter] = useState(null);
  const [teams, setTeams] = useState([]);
  const [selectedRule, setSelectedRule] = useState(null);
  const [formMode, setFormMode] = useState(null); // 'create' | 'edit' | null
  const [toggleTarget, setToggleTarget] = useState(null);
  const [references, setReferences] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState('');


  // ── Data Loading ─────────────────────────────────────────────

  // Load active teams for filter + scope dropdowns
  useEffect(() => {
    api.listTriageTeams('active').then((d) => {
      const sorted = (d.items || []).sort(
        (a, b) => (a.displayOrder ?? 100) - (b.displayOrder ?? 100)
      );
      setTeams(sorted);
    }).catch(() => {});
  }, []);

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listRules(statusFilter, teamFilter);
      setRules(data.items || []);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, teamFilter, addToast]);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  // Reset to page 1 when filters or search change
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, teamFilter, searchTerm]);

  // Search filter (name, field, fields, value — case-insensitive)
  const filteredRules = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return rules;
    return rules.filter((r) => {
      const name = (r.name || '').toLowerCase();
      const field = (r.field || '').toLowerCase();
      const fields = (r.fields || []).join(' ').toLowerCase();
      const value = Array.isArray(r.value)
        ? r.value.join(' ').toLowerCase()
        : (r.value ?? '').toString().toLowerCase();
      return name.includes(q) || field.includes(q) || fields.includes(q) || value.includes(q);
    });
  }, [rules, searchTerm]);

  // Paginate filtered results
  const paginatedRules = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredRules.slice(start, start + pageSize);
  }, [filteredRules, currentPage, pageSize]);


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

  /** Initiate status toggle (shows confirmation dialog) */
  const handleToggleStatusClick = (rule) => {
    setToggleTarget(rule);
  };

  /** Confirm status toggle (disable or enable) */
  const handleToggleStatusConfirm = async () => {
    if (!toggleTarget) return;
    const newStatus = toggleTarget.status === 'disabled' ? 'active' : 'disabled';
    const action = newStatus === 'disabled' ? 'Disabled' : 'Enabled';
    try {
      await api.updateRuleStatus(toggleTarget.id, newStatus, toggleTarget.version);
      addToast?.(`${action} "${toggleTarget.name}"`, 'success');
      setToggleTarget(null);
      loadRules();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this rule was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setToggleTarget(null);
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
    { key: 'name', label: 'Name', width: '20%' },
    {
      key: 'field',
      label: 'Field',
      width: '20%',
      render: (val, row) => {
        // Multi-field rules (containsAny) show fields array as chips
        if (Array.isArray(row.fields) && row.fields.length > 0) {
          if (row.fields.length <= 2) {
            return row.fields.map((f) => (
              <code key={f} className="field-ref" style={{ marginRight: 4 }}>{f}</code>
            ));
          }
          return (
            <span title={row.fields.join(', ')}>
              <code className="field-ref">{row.fields[0]}</code>{' '}
              <span className="text-muted">+{row.fields.length - 1} more</span>
            </span>
          );
        }
        return <code className="field-ref">{val}</code>;
      },
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
      width: '25%',
      render: (val) => {
        if (val === null || val === undefined) return <span className="text-muted">—</span>;
        return <ExpandableValue value={val} maxVisible={3} />;
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
          <div className="entity-search">
            <input
              type="text"
              className="entity-search-input"
              placeholder="Search rules by name, field, or value…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button
                className="entity-search-clear"
                onClick={() => setSearchTerm('')}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
          <TeamFilter value={teamFilter} onChange={setTeamFilter} teams={teams} />
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
              items={paginatedRules}
              loading={loading}
              emptyMessage="No rules found. Create your first rule to get started."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onToggleStatus={handleToggleStatusClick}
            />
            <Pagination
              currentPage={currentPage}
              totalItems={filteredRules.length}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
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
                teams={teams}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Cross-references (edit mode only) */}
              {formMode === 'edit' && references && (
                <div className="panel-section">
                  <h3>Used In</h3>
                  {Object.keys(references.references || {}).length === 0 ? (
                    <p className="text-muted">Not referenced by any triggers.</p>
                  ) : (
                    <ul className="reference-list">
                      {Object.entries(references.references).map(([type, ids]) =>
                        ids.map((id) => (
                          <li key={`${type}-${id}`}>
                            <StatusBadge status="active" /> {type}: {references.referenceNames?.[id] || id}
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

      {/* Toggle Status Confirmation Dialog */}
      <ConfirmDialog
        open={!!toggleTarget}
        title={toggleTarget?.status === 'disabled' ? 'Enable Rule' : 'Disable Rule'}
        message={
          toggleTarget?.status === 'disabled'
            ? `Enable "${toggleTarget?.name}"? It will be included in evaluations again.`
            : `Disable "${toggleTarget?.name}"? It will be excluded from evaluations. You can re-enable it later.`
        }
        confirmLabel={toggleTarget?.status === 'disabled' ? 'Enable Rule' : 'Disable Rule'}
        danger={toggleTarget?.status !== 'disabled'}
        onConfirm={handleToggleStatusConfirm}
        onCancel={() => setToggleTarget(null)}
      />
    </div>
  );
}
