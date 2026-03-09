/**
 * GuidanceBanner — renders category-specific guidance alerts.
 */
import React from 'react';

export default function GuidanceBanner({ guidance }) {
  if (!guidance) return null;

  const variantClass = `alert alert-${guidance.variant || 'info'}`;

  return (
    <div className={variantClass}>
      <h3>{guidance.title}</h3>
      {guidance.items && guidance.items.length > 0 && (
        <ul>
          {guidance.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
      {guidance.links && Object.keys(guidance.links).length > 0 && (
        <div style={{ marginTop: 8 }}>
          {Object.entries(guidance.links).map(([label, url]) => (
            <a
              key={label}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
              style={{ marginRight: 8, marginBottom: 4 }}
            >
              {label} ↗
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
