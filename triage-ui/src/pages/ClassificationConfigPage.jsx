/**
 * ClassificationConfigPage — Dynamic Classification Management
 * ==============================================================
 *
 * Manage categories, intents, and business impacts that drive AI
 * classification. Items can be official (seed/admin-approved),
 * AI-discovered (pending review), or rejected.
 *
 * Admins can:
 *  - View all items, filter by type/status
 *  - Accept a discovered item → promotes to "official"
 *  - Redirect a discovered item → maps it to an existing value
 *  - Reject a discovered item → hides it from the classifier
 */

import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import './ClassificationConfigPage.css';


const CONFIG_TYPES = [
  { value: '',                label: 'All Types' },
  { value: 'category',       label: 'Categories' },
  { value: 'intent',         label: 'Intents' },
  { value: 'business_impact', label: 'Business Impacts' },
];

const STATUS_FILTERS = [
  { value: '',           label: 'All Statuses' },
  { value: 'official',   label: 'Official' },
  { value: 'discovered', label: 'Discovered' },
  { value: 'rejected',   label: 'Rejected' },
];

function statusBadge(status) {
  const map = {
    official:   { cls: 'badge-official',   icon: '✅', label: 'Official' },
    discovered: { cls: 'badge-discovered', icon: '🆕', label: 'Discovered' },
    rejected:   { cls: 'badge-rejected',   icon: '🚫', label: 'Rejected' },
  };
  const s = map[status] || { cls: '', icon: '❓', label: status };
  return <span className={`config-badge ${s.cls}`}>{s.icon} {s.label}</span>;
}

function typeBadge(configType) {
  const map = {
    category:        { cls: 'type-category', label: 'Category' },
    intent:          { cls: 'type-intent',   label: 'Intent' },
    business_impact: { cls: 'type-impact',   label: 'Impact' },
  };
  const t = map[configType] || { cls: '', label: configType };
  return <span className={`config-type-badge ${t.cls}`}>{t.label}</span>;
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}


export default function ClassificationConfigPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [selected, setSelected] = useState(null);  // item being edited
  const [saving, setSaving] = useState(false);

  // Edit form state
  const [editStatus, setEditStatus] = useState('');
  const [editRedirect, setEditRedirect] = useState('');
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  // ── Load data ────────────────────────────────────────────────
  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = {};
      if (filterType) filters.configType = filterType;
      if (filterStatus) filters.status = filterStatus;
      const res = await api.listClassificationConfig(filters);
      setItems(res.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load classification config');
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus]);

  useEffect(() => { loadItems(); }, [loadItems]);

  // ── Select an item for editing ───────────────────────────────
  const selectItem = (item) => {
    setSelected(item);
    setEditStatus(item.status);
    setEditRedirect(item.redirectTo || '');
    setEditDisplayName(item.displayName || '');
    setEditDescription(item.description || '');
  };

  // ── Quick actions ────────────────────────────────────────────
  const quickAccept = async (item) => {
    setSaving(true);
    try {
      await api.updateClassificationConfig(item.id, { status: 'official' });
      await loadItems();
      if (selected?.id === item.id) setSelected(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const quickReject = async (item) => {
    setSaving(true);
    try {
      await api.updateClassificationConfig(item.id, { status: 'rejected' });
      await loadItems();
      if (selected?.id === item.id) setSelected(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Save edits ───────────────────────────────────────────────
  const saveEdit = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const updates = {};
      if (editStatus !== selected.status) updates.status = editStatus;
      if (editRedirect !== (selected.redirectTo || '')) updates.redirectTo = editRedirect || null;
      if (editDisplayName !== (selected.displayName || '')) updates.displayName = editDisplayName;
      if (editDescription !== (selected.description || '')) updates.description = editDescription;
      if (Object.keys(updates).length === 0) { setSaving(false); return; }
      await api.updateClassificationConfig(selected.id, updates);
      setSelected(null);
      await loadItems();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Collect official values for the redirect dropdown
  const officialValues = items
    .filter(i => i.status === 'official' && i.configType === selected?.configType)
    .map(i => i.value);

  // Stats
  const discoveredCount = items.filter(i => i.status === 'discovered').length;
  const officialCount   = items.filter(i => i.status === 'official').length;
  const rejectedCount   = items.filter(i => i.status === 'rejected').length;

  return (
    <div className="classification-config-page">
      <header className="page-header">
        <div className="page-header-left">
          <h1>🧠 Classification Config</h1>
          <p className="page-subtitle">
            Manage dynamic categories, intents, and business impacts.
            AI-discovered values appear here for review.
          </p>
        </div>
        <div className="config-stats">
          <span className="stat-chip official">{officialCount} official</span>
          <span className="stat-chip discovered">{discoveredCount} discovered</span>
          <span className="stat-chip rejected">{rejectedCount} rejected</span>
        </div>
      </header>

      {error && (
        <div className="config-error">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Filters */}
      <div className="config-filters">
        <select value={filterType} onChange={e => setFilterType(e.target.value)}>
          {CONFIG_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          {STATUS_FILTERS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <button className="btn btn-sm" onClick={loadItems} disabled={loading}>
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {/* Main layout: list + detail panel */}
      <div className="config-layout">
        {/* List */}
        <div className={`config-list ${selected ? 'config-list-narrow' : ''}`}>
          {loading && items.length === 0 ? (
            <div className="config-skeleton">Loading...</div>
          ) : items.length === 0 ? (
            <div className="config-empty">No items match the current filters.</div>
          ) : (
            <table className="config-table">
              <thead>
                <tr>
                  <th>Value</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Seen</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr
                    key={item.id}
                    className={`config-row ${selected?.id === item.id ? 'config-row-selected' : ''} ${item.status === 'discovered' ? 'config-row-discovered' : ''}`}
                    onClick={() => selectItem(item)}
                  >
                    <td>
                      <span className="config-value">{item.displayName || item.value}</span>
                      {item.redirectTo && (
                        <span className="config-redirect-hint">→ {item.redirectTo}</span>
                      )}
                    </td>
                    <td>{typeBadge(item.configType)}</td>
                    <td>{statusBadge(item.status)}</td>
                    <td><span className={`source-${item.source}`}>{item.source}</span></td>
                    <td>{item.discoveredCount > 0 ? item.discoveredCount : '—'}</td>
                    <td className="config-actions-cell" onClick={e => e.stopPropagation()}>
                      {item.status === 'discovered' && (
                        <>
                          <button
                            className="btn btn-xs btn-success"
                            onClick={() => quickAccept(item)}
                            disabled={saving}
                            title="Accept as official"
                          >✅</button>
                          <button
                            className="btn btn-xs btn-danger"
                            onClick={() => quickReject(item)}
                            disabled={saving}
                            title="Reject"
                          >🚫</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail / Edit panel */}
        {selected && (
          <div className="config-detail-panel card">
            <div className="card-header">
              <h3>Edit: {selected.displayName || selected.value}</h3>
              <button className="btn btn-xs" onClick={() => setSelected(null)}>✕</button>
            </div>
            <div className="card-body">
              <div className="config-detail-meta">
                <div><strong>ID:</strong> {selected.id}</div>
                <div><strong>Type:</strong> {typeBadge(selected.configType)}</div>
                <div><strong>Source:</strong> {selected.source}</div>
                <div><strong>Created:</strong> {formatDate(selected.createdAt)}</div>
                <div><strong>Updated:</strong> {formatDate(selected.updatedAt)}</div>
                {selected.discoveredFrom && (
                  <div><strong>Discovered from:</strong> #{selected.discoveredFrom}</div>
                )}
                {selected.discoveredCount > 0 && (
                  <div><strong>Times seen:</strong> {selected.discoveredCount}</div>
                )}
              </div>

              <hr />

              <div className="config-edit-form">
                <label>
                  Status
                  <select value={editStatus} onChange={e => setEditStatus(e.target.value)}>
                    <option value="official">Official</option>
                    <option value="discovered">Discovered</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </label>

                <label>
                  Redirect To
                  <select value={editRedirect} onChange={e => setEditRedirect(e.target.value)}>
                    <option value="">— none —</option>
                    {officialValues.map(v => (
                      <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                  <span className="help-text">
                    Map this value to an existing official value.
                  </span>
                </label>

                <label>
                  Display Name
                  <input
                    type="text"
                    value={editDisplayName}
                    onChange={e => setEditDisplayName(e.target.value)}
                  />
                </label>

                <label>
                  Description
                  <textarea
                    rows={3}
                    value={editDescription}
                    onChange={e => setEditDescription(e.target.value)}
                  />
                </label>
              </div>

              <div className="config-edit-actions">
                <button className="btn btn-primary" onClick={saveEdit} disabled={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button className="btn" onClick={() => setSelected(null)}>Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
