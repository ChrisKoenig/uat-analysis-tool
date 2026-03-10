/**
 * Steps 3-4: Analysis Results + Review / Correction
 *
 * Displays the AI classification results in a summary view:
 *   - Category, Intent, Business Impact, Technical Complexity (colour-coded badges)
 *   - Confidence bar (0-100%)
 *   - AI Reasoning with structured breakdown (data sources, products, etc.)
 *   - AI offline warning with "Retry with AI" button when pattern fallback was used
 *
 * User actions:
 *   - "Looks Good — Continue" → approve and navigate to /searching (Step 5)
 *   - "Modify Classification"  → expand correction form (Step 4)
 *   - "Reject & Start Over"    → discard session, back to /
 *   - "See Detailed Analysis"  → navigate to /analysis/detail/{sid}
 *
 * Correction form allows overriding category, intent, business impact, and
 * adding notes. Can either "Reanalyze" (re-run AI with hints) or
 * "Save Corrections & Continue" (persist feedback for learning).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import ProgressStepper from '../components/ProgressStepper';
import ConfidenceBar from '../components/ConfidenceBar';
import { submitCorrection, analyzeContext } from '../api/fieldApi';
import { useWizard } from '../auth/WizardContext';

const DEFLECT_CATEGORIES = new Set([
  'technical_support', 'cost_billing', 'aoai_capacity',
  'capacity', 'support', 'support_escalation',
]);

const CATEGORIES = [
  'technical_support', 'feature_request', 'cost_billing', 'capacity',
  'aoai_capacity', 'service_request', 'information', 'general',
];

const INTENTS = [
  'escalation', 'information', 'action_required', 'consultation',
  'feature_request', 'general',
];

const IMPACTS = ['low', 'medium', 'high', 'critical'];

/* Format raw snake_case or lowercase values for display */
function formatValue(s) {
  if (!s) return '—';
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function AnalysisPage() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const sessionId = state?.sessionId;
  const data = state?.analysisData;
  const { cacheStep, setFlowPath } = useWizard();

  // Cache for backward navigation (steps 3 & 4 share this route)
  useEffect(() => {
    if (data && sessionId) {
      const cached = { analysisData: data, sessionId };
      cacheStep(3, cached);
      cacheStep(4, cached);
    }
  }, [data, sessionId, cacheStep]);

  const [showCorrection, setShowCorrection] = useState(false);
  const [corrCategory, setCorrCategory] = useState('');
  const [corrIntent, setCorrIntent] = useState('');
  const [corrImpact, setCorrImpact] = useState('');
  const [corrNotes, setCorrNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState('');

  if (!data || !sessionId) {
    navigate('/');
    return null;
  }

  const { analysis, original_input } = data;

  const aiOffline = analysis.ai_available === false
    || (analysis.source || '').toLowerCase().includes('pattern')
    || (analysis.source || '').toLowerCase().includes('fallback');

  const handleRetryAI = async () => {
    setRetrying(true);
    setError('');
    try {
      const result = await analyzeContext(sessionId);
      const retryAnalysis = result?.analysis;
      // If AI is still unavailable after retry, show the specific error
      if (retryAnalysis?.ai_available === false
          || (retryAnalysis?.source || '').toLowerCase().includes('pattern')
          || (retryAnalysis?.source || '').toLowerCase().includes('fallback')) {
        const reason = retryAnalysis?.ai_error || 'Azure OpenAI service is still unreachable';
        setError(`AI is still unavailable: ${reason}`);
        // Update the page with latest results anyway
        navigate('/analysis', {
          state: { analysisData: result, sessionId },
          replace: true,
        });
      } else {
        // AI worked this time!
        navigate('/analysis', {
          state: { analysisData: result, sessionId },
          replace: true,
        });
      }
    } catch (err) {
      setError(`Retry failed: ${err.message}`);
    } finally {
      setRetrying(false);
    }
  };

  const handleViewDetail = () => {
    navigate(`/analysis/detail/${sessionId}`);
  };

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await submitCorrection({ session_id: sessionId, action: 'approve' });
      setFlowPath(DEFLECT_CATEGORIES.has(analysis.category) ? 'deflect' : 'create_uat');
      navigate('/searching', { state: { sessionId, category: analysis.category } });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReanalyze = async () => {
    setSubmitting(true);
    setError('');
    try {
      const result = await submitCorrection({
        session_id: sessionId,
        action: 'reanalyze',
        correct_category: corrCategory || undefined,
        correct_intent: corrIntent || undefined,
        correct_business_impact: corrImpact || undefined,
        correction_notes: corrNotes || undefined,
      });
      // Show updated analysis
      navigate('/analysis', {
        state: {
          analysisData: {
            ...data,
            analysis: result.updated_analysis || analysis,
          },
          sessionId,
        },
        replace: true,
      });
      setShowCorrection(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveCorrections = async () => {
    setSubmitting(true);
    try {
      await submitCorrection({
        session_id: sessionId,
        action: 'save_corrections',
        correct_category: corrCategory || undefined,
        correct_intent: corrIntent || undefined,
        correct_business_impact: corrImpact || undefined,
        correction_notes: corrNotes || undefined,
      });
      const effectiveCategory = corrCategory || analysis.category;
      setFlowPath(DEFLECT_CATEGORIES.has(effectiveCategory) ? 'deflect' : 'create_uat');
      navigate('/searching', { state: { sessionId, category: effectiveCategory } });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    await submitCorrection({ session_id: sessionId, action: 'reject' });
    navigate('/');
  };

  return (
    <>
      <ProgressStepper currentStep={showCorrection ? 4 : 3} />
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="card-header" style={{ border: 'none', marginBottom: 0, paddingBottom: 0 }}>Context Analysis</div>
          <button className="btn btn-secondary" onClick={handleViewDetail} style={{ fontSize: 13 }}>
            🔍 See Detailed Analysis
          </button>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* AI Offline Warning */}
        {aiOffline && (
          <div style={{
            background: '#fff4ce', border: '1px solid #ffb900', borderRadius: 6,
            padding: '14px 18px', marginTop: 8, marginBottom: 8,
            display: 'flex', alignItems: 'flex-start', gap: 12,
          }}>
            <span style={{ fontSize: 22, lineHeight: 1 }}>⚠️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: '#8a6d3b', marginBottom: 4 }}>
                AI Classification Unavailable — Pattern Matching Used
              </div>
              <p style={{ fontSize: 13, color: '#605e5c', margin: '0 0 6px', lineHeight: 1.5 }}>
                The Azure OpenAI service was not available for this analysis. Results were generated using
                rule-based pattern matching, which may be less accurate. Confidence and classifications
                should be reviewed carefully.
              </p>
              {analysis.ai_error && (
                <p style={{ fontSize: 12, color: '#a4262c', margin: '0 0 6px', fontFamily: 'monospace' }}>
                  Error: {analysis.ai_error}
                </p>
              )}
              <button
                className="btn btn-primary"
                onClick={handleRetryAI}
                disabled={retrying}
                style={{ fontSize: 13, padding: '6px 16px', marginTop: 4 }}
              >
                {retrying ? '⏳ Retrying…' : '🔄 Retry with AI'}
              </button>
            </div>
          </div>
        )}

        {/* Analysis Results */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 8 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#605e5c', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Category</div>
            <span style={{
              display: 'inline-block', padding: '4px 14px', borderRadius: 14,
              fontSize: 15, fontWeight: 600, color: '#fff', background: '#0078d4',
            }}>
              {formatValue(analysis.category_display || analysis.category)}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#605e5c', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Intent</div>
            <span style={{
              display: 'inline-block', padding: '4px 14px', borderRadius: 14,
              fontSize: 15, fontWeight: 600, color: '#fff', background: '#27ae60',
            }}>
              {formatValue(analysis.intent_display || analysis.intent)}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#605e5c', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Business Impact</div>
            <span style={{
              display: 'inline-block', padding: '4px 14px', borderRadius: 14,
              fontSize: 15, fontWeight: 600, color: '#fff',
              background: { critical: '#d13438', high: '#d13438', medium: '#ffb900', low: '#107c10' }[(analysis.business_impact || '').toLowerCase()] || '#8a8886',
            }}>
              {formatValue(analysis.business_impact_display || analysis.business_impact)}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#605e5c', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Technical Complexity</div>
            <span style={{
              display: 'inline-block', padding: '4px 14px', borderRadius: 14,
              fontSize: 15, fontWeight: 600, color: '#fff',
              background: { critical: '#d13438', high: '#d13438', medium: '#ffb900', low: '#107c10' }[(analysis.technical_complexity || '').toLowerCase()] || '#8a8886',
            }}>
              {formatValue(analysis.technical_complexity)}
            </span>
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <ConfidenceBar
            value={analysis.confidence}
            label="Confidence"
            max={1}
          />
        </div>

        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`badge badge-${analysis.source || 'pattern'}`}>
            Source: {analysis.source || 'pattern'}
          </span>
          {!aiOffline && (
            <span style={{
              display: 'inline-block', padding: '2px 8px', borderRadius: 10,
              fontSize: 11, fontWeight: 600, color: '#107c10', background: '#dff6dd',
            }}>
              ✓ AI Powered
            </span>
          )}
        </div>

        {/* AI Reasoning — formatted summary */}
        {analysis.reasoning && (
          <div style={{ marginTop: 16 }}>
            <h3>AI Reasoning</h3>

            {/* Context Summary — only shown when reasoning is structured (object),
                because when reasoning is a plain string it IS the context summary */}
            {analysis.context_summary && typeof analysis.reasoning === 'object' && (
              <p style={{ fontSize: 14, lineHeight: 1.6, color: '#323130', marginBottom: 12 }}>
                {analysis.context_summary}
              </p>
            )}

            {typeof analysis.reasoning === 'object' ? (
              <>
                {/* Classification Reasoning */}
                {analysis.reasoning.first_analysis && (
                  <div style={{ background: '#f3f2f1', padding: 14, borderRadius: 6, marginBottom: 12 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: '#0078d4' }}>Classification Reasoning</div>
                    {analysis.reasoning.first_analysis.category_reason && (
                      <p style={{ fontSize: 13, margin: '4px 0' }}><strong>Category:</strong> {analysis.reasoning.first_analysis.category_reason}</p>
                    )}
                    {analysis.reasoning.first_analysis.intent_reason && (
                      <p style={{ fontSize: 13, margin: '4px 0' }}><strong>Intent:</strong> {analysis.reasoning.first_analysis.intent_reason}</p>
                    )}
                    {analysis.reasoning.first_analysis.data_source_summary && (
                      <p style={{ fontSize: 13, margin: '4px 0', color: '#605e5c' }}>{analysis.reasoning.first_analysis.data_source_summary}</p>
                    )}
                  </div>
                )}

                {/* Data Sources Consulted */}
                {analysis.reasoning.data_sources_used?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Data Sources Consulted</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                      {analysis.reasoning.data_sources_used.map((ds, i) => (
                        <div key={i} style={{
                          padding: '8px 12px', borderRadius: 4, fontSize: 12,
                          background: ds.status === 'USED' ? '#e6f4ea' : ds.status === 'AVAILABLE' ? '#fff3e0' : '#f3f2f1',
                          border: `1px solid ${ds.status === 'USED' ? '#a8dab5' : ds.status === 'AVAILABLE' ? '#ffe0b2' : '#edebe9'}`,
                        }}>
                          <div style={{ fontWeight: 600 }}>
                            <span style={{
                              display: 'inline-block', width: 8, height: 8, borderRadius: '50%', marginRight: 6,
                              background: ds.status === 'USED' ? '#107c10' : ds.status === 'AVAILABLE' ? '#ffb900' : '#8a8886',
                            }} />
                            {ds.source}
                          </div>
                          <div style={{ color: '#605e5c', marginTop: 2 }}>{ds.reason}</div>
                          {ds.matches_found?.length > 0 && (
                            <div style={{ marginTop: 4 }}>
                              {ds.matches_found.map((m, j) => (
                                <span key={j} className="badge" style={{ background: '#e1dfdd', marginRight: 4, fontSize: 11 }}>{m}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Skipped Sources (collapsed) */}
                {analysis.reasoning.data_sources_skipped?.length > 0 && (
                  <div style={{ marginBottom: 12, fontSize: 12, color: '#8a8886' }}>
                    <strong>Skipped:</strong>{' '}
                    {analysis.reasoning.data_sources_skipped.map(ds => ds.source).join(', ')}
                  </div>
                )}

                {/* Confidence Breakdown */}
                {analysis.reasoning.confidence_breakdown && typeof analysis.reasoning.confidence_breakdown === 'object' && (
                  <div style={{ marginBottom: 12, background: '#f3f2f1', padding: 12, borderRadius: 6 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Confidence Breakdown</div>
                    <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13 }}>
                      {Object.entries(analysis.reasoning.confidence_breakdown).map(([key, val]) => (
                        <div key={key}>
                          <span style={{ color: '#605e5c' }}>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:</span>{' '}
                          <strong>{typeof val === 'number' ? `${Math.round(val * 100)}%` : val}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Microsoft Products Detected */}
                {analysis.reasoning.microsoft_products?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Microsoft Products Detected</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {analysis.reasoning.microsoft_products.map((p, i) => (
                        <a key={i} href={p.url} target="_blank" rel="noopener noreferrer"
                          style={{
                            padding: '4px 12px', borderRadius: 14, fontSize: 12,
                            background: '#e8f0fe', color: '#0078d4', textDecoration: 'none',
                            border: '1px solid #c7dffc',
                          }}>
                          {p.title || p.name}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* Fallback: plain-text reasoning */
              <div style={{
                background: '#f3f2f1', padding: 12, borderRadius: 4,
                fontSize: 13, whiteSpace: 'pre-wrap',
              }}>
                {analysis.reasoning}
              </div>
            )}
          </div>
        )}

        {/* Key Concepts */}
        {analysis.key_concepts?.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>Key Concepts:</strong>{' '}
            {analysis.key_concepts.map((c, i) => (
              <span key={i} className="badge" style={{ background: '#eee', marginRight: 4 }}>
                {c}
              </span>
            ))}
          </div>
        )}

        {/* Approve / Modify Actions */}
        {!showCorrection && (
          <div className="btn-group">
            <button className="btn btn-success" onClick={handleApprove} disabled={submitting}>
              Looks Good — Continue →
            </button>
            <button className="btn btn-secondary" onClick={() => setShowCorrection(true)}>
              Modify Classification
            </button>
            <button className="btn btn-danger" onClick={handleReject} disabled={submitting}>
              Reject & Start Over
            </button>
          </div>
        )}

        {/* Correction Form */}
        {showCorrection && (
          <div style={{ marginTop: 24, paddingTop: 16, borderTop: '2px solid var(--color-border)' }}>
            <h3>Correct Classification</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group">
                <label>Correct Category</label>
                <select value={corrCategory} onChange={(e) => setCorrCategory(e.target.value)}>
                  <option value="">— Keep current —</option>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label>Correct Intent</label>
                <select value={corrIntent} onChange={(e) => setCorrIntent(e.target.value)}>
                  <option value="">— Keep current —</option>
                  {INTENTS.map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label>Correct Business Impact</label>
                <select value={corrImpact} onChange={(e) => setCorrImpact(e.target.value)}>
                  <option value="">— Keep current —</option>
                  {IMPACTS.map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label>Notes</label>
              <textarea
                value={corrNotes}
                onChange={(e) => setCorrNotes(e.target.value)}
                rows={3}
                placeholder="Why is the classification incorrect? What should it be?"
              />
            </div>

            <div className="btn-group">
              <button className="btn btn-primary" onClick={handleReanalyze} disabled={submitting}>
                Reanalyze with Corrections
              </button>
              <button className="btn btn-success" onClick={handleSaveCorrections} disabled={submitting}>
                Save Corrections & Continue
              </button>
              <button className="btn btn-secondary" onClick={() => setShowCorrection(false)}>
                Cancel Edits
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
