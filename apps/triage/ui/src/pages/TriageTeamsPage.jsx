/**
 * TriageTeamsPage — Triage Team Configuration
 * ==============================================
 *
 * Full CRUD interface for triage teams. Each team has its own
 * ADO saved query that drives its triage queue.
 *
 * Features:
 *   - List all triage teams with status filter
 *   - Create new teams
 *   - Edit existing teams (with optimistic locking)
 *   - Copy/clone teams
 *   - Toggle active/disabled
 *   - View Code toggle for raw JSON
 *
 * Follows the blade pattern: list on the left, detail/form panel
 * slides in from the right when an item is selected.
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import EntityTable from '../components/common/EntityTable';
import StatusFilter from '../components/common/StatusFilter';
import ConfirmDialog from '../components/common/ConfirmDialog';
import ViewCodeToggle from '../components/common/ViewCodeToggle';
import TriageTeamForm from '../components/teams/TriageTeamForm';
import { truncate } from '../utils/helpers';
import './TriageTeamsPage.css';


export default function TriageTeamsPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [formMode, setFormMode] = useState(null); // 'create' | 'edit' | null
  const [toggleTarget, setToggleTarget] = useState(null);


  // ── Data Loading ─────────────────────────────────────────────

  const loadTeams = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listTriageTeams(statusFilter);
      // Sort by displayOrder, then name
      const sorted = (data.items || []).sort(
        (a, b) => (a.displayOrder ?? 100) - (b.displayOrder ?? 100) || (a.name || '').localeCompare(b.name || '')
      );
      setTeams(sorted);
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, addToast]);

  useEffect(() => {
    loadTeams();
  }, [loadTeams]);


  // ── Handlers ─────────────────────────────────────────────────

  const handleCreate = () => {
    setSelectedTeam(null);
    setFormMode('create');
  };

  const handleEdit = (team) => {
    setSelectedTeam(team);
    setFormMode('edit');
  };

  const handleCopy = async (team) => {
    try {
      await api.copyTriageTeam(team.id);
      addToast?.(`Copied "${team.name}"`, 'success');
      loadTeams();
    } catch (err) {
      addToast?.(err.message, 'error');
    }
  };

  const handleToggleStatusClick = (team) => {
    setToggleTarget(team);
  };

  const handleToggleStatusConfirm = async () => {
    if (!toggleTarget) return;
    const newStatus = toggleTarget.status === 'disabled' ? 'active' : 'disabled';
    const action = newStatus === 'disabled' ? 'Disabled' : 'Enabled';
    try {
      await api.updateTriageTeamStatus(toggleTarget.id, newStatus, toggleTarget.version);
      addToast?.(`${action} "${toggleTarget.name}"`, 'success');
      setToggleTarget(null);
      loadTeams();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this team was modified by another user. Please reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
      setToggleTarget(null);
    }
  };

  const handleFormSubmit = async (data) => {
    try {
      if (formMode === 'create') {
        await api.createTriageTeam(data);
        addToast?.('Triage team created', 'success');
      } else {
        await api.updateTriageTeam(selectedTeam.id, { ...data, version: selectedTeam.version });
        addToast?.('Triage team updated', 'success');
      }
      setFormMode(null);
      setSelectedTeam(null);
      loadTeams();
    } catch (err) {
      if (err.status === 409) {
        addToast?.('Conflict: this team was modified by another user. Reload and try again.', 'error');
      } else {
        addToast?.(err.message, 'error');
      }
    }
  };

  const handleClosePanel = () => {
    setFormMode(null);
    setSelectedTeam(null);
  };


  // ── Table Columns ────────────────────────────────────────────

  const columns = [
    { key: 'name', label: 'Team Name', width: '25%' },
    {
      key: 'adoQueryName',
      label: 'ADO Query',
      width: '25%',
      render: (val) => val || <span className="text-muted">—</span>,
    },
    {
      key: 'displayOrder',
      label: 'Order',
      width: '10%',
    },
    {
      key: 'description',
      label: 'Description',
      width: '25%',
      render: (val) => val ? truncate(val, 50) : <span className="text-muted">—</span>,
    },
    { key: 'status', label: 'Status', width: '10%' },
  ];


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="teams-page">
      {/* Page Header */}
      <div className="page-header">
        <h1>👥 Triage Teams</h1>
        <div className="page-header-actions">
          <StatusFilter value={statusFilter} onChange={setStatusFilter} />
          <button className="btn btn-primary" onClick={handleCreate}>
            + New Team
          </button>
        </div>
      </div>

      <div className="teams-layout">
        {/* Left: Teams Table */}
        <div className={`teams-list ${formMode ? 'teams-list-narrow' : ''}`}>
          <div className="card">
            <EntityTable
              columns={columns}
              items={teams}
              loading={loading}
              emptyMessage="No triage teams configured. Create your first team to get started."
              onRowClick={handleEdit}
              onEdit={handleEdit}
              onCopy={handleCopy}
              onToggleStatus={handleToggleStatusClick}
            />
          </div>

          <div className="teams-count">
            {teams.length} team{teams.length !== 1 ? 's' : ''}
            {statusFilter && ` (filtered: ${statusFilter})`}
          </div>
        </div>

        {/* Right: Detail / Form Panel */}
        {formMode && (
          <div className="teams-detail-panel card">
            <div className="card-header">
              <h2>{formMode === 'create' ? 'New Triage Team' : `Edit: ${selectedTeam?.name}`}</h2>
              <button className="btn-icon" onClick={handleClosePanel} title="Close">
                ✕
              </button>
            </div>
            <div className="card-body">
              <TriageTeamForm
                team={formMode === 'edit' ? selectedTeam : null}
                onSubmit={handleFormSubmit}
                onCancel={handleClosePanel}
              />

              {/* View Code toggle (edit mode only) */}
              {formMode === 'edit' && selectedTeam && (
                <ViewCodeToggle data={selectedTeam} label="View JSON" />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Toggle Status Confirmation Dialog */}
      <ConfirmDialog
        open={!!toggleTarget}
        title={toggleTarget?.status === 'disabled' ? 'Enable Team' : 'Disable Team'}
        message={
          toggleTarget?.status === 'disabled'
            ? `Enable "${toggleTarget?.name}"? It will appear in team dropdowns.`
            : `Disable "${toggleTarget?.name}"? It will be hidden from team dropdowns.`
        }
        confirmLabel={toggleTarget?.status === 'disabled' ? 'Enable Team' : 'Disable Team'}
        danger={toggleTarget?.status !== 'disabled'}
        onConfirm={handleToggleStatusConfirm}
        onCancel={() => setToggleTarget(null)}
      />
    </div>
  );
}
