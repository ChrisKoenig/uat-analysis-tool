/**
 * RoutesPage — Routes Management
 * ================================
 *
 * CRUD interface for triage routes. A route is an ordered list
 * of actions that execute when a trigger matches.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import StatusFilter from '../components/common/StatusFilter';
import TeamFilter from '../components/common/TeamFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import RouteForm from '../components/routes/RouteForm';
import './RoutesPage.css';


export default function RoutesPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [routes, setRoutes] = useState([]);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [teamFilter, setTeamFilter] = useState(null);
  const [teams, setTeams] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [formMode, setFormMode] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [references, setReferences] = useState(null);


  // ── Data Loading ─────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [routesData, actionsData, teamsData] = await Promise.all([
        api.listRoutes(statusFilter, teamFilter),
        api.listActions(),
        api.listTriageTeams('active'),
      ]);
      setRoutes(routesData.items || []);
      setActions(actionsData.items || []);
      const sortedTeams = (teamsData.items || []).sort(
        (a, b) => (a.displayOrder ?? 100) - (b.displayOrder ?? 100)
      );
      setTeams(sortedTeams);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, teamFilter, addToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);


  // ── Name Lookups ─────────────────────────────────────────────

  const actionNameMap = new Map(actions.map((a) => [a.id, a.name]));


  // ── Handlers ─────────────────────────────────────────────────

  const handleCreate = () => {
    setSelectedRoute(null);
    setReferences(null);
    setFormMode('create');
  };

  const handleEdit = (route) => {
    setSelectedRoute(route);
    setFormMode('edit');
    api.getRouteReferences(route.id)
      .then(setReferences)
      .catch(() => setReferences(null));
  };

  const handleCopy = async (route) => {
    try {
      await api.copyRoute(route.id);
      addToast?.(`Copied "${route.name}"`, 'success');
      loadData();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  const handleDeleteClick = (route) => setDeleteTarget(route);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteRoute(deleteTarget.id, { version: deleteTarget.version });
      addToast?.(`Deleted "${deleteTarget.name}"`, 'success');
      setDeleteTarget(null);
      if (selectedRoute?.id === deleteTarget.id) {
        setSelectedRoute(null);
        setFormMode(null);
      }
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this route was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setDeleteTarget(null);
    }
  };

  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createRoute(data);
        addToast?.('Route created', 'success');
      } else {
        await api.updateRoute(selectedRoute.id, {
          ...data,
          version: selectedRoute.version,
        });
        addToast?.('Route updated', 'success');
      }
      setFormMode(null);
      setSelectedRoute(null);
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this route was modified by another user. Reload the page and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedRoute(null);
    setReferences(null);
  };


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    { key: 'name', label: 'Name', width: '30%' },
    {
      key: 'actions',
      label: 'Actions',
      width: '40%',
      render: (val) => {
        if (!val || val.length === 0) return <span className="text-muted">No actions</span>;
        return val
          .map((id) => actionNameMap.get(id) || id)
          .join(' → ');
      },
    },
    {
      key: 'actions',
      label: 'Count',
      width: '10%',
      render: (val) => val?.length || 0,
    },
    { key: 'status', label: 'Status', width: '10%' },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="routes-page">
      <div className="page-header">
        <h1>🔀 Routes</h1>
        <div className="page-header-actions">
          <TeamFilter value={teamFilter} onChange={setTeamFilter} teams={teams} />
          <StatusFilter value={statusFilter} onChange={setStatusFilter} />
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Route
          </button>
        </div>
      </div>

      <div className="routes-layout">
        {/* List */}
        <div className={`routes-list ${formMode ? 'routes-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={routes}
              loading={loading}
              emptyMessage="No routes found. Create a route to define action sequences."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onDelete={handleDeleteClick}
            />
          </div>
          <div className="routes-count">
            {routes.length} route{routes.length !== 1 ? 's' : ''}
            {statusFilter && ` (filtered: ${statusFilter})`}
          </div>
        </div>

        {/* Detail Panel */}
        {formMode && (
          <div className="routes-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Route' : `Edit: ${selectedRoute?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">✕</button>
            </div>
            <div className="card-body">
              <RouteForm
                route={formMode === 'edit' ? selectedRoute : null}
                actions={actions}
                teams={teams}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* Cross-references */}
              {formMode === 'edit' && references && (
                <div className="panel-section">
                  <h3>Used In</h3>
                  {Object.keys(references.references || {}).length === 0 ? (
                    <p className="text-muted">Not referenced by any triggers.</p>
                  ) : (
                    <ul className="reference-list">
                      {Object.entries(references.references).map(([type, ids]) =>
                        ids.map((id) => (
                          <li key={`${type}-${id}`}>{type}: {id}</li>
                        ))
                      )}
                    </ul>
                  )}
                </div>
              )}

              {formMode === 'edit' && selectedRoute && (
                <ViewCodeToggle data={selectedRoute} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Route"
        message={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmLabel="Delete Route"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
