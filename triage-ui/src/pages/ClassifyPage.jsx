/**
 * ClassifyPage — Quick ICA / Standalone Classifier
 * ===================================================
 *
 * Paste a title and description, get instant AI + pattern
 * classification — no ADO coupling, no Cosmos writes.
 *
 * This is the new-platform replacement for the legacy Flask
 * "Quick ICA" form in app.py.
 */

import React, { useState, useRef } from 'react';
import * as api from '../api/triageApi';
import './ClassifyPage.css';


export default function ClassifyPage({ addToast }) {
  // ── State ────────────────────────────────────────────────────
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [impact, setImpact] = useState('');
  const [includeDetails, setIncludeDetails] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiStatus, setAiStatus] = useState(null);
  const titleRef = useRef(null);


  // ── AI Status Check ──────────────────────────────────────────
  React.useEffect(() => {
    api.getClassifyStatus()
      .then(setAiStatus)
      .catch(() => null);
  }, []);


  // ── Submit ───────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim()) {
      addToast?.('Title is required', 'error');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await api.classify({
        title: title.trim(),
        description: description.trim(),
        impact: impact.trim(),
        include_pattern_details: includeDetails,
      });
      setResult(res);
    } catch (err) {
      addToast?.(err.message || 'Classification failed', 'error');
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    setTitle('');
    setDescription('');
    setImpact('');
    setResult(null);
    titleRef.current?.focus();
  }

  function confidenceClass(c) {
    if (c >= 0.8) return 'high';
    if (c >= 0.5) return 'medium';
    return 'low';
  }

  function formatCategory(cat) {
    return (cat || '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase());
  }


  // ── Render ───────────────────────────────────────────────────
  return (
    <div className="classify-page">
      <h1>Classify</h1>
      <p style={{ color: 'var(--text-light)', marginBottom: 'var(--space-lg)' }}>
        Paste a title and description to get instant AI classification — no ADO required.
      </p>

      {/* AI status banner */}
      {aiStatus && (
        <div className={`classify-ai-banner ${aiStatus.ai_available ? 'available' : 'unavailable'}`}>
          <span>{aiStatus.ai_available ? '🤖' : '⚠️'}</span>
          <span>
            {aiStatus.ai_available
              ? `AI engine active (${aiStatus.mode})`
              : `AI unavailable — pattern matching only`}
          </span>
        </div>
      )}

      {/* Input form */}
      <form className="classify-form" onSubmit={handleSubmit}>
        <div className="classify-field">
          <label htmlFor="classify-title">Title *</label>
          <input
            id="classify-title"
            ref={titleRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., SQL MI in West Europe availability"
            autoFocus
          />
        </div>

        <div className="classify-field">
          <label htmlFor="classify-desc">Description</label>
          <textarea
            id="classify-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Paste the full description or body text here..."
          />
          <div className="field-hint">
            The more detail you provide, the more accurate the classification.
          </div>
        </div>

        <div className="classify-field">
          <label htmlFor="classify-impact">Business Impact</label>
          <input
            id="classify-impact"
            type="text"
            value={impact}
            onChange={(e) => setImpact(e.target.value)}
            placeholder="e.g., Blocking production deployment"
          />
        </div>

        <div className="classify-actions">
          <button type="submit" className="btn btn-primary" disabled={loading || !title.trim()}>
            {loading ? 'Analyzing…' : 'Classify'}
          </button>
          <button type="button" className="btn btn-default" onClick={handleClear}>
            Clear
          </button>
          <label style={{ fontSize: 'var(--font-size-sm)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input
              type="checkbox"
              checked={includeDetails}
              onChange={(e) => setIncludeDetails(e.target.checked)}
            />
            Include pattern details
          </label>
        </div>
      </form>

      {/* Results */}
      {result && (
        <div className="classify-result">
          <div className="classify-result-header">
            <h2>Classification Result</h2>
            <span className="classify-elapsed">{result.elapsed_ms}ms</span>
          </div>

          {/* Primary cards */}
          <div className="classify-primary">
            <div className="classify-card">
              <div className="classify-card-label">Category</div>
              <div className="classify-card-value">
                {formatCategory(result.category)}
              </div>
            </div>
            <div className="classify-card">
              <div className="classify-card-label">Intent</div>
              <div className="classify-card-value">
                {formatCategory(result.intent)}
              </div>
            </div>
            <div className="classify-card">
              <div className="classify-card-label">Business Impact</div>
              <div className="classify-card-value">
                {formatCategory(result.business_impact)}
              </div>
            </div>
            <div className="classify-card">
              <div className="classify-card-label">Source</div>
              <div className="classify-card-value">
                <span className={`source-badge ${result.source}`}>
                  {result.source}
                </span>
                {result.agreement && <span style={{ marginLeft: '8px', fontSize: 'var(--font-size-xs)' }}>✓ agreed</span>}
              </div>
            </div>
          </div>

          {/* Confidence bar */}
          <div className="classify-card" style={{ marginBottom: 'var(--space-md)' }}>
            <div className="classify-card-label">Confidence</div>
            <div className="confidence-bar-container">
              <div className="confidence-bar">
                <div
                  className={`confidence-bar-fill ${confidenceClass(result.confidence)}`}
                  style={{ width: `${Math.round(result.confidence * 100)}%` }}
                />
              </div>
              <span className="confidence-value">
                {Math.round(result.confidence * 100)}%
              </span>
            </div>
          </div>

          {/* Urgency / Complexity */}
          {(result.urgency_level || result.technical_complexity) && (
            <div className="classify-primary" style={{ marginBottom: 'var(--space-md)' }}>
              {result.urgency_level && (
                <div className="classify-card">
                  <div className="classify-card-label">Urgency</div>
                  <div className="classify-card-value">{formatCategory(result.urgency_level)}</div>
                </div>
              )}
              {result.technical_complexity && (
                <div className="classify-card">
                  <div className="classify-card-label">Technical Complexity</div>
                  <div className="classify-card-value">{formatCategory(result.technical_complexity)}</div>
                </div>
              )}
            </div>
          )}

          {/* Context summary */}
          {result.context_summary && (
            <div className="classify-enrichments">
              <h3>Context Summary</h3>
              <div className="classify-reasoning">
                {result.context_summary}
              </div>
            </div>
          )}

          {/* Reasoning */}
          {result.reasoning && (
            <div className="classify-enrichments">
              <h3>Reasoning</h3>
              <div className="classify-reasoning">
                {typeof result.reasoning === 'string'
                  ? result.reasoning
                  : JSON.stringify(result.reasoning, null, 2)}
              </div>
            </div>
          )}

          {/* Keywords & Concepts */}
          {(result.semantic_keywords?.length > 0 || result.key_concepts?.length > 0) && (
            <div className="classify-enrichments">
              {result.semantic_keywords?.length > 0 && (
                <>
                  <h3>Semantic Keywords</h3>
                  <div className="classify-tags">
                    {result.semantic_keywords.map((kw, i) => (
                      <span key={i} className="classify-tag">{kw}</span>
                    ))}
                  </div>
                </>
              )}
              {result.key_concepts?.length > 0 && (
                <>
                  <h3 style={{ marginTop: 'var(--space-md)' }}>Key Concepts</h3>
                  <div className="classify-tags">
                    {result.key_concepts.map((c, i) => (
                      <span key={i} className="classify-tag">{c}</span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Domain entities */}
          {result.domain_entities && Object.keys(result.domain_entities).length > 0 && (
            <div className="classify-enrichments">
              <h3>Detected Entities</h3>
              {Object.entries(result.domain_entities).map(([key, vals]) => (
                vals && vals.length > 0 && (
                  <div key={key} style={{ marginBottom: 'var(--space-sm)' }}>
                    <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)', textTransform: 'capitalize' }}>
                      {key.replace(/_/g, ' ')}:
                    </span>{' '}
                    <span className="classify-tags" style={{ display: 'inline-flex' }}>
                      {vals.map((v, i) => (
                        <span key={i} className="classify-tag">{v}</span>
                      ))}
                    </span>
                  </div>
                )
              ))}
            </div>
          )}

          {/* Pattern details (if requested) */}
          {result.pattern_details && (
            <div className="classify-enrichments">
              <h3>Pattern Matching Evidence</h3>
              <div className="classify-reasoning">
                {JSON.stringify(result.pattern_details, null, 2)}
              </div>
            </div>
          )}

          {/* AI error notice */}
          {result.ai_error && (
            <div className="classify-ai-banner unavailable" style={{ marginTop: 'var(--space-md)' }}>
              <span>⚠️</span>
              <span>AI error: {result.ai_error} — results are from pattern matching only</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
