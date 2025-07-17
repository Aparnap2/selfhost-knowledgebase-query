import { useState } from 'react';
import axios from 'axios';
import '../styles/PythonExecutor.css';
import Alert from './Alert';

// Icons
const CodeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 18 22 12 16 6"></polyline>
    <polyline points="8 6 2 12 8 18"></polyline>
  </svg>
);

const TerminalIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="4 17 10 11 4 5"></polyline>
    <line x1="12" y1="19" x2="20" y2="19"></line>
  </svg>
);

const ChartIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"></line>
    <line x1="12" y1="20" x2="12" y2="4"></line>
    <line x1="6" y1="20" x2="6" y2="14"></line>
  </svg>
);

const InfoIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="16" x2="12" y2="12"></line>
    <line x1="12" y1="8" x2="12.01" y2="8"></line>
  </svg>
);

function PythonExecutor() {
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('code');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post('http://localhost:3001/execute', {
        prompt: prompt.trim(),
        maxAttempts: 3
      }, {
        timeout: 60000 // 60 seconds timeout
      });
      
      setResult(response.data);
      setActiveTab('code'); // Default to showing code tab after generation
    } catch (err) {
      console.error('Error executing Python code:', err);
      setError(
        err.response?.data?.error || 
        err.response?.data?.details || 
        'Failed to execute code. The server might be unavailable. Please try again later.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="python-executor">
      <h2>Python Code Generator</h2>
      <p className="description">
        Describe what you want to do with Python, and AI will generate and execute the code for you.
      </p>
      
      <form onSubmit={handleSubmit} className="code-form">
        <div className="form-group">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="E.g., Create a bar chart showing the top 5 countries by population"
            rows="4"
            maxLength="500"
            disabled={loading}
          ></textarea>
          <div className="form-footer">
            <div className="char-count">
              {prompt.length}/500 characters
            </div>
            <button 
              type="submit" 
              disabled={loading || !prompt.trim()}
              className="generate-button"
            >
              {loading ? (
                <>
                  <span className="loading-spinner"></span> Generating...
                </>
              ) : (
                'Generate & Execute Code'
              )}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <Alert message={error} type="error" />
      )}

      {result && (
        <div className="result-container">
          <div className="tabs">
            <button 
              className={`tab ${activeTab === 'code' ? 'active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              <CodeIcon /> Code
            </button>
            <button 
              className={`tab ${activeTab === 'output' ? 'active' : ''}`}
              onClick={() => setActiveTab('output')}
            >
              <TerminalIcon /> Output
            </button>
            {result.plot && (
              <button 
                className={`tab ${activeTab === 'plot' ? 'active' : ''}`}
                onClick={() => setActiveTab('plot')}
              >
                <ChartIcon /> Plot
              </button>
            )}
            {result.explanation && (
              <button 
                className={`tab ${activeTab === 'explanation' ? 'active' : ''}`}
                onClick={() => setActiveTab('explanation')}
              >
                <InfoIcon /> Explanation
              </button>
            )}
          </div>

          <div className="tab-content">
            {activeTab === 'code' && (
              <div className="code-section">
                <div className="code-header">
                  <h3>Generated Python Code</h3>
                  <button 
                    className="copy-button"
                    onClick={() => {
                      navigator.clipboard.writeText(result.code);
                      // You might want to add a toast notification here
                    }}
                    title="Copy to clipboard"
                  >
                    Copy
                  </button>
                </div>
                <pre className="code-block">
                  <code>{result.code}</code>
                </pre>
              </div>
            )}

            {activeTab === 'output' && (
              <div className="output-section">
                <h3>Execution Output</h3>
                <pre className="output-block">
                  {result.output || 'No output produced.'}
                </pre>
              </div>
            )}

            {activeTab === 'plot' && result.plot && (
              <div className="plot-section">
                <h3>Generated Visualization</h3>
                <div className="plot-container">
                  <img 
                    src={result.plot} 
                    alt="Generated plot" 
                    className="plot-image" 
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="200" viewBox="0 0 100% 200" fill="%23f0f0f0"><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14" fill="%23999">Could not load image</text></svg>';
                    }}
                  />
                </div>
              </div>
            )}

            {activeTab === 'explanation' && result.explanation && (
              <div className="explanation-section">
                <h3>How This Works</h3>
                <div className="explanation-text">
                  {result.explanation.split('\n').map((paragraph, i) => (
                    <p key={i}>{paragraph}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default PythonExecutor;