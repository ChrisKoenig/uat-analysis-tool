/**
 * ConfidenceBar — horizontal bar showing confidence / quality score.
 */
import React from 'react';

export default function ConfidenceBar({ value, label = '', max = 100 }) {
  const pct = Math.round((value / max) * 100);
  const colorClass = pct >= 80 ? 'score-high' : pct >= 50 ? 'score-medium' : 'score-low';

  return (
    <div style={{ marginBottom: 8 }}>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
          <span>{label}</span>
          <span style={{ fontWeight: 600 }}>{typeof value === 'number' && value <= 1 ? `${(value * 100).toFixed(0)}%` : `${pct}%`}</span>
        </div>
      )}
      <div className="score-bar">
        <div className={`score-bar-fill ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
