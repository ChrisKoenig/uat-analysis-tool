/**
 * RouteDesigner — Visual Action Composer
 * ========================================
 *
 * Interactive component for composing a route's action list.
 * A route is an ordered sequence of action IDs. The designer
 * allows users to:
 *
 *   - Browse available actions
 *   - Add actions to the route
 *   - Reorder actions (move up/down)
 *   - Remove actions from the route
 *   - Preview what each action does
 *
 * The design uses two panels:
 *   Left:  "Available Actions" — all actions not yet in the route
 *   Right: "Route Actions" — the ordered list of actions in the route
 *
 * Props:
 *   actionIds : Array<string> — current ordered action IDs
 *   onChange  : (newActionIds: string[]) => void
 *   actions   : Array — full action objects [{ id, name, field, operation, ... }]
 */

import React from 'react';
import './RouteDesigner.css';


export default function RouteDesigner({ actionIds = [], onChange, actions = [] }) {
  // Map action IDs to full objects for display
  const actionMap = new Map(actions.map((a) => [a.id, a]));

  // Actions currently in the route (ordered)
  const routeActions = actionIds
    .map((id) => actionMap.get(id))
    .filter(Boolean);

  // Actions available to add (not already in route, active only)
  const available = actions.filter(
    (a) => a.status === 'active' && !actionIds.includes(a.id)
  );

  /** Add an action to the route */
  const addAction = (actionId) => {
    onChange([...actionIds, actionId]);
  };

  /** Remove an action from the route by index */
  const removeAction = (index) => {
    const newIds = [...actionIds];
    newIds.splice(index, 1);
    onChange(newIds);
  };

  /** Move an action up in the order */
  const moveUp = (index) => {
    if (index === 0) return;
    const newIds = [...actionIds];
    [newIds[index - 1], newIds[index]] = [newIds[index], newIds[index - 1]];
    onChange(newIds);
  };

  /** Move an action down in the order */
  const moveDown = (index) => {
    if (index >= actionIds.length - 1) return;
    const newIds = [...actionIds];
    [newIds[index], newIds[index + 1]] = [newIds[index + 1], newIds[index]];
    onChange(newIds);
  };


  return (
    <div className="route-designer">
      {/* Left panel: Available actions */}
      <div className="route-designer-available">
        <h4 className="route-designer-title">Available Actions</h4>
        {available.length === 0 ? (
          <p className="route-designer-empty">
            All actions are already in this route.
          </p>
        ) : (
          <ul className="route-designer-list">
            {available.map((action) => (
              <li key={action.id} className="route-designer-available-item">
                <div className="route-designer-item-info">
                  <span className="route-designer-item-name">{action.name}</span>
                  <span className="route-designer-item-detail">
                    {action.operation}: {action.field}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => addAction(action.id)}
                  title="Add to route"
                >
                  + Add
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Arrow separator */}
      <div className="route-designer-arrow">
        →
      </div>

      {/* Right panel: Route actions (ordered) */}
      <div className="route-designer-selected">
        <h4 className="route-designer-title">
          Route Actions ({routeActions.length})
        </h4>
        {routeActions.length === 0 ? (
          <p className="route-designer-empty">
            No actions yet. Add actions from the left panel.
          </p>
        ) : (
          <ol className="route-designer-list route-designer-ordered">
            {routeActions.map((action, index) => (
              <li key={action.id} className="route-designer-selected-item">
                <span className="route-designer-step">{index + 1}</span>
                <div className="route-designer-item-info">
                  <span className="route-designer-item-name">{action.name}</span>
                  <span
                    className="route-designer-item-detail"
                    title={`${action.operation}: ${action.field}${action.value ? ` → ${action.value}` : ''}`}
                  >
                    {action.operation}: {action.field}
                    {action.value ? ` → ${action.value}` : ''}
                  </span>
                </div>
                <div className="route-designer-item-actions">
                  <button
                    type="button"
                    className="btn-icon btn-sm"
                    title="Move up"
                    onClick={() => moveUp(index)}
                    disabled={index === 0}
                  >
                    ▲
                  </button>
                  <button
                    type="button"
                    className="btn-icon btn-sm"
                    title="Move down"
                    onClick={() => moveDown(index)}
                    disabled={index === routeActions.length - 1}
                  >
                    ▼
                  </button>
                  <button
                    type="button"
                    className="btn-icon btn-sm"
                    title="Remove"
                    onClick={() => removeAction(index)}
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
