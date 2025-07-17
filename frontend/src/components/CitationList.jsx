import React from 'react';
import PropTypes from 'prop-types';

/**
 * Modular citation list for Q&A sources
 * @param {Array} sources - [{ filename, snippet, distance }]
 */
function CitationList({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="citation-list" style={{ marginTop: '1rem' }}>
      <h4 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Sources</h4>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {sources.map((src, idx) => (
          <li key={src.id || idx} style={{ marginBottom: '0.5rem', fontSize: '0.95rem', color: '#64748b' }}>
            <strong>{src.filename}</strong>: <span style={{ fontStyle: 'italic' }}>{src.snippet}</span>
            {typeof src.distance === 'number' && (
              <span style={{ marginLeft: 8, color: '#aaa', fontSize: '0.85em' }}>({src.distance.toFixed(2)})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

CitationList.propTypes = {
  sources: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string,
      filename: PropTypes.string.isRequired,
      snippet: PropTypes.string.isRequired,
      distance: PropTypes.number,
    })
  ),
};

export default CitationList;
