/**
 * Analysis Detail Page — Full "Intelligent Context Analysis - Please Review"
 *
 * FR-1999: Content organized into 4 pill-style tabs to reduce scrolling:
 *   📋 Overview  — Original issue, classification badges, context summary
 *   🧠 Analysis  — AI/pattern reasoning, confidence breakdown, data sources
 *   🎯 Decision  — Decision summary, key concepts, domain entities, search strategy
 *   ✅ Evaluate  — Approve/correct form with feedback
 *
 * Status banner (LLM vs pattern) remains above tabs, always visible.
 * Tab CSS lives in global.css (.analysis-tabs, .analysis-tab, etc.).
 */
import React, { useState, useEffect, Component } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import ConfidenceBar from '../components/ConfidenceBar';
import { getAnalysisDetail, submitCorrection, analyzeContext } from '../api/fieldApi';

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

/* ---------- small helpers ---------- */
function Badge({ children, color = '#0078d4', bg = '#deecf9' }) {
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
  return <Badge color={style.fg} bg={style.bg}>{level || '—'}</Badge>;
}

function CategoryBadge({ value }) {
  return <Badge color="#fff" bg="#0078d4">{formatLabel(value)}</Badge>;
}

function formatLabel(s) {
  if (!s) return '—';
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/* ---------- collapsible section ---------- */
function CollapsibleSection({ title, count, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ border: '1px solid var(--color-border)', borderRadius: 6, marginBottom: 8 }}>
      <button onClick={() => setOpen(!open)} style={{
        width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'none', border: 'none', padding: '10px 14px', cursor: 'pointer',
        fontSize: 14, fontWeight: 600, fontFamily: 'inherit',
      }}>
        <span>{title} {count != null && <Badge bg="#e1dfdd" color="#323130">{count}</Badge>}</span>
        <span style={{ fontSize: 18 }}>{open ? '▾' : '▸'}</span>
      </button>
      {open && <div style={{ padding: '0 14px 12px' }}>{children}</div>}
    </div>
  );
}


/* ---------- Error Boundary ---------- */
class DetailErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="card">
          <div className="alert alert-danger">
            <h3>Render Error</h3>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{this.state.error.toString()}\n{this.state.error.stack}</pre>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ============================================================
   Main Component
   ============================================================ */
export default function AnalysisDetailPage() {
  const params = useParams();
  const { state: navState } = useLocation();
  const sessionId = params.sessionId || navState?.sessionId;
  const [detail, setDetail] = useState(null);
  const setDetail_outer = (d) => setDetail(d);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const d = await getAnalysisDetail(sessionId);
        setDetail(d); setLoading(false);
      } catch (err) {
        setError(err.message); setLoading(false);
      }
    })();
  }, [sessionId]);

  if (!sessionId) {
    return <div className="card"><h2>No session ID in URL</h2><p>Params: {JSON.stringify(params)}</p></div>;
  }
  if (loading) {
    return <div className="card"><h2>Loading...</h2><p>Session: {sessionId}</p></div>;
  }
  if (error) {
    return <div className="card"><h2>Error</h2><p>{error}</p></div>;
  }
  if (!detail) {
    return <div className="card"><h2>No data</h2></div>;
  }

  return (
    <DetailErrorBoundary>
      <AnalysisDetailContent detail={detail} sessionId={sessionId} setDetail={setDetail} />
    </DetailErrorBoundary>
  );
}

function AnalysisDetailContent({ detail, sessionId, setDetail }) {
  const navigate = useNavigate();

  // Evaluation state
  const [evalCorrect, setEvalCorrect] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [correctedCategory, setCorrectedCategory] = useState('');
  const [correctedIntent, setCorrectedIntent] = useState('');
  const [correctedImpact, setCorrectedImpact] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  // FR-1999: Active tab for the 4-tab detail layout (overview | analysis | decision | evaluate)
  const [activeTab, setActiveTab] = useState('overview');

  const { analysis, original_input, analysis_method, reasoning, pattern_analysis_steps,
    domain_entities, key_concepts, semantic_keywords, search_strategy,
    technical_complexity, urgency_level, context_summary,
    data_sources, confidence_breakdown, final_analysis } = detail;

  const srcLower = (analysis_method?.source || '').toLowerCase();
  const isLLM = srcLower.includes('llm') || srcLower.includes('ai') || srcLower.includes('hybrid');
  const aiOffline = analysis_method?.ai_available === false || !isLLM;
  const aiError = analysis_method?.ai_error || analysis?.ai_error || null;
  const sourceLabel = isLLM
    ? 'Large Language Model (LLM) Classification'
    : 'Pattern Matching Classification';

  /* ── action handlers ── */
  const handleRetryAI = async () => {
    setSubmitting(true);
    setError('');
    try {
      const result = await analyzeContext(sessionId);
      const retryAnalysis = result?.analysis;
      if (retryAnalysis?.ai_available === false
          || (retryAnalysis?.source || '').toLowerCase().includes('pattern')
          || (retryAnalysis?.source || '').toLowerCase().includes('fallback')) {
        const reason = retryAnalysis?.ai_error || 'Azure OpenAI service is still unreachable';
        setError(`AI is still unavailable: ${reason}`);
      } else {
        setError('');
      }
      // Reload detail with fresh data
      const freshDetail = await getAnalysisDetail(sessionId);
      setDetail(freshDetail);
    } catch (err) {
      setError(`Retry failed: ${err.message}`);
    } finally { setSubmitting(false); }
  };

  const handleReanalyze = async () => {
    setSubmitting(true);
    try {
      await submitCorrection({
        session_id: sessionId,
        action: 'reanalyze',
        correct_category: correctedCategory || undefined,
        correct_intent: correctedIntent || undefined,
        correct_business_impact: correctedImpact || undefined,
        correction_notes: feedback,
      });
      // Reload detail with fresh data
      const freshDetail = await getAnalysisDetail(sessionId);
      setDetail(freshDetail);
    } catch (err) {
      setError(err.message);
    } finally { setSubmitting(false); }
  };

  const handleSaveCorrections = async () => {
    setSubmitting(true);
    try {
      await submitCorrection({
        session_id: sessionId,
        action: 'save_corrections',
        correct_category: correctedCategory || undefined,
        correct_intent: correctedIntent || undefined,
        correct_business_impact: correctedImpact || undefined,
        correction_notes: feedback,
      });
      navigate('/searching', { state: { sessionId } });
    } catch (err) {
      setError(err.message);
    } finally { setSubmitting(false); }
  };

  const handleBackToSummary = () => {
    navigate('/analysis', { state: { sessionId, analysisData: { analysis, original_input } } });
  };

  return (
    <>
      <ProgressStepper currentStep={3} />

      {/* Header bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 16,
      }}>
        <h2 style={{ margin: 0 }}>Intelligent Context Analysis — Please Review</h2>
        <button className="btn btn-secondary" onClick={handleBackToSummary} style={{ fontSize: 13 }}>
          ← Back to Summary
        </button>
      </div>

      <p style={{ color: 'var(--color-text-secondary)', fontSize: 13, marginBottom: 20 }}>
        Please review the system's analysis below. Your feedback helps improve the matching accuracy over time.
      </p>

      {/* ── Analysis Status Banner (always visible) ── */}
      {aiOffline ? (
        <div style={{
          background: '#fff4ce', border: '1px solid #ffb900', borderRadius: 8,
          padding: '18px 22px', marginBottom: 16,
        }}>
          <h3 style={{ marginBottom: 6, color: '#8a6d3b' }}>⚠️ AI Classification Unavailable — Pattern Matching Used</h3>
          <p style={{ margin: '0 0 8px', fontSize: 13, color: '#605e5c', lineHeight: 1.6 }}>
            The Azure OpenAI service was not reachable during this analysis. The system fell back to
            rule-based pattern matching, which provides a baseline classification but may be less accurate
            than AI-powered analysis.
          </p>
          {aiError && (
            <div style={{
              background: '#fde7e9', padding: '8px 12px', borderRadius: 4,
              fontSize: 12, color: '#a4262c', fontFamily: 'monospace', marginBottom: 10,
            }}>
              <strong>Reason:</strong> {aiError}
            </div>
          )}
          <ul style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13 }}>
            <li><strong>Analysis Method:</strong> {sourceLabel}</li>
            <li><strong>Confidence Level:</strong> {Math.round((analysis.confidence || 0) * 100)}%</li>
            <li><strong>Source:</strong> {analysis.source || 'unknown'}</li>
          </ul>
          <button
            className="btn btn-primary"
            onClick={handleRetryAI}
            disabled={submitting}
            style={{ marginTop: 12, fontSize: 13 }}
          >
            {submitting ? '⏳ Retrying…' : '🔄 Retry with AI'}
          </button>
          {error && (
            <div style={{
              background: '#fde7e9', border: '1px solid #d13438', borderRadius: 4,
              padding: '10px 14px', marginTop: 12, fontSize: 13,
            }}>
              <strong style={{ color: '#a4262c' }}>⚠ Retry Result:</strong>
              <p style={{ margin: '4px 0 8px', color: '#a4262c' }}>{error}</p>
              <div style={{
                background: '#fff', border: '1px solid #edebe9', borderRadius: 4,
                padding: '8px 12px', fontFamily: 'Consolas, monospace', fontSize: 11,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#323130',
                userSelect: 'all', cursor: 'text',
              }}>
                {`Session: ${sessionId}\nSource: ${analysis?.source || 'unknown'}\nAI Available: ${analysis_method?.ai_available}\nError: ${aiError || 'N/A'}\nTimestamp: ${new Date().toISOString()}`}
              </div>
              <p style={{ fontSize: 11, color: '#8a8886', marginTop: 6, marginBottom: 0 }}>
                Copy the above and share with the engineering team for troubleshooting.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="alert alert-success">
          <h3 style={{ marginBottom: 6 }}>✓ AI-Powered Analysis Complete</h3>
          <p style={{ margin: 0, fontSize: 13 }}>
            Your submission has been analyzed using advanced AI classification.
            {isLLM && ' The system used Azure OpenAI\'s GPT-4o model to understand the context, intent, and technical requirements of your issue.'}
          </p>
          <ul style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13 }}>
            <li><strong>Analysis Method:</strong> {sourceLabel}</li>
            <li><strong>Confidence Level:</strong> {Math.round((analysis.confidence || 0) * 100)}%</li>
            <li><strong>Source:</strong> {analysis.source || 'unknown'}</li>
          </ul>
          {isLLM && (
            <p style={{ fontSize: 12, marginTop: 8, marginBottom: 0, opacity: 0.85 }}>
              🤖 AI-powered analysis provides superior accuracy by understanding natural language context,
              technical nuances, and business impact rather than relying solely on keyword patterns.
            </p>
          )}
        </div>
      )}

      {/* ── Tab Bar ── */}
      <div className="analysis-tabs">
        <button className={`analysis-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
          <span className="tab-icon">📋</span> Overview
        </button>
        <button className={`analysis-tab ${activeTab === 'analysis' ? 'active' : ''}`} onClick={() => setActiveTab('analysis')}>
          <span className="tab-icon">🧠</span> Analysis
        </button>
        <button className={`analysis-tab ${activeTab === 'decision' ? 'active' : ''}`} onClick={() => setActiveTab('decision')}>
          <span className="tab-icon">🎯</span> Decision
          {domain_entities && <span className="tab-badge">{
            (domain_entities.azure_services?.length || 0) + (domain_entities.technologies?.length || 0) +
            (domain_entities.technical_areas?.length || 0) + (domain_entities.regions?.length || 0) +
            (domain_entities.business_domains?.length || 0) + (domain_entities.discovered_services?.length || 0)
          }</span>}
        </button>
        <button className={`analysis-tab ${activeTab === 'evaluate' ? 'active' : ''}`} onClick={() => setActiveTab('evaluate')}>
          <span className="tab-icon">✅</span> Evaluate
        </button>
      </div>

      {/* ══════════ TAB: Overview ══════════ */}
      {activeTab === 'overview' && (
        <div className="analysis-tab-panel">
          {/* Original Issue */}
          <div className="card">
            <div className="card-header" style={{ background: '#fff4ce', margin: '-24px -24px 16px', padding: '12px 24px', borderRadius: '8px 8px 0 0' }}>
              📋 Original Issue
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <strong>Title:</strong>
                <p style={{ margin: '4px 0' }}>{original_input?.title || '—'}</p>
                <strong>Description:</strong>
                <p style={{ margin: '4px 0', fontSize: 13, whiteSpace: 'pre-wrap' }}>
                  {original_input?.description || '—'}
                </p>
              </div>
              <div>
                <strong>Impact:</strong>
                <p style={{ margin: '4px 0', fontSize: 13 }}>{original_input?.impact || '—'}</p>
              </div>
            </div>
          </div>

          {/* Classification Summary */}
          <div className="card">
            <div className="card-header" style={{ background: '#deecf9', margin: '-24px -24px 16px', padding: '12px 24px', borderRadius: '8px 8px 0 0' }}>
              🤖 System's Classification
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
              <div>
                <strong>Category:</strong><br />
                <CategoryBadge value={analysis.category_display || analysis.category} />
              </div>
              <div>
                <strong>Intent:</strong><br />
                <Badge color="#fff" bg="#27ae60">{formatLabel(analysis.intent_display || analysis.intent)}</Badge>
              </div>
              <div>
                <strong>Business Impact:</strong><br />
                <ImpactBadge level={analysis.business_impact_display || analysis.business_impact} />
              </div>
              <div>
                <strong>Confidence:</strong><br />
                <Badge color="#fff" bg="#2471a3">{Math.round((analysis.confidence || 0) * 100)}%</Badge>
              </div>
            </div>

            {/* Context Summary */}
            {context_summary && (
              <div style={{ marginBottom: 16 }}>
                <strong>Context Summary:</strong>
                <div style={{
                  background: '#f8f9fa', padding: 12, borderRadius: 6,
                  fontSize: 13, marginTop: 6, lineHeight: 1.6,
                }}>
                  {context_summary}
                </div>
              </div>
            )}

            {/* Technical Complexity & Urgency */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <strong>Technical Complexity:</strong><br />
                <ImpactBadge level={technical_complexity} />
              </div>
              <div>
                <strong>Urgency Level:</strong><br />
                <ImpactBadge level={urgency_level} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════ TAB: Analysis ══════════ */}
      {activeTab === 'analysis' && (
        <div className="analysis-tab-panel">
          <div className="card">
            <div className="card-header" style={{ background: '#deecf9', margin: '-24px -24px 16px', padding: '12px 24px', borderRadius: '8px 8px 0 0' }}>
              {isLLM ? '🔍 Comprehensive AI Analysis & Reasoning' : '📊 Pattern-Based Analysis & Reasoning'}
            </div>

            {/* Classification reasoning text */}
            {reasoning && (
              <div style={{ marginBottom: 16 }}>
                <strong>{isLLM ? '🧠 AI Classification Reasoning' : '🧠 Classification Reasoning'}</strong>
                <div style={{
                  background: '#f3f2f1', padding: 14, borderRadius: 6, marginTop: 6,
                  fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap',
                }}>
                  {typeof reasoning === 'object' ? JSON.stringify(reasoning, null, 2) : reasoning}
                </div>
              </div>
            )}

            {/* Pattern Analysis Steps */}
            {pattern_analysis_steps && pattern_analysis_steps.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>📊 Pattern Analysis — Step-by-Step Process</strong>
                <ol style={{ marginTop: 8, paddingLeft: 24, fontSize: 13, lineHeight: 1.8 }}>
                  {pattern_analysis_steps.map((step, i) => (
                    <li key={i} style={{ marginBottom: 2 }}>{step}</li>
                  ))}
                </ol>
              </div>
            )}

            {/* Confidence Breakdown */}
            {confidence_breakdown && confidence_breakdown.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>📈 Confidence Breakdown</strong>
                <ul style={{ marginTop: 8, paddingLeft: 20, fontSize: 13, lineHeight: 1.8 }}>
                  {confidence_breakdown.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Data Sources */}
            {data_sources && data_sources.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>📁 Data Sources Consulted</strong>
                <ul style={{ marginTop: 8, paddingLeft: 20, fontSize: 13, lineHeight: 1.8 }}>
                  {data_sources.map((ds, i) => (
                    <li key={i}>
                      {typeof ds === 'string' ? ds : (
                        <>
                          <strong>{ds.source}</strong>
                          {ds.status && <> — <Badge color={ds.status === 'USED' ? '#fff' : '#323130'} bg={ds.status === 'USED' ? '#107c10' : '#e1dfdd'}>{ds.status}</Badge></>}
                          {ds.reason && <span style={{ marginLeft: 4 }}>{ds.reason}</span>}
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Final Analysis Reasoning */}
            {final_analysis && (final_analysis.category_reason || final_analysis.intent_reason) && (
              <div style={{ marginBottom: 16, background: '#f8f9fa', padding: 12, borderRadius: 6, fontSize: 13 }}>
                {final_analysis.category_reason && (
                  <p style={{ margin: '0 0 6px' }}><strong>Category Reason:</strong> {final_analysis.category_reason}</p>
                )}
                {final_analysis.intent_reason && (
                  <p style={{ margin: '0 0 6px' }}><strong>Intent Reason:</strong> {final_analysis.intent_reason}</p>
                )}
                {final_analysis.data_source_summary && (
                  <p style={{ margin: 0 }}><strong>Data Sources:</strong> {final_analysis.data_source_summary}</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════ TAB: Decision ══════════ */}
      {activeTab === 'decision' && (
        <div className="analysis-tab-panel">
          <div className="card">
            <div className="card-header" style={{ background: '#fde7e9', margin: '-24px -24px 16px', padding: '12px 24px', borderRadius: '8px 8px 0 0' }}>
              🎯 Final Decision Summary
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong>Category Decision:</strong>{' '}
              <CategoryBadge value={analysis.category_display || analysis.category} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <strong>Intent:</strong>{' '}
              <Badge color="#fff" bg="#27ae60">{formatLabel(analysis.intent_display || analysis.intent)}</Badge>
            </div>
            <div style={{ marginBottom: 12 }}>
              <strong>Business Impact:</strong>{' '}
              <ImpactBadge level={analysis.business_impact_display || analysis.business_impact} />
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>Confidence Level:</strong>{' '}
              <Badge color="#fff" bg="#2471a3">{Math.round((analysis.confidence || 0) * 100)}%</Badge>
            </div>

            {isLLM ? (
              <div className="alert alert-info" style={{ fontSize: 12, marginBottom: 16 }}>
                ℹ️ This analysis was performed using Azure OpenAI's GPT-4o model with advanced natural language understanding.
              </div>
            ) : (
              <div style={{
                background: '#fff4ce', border: '1px solid #ffb900', borderRadius: 6,
                padding: '10px 14px', fontSize: 12, marginBottom: 16, color: '#8a6d3b',
              }}>
                ⚠️ This analysis was performed using rule-based pattern matching. AI classification was unavailable.
              </div>
            )}

            {/* Key Concepts */}
            {key_concepts?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <strong>Key Concepts Identified:</strong><br />
                <div style={{ marginTop: 4 }}>
                  {key_concepts.map((c, i) => (
                    <Badge key={i} color="#fff" bg="#34495e">{c}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Semantic Keywords */}
            {semantic_keywords?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <strong>Semantic Keywords:</strong><br />
                <div style={{ marginTop: 4 }}>
                  {semantic_keywords.map((k, i) => (
                    <Badge key={i} color="#fff" bg="#2980b9">{k}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Domain Entities */}
            {domain_entities && (
              <div style={{ marginTop: 16 }}>
                <strong>Domain Entities Detected:</strong>
                <div style={{ marginTop: 8 }}>
                  {domain_entities.azure_services?.length > 0 && (
                    <CollapsibleSection title="Services" count={domain_entities.azure_services.length} defaultOpen={true}>
                      <div>{domain_entities.azure_services.map((s, i) => <Badge key={i} bg="#deecf9" color="#0078d4">{s}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                  {domain_entities.technologies?.length > 0 && (
                    <CollapsibleSection title="Technologies" count={domain_entities.technologies.length} defaultOpen={true}>
                      <div>{domain_entities.technologies.map((t, i) => <Badge key={i} bg="#e8daef" color="#6c3483">{t}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                  {domain_entities.technical_areas?.length > 0 && (
                    <CollapsibleSection title="Technical Areas" count={domain_entities.technical_areas.length}>
                      <div>{domain_entities.technical_areas.map((t, i) => <Badge key={i} bg="#d5f5e3" color="#1e8449">{t}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                  {domain_entities.business_domains?.length > 0 && (
                    <CollapsibleSection title="Business Domains" count={domain_entities.business_domains.length}>
                      <div>{domain_entities.business_domains.map((b, i) => <Badge key={i} bg="#fde7e9" color="#d13438">{b}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                  {domain_entities.regions?.length > 0 && (
                    <CollapsibleSection title="Regions" count={domain_entities.regions.length}>
                      <div>{domain_entities.regions.map((r, i) => <Badge key={i} bg="#d6eaf8" color="#2471a3">{r}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                  {domain_entities.discovered_services?.length > 0 && (
                    <CollapsibleSection title="Discovered Services" count={domain_entities.discovered_services.length}>
                      <div>{domain_entities.discovered_services.map((s, i) => <Badge key={i} bg="#fde7e9" color="#a93226">{s}</Badge>)}</div>
                    </CollapsibleSection>
                  )}
                </div>
              </div>
            )}

            {/* Search Strategy */}
            {search_strategy && Object.keys(search_strategy).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <strong>Recommended Search Strategy:</strong>
                <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
                  {Object.entries(search_strategy).map(([key, val]) => (
                    <div key={key} style={{ fontSize: 13 }}>
                      {val === true && <span>✔ {formatLabel(key)}</span>}
                      {val === false && <span style={{ opacity: 0.5 }}>✗ {formatLabel(key)}</span>}
                      {typeof val === 'string' && <span>✔ {formatLabel(key)}: {val}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════ TAB: Evaluate ══════════ */}
      {activeTab === 'evaluate' && (
        <div className="analysis-tab-panel">
          <div className="card">
            <div className="card-header" style={{ background: '#dff6dd', margin: '-24px -24px 16px', padding: '12px 24px', borderRadius: '8px 8px 0 0' }}>
              ✅ Your Evaluation
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong>Is this analysis correct?</strong>

              <div style={{ marginTop: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 8 }}>
                  <input
                    type="radio"
                    name="eval"
                    checked={evalCorrect === true}
                    onChange={() => setEvalCorrect(true)}
                    style={{ accentColor: 'var(--color-success)' }}
                  />
                  <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>
                    ✔ Yes, this analysis is correct — proceed with matching
                  </span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="eval"
                    checked={evalCorrect === false}
                    onChange={() => {
                      setEvalCorrect(false);
                      if (!correctedCategory) setCorrectedCategory(analysis?.category || '');
                      if (!correctedIntent) setCorrectedIntent(analysis?.intent || '');
                      if (!correctedImpact) setCorrectedImpact(analysis?.business_impact || '');
                    }}
                    style={{ accentColor: 'var(--color-danger)' }}
                  />
                  <span style={{ color: 'var(--color-danger)', fontWeight: 600 }}>
                    ✗ No, this analysis needs correction
                  </span>
                </label>
              </div>
            </div>

            {/* Correction Dropdowns */}
            {evalCorrect === false && (
              <div style={{
                background: 'var(--color-bg-secondary, #f3f2f1)', border: '1px solid var(--color-border, #edebe9)',
                borderLeft: '4px solid var(--color-primary, #0078d4)', borderRadius: 6, padding: 16, marginBottom: 16,
              }}>
                <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-primary, #0078d4)', margin: '0 0 12px 0' }}>
                  Please provide the correct analysis:
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Correct Category:</label>
                    <select
                      value={correctedCategory}
                      onChange={(e) => setCorrectedCategory(e.target.value)}
                      style={{ width: '100%', padding: '6px 10px', border: '1px solid var(--color-border, #8a8886)', borderRadius: 4, fontSize: 13 }}
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
                  <div>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Correct Intent:</label>
                    <select
                      value={correctedIntent}
                      onChange={(e) => setCorrectedIntent(e.target.value)}
                      style={{ width: '100%', padding: '6px 10px', border: '1px solid var(--color-border, #8a8886)', borderRadius: 4, fontSize: 13 }}
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
                  <div>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Correct Business Impact:</label>
                    <select
                      value={correctedImpact}
                      onChange={(e) => setCorrectedImpact(e.target.value)}
                      style={{ width: '100%', padding: '6px 10px', border: '1px solid var(--color-border, #8a8886)', borderRadius: 4, fontSize: 13 }}
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

            <div className="form-group">
              <label>{evalCorrect === false ? 'Explain why the analysis is wrong:' : 'General Feedback (optional):'}</label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={3}
                placeholder={evalCorrect === false
                  ? 'Please explain why the system\'s analysis was incorrect and provide any additional context...'
                  : 'Any additional feedback to help improve the system...'}
              />
            </div>

            {error && <div className="alert alert-danger" style={{ fontSize: 13 }}>{error}</div>}

            <div className="btn-group" style={{ justifyContent: 'center' }}>
              {evalCorrect === false && (
                <>
                  <button className="btn btn-primary" onClick={handleReanalyze} disabled={submitting}>
                    🔄 Reanalyze with Corrections
                  </button>
                  <button className="btn btn-success" onClick={handleSaveCorrections} disabled={submitting}>
                    💾 Save Corrections Only
                  </button>
                </>
              )}
              {evalCorrect === true && (
                <button
                  className="btn btn-success"
                  onClick={async () => {
                    setSubmitting(true);
                    try {
                      await submitCorrection({
                        session_id: sessionId,
                        action: 'approve',
                        correction_notes: feedback || undefined,
                      });
                      navigate('/searching', { state: { sessionId } });
                    } catch (err) { setError(err.message); }
                    finally { setSubmitting(false); }
                  }}
                  disabled={submitting}
                >
                  ✔ Approve & Continue to Search →
                </button>
              )}
            </div>

            {evalCorrect === null && (
              <div style={{ textAlign: 'center', marginTop: 8, fontSize: 13, color: 'var(--color-text-secondary)' }}>
                ⚠ Please select an option above
              </div>
            )}

            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <button className="btn btn-secondary" onClick={() => navigate('/')} style={{ fontSize: 13 }}>
                ✗ Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
