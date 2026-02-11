/**
 * EntityTable — Reusable Data Table
 * ===================================
 *
 * Generic table component for displaying lists of entities
 * (rules, actions, triggers, routes) with consistent styling.
 *
 * Features:
 *   - Configurable columns via column definitions
 *   - Row click handler for detail view
 *   - Status badge integration
 *   - Action buttons column (edit, copy, delete)
 *   - Empty state message
 *   - Loading state
 *
 * Props:
 *   columns    : Array of { key, label, render?, width? }
 *   items      : Array of data objects
 *   onRowClick : (item) => void
 *   onEdit     : (item) => void
 *   onCopy     : (item) => void
 *   onDelete   : (item) => void
 *   loading    : boolean
 *   emptyMessage : string
 */

import React from 'react';
import StatusBadge from './StatusBadge';
import './EntityTable.css';


export default function EntityTable({
  columns,
  items = [],
  onRowClick,
  onEdit,
  onCopy,
  onDelete,
  onToggleStatus,
  loading = false,
  emptyMessage = 'No items found.',
}) {
  if (loading) {
    return (
      <div className="entity-table-loading">
        <span className="spinner" /> Loading…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="entity-table-empty">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="entity-table-wrapper">
      <table className="entity-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={col.width ? { width: col.width } : undefined}>
                {col.label}
              </th>
            ))}
            {/* Actions column */}
            {(onEdit || onCopy || onDelete || onToggleStatus) && (
              <th style={{ width: '120px' }}>Actions</th>
            )}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className={onRowClick ? 'entity-table-row-clickable' : ''}
              onClick={() => onRowClick?.(item)}
            >
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render
                    ? col.render(item[col.key], item)
                    : col.key === 'status'
                      ? <StatusBadge status={item[col.key]} />
                      : (item[col.key] ?? '—')}
                </td>
              ))}

              {/* Action buttons — stop propagation to prevent row click */}
              {(onEdit || onCopy || onDelete || onToggleStatus) && (
                <td className="entity-table-actions" onClick={(e) => e.stopPropagation()}>
                  {onEdit && (
                    <button
                      className="btn-icon"
                      title="Edit"
                      onClick={() => onEdit(item)}
                    >
                      ✏️
                    </button>
                  )}
                  {onCopy && (
                    <button
                      className="btn-icon"
                      title="Copy"
                      onClick={() => onCopy(item)}
                    >
                      📋
                    </button>
                  )}
                  {onToggleStatus && (
                    <button
                      className={`btn-icon ${item.status === 'disabled' ? 'btn-icon-enable' : 'btn-icon-disable'}`}
                      title={item.status === 'disabled' ? 'Enable' : 'Disable'}
                      onClick={() => onToggleStatus(item)}
                    >
                      {item.status === 'disabled' ? '▶️' : '⏸️'}
                    </button>
                  )}
                  {onDelete && (
                    <button
                      className="btn-icon"
                      title="Delete"
                      onClick={() => onDelete(item)}
                    >
                      🗑️
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
