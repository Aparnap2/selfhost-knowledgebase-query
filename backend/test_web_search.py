#!/usr/bin/env python3
import asyncio
from web_search import WebSearch
import json

async def test_search():
    search = WebSearch()
    
    # Test search
    print("Testing web search...")
    results = await search.search("Python programming language")
    print(f"Found {len(results['results'])} results")
    print(json.dumps(results, indent=2))
    
    # Test content extraction
    if results['results']:
        url = results['results'][0]['link']
        print(f"\nTesting content extraction from {url}...")
        content = await search.extract_content(url)
        print(f"Extraction success: {content['success']}")
        if content['success']:
            print(f"Title: {content['title']}")
            print(f"Content preview: {content['content'][:200]}...")

if __name__ == "__main__":
    asyncio.run(test_search())