/**
 * TeamFilter — Shared team filter dropdown for CRUD pages
 * =========================================================
 *
 * Renders a dropdown that lets users filter entities by triage team.
 * Options:
 *   - "All" (default) → show everything
 *   - "Shared (All Teams)" → only items with no team scope
 *   - Each active team → items scoped to that team + shared items
 *
 * Props:
 *   value    — current filter value (null | 'all' | teamId)
 *   onChange — callback(newValue)
 *   teams    — array of team objects [{ id, name }]
 */

import React from 'react';

export default function TeamFilter({ value, onChange, teams = [] }) {
  return (
    <select
      className="team-filter"
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      title="Filter by triage team"
    >
      <option value="">All Teams</option>
      <option value="all">Shared Only (no team)</option>
      {teams.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}
