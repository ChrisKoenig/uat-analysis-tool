/**
 * TriggersPage — Triggers Management
 * =====================================
 *
 * CRUD interface for triggers. Triggers evaluate boolean
 * expressions referencing rules, and when TRUE, execute a route.
 * Triggers are evaluated in priority order — first TRUE wins.
 *
 * This page loads rules and routes in addition to triggers, because:
 *   - The expression builder needs the rule list
 *   - The route selector needs the route list
 *   - The table shows resolved names instead of IDs
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import StatusFilter from '../components/common/StatusFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import TriggerForm from '../components/triggers/TriggerForm';
import { expressionToDsl } from '../utils/helpers';
import './TriggersPage.css';


export default function TriggersPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [triggers, setTriggers] = useState([]);
  const [rules, setRules] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selectedTrigger, setSelectedTrigger] = useState(null);
  const [formMode, setFormMode] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);


  // ── Data Loading ─────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [triggersData, rulesData, routesData] = await Promise.all([
        api.listTriggers(statusFilter),
        api.listRules(),      // All rules for expression builder
        api.listRoutes(),     // All routes for onTrue selector
      ]);
      // Sort triggers by priority
      const sorted = (triggersData.items || []).sort(
        (a, b) => (a.priority ?? 9999) - (b.priority ?? 9999)
      );
      setTriggers(sorted);
      setRules(rulesData.items || []);
      setRoutes(routesData.items || []);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, addToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);


  // ── Name Lookups ─────────────────────────────────────────────

  const ruleNameMap = new Map(rules.map((r) => [r.id, r.name]));
  const routeNameMap = new Map(routes.map((r) => [r.id, r.name]));


  // ── Handlers ─────────────────────────────────────────────────

  const handleCreate = () => {
    setSelectedTrigger(null);
    setFormMode('create');
  };

  const handleEdit = (trigger) => {
    setSelectedTrigger(trigger);
    setFormMode('edit');
  };

  const handleCopy = async (trigger) => {
    try {
      await api.copyTrigger(trigger.id);
      addToast?.(`Copied "${trigger.name}"`, 'success');
      loadData();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  const handleDeleteClick = (trigger) => setDeleteTarget(trigger);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteTrigger(deleteTarget.id, { version: deleteTarget.version });
      addToast?.(`Deleted "${deleteTarget.name}"`, 'success');
      setDeleteTarget(null);
      if (selectedTrigger?.id === deleteTarget.id) {
        setSelectedTrigger(null);
        setFormMode(null);
      }
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this trigger was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setDeleteTarget(null);
    }
  };

  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createTrigger(data);
        addToast?.('Trigger created', 'success');
      } else {
        await api.updateTrigger(selectedTrigger.id, { ...data, version: selectedTrigger.version });
        addToast?.('Trigger updated', 'success');
      }
      setFormMode(null);
      setSelectedTrigger(null);
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this trigger was modified by another user. Reload the page and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedTrigger(null);
  };


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    {
      key: 'priority',
      label: '#',
      width: '60px',
      render: (val) => <strong>{val}</strong>,
    },
    { key: 'name', label: 'Name', width: '25%' },
    {
      key: 'expression',
      label: 'Expression',
      width: '30%',
      render: (val) => {
        if (!val) return '—';
        const dsl = expressionToDsl(val, ruleNameMap);
        // Show first line only in table
        const firstLine = dsl.split('\n').slice(0, 2).join(' ');
        return (
          <code className="field-ref" title={dsl}>
            {firstLine.length > 60 ? firstLine.slice(0, 60) + '…' : firstLine}
          </code>
        );
      },
    },
    {
      key: 'onTrue',
      label: 'Route',
      width: '20%',
      render: (val) => routeNameMap.get(val) || val || '—',
    },
    { key: 'status', label: 'Status', width: '10%' },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="triggers-page">
      <div className="page-header">
        <h1>⚡ Triggers</h1>
        <div className="page-header-actions">
          <StatusFilter value={statusFilter} onChange={setStatusFilter} />
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Trigger
          </button>
        </div>
      </div>

      <div className="triggers-layout">
        {/* List */}
        <div className={`triggers-list ${formMode ? 'triggers-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={triggers}
              loading={loading}
              emptyMessage="No triggers yet. Create one to start routing triage items."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onDelete={handleDeleteClick}
            />
          </div>
          <div className="triggers-count">
            {triggers.length} trigger{triggers.length !== 1 ? 's' : ''}
            {statusFilter && ` (filtered: ${statusFilter})`}
          </div>
        </div>

        {/* Detail Panel */}
        {formMode && (
          <div className="triggers-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Trigger' : `Edit: ${selectedTrigger?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">✕</button>
            </div>
            <div className="card-body">
              <TriggerForm
                trigger={formMode === 'edit' ? selectedTrigger : null}
                rules={rules}
                routes={routes}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Execution Preview: show the DSL view */}
              {formMode === 'edit' && selectedTrigger?.expression && (
                <div className="panel-section">
                  <h3>Expression Preview (DSL)</h3>
                  <pre className="view-code-block">
                    <code>
                      {expressionToDsl(selectedTrigger.expression, ruleNameMap)}
                    </code>
                  </pre>
                </div>
              )}

              {formMode === 'edit' && selectedTrigger && (
                <ViewCodeToggle data={selectedTrigger} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Trigger"
        message={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmLabel="Delete Trigger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
