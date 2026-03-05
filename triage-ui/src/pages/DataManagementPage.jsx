import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/triageApi';
import './DataManagementPage.css';

const ENTITY_TYPES = [
  { key: 'rules',    label: 'Rules',    icon: '📋' },
  { key: 'actions',  label: 'Actions',  icon: '🎯' },
  { key: 'routes',   label: 'Routes',   icon: '🔀' },
  { key: 'triggers', label: 'Triggers', icon: '⚡' },
];

/** Import order — dependencies first */
const IMPORT_ORDER = ['rules', 'actions', 'routes', 'triggers'];

export default function DataManagementPage({ addToast }) {
  // ====== shared ======
  const [activeTab, setActiveTab] = useState('export');

  // ====== export state ======
  const [exportTypes, setExportTypes]       = useState({ rules: true, actions: true, routes: true, triggers: true });
  const [entityData, setEntityData]         = useState({});        // { rules: [...], ... }
  const [selectedIds, setSelectedIds]       = useState({});        // { rules: Set, ... }
  const [loadingEntities, setLoadingEntities] = useState(false);
  const [exporting, setExporting]           = useState(false);
  const [exportResult, setExportResult]     = useState(null);

  // ====== import state ======
  const [importFile, setImportFile]         = useState(null);
  const [importBundle, setImportBundle]     = useState(null);
  const [importPreview, setImportPreview]   = useState(null);
  const [selectedImports, setSelectedImports] = useState({});      // { rules: Set<name>, ... }
  const [importing, setImporting]           = useState(false);
  const [importResult, setImportResult]     = useState(null);
  const [previewing, setPreviewing]         = useState(false);

  // ===================================================================
  // EXPORT — load entities for selection
  // ===================================================================

  const loadEntities = useCallback(async () => {
    setLoadingEntities(true);
    try {
      const results = {};
      for (const t of ENTITY_TYPES) {
        if (!exportTypes[t.key]) continue;
        const resp = await api[`list${t.label}`]();
        results[t.key] = resp.items || [];
      }
      setEntityData(results);
      // Pre-select all
      const sel = {};
      for (const [type, items] of Object.entries(results)) {
        sel[type] = new Set(items.map((i) => i.id));
      }
      setSelectedIds(sel);
    } catch (err) {
      addToast(`Failed to load entities: ${err.message}`, 'error');
    } finally {
      setLoadingEntities(false);
    }
  }, [exportTypes, addToast]);

  useEffect(() => {
    if (activeTab === 'export') loadEntities();
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleExportType = (key) => {
    setExportTypes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleEntityId = (type, id) => {
    setSelectedIds((prev) => {
      const next = { ...prev };
      const set = new Set(next[type] || []);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      next[type] = set;
      return next;
    });
  };

  const selectAll = (type) => {
    setSelectedIds((prev) => ({
      ...prev,
      [type]: new Set((entityData[type] || []).map((i) => i.id)),
    }));
  };

  const selectNone = (type) => {
    setSelectedIds((prev) => ({ ...prev, [type]: new Set() }));
  };

  // ===================================================================
  // EXPORT — execute
  // ===================================================================

  const handleExport = async () => {
    setExporting(true);
    setExportResult(null);
    try {
      const selections = {};
      for (const t of ENTITY_TYPES) {
        if (!exportTypes[t.key]) continue;
        const ids = selectedIds[t.key];
        const allItems = entityData[t.key] || [];
        if (ids && ids.size > 0 && ids.size < allItems.length) {
          selections[t.key] = [...ids];
        } else if (ids && ids.size === allItems.length) {
          selections[t.key] = null;         // null = all
        }
        // if ids empty → skip this type
      }

      if (Object.keys(selections).length === 0) {
        addToast('No entities selected for export', 'warning');
        setExporting(false);
        return;
      }

      const bundle = await api.exportEntities(selections);
      setExportResult(bundle);

      // Trigger download
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `triage-export-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      addToast(`Exported ${bundle.metadata?.totalEntities || 0} entities`, 'success');
    } catch (err) {
      addToast(`Export failed: ${err.message}`, 'error');
    } finally {
      setExporting(false);
    }
  };

  // ===================================================================
  // IMPORT — file handling
  // ===================================================================

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportFile(file);
    setImportBundle(null);
    setImportPreview(null);
    setImportResult(null);

    try {
      const text = await file.text();
      const bundle = JSON.parse(text);
      setImportBundle(bundle);

      // Auto-preview
      setPreviewing(true);
      const preview = await api.previewImport(bundle);
      setImportPreview(preview);

      // Pre-select all for import
      const sel = {};
      if (preview.preview) {
        for (const [type, info] of Object.entries(preview.preview)) {
          sel[type] = new Set((info.items || []).map((i) => i.name));
        }
      }
      setSelectedImports(sel);
    } catch (err) {
      addToast(`Invalid file: ${err.message}`, 'error');
    } finally {
      setPreviewing(false);
    }
  };

  const toggleImportItem = (type, name) => {
    setSelectedImports((prev) => {
      const next = { ...prev };
      const set = new Set(next[type] || []);
      if (set.has(name)) set.delete(name);
      else set.add(name);
      next[type] = set;
      return next;
    });
  };

  const selectAllImports = (type) => {
    const items = importPreview?.preview?.[type]?.items || [];
    setSelectedImports((prev) => ({
      ...prev,
      [type]: new Set(items.map((i) => i.name)),
    }));
  };

  const selectNoneImports = (type) => {
    setSelectedImports((prev) => ({ ...prev, [type]: new Set() }));
  };

  // ===================================================================
  // IMPORT — execute
  // ===================================================================

  const handleImport = async () => {
    if (!importBundle) return;
    setImporting(true);
    setImportResult(null);
    try {
      // Build selected filter (names per type)
      const selected = {};
      let hasAny = false;
      for (const [type, names] of Object.entries(selectedImports)) {
        if (names.size > 0) {
          selected[type] = [...names];
          hasAny = true;
        }
      }
      if (!hasAny) {
        addToast('No entities selected for import', 'warning');
        setImporting(false);
        return;
      }

      const result = await api.executeImport(importBundle, selected);
      setImportResult(result);

      const t = result.totals || {};
      addToast(
        `Import complete: ${t.created || 0} created, ${t.updated || 0} updated` +
        (t.failed ? `, ${t.failed} failed` : ''),
        t.failed > 0 ? 'warning' : 'success',
      );
    } catch (err) {
      addToast(`Import failed: ${err.message}`, 'error');
    } finally {
      setImporting(false);
    }
  };

  // ===================================================================
  // RENDER
  // ===================================================================

  return (
    <div className="dm-page">
      {/* Header */}
      <div className="page-header">
        <h1>Data Management</h1>
        <p className="page-subtitle">
          Export and import Rules, Actions, Routes, and Triggers between environments
        </p>
      </div>

      {/* Tab bar */}
      <div className="dm-tabs">
        <button
          className={`dm-tab ${activeTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveTab('export')}
        >
          📤 Export
        </button>
        <button
          className={`dm-tab ${activeTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveTab('import')}
        >
          📥 Import
        </button>
      </div>

      {/* ======================== EXPORT TAB ======================== */}
      {activeTab === 'export' && (
        <div className="dm-section">
          {/* Entity type toggles */}
          <div className="dm-card">
            <h3>Select Entity Types</h3>
            <div className="dm-type-toggles">
              {ENTITY_TYPES.map((t) => (
                <label key={t.key} className="dm-type-toggle">
                  <input
                    type="checkbox"
                    checked={exportTypes[t.key]}
                    onChange={() => toggleExportType(t.key)}
                  />
                  <span className="dm-type-icon">{t.icon}</span>
                  {t.label}
                  {entityData[t.key] && (
                    <span className="dm-type-count">
                      ({selectedIds[t.key]?.size || 0}/{entityData[t.key].length})
                    </span>
                  )}
                </label>
              ))}
              <button className="dm-btn-sm" onClick={loadEntities} disabled={loadingEntities}>
                {loadingEntities ? 'Loading…' : '↻ Refresh'}
              </button>
            </div>
          </div>

          {/* Per-record selection */}
          {ENTITY_TYPES.filter((t) => exportTypes[t.key] && entityData[t.key]?.length > 0).map((t) => (
            <div key={t.key} className="dm-card dm-record-card">
              <div className="dm-record-header">
                <h4>{t.icon} {t.label}</h4>
                <div className="dm-record-actions">
                  <button className="dm-btn-link" onClick={() => selectAll(t.key)}>Select All</button>
                  <button className="dm-btn-link" onClick={() => selectNone(t.key)}>Select None</button>
                </div>
              </div>
              <div className="dm-record-list">
                {(entityData[t.key] || []).map((item) => (
                  <label key={item.id} className="dm-record-item">
                    <input
                      type="checkbox"
                      checked={selectedIds[t.key]?.has(item.id) || false}
                      onChange={() => toggleEntityId(t.key, item.id)}
                    />
                    <span className="dm-record-name">{item.name}</span>
                    <span className={`dm-status-badge dm-status-${item.status}`}>
                      {item.status}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ))}

          {/* Export button & result */}
          <div className="dm-action-bar">
            <button
              className="dm-btn-primary"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting ? 'Exporting…' : '📤 Export Selected'}
            </button>
          </div>

          {exportResult && (
            <div className="dm-result-card dm-result-success">
              <h4>✓ Export Complete</h4>
              <p>{exportResult.metadata?.totalEntities} entities exported</p>
              {exportResult.dependencies?.length > 0 && (
                <div className="dm-dep-section">
                  <h5>Auto-included dependencies:</h5>
                  <ul>
                    {exportResult.dependencies.map((d, i) => (
                      <li key={i}>
                        <strong>{d.name}</strong> ({d.type}) — {d.reason}
                        <span className="dm-dep-tag">required by {d.requiredBy}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="dm-entity-counts">
                {Object.entries(exportResult.metadata?.entityCounts || {}).map(([type, count]) => (
                  <span key={type} className="dm-count-badge">
                    {type}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================== IMPORT TAB ======================== */}
      {activeTab === 'import' && (
        <div className="dm-section">
          {/* File upload */}
          <div className="dm-card">
            <h3>Upload Export File</h3>
            <div className="dm-upload-area">
              <input
                type="file"
                accept=".json"
                onChange={handleFileChange}
                id="import-file"
                className="dm-file-input"
              />
              <label htmlFor="import-file" className="dm-upload-label">
                {importFile ? (
                  <>📄 {importFile.name}</>
                ) : (
                  <>📂 Choose a .json export file</>
                )}
              </label>
            </div>
          </div>

          {/* Preview */}
          {previewing && (
            <div className="dm-card">
              <p className="dm-loading">Analyzing file…</p>
            </div>
          )}

          {importPreview && importPreview.valid && (
            <>
              {/* Metadata */}
              <div className="dm-card dm-meta-card">
                <h4>File Info</h4>
                <div className="dm-meta-grid">
                  <span>Exported:</span>
                  <span>{new Date(importPreview.metadata?.exportDate).toLocaleString()}</span>
                  <span>By:</span>
                  <span>{importPreview.metadata?.exportedBy || 'unknown'}</span>
                  <span>Format:</span>
                  <span>v{importPreview.metadata?.formatVersion || '?'}</span>
                </div>
              </div>

              {/* Per-type preview */}
              {IMPORT_ORDER.filter((key) => importPreview.preview?.[key]).map((key) => {
                const info = importPreview.preview[key];
                const label = ENTITY_TYPES.find((t) => t.key === key)?.label || key;
                const icon  = ENTITY_TYPES.find((t) => t.key === key)?.icon || '';
                return (
                  <div key={key} className="dm-card dm-record-card">
                    <div className="dm-record-header">
                      <h4>
                        {icon} {label}
                        <span className="dm-preview-counts">
                          <span className="dm-count-new">{info.new} new</span>
                          <span className="dm-count-update">{info.update} update</span>
                        </span>
                      </h4>
                      <div className="dm-record-actions">
                        <button className="dm-btn-link" onClick={() => selectAllImports(key)}>Select All</button>
                        <button className="dm-btn-link" onClick={() => selectNoneImports(key)}>Select None</button>
                      </div>
                    </div>
                    <div className="dm-record-list">
                      {(info.items || []).map((item, i) => (
                        <label key={i} className={`dm-record-item dm-import-${item.action}`}>
                          <input
                            type="checkbox"
                            checked={selectedImports[key]?.has(item.name) || false}
                            onChange={() => toggleImportItem(key, item.name)}
                          />
                          <span className="dm-record-name">{item.name}</span>
                          <span className={`dm-action-badge dm-action-${item.action}`}>
                            {item.action}
                          </span>
                          {item.existingId && (
                            <span className="dm-existing-id" title={`Existing: ${item.existingId}`}>
                              → {item.existingId}
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Import button */}
              <div className="dm-action-bar">
                <button
                  className="dm-btn-primary dm-btn-import"
                  onClick={handleImport}
                  disabled={importing}
                >
                  {importing ? 'Importing…' : '📥 Import Selected'}
                </button>
                <span className="dm-backup-note">
                  ⓘ Current state will be auto-backed up before import
                </span>
              </div>
            </>
          )}

          {/* Import result */}
          {importResult && (
            <div className={`dm-result-card ${importResult.success ? 'dm-result-success' : 'dm-result-error'}`}>
              <h4>{importResult.success ? '✓ Import Complete' : '✗ Import Failed'}</h4>
              <div className="dm-import-totals">
                <span className="dm-count-new">Created: {importResult.totals?.created || 0}</span>
                <span className="dm-count-update">Updated: {importResult.totals?.updated || 0}</span>
                {(importResult.totals?.failed > 0) && (
                  <span className="dm-count-failed">Failed: {importResult.totals.failed}</span>
                )}
              </div>

              {/* Per-type details */}
              {importResult.results && Object.entries(importResult.results).map(([type, r]) => (
                <div key={type} className="dm-import-type-result">
                  <strong>{type}:</strong> {r.created} created, {r.updated} updated
                  {r.failed > 0 && <span className="dm-count-failed"> ({r.failed} failed)</span>}
                  {r.errors?.length > 0 && (
                    <ul className="dm-error-list">
                      {r.errors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  )}
                </div>
              ))}

              {importResult.backup && (
                <div className="dm-backup-info">
                  <p>📦 Pre-import backup created at {importResult.backup.exportDate}</p>
                  {importResult.backup.isBackup && (
                    <span className="dm-backup-tag">Available in Audit Log</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
