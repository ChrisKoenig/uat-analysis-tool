/**
 * EvaluatePage — Triage Evaluation & AI Analysis Interface
 * ==========================================================
 *
 * Two modes:
 *   ⚡ Evaluate — Run work items through the triage pipeline
 *   🔬 Analyze — Run AI analysis on work items and display detailed results
 *
 * Both modes accept comma-separated work item IDs.
 * Analyze mode shows results in tabs when multiple IDs are entered.
 *
 * Features:
 *   - Toggle between Evaluate and Analyze modes
 *   - Enter work item IDs (comma-separated)
 *   - Evaluate: Dry run vs. live mode, expandable result cards
 *   - Analyze: Full AI analysis details with tabbed multi-item view
 */

import React, { useState } from 'react';
import * as api from '../api/triageApi';
import StatusBadge from '../components/common/StatusBadge';
import { formatDateTime, formatDate } from '../utils/helpers';
import './EvaluatePage.css';

/* ── Category / Intent Options (match Flask UI reference) ───── */

const CATEGORY_OPTIONS = [
  { group: 'Core', items: [
    { value: 'technical_support', label: 'Technical Support' },
    { value: 'feature_request', label: 'Feature Request' },
    { value: 'compliance_regulatory', label: 'Compliance/Regulatory' },
    { value: 'security_governance', label: 'Security/Governance' },
  ]},
  { group: 'Service', items: [
    { value: 'service_availability', label: 'Service Availability' },
    { value: 'service_retirement', label: 'Service Retirement' },
    { value: 'retirements', label: 'Retirements' },
  ]},
  { group: 'Capacity', items: [
    { value: 'aoai_capacity', label: 'AOAI Capacity' },
    { value: 'capacity', label: 'Capacity' },
  ]},
  { group: 'Business', items: [
    { value: 'business_desk', label: 'Business Desk' },
    { value: 'roadmap', label: 'Roadmap' },
    { value: 'product_roadmap', label: 'Product Roadmap' },
  ]},
  { group: 'Support', items: [
    { value: 'support', label: 'Support' },
    { value: 'support_escalation', label: 'Support Escalation' },
  ]},
  { group: 'Specialized', items: [
    { value: 'data_sovereignty', label: 'Data Sovereignty' },
    { value: 'sustainability', label: 'Sustainability' },
    { value: 'migration_modernization', label: 'Migration/Modernization' },
    { value: 'performance_optimization', label: 'Performance Issue' },
    { value: 'integration_connectivity', label: 'Integration Issue' },
    { value: 'cost_billing', label: 'Cost/Billing' },
    { value: 'training_documentation', label: 'Training/Documentation' },
    { value: 'other', label: 'Other' },
  ]},
];

const INTENT_OPTIONS = [
  { group: 'Support', items: [
    { value: 'seeking_guidance', label: 'Seeking Guidance' },
    { value: 'reporting_issue', label: 'Reporting Issue' },
    { value: 'troubleshooting', label: 'Troubleshooting' },
    { value: 'configuration_help', label: 'Configuration Help' },
  ]},
  { group: 'Requests', items: [
    { value: 'requesting_feature', label: 'Requesting Feature' },
    { value: 'requesting_service', label: 'Requesting Service' },
    { value: 'capacity_request', label: 'Capacity Request' },
  ]},
  { group: 'Business', items: [
    { value: 'business_engagement', label: 'Business Engagement' },
    { value: 'escalation_request', label: 'Escalation Request' },
  ]},
  { group: 'Specialized', items: [
    { value: 'compliance_support', label: 'Compliance Support' },
    { value: 'sovereignty_concern', label: 'Sovereignty Concern' },
    { value: 'roadmap_inquiry', label: 'Roadmap Inquiry' },
    { value: 'sustainability_inquiry', label: 'Sustainability Inquiry' },
    { value: 'need_migration_help', label: 'Migration Help' },
    { value: 'best_practices', label: 'Best Practices' },
  ]},
];

const BUSINESS_IMPACT_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

/* ── Helper Components (match Field Portal style) ───────────── */

function AnalysisBadge({ children, color = '#0078d4', bg = '#deecf9' }) {
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, color, background: bg, marginRight: 4, marginBottom: 4,
    }}>
      {children}
    </span>
  );
}

function ImpactBadge({ level }) {
  const map = {
    critical: { bg: '#d13438', fg: '#fff' },
    high: { bg: '#d13438', fg: '#fff' },
    medium: { bg: '#ffb900', fg: '#323130' },
    low: { bg: '#107c10', fg: '#fff' },
  };
  const style = map[(level || '').toLowerCase()] || { bg: '#e1dfdd', fg: '#323130' };
  return <AnalysisBadge color={style.fg} bg={style.bg}>{level || '—'}</AnalysisBadge>;
}

function CategoryBadge({ value }) {
  return <AnalysisBadge color="#fff" bg="#0078d4">{formatFieldLabel(value)}</AnalysisBadge>;
}

function formatFieldLabel(s) {
  if (!s) return '—';
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function CollapsibleEntitySection({ title, count, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="entity-collapsible">
      <button onClick={() => setOpen(!open)} className="entity-collapsible-btn">
        <span>{title} {count != null && <AnalysisBadge bg="#e1dfdd" color="#323130">{count}</AnalysisBadge>}</span>
        <span style={{ fontSize: 18 }}>{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="entity-collapsible-body">{children}</div>}
    </div>
  );
}


export default function EvaluatePage({ addToast }) {
  // ── Mode: 'evaluate' or 'analyze' ───────────────────────────
  const [mode, setMode] = useState('evaluate');

  // ── Shared State ─────────────────────────────────────────────
  const [inputIds, setInputIds] = useState('');
  const [running, setRunning] = useState(false);

  // ── Evaluate State ───────────────────────────────────────────
  const [dryRun, setDryRun] = useState(true);
  const [results, setResults] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [applying, setApplying] = useState(null);

  // ── Analyze State ────────────────────────────────────────────
  const [analysisResults, setAnalysisResults] = useState([]);  // [{workItemId, detail, error, loading}]
  const [activeTab, setActiveTab] = useState(null);

  // ── Evaluation / Corrections State (per work item) ──────────
  const [evalStates, setEvalStates] = useState({});
  // evalStates[workItemId] = { evalCorrect, feedback, correctedCategory, correctedIntent, correctedImpact, submitting, error }

  const defaultEvalState = { evalCorrect: null, feedback: '', correctedCategory: '', correctedIntent: '', correctedImpact: '', submitting: false, error: '' };
  const getEvalState = (workItemId) => evalStates[workItemId] || defaultEvalState;
  const updateEvalState = (workItemId, patch) =>
    setEvalStates(prev => ({ ...prev, [workItemId]: { ...getEvalState(workItemId), ...patch } }));

  // ── Parse IDs helper ─────────────────────────────────────────
  const parseIds = () =>
    inputIds
      .split(/[,\s]+/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0);


  // ── Run Evaluation ───────────────────────────────────────────

  const handleEvaluate = async (e) => {
    e.preventDefault();
    const ids = parseIds();
    if (ids.length === 0) {
      addToast?.('Please enter valid work item IDs', 'warning');
      return;
    }

    setRunning(true);
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
      setRunning(false);
    }
  };


  // ── Run Analysis ─────────────────────────────────────────────

  const handleAnalyze = async (e) => {
    e.preventDefault();
    const ids = parseIds();
    if (ids.length === 0) {
      addToast?.('Please enter valid work item IDs', 'warning');
      return;
    }

    setRunning(true);

    // Initialize placeholders
    const placeholders = ids.map((id) => ({
      workItemId: id,
      detail: null,
      error: null,
      loading: true,
    }));
    setAnalysisResults(placeholders);
    setActiveTab(ids[0]);

    try {
      // Step 1: Run analysis engine
      const runResult = await api.runAnalysis(ids);
      const errors = runResult.errors || [];

      if (errors.length > 0) {
        addToast?.(`Analysis completed with ${errors.length} warning(s)`, 'warning');
      }

      // Step 2: Fetch full detail for each item
      const detailed = await Promise.all(
        ids.map(async (id) => {
          const summary = (runResult.results || []).find((r) => r.workItemId === id);
          if (summary && !summary.success) {
            return { workItemId: id, detail: null, error: summary.error, loading: false };
          }
          try {
            const detail = await api.getAnalysisDetail(id);
            return { workItemId: id, detail, error: null, loading: false };
          } catch (err) {
            return { workItemId: id, detail: null, error: err.message, loading: false };
          }
        })
      );

      setAnalysisResults(detailed);
      const successCount = detailed.filter((d) => d.detail).length;
      addToast?.(
        `Analyzed ${successCount} of ${ids.length} item(s)`,
        successCount === ids.length ? 'success' : 'warning'
      );
    } catch (err) {
      addToast?.(err.message, 'error');
      setAnalysisResults(
        ids.map((id) => ({ workItemId: id, detail: null, error: err.message, loading: false }))
      );
    } finally {
      setRunning(false);
    }
  };


  // ── Apply Results to ADO ─────────────────────────────────────

  const handleApply = async (evaluation) => {
    setApplying(evaluation.id);
    try {
      const result = await api.applyEvaluation(
        evaluation.id,
        evaluation.workItemId
      );
      if (result.success) {
        addToast?.(
          `Applied ${result.fieldsUpdated} changes to work item ${evaluation.workItemId}`,
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


  // ── Render Analysis Detail for one item (Field Portal style) ─

  const handleSubmitCorrection = async (workItemId, detail, action) => {
    updateEvalState(workItemId, { submitting: true, error: '' });
    const es = getEvalState(workItemId);
    try {
      await api.addCorrection({
        original_category: detail.category || '',
        corrected_category: action === 'approve'
          ? detail.category
          : (es.correctedCategory || detail.category || ''),
        original_text: detail.originalTitle || '',
        corrected_intent: action === 'approve'
          ? detail.intent
          : (es.correctedIntent || detail.intent || ''),
        correction_notes: action === 'approve'
          ? (es.feedback || 'Analysis approved — no corrections needed')
          : (es.feedback || ''),
      });
      addToast?.(
        action === 'approve'
          ? `Analysis for #${workItemId} approved`
          : `Corrections saved for #${workItemId}`,
        'success'
      );
      updateEvalState(workItemId, { submitting: false });
    } catch (err) {
      updateEvalState(workItemId, { submitting: false, error: err.message });
    }
  };

  const handleReanalyze = async (workItemId, detail) => {
    updateEvalState(workItemId, { submitting: true, error: '' });
    const es = getEvalState(workItemId);
    try {
      // Save correction first
      await api.addCorrection({
        original_category: detail.category || '',
        corrected_category: es.correctedCategory || detail.category || '',
        original_text: detail.originalTitle || '',
        corrected_intent: es.correctedIntent || detail.intent || '',
        correction_notes: es.feedback || '',
      });

      // Re-analyze with correction hints
      const result = await api.reanalyzeWithCorrections(workItemId, {
        correct_category: es.correctedCategory || '',
        correct_intent: es.correctedIntent || '',
        correct_business_impact: es.correctedImpact || '',
        correction_notes: es.feedback || '',
      });

      if (result.success && result.analysis) {
        // Update the analysis detail in-place
        setAnalysisResults(prev => prev.map(item =>
          item.workItemId === workItemId
            ? { ...item, detail: result.analysis }
            : item
        ));
        addToast?.(`Re-analysis complete for #${workItemId}`, 'success');
        updateEvalState(workItemId, { submitting: false, evalCorrect: null, feedback: '' });
      } else {
        throw new Error(result.message || 'Re-analysis returned no result');
      }
    } catch (err) {
      updateEvalState(workItemId, { submitting: false, error: err.message });
    }
  };

  const renderAnalysisDetail = (detail, workItemId) => {
    if (!detail) return null;

    const isLLM = (detail.source || '').toLowerCase().includes('llm')
      || (detail.source || '').toLowerCase().includes('ai')
      || (detail.source || '').toLowerCase().includes('openai');
    const aiOffline = detail.aiAvailable === false || !isLLM;
    const sourceLabel = isLLM
      ? 'Large Language Model (LLM) Classification'
      : 'Pattern Matching Classification';
    const es = getEvalState(workItemId);

    return (
      <div className="fp-analysis-body">

        {/* ── Analysis Status Banner ── */}
        {aiOffline ? (
          <div className="fp-banner fp-banner-warning">
            <h3>⚠️ AI Classification Unavailable — Pattern Matching Used</h3>
            <p>
              The Azure OpenAI service was not reachable during this analysis. The system fell back to
              rule-based pattern matching, which provides a baseline classification but may be less accurate.
            </p>
            {detail.aiError && (
              <div className="fp-error-detail">
                <strong>Reason:</strong> {detail.aiError}
              </div>
            )}
            <ul className="fp-meta-list">
              <li><strong>Analysis Method:</strong> {sourceLabel}</li>
              <li><strong>Confidence Level:</strong> {Math.round((detail.confidence || 0) * 100)}%</li>
              <li><strong>Source:</strong> {detail.source || 'unknown'}</li>
            </ul>
          </div>
        ) : (
          <div className="fp-banner fp-banner-success">
            <h3>✓ AI-Powered Analysis Complete</h3>
            <p>
              This work item has been analyzed using advanced AI classification.
              {isLLM && ' The system used Azure OpenAI to understand the context, intent, and technical requirements.'}
            </p>
            <ul className="fp-meta-list">
              <li><strong>Analysis Method:</strong> {sourceLabel}</li>
              <li><strong>Confidence Level:</strong> {Math.round((detail.confidence || 0) * 100)}%</li>
              <li><strong>Source:</strong> {detail.source || 'unknown'}</li>
            </ul>
          </div>
        )}

        {/* ── Original Issue ── */}
        {(detail.originalTitle || detail.originalDescription) && (
          <div className="fp-card">
            <div className="fp-card-header fp-card-header-issue">📋 Original Issue</div>
            <div className="fp-card-body">
              <div className="fp-issue-grid">
                <div>
                  <strong>Title:</strong>
                  <p>{detail.originalTitle || '—'}</p>
                  <strong>Description:</strong>
                  <p className="fp-description">{detail.originalDescription || '—'}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── System's Analysis ── */}
        <div className="fp-card">
          <div className="fp-card-header fp-card-header-analysis">🤖 System's Analysis</div>
          <div className="fp-card-body">
            <div className="fp-badge-grid">
              <div>
                <strong>Category:</strong><br />
                <CategoryBadge value={detail.category} />
              </div>
              <div>
                <strong>Intent:</strong><br />
                <AnalysisBadge color="#fff" bg="#27ae60">{formatFieldLabel(detail.intent)}</AnalysisBadge>
              </div>
              <div>
                <strong>Business Impact:</strong><br />
                <ImpactBadge level={detail.businessImpact} />
              </div>
              <div>
                <strong>Confidence:</strong><br />
                <AnalysisBadge color="#fff" bg="#2471a3">{Math.round((detail.confidence || 0) * 100)}%</AnalysisBadge>
              </div>
            </div>

            {/* Context Summary */}
            {detail.contextSummary && (
              <div className="fp-context-summary">
                <strong>Context Summary:</strong>
                <div className="fp-summary-box">{detail.contextSummary}</div>
              </div>
            )}

            {/* Comprehensive Reasoning */}
            <h3 className="fp-subsection-title">
              {isLLM ? '🔍 Comprehensive AI Analysis & Reasoning' : '📊 Pattern-Based Analysis & Reasoning'}
            </h3>

            {detail.reasoning && detail.reasoning !== detail.contextSummary && (
              <div className="fp-reasoning-block">
                <strong>{isLLM ? '🧠 AI Classification Reasoning' : '🧠 Classification Reasoning'}</strong>
                <div className="fp-reasoning-text">
                  {detail.reasoning}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Final Decision Summary ── */}
        <div className="fp-card">
          <div className="fp-card-header fp-card-header-decision">🎯 Final Decision Summary</div>
          <div className="fp-card-body">
            <div className="fp-decision-row">
              <strong>Category Decision:</strong>{' '}
              <CategoryBadge value={detail.category} />
            </div>
            <div className="fp-decision-row">
              <strong>Intent:</strong>{' '}
              <AnalysisBadge color="#fff" bg="#27ae60">{formatFieldLabel(detail.intent)}</AnalysisBadge>
            </div>
            <div className="fp-decision-row">
              <strong>Business Impact:</strong>{' '}
              <ImpactBadge level={detail.businessImpact} />
            </div>
            <div className="fp-decision-row">
              <strong>Confidence Level:</strong>{' '}
              <AnalysisBadge color="#fff" bg="#2471a3">{Math.round((detail.confidence || 0) * 100)}%</AnalysisBadge>
            </div>

            {isLLM ? (
              <div className="fp-info-note">
                ℹ️ This analysis was performed using Azure OpenAI with advanced natural language understanding.
              </div>
            ) : (
              <div className="fp-warning-note">
                ⚠️ This analysis was performed using rule-based pattern matching. AI classification was unavailable.
              </div>
            )}

            {/* Technical Complexity & Urgency */}
            <div className="fp-complexity-grid">
              <div>
                <strong>Technical Complexity:</strong><br />
                <ImpactBadge level={detail.technicalComplexity} />
              </div>
              <div>
                <strong>Urgency Level:</strong><br />
                <ImpactBadge level={detail.urgencyLevel} />
              </div>
            </div>

            {/* Key Concepts */}
            {detail.keyConcepts?.length > 0 && (
              <div className="fp-tag-section">
                <strong>Key Concepts Identified:</strong>
                <div className="fp-tags">
                  {detail.keyConcepts.map((c, i) => (
                    <AnalysisBadge key={i} color="#fff" bg="#34495e">{c}</AnalysisBadge>
                  ))}
                </div>
              </div>
            )}

            {/* Semantic Keywords */}
            {detail.semanticKeywords?.length > 0 && (
              <div className="fp-tag-section">
                <strong>Semantic Keywords:</strong>
                <div className="fp-tags">
                  {detail.semanticKeywords.map((k, i) => (
                    <AnalysisBadge key={i} color="#fff" bg="#2980b9">{k}</AnalysisBadge>
                  ))}
                </div>
              </div>
            )}

            {/* Domain Entities */}
            {(detail.azureServices?.length > 0 || detail.technologies?.length > 0 ||
              detail.detectedProducts?.length > 0 || detail.regions?.length > 0) && (
              <div className="fp-entities-section">
                <strong>Domain Entities Detected:</strong>
                <div className="fp-entities">
                  {detail.azureServices?.length > 0 && (
                    <CollapsibleEntitySection title="Azure Services" count={detail.azureServices.length}>
                      <div>{detail.azureServices.map((s, i) => <AnalysisBadge key={i} bg="#deecf9" color="#0078d4">{s}</AnalysisBadge>)}</div>
                    </CollapsibleEntitySection>
                  )}
                  {detail.technologies?.length > 0 && (
                    <CollapsibleEntitySection title="Technologies" count={detail.technologies.length}>
                      <div>{detail.technologies.map((t, i) => <AnalysisBadge key={i} bg="#e8daef" color="#6c3483">{t}</AnalysisBadge>)}</div>
                    </CollapsibleEntitySection>
                  )}
                  {detail.detectedProducts?.length > 0 && (
                    <CollapsibleEntitySection title="Detected Products" count={detail.detectedProducts.length}>
                      <div>{detail.detectedProducts.map((p, i) => <AnalysisBadge key={i} bg="#fde7e9" color="#d13438">{p}</AnalysisBadge>)}</div>
                    </CollapsibleEntitySection>
                  )}
                  {detail.regions?.length > 0 && (
                    <CollapsibleEntitySection title="Regions" count={detail.regions.length}>
                      <div>{detail.regions.map((r, i) => <AnalysisBadge key={i} bg="#d6eaf8" color="#2471a3">{r}</AnalysisBadge>)}</div>
                    </CollapsibleEntitySection>
                  )}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="fp-metadata">
              <span>Analyzed: {detail.timestamp ? formatDate(detail.timestamp) : '—'}</span>
              <span>Pattern Confidence: {((detail.patternConfidence || 0) * 100).toFixed(0)}%</span>
              <span>ID: {detail.id}</span>
            </div>
          </div>
        </div>

        {/* ── Your Evaluation ── */}
        <div className="fp-card">
          <div className="fp-card-header fp-card-header-eval">✅ Your Evaluation</div>
          <div className="fp-card-body">
            <div className="fp-eval-question">
              <strong>Is this analysis correct?</strong>

              <div className="fp-eval-options">
                <label className="fp-eval-option">
                  <input
                    type="radio"
                    name={`eval-${workItemId}`}
                    checked={es.evalCorrect === true}
                    onChange={() => updateEvalState(workItemId, { evalCorrect: true })}
                    style={{ accentColor: 'var(--success, #107c10)' }}
                  />
                  <span className="fp-eval-yes">
                    ✔ Yes, this analysis is correct
                  </span>
                </label>
                <label className="fp-eval-option">
                  <input
                    type="radio"
                    name={`eval-${workItemId}`}
                    checked={es.evalCorrect === false}
                    onChange={() => updateEvalState(workItemId, {
                      evalCorrect: false,
                      // Pre-populate dropdowns with current analysis values
                      correctedCategory: es.correctedCategory || detail.category || '',
                      correctedIntent: es.correctedIntent || detail.intent || '',
                      correctedImpact: es.correctedImpact || detail.businessImpact || '',
                    })}
                    style={{ accentColor: 'var(--danger, #d13438)' }}
                  />
                  <span className="fp-eval-no">
                    ✗ No, this analysis needs correction
                  </span>
                </label>
              </div>
            </div>

            {/* ── Correction Dropdowns (shown when "No" is selected) ── */}
            {es.evalCorrect === false && (
              <div className="fp-correction-fields">
                <h4 className="fp-correction-heading">Please provide the correct analysis:</h4>
                <div className="fp-correction-row">
                  <div className="fp-correction-field">
                    <label htmlFor={`cat-${workItemId}`}>Correct Category:</label>
                    <select
                      id={`cat-${workItemId}`}
                      className="fp-correction-select"
                      value={es.correctedCategory}
                      onChange={(e) => updateEvalState(workItemId, { correctedCategory: e.target.value })}
                    >
                      <option value="">-- Select Category --</option>
                      {CATEGORY_OPTIONS.map((g) => (
                        <optgroup key={g.group} label={g.group}>
                          {g.items.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div className="fp-correction-field">
                    <label htmlFor={`int-${workItemId}`}>Correct Intent:</label>
                    <select
                      id={`int-${workItemId}`}
                      className="fp-correction-select"
                      value={es.correctedIntent}
                      onChange={(e) => updateEvalState(workItemId, { correctedIntent: e.target.value })}
                    >
                      <option value="">-- Select Intent --</option>
                      {INTENT_OPTIONS.map((g) => (
                        <optgroup key={g.group} label={g.group}>
                          {g.items.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <div className="fp-correction-field">
                    <label htmlFor={`imp-${workItemId}`}>Correct Business Impact:</label>
                    <select
                      id={`imp-${workItemId}`}
                      className="fp-correction-select"
                      value={es.correctedImpact}
                      onChange={(e) => updateEvalState(workItemId, { correctedImpact: e.target.value })}
                    >
                      <option value="">-- Select Impact --</option>
                      {BUSINESS_IMPACT_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            <div className="fp-eval-feedback">
              <label>{es.evalCorrect === false ? 'Explain why the analysis is wrong:' : 'General Feedback (optional):'}</label>
              <textarea
                value={es.feedback}
                onChange={(e) => updateEvalState(workItemId, { feedback: e.target.value })}
                rows={3}
                placeholder={es.evalCorrect === false
                  ? 'Please explain why the system\'s analysis was incorrect and provide any additional context...'
                  : 'Any additional feedback to help improve the system...'}
                className="fp-eval-textarea"
              />
            </div>

            {es.error && <div className="fp-eval-error">{es.error}</div>}

            <div className="fp-eval-actions">
              {es.evalCorrect === false && (
                <>
                  <button
                    className="btn btn-primary"
                    style={{ backgroundColor: '#0078d4', borderColor: '#0078d4' }}
                    onClick={() => handleReanalyze(workItemId, detail)}
                    disabled={es.submitting}
                  >
                    {es.submitting ? '⏳ Reanalyzing…' : '🔄 Reanalyze with Corrections'}
                  </button>
                  <button
                    className="btn btn-success"
                    onClick={() => handleSubmitCorrection(workItemId, detail, 'save_corrections')}
                    disabled={es.submitting}
                  >
                    {es.submitting ? '⏳ Saving…' : '💾 Save Corrections Only'}
                  </button>
                </>
              )}
              {es.evalCorrect === true && (
                <button
                  className="btn btn-success"
                  onClick={() => handleSubmitCorrection(workItemId, detail, 'approve')}
                  disabled={es.submitting}
                >
                  {es.submitting ? '⏳ Saving…' : '✔ Approve Analysis'}
                </button>
              )}
            </div>

            {es.evalCorrect === null && (
              <div className="fp-eval-hint">
                ⚠ Please select an option above
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };


  // ── Render ───────────────────────────────────────────────────

  return (
    <div className="evaluate-page">
      <div className="page-header">
        <h1>{mode === 'evaluate' ? '⚡ Evaluate' : '🔬 Analyze'}</h1>
      </div>

      {/* Input Form */}
      <div className="card evaluate-input-card">
        <div className="card-body">
          {/* Mode Toggle */}
          <div className="evaluate-mode-toggle">
            <button
              type="button"
              className={`mode-btn ${mode === 'evaluate' ? 'active' : ''}`}
              onClick={() => setMode('evaluate')}
            >
              ⚡ Evaluate
            </button>
            <button
              type="button"
              className={`mode-btn ${mode === 'analyze' ? 'active' : ''}`}
              onClick={() => setMode('analyze')}
            >
              🔬 Analyze
            </button>
          </div>

          <form onSubmit={mode === 'evaluate' ? handleEvaluate : handleAnalyze} className="evaluate-form">
            <div className="form-group">
              <label htmlFor="eval-ids">Work Item IDs</label>
              <input
                id="eval-ids"
                className="form-input"
                type="text"
                value={inputIds}
                onChange={(e) => setInputIds(e.target.value)}
                placeholder="Enter IDs separated by commas, e.g.: 12345, 12346, 12347"
                required
              />
              <span className="hint">
                {mode === 'evaluate'
                  ? 'Enter one or more ADO work item IDs to evaluate through the triage pipeline'
                  : 'Enter one or more ADO work item IDs to run AI analysis and view detailed results'}
              </span>
            </div>

            <div className="evaluate-form-actions">
              {mode === 'evaluate' && (
                <label className="evaluate-dryrun-toggle">
                  <input
                    type="checkbox"
                    checked={dryRun}
                    onChange={(e) => setDryRun(e.target.checked)}
                  />
                  <span>Dry Run</span>
                  <span className="hint">(compute results without writing to ADO)</span>
                </label>
              )}
              {mode === 'analyze' && <div />}

              <button
                type="submit"
                className="btn btn-primary"
                disabled={running}
              >
                {running
                  ? (mode === 'evaluate' ? 'Evaluating…' : 'Analyzing…')
                  : (mode === 'evaluate' ? '⚡ Evaluate' : '🔬 Analyze')}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* ─── Evaluate Results ───────────────────────────────────── */}
      {mode === 'evaluate' && results && (
        <div className="evaluate-results">
          <h2>
            Results — {results.evaluations?.length || 0} item(s)
            {results.evaluations?.[0]?.isDryRun && (
              <span className="evaluate-dryrun-badge">DRY RUN</span>
            )}
          </h2>

          {results.errors?.length > 0 && (
            <div className="evaluate-errors">
              {results.errors.map((err, i) => (
                <div key={i} className="toast toast-error">{err}</div>
              ))}
            </div>
          )}

          {results.evaluations?.map((evalResult) => (
            <div key={evalResult.id} className="card evaluate-result-card">
              <div
                className="evaluate-result-header"
                onClick={() => setExpandedId(
                  expandedId === evalResult.id ? null : evalResult.id
                )}
              >
                <div className="evaluate-result-summary">
                  <strong>#{evalResult.workItemId}</strong>
                  <span
                    className={`evaluate-state evaluate-state-${evalResult.analysisState?.replace(/\s/g, '-').toLowerCase()}`}
                    title={evalResult.analysisState === 'No Match'
                      ? 'Rules were evaluated but no trigger condition was fully satisfied'
                      : evalResult.analysisState}
                  >
                    {evalResult.analysisState === 'No Match' ? 'No Trigger Matched' : evalResult.analysisState}
                  </span>
                  {evalResult.matchedTrigger && (
                    <span className="evaluate-matched">
                      ⚡ {evalResult.matchedTrigger}
                    </span>
                  )}
                  {evalResult.appliedRoute && (
                    <span className="evaluate-route">
                      🔀 {evalResult.appliedRoute}
                    </span>
                  )}
                </div>
                <div className="evaluate-result-actions">
                  {evalResult.adoLink && (
                    <a
                      href={evalResult.adoLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open in ADO ↗
                    </a>
                  )}
                  {!evalResult.isDryRun && (
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={applying === evalResult.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleApply(evalResult);
                      }}
                    >
                      {applying === evalResult.id ? 'Applying…' : 'Apply to ADO'}
                    </button>
                  )}
                  <span className="evaluate-expand-icon">
                    {expandedId === evalResult.id ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedId === evalResult.id && (
                <div className="evaluate-result-details">
                  {/* Rule Results */}
                  <div className="evaluate-detail-section">
                    <h4>Rule Results ({Object.keys(evalResult.ruleResults || {}).length})</h4>
                    <div className="evaluate-rule-results">
                      {Object.entries(evalResult.ruleResults || {}).map(([ruleId, result]) => {
                        const ruleName = evalResult.ruleNames?.[ruleId] || ruleId;
                        return (
                          <span
                            key={ruleId}
                            className={`evaluate-rule-chip ${result ? 'rule-true' : 'rule-false'}`}
                            title={ruleId}
                          >
                            {result ? '✓' : '✗'} {ruleName}
                          </span>
                        );
                      })}
                    </div>
                  </div>

                  {/* Field Changes */}
                  {Object.keys(evalResult.fieldsChanged || {}).length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Field Changes</h4>
                      <table className="evaluate-changes-table">
                        <thead>
                          <tr>
                            <th>Field</th>
                            <th>From</th>
                            <th>To</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(evalResult.fieldsChanged).map(([field, change]) => (
                            <tr key={field}>
                              <td><code className="field-ref">{field}</code></td>
                              <td className="text-muted">{change.from ?? '—'}</td>
                              <td><strong>{change.to ?? '—'}</strong></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Actions Executed */}
                  {evalResult.actionsExecuted?.length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Actions Executed</h4>
                      <ol className="evaluate-actions-list">
                        {evalResult.actionsExecuted.map((actionId, i) => (
                          <li key={i}>{actionId}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* Errors */}
                  {evalResult.errors?.length > 0 && (
                    <div className="evaluate-detail-section">
                      <h4>Errors</h4>
                      {evalResult.errors.map((err, i) => (
                        <div key={i} className="toast toast-error" style={{ position: 'static' }}>{err}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ─── Analyze Results ────────────────────────────────────── */}
      {mode === 'analyze' && analysisResults.length > 0 && (
        <div className="analyze-results">
          <h2>🔬 Analysis Results — {analysisResults.length} item(s)</h2>

          {/* Tabs (only show if >1 item) */}
          {analysisResults.length > 1 && (
            <div className="analyze-tabs">
              {analysisResults.map((item) => (
                <button
                  key={item.workItemId}
                  type="button"
                  className={`analyze-tab ${activeTab === item.workItemId ? 'active' : ''} ${item.error ? 'tab-error' : ''}`}
                  onClick={() => setActiveTab(item.workItemId)}
                >
                  #{item.workItemId}
                  {item.loading && <span className="tab-spinner">⏳</span>}
                  {item.detail && <span className="tab-check">✓</span>}
                  {item.error && <span className="tab-err">✗</span>}
                </button>
              ))}
            </div>
          )}

          {/* Active Tab Content */}
          {analysisResults.map((item) => (
            <div
              key={item.workItemId}
              className="analyze-tab-content"
              style={{ display: activeTab === item.workItemId ? 'block' : 'none' }}
            >
              <div className="card analyze-result-card">
                <div className="analyze-result-card-header">
                  <h3>#{item.workItemId}</h3>
                  {item.detail?.originalTitle && (
                    <span className="analyze-title-text">{item.detail.originalTitle}</span>
                  )}
                </div>

                {item.loading && (
                  <div className="analyze-loading">
                    <div className="analyze-spinner" />
                    Analyzing work item #{item.workItemId}…
                  </div>
                )}

                {item.error && (
                  <div className="analyze-error">
                    <strong>Error:</strong> {item.error}
                  </div>
                )}

                {item.detail && renderAnalysisDetail(item.detail, item.workItemId)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
