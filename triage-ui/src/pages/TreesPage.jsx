/**
 * TreesPage — Decision Trees Management
 * ========================================
 *
 * CRUD interface for decision trees. Trees evaluate boolean
 * expressions referencing rules, and when TRUE, execute a route.
 * Trees are evaluated in priority order — first TRUE wins.
 *
 * This page loads rules and routes in addition to trees, because:
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
import TreeForm from '../components/trees/TreeForm';
import { expressionToDsl } from '../utils/helpers';
import './TreesPage.css';


export default function TreesPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [trees, setTrees] = useState([]);
  const [rules, setRules] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selectedTree, setSelectedTree] = useState(null);
  const [formMode, setFormMode] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);


  // ── Data Loading ─────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [treesData, rulesData, routesData] = await Promise.all([
        api.listTrees(statusFilter),
        api.listRules(),      // All rules for expression builder
        api.listRoutes(),     // All routes for onTrue selector
      ]);
      // Sort trees by priority
      const sorted = (treesData.items || []).sort(
        (a, b) => (a.priority ?? 9999) - (b.priority ?? 9999)
      );
      setTrees(sorted);
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
    setSelectedTree(null);
    setFormMode('create');
  };

  const handleEdit = (tree) => {
    setSelectedTree(tree);
    setFormMode('edit');
  };

  const handleCopy = async (tree) => {
    try {
      await api.copyTree(tree.id);
      addToast?.(`Copied "${tree.name}"`, 'success');
      loadData();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  const handleDeleteClick = (tree) => setDeleteTarget(tree);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteTree(deleteTarget.id, { version: deleteTarget.version });
      addToast?.(`Deleted "${deleteTarget.name}"`, 'success');
      setDeleteTarget(null);
      if (selectedTree?.id === deleteTarget.id) {
        setSelectedTree(null);
        setFormMode(null);
      }
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this tree was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setDeleteTarget(null);
    }
  };

  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createTree(data);
        addToast?.('Tree created', 'success');
      } else {
        await api.updateTree(selectedTree.id, { ...data, version: selectedTree.version });
        addToast?.('Tree updated', 'success');
      }
      setFormMode(null);
      setSelectedTree(null);
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this tree was modified by another user. Reload the page and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedTree(null);
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
    <div className="trees-page">
      <div className="page-header">
        <h1>🌳 Decision Trees</h1>
        <div className="page-header-actions">
          <StatusFilter value={statusFilter} onChange={setStatusFilter} />
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Tree
          </button>
        </div>
      </div>

      <div className="trees-layout">
        {/* List */}
        <div className={`trees-list ${formMode ? 'trees-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={trees}
              loading={loading}
              emptyMessage="No decision trees yet. Create one to start routing triage items."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onDelete={handleDeleteClick}
            />
          </div>
          <div className="trees-count">
            {trees.length} tree{trees.length !== 1 ? 's' : ''}
            {statusFilter && ` (filtered: ${statusFilter})`}
          </div>
        </div>

        {/* Detail Panel */}
        {formMode && (
          <div className="trees-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Decision Tree' : `Edit: ${selectedTree?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">✕</button>
            </div>
            <div className="card-body">
              <TreeForm
                tree={formMode === 'edit' ? selectedTree : null}
                rules={rules}
                routes={routes}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Execution Preview: show the DSL view */}
              {formMode === 'edit' && selectedTree?.expression && (
                <div className="panel-section">
                  <h3>Expression Preview (DSL)</h3>
                  <pre className="view-code-block">
                    <code>
                      {expressionToDsl(selectedTree.expression, ruleNameMap)}
                    </code>
                  </pre>
                </div>
              )}

              {formMode === 'edit' && selectedTree && (
                <ViewCodeToggle data={selectedTree} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Decision Tree"
        message={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmLabel="Delete Tree"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
