/**
 * ExpandableValue — Truncated value with expand/collapse
 * ========================================================
 *
 * Displays a comma-separated list truncated to `maxVisible` items.
 * A "+N more" badge toggles full list on click.
 * Hover shows full list in a tooltip.
 *
 * Props:
 *   value      : string | string[]   (comma-separated string or array)
 *   maxVisible : number              (items to show before truncating, default 3)
 */

import React, { useState } from 'react';
import './ExpandableValue.css';

export default function ExpandableValue({ value, maxVisible = 3 }) {
  const [expanded, setExpanded] = useState(false);

  if (value === null || value === undefined || value === '') {
    return <span className="text-muted">—</span>;
  }

  // Normalise to an array of items
  const items = Array.isArray(value)
    ? value
    : String(value).split(',').map((s) => s.trim()).filter(Boolean);

  // Short list — no truncation needed
  if (items.length <= maxVisible) {
    return <span className="expandable-value">{items.join(', ')}</span>;
  }

  const visible = expanded ? items : items.slice(0, maxVisible);
  const hiddenCount = items.length - maxVisible;

  return (
    <span className="expandable-value" title={items.join(', ')}>
      <span className="expandable-value-list">
        {visible.join(', ')}
      </span>
      {!expanded && (
        <button
          className="expandable-value-badge"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(true);
          }}
          title={`Show all ${items.length} items`}
        >
          +{hiddenCount} more
        </button>
      )}
      {expanded && (
        <button
          className="expandable-value-badge expandable-value-badge-collapse"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(false);
          }}
          title="Show less"
        >
          show less
        </button>
      )}
    </span>
  );
}
