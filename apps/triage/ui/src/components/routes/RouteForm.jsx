/**
 * RouteForm — Create / Edit Route Form
 * =======================================
 *
 * Form for creating or editing a route. A route is an ordered
 * list of action IDs that get executed when a trigger matches.
 *
 * Uses the RouteDesigner component for the visual action composer.
 *
 * Props:
 *   route    : object | null — existing route for edit mode
 *   actions  : Array — available actions [{id, name, field, operation, ...}]
 *   onSubmit : (formData) => void
 *   onCancel : () => void
 */

import React, { useState, useEffect } from 'react';
import RouteDesigner from './RouteDesigner';
import TeamScopeSelect from '../common/TeamScopeSelect';


export default function RouteForm({ route, actions = [], teams = [], onSubmit, onCancel }) {
  // ── Form State ───────────────────────────────────────────────
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [actionIds, setActionIds] = useState([]);
  const [triageTeamId, setTriageTeamId] = useState('');
  const [status, setStatus] = useState('active');
  const [submitting, setSubmitting] = useState(false);


  // ── Populate for edit mode ───────────────────────────────────
  useEffect(() => {
    if (route) {
      setName(route.name || '');
      setDescription(route.description || '');
      setActionIds(route.actions || []);
      setTriageTeamId(route.triageTeamId || '');
      setStatus(route.status || 'active');
    } else {
      setName('');
      setDescription('');
      setActionIds([]);
      setTriageTeamId('');
      setStatus('active');
    }
  }, [route]);


  // ── Submit ───────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        actions: actionIds,
        triageTeamId: triageTeamId || null,
        status,
      });
    } finally {
      setSubmitting(false);
    }
  };


  // ── Render ───────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} className="route-form">
      {/* Name */}
      <div className="form-group">
        <label htmlFor="route-name">Name *</label>
        <input
          id="route-name"
          className="form-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., AI Triage Team Route"
          required
        />
      </div>

      {/* Description */}
      <div className="form-group">
        <label htmlFor="route-desc">Description</label>
        <textarea
          id="route-desc"
          className="form-textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this route do?"
          rows={2}
        />
      </div>

      {/* Route Designer: visual action composer */}
      <div className="form-group">
        <label>Actions (ordered)</label>
        <span className="hint">
          Add and order actions for this route. Actions execute left→right, top→bottom.
        </span>
        <RouteDesigner
          actionIds={actionIds}
          onChange={setActionIds}
          actions={actions}
        />
      </div>

      {/* Triage Team Scope */}
      {teams.length > 0 && (
        <TeamScopeSelect value={triageTeamId} onChange={setTriageTeamId} teams={teams} />
      )}

      {/* Status */}
      <div className="form-group">
        <label htmlFor="route-status">Status</label>
        <select
          id="route-status"
          className="form-select"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
          <option value="staged">Staged (test only)</option>
        </select>
      </div>

      {/* Form Actions */}
      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : route ? 'Update Route' : 'Create Route'}
        </button>
      </div>
    </form>
  );
}
