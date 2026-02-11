/**
 * StatusFilter — Dropdown Filter for Entity Status
 * ==================================================
 *
 * Small filter dropdown used in list page headers to filter
 * entities by status (All / Active / Disabled / Staged).
 *
 * Props:
 *   value    : string | null — current filter value
 *   onChange : (value: string | null) => void
 */

import React from 'react';
import { STATUSES } from '../../utils/constants';


export default function StatusFilter({ value, onChange }) {
  return (
    <select
      className="form-select"
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      aria-label="Filter by status"
      style={{ minWidth: '120px' }}
    >
      <option value="">All Statuses</option>
      {STATUSES.map((s) => (
        <option key={s.value} value={s.value}>
          {s.label}
        </option>
      ))}
    </select>
  );
}
