/**
 * FieldCombobox — ADO Field Autocomplete
 * =========================================
 *
 * Searchable dropdown for selecting ADO field reference names.
 * On focus the search text clears so the user sees all available fields.
 * Falls back to a regular text input if the field list fails to load.
 *
 * Props:
 *   value      : string — current field reference name (e.g., "System.AreaPath")
 *   onChange    : (refName: string) => void
 *   fields     : Array — field schema objects from the API
 *   id         : string — HTML id for the input
 *   placeholder: string
 *   required   : boolean
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import './FieldCombobox.css';


export default function FieldCombobox({
  value,
  onChange,
  fields = [],
  id,
  placeholder = 'Click here and start typing to search fields…',
  required = false,
  loading = false,
}) {
  const [searchText, setSearchText] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef(null);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  // ── Display text when NOT searching ────────────────────────
  const displayText = useMemo(() => {
    if (!value) return '';
    if (fields.length > 0) {
      const match = fields.find((f) => f.id === value);
      return match ? `${match.displayName}  —  ${match.id}` : value;
    }
    return value;
  }, [value, fields]);

  // ── Close dropdown on outside click ────────────────────────
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

  // ── Input handlers ─────────────────────────────────────────
  const handleInputChange = (e) => {
    setSearchText(e.target.value);
    setOpen(true);
    setHighlightIndex(-1);
    // If the user clears the input, also clear the value
    if (!e.target.value) {
      onChange('');
    }
  };

  const handleFocus = () => {
    // Clear search so the user sees the full list
    setSearchText('');
    setOpen(true);
    setHighlightIndex(-1);
    // Select input text for easy replacement
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const selectField = (f) => {
    onChange(f.id);
    setSearchText('');
    setOpen(false);
  };

  const handleKeyDown = (e) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setOpen(true);
        setSearchText('');
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
          selectField(filtered[highlightIndex]);
        } else if (filtered.length === 1) {
          selectField(filtered[0]);
        } else if (searchText.trim()) {
          // Allow typing a custom reference name
          onChange(searchText.trim());
          setOpen(false);
          setSearchText('');
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

  // ── Build grouped list for rendering ────────────────────────
  // Maintains flat indices for keyboard navigation while inserting
  // group headers between sections.
  // NOTE: Must be above early returns to satisfy React Rules of Hooks.
  const groupedItems = useMemo(() => {
    const items = [];
    let lastGroup = null;
    filtered.forEach((f, idx) => {
      const g = f.group || f.source || '';
      if (g !== lastGroup) {
        const groupLabels = {
          'Analysis': '🔬 AI / Evaluation Fields',
          'Custom':   'Custom Fields',
          'System':   'System Fields',
          'Microsoft': 'Microsoft Fields',
        };
        items.push({ _isHeader: true, label: groupLabels[g] || `${g} Fields` });
        lastGroup = g;
      }
      items.push({ ...f, _flatIndex: idx });
    });
    return items;
  }, [filtered]);

  // ── Loading state ──────────────────────────────────────────
  if (loading) {
    return (
      <div className="field-combobox">
        <div className="field-combobox-input-wrap">
          <input
            id={id}
            className="form-input field-combobox-loading"
            type="text"
            value=""
            placeholder="Loading ADO fields…"
            disabled
          />
          <span className="field-combobox-chevron" aria-hidden="true">⏳</span>
        </div>
      </div>
    );
  }

  // ── No fields loaded → plain text input ────────────────────
  if (fields.length === 0) {
    return (
      <input
        id={id}
        className="form-input"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g., Custom.SolutionArea or System.AreaPath"
        required={required}
      />
    );
  }

  // ── Render ─────────────────────────────────────────────────
  // When the dropdown is open we show the search text; otherwise the display text
  const inputText = open ? searchText : displayText;

  return (
    <div className="field-combobox" ref={wrapperRef}>
      <div className="field-combobox-input-wrap">
        <input
          ref={inputRef}
          id={id}
          className="form-input"
          type="text"
          value={inputText}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          required={required}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
        />
        <span className="field-combobox-chevron" aria-hidden="true">
          {open ? '▲' : '▼'}
        </span>
      </div>

      {open && filtered.length > 0 && (
        <div className="field-combobox-dropdown" ref={listRef} role="listbox">
          {groupedItems.map((item, i) =>
            item._isHeader ? (
              <div key={`hdr-${i}`} className="field-combobox-group-header">
                {item.label}
              </div>
            ) : (
              <div
                key={item.id}
                data-index={item._flatIndex}
                className={`field-combobox-option ${item._flatIndex === highlightIndex ? 'highlighted' : ''} ${item.id === value ? 'selected' : ''}`}
                role="option"
                aria-selected={item.id === value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectField(item);
                }}
                onMouseEnter={() => setHighlightIndex(item._flatIndex)}
              >
                <span className="field-display-name">{item.displayName}</span>
                <span className="field-ref-name">{item.id}</span>
                {item.type && <span className="field-type-badge">{item.type}</span>}
              </div>
            )
          )}
        </div>
      )}

      {open && filtered.length === 0 && searchText && (
        <div className="field-combobox-dropdown" role="listbox">
          <div className="field-combobox-empty">
            No matching fields — press <strong>Enter</strong> to use "{searchText}" as a custom reference name.
          </div>
        </div>
      )}
    </div>
  );
}
