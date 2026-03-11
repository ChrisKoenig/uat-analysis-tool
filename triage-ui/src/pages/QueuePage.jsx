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
 *
 * FR-1999: Analysis detail blade uses linear scrolling layout.
 *   All section headers always render; empty fields show "No data"
 *   placeholders for consistent layout across LLM and pattern items.
 *   (Tabs were tested for the blade but reverted per user feedback.)
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import * as api from '../api/triageApi';
import { getCachedQueue, setCachedQueue, clearQueueCache, updateCachedAnalysis } from '../api/queueCache';
import { formatDate, truncate } from '../utils/helpers';
import ServiceTreeRouting from '../components/ServiceTreeRouting';
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
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [showAllQueueRules, setShowAllQueueRules] = useState(false);
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

  // Graph user info cache + blade state (FR-1998)
  // Cache: email → { data, loading, promise } — persists across blade open/close
  const graphCacheRef = useRef(new Map());
  const [graphUser, setGraphUser] = useState(null);       // current blade's resolved user
  const [graphUserLoading, setGraphUserLoading] = useState(false);

  // Collapsible blade section state — keys that are currently collapsed
  const [collapsedSections, setCollapsedSections] = useState(new Set(['entities']));
  const toggleSection = (key) =>
    setCollapsedSections(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // Analysis progress panel state
  const [analysisProgress, setAnalysisProgress] = useState(null);
  // Shape: { total, completed, failed, currentId, items: [ { id, title, status, category, intent, confidence, source, error } ] }

  // ── ENG-003: Disagreement resolution state ──────────────────
  const [bladeDisagreement, setBladeDisagreement] = useState({});
  // bladeDisagreement[workItemId] = { choice, neitherCategory, neitherIntent, notes, submitting, submitted }
  const getBladeDs = (wid) => bladeDisagreement[wid] || { choice: null, neitherCategory: '', neitherIntent: '', notes: '', submitting: false, submitted: false };
  const updateBladeDs = (wid, patch) =>
    setBladeDisagreement(prev => ({ ...prev, [wid]: { ...getBladeDs(wid), ...patch } }));

  const handleBladeSubmitSignal = async (wid) => {
    const ds = getBladeDs(wid);
    if (!ds.choice || !analysisDetail) return;
    updateBladeDs(wid, { submitting: true });
    try {
      await api.submitTrainingSignal({
        workItemId: String(wid),
        llmCategory: analysisDetail.category || '',
        llmIntent: analysisDetail.intent || '',
        patternCategory: analysisDetail.patternCategory || '',
        patternIntent: analysisDetail.patternIntent || '',
        humanChoice: ds.choice,
        resolvedCategory: ds.choice === 'neither' ? ds.neitherCategory : '',
        resolvedIntent: ds.choice === 'neither' ? ds.neitherIntent : '',
        notes: ds.notes,
      });
      updateBladeDs(wid, { submitting: false, submitted: true });
    } catch (err) {
      updateBladeDs(wid, { submitting: false });
    }
  };

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

      // FR-1998: Prefetch Graph user data for all requestor emails in background
      (() => {
        const cache = graphCacheRef.current;
        const emails = new Set();
        for (const it of loadedItems) {
          const em = it.fields?.['Custom.Requestors']
            || it.fields?.['_requestorEmail']
            || it.fields?.['_createdByEmail']
            || it.fields?.['Custom.Requestor']
            || it.fields?.['System.CreatedBy']
            || '';
          if (em && !cache.has(em)) emails.add(em);
        }
        // Fire-and-forget: fetch each unique email with slight stagger to avoid burst
        let delay = 0;
        for (const email of emails) {
          cache.set(email, { data: null, loading: true, promise: null });
          const entry = cache.get(email);
          entry.promise = new Promise(resolve => setTimeout(resolve, delay))
            .then(() => api.getGraphUser(email))
            .then(info => { entry.data = info; entry.loading = false; })
            .catch(() => { entry.data = null; entry.loading = false; });
          delay += 80; // 80ms stagger between requests
        }
      })();

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

  /**
   * Convert a raw cell value to its display string, matching what renderCell shows.
   * This keeps the filter dropdown values consistent with the grid text.
   */
  const displayValue = useCallback((colKey, rawVal) => {
    if (rawVal === undefined || rawVal === null || rawVal === '') return '(Blank)';

    // Analysis columns: underscores → spaces
    if (colKey === 'analysis.category' || colKey === 'analysis.intent') {
      return String(rawVal).replace(/_/g, ' ');
    }

    // ROBAnalysisState: blank → "Pending"
    if (colKey === 'Custom.ROBAnalysisState' && !rawVal) return 'Pending';

    // Date strings → formatted
    if (typeof rawVal === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(rawVal)) {
      return formatDate(rawVal);
    }

    return String(rawVal);
  }, []);

  /** Read the raw value for a column from an item */
  const rawCellValue = useCallback((colKey, item) => {
    if (colKey.startsWith('analysis.')) {
      return analysisMap[String(item.id)]?.[colKey.replace('analysis.', '')];
    }
    return item.fields?.[colKey];
  }, [analysisMap]);

  /** Unique display values for the currently-open filter column */
  const filterValues = useMemo(() => {
    if (!filterOpen) return [];
    const colKey = filterOpen.colKey;
    const vals = new Set();
    for (const item of tabItems) {
      vals.add(displayValue(colKey, rawCellValue(colKey, item)));
    }
    return [...vals].sort((a, b) => a.localeCompare(b));
  }, [filterOpen, tabItems, displayValue, rawCellValue]);

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
        return allowed.has(displayValue(colKey, rawCellValue(colKey, item)));
      })
    );
  }, [tabItems, filters, displayValue, rawCellValue]);


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
    setExpandedIds(new Set());
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

    // ── Immediate feedback: disable button + show progress panel ──
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

    setAnalyzing(true);  // disable button immediately (prevents double-click)
    setAnalysisProgress({
      total: ids.length,
      completed: 0,
      failed: 0,
      currentId: null,
      items: progressItems,
      engineNote: null,  // populated after status check
    });

    // ── Check AI availability (non-blocking — no confirm dialog) ──
    let aiNote = null;
    try {
      const status = await api.getAnalysisEngineStatus();
      if (!status.aiAvailable) {
        aiNote = `AI engine unavailable (${status.mode}) — using pattern matching`;
        addToast?.(aiNote, 'warning');
      }
    } catch {
      aiNote = 'Unable to check AI engine — proceeding with available mode';
      addToast?.(aiNote, 'warning');
    }

    if (aiNote) {
      setAnalysisProgress((prev) => prev ? { ...prev, engineNote: aiNote } : prev);
    }

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

    // Refresh analysis map for all processed items and update the cache
    // (analysis only writes to Cosmos — ADO items are unchanged, so we
    //  update the cached analysisMap rather than clearing the entire cache,
    //  which would force a slow full ADO re-query.)
    try {
      const analysisData = await api.getAnalysisBatch(ids);
      const updates = analysisData.results || {};
      setAnalysisMap((prev) => ({ ...prev, ...updates }));
      updateCachedAnalysis(activeQueryId, updates);
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

      // Check for individual failures in the response
      const succeeded = (data.results || []).filter(r => r.success).map(r => r.workItemId);
      const failedCount = (data.results || []).filter(r => !r.success).length;

      if (failedCount > 0) {
        addToast?.(
          `${succeeded.length} updated, ${failedCount} failed — check ADO permissions`,
          'warning'
        );
      } else {
        addToast?.(
          successMsg || `Set ${succeeded.length} item(s) to "${newState}"`,
          'success'
        );
      }

      // Update local item fields only for items that succeeded
      const successSet = new Set(succeeded);
      setItems((prev) => {
        const updated = prev.map((item) =>
          successSet.has(item.id)
            ? { ...item, fields: { ...item.fields, 'Custom.ROBAnalysisState': newState } }
            : item
        );
        // Persist updated items to cache so navigating away and back keeps the state
        if (activeQueryId) {
          setCachedQueue(activeQueryId, {
            items: updated,
            queryName,
            totalAvailable,
            analysisMap,
            queryColumns,
          });
        }
        return updated;
      });
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

      // Auto-expand all rows that received results
      const evalIds = new Set((data.evaluations || []).map((e) => e.workItemId));
      setExpandedIds(evalIds);

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
      clearQueueCache(activeQueryId); // ADO fields changed — invalidate this query's cache
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
      setGraphUser(null);
      return;
    }
    setAnalysisDetailId(workItemId);
    setLoadingDetail(true);
    setGraphUser(null);
    setGraphUserLoading(false);
    try {
      const detail = await api.getAnalysisDetail(workItemId);
      setAnalysisDetail(detail);

      // FR-1998: Resolve Graph user from cache or fetch on-demand
      const item = items.find(i => i.id === workItemId);
      const email = item?.fields?.['Custom.Requestors']
        || item?.fields?.['_requestorEmail']
        || item?.fields?.['_createdByEmail']
        || item?.fields?.['Custom.Requestor']
        || item?.fields?.['System.CreatedBy']
        || '';
      if (email) {
        const cache = graphCacheRef.current;
        const cached = cache.get(email);
        if (cached?.data) {
          // Cache hit — instant
          setGraphUser(cached.data);
          setGraphUserLoading(false);
        } else if (cached?.promise) {
          // Prefetch in progress — wait for it
          setGraphUserLoading(true);
          cached.promise
            .then(() => setGraphUser(cached.data))
            .finally(() => setGraphUserLoading(false));
        } else {
          // Cache miss — fetch on-demand and cache
          setGraphUserLoading(true);
          const entry = { data: null, loading: true, promise: null };
          cache.set(email, entry);
          entry.promise = api.getGraphUser(email)
            .then(info => { entry.data = info; entry.loading = false; setGraphUser(info); })
            .catch(() => { entry.data = null; entry.loading = false; setGraphUser(null); })
            .finally(() => setGraphUserLoading(false));
        }
      }
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
            {'\u2715'} Clear {activeFilterCount} Filter{activeFilterCount !== 1 ? 's' : ''}
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

            {/* Engine note (shown when AI is unavailable) */}
            {analysisProgress.engineNote && (
              <div className="analysis-engine-note">
                ⚠️ {analysisProgress.engineNote}
              </div>
            )}

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
                        {'\u25BE'}
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
                const isExpanded = expandedIds.has(item.id);
                return (
                  <React.Fragment key={item.id}>
                    <tr
                      className={`queue-row ${selectedIds.has(item.id) ? 'selected' : ''} ${evalResult ? 'has-result' : ''} ${isExpanded ? 'expanded' : ''}`}
                      onClick={() => {
                        if (evalResult) {
                          // When results exist, row click toggles expansion
                          setExpandedIds((prev) => {
                            const next = new Set(prev);
                            if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                            return next;
                          });
                        } else {
                          toggleSelect(item.id);
                        }
                      }}
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
                            onClick={() => setExpandedIds((prev) => {
                              const next = new Set(prev);
                              if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                              return next;
                            })}
                          >
                            {expandedIds.has(item.id) ? '\u25BC' : '\u25B6'} Results
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
                    {evalResult && expandedIds.has(item.id) && (
                      <tr className="queue-result-row">
                        <td colSpan={colCount}>
                          <div className="queue-result-detail">
                            <div className="queue-result-summary">
                              <span className={`queue-analysis-badge analysis-${evalResult.analysisState?.replace(/\s/g, '-').toLowerCase()}`}>
                                {evalResult.analysisState}
                              </span>
                              {evalResult.matchedTrigger && (
                                <span className="queue-result-tag" title={evalResult.matchedTrigger}>⚡ {evalResult.triggerNames?.[evalResult.matchedTrigger] || evalResult.matchedTrigger}</span>
                              )}
                              {evalResult.appliedRoute && (
                                <span className="queue-result-tag" title={evalResult.appliedRoute}>🔀 {evalResult.routeNames?.[evalResult.appliedRoute] || evalResult.appliedRoute}</span>
                              )}
                            </div>

                            {/* Rule Results — FR-2055: show fired only by default */}
                            {(() => {
                              const allEntries = Object.entries(evalResult.ruleResults || {});
                              const firedEntries = allEntries.filter(([, r]) => r);
                              const displayEntries = showAllQueueRules ? allEntries : firedEntries;
                              return (
                                <div className="queue-result-rules">
                                  <div className="queue-rules-header">
                                    <span>Rules Fired ({firedEntries.length} of {allEntries.length})</span>
                                    {allEntries.length > firedEntries.length && (
                                      <button
                                        className="evaluate-toggle-rules"
                                        onClick={() => setShowAllQueueRules(prev => !prev)}
                                      >
                                        {showAllQueueRules ? 'Show fired only' : `Show all ${allEntries.length}`}
                                      </button>
                                    )}
                                  </div>
                                  {displayEntries.map(([ruleId, passed]) => (
                                    <span
                                      key={ruleId}
                                      className={`queue-rule-chip ${passed ? 'rule-true' : 'rule-false'}`}
                                      title={ruleId}
                                    >
                                      {passed ? '\u2713' : '\u2717'} {evalResult.ruleNames?.[ruleId] || ruleId}
                                    </span>
                                  ))}
                                </div>
                              );
                            })()}

                            {/* Field Changes */}
                            {Object.keys(evalResult.fieldsChanged || {}).length > 0 && (
                              <table className="queue-changes-table">
                                <thead>
                                  <tr><th>Field</th><th>From</th><th>To</th></tr>
                                </thead>
                                <tbody>
                                  {Object.entries(evalResult.fieldsChanged).map(([field, change]) => {
                                    const renderVal = (v) => {
                                      if (v == null) return '\u2014';
                                      if (typeof v === 'object') {
                                        if (v.displayName) return v.displayName;
                                        if (v.name) return v.name;
                                        const s = JSON.stringify(v);
                                        return s.length > 200 ? s.slice(0, 200) + '\u2026' : s;
                                      }
                                      return String(v);
                                    };
                                    return (
                                      <tr key={field}>
                                        <td><code className="field-ref">{field}</code></td>
                                        <td className="text-muted">{renderVal(change.from)}</td>
                                        <td><strong>{renderVal(change.to)}</strong></td>
                                      </tr>
                                    );
                                  })}
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
        <div className="analysis-detail-overlay" onClick={() => { setAnalysisDetailId(null); setAnalysisDetail(null); setGraphUser(null); }}>
          <div className="analysis-detail-panel" onClick={(e) => e.stopPropagation()}>
            <div className="analysis-detail-header">
              <h3>Analysis Details — #{analysisDetailId}</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => { setAnalysisDetailId(null); setAnalysisDetail(null); setGraphUser(null); }}>
                {'✕'}
              </button>
            </div>
            {loadingDetail ? (
              <div className="analysis-detail-loading">Loading analysis...</div>
            ) : analysisDetail ? (
              <div className="analysis-detail-body">
                {/* FR-1999 + FR-1998: Collapsible accordion sections.
                    Summary (confidence + classification) always visible.
                    Remaining sections are collapsible to reduce scrolling.
                    Requestor card powered by Graph user lookup (FR-1998). */}

                {/* AI Availability Warning */}
                {analysisDetail.aiAvailable === false && (
                  <div className="analysis-ai-warning">
                    {'⚠️'} AI engine was not available — results are pattern-matching only
                    {analysisDetail.aiError && <span className="ai-error-detail"> ({analysisDetail.aiError})</span>}
                  </div>
                )}

                {/* ═══ SUMMARY (always visible) ═══ */}

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
                      <span className="queue-badge analysis-category-badge">{(analysisDetail.category || '').replace(/_/g, ' ') || <span className="no-data">No data</span>}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Intent</label>
                      <span>{(analysisDetail.intent || '').replace(/_/g, ' ') || <span className="no-data">No data</span>}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Business Impact</label>
                      {analysisDetail.businessImpact ? (
                        <span className={`impact-badge impact-${(analysisDetail.businessImpact || '').toLowerCase()}`}>
                          {analysisDetail.businessImpact}
                        </span>
                      ) : <span className="no-data">No data</span>}
                    </div>
                    <div className="analysis-field">
                      <label>Technical Complexity</label>
                      <span>{analysisDetail.technicalComplexity || <span className="no-data">No data</span>}</span>
                    </div>
                    <div className="analysis-field">
                      <label>Urgency</label>
                      {analysisDetail.urgencyLevel ? (
                        <span className={`impact-badge impact-${(analysisDetail.urgencyLevel || '').toLowerCase()}`}>
                          {analysisDetail.urgencyLevel}
                        </span>
                      ) : <span className="no-data">No data</span>}
                    </div>
                  </div>
                </section>

                {/* ═══ REQUESTOR (FR-1998 — collapsible, open by default) ═══ */}
                <div className={`blade-accordion ${collapsedSections.has('requestor') ? 'collapsed' : ''}`}>
                  <button type="button" className="blade-accordion-toggle" onClick={() => toggleSection('requestor')}>
                    <span className="blade-accordion-chevron">{collapsedSections.has('requestor') ? '▸' : '▾'}</span>
                    <h4>👤 Requestor</h4>
                  </button>
                  {!collapsedSections.has('requestor') && (
                    <div className="blade-accordion-body">
                      {graphUserLoading ? (
                        <p className="no-data">Loading requestor info…</p>
                      ) : graphUser ? (
                        <div className="requestor-card">
                          <div className="requestor-avatar">{(graphUser.displayName || '?')[0].toUpperCase()}</div>
                          <div className="requestor-info">
                            <span className="requestor-name">{graphUser.displayName}</span>
                            <span className="requestor-detail">{graphUser.jobTitle}</span>
                            <span className="requestor-detail">{graphUser.department}</span>
                            {graphUser.email && <span className="requestor-email">{graphUser.email}</span>}
                          </div>
                        </div>
                      ) : (
                        <p className="no-data">No requestor data available</p>
                      )}
                    </div>
                  )}
                </div>

                {/* ═══ SERVICETREE ROUTING (collapsible, open by default) ═══ */}
                <div className={`blade-accordion ${collapsedSections.has('routing') ? 'collapsed' : ''}`}>
                  <button type="button" className="blade-accordion-toggle" onClick={() => toggleSection('routing')}>
                    <span className="blade-accordion-chevron">{collapsedSections.has('routing') ? '▸' : '▾'}</span>
                    <h4>🌳 ServiceTree Routing</h4>
                  </button>
                  {!collapsedSections.has('routing') && (
                    <div className="blade-accordion-body">
                      <ServiceTreeRouting
                        detail={analysisDetail}
                        workItemId={analysisDetailId}
                        onSaved={(updatedFields) => {
                          setAnalysisDetail(prev => ({ ...prev, ...updatedFields }));
                        }}
                      />
                    </div>
                  )}
                </div>

                {/* ═══ AI REASONING (collapsible, open by default) ═══ */}
                <div className={`blade-accordion ${collapsedSections.has('reasoning') ? 'collapsed' : ''}`}>
                  <button type="button" className="blade-accordion-toggle" onClick={() => toggleSection('reasoning')}>
                    <span className="blade-accordion-chevron">{collapsedSections.has('reasoning') ? '▸' : '▾'}</span>
                    <h4>{(analysisDetail.source || '').includes('llm') || (analysisDetail.source || '').includes('hybrid')
                      ? '🧠 AI Classification Reasoning' : '🧠 Classification Reasoning'}</h4>
                  </button>
                  {!collapsedSections.has('reasoning') && (
                    <div className="blade-accordion-body">
                      {analysisDetail.reasoning
                        ? <p className="analysis-summary-text" style={{ whiteSpace: 'pre-wrap' }}>
                            {typeof analysisDetail.reasoning === 'object'
                              ? JSON.stringify(analysisDetail.reasoning, null, 2)
                              : analysisDetail.reasoning}
                          </p>
                        : <p className="no-data">No data</p>}
                    </div>
                  )}
                </div>

                {/* ═══ PATTERN & DISAGREEMENT (collapsible, open by default when present) ═══ */}
                {analysisDetail.patternCategory && (
                  <div className={`blade-accordion ${collapsedSections.has('pattern') ? 'collapsed' : ''}`}>
                    <button type="button" className="blade-accordion-toggle" onClick={() => toggleSection('pattern')}>
                      <span className="blade-accordion-chevron">{collapsedSections.has('pattern') ? '▸' : '▾'}</span>
                      <h4>📊 Pattern Comparison</h4>
                      {!analysisDetail.agreement && <span className="blade-accordion-badge badge-warn">Disagreement</span>}
                    </button>
                    {!collapsedSections.has('pattern') && (
                      <div className="blade-accordion-body">
                        <div className="analysis-field-grid">
                          <div className="analysis-field">
                            <label>Pattern Category</label>
                            <span className="queue-badge analysis-category-badge">{(analysisDetail.patternCategory || '').replace(/_/g, ' ')}</span>
                          </div>
                          <div className="analysis-field">
                            <label>Pattern Confidence</label>
                            <span>{((analysisDetail.patternConfidence || 0) * 100).toFixed(0)}%</span>
                          </div>
                          <div className="analysis-field">
                            <label>Agreement</label>
                            <span>{analysisDetail.agreement ? '✅ LLM & Pattern agree' : '⚠️ Disagreement'}</span>
                          </div>
                        </div>

                        {/* ENG-003: Disagreement Resolution */}
                        {!analysisDetail.agreement && analysisDetailId && (() => {
                          const ds = getBladeDs(analysisDetailId);
                          if (ds.submitted) {
                            return (
                              <section className="analysis-section" style={{ background: '#f0faf0', borderRadius: 8, padding: 12, marginTop: 12 }}>
                                <h4>✅ Training Signal Submitted</h4>
                                <p className="no-data" style={{ color: '#555' }}>
                                  You selected <strong>{ds.choice === 'llm' ? 'LLM' : ds.choice === 'pattern' ? 'Pattern' : 'Neither'}</strong>.
                                </p>
                              </section>
                            );
                          }
                          return (
                            <section className="analysis-section" style={{ border: '2px solid #e67e22', borderRadius: 8, padding: 12, background: '#fef9f3', marginTop: 12 }}>
                              <h4>🎓 Resolve Disagreement</h4>
                              <p style={{ margin: '4px 0 10px', color: '#555', fontSize: 13 }}>
                                LLM says <strong>{(analysisDetail.category || '').replace(/_/g, ' ')}</strong>,
                                Pattern says <strong>{(analysisDetail.patternCategory || '').replace(/_/g, ' ')}</strong>.
                                Which is correct?
                              </p>
                              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                <button
                                  className={`btn btn-sm ${ds.choice === 'llm' ? 'btn-primary' : 'btn-ghost'}`}
                                  onClick={() => updateBladeDs(analysisDetailId, { choice: 'llm' })}
                                  disabled={ds.submitting}
                                >🧠 LLM</button>
                                <button
                                  className={`btn btn-sm ${ds.choice === 'pattern' ? 'btn-primary' : 'btn-ghost'}`}
                                  onClick={() => updateBladeDs(analysisDetailId, { choice: 'pattern' })}
                                  disabled={ds.submitting}
                                >📊 Pattern</button>
                                <button
                                  className={`btn btn-sm ${ds.choice === 'neither' ? 'btn-primary' : 'btn-ghost'}`}
                                  onClick={() => updateBladeDs(analysisDetailId, { choice: 'neither' })}
                                  disabled={ds.submitting}
                                >❌ Neither</button>
                              </div>
                              {ds.choice === 'neither' && (
                                <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                  <input
                                    type="text"
                                    placeholder="Correct category..."
                                    value={ds.neitherCategory}
                                    onChange={(e) => updateBladeDs(analysisDetailId, { neitherCategory: e.target.value })}
                                    style={{ padding: '3px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: 13, width: 160 }}
                                  />
                                  <input
                                    type="text"
                                    placeholder="Correct intent..."
                                    value={ds.neitherIntent}
                                    onChange={(e) => updateBladeDs(analysisDetailId, { neitherIntent: e.target.value })}
                                    style={{ padding: '3px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: 13, width: 160 }}
                                  />
                                </div>
                              )}
                              {ds.choice && (
                                <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
                                  <input
                                    type="text"
                                    placeholder="Notes (optional)..."
                                    value={ds.notes}
                                    onChange={(e) => updateBladeDs(analysisDetailId, { notes: e.target.value })}
                                    style={{ flex: 1, padding: '3px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: 13 }}
                                    disabled={ds.submitting}
                                  />
                                  <button
                                    className="btn btn-sm btn-primary"
                                    onClick={() => handleBladeSubmitSignal(analysisDetailId)}
                                    disabled={ds.submitting || (ds.choice === 'neither' && !ds.neitherCategory)}
                                  >
                                    {ds.submitting ? '...' : 'Submit'}
                                  </button>
                                </div>
                              )}
                            </section>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}

                {/* ═══ DOMAIN ENTITIES (collapsible, collapsed by default) ═══ */}
                <div className={`blade-accordion ${collapsedSections.has('entities') ? 'collapsed' : ''}`}>
                  <button type="button" className="blade-accordion-toggle" onClick={() => toggleSection('entities')}>
                    <span className="blade-accordion-chevron">{collapsedSections.has('entities') ? '▸' : '▾'}</span>
                    <h4>🏷️ Domain Entities</h4>
                    {(() => {
                      const total = (analysisDetail.keyConcepts?.length || 0)
                        + (analysisDetail.azureServices?.length || 0)
                        + (analysisDetail.technologies?.length || 0)
                        + (analysisDetail.technicalAreas?.length || 0)
                        + (analysisDetail.regions?.length || 0)
                        + (analysisDetail.complianceFrameworks?.length || 0)
                        + (analysisDetail.detectedProducts?.length || 0);
                      return total > 0
                        ? <span className="blade-accordion-badge">{total} tags</span>
                        : null;
                    })()}
                  </button>
                  {!collapsedSections.has('entities') && (
                    <div className="blade-accordion-body blade-entities-grid">
                      {/* Key Concepts */}
                      <div className="entity-group">
                        <label>Key Concepts</label>
                        {analysisDetail.keyConcepts?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.keyConcepts.map((c, i) => <span key={i} className="analysis-tag tag-concept">{c}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Azure & Modern Work Services */}
                      <div className="entity-group">
                        <label>Azure & Modern Work Services</label>
                        {analysisDetail.azureServices?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.azureServices.map((s, i) => <span key={i} className="analysis-tag tag-service">{s}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Technologies */}
                      <div className="entity-group">
                        <label>Technologies</label>
                        {analysisDetail.technologies?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.technologies.map((t, i) => <span key={i} className="analysis-tag tag-tech">{t}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Technical Areas */}
                      <div className="entity-group">
                        <label>Technical Areas</label>
                        {analysisDetail.technicalAreas?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.technicalAreas.map((a, i) => <span key={i} className="analysis-tag tag-area">{a}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Regions / Locations */}
                      <div className="entity-group">
                        <label>Regions / Locations</label>
                        {analysisDetail.regions?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.regions.map((r, i) => <span key={i} className="analysis-tag tag-region">{r}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Compliance Frameworks */}
                      <div className="entity-group">
                        <label>Compliance Frameworks</label>
                        {analysisDetail.complianceFrameworks?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.complianceFrameworks.map((f, i) => <span key={i} className="analysis-tag tag-compliance">{f}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>

                      {/* Products */}
                      <div className="entity-group">
                        <label>Detected Products</label>
                        {analysisDetail.detectedProducts?.length > 0
                          ? <div className="analysis-tags">{analysisDetail.detectedProducts.map((p, i) => <span key={i} className="analysis-tag tag-product">{p}</span>)}</div>
                          : <span className="no-data">None</span>}
                      </div>
                    </div>
                  )}
                </div>

                {/* ═══ METADATA (always visible footer) ═══ */}
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
          <div className="queue-bulk-summary-header">
            <h3>
              Evaluation Complete — {results.evaluations?.length || 0} items
              {results.evaluations?.[0]?.isDryRun && (
                <span className="queue-dryrun-badge">DRY RUN</span>
              )}
            </h3>
            <div className="queue-bulk-summary-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  const allIds = new Set((results.evaluations || []).map((e) => e.workItemId));
                  setExpandedIds((prev) => prev.size === allIds.size ? new Set() : allIds);
                }}
              >
                {expandedIds.size === (results.evaluations?.length || 0) ? '▲ Collapse All' : '▼ Expand All'}
              </button>
            </div>
          </div>
          {results.errors?.length > 0 && (
            <div className="queue-bulk-errors">
              {results.errors.map((err, i) => (
                <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
              ))}
            </div>
          )}
          <p className="text-muted">
            Click any row or its Results button to toggle evaluation details.
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
