/**
 * MultiFieldCombobox — Multi-Select ADO Field Picker
 * =====================================================
 *
 * Allows the user to select **multiple** ADO fields.
 * Selected fields appear as removable chips above the search input.
 * The dropdown is identical to FieldCombobox but clicking a field
 * toggles it in/out of the selection instead of replacing the value.
 *
 * Props:
 *   values     : string[]           — selected field reference names
 *   onChange   : (string[]) => void  — callback with updated array
 *   fields     : Array               — field schema objects from the API
 *   id         : string
 *   placeholder: string
 *   required   : boolean
 *   loading    : boolean
 */

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import './MultiFieldCombobox.css';


export default function MultiFieldCombobox({
  values = [],
  onChange,
  fields = [],
  id,
  placeholder = 'Search and select fields…',
  required = false,
  loading = false,
}) {
  const [searchText, setSearchText] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef(null);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  // ── Close on outside click ─────────────────────────────────
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
        setSearchText('');
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // ── Filter fields by search text ───────────────────────────
  const filtered = useMemo(() => {
    if (!searchText.trim()) return fields;
    const q = searchText.toLowerCase();
    return fields.filter(
      (f) =>
        f.displayName.toLowerCase().includes(q) ||
        f.id.toLowerCase().includes(q) ||
        (f.description || '').toLowerCase().includes(q)
    );
  }, [searchText, fields]);

  // ── Selected set for quick lookup ──────────────────────────
  const selectedSet = useMemo(() => new Set(values), [values]);

  // ── Toggle a field in the selection ────────────────────────
  const toggleField = useCallback(
    (refName) => {
      if (selectedSet.has(refName)) {
        onChange(values.filter((v) => v !== refName));
      } else {
        onChange([...values, refName]);
      }
      setSearchText('');
      // Keep focus so the user can continue selecting
      setTimeout(() => inputRef.current?.focus(), 0);
    },
    [values, onChange, selectedSet]
  );

  // ── Remove a chip ──────────────────────────────────────────
  const removeField = useCallback(
    (refName) => {
      onChange(values.filter((v) => v !== refName));
    },
    [values, onChange]
  );

  // ── Input handlers ─────────────────────────────────────────
  const handleInputChange = (e) => {
    setSearchText(e.target.value);
    setOpen(true);
    setHighlightIndex(-1);
  };

  const handleFocus = () => {
    setOpen(true);
    setHighlightIndex(-1);
  };

  const handleKeyDown = (e) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        e.preventDefault();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex((prev) => Math.min(prev + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex >= 0 && highlightIndex < filtered.length) {
          toggleField(filtered[highlightIndex].id);
        } else if (filtered.length === 1) {
          toggleField(filtered[0].id);
        } else if (searchText.trim()) {
          // Allow custom field reference names
          toggleField(searchText.trim());
        }
        break;
      case 'Backspace':
        // Remove last chip if input is empty
        if (!searchText && values.length > 0) {
          removeField(values[values.length - 1]);
        }
        break;
      case 'Escape':
        setOpen(false);
        setSearchText('');
        break;
      default:
        break;
    }
  };

  // ── Scroll highlighted item into view ──────────────────────
  useEffect(() => {
    if (highlightIndex >= 0 && listRef.current) {
      const item = listRef.current.querySelector(`[data-index="${highlightIndex}"]`);
      item?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightIndex]);

  // ── Grouped items for rendering ────────────────────────────
  const groupedItems = useMemo(() => {
    const items = [];
    let lastGroup = null;
    filtered.forEach((f, idx) => {
      const g = f.group || f.source || '';
      if (g !== lastGroup) {
        const groupLabels = {
          Analysis: '🔬 AI / Evaluation Fields',
          Custom: 'Custom Fields',
          System: 'System Fields',
          Microsoft: 'Microsoft Fields',
        };
        items.push({ _isHeader: true, label: groupLabels[g] || `${g} Fields` });
        lastGroup = g;
      }
      items.push({ ...f, _flatIndex: idx });
    });
    return items;
  }, [filtered]);

  // ── Resolve display name for a ref name ────────────────────
  const getDisplayName = useCallback(
    (refName) => {
      const match = fields.find((f) => f.id === refName);
      return match ? match.displayName : refName;
    },
    [fields]
  );

  // ── Loading state ──────────────────────────────────────────
  if (loading) {
    return (
      <div className="multi-field-combobox">
        <div className="mfc-input-area">
          <input
            className="form-input mfc-loading"
            type="text"
            value=""
            placeholder="Loading ADO fields…"
            disabled
          />
          <span className="mfc-chevron" aria-hidden="true">⏳</span>
        </div>
      </div>
    );
  }

  // ── No fields → plain text input ──────────────────────────
  if (fields.length === 0) {
    return (
      <input
        id={id}
        className="form-input"
        type="text"
        value={values.join(', ')}
        onChange={(e) =>
          onChange(
            e.target.value
              .split(',')
              .map((v) => v.trim())
              .filter(Boolean)
          )
        }
        placeholder="Comma-separated field reference names"
        required={required}
      />
    );
  }

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="multi-field-combobox" ref={wrapperRef}>
      {/* Selected chips + search input on the same line */}
      <div
        className={`mfc-input-area ${open ? 'mfc-focused' : ''}`}
        onClick={() => inputRef.current?.focus()}
      >
        {values.map((refName) => (
          <span key={refName} className="mfc-chip">
            {getDisplayName(refName)}
            <button
              type="button"
              className="mfc-chip-remove"
              onClick={(e) => {
                e.stopPropagation();
                removeField(refName);
              }}
              aria-label={`Remove ${getDisplayName(refName)}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          id={id}
          className="mfc-search-input"
          type="text"
          value={searchText}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={values.length === 0 ? placeholder : ''}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
        />
        <span className="mfc-chevron" aria-hidden="true">
          {open ? '▲' : '▼'}
        </span>
      </div>

      {/* Hidden native input for required validation */}
      {required && (
        <input
          type="text"
          value={values.length > 0 ? 'ok' : ''}
          required
          style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
          tabIndex={-1}
          aria-hidden="true"
          onChange={() => {}}
        />
      )}

      {/* Dropdown */}
      {open && filtered.length > 0 && (
        <div className="mfc-dropdown" ref={listRef} role="listbox">
          {groupedItems.map((item, i) =>
            item._isHeader ? (
              <div key={`hdr-${i}`} className="mfc-group-header">
                {item.label}
              </div>
            ) : (
              <div
                key={item.id}
                data-index={item._flatIndex}
                className={`mfc-option ${item._flatIndex === highlightIndex ? 'highlighted' : ''} ${selectedSet.has(item.id) ? 'selected' : ''}`}
                role="option"
                aria-selected={selectedSet.has(item.id)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  toggleField(item.id);
                }}
                onMouseEnter={() => setHighlightIndex(item._flatIndex)}
              >
                <span className="mfc-check">{selectedSet.has(item.id) ? '☑' : '☐'}</span>
                <span className="field-display-name">{item.displayName}</span>
                <span className="field-ref-name">{item.id}</span>
                {item.type && <span className="field-type-badge">{item.type}</span>}
              </div>
            )
          )}
        </div>
      )}

      {open && filtered.length === 0 && searchText && (
        <div className="mfc-dropdown" role="listbox">
          <div className="mfc-empty">
            No matching fields — press <strong>Enter</strong> to add "{searchText}" as a custom reference.
          </div>
        </div>
      )}
    </div>
  );
}
