/**
 * FieldCombobox — ADO Field Autocomplete
 * =========================================
 *
 * Combobox input that searches and selects ADO field reference names.
 * Shows displayName + reference name, grouped by category.
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
  placeholder = 'Search fields…',
  required = false,
}) {
  const [inputValue, setInputValue] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const wrapperRef = useRef(null);
  const listRef = useRef(null);

  // ── Sync input text with selected value ────────────────────
  useEffect(() => {
    if (value && fields.length > 0) {
      const match = fields.find((f) => f.id === value);
      setInputValue(match ? `${match.displayName}  (${match.id})` : value);
    } else {
      setInputValue(value || '');
    }
  }, [value, fields]);

  // ── Close dropdown on outside click ────────────────────────
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // ── Filter and group fields ────────────────────────────────
  const filtered = useMemo(() => {
    if (!inputValue.trim()) return fields;
    const q = inputValue.toLowerCase();
    return fields.filter(
      (f) =>
        f.displayName.toLowerCase().includes(q) ||
        f.id.toLowerCase().includes(q) ||
        (f.description || '').toLowerCase().includes(q)
    );
  }, [inputValue, fields]);

  // Group by the "group" property
  const grouped = useMemo(() => {
    const groups = {};
    for (const f of filtered) {
      const g = f.group || 'Other';
      if (!groups[g]) groups[g] = [];
      groups[g].push(f);
    }
    return groups;
  }, [filtered]);

  // Flat list for keyboard nav
  const flatList = useMemo(() => filtered, [filtered]);

  // ── Input handlers ─────────────────────────────────────────
  const handleInputChange = (e) => {
    setInputValue(e.target.value);
    setOpen(true);
    setHighlightIndex(-1);
    // If the user clears the input, also clear the value
    if (!e.target.value) {
      onChange('');
    }
  };

  const handleFocus = () => {
    setOpen(true);
  };

  const selectField = (f) => {
    onChange(f.id);
    setInputValue(`${f.displayName}  (${f.id})`);
    setOpen(false);
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
        setHighlightIndex((prev) => Math.min(prev + 1, flatList.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex >= 0 && highlightIndex < flatList.length) {
          selectField(flatList[highlightIndex]);
        } else if (flatList.length === 1) {
          selectField(flatList[0]);
        }
        break;
      case 'Escape':
        setOpen(false);
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
  let flatIdx = -1;

  return (
    <div className="field-combobox" ref={wrapperRef}>
      <input
        id={id}
        className="form-input"
        type="text"
        value={inputValue}
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

      {open && flatList.length > 0 && (
        <div className="field-combobox-dropdown" ref={listRef} role="listbox">
          {Object.entries(grouped).map(([groupName, items]) => (
            <div key={groupName} className="field-combobox-group">
              <div className="field-combobox-group-label">{groupName}</div>
              {items.map((f) => {
                flatIdx++;
                const idx = flatIdx;
                return (
                  <div
                    key={f.id}
                    data-index={idx}
                    className={`field-combobox-option ${idx === highlightIndex ? 'highlighted' : ''} ${f.id === value ? 'selected' : ''}`}
                    role="option"
                    aria-selected={f.id === value}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectField(f);
                    }}
                    onMouseEnter={() => setHighlightIndex(idx)}
                  >
                    <span className="field-display-name">{f.displayName}</span>
                    <span className="field-ref-name">{f.id}</span>
                    {f.type && <span className="field-type-badge">{f.type}</span>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {open && flatList.length === 0 && inputValue && (
        <div className="field-combobox-dropdown" role="listbox">
          <div className="field-combobox-empty">
            No matching fields. You can type a custom reference name.
          </div>
        </div>
      )}
    </div>
  );
}
