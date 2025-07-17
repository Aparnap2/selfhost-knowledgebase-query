import { useState, useEffect, ChangeEvent, FormEvent, DragEvent } from 'react';
import axios from 'axios';
import styled from 'styled-components';
import PythonExecutor from './components/PythonExecutor';
import WebSearch from './components/WebSearch';
import CitationList from './components/CitationList';
import Alert from './components/Alert';
import Login from './components/Login';

// Define TypeScript interfaces
interface File {
  id: string;
  filename: string;
}

interface Source {
  id: string;
  filename: string;
  snippet: string;
  distance: number;
}

// Styled components
const AppContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
`;

const Header = styled.header`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  border-bottom: 1px solid #eaeaea;
  padding-bottom: 15px;
`;

const StatusIndicator = styled.div`
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 5px;

  span {
    &.connected {
      color: #10b981;
    }
    &.error {
      color: #ef4444;
    }
  }
`;

const Main = styled.main`
  display: grid;
  grid-template-columns: 1fr;
  gap: 30px;

  @media (min-width: 768px) {
    grid-template-columns: 1fr 1fr;
  }
`;

const Section = styled.section`
  background: #ffffff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  grid-column: 1 / -1;
`;

const FileUploadArea = styled.div<{ isDragOver: boolean }>`
  border: 2px dashed ${props => props.isDragOver ? '#10b981' : '#d1d5db'};
  border-radius: 8px;
  padding: 30px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: ${props => props.isDragOver ? 'rgba(16, 185, 129, 0.05)' : '#f9fafb'};
  
  &:hover {
    border-color: #10b981;
    background-color: rgba(16, 185, 129, 0.05);
  }
`;

const Button = styled.button`
  padding: 10px 16px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const PrimaryButton = styled(Button)`
  background-color: #10b981;
  color: white;
  border: none;
  
  &:hover:not(:disabled) {
    background-color: #059669;
  }
`;

const SecondaryButton = styled(Button)`
  background-color: transparent;
  color: #4b5563;
  border: 1px solid #d1d5db;
  
  &:hover:not(:disabled) {
    background-color: #f3f4f6;
  }
`;

const QueryTextarea = styled.textarea`
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 16px;
  resize: vertical;
  min-height: 100px;
  margin-bottom: 15px;
  
  &:focus {
    outline: none;
    border-color: #10b981;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  }
`;

const App = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [query, setQuery] = useState<string>('');
  const [response, setResponse] = useState<string>('');
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<string>('Checking...');
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [filesLoading, setFilesLoading] = useState<boolean>(true);

  // Attach JWT to all axios requests
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  // Fetch files when authenticated
  useEffect(() => {
    if (token) {
      fetchFiles();
    }
  }, [token]);

  // Check backend health on component mount
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await axios.get(`${import.meta.env.VITE_API_URL}/health`, {
          timeout: 5000  // 5 second timeout
        });
        if (response.data.status === 'healthy') {
          setBackendStatus('Connected');
        } else {
          setBackendStatus('Error: Backend is not healthy');
        }
      } catch (error) {
        console.error('Backend health check failed:', error);
        setBackendStatus('Error: Cannot connect to backend');
      }
    };
  
    const healthCheckInterval = setInterval(checkBackendHealth, 30000); // Check every 30 seconds
    checkBackendHealth(); // Initial check
  
    return () => clearInterval(healthCheckInterval);
  }, []);
  
  const fetchFiles = async () => {
    try {
      setFilesLoading(true);
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/files`);
      setFiles(response.data);
    } catch (error) {
      console.error('Error fetching files:', error);
    } finally {
      setFilesLoading(false);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      processSelectedFile(file);
    }
    
    // Reset the file input
    if (event.target) {
      event.target.value = '';
    }
  };

  const processSelectedFile = (file: File) => {
    if (!file) return;
    
    setSelectedFile(file);
    
    // Reset upload status when a new file is selected
    setUploadStatus('');
    
    // Validate file size (limit to 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setUploadStatus('File size exceeds 10MB limit. Please select a smaller file.');
      setSelectedFile(null);
      return;
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      processSelectedFile(droppedFiles[0]);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a file first');
      return;
    }

    // Get file extension
    const fileExt = selectedFile.name.split('.').pop()?.toLowerCase() || '';
    
    // List of supported file types
    const supportedTextTypes = ['txt', 'md', 'py', 'js', 'html', 'css', 'json', 'xml', 'csv'];
    const supportedDocTypes = ['pdf', 'doc', 'docx'];
    const supportedTypes = [...supportedTextTypes, ...supportedDocTypes];
    
    // Check if file type is supported
    if (!supportedTypes.includes(fileExt)) {
      setUploadStatus(`File type .${fileExt} is not fully supported. The system will try to process it, but results may vary.`);
    }

    setUploadStatus('Uploading...');
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post(`${import.meta.env.VITE_API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        // Add timeout and progress tracking
        timeout: 30000, // 30 seconds timeout
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadStatus(`Uploading: ${percentCompleted}%`);
          }
        }
      });
      
      setUploadStatus('File uploaded successfully!');
      setSelectedFile(null);
      // Reset the file input
      const fileInput = document.querySelector('input[type="file"]');
      if (fileInput) {
        (fileInput as HTMLInputElement).value = '';
      }
      // Refresh the file list
      fetchFiles();
    } catch (error: any) {
      console.error('Error uploading file:', error);
      let errorMessage = 'Upload failed';
      
      if (error.response) {
        // The server responded with an error status
        errorMessage = `Upload failed: ${error.response.status} - ${error.response.data?.detail || error.response.statusText}`;
      } else if (error.request) {
        // The request was made but no response was received
        errorMessage = 'Upload failed: No response from server. Please check your connection.';
      } else {
        // Something happened in setting up the request
        errorMessage = `Upload failed: ${error.message}`;
      }
      
      setUploadStatus(errorMessage);
    }
  };

  const handleQuerySubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResponse('');
    setSources([]);

    try {
      const result = await axios.post(`${import.meta.env.VITE_API_URL}/query`, {
        query: query,
      });
      setResponse(result.data.response);
      setSources(result.data.sources || []);
    } catch (error) {
      console.error('Error querying:', error);
      setResponse('Error: Failed to get a response from the server.');
      setSources([]);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return (
    <AppContainer>
      <Header>
        <h1>NotebookLM</h1>
        <StatusIndicator>
          Backend: <span className={backendStatus === 'Connected' ? 'connected' : 'error'}>{backendStatus}</span>
        </StatusIndicator>
      </Header>

      <Main>
        <Section>
          <h2>Upload Documents</h2>
          <div className="file-upload">
            <FileUploadArea 
              isDragOver={isDragOver}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-upload')?.click()}
            >
              <svg className="file-upload-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <div className="file-upload-text">
                {selectedFile ? (
                  <div>
                    <strong>{selectedFile.name}</strong>
                    <br />
                    <span>Click to change or drag a new file</span>
                  </div>
                ) : (
                  <div>
                    <strong>Click to upload</strong> or drag and drop
                    <br />
                    <span>Supported: PDF, DOC, TXT, MD, and more</span>
                  </div>
                )}
              </div>
              <input 
                type="file" 
                onChange={handleFileChange} 
                id="file-upload"
                accept=".txt,.pdf,.doc,.docx,.md,.py,.js,.html,.css,.json,.xml,.csv"
                style={{ display: 'none' }}
              />
            </FileUploadArea>
            {selectedFile && (
              <div className="file-upload-actions">
                <PrimaryButton 
                  onClick={handleFileUpload} 
                  disabled={uploadStatus.startsWith('Uploading')}
                >
                  {uploadStatus.startsWith('Uploading') ? (
                    <>
                      <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Uploading...
                    </>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 12l2 2 4-4" />
                      </svg>
                      Upload File
                    </>
                  )}
                </PrimaryButton>
                <SecondaryButton 
                  onClick={() => setSelectedFile(null)}
                >
                  Cancel
                </SecondaryButton>
              </div>
            )}
          </div>
          {uploadStatus && (
            <p className={`upload-status fade-in ${
              uploadStatus.includes('failed') || uploadStatus.includes('exceeds') 
                ? 'error' 
                : uploadStatus.includes('success') 
                  ? 'success' 
                  : ''
            }`}>
              {uploadStatus}
            </p>
          )}
          <div className="supported-files">
            <p>Supported file types: .txt, .pdf, .doc, .docx, .md, .py, .js, .html, .css, .json, .xml, .csv</p>
            <p>Maximum file size: 10MB</p>
          </div>
        </Section>

        <Section>
          <h2>Your Documents</h2>
          {filesLoading ? (
            <div className="loading-state">
              <svg className="animate-spin" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <p>Loading documents...</p>
            </div>
          ) : files.length > 0 ? (
            <ul className="file-list">
              {files.map((file, index) => (
                <li key={index} className="slide-in" style={{animationDelay: `${index * 0.1}s`}}>
                  {file.filename}
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" className="empty-icon">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p>No documents uploaded yet.</p>
              <p className="empty-subtitle">Upload your first document to get started!</p>
            </div>
          )}
        </Section>

        <Section>
          <h2>Ask a Question</h2>
          <form onSubmit={handleQuerySubmit} className="query-form">
            <QueryTextarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask something about your documents..."
              rows={4}
            />
            <PrimaryButton type="submit" disabled={loading}>
              {loading ? (
                <>
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Processing...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  Ask Question
                </>
              )}
            </PrimaryButton>
          </form>
        </Section>

        {response && (
          <Section className="fade-in">
            <h2>Response</h2>
            {response.startsWith('Error:') && (
              <Alert message={response.replace('Error:', '').trim()} type="error" />
            )}
            <div className="response-content">
              {!response.startsWith('Error:') && response}
            </div>
            <CitationList sources={sources} />
          </Section>
        )}

        <Section>
          <WebSearch />
        </Section>

        <Section>
          <PythonExecutor />
        </Section>
      </Main>

      <footer>
        <p>NotebookLM - Your Personal Document Assistant</p>
      </footer>
    </AppContainer>
  );
};

export default App;