"""
Web tools for search, browser automation, and API interactions.
"""

import aiohttp
import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import json

from .base import AsyncTool
from ..models import ToolCategory


class WebSearchTool(AsyncTool):
    """Tool for web search operations."""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            category=ToolCategory.WEB,
            description="Search the web using various search engines"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute web search."""
        query = parameters.get("query")
        engine = parameters.get("engine", "duckduckgo")
        max_results = parameters.get("max_results", 10)
        
        if not query:
            raise ValueError("Query is required")
        
        if engine == "duckduckgo":
            return await self._search_duckduckgo(query, max_results)
        elif engine == "google":
            return await self._search_google(query, max_results)
        else:
            raise ValueError(f"Unsupported search engine: {engine}")
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo."""
        # This is a simplified implementation
        # In a real implementation, you'd use a proper DuckDuckGo API or scraper
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    # Extract results from DuckDuckGo response
                    for item in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(item, dict) and "Text" in item and "FirstURL" in item:
                            results.append({
                                "title": item.get("Text", "").split(" - ")[0],
                                "url": item.get("FirstURL", ""),
                                "snippet": item.get("Text", ""),
                                "source": "DuckDuckGo"
                            })
                    
                    return results
                else:
                    raise RuntimeError(f"Search failed with status {response.status}")
    
    async def _search_google(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using Google (placeholder implementation)."""
        # This would require Google Custom Search API or web scraping
        # For now, return a placeholder
        return [{
            "title": f"Google search result for: {query}",
            "url": f"https://www.google.com/search?q={query}",
            "snippet": "This is a placeholder for Google search results",
            "source": "Google"
        }]
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "engine": {
                    "type": "string",
                    "enum": ["duckduckgo", "google"],
                    "default": "duckduckgo",
                    "description": "Search engine to use"
                },
                "max_results": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of results to return"
                }
            },
            "required": ["query"]
        }


class BrowserAutomationTool(AsyncTool):
    """Tool for browser automation."""
    
    def __init__(self):
        super().__init__(
            name="browser_automation",
            category=ToolCategory.WEB,
            description="Automate browser operations like opening pages, clicking, filling forms"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute browser automation."""
        operation = parameters.get("operation")
        
        if operation == "navigate":
            url = parameters.get("url")
            if not url:
                raise ValueError("URL is required for navigate operation")
            return await self._navigate_to_url(url)
        elif operation == "click":
            selector = parameters.get("selector")
            if not selector:
                raise ValueError("Selector is required for click operation")
            return await self._click_element(selector)
        elif operation == "fill_form":
            form_data = parameters.get("form_data", {})
            return await self._fill_form(form_data)
        elif operation == "get_text":
            selector = parameters.get("selector")
            return await self._get_element_text(selector)
        elif operation == "screenshot":
            return await self._take_screenshot()
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _navigate_to_url(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        # This is a placeholder implementation
        # In a real implementation, you'd use Playwright or Selenium
        return {
            "success": True,
            "url": url,
            "title": f"Page title for {url}",
            "message": "Navigation completed (placeholder)"
        }
    
    async def _click_element(self, selector: str) -> Dict[str, Any]:
        """Click an element."""
        # Placeholder implementation
        return {
            "success": True,
            "selector": selector,
            "message": "Element clicked (placeholder)"
        }
    
    async def _fill_form(self, form_data: Dict[str, str]) -> Dict[str, Any]:
        """Fill form fields."""
        # Placeholder implementation
        return {
            "success": True,
            "filled_fields": list(form_data.keys()),
            "message": "Form filled (placeholder)"
        }
    
    async def _get_element_text(self, selector: str) -> str:
        """Get text from an element."""
        # Placeholder implementation
        return f"Text from element {selector} (placeholder)"
    
    async def _take_screenshot(self) -> str:
        """Take a screenshot."""
        # Placeholder implementation
        return "screenshot_placeholder.png"
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["navigate", "click", "fill_form", "get_text", "screenshot"],
                    "description": "Browser operation to perform"
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (for navigate operation)"
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element (for click/get_text operations)"
                },
                "form_data": {
                    "type": "object",
                    "description": "Form data to fill (for fill_form operation)"
                }
            },
            "required": ["operation"]
        }


class APITool(AsyncTool):
    """Tool for API interactions."""
    
    def __init__(self):
        super().__init__(
            name="api_interactions",
            category=ToolCategory.WEB,
            description="Make HTTP requests to APIs and web services"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute API request."""
        url = parameters.get("url")
        method = parameters.get("method", "GET").upper()
        headers = parameters.get("headers", {})
        data = parameters.get("data")
        params = parameters.get("params", {})
        
        if not url:
            raise ValueError("URL is required")
        
        return await self._make_request(url, method, headers, data, params)
    
    async def _make_request(self, url: str, method: str, headers: Dict[str, str], 
                          data: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request."""
        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers, params=params) as response:
                        return await self._process_response(response)
                elif method == "POST":
                    async with session.post(url, headers=headers, json=data, params=params) as response:
                        return await self._process_response(response)
                elif method == "PUT":
                    async with session.put(url, headers=headers, json=data, params=params) as response:
                        return await self._process_response(response)
                elif method == "DELETE":
                    async with session.delete(url, headers=headers, params=params) as response:
                        return await self._process_response(response)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Request failed: {e}")
    
    async def _process_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Process HTTP response."""
        try:
            # Try to parse as JSON first
            content = await response.json()
            content_type = "json"
        except (json.JSONDecodeError, aiohttp.ContentTypeError):
            # Fall back to text
            content = await response.text()
            content_type = "text"
        
        return {
            "status_code": response.status,
            "headers": dict(response.headers),
            "content": content,
            "content_type": content_type,
            "url": str(response.url)
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "API endpoint URL"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "default": "GET",
                    "description": "HTTP method"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers"
                },
                "data": {
                    "description": "Request body data"
                },
                "params": {
                    "type": "object",
                    "description": "URL parameters"
                }
            },
            "required": ["url"]
        }
