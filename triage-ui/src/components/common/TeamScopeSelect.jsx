/**
 * TeamScopeSelect — Shared team scope dropdown for entity forms
 * ===============================================================
 *
 * Renders a dropdown that lets users assign an entity (rule, action,
 * trigger, route) to a specific triage team or make it available
 * to all teams.
 *
 * Props:
 *   value    — current triageTeamId (null/'' = all teams, or a team ID)
 *   onChange — callback(newValue)  — passes '' for "All Teams", or team ID
 *   teams    — array of team objects [{ id, name }]
 */

import React from 'react';

export default function TeamScopeSelect({ value, onChange, teams = [] }) {
  return (
    <div className="form-group">
      <label>Triage Team Scope</label>
      <select
        className="form-control"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All Teams (shared)</option>
        {teams.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      <small className="form-hint">
        Assign to a specific team, or leave as "All Teams" to make this available everywhere.
      </small>
    </div>
  );
}
