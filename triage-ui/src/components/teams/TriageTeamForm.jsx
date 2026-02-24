/**
 * TriageTeamForm — Create / Edit a Triage Team
 * ================================================
 *
 * Form fields:
 *   - name           (required)
 *   - description
 *   - adoQueryId     (required — GUID of the saved ADO query)
 *   - adoQueryName   (display name of the query)
 *   - organization   (blank = default read org)
 *   - project        (blank = default read project)
 *   - displayOrder   (sort position, default 100)
 *   - status         (active / disabled)
 */

import React, { useState, useEffect } from 'react';

const INITIAL = {
  name: '',
  description: '',
  adoQueryId: '',
  adoQueryName: '',
  organization: '',
  project: '',
  displayOrder: 100,
  status: 'active',
};


export default function TriageTeamForm({ team, onSubmit, onCancel }) {
  const [form, setForm] = useState(INITIAL);

  useEffect(() => {
    if (team) {
      setForm({
        name: team.name || '',
        description: team.description || '',
        adoQueryId: team.adoQueryId || '',
        adoQueryName: team.adoQueryName || '',
        organization: team.organization || '',
        project: team.project || '',
        displayOrder: team.displayOrder ?? 100,
        status: team.status || 'active',
      });
    } else {
      setForm(INITIAL);
    }
  }, [team]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...form,
      displayOrder: Number(form.displayOrder) || 100,
    });
  };

  const isValid = form.name.trim() && form.adoQueryId.trim();

  return (
    <form className="entity-form" onSubmit={handleSubmit}>
      {/* Name */}
      <div className="form-group">
        <label className="form-label">
          Team Name <span className="required">*</span>
        </label>
        <input
          type="text"
          className="form-input"
          value={form.name}
          onChange={(e) => handleChange('name', e.target.value)}
          placeholder="e.g., Azure Corp Daily Triage"
          required
        />
      </div>

      {/* Description */}
      <div className="form-group">
        <label className="form-label">Description</label>
        <textarea
          className="form-input"
          rows={2}
          value={form.description}
          onChange={(e) => handleChange('description', e.target.value)}
          placeholder="Purpose of this triage team"
        />
      </div>

      {/* ADO Query ID */}
      <div className="form-group">
        <label className="form-label">
          ADO Saved Query ID <span className="required">*</span>
        </label>
        <input
          type="text"
          className="form-input"
          value={form.adoQueryId}
          onChange={(e) => handleChange('adoQueryId', e.target.value)}
          placeholder="GUID — e.g., b0ad9398-4942-4d8f-829e-604a347d8ac8"
          required
        />
        <span className="form-hint">
          The GUID of the saved query in Azure DevOps that drives this team's queue.
        </span>
      </div>

      {/* ADO Query Name */}
      <div className="form-group">
        <label className="form-label">ADO Query Name</label>
        <input
          type="text"
          className="form-input"
          value={form.adoQueryName}
          onChange={(e) => handleChange('adoQueryName', e.target.value)}
          placeholder="e.g., Azure Corp Daily Triage"
        />
        <span className="form-hint">
          Display name only — helps identify which query this team uses.
        </span>
      </div>

      {/* Organization / Project (optional overrides) */}
      <div className="form-row">
        <div className="form-group form-group-half">
          <label className="form-label">Organization</label>
          <input
            type="text"
            className="form-input"
            value={form.organization}
            onChange={(e) => handleChange('organization', e.target.value)}
            placeholder="(default)"
          />
        </div>
        <div className="form-group form-group-half">
          <label className="form-label">Project</label>
          <input
            type="text"
            className="form-input"
            value={form.project}
            onChange={(e) => handleChange('project', e.target.value)}
            placeholder="(default)"
          />
        </div>
      </div>

      {/* Display Order */}
      <div className="form-group">
        <label className="form-label">Display Order</label>
        <input
          type="number"
          className="form-input"
          value={form.displayOrder}
          onChange={(e) => handleChange('displayOrder', e.target.value)}
          min={0}
          step={1}
          style={{ width: 120 }}
        />
        <span className="form-hint">Lower numbers appear first in dropdowns.</span>
      </div>

      {/* Status */}
      <div className="form-group">
        <label className="form-label">Status</label>
        <select
          className="form-input"
          value={form.status}
          onChange={(e) => handleChange('status', e.target.value)}
        >
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>

      {/* Buttons */}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={!isValid}>
          {team ? 'Save Changes' : 'Create Team'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
