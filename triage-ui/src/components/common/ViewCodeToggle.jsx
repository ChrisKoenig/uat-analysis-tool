/**
 * ViewCodeToggle — DSL / JSON View
 * ==================================
 *
 * Toggle button that switches between the visual editor
 * and a raw code / DSL view of an entity's configuration.
 * Useful for power users who want to see the underlying data.
 *
 * Props:
 *   data       : any — the data to display as JSON / DSL
 *   dslText    : string | null — optional DSL representation
 *   label      : string — toggle button label
 */

import React, { useState } from 'react';
import './ViewCodeToggle.css';


export default function ViewCodeToggle({ data, dslText = null, label = 'View Code' }) {
  const [showCode, setShowCode] = useState(false);

  const displayText = dslText || JSON.stringify(data, null, 2);

  return (
    <div className="view-code-toggle">
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => setShowCode(!showCode)}
        title={showCode ? 'Hide code view' : 'Show code view'}
      >
        {showCode ? '🔽 Hide Code' : `🔧 ${label}`}
      </button>

      {showCode && (
        <pre className="view-code-block">
          <code>{displayText}</code>
        </pre>
      )}
    </div>
  );
}
