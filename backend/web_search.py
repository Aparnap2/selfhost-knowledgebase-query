import asyncio
import os
import json
import hashlib
import time
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from loguru import logger
import aiofiles
import aiofiles.os
from bs4 import BeautifulSoup

# Import offline mode manager
from config.offline_mode import OfflineModeManager

# Import crawl4ai
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "search")
os.makedirs(CACHE_DIR, exist_ok=True)

class WebSearch:
    def __init__(self):
        self.cache_ttl = int(os.getenv("SEARCH_CACHE_TTL", "86400"))  # 24 hours default
        self.use_cache = os.getenv("SEARCH_USE_CACHE", "true").lower() == "true"
        
        # Browser configuration
        self.browser_config = BrowserConfig(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Default search engine
        self.search_engine = os.getenv("SEARCH_ENGINE", "https://www.google.com/search?q=")
        
        # Offline mode manager
        self.offline_mode_manager = OfflineModeManager()
    
    async def initialize(self):
        logger.info("Initialized web search client with crawl4ai")
    
    async def close(self):
        logger.info("Closed web search client session")
    
    def _get_cache_key(self, query: str, engine: str, num_results: int) -> str:
        """Generate a cache key based on search parameters"""
        cache_data = {
            "query": query,
            "engine": engine,
            "num_results": num_results
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Try to get search results from cache"""
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
                        logger.info(f"Cache hit for search: {cache_key}")
                        return json.loads(content)
                else:
                    logger.info(f"Cache expired for search: {cache_key}")
        except Exception as e:
            logger.error(f"Error reading from cache: {str(e)}")
        
        return None
    
    async def _save_to_cache(self, cache_key: str, results: Dict[str, Any]):
        """Save search results to cache"""
        if not self.use_cache:
            return
            
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
        
        try:
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(json.dumps(results))
            logger.info(f"Saved search results to cache: {cache_key}")
        except Exception as e:
            logger.error(f"Error saving to cache: {str(e)}")
    
    async def search(self, query: str, engine: Optional[str] = None, num_results: int = 5) -> Dict[str, Any]:
        """Perform a web search using crawl4ai"""
        # Check if we're in offline mode
        offline_status = self.offline_mode_manager.get_offline_status()
        if offline_status["is_offline"]:
            logger.info("System is in offline mode, returning cached results only")
            # Try to get from cache
            engine_url = engine or self.search_engine
            cache_key = self._get_cache_key(query, engine_url, num_results)
            cached_results = await self._get_from_cache(cache_key)
            
            if cached_results:
                return cached_results
            else:
                # Return empty results with offline mode notice
                return {
                    "query": query,
                    "results": [],
                    "offline_mode": True,
                    "message": "Web search is unavailable in offline mode"
                }
        
        # Online mode - proceed with search
        engine_url = engine or self.search_engine
        
        # Try to get from cache
        cache_key = self._get_cache_key(query, engine_url, num_results)
        cached_results = await self._get_from_cache(cache_key)
        if cached_results:
            return cached_results
        
        # Encode the query for URL
        encoded_query = urllib.parse.quote(query)
        search_url = f"{engine_url}{encoded_query}"
        
        logger.info(f"Searching with URL: {search_url}")
        
        # Configure the crawler
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Always get fresh results
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(threshold=0.4, threshold_type="fixed")
            )
        )
        
        try:
            # Perform the search
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    config=run_config
                )
                
                # Extract search results from the page
                search_results = self._extract_search_results(result.html, query, num_results)
                
                # Save to cache
                await self._save_to_cache(cache_key, search_results)
                
                return search_results
        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")
            # Return empty results on error
            return {
                "query": query,
                "results": [],
                "error": str(e)
            }
    
    def _extract_search_results(self, html: str, query: str, num_results: int) -> Dict[str, Any]:
        """Extract search results from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        
        # Format for the results
        formatted_results = {
            "query": query,
            "results": []
        }
        
        # Try to extract Google search results
        search_divs = soup.select("div.g")
        if not search_divs:
            # Try alternative selectors for different search engines
            search_divs = soup.select("div.result") or soup.select(".searchResult") or soup.select(".result")
        
        count = 0
        for div in search_divs:
            if count >= num_results:
                break
                
            # Try to extract title and link
            title_elem = div.select_one("h3") or div.select_one(".title") or div.select_one("a")
            link_elem = div.select_one("a")
            
            # Try to extract snippet
            snippet_elem = div.select_one(".snippet") or div.select_one(".description") or div.select_one(".content")
            
            if title_elem and link_elem and link_elem.get("href"):
                link = link_elem.get("href")
                
                # Clean up Google redirect links
                if link.startswith("/url?q="):
                    link = link.split("/url?q=")[1].split("&")[0]
                
                # Skip non-http links
                if not link.startswith("http"):
                    continue
                    
                result = {
                    "title": title_elem.get_text(strip=True),
                    "link": link,
                    "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                    "source": "web_search"
                }
                
                formatted_results["results"].append(result)
                count += 1
        
        return formatted_results
    
    async def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from a web page using crawl4ai"""
        # Check if we're in offline mode
        offline_status = self.offline_mode_manager.get_offline_status()
        if offline_status["is_offline"]:
            logger.info("System is in offline mode, web content extraction unavailable")
            return {
                "url": url,
                "success": False,
                "offline_mode": True,
                "message": "Web content extraction is unavailable in offline mode"
            }
            
        try:
            # Configure the crawler for content extraction
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=PruningContentFilter(threshold=0.3, threshold_type="fixed")
                )
            )
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=run_config
                )
                
                # Get the page title
                soup = BeautifulSoup(result.html, "html.parser")
                title = soup.title.string if soup.title else ""
                
                # Use the markdown content as it's already cleaned
                content = result.markdown.fit_markdown or result.markdown.raw_markdown
                
                return {
                    "url": url,
                    "success": True,
                    "title": title,
                    "content": content[:10000]  # Limit content length
                }
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return {
                "url": url,
                "success": False,
                "error": str(e)
            }