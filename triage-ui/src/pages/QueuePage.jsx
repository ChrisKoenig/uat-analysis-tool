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

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import * as api from '../api/triageApi';
import { getCachedQueue, setCachedQueue, clearQueueCache } from '../api/queueCache';
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


// ── Fixed columns (always shown, in this order) ────────────────

const FIXED_COLUMNS = [
  { key: 'System.Id',               label: 'ID',             width: 70,  sticky: true, fixed: true },
  { key: 'System.Title',            label: 'Title',          width: 260, fixed: true },
  { key: 'Custom.ROBAnalysisState', label: 'Analysis State', width: 120, fixed: true },
  { key: 'analysis.category',       label: 'Category',       width: 130, fixed: true },
  { key: 'analysis.intent',         label: 'Intent',         width: 130, fixed: true },
];

const FIXED_KEYS = new Set(FIXED_COLUMNS.map((c) => c.key));

/** Default width for dynamically-discovered ADO columns */
const DEFAULT_DYNAMIC_WIDTH = 120;

/** Known column widths / labels (override ADO display names when we know better) */
const COLUMN_OVERRIDES = {
  'System.CommentCount':          { label: '\uD83D\uDCAC', width: 40 },
  'Custom.Customer_Commitment':   { label: 'Commitment', width: 105 },
  'Custom.MilestoneStatus':       { label: 'MS Status', width: 100 },
  'Custom.MilestoneID':          { label: 'Milestone ID', width: 120 },
  'Custom.SolutionArea':          { label: 'Solution Area', width: 140 },
  'Custom.AreaField':             { label: 'Area', width: 100 },
  'Custom.Segment':              { label: 'Segment', width: 150 },
  'Custom.pTriageType':          { label: 'Triage Type', width: 120 },
  'Custom.HelpNeededField':      { label: 'Help Needed', width: 130 },
  'Custom.Opportunity_ID':       { label: 'Opp ID', width: 120 },
  'Custom.OpportunityStage':     { label: 'Opp Stage', width: 120 },
  'Custom.PartnerOneName':       { label: 'Partner', width: 120 },
  'Custom.AssignToCorpDate':     { label: 'Corp Date', width: 100 },
};

/**
 * Build dynamic columns from the ADO query response.
 * Fixed columns appear first (always), then the remaining query columns
 * in the order they appear in the ADO saved query.
 */
function buildColumns(queryColumns) {
  if (!queryColumns || queryColumns.length === 0) {
    return FIXED_COLUMNS;
  }

  const dynamicCols = [];
  for (const qc of queryColumns) {
    // qc can be { referenceName, name } (new) or a plain string (legacy)
    const ref = typeof qc === 'string' ? qc : qc.referenceName;
    const adoName = typeof qc === 'string' ? ref.split('.').pop() : qc.name;

    // Skip columns that are already in the fixed set
    if (FIXED_KEYS.has(ref)) continue;

    const overrides = COLUMN_OVERRIDES[ref] || {};
    dynamicCols.push({
      key: ref,
      label: overrides.label || adoName || ref.split('.').pop(),
      width: overrides.width || DEFAULT_DYNAMIC_WIDTH,
      // Date columns get auto-formatter
      render: ref === 'Custom.AssignToCorpDate'
        ? (v) => v ? formatDate(v) : '\u2014'
        : undefined,
    });
  }

  return [...FIXED_COLUMNS, ...dynamicCols];
}

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
  // ── Team State ───────────────────────────────────────────────
  const [teams, setTeams] = useState([]);
  const [selectedTeamId, setSelectedTeamId] = useState(() =>
    localStorage.getItem('triage_selectedTeamId') || ''
  );

  // ── State ────────────────────────────────────────────────────
  const [items, setItems] = useState([]);
  const [queryName, setQueryName] = useState('');
  const [queryColumns, setQueryColumns] = useState([]);       // columns from ADO query response
  const [loading, setLoading] = useState(true);
  const [loadingStep, setLoadingStep] = useState(null);
  // Shape: { steps: [ { label, status: 'pending'|'active'|'done'|'error', detail? } ] }

  // ── Column Filtering ──────────────────────────────────────
  const [filters, setFilters] = useState({});           // { colKey: Set<string> } — inclusion filter
  const [filterOpen, setFilterOpen] = useState(null);    // { colKey, top, left } | null
  const [filterSearch, setFilterSearch] = useState('');

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
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 20;

  // Analysis state
  const [analysisMap, setAnalysisMap] = useState({});       // { workItemId: { category, intent, ... } }
  const [analysisDetail, setAnalysisDetail] = useState(null);
  const [analysisDetailId, setAnalysisDetailId] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Analysis progress panel state
  const [analysisProgress, setAnalysisProgress] = useState(null);
  // Shape: { total, completed, failed, currentId, items: [ { id, title, status, category, intent, confidence, source, error } ] }

  // ── Derived: active columns for the current query ───────────
  const COLUMNS = useMemo(() => buildColumns(queryColumns), [queryColumns]);

  // ── Column Resize State ────────────────────────────────────
  const [colWidths, setColWidths] = useState(() => {
    try {
      const saved = localStorage.getItem('triage_colWidths');
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    return {};
  });
  const resizeRef = useRef(null);  // tracks active drag { key, startX, startW }
  const loadSeqRef = useRef(0);     // monotonic counter to discard stale loadQueue responses

  /** Merge saved widths with current column defaults (dynamic columns may change) */
  const effectiveColWidths = useMemo(() => {
    const defaults = Object.fromEntries(COLUMNS.map((c) => [c.key, c.width]));
    return { ...defaults, ...colWidths };
  }, [COLUMNS, colWidths]);

  /** Persist column widths to localStorage on change */
  useEffect(() => {
    localStorage.setItem('triage_colWidths', JSON.stringify(colWidths));
  }, [colWidths]);

  /** Number of columns with an active filter */
  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((s) => s.size > 0).length,
    [filters]
  );

  /** Start column resize drag */
  const handleResizeStart = useCallback((e, colKey) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startW = effectiveColWidths[colKey] || 100;
    resizeRef.current = { key: colKey, startX, startW };

    const onMouseMove = (ev) => {
      if (!resizeRef.current) return;
      const diff = ev.clientX - resizeRef.current.startX;
      const newW = Math.max(40, resizeRef.current.startW + diff);
      setColWidths((prev) => ({ ...prev, [resizeRef.current.key]: newW }));
    };
    const onMouseUp = () => {
      resizeRef.current = null;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [effectiveColWidths]);

  /** Reset columns to default widths on double-click */
  const handleResizeReset = useCallback(() => {
    const defaults = Object.fromEntries(COLUMNS.map((c) => [c.key, c.width]));
    setColWidths(defaults);
  }, [COLUMNS]);


  // ── Column Filter Handlers ───────────────────────────────────

  /** Open / close the filter dropdown for a column */
  const openFilter = useCallback((colKey, e) => {
    e.stopPropagation();
    if (filterOpen?.colKey === colKey) {
      setFilterOpen(null);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    setFilterOpen({
      colKey,
      top: rect.bottom + 2,
      left: Math.min(rect.left, window.innerWidth - 260),
    });
    setFilterSearch('');
  }, [filterOpen]);

  /** Toggle a single value in the filter for a column */
  const toggleFilterValue = useCallback((colKey, value) => {
    setFilters((prev) => {
      const next = new Set(prev[colKey] || []);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return { ...prev, [colKey]: next };
    });
  }, []);

  /** Select all visible (search-filtered) values for a column */
  const selectAllFilterValues = useCallback((colKey, values) => {
    setFilters((prev) => {
      const next = new Set(prev[colKey] || []);
      values.forEach((v) => next.add(v));
      return { ...prev, [colKey]: next };
    });
  }, []);

  /** Clear the filter for a single column */
  const clearColumnFilter = useCallback((colKey) => {
    setFilters((prev) => {
      const result = { ...prev };
      delete result[colKey];
      return result;
    });
  }, []);

  /** Clear all column filters */
  const clearAllFilters = useCallback(() => {
    setFilters({});
    setFilterOpen(null);
  }, []);

  /** Close filter dropdown on outside click */
  useEffect(() => {
    if (!filterOpen) return;
    const handle = (e) => {
      if (e.target.closest('.col-filter-dropdown') || e.target.closest('.col-filter-btn')) return;
      setFilterOpen(null);
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [filterOpen]);


  // ── Load Active Triage Teams ─────────────────────────────────

  useEffect(() => {
    (async () => {
      try {
        const data = await api.listTriageTeams('active');
        const sorted = (data.items || []).sort(
          (a, b) => (a.displayOrder ?? 100) - (b.displayOrder ?? 100)
        );
        setTeams(sorted);

        // If no team selected yet and teams exist, auto-select the first
        if (!selectedTeamId && sorted.length > 0) {
          setSelectedTeamId(sorted[0].id);
          localStorage.setItem('triage_selectedTeamId', sorted[0].id);
        }
      } catch {
        // Non-fatal — teams feature may not be configured yet
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** Handle team dropdown change — use per-team cache (no clear needed) */
  const handleTeamChange = useCallback((e) => {
    const teamId = e.target.value;
    setSelectedTeamId(teamId);
    localStorage.setItem('triage_selectedTeamId', teamId);
    // Cache is per-team now — loadQueue will re-run via activeQueryId change
    // and serve from cache if available, so no clearQueueCache() here.
  }, []);

  /** Resolve the ADO query ID to use based on selected team */
  const activeQueryId = useMemo(() => {
    if (!selectedTeamId) return null;
    const team = teams.find((t) => t.id === selectedTeamId);
    return team?.adoQueryId || null;
  }, [selectedTeamId, teams]);


  // ── Load Queue (Saved Query) — with step progress ─────────

  /** Helper: update a specific step in loadingStep state */
  const updateStep = useCallback((idx, updates) => {
    setLoadingStep((prev) => {
      if (!prev) return prev;
      const steps = [...prev.steps];
      steps[idx] = { ...steps[idx], ...updates };
      return { ...prev, steps };
    });
  }, []);

  const loadQueue = useCallback(async (forceRefresh = false) => {
    // Increment sequence — any prior in-flight request becomes stale
    const seq = ++loadSeqRef.current;
    const isStale = () => seq !== loadSeqRef.current;

    // Check cache first (skip on explicit refresh)
    if (!forceRefresh && activeQueryId) {
      const cached = getCachedQueue(activeQueryId);
      if (cached) {
        setItems(cached.items);
        setQueryName(cached.queryName);
        setTotalAvailable(cached.totalAvailable);
        setAnalysisMap(cached.analysisMap);
        if (cached.queryColumns) setQueryColumns(cached.queryColumns);
        setLoading(false);
        setLoadingStep(null);
        return;
      }
    }

    setLoading(true);
    setSelectedIds(new Set());
    setResults(null);
    setAnalysisMap({});
    setAnalysisDetail(null);
    setAnalysisDetailId(null);

    // Initialize loading steps
    const teamObj = teams.find((t) => t.id === selectedTeamId);
    const teamLabel = teamObj?.name || 'team';
    setLoadingStep({
      steps: [
        { label: `Running saved query for ${teamLabel}`, status: 'active', detail: 'Connecting to Azure DevOps…' },
        { label: 'Loading work item details', status: 'pending' },
        { label: 'Loading analysis results', status: 'pending' },
      ],
    });

    let loadedItems = [];
    let loadedQueryName = '';
    let loadedTotal = 0;
    let loadedColumns = [];

    try {
      //  Step 1: Run saved query
      const data = await api.getSavedQueryResults(activeQueryId, 500);
      if (isStale()) return;

      loadedItems = data.items || [];
      loadedQueryName = data.queryName || '';
      loadedTotal = data.totalAvailable || data.count || 0;
      loadedColumns = data.columns || [];

      updateStep(0, {
        status: 'done',
        detail: `Found ${loadedTotal} item${loadedTotal !== 1 ? 's' : ''} in "${loadedQueryName}"`,
      });

      setItems(loadedItems);
      setQueryName(loadedQueryName);
      setTotalAvailable(loadedTotal);
      setQueryColumns(loadedColumns);

      if (data.failedIds?.length > 0) {
        addToast?.(`${data.failedIds.length} items failed to load`, 'warning');
      }

      // Step 2: Details loaded (batch fetch happened server-side)
      updateStep(1, {
        status: 'done',
        detail: `${loadedItems.length} item${loadedItems.length !== 1 ? 's' : ''} hydrated`,
      });

      // Step 3: Batch-fetch analysis status
      let loadedAnalysisMap = {};
      if (loadedItems.length > 0) {
        updateStep(2, { status: 'active', detail: `Checking analysis for ${loadedItems.length} items…` });
        try {
          const ids = loadedItems.map((i) => i.id);
          const analysisData = await api.getAnalysisBatch(ids);
          if (isStale()) return;
          loadedAnalysisMap = analysisData.results || {};
          setAnalysisMap(loadedAnalysisMap);
          const analysisCount = Object.keys(loadedAnalysisMap).length;
          updateStep(2, {
            status: 'done',
            detail: `${analysisCount} item${analysisCount !== 1 ? 's' : ''} have analysis results`,
          });
        } catch {
          updateStep(2, { status: 'done', detail: 'Analysis lookup skipped' });
        }
      } else {
        updateStep(2, { status: 'done', detail: 'No items to analyze' });
      }

      // Persist to per-team cache
      if (activeQueryId && !isStale()) {
        setCachedQueue(activeQueryId, {
          items: loadedItems,
          queryName: loadedQueryName,
          totalAvailable: loadedTotal,
          analysisMap: loadedAnalysisMap,
          queryColumns: loadedColumns,
        });
      }
    } catch (err) {
      if (isStale()) return;
      addToast?.(err.message, 'error');
      setItems([]);
      // Mark current active step as error
      setLoadingStep((prev) => {
        if (!prev) return prev;
        const steps = prev.steps.map((s) =>
          s.status === 'active' ? { ...s, status: 'error', detail: err.message } : s
        );
        return { ...prev, steps };
      });
    } finally {
      if (!isStale()) {
        setLoading(false);
        // Auto-clear loading steps after a brief delay so user sees the "done" state
        setTimeout(() => {
          if (!isStale()) setLoadingStep(null);
        }, 800);
      }
    }
  }, [addToast, activeQueryId, teams, selectedTeamId, updateStep]);

  /** Force-refresh: clears current team's cache and reloads from ADO */
  const refreshQueue = useCallback(() => {
    clearQueueCache(activeQueryId);
    loadQueue(true);
  }, [loadQueue, activeQueryId]);


  useEffect(() => {
    loadQueue();
  }, [loadQueue]);


  // ── Filtered items per tab ───────────────────────────────────

  const analysisItems = useMemo(() => items.filter(isAnalysisItem), [items]);
  const triageItems   = useMemo(() => items.filter(isTriageItem), [items]);
  const tabItems      = activeTab === 'analysis' ? analysisItems : triageItems;


  // ── Column Filter Logic ──────────────────────────────────────

  /** Unique display values for the currently-open filter column */
  const filterValues = useMemo(() => {
    if (!filterOpen) return [];
    const colKey = filterOpen.colKey;
    const vals = new Set();
    for (const item of tabItems) {
      let v;
      if (colKey.startsWith('analysis.')) {
        v = analysisMap[String(item.id)]?.[colKey.replace('analysis.', '')];
      } else {
        v = item.fields?.[colKey];
      }
      vals.add(v === undefined || v === null || v === '' ? '(Blank)' : String(v));
    }
    return [...vals].sort((a, b) => a.localeCompare(b));
  }, [filterOpen, tabItems, analysisMap]);

  /** Filter values narrowed by the search box inside the dropdown */
  const visibleFilterValues = useMemo(() => {
    if (!filterSearch) return filterValues;
    const q = filterSearch.toLowerCase();
    return filterValues.filter((v) => v.toLowerCase().includes(q));
  }, [filterValues, filterSearch]);

  /** Apply column filters (additive / AND across columns) */
  const filteredItems = useMemo(() => {
    const active = Object.entries(filters).filter(([, s]) => s.size > 0);
    if (active.length === 0) return tabItems;
    return tabItems.filter((item) =>
      active.every(([colKey, allowed]) => {
        let v;
        if (colKey.startsWith('analysis.')) {
          v = analysisMap[String(item.id)]?.[colKey.replace('analysis.', '')];
        } else {
          v = item.fields?.[colKey];
        }
        const display = v === undefined || v === null || v === '' ? '(Blank)' : String(v);
        return allowed.has(display);
      })
    );
  }, [tabItems, filters, analysisMap]);


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
    if (!sortCol) return filteredItems;
    return [...filteredItems].sort((a, b) => {
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
  }, [filteredItems, sortCol, sortDir, analysisMap]);

  // ── Pagination ───────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(sortedItems.length / PAGE_SIZE));

  // Reset to page 1 when tab, sort, filter, or items change
  useEffect(() => { setCurrentPage(1); }, [activeTab, sortCol, sortDir, filteredItems.length]);

  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return sortedItems.slice(start, start + PAGE_SIZE);
  }, [sortedItems, currentPage, PAGE_SIZE]);


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
    if (selectedIds.size === filteredItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredItems.map((i) => i.id)));
    }
  };

  // Clear selection when switching tabs
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSelectedIds(new Set());
    setResults(null);
    setExpandedId(null);
    setCurrentPage(1);
    setFilters({});
    setFilterOpen(null);
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

    clearQueueCache(); // data changed — invalidate
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
      clearQueueCache(); // data changed — invalidate
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
      clearQueueCache(); // ADO was written — stale cache
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

    // Auto-detect date strings from dynamic columns (ISO 8601 pattern)
    if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(val)) {
      return formatDate(val);
    }

    return String(val);
  };


  // ── Busy state for any action ────────────────────────────────

  const busy = loading || evaluating || analyzing || settingState;
  const showSimpleOverlay = (evaluating || settingState) && !analyzing;
  const simpleOverlayMsg = evaluating
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
          {/* Team Selector */}
          {teams.length > 0 ? (
            <select
              className="team-selector"
              value={selectedTeamId}
              onChange={handleTeamChange}
              title="Select triage team"
            >
              {!selectedTeamId && <option value="">— Select Team —</option>}
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          ) : queryName ? (
            <span className="queue-query-name" title={queryName}>
              {queryName}
            </span>
          ) : null}
          <button
            className="btn btn-secondary"
            onClick={refreshQueue}
            disabled={busy}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* ── Toolbar ───────────────────────────────────────────────── */}
      <div className="queue-action-bar">
        <span className="queue-count">
          {loading ? 'Loading\u2026' : (
            <>
              {activeFilterCount > 0
                ? `${filteredItems.length} of ${tabItems.length} items (filtered)`
                : `${tabItems.length} items`
              }
              {totalAvailable > items.length && ` of ${totalAvailable} total`}
              {selectedIds.size > 0 && ` \xb7 ${selectedIds.size} selected`}
              {totalPages > 1 && ` \xb7 Page ${currentPage} of ${totalPages}`}
            </>
          )}
        </span>
        {activeFilterCount > 0 && (
          <button
            className="btn btn-toolbar btn-clear-filters"
            onClick={clearAllFilters}
            title="Remove all column filters"
          >
            \u2715 Clear {activeFilterCount} Filter{activeFilterCount !== 1 ? 's' : ''}
          </button>
        )}
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

      {/* Step-by-step Loading Progress (queue load) */}
      {loadingStep && (
        <div className="queue-loading-steps">
          <div className="queue-loading-steps-inner">
            <div className="queue-loading-header">
              <div className="queue-spinner queue-spinner-sm" />
              <span>Loading Triage Queue</span>
            </div>
            <ol className="queue-steps-list">
              {loadingStep.steps.map((step, idx) => (
                <li key={idx} className={`queue-step queue-step-${step.status}`}>
                  <span className="queue-step-icon">
                    {step.status === 'done' && '\u2713'}
                    {step.status === 'error' && '\u2717'}
                    {step.status === 'active' && ''}
                    {step.status === 'pending' && '\u00B7'}
                  </span>
                  <span className="queue-step-label">{step.label}</span>
                  {step.detail && (
                    <span className="queue-step-detail">{step.detail}</span>
                  )}
                  {step.status === 'active' && (
                    <span className="queue-step-spinner" />
                  )}
                </li>
              ))}
            </ol>
          </div>
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
                  checked={filteredItems.length > 0 && selectedIds.size === filteredItems.length}
                  onChange={toggleSelectAll}
                  disabled={filteredItems.length === 0}
                />
              </th>
              {COLUMNS.map((col) => {
                const isFiltered = filters[col.key]?.size > 0;
                return (
                  <th
                    key={col.key}
                    className={`queue-col-header ${isFiltered ? 'col-filtered' : ''}`}
                    style={{ width: effectiveColWidths[col.key] || col.width, minWidth: 40 }}
                  >
                    <div className="col-header-inner">
                      <span
                        className="col-header-label"
                        onClick={() => handleSort(col.key)}
                        title={`Sort by ${col.label}`}
                      >
                        {col.label}
                        {sortCol === col.key && (
                          <span className="sort-arrow">{sortDir === 'asc' ? ' \u25B2' : ' \u25BC'}</span>
                        )}
                      </span>
                      <button
                        className={`col-filter-btn ${isFiltered ? 'active' : ''}`}
                        onClick={(e) => openFilter(col.key, e)}
                        title={isFiltered ? 'Filter active \u2014 click to edit' : `Filter ${col.label}`}
                      >
                        \u25BE
                      </button>
                    </div>
                    <div
                      className="col-resize-handle"
                      onMouseDown={(e) => handleResizeStart(e, col.key)}
                      onDoubleClick={handleResizeReset}
                    />
                  </th>
                );
              })}
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
              paginatedItems.map((item) => {
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
                      {COLUMNS.map((col) => {
                        const w = effectiveColWidths[col.key] || col.width;
                        return (
                          <td
                            key={col.key}
                            className={`queue-cell ${col.sticky ? 'queue-col-id' : ''}`}
                            style={{ width: w, minWidth: 40 }}
                          >
                            {renderCell(col, item)}
                          </td>
                        );
                      })}
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

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="queue-pagination">
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(1)}
            title="First page"
          >
            ⏮
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => p - 1)}
            title="Previous page"
          >
            ◀
          </button>
          <span className="queue-pagination-info">
            Page {currentPage} of {totalPages}
            <span className="queue-pagination-range">
              {' '}({(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, sortedItems.length)} of {sortedItems.length})
            </span>
          </span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => p + 1)}
            title="Next page"
          >
            ▶
          </button>
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(totalPages)}
            title="Last page"
          >
            ⏭
          </button>
        </div>
      )}

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

      {/* ── Column Filter Dropdown (portal to body to avoid table overflow clip) */}
      {filterOpen && createPortal(
        <div
          className="col-filter-dropdown"
          style={{ top: filterOpen.top, left: filterOpen.left }}
        >
          {/* Sort section */}
          <div className="cfd-sort">
            <button
              className={`cfd-sort-btn ${sortCol === filterOpen.colKey && sortDir === 'asc' ? 'active' : ''}`}
              onClick={() => { setSortCol(filterOpen.colKey); setSortDir('asc'); }}
            >
              ▲ Sort A → Z
            </button>
            <button
              className={`cfd-sort-btn ${sortCol === filterOpen.colKey && sortDir === 'desc' ? 'active' : ''}`}
              onClick={() => { setSortCol(filterOpen.colKey); setSortDir('desc'); }}
            >
              ▼ Sort Z → A
            </button>
          </div>
          <div className="cfd-divider" />
          {/* Search */}
          <div className="cfd-search">
            <input
              placeholder="Search values…"
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          </div>
          {/* Select all / Clear */}
          <div className="cfd-bulk">
            <label className="cfd-select-all">
              <input
                type="checkbox"
                checked={visibleFilterValues.length > 0 && visibleFilterValues.every((v) => filters[filterOpen.colKey]?.has(v))}
                ref={(el) => {
                  if (el) {
                    const someChecked = visibleFilterValues.some((v) => filters[filterOpen.colKey]?.has(v));
                    const allChecked = visibleFilterValues.length > 0 && visibleFilterValues.every((v) => filters[filterOpen.colKey]?.has(v));
                    el.indeterminate = someChecked && !allChecked;
                  }
                }}
                onChange={() => {
                  const allChecked = visibleFilterValues.every((v) => filters[filterOpen.colKey]?.has(v));
                  if (allChecked) {
                    // Deselect all visible
                    setFilters((prev) => {
                      const next = new Set(prev[filterOpen.colKey] || []);
                      visibleFilterValues.forEach((v) => next.delete(v));
                      return { ...prev, [filterOpen.colKey]: next };
                    });
                  } else {
                    selectAllFilterValues(filterOpen.colKey, visibleFilterValues);
                  }
                }}
              />
              <span>Select All</span>
            </label>
            {filters[filterOpen.colKey]?.size > 0 && (
              <button className="cfd-clear-btn" onClick={() => clearColumnFilter(filterOpen.colKey)}>
                Clear Filter
              </button>
            )}
          </div>
          <div className="cfd-divider" />
          {/* Value list */}
          <div className="cfd-values">
            {visibleFilterValues.map((val) => (
              <label key={val} className="cfd-value-item">
                <input
                  type="checkbox"
                  checked={filters[filterOpen.colKey]?.has(val) ?? false}
                  onChange={() => toggleFilterValue(filterOpen.colKey, val)}
                />
                <span title={val}>{val}</span>
              </label>
            ))}
            {visibleFilterValues.length === 0 && (
              <div className="cfd-empty">No matching values</div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
