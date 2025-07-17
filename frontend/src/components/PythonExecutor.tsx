import { useState, useEffect } from 'react';
import axios from 'axios';
import styled from 'styled-components';
import Alert from './Alert';

// Types
interface ExecutionResult {
  success: boolean;
  code: string;
  output: string;
  error?: string;
  plot?: string;
  sessionId?: string;
}

interface Session {
  id: string;
  created: string;
  code: string;
}

// Styled components
const Container = styled.div`
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 20px;
  margin-bottom: 20px;
`;

const Title = styled.h2`
  margin-top: 0;
  margin-bottom: 10px;
  color: #333;
`;

const Description = styled.p`
  color: #666;
  margin-bottom: 20px;
`;

const Form = styled.form`
  margin-bottom: 20px;
`;

const TextArea = styled.textarea`
  width: 100%;
  min-height: 150px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: monospace;
  font-size: 14px;
  resize: vertical;
  margin-bottom: 10px;
`;

const FormFooter = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const CharCount = styled.div`
  color: #666;
  font-size: 14px;
`;

const Button = styled.button<{ variant?: 'primary' | 'secondary' }>`
  background-color: ${props => props.variant === 'secondary' ? '#f3f4f6' : '#10b981'};
  color: ${props => props.variant === 'secondary' ? '#4b5563' : '#fff'};
  border: ${props => props.variant === 'secondary' ? '1px solid #d1d5db' : 'none'};
  padding: 10px 16px;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  
  &:hover:not(:disabled) {
    background-color: ${props => props.variant === 'secondary' ? '#e5e7eb' : '#059669'};
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  gap: 10px;
`;

const Tabs = styled.div`
  display: flex;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 16px;
`;

const Tab = styled.button<{ active: boolean }>`
  padding: 10px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid ${props => props.active ? '#10b981' : 'transparent'};
  color: ${props => props.active ? '#10b981' : '#4b5563'};
  font-weight: ${props => props.active ? '600' : '400'};
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    color: #10b981;
  }
`;

const TabContent = styled.div`
  margin-bottom: 20px;
`;

const CodeSection = styled.div`
  margin-bottom: 20px;
`;

const CodeHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
`;

const CodeTitle = styled.h3`
  margin: 0;
  font-size: 16px;
  color: #333;
`;

const CopyButton = styled.button`
  background: none;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: #f3f4f6;
  }
`;

const CodeBlock = styled.pre`
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 16px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 14px;
  line-height: 1.5;
`;

const OutputBlock = styled.pre`
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 16px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
`;

const PlotContainer = styled.div`
  display: flex;
  justify-content: center;
  margin: 20px 0;
`;

const PlotImage = styled.img`
  max-width: 100%;
  max-height: 500px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
`;

const SessionInfo = styled.div`
  background-color: #f0fdf4;
  border: 1px solid #d1fae5;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const SessionText = styled.div`
  font-size: 14px;
  color: #065f46;
`;

const LoadingSpinner = styled.span`
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  animation: spin 1s ease-in-out infinite;
  margin-right: 8px;
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

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

const SessionIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
  </svg>
);

const PythonExecutor: React.FC = () => {
  const [code, setCode] = useState<string>('');
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('code');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionCreating, setSessionCreating] = useState<boolean>(false);

  // Create a session on component mount
  useEffect(() => {
    const createSession = async () => {
      try {
        setSessionCreating(true);
        const response = await axios.post('http://localhost:3001/session');
        if (response.data.success) {
          setSessionId(response.data.sessionId);
        }
      } catch (err) {
        console.error('Error creating session:', err);
      } finally {
        setSessionCreating(false);
      }
    };

    createSession();

    // Clean up session on component unmount
    return () => {
      if (sessionId) {
        axios.delete(`http://localhost:3001/session/${sessionId}`)
          .catch(err => console.error('Error deleting session:', err));
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post('http://localhost:3001/execute', {
        code: code.trim(),
        sessionId,
        timeout: 30000 // 30 seconds timeout
      }, {
        timeout: 60000 // 60 seconds timeout for the request
      });
      
      setResult(response.data);
      setActiveTab('output'); // Default to showing output tab after execution
    } catch (err: any) {
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

  const createNewSession = async () => {
    try {
      setSessionCreating(true);
      
      // Delete the current session if it exists
      if (sessionId) {
        await axios.delete(`http://localhost:3001/session/${sessionId}`);
      }
      
      // Create a new session
      const response = await axios.post('http://localhost:3001/session');
      if (response.data.success) {
        setSessionId(response.data.sessionId);
        setResult(null);
        setCode('');
      }
    } catch (err) {
      console.error('Error creating new session:', err);
      setError('Failed to create a new session. Please try again.');
    } finally {
      setSessionCreating(false);
    }
  };

  return (
    <Container>
      <Title>Python Code Executor</Title>
      <Description>
        Write and execute Python code with support for data visualization and persistent sessions.
      </Description>
      
      {sessionId && (
        <SessionInfo>
          <SessionText>
            <strong>Active Session:</strong> Your code and variables will persist between executions.
          </SessionText>
          <Button variant="secondary" onClick={createNewSession} disabled={sessionCreating}>
            {sessionCreating ? (
              <>
                <LoadingSpinner /> Creating...
              </>
            ) : (
              'New Session'
            )}
          </Button>
        </SessionInfo>
      )}
      
      <Form onSubmit={handleSubmit}>
        <TextArea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="# Write your Python code here
# Example:
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.plot(x, y)
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')

print('Sine wave plotted!')"
          disabled={loading}
        />
        <FormFooter>
          <CharCount>
            {code.length} characters
          </CharCount>
          <Button 
            type="submit" 
            disabled={loading || !code.trim()}
          >
            {loading ? (
              <>
                <LoadingSpinner /> Executing...
              </>
            ) : (
              'Execute Code'
            )}
          </Button>
        </FormFooter>
      </Form>

      {error && (
        <Alert message={error} type="error" />
      )}

      {result && (
        <div>
          <Tabs>
            <Tab 
              active={activeTab === 'output'} 
              onClick={() => setActiveTab('output')}
            >
              <TerminalIcon /> Output
            </Tab>
            <Tab 
              active={activeTab === 'code'} 
              onClick={() => setActiveTab('code')}
            >
              <CodeIcon /> Code
            </Tab>
            {result.plot && (
              <Tab 
                active={activeTab === 'plot'} 
                onClick={() => setActiveTab('plot')}
              >
                <ChartIcon /> Plot
              </Tab>
            )}
          </Tabs>

          <TabContent>
            {activeTab === 'code' && (
              <CodeSection>
                <CodeHeader>
                  <CodeTitle>Executed Code</CodeTitle>
                  <CopyButton 
                    onClick={() => {
                      navigator.clipboard.writeText(result.code);
                      // You could add a toast notification here
                    }}
                  >
                    Copy
                  </CopyButton>
                </CodeHeader>
                <CodeBlock>
                  <code>{result.code}</code>
                </CodeBlock>
              </CodeSection>
            )}

            {activeTab === 'output' && (
              <div>
                <CodeTitle>Execution Output</CodeTitle>
                <OutputBlock>
                  {result.error ? (
                    <span style={{ color: '#ef4444' }}>{result.error}</span>
                  ) : result.output ? (
                    result.output
                  ) : (
                    'No output produced.'
                  )}
                </OutputBlock>
              </div>
            )}

            {activeTab === 'plot' && result.plot && (
              <div>
                <CodeTitle>Generated Visualization</CodeTitle>
                <PlotContainer>
                  <PlotImage 
                    src={result.plot} 
                    alt="Generated plot" 
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.onerror = null;
                      target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="200" viewBox="0 0 100% 200" fill="%23f0f0f0"><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14" fill="%23999">Could not load image</text></svg>';
                    }}
                  />
                </PlotContainer>
              </div>
            )}
          </TabContent>
        </div>
      )}
    </Container>
  );
};

export default PythonExecutor;