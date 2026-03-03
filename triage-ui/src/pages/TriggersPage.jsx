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

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import Pagination from '../components/common/Pagination';
import StatusFilter from '../components/common/StatusFilter';
import TeamFilter from '../components/common/TeamFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import TriggerForm from '../components/triggers/TriggerForm';
import { expressionToDsl } from '../utils/helpers';
import '../components/common/EntitySearch.css';
import './TriggersPage.css';


export default function TriggersPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [triggers, setTriggers] = useState([]);
  const [rules, setRules] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [teamFilter, setTeamFilter] = useState(null);
  const [teams, setTeams] = useState([]);
  const [selectedTrigger, setSelectedTrigger] = useState(null);
  const [formMode, setFormMode] = useState(null);
  const [toggleTarget, setToggleTarget] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState('');


  // ── Data Loading ─────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [triggersData, rulesData, routesData, teamsData] = await Promise.all([
        api.listTriggers(statusFilter, teamFilter),
        api.listRules(),      // All rules for expression builder
        api.listRoutes(),     // All routes for onTrue selector
        api.listTriageTeams('active'),
      ]);
      // Sort triggers by priority
      const sorted = (triggersData.items || []).sort(
        (a, b) => (a.priority ?? 9999) - (b.priority ?? 9999)
      );
      setTriggers(sorted);
      setRules(rulesData.items || []);
      setRoutes(routesData.items || []);
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
  const ruleNameMap = useMemo(() => new Map(rules.map((r) => [r.id, r.name])), [rules]);
  const routeNameMap = useMemo(() => new Map(routes.map((r) => [r.id, r.name])), [routes]);

  // Reset to page 1 when filters or search change
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, teamFilter, searchTerm]);

  // Search filter (name, expression DSL, route name — case-insensitive)
  const filteredTriggers = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return triggers;
    return triggers.filter((t) => {
      const name = (t.name || '').toLowerCase();
      const dsl = t.expression ? expressionToDsl(t.expression, ruleNameMap).toLowerCase() : '';
      const route = routeNameMap.get(t.onTrue)?.toLowerCase() || '';
      return name.includes(q) || dsl.includes(q) || route.includes(q);
    });
  }, [triggers, searchTerm, ruleNameMap, routeNameMap]);

  // Paginate filtered results
  const paginatedTriggers = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredTriggers.slice(start, start + pageSize);
  }, [filteredTriggers, currentPage, pageSize]);


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

  const handleToggleStatusClick = (trigger) => setToggleTarget(trigger);

  const handleToggleStatusConfirm = async () => {
    if (!toggleTarget) return;
    const newStatus = toggleTarget.status === 'disabled' ? 'active' : 'disabled';
    const action = newStatus === 'disabled' ? 'Disabled' : 'Enabled';
    try {
      await api.updateTriggerStatus(toggleTarget.id, newStatus, toggleTarget.version);
      addToast?.(`${action} "${toggleTarget.name}"`, 'success');
      setToggleTarget(null);
      loadData();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this trigger was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setToggleTarget(null);
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
          <div className="entity-search">
            <input
              type="text"
              className="entity-search-input"
              placeholder="Search triggers by name, expression, or route…"
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
              items={paginatedTriggers}
              loading={loading}
              emptyMessage="No triggers yet. Create one to start routing triage items."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onToggleStatus={handleToggleStatusClick}
            />
            <Pagination
              currentPage={currentPage}
              totalItems={filteredTriggers.length}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
          </div>
          <div className="triggers-count">
            {filteredTriggers.length} trigger{filteredTriggers.length !== 1 ? 's' : ''}
            {searchTerm && ` matching "${searchTerm}"`}
            {statusFilter && ` (${statusFilter})`}
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
                teams={teams}
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
        open={!!toggleTarget}
        title={toggleTarget?.status === 'disabled' ? 'Enable Trigger' : 'Disable Trigger'}
        message={
          toggleTarget?.status === 'disabled'
            ? `Enable "${toggleTarget?.name}"? It will participate in evaluations again.`
            : `Disable "${toggleTarget?.name}"? It will be skipped during evaluations. You can re-enable it later.`
        }
        confirmLabel={toggleTarget?.status === 'disabled' ? 'Enable Trigger' : 'Disable Trigger'}
        danger={toggleTarget?.status !== 'disabled'}
        onConfirm={handleToggleStatusConfirm}
        onCancel={() => setToggleTarget(null)}
      />
    </div>
  );
}
