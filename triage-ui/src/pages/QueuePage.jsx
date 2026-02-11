/**
 * QueuePage — Tabbed Analysis / Triage Queue
 * =============================================
 *
 * Two-tab interface driven by Custom.ROBAnalysisState:
 *
 *  Analysis tab  – items needing analysis (Pending / Needs Info / No Match / blank)
 *    Actions: "Analyze Selected", "Ready for Triage"
 *
 *  Triage tab    – items ready for triage (Awaiting Approval)
 *    Actions: "Dry Run Selected", "Evaluate Selected", per-row Apply, "Return to Analysis"
 *
 * Items with Approved / Override / Redirected are hidden (done).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import * as api from '../api/triageApi';
import { formatDate, truncate } from '../utils/helpers';
import './QueuePage.css';


// ── ROBAnalysisState bucket definitions ─────────────────────────

/** States that appear in the Analysis tab */
const ANALYSIS_STATES = new Set(['Pending', 'Needs Info', 'No Match', '', undefined, null]);
const isAnalysisItem = (item) => {
  const state = item.fields?.['Custom.ROBAnalysisState'] ?? '';
  return ANALYSIS_STATES.has(state);
};

/** States that appear in the Triage tab */
const isTriageItem = (item) => {
  const state = item.fields?.['Custom.ROBAnalysisState'] ?? '';
  return state === 'Awaiting Approval';
};


// ── Column definitions ──────────────────────────────────────────

const COLUMNS = [
  { key: 'System.Id',                    label: 'ID',          width: 70,  sticky: true },
  { key: 'System.Title',                 label: 'Title',       width: 260 },
  { key: 'Custom.ROBAnalysisState',      label: 'Analysis State', width: 120 },
  { key: 'Custom.Customer_Commitment',   label: 'Commitment',  width: 105 },
  { key: 'Custom.MilestoneStatus',       label: 'MS Status',   width: 100 },
  { key: 'Custom.MilestoneID',          label: 'Milestone ID',width: 120 },
  { key: 'Custom.SolutionArea',          label: 'Solution Area',width: 140 },
  { key: 'analysis.category',           label: 'Category',    width: 130 },
  { key: 'analysis.intent',             label: 'Intent',      width: 130 },
  { key: 'Custom.AreaField',             label: 'Area',        width: 100 },
  { key: 'Custom.Segment',              label: 'Segment',     width: 150 },
  { key: 'Custom.pTriageType',          label: 'Triage Type', width: 120 },
  { key: 'Custom.HelpNeededField',      label: 'Help Needed', width: 130 },
  { key: 'Custom.Opportunity_ID',       label: 'Opp ID',      width: 120 },
  { key: 'Custom.OpportunityStage',     label: 'Opp Stage',   width: 120 },
  { key: 'Custom.PartnerOneName',       label: 'Partner',     width: 120 },
  { key: 'System.CommentCount',         label: '\uD83D\uDCAC',   width: 40  },
  { key: 'Custom.AssignToCorpDate',     label: 'Corp Date',   width: 100,
    render: (v) => v ? formatDate(v) : '\u2014' },
];

/** Badge color mapping for commitment values */
const COMMITMENT_CLASSES = {
  'Committed': 'badge-committed',
  'Uncommitted': 'badge-uncommitted',
  'Best Case': 'badge-bestcase',
};

/** Badge color mapping for milestone status */
const MS_STATUS_CLASSES = {
  'On Track': 'badge-ontrack',
  'Blocked': 'badge-blocked',
  'At Risk': 'badge-atrisk',
  'Completed': 'badge-completed',
};

/** Badge color mapping for ROBAnalysisState */
const STATE_CLASSES = {
  'Pending':            'state-pending',
  'Needs Info':         'state-needs-info',
  'No Match':           'state-no-match',
  'Awaiting Approval':  'state-awaiting',
  'Approved':           'state-approved',
  'Override':           'state-override',
  'Redirected':         'state-redirected',
};


export default function QueuePage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [items, setItems] = useState([]);
  const [queryName, setQueryName] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('analysis');   // 'analysis' | 'triage'
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [evaluating, setEvaluating] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [settingState, setSettingState] = useState(false);
  const [results, setResults] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [applying, setApplying] = useState(null);
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [totalAvailable, setTotalAvailable] = useState(0);

  // Analysis state
  const [analysisMap, setAnalysisMap] = useState({});       // { workItemId: { category, intent, ... } }
  const [analysisDetail, setAnalysisDetail] = useState(null);
  const [analysisDetailId, setAnalysisDetailId] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Analysis progress panel state
  const [analysisProgress, setAnalysisProgress] = useState(null);
  // Shape: { total, completed, failed, currentId, items: [ { id, title, status, category, intent, confidence, source, error } ] }


  // ── Load Queue (Saved Query) ─────────────────────────────────

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setSelectedIds(new Set());
    setResults(null);
    setAnalysisMap({});
    setAnalysisDetail(null);
    setAnalysisDetailId(null);
    try {
      const data = await api.getSavedQueryResults(null, 200);
      const loadedItems = data.items || [];
      setItems(loadedItems);
      setQueryName(data.queryName || '');
      setTotalAvailable(data.totalAvailable || data.count || 0);
      if (data.failedIds?.length > 0) {
        addToast?.(`${data.failedIds.length} items failed to load`, 'warning');
      }

      // Batch-fetch analysis status for all work item IDs
      if (loadedItems.length > 0) {
        try {
          const ids = loadedItems.map((i) => i.id);
          const analysisData = await api.getAnalysisBatch(ids);
          setAnalysisMap(analysisData.results || {});
        } catch {
          // Non-fatal: analysis lookup can fail silently
        }
      }
    } catch (err) {
      addToast?.(err.message, 'error');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [addToast]);


  useEffect(() => {
    loadQueue();
  }, [loadQueue]);


  // ── Filtered items per tab ───────────────────────────────────

  const analysisItems = useMemo(() => items.filter(isAnalysisItem), [items]);
  const triageItems   = useMemo(() => items.filter(isTriageItem), [items]);
  const tabItems      = activeTab === 'analysis' ? analysisItems : triageItems;


  // ── Sorting ──────────────────────────────────────────────────

  const handleSort = (colKey) => {
    if (sortCol === colKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(colKey);
      setSortDir('asc');
    }
  };

  const sortedItems = useMemo(() => {
    if (!sortCol) return tabItems;
    return [...tabItems].sort((a, b) => {
      let av, bv;
      if (sortCol.startsWith('analysis.')) {
        const field = sortCol.replace('analysis.', '');
        av = analysisMap[String(a.id)]?.[field] ?? '';
        bv = analysisMap[String(b.id)]?.[field] ?? '';
      } else {
        av = a.fields?.[sortCol] ?? '';
        bv = b.fields?.[sortCol] ?? '';
      }
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [tabItems, sortCol, sortDir, analysisMap]);


  // ── Selection ────────────────────────────────────────────────

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === tabItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tabItems.map((i) => i.id)));
    }
  };

  // Clear selection when switching tabs
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSelectedIds(new Set());
    setResults(null);
    setExpandedId(null);
  };


  // ── Analyze Selected (Analysis tab) — per-item progress ────

  const handleAnalyze = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      addToast?.('Select at least one work item', 'warning');
      return;
    }

    // Check AI availability before starting
    try {
      const status = await api.getAnalysisEngineStatus();
      if (!status.aiAvailable) {
        const proceed = window.confirm(
          `⚠️ AI Analysis Engine is not available.\n\n` +
          `Mode: ${status.mode}\n` +
          `${status.error ? `Error: ${status.error}\n\n` : '\n'}` +
          `Analysis will use pattern matching only, which provides lower ` +
          `confidence results without LLM-powered reasoning.\n\n` +
          `Do you want to continue with pattern-only analysis?`
        );
        if (!proceed) return;
      }
    } catch {
      // If status check fails, warn and let user decide
      const proceed = window.confirm(
        `⚠️ Unable to check analysis engine status.\n\n` +
        `The AI service may be unavailable. Continue anyway?`
      );
      if (!proceed) return;
    }

    // Build progress tracker with titles from loaded items
    const progressItems = ids.map((id) => {
      const item = items.find((i) => i.id === id);
      return {
        id,
        title: item?.fields?.['System.Title'] || `#${id}`,
        status: 'queued',   // queued → analyzing → done | failed
        category: null,
        intent: null,
        confidence: null,
        source: null,
        error: null,
      };
    });

    setAnalysisProgress({
      total: ids.length,
      completed: 0,
      failed: 0,
      currentId: null,
      items: progressItems,
    });
    setAnalyzing(true);

    let completed = 0;
    let failed = 0;

    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];

      // Mark current item as analyzing
      setAnalysisProgress((prev) => ({
        ...prev,
        currentId: id,
        items: prev.items.map((it) =>
          it.id === id ? { ...it, status: 'analyzing' } : it
        ),
      }));

      try {
        const data = await api.runAnalysis([id]);
        const result = data.results?.[0];

        if (result?.success) {
          completed++;
          setAnalysisProgress((prev) => ({
            ...prev,
            completed,
            failed,
            items: prev.items.map((it) =>
              it.id === id
                ? {
                    ...it,
                    status: 'done',
                    category: result.category,
                    intent: result.intent,
                    confidence: result.confidence,
                    source: result.source,
                  }
                : it
            ),
          }));
        } else {
          failed++;
          setAnalysisProgress((prev) => ({
            ...prev,
            completed,
            failed,
            items: prev.items.map((it) =>
              it.id === id
                ? { ...it, status: 'failed', error: result?.error || 'Unknown error' }
                : it
            ),
          }));
        }
      } catch (err) {
        failed++;
        setAnalysisProgress((prev) => ({
          ...prev,
          completed,
          failed,
          items: prev.items.map((it) =>
            it.id === id
              ? { ...it, status: 'failed', error: err.message }
              : it
          ),
        }));
      }
    }

    // Mark progress as finished (currentId = null)
    setAnalysisProgress((prev) => prev ? { ...prev, currentId: null } : null);

    addToast?.(
      `Analyzed ${completed + failed} item(s) — ${completed} succeeded${failed > 0 ? `, ${failed} failed` : ''}`,
      failed > 0 ? 'warning' : 'success'
    );

    // Refresh analysis map for all processed items
    try {
      const analysisData = await api.getAnalysisBatch(ids);
      setAnalysisMap((prev) => ({ ...prev, ...(analysisData.results || {}) }));
    } catch { /* non-fatal */ }

    setAnalyzing(false);
  };


  // ── Set Analysis State (shared) ──────────────────────────────

  const handleSetState = async (newState, successMsg) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      addToast?.('Select at least one work item', 'warning');
      return;
    }

    setSettingState(true);
    try {
      const data = await api.setAnalysisState(ids, newState);
      addToast?.(
        successMsg || `Set ${data.updated} item(s) to "${newState}"`,
        data.failed > 0 ? 'warning' : 'success'
      );

      // Update local item fields so filtering re-renders correctly
      setItems((prev) =>
        prev.map((item) =>
          ids.includes(item.id)
            ? { ...item, fields: { ...item.fields, 'Custom.ROBAnalysisState': newState } }
            : item
        )
      );
      setSelectedIds(new Set());
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setSettingState(false);
    }
  };


  // ── Evaluate Selected (Triage tab) ───────────────────────────

  const handleEvaluate = async (dryRun = true) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      addToast?.('Select at least one work item', 'warning');
      return;
    }

    setEvaluating(true);
    setResults(null);
    try {
      const data = dryRun
        ? await api.evaluateTest(ids)
        : await api.evaluate(ids, false);

      setResults(data);
      addToast?.(
        `Evaluated ${data.evaluations?.length || 0} item(s)${dryRun ? ' (dry run)' : ''}`,
        'success'
      );
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setEvaluating(false);
    }
  };


  // ── Apply Single Result ──────────────────────────────────────

  const handleApply = async (evalResult) => {
    setApplying(evalResult.id);
    try {
      const result = await api.applyEvaluation(evalResult.id, evalResult.workItemId);
      if (result.success) {
        addToast?.(
          `Applied ${result.fieldsUpdated} changes to #${evalResult.workItemId}`,
          'success'
        );
      } else {
        addToast?.(result.error || 'Apply failed', 'error');
      }
    } catch (err) {
      addToast?.(err.message, 'error');
    } finally {
      setApplying(null);
    }
  };


  // ── Find result for a queue item ─────────────────────────────

  const getResultForItem = (workItemId) => {
    return results?.evaluations?.find((e) => e.workItemId === workItemId);
  };


  // ── Analysis Detail Panel ────────────────────────────────────

  const handleAnalysisClick = async (workItemId, e) => {
    e.stopPropagation();
    if (analysisDetailId === workItemId) {
      setAnalysisDetailId(null);
      setAnalysisDetail(null);
      return;
    }
    setAnalysisDetailId(workItemId);
    setLoadingDetail(true);
    try {
      const detail = await api.getAnalysisDetail(workItemId);
      setAnalysisDetail(detail);
    } catch {
      setAnalysisDetail(null);
      addToast?.(`No analysis found for #${workItemId}`, 'info');
      setAnalysisDetailId(null);
    } finally {
      setLoadingDetail(false);
    }
  };


  // ── Render a cell value ──────────────────────────────────────

  const renderCell = (col, item) => {
    // Analysis columns — pull from analysisMap
    if (col.key.startsWith('analysis.')) {
      const field = col.key.replace('analysis.', '');
      const analysis = analysisMap[String(item.id)];
      if (!analysis) return '\u2014';
      const val = analysis[field];
      if (val === undefined || val === null || val === '') return '\u2014';
      if (field === 'category') {
        const label = String(val).replace(/_/g, ' ');
        return <span className="queue-badge analysis-category-badge">{label}</span>;
      }
      if (field === 'intent') {
        const label = String(val).replace(/_/g, ' ');
        return <span className="queue-analysis-intent">{label}</span>;
      }
      return String(val);
    }

    const val = item.fields?.[col.key];

    if (col.render) return col.render(val, item);

    // ID column → ADO link
    if (col.key === 'System.Id') {
      return (
        <a
          href={item.adoLink}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="queue-id-link"
        >
          {item.id}
        </a>
      );
    }

    // Title column → truncated with tooltip
    if (col.key === 'System.Title') {
      return <span title={val}>{truncate(val, 55)}</span>;
    }

    // ROBAnalysisState → colored badge
    if (col.key === 'Custom.ROBAnalysisState') {
      const state = val || 'Pending';
      const cls = STATE_CLASSES[state] || '';
      return <span className={`queue-badge queue-state-badge ${cls}`}>{state}</span>;
    }

    // Commitment badge
    if (col.key === 'Custom.Customer_Commitment' && val) {
      const cls = COMMITMENT_CLASSES[val] || '';
      return <span className={`queue-badge ${cls}`}>{val}</span>;
    }

    // Milestone status badge
    if (col.key === 'Custom.MilestoneStatus' && val) {
      const cls = MS_STATUS_CLASSES[val] || '';
      return <span className={`queue-badge ${cls}`}>{val}</span>;
    }

    // Triage Type
    if (col.key === 'Custom.pTriageType' && val) {
      return <span className="queue-triage-type">{val}</span>;
    }

    if (val === undefined || val === null || val === '') return '\u2014';
    return String(val);
  };


  // ── Busy state for any action ────────────────────────────────

  const busy = loading || evaluating || analyzing || settingState;
  const showSimpleOverlay = (loading || evaluating || settingState) && !analyzing;
  const simpleOverlayMsg = loading
    ? 'Loading triage queue from ADO\u2026'
    : evaluating
      ? 'Running evaluation pipeline\u2026'
      : settingState
        ? 'Updating analysis state\u2026'
        : '';


  // ── Render ───────────────────────────────────────────────────

  const colCount = COLUMNS.length + 3; // +analysis dot +checkbox +actions

  return (
    <div className="queue-page">
      <div className="page-header">
        <h1>📥 Triage Queue</h1>
        <div className="page-header-actions">
          {queryName && (
            <span className="queue-query-name" title={queryName}>
              {queryName}
            </span>
          )}
          <button
            className="btn btn-secondary"
            onClick={loadQueue}
            disabled={busy}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* ── Toolbar ───────────────────────────────────────────────── */}
      <div className="queue-action-bar">
        <span className="queue-count">
          {loading ? 'Loading\u2026' : `${tabItems.length} items`}
          {totalAvailable > items.length && ` of ${totalAvailable} total`}
          {selectedIds.size > 0 && ` \xb7 ${selectedIds.size} selected`}
        </span>
        <div className="queue-action-buttons">
          {activeTab === 'analysis' ? (
            <>
              <button
                className="btn btn-toolbar"
                disabled={selectedIds.size === 0 || busy}
                onClick={handleAnalyze}
              >
                {analyzing ? 'Analyzing…' : '🧠 Analyze Selected'}
              </button>
              <button
                className="btn btn-toolbar"
                disabled={selectedIds.size === 0 || busy}
                onClick={() => handleSetState('Awaiting Approval')}
                title="Mark selected items as ready for triage"
              >
                {settingState ? 'Updating…' : '✅ Ready for Triage'}
              </button>
            </>
          ) : (
            <>
              <button
                className="btn btn-toolbar"
                disabled={selectedIds.size === 0 || busy}
                onClick={() => handleEvaluate(true)}
              >
                {evaluating ? 'Evaluating…' : '🧪 Dry Run Selected'}
              </button>
              <button
                className="btn btn-toolbar"
                disabled={selectedIds.size === 0 || busy}
                onClick={() => handleEvaluate(false)}
              >
                {evaluating ? 'Evaluating…' : '⚡ Evaluate Selected'}
              </button>
              <button
                className="btn btn-toolbar"
                disabled={selectedIds.size === 0 || busy}
                onClick={() => handleSetState('Pending', 'Returned items to Analysis')}
                title="Return selected items to the Analysis tab"
              >
                {settingState ? 'Updating…' : '↩️ Return to Analysis'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Tab Bar ─────────────────────────────────────────────── */}
      <div className="queue-tabs">
        <button
          className={`queue-tab tab-analysis ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => handleTabChange('analysis')}
        >
          🔬 Analysis
          <span className="queue-tab-count">{analysisItems.length}</span>
        </button>
        <button
          className={`queue-tab tab-triage ${activeTab === 'triage' ? 'active' : ''}`}
          onClick={() => handleTabChange('triage')}
        >
          ⚖️ Triage
          <span className="queue-tab-count">{triageItems.length}</span>
        </button>
      </div>

      {/* Loading / Busy Overlay (non-analysis) */}
      {showSimpleOverlay && (
        <div className="queue-overlay">
          <div className="queue-spinner" />
          <p className="queue-overlay-text">{simpleOverlayMsg}</p>
        </div>
      )}

      {/* ── Analysis Progress Panel ────────────────────────────── */}
      {analysisProgress && (
        <div className="analysis-progress-overlay">
          <div className="analysis-progress-panel">
            <div className="analysis-progress-header">
              <h3>🧠 Analyzing Work Items</h3>
              {!analyzing && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setAnalysisProgress(null)}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Overall progress bar */}
            <div className="analysis-progress-bar-section">
              <div className="analysis-progress-stats">
                <span>
                  {analysisProgress.completed + analysisProgress.failed} of {analysisProgress.total} items
                </span>
                <span className="analysis-progress-pct">
                  {Math.round(((analysisProgress.completed + analysisProgress.failed) / analysisProgress.total) * 100)}%
                </span>
              </div>
              <div className="analysis-progress-track">
                <div
                  className={`analysis-progress-fill ${!analyzing ? 'done' : ''}`}
                  style={{
                    width: `${((analysisProgress.completed + analysisProgress.failed) / analysisProgress.total) * 100}%`,
                  }}
                />
              </div>
              {analysisProgress.failed > 0 && (
                <div className="analysis-progress-fail-note">
                  {analysisProgress.failed} failed
                </div>
              )}
            </div>

            {/* Per-item status cards */}
            <div className="analysis-progress-items">
              {analysisProgress.items.map((pi) => (
                <div key={pi.id} className={`analysis-progress-item status-${pi.status}`}>
                  <div className="api-status-icon">
                    {pi.status === 'queued' && <span className="api-icon queued">○</span>}
                    {pi.status === 'analyzing' && <span className="api-icon analyzing" />}
                    {pi.status === 'done' && <span className="api-icon done">✓</span>}
                    {pi.status === 'failed' && <span className="api-icon failed">✗</span>}
                  </div>
                  <div className="api-item-info">
                    <div className="api-item-title">
                      <span className="api-item-id">#{pi.id}</span>
                      {truncate(pi.title, 60)}
                    </div>
                    {pi.status === 'done' && (
                      <div className="api-item-result">
                        <span className="queue-badge analysis-category-badge">
                          {(pi.category || '').replace(/_/g, ' ')}
                        </span>
                        <span className="api-item-intent">
                          {(pi.intent || '').replace(/_/g, ' ')}
                        </span>
                        <span className={`api-item-confidence ${pi.confidence >= 0.8 ? 'high' : pi.confidence >= 0.5 ? 'medium' : 'low'}`}>
                          {((pi.confidence || 0) * 100).toFixed(0)}%
                        </span>
                        <span className="api-item-source">{pi.source}</span>
                      </div>
                    )}
                    {pi.status === 'failed' && (
                      <div className="api-item-error">{pi.error}</div>
                    )}
                    {pi.status === 'analyzing' && (
                      <div className="api-item-analyzing">Analyzing title, description, and context…</div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Done state */}
            {!analyzing && (
              <div className="analysis-progress-footer">
                <button
                  className="btn btn-primary"
                  onClick={() => setAnalysisProgress(null)}
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Queue Table */}
      <div className="card queue-table-card">
        <table className="queue-table">
          <thead>
            <tr>
              <th className="queue-col-analysis" title="Analysis status">A</th>
              <th className="queue-col-check">
                <input
                  type="checkbox"
                  checked={tabItems.length > 0 && selectedIds.size === tabItems.length}
                  onChange={toggleSelectAll}
                  disabled={tabItems.length === 0}
                />
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="queue-col-header"
                  style={{ width: col.width, minWidth: col.width }}
                  onClick={() => handleSort(col.key)}
                  title={`Sort by ${col.label}`}
                >
                  {col.label}
                  {sortCol === col.key && (
                    <span className="sort-arrow">{sortDir === 'asc' ? ' \u25B2' : ' \u25BC'}</span>
                  )}
                </th>
              ))}
              <th className="queue-col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={colCount} className="queue-loading"></td>
              </tr>
            ) : tabItems.length === 0 ? (
              <tr>
                <td colSpan={colCount} className="queue-empty">
                  {activeTab === 'analysis'
                    ? 'No items need analysis. All items are in triage or done.'
                    : 'No items awaiting triage. Run analysis first, then mark items "Ready for Triage".'
                  }
                </td>
              </tr>
            ) : (
              sortedItems.map((item) => {
                const evalResult = getResultForItem(item.id);
                return (
                  <React.Fragment key={item.id}>
                    <tr
                      className={`queue-row ${selectedIds.has(item.id) ? 'selected' : ''} ${evalResult ? 'has-result' : ''}`}
                      onClick={() => toggleSelect(item.id)}
                    >
                      <td className="queue-col-analysis" onClick={(e) => e.stopPropagation()}>
                        {(() => {
                          const hasAnalysis = !!analysisMap[String(item.id)];
                          return (
                            <button
                              className={`analysis-dot ${hasAnalysis ? 'analysis-done' : 'analysis-none'}`}
                              title={hasAnalysis ? 'View analysis details' : 'No analysis yet'}
                              onClick={(e) => hasAnalysis ? handleAnalysisClick(item.id, e) : e.stopPropagation()}
                              disabled={!hasAnalysis}
                            />
                          );
                        })()}
                      </td>
                      <td className="queue-col-check" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={() => toggleSelect(item.id)}
                        />
                      </td>
                      {COLUMNS.map((col) => (
                        <td
                          key={col.key}
                          className={`queue-cell ${col.sticky ? 'queue-col-id' : ''}`}
                        >
                          {renderCell(col, item)}
                        </td>
                      ))}
                      <td className="queue-col-actions" onClick={(e) => e.stopPropagation()}>
                        {evalResult && (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setExpandedId(
                              expandedId === item.id ? null : item.id
                            )}
                          >
                            {expandedId === item.id ? '\u25BC' : '\u25B6'} Results
                          </button>
                        )}
                        <a
                          href={item.adoLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-ghost btn-sm"
                        >
                          ADO ↗
                        </a>
                      </td>
                    </tr>

                    {/* Inline Evaluation Result (expandable) */}
                    {evalResult && expandedId === item.id && (
                      <tr className="queue-result-row">
                        <td colSpan={colCount}>
                          <div className="queue-result-detail">
                            <div className="queue-result-summary">
                              <span className={`queue-analysis-badge analysis-${evalResult.analysisState?.replace(/\s/g, '-').toLowerCase()}`}>
                                {evalResult.analysisState}
                              </span>
                              {evalResult.matchedTrigger && (
                                <span className="queue-result-tag">⚡ {evalResult.matchedTrigger}</span>
                              )}
                              {evalResult.appliedRoute && (
                                <span className="queue-result-tag">🔀 {evalResult.appliedRoute}</span>
                              )}
                            </div>

                            {/* Rule Results */}
                            <div className="queue-result-rules">
                              {Object.entries(evalResult.ruleResults || {}).map(([ruleId, passed]) => (
                                <span
                                  key={ruleId}
                                  className={`queue-rule-chip ${passed ? 'rule-true' : 'rule-false'}`}
                                >
                                  {passed ? '\u2713' : '\u2717'} {ruleId}
                                </span>
                              ))}
                            </div>

                            {/* Field Changes */}
                            {Object.keys(evalResult.fieldsChanged || {}).length > 0 && (
                              <table className="queue-changes-table">
                                <thead>
                                  <tr><th>Field</th><th>From</th><th>To</th></tr>
                                </thead>
                                <tbody>
                                  {Object.entries(evalResult.fieldsChanged).map(([field, change]) => (
                                    <tr key={field}>
                                      <td><code className="field-ref">{field}</code></td>
                                      <td className="text-muted">{change.from ?? '\u2014'}</td>
                                      <td><strong>{change.to ?? '\u2014'}</strong></td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}

                            {/* Apply Button */}
                            {!evalResult.isDryRun && (
                              <div className="queue-result-actions">
                                <button
                                  className="btn btn-primary btn-sm"
                                  disabled={applying === evalResult.id}
                                  onClick={() => handleApply(evalResult)}
                                >
                                  {applying === evalResult.id ? 'Applying\u2026' : 'Apply to ADO'}
                                </button>
                              </div>
                            )}

                            {/* Errors */}
                            {evalResult.errors?.length > 0 && (
                              <div className="queue-result-errors">
                                {evalResult.errors.map((err, i) => (
                                  <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Analysis Detail Panel (slide-out) */}
      {analysisDetailId && (
        <div className="analysis-detail-overlay" onClick={() => { setAnalysisDetailId(null); setAnalysisDetail(null); }}>
          <div className="analysis-detail-panel" onClick={(e) => e.stopPropagation()}>
            <div className="analysis-detail-header">
              <h3>Analysis Details — #{analysisDetailId}</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => { setAnalysisDetailId(null); setAnalysisDetail(null); }}>
                {'✕'}
              </button>
            </div>
            {loadingDetail ? (
              <div className="analysis-detail-loading">Loading analysis...</div>
            ) : analysisDetail ? (
              <div className="analysis-detail-body">

                {/* AI Availability Warning */}
                {analysisDetail.aiAvailable === false && (
                  <div className="analysis-ai-warning">
                    {'⚠️'} AI engine was not available — results are pattern-matching only
                    {analysisDetail.aiError && <span className="ai-error-detail"> ({analysisDetail.aiError})</span>}
                  </div>
                )}

                {/* Quality Score (prominent) */}
                <section className="analysis-section analysis-quality-section">
                  <div className="quality-score-display">
                    <div className={`quality-score-ring ${analysisDetail.confidence >= 0.8 ? 'high' : analysisDetail.confidence >= 0.5 ? 'medium' : 'low'}`}>
                      <span className="quality-score-value">{((analysisDetail.confidence || 0) * 100).toFixed(0)}</span>
                      <span className="quality-score-label">%</span>
                    </div>
                    <div className="quality-score-meta">
                      <span className="quality-score-title">Confidence Score</span>
                      <span className="quality-score-source">Source: {analysisDetail.source || 'Unknown'}</span>
                      {analysisDetail.agreement !== undefined && (
                        <span className="quality-score-agreement">{analysisDetail.agreement ? '✅ Models agree' : '❌ Models disagree'}</span>
                      )}
                    </div>
                  </div>
                </section>

                {/* Classification */}
                <section className="analysis-section">
                  <h4>Classification</h4>
                  <div className="analysis-field-grid">
                    <div className="analysis-field">
                      <label>Category</label>
                      <span className="queue-badge analysis-category-badge">{(analysisDetail.category || '').replace(/_/g, ' ')}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Intent</label>
                      <span>{(analysisDetail.intent || '').replace(/_/g, ' ')}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Business Impact</label>
                      <span className={`impact-badge impact-${(analysisDetail.businessImpact || '').toLowerCase()}`}>
                        {analysisDetail.businessImpact || '—'}
                      </span>
                    </div>
                    <div className="analysis-field">
                      <label>Technical Complexity</label>
                      <span>{analysisDetail.technicalComplexity || '—'}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Urgency</label>
                      <span className={`impact-badge impact-${(analysisDetail.urgencyLevel || '').toLowerCase()}`}>
                        {analysisDetail.urgencyLevel || '—'}
                      </span>
                    </div>
                  </div>
                </section>

                {/* AI Analysis Summary */}
                {analysisDetail.contextSummary && (
                  <section className="analysis-section">
                    <h4>AI Analysis Summary</h4>
                    <p className="analysis-summary-text">{analysisDetail.contextSummary}</p>
                  </section>
                )}

                {/* Key Concepts */}
                {analysisDetail.keyConcepts?.length > 0 && (
                  <section className="analysis-section">
                    <h4>Key Concepts</h4>
                    <div className="analysis-tags">
                      {analysisDetail.keyConcepts.map((c, i) => <span key={i} className="analysis-tag tag-concept">{c}</span>)}
                    </div>
                  </section>
                )}

                {/* Azure Services */}
                {analysisDetail.azureServices?.length > 0 && (
                  <section className="analysis-section">
                    <h4>Azure Services</h4>
                    <div className="analysis-tags">
                      {analysisDetail.azureServices.map((s, i) => <span key={i} className="analysis-tag tag-service">{s}</span>)}
                    </div>
                  </section>
                )}

                {/* Technologies */}
                {analysisDetail.technologies?.length > 0 && (
                  <section className="analysis-section">
                    <h4>Technologies</h4>
                    <div className="analysis-tags">
                      {analysisDetail.technologies.map((t, i) => <span key={i} className="analysis-tag tag-tech">{t}</span>)}
                    </div>
                  </section>
                )}

                {/* Technical Areas */}
                {analysisDetail.technicalAreas?.length > 0 && (
                  <section className="analysis-section">
                    <h4>Technical Areas</h4>
                    <div className="analysis-tags">
                      {analysisDetail.technicalAreas.map((a, i) => <span key={i} className="analysis-tag tag-area">{a}</span>)}
                    </div>
                  </section>
                )}

                {/* Products */}
                {analysisDetail.detectedProducts?.length > 0 && (
                  <section className="analysis-section">
                    <h4>Detected Products</h4>
                    <div className="analysis-tags">
                      {analysisDetail.detectedProducts.map((p, i) => <span key={i} className="analysis-tag tag-product">{p}</span>)}
                    </div>
                  </section>
                )}

                {/* Metadata */}
                <section className="analysis-section analysis-meta">
                  <span className="text-muted">Analyzed: {analysisDetail.timestamp ? formatDate(analysisDetail.timestamp) : '—'}</span>
                  <span className="text-muted">ID: {analysisDetail.id}</span>
                </section>
              </div>
            ) : (
              <div className="analysis-detail-loading">No analysis data available.</div>
            )}
          </div>
        </div>
      )}

      {/* Bulk Results Summary */}
      {results && (
        <div className="queue-bulk-summary">
          <h3>
            Evaluation Complete — {results.evaluations?.length || 0} items
            {results.evaluations?.[0]?.isDryRun && (
              <span className="queue-dryrun-badge">DRY RUN</span>
            )}
          </h3>
          {results.errors?.length > 0 && (
            <div className="queue-bulk-errors">
              {results.errors.map((err, i) => (
                <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
              ))}
            </div>
          )}
          <p className="text-muted">
            Expand individual rows above to see details and apply changes.
          </p>
        </div>
      )}
    </div>
  );
}
