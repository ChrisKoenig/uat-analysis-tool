/**
 * Pagination — Page navigation with size selector
 * ==================================================
 *
 * Lightweight pagination control for tables.
 *
 * Props:
 *   currentPage  : number (1-based)
 *   totalItems   : number
 *   pageSize     : number
 *   pageSizes    : number[]  (options for dropdown, default [25, 50, 100])
 *   onPageChange : (page: number) => void
 *   onPageSizeChange : (size: number) => void
 */

import React from 'react';
import './Pagination.css';

const DEFAULT_PAGE_SIZES = [25, 50, 100];

export default function Pagination({
  currentPage = 1,
  totalItems = 0,
  pageSize = 25,
  pageSizes = DEFAULT_PAGE_SIZES,
  onPageChange,
  onPageSizeChange,
}) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalItems);

  const handlePrev = () => {
    if (currentPage > 1) onPageChange?.(currentPage - 1);
  };

  const handleNext = () => {
    if (currentPage < totalPages) onPageChange?.(currentPage + 1);
  };

  const handleFirst = () => onPageChange?.(1);
  const handleLast = () => onPageChange?.(totalPages);

  /** Build visible page numbers with ellipsis */
  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 7;

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push('…');

      const rangeStart = Math.max(2, currentPage - 1);
      const rangeEnd = Math.min(totalPages - 1, currentPage + 1);
      for (let i = rangeStart; i <= rangeEnd; i++) pages.push(i);

      if (currentPage < totalPages - 2) pages.push('…');
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div className="pagination">
      <div className="pagination-info">
        <span className="pagination-range">
          {totalItems === 0 ? 'No items' : `${start}–${end} of ${totalItems}`}
        </span>
        <label className="pagination-size-label">
          Rows:
          <select
            className="pagination-size-select"
            value={pageSize}
            onChange={(e) => onPageSizeChange?.(Number(e.target.value))}
          >
            {pageSizes.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="pagination-controls">
        <button
          className="pagination-btn"
          onClick={handleFirst}
          disabled={currentPage === 1}
          title="First page"
        >
          «
        </button>
        <button
          className="pagination-btn"
          onClick={handlePrev}
          disabled={currentPage === 1}
          title="Previous page"
        >
          ‹
        </button>

        {getPageNumbers().map((p, i) =>
          p === '…' ? (
            <span key={`e${i}`} className="pagination-ellipsis">…</span>
          ) : (
            <button
              key={p}
              className={`pagination-btn ${p === currentPage ? 'pagination-btn-active' : ''}`}
              onClick={() => onPageChange?.(p)}
            >
              {p}
            </button>
          )
        )}

        <button
          className="pagination-btn"
          onClick={handleNext}
          disabled={currentPage === totalPages}
          title="Next page"
        >
          ›
        </button>
        <button
          className="pagination-btn"
          onClick={handleLast}
          disabled={currentPage === totalPages}
          title="Last page"
        >
          »
        </button>
      </div>
    </div>
  );
}
