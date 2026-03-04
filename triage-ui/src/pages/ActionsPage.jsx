/**
 * ActionsPage — Actions Management
 * ==================================
 *
 * Full CRUD interface for triage actions. An action is an atomic
 * field modification: it sets, copies, appends, or templates a
 * value into a specific ADO field.
 *
 * Same blade layout pattern as RulesPage: list + detail panel.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import Pagination from '../components/common/Pagination';
import ExpandableValue from '../components/common/ExpandableValue';
import StatusFilter from '../components/common/StatusFilter';
import TeamFilter from '../components/common/TeamFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import ActionForm from '../components/actions/ActionForm';
import { truncate } from '../utils/helpers';
import { OPERATIONS } from '../utils/constants';
import '../components/common/EntitySearch.css';
import './ActionsPage.css';


export default function ActionsPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [teamFilter, setTeamFilter] = useState(null);
  const [teams, setTeams] = useState([]);
  const [selectedAction, setSelectedAction] = useState(null);
  const [formMode, setFormMode] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
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

  const loadActions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listActions(statusFilter, teamFilter);
      setActions(data.items || []);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, teamFilter, addToast]);

  useEffect(() => {
    loadActions();
  }, [loadActions]);

  // Reset to page 1 when filters or search change
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, teamFilter, searchTerm]);

  // Search filter (name, field, operation, value — case-insensitive)
  const filteredActions = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((a) => {
      const name = (a.name || '').toLowerCase();
      const field = (a.field || '').toLowerCase();
      const op = OPERATIONS.find((o) => o.value === a.operation);
      const opLabel = op ? op.label.toLowerCase() : (a.operation || '').toLowerCase();
      const value = (a.value ?? '').toString().toLowerCase();
      return name.includes(q) || field.includes(q) || opLabel.includes(q) || value.includes(q);
    });
  }, [actions, searchTerm]);

  // Paginate filtered results
  const paginatedActions = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredActions.slice(start, start + pageSize);
  }, [filteredActions, currentPage, pageSize]);


  // ── Handlers ─────────────────────────────────────────────────

  const handleCreate = () => {
    setSelectedAction(null);
    setReferences(null);
    setFormMode('create');
  };

  const handleEdit = (action) => {
    setSelectedAction(action);
    setFormMode('edit');
    api.getActionReferences(action.id)
      .then(setReferences)
      .catch(() => setReferences(null));
  };

  const handleCopy = async (action) => {
    try {
      await api.copyAction(action.id);
      addToast?.(`Copied "${action.name}"`, 'success');
      loadActions();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  const handleDeleteClick = (action) => setDeleteTarget(action);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteAction(deleteTarget.id, { version: deleteTarget.version });
      addToast?.(`Deleted "${deleteTarget.name}"`, 'success');
      setDeleteTarget(null);
      if (selectedAction?.id === deleteTarget.id) {
        setSelectedAction(null);
        setFormMode(null);
      }
      loadActions();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this action was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setDeleteTarget(null);
    }
  };

  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createAction(data);
        addToast?.('Action created', 'success');
      } else {
        await api.updateAction(selectedAction.id, {
          ...data,
          version: selectedAction.version,
        });
        addToast?.('Action updated', 'success');
      }
      setFormMode(null);
      setSelectedAction(null);
      loadActions();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this action was modified by another user. Reload the page and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedAction(null);
    setReferences(null);
  };


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    { key: 'name', label: 'Name', width: '25%' },
    {
      key: 'field',
      label: 'Target Field',
      width: '25%',
      render: (val) => <code className="field-ref">{val}</code>,
    },
    {
      key: 'operation',
      label: 'Operation',
      width: '15%',
      render: (val) => {
        const op = OPERATIONS.find((o) => o.value === val);
        return op ? op.label : val;
      },
    },
    {
      key: 'value',
      label: 'Value',
      width: '20%',
      render: (val) => {
        if (val === null || val === undefined) return <span className="text-muted">—</span>;
        return <ExpandableValue value={val} maxVisible={3} />;
      },
    },
    { key: 'status', label: 'Status', width: '10%' },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="actions-page">
      <div className="page-header">
        <h1>🎯 Actions</h1>
        <div className="page-header-actions">
          <div className="entity-search">
            <input
              type="text"
              className="entity-search-input"
              placeholder="Search actions by name, field, or value…"
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
            + New Action
          </button>
        </div>
      </div>

      <div className="actions-layout">
        {/* List */}
        <div className={`actions-list ${formMode ? 'actions-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={paginatedActions}
              loading={loading}
              emptyMessage="No actions found. Create your first action to define field modifications."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onDelete={handleDeleteClick}
            />
            <Pagination
              currentPage={currentPage}
              totalItems={filteredActions.length}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
          </div>
          <div className="actions-count">
            {filteredActions.length} action{filteredActions.length !== 1 ? 's' : ''}
            {searchTerm && ` matching "${searchTerm}"`}
            {statusFilter && ` (${statusFilter})`}
          </div>
        </div>

        {/* Detail Panel */}
        {formMode && (
          <div className="actions-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Action' : `Edit: ${selectedAction?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">✕</button>
            </div>
            <div className="card-body">
              <ActionForm
                action={formMode === 'edit' ? selectedAction : null}
                teams={teams}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Cross-references */}
              {formMode === 'edit' && references && (
                <div className="panel-section">
                  <h3>Used In</h3>
                  {Object.keys(references.references || {}).length === 0 ? (
                    <p className="text-muted">Not referenced by any routes.</p>
                  ) : (
                    <ul className="reference-list">
                      {Object.entries(references.references).map(([type, ids]) =>
                        ids.map((id) => (
                          <li key={`${type}-${id}`}>{type}: {references.referenceNames?.[id] || id}</li>
                        ))
                      )}
                    </ul>
                  )}
                </div>
              )}

              {formMode === 'edit' && selectedAction && (
                <ViewCodeToggle data={selectedAction} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Action"
        message={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmLabel="Delete Action"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
