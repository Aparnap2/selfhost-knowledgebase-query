import { useState } from 'react';
import axios from 'axios';
import styled from 'styled-components';
import Alert from './Alert';

// Types
interface SearchResult {
  title: string;
  link: string;
  snippet: string;
  source: string;
  extracted_content?: string;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  error?: string;
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

const SearchInput = styled.input`
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
  margin-bottom: 10px;
`;

const Button = styled.button`
  background-color: #10b981;
  color: #fff;
  border: none;
  padding: 10px 16px;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  
  &:hover:not(:disabled) {
    background-color: #059669;
  }
  
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const ResultsList = styled.div`
  margin-top: 20px;
`;

const ResultItem = styled.div`
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
  
  &:last-child {
    border-bottom: none;
  }
`;

const ResultTitle = styled.h3`
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #1a56db;
`;

const ResultLink = styled.a`
  color: #10b981;
  font-size: 14px;
  text-decoration: none;
  display: block;
  margin-bottom: 8px;
  word-break: break-all;
  
  &:hover {
    text-decoration: underline;
  }
`;

const ResultSnippet = styled.p`
  margin: 0;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.5;
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

const NoResults = styled.div`
  text-align: center;
  padding: 20px;
  color: #6b7280;
`;

const WebSearch: React.FC = () => {
  const [query, setQuery] = useState<string>('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const response = await axios.post(`${import.meta.env.VITE_API_URL}/search`, {
        query: query.trim(),
        num_results: 5,
        extract_content: true
      }, {
        timeout: 30000 // 30 seconds timeout
      });
      
      setResults(response.data);
    } catch (err: any) {
      console.error('Error performing web search:', err);
      setError(
        err.response?.data?.detail || 
        'Failed to perform web search. Please try again later.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container>
      <Title>Web Search</Title>
      <Description>
        Search the web for information and automatically extract content from web pages.
      </Description>
      
      <Form onSubmit={handleSubmit}>
        <SearchInput
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your search query..."
          disabled={loading}
        />
        <Button 
          type="submit" 
          disabled={loading || !query.trim()}
        >
          {loading ? (
            <>
              <LoadingSpinner /> Searching...
            </>
          ) : (
            'Search Web'
          )}
        </Button>
      </Form>

      {error && (
        <Alert message={error} type="error" />
      )}

      {results && (
        <ResultsList>
          {results.results.length > 0 ? (
            results.results.map((result, index) => (
              <ResultItem key={index}>
                <ResultTitle>{result.title}</ResultTitle>
                <ResultLink href={result.link} target="_blank" rel="noopener noreferrer">
                  {result.link}
                </ResultLink>
                <ResultSnippet>
                  {result.extracted_content ? 
                    result.extracted_content.substring(0, 200) + '...' : 
                    result.snippet}
                </ResultSnippet>
              </ResultItem>
            ))
          ) : (
            <NoResults>
              No results found for "{query}". Please try a different search query.
            </NoResults>
          )}
        </ResultsList>
      )}
    </Container>
  );
};

export default WebSearch;