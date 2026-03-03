/**
 * Constants
 * =========
 *
 * Shared constants for the Triage Management UI.
 * Mirrors values from the backend Python models to keep
 * the frontend in sync without runtime validation calls.
 */

// ---------------------------------------------------------------------------
// API base path — in development, Vite proxy forwards /api to port 8009
// ---------------------------------------------------------------------------
export const API_BASE = '/api/v1';

// ---------------------------------------------------------------------------
// ADO base URL — used for deep-linking to work items in the browser.
// Points to the READ org (production data source).
// ---------------------------------------------------------------------------
export const ADO_BASE_URL =
  'https://dev.azure.com/unifiedactiontracker/Unified%20Action%20Tracker';


// ---------------------------------------------------------------------------
// Rule Operators
// Mirrors triage/models/rule.py → VALID_OPERATORS (15 total)
// ---------------------------------------------------------------------------
export const OPERATORS = [
  { value: 'equals',      label: 'Equals',             group: 'String / All' },
  { value: 'notEquals',   label: 'Not Equals',         group: 'String / All' },
  { value: 'in',          label: 'In (list)',          group: 'String / All' },
  { value: 'notIn',       label: 'Not In (list)',      group: 'String / All' },
  { value: 'isNull',      label: 'Is Null',            group: 'String / All' },
  { value: 'isNotNull',   label: 'Is Not Null',        group: 'String / All' },
  { value: 'contains',    label: 'Contains',           group: 'String' },
  { value: 'notContains', label: 'Not Contains',       group: 'String' },
  { value: 'containsAny', label: 'Contains Any (multi-field)', group: 'String' },
  { value: 'regexMatchAny', label: 'Regex Match Any (multi-field)', group: 'String' },
  { value: 'startsWith',  label: 'Starts With',        group: 'String' },
  { value: 'matches',     label: 'Matches (Regex)',    group: 'String' },
  { value: 'under',       label: 'Under (Tree Path)',  group: 'Hierarchical' },
  { value: 'gt',          label: 'Greater Than',       group: 'Numeric / Date' },
  { value: 'lt',          label: 'Less Than',          group: 'Numeric / Date' },
  { value: 'gte',         label: 'Greater or Equal',   group: 'Numeric / Date' },
  { value: 'lte',         label: 'Less or Equal',      group: 'Numeric / Date' },
];

/**
 * Operators that don't require a value input (null checks).
 */
export const VALUELESS_OPERATORS = ['isNull', 'isNotNull'];

/**
 * Operators that support multiple fields (multi-field search).
 * When one of these is selected, the form shows a multi-field selector
 * instead of a single field picker.
 */
export const MULTI_FIELD_OPERATORS = ['containsAny', 'regexMatchAny'];


// ---------------------------------------------------------------------------
// Action Operations
// Mirrors triage/models/action.py → VALID_OPERATIONS (5 total)
// ---------------------------------------------------------------------------
export const OPERATIONS = [
  { value: 'set',          label: 'Set',           description: 'Set field to a static value' },
  { value: 'set_computed', label: 'Set Computed',  description: 'Set to computed value (today(), currentUser())' },
  { value: 'copy',         label: 'Copy',          description: 'Copy value from another field' },
  { value: 'append',       label: 'Append',        description: 'Append to existing value' },
  { value: 'template',     label: 'Template',      description: 'Set with variable substitution' },
];


// ---------------------------------------------------------------------------
// Template Variables (for the "template" operation)
// Mirrors triage/models/action.py → TEMPLATE_VARIABLES
// ---------------------------------------------------------------------------
export const TEMPLATE_VARIABLES = [
  '{CreatedBy}',
  '{SubmitterAlias}',
  '{WorkItemId}',
  '{Title}',
  '{today()}',
  '{currentUser()}',
  '{Analysis.Category}',
  '{Analysis.Products}',
  '{Analysis.Confidence}',
  '{Analysis.Intent}',
  '{Analysis.ContextSummary}',
];


// ---------------------------------------------------------------------------
// Entity Statuses
// Shared across rules, actions, triggers, routes
// ---------------------------------------------------------------------------
export const STATUSES = [
  { value: 'active',   label: 'Active',   color: 'var(--success)' },
  { value: 'disabled', label: 'Disabled', color: 'var(--muted)' },
  { value: 'staged',   label: 'Staged',   color: 'var(--warning)' },
];


// ---------------------------------------------------------------------------
// Analysis States
// From the evaluation state machine
// ---------------------------------------------------------------------------
export const ANALYSIS_STATES = [
  'Pending',
  'Awaiting Approval',
  'Needs Info',
  'Redirected',
  'No Match',
  'Error',
  'Approved',
  'Override',
];


// ---------------------------------------------------------------------------
// Value Types for Actions
// ---------------------------------------------------------------------------
export const VALUE_TYPES = [
  { value: 'static',     label: 'Static Value' },
  { value: 'computed',   label: 'Computed Expression' },
  { value: 'field_ref',  label: 'Field Reference' },
  { value: 'template',   label: 'Template String' },
];


// ---------------------------------------------------------------------------
// Navigation items for the sidebar
// ---------------------------------------------------------------------------
export const NAV_ITEMS = [
  { path: '/',           label: 'Dashboard',   icon: '📊' },
  { path: '/queue',      label: 'Queue',       icon: '📥' },
  { path: '/evaluate',   label: 'Evaluate\\Analyze', icon: '⚡' },
  { divider: true },
  { path: '/rules',      label: 'Rules',       icon: '📋' },
  { path: '/triggers',   label: 'Triggers',    icon: '⚡' },
  { path: '/actions',    label: 'Actions',     icon: '🎯' },
  { path: '/routes',     label: 'Routes',      icon: '🔀' },
  { divider: true },
  { path: '/teams',      label: 'Triage Teams', icon: '👥' },
  { divider: true },
  { path: '/validation', label: 'Validation',  icon: '⚠️' },
  { path: '/audit',      label: 'Audit Log',   icon: '📜' },
  { path: '/history',    label: 'Eval History', icon: '📑' },
  { divider: true },
  { path: '/corrections', label: 'Corrections',  icon: '✏️' },
];
