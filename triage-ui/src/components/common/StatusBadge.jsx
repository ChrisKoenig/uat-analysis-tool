/**
 * StatusBadge — Entity Status Indicator
 * =======================================
 *
 * Small colored pill that shows an entity's status:
 *   - Active  → green
 *   - Disabled → grey
 *   - Staged  → amber/orange
 *
 * Usage:
 *   <StatusBadge status="active" />
 *   <StatusBadge status="staged" />
 */

import React from 'react';
import './StatusBadge.css';


const STATUS_STYLES = {
  active:   { className: 'status-active',   label: 'Active' },
  disabled: { className: 'status-disabled', label: 'Disabled' },
  staged:   { className: 'status-staged',   label: 'Staged' },
  deleted:  { className: 'status-deleted',  label: 'Deleted' },
};


export default function StatusBadge({ status }) {
  const config = STATUS_STYLES[status] || STATUS_STYLES.disabled;

  return (
    <span className={`status-badge ${config.className}`}>
      {config.label}
    </span>
  );
}
