import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, AsyncGenerator
from loguru import logger
import os
import hashlib
import aiofiles
import aiofiles.os

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class OllamaClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
        self.retry_delay = int(os.getenv("OLLAMA_RETRY_DELAY", "2"))
        self.use_cache = os.getenv("OLLAMA_USE_CACHE", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("OLLAMA_CACHE_TTL", "3600"))  # 1 hour default
    
    async def initialize(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        logger.info(f"Initialized Ollama client with base URL: {self.base_url}")
    
    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Closed Ollama client session")
    
    def _get_cache_key(self, model: str, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Generate a cache key based on model and messages"""
        cache_data = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Try to get a response from cache"""
        if not self.use_cache:
            return None
            
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
        
        try:
            if await aiofiles.os.path.exists(cache_file):
                # Check if cache is still valid
                stats = await aiofiles.os.stat(cache_file)
                if time.time() - stats.st_mtime < self.cache_ttl:
                    async with aiofiles.open(cache_file, "r") as f:
                        content = await f.read()
                        logger.info(f"Cache hit for key: {cache_key}")
                        return json.loads(content)
                else:
                    logger.info(f"Cache expired for key: {cache_key}")
        except Exception as e:
            logger.error(f"Error reading from cache: {str(e)}")
        
        return None
    
    async def _save_to_cache(self, cache_key: str, response: Dict[str, Any]):
        """Save a response to cache"""
        if not self.use_cache:
            return
            
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
        
        try:
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(json.dumps(response))
            logger.info(f"Saved response to cache: {cache_key}")
        except Exception as e:
            logger.error(f"Error saving to cache: {str(e)}")
    
    async def chat(self, model: str, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any] or AsyncGenerator[Dict[str, Any], None]:
        """Send a chat request to Ollama with retry logic and caching"""
        if not self.session:
            await self.initialize()
        
        # Try to get from cache for non-streaming requests
        if not stream:
            cache_key = self._get_cache_key(model, messages)
            cached_response = await self._get_from_cache(cache_key)
            if cached_response:
                return cached_response
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        # Add temperature and other parameters if provided
        if "temperature" not in kwargs:
            payload["temperature"] = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
        
        for attempt in range(self.max_retries):
            try:
                if stream:
                    return self._stream_response(url, payload)
                else:
                    async with self.session.post(url, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Ollama API error: {response.status} - {error_text}")
                            if attempt < self.max_retries - 1:
                                logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                                await asyncio.sleep(self.retry_delay)
                                continue
                            raise Exception(f"Ollama API error: {response.status}")
                        
                        result = await response.json()
                        
                        # Save to cache
                        if not stream:
                            cache_key = self._get_cache_key(model, messages)
                            await self._save_to_cache(cache_key, result)
                        
                        return result
            except asyncio.TimeoutError:
                logger.error(f"Ollama request timed out (Attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise Exception("Ollama request timed out after multiple attempts")
            except Exception as e:
                logger.error(f"Error in Ollama chat: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise
    
    async def _stream_response(self, url: str, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream response from Ollama"""
        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ollama streaming API error: {response.status} - {error_text}")
                    raise Exception(f"Ollama API error: {response.status}")
                
                # Process the streaming response
                async for line in response.content:
                    if line:
                        try:
                            line_text = line.decode('utf-8').strip()
                            if line_text:
                                yield json.loads(line_text)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse streaming JSON: {line}")
                        except Exception as e:
                            logger.error(f"Error processing stream: {str(e)}")
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            raise
    
    async def generate_embeddings(self, model: str, text: str) -> List[float]:
        """Generate embeddings for text using Ollama with retry logic"""
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": model,
            "prompt": text,
            "options": {"embedding_only": True}
        }
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(url, json=payload, timeout=self.timeout) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama embeddings API error: {response.status} - {error_text}")
                        if attempt < self.max_retries - 1:
                            logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise Exception(f"Ollama embeddings API error: {response.status}")
                    
                    result = await response.json()
                    
                    if 'embedding' not in result:
                        logger.error(f"No 'embedding' field in Ollama response. Full response: {result}")
                        if attempt < self.max_retries - 1:
                            logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise Exception("No 'embedding' field in Ollama response")
                    
                    embedding = result['embedding']
                    if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
                        logger.error(f"Unexpected embedding format: {type(embedding)}")
                        if attempt < self.max_retries - 1:
                            logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise Exception(f"Unexpected embedding format: {type(embedding)}")
                    
                    logger.info(f"Successfully generated embedding of length {len(embedding)}")
                    return embedding
            except asyncio.TimeoutError:
                logger.error(f"Ollama embeddings request timed out (Attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise Exception("Ollama embeddings request timed out after multiple attempts")
            except Exception as e:
                logger.error(f"Error in generate_embeddings: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise