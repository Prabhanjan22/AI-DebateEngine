"""
backend/mcp/mcp_manager.py

A lightweight Model Context Protocol (MCP) manager that provides external tools
(like Wikipedia Search) to the LLM agents during the debate.
"""

import httpx
import json

class MCPManager:
    """
    Registry for tools available to debate agents.
    Provides schemas for the LLM and executes tool calls.
    """
    
    def __init__(self):
        # We define tools in the exact schema format Groq/OpenAI expects.
        self._tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_wikipedia",
                    "description": "Searches Wikipedia for a given topic and returns a brief summary. Use this to find factual information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The search query (e.g., 'Tokyo population 2024')"
                            }
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

    def get_tools_schema(self) -> list[dict]:
        """Return the JSON schemas of all available tools."""
        return self._tools

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Execute a tool by name and return its result as a string.
        """
        # Route the requested tool execution to its specific handler method
        if tool_name == "search_wikipedia":
            return self._search_wikipedia(arguments.get("query", ""))
        
        return f"Error: Tool '{tool_name}' not found."

    def _search_wikipedia(self, query: str) -> str:
        """
        Hits the public Wikipedia API to get a summary of a topic.
        """
        if not query:
            return "Error: Empty query provided."
            
        # We use httpx to call the Wikipedia REST API (summary endpoint)
        # Note: In a real production app, we'd handle pagination, disambiguation, etc.
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("extract", "No summary found for this topic.")
                elif response.status_code == 404:
                    # If direct match fails, try a search to get the closest title
                    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&utf8=&format=json"
                    search_res = client.get(search_url)
                    if search_res.status_code == 200:
                        search_data = search_res.json()
                        search_results = search_data.get("query", {}).get("search", [])
                        if search_results:
                            best_title = search_results[0]["title"]
                            return f"Topic not found directly. Did you mean '{best_title}'? Try searching for exactly that title."
                    
                    return f"Topic '{query}' not found on Wikipedia."
                else:
                    return f"Wikipedia API returned status code {response.status_code}"
                    
        except Exception as e:
            return f"Error contacting Wikipedia: {str(e)}"
