# Python MCP Server Template (FastMCP)

## Minimal server

```python
from fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str) -> str:
    """One-line description Claude will use to decide when to call this."""
    return f"result: {param}"

if __name__ == "__main__":
    mcp.run()
```

## Tool with typed parameters and error handling

```python
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

mcp = FastMCP("server-name")

@mcp.tool()
def fetch_data(query: str, limit: int = 10) -> list[dict]:
    """Fetch records matching query from the data source."""
    if not query:
        raise ToolError("query must not be empty")
    # ... implementation
    return results
```

## Tool returning structured content

```python
@mcp.tool()
def get_report(id: str) -> dict:
    """Return a full report object by ID."""
    return {"id": id, "status": "ok", "data": [...]}
```

## Tool with external API call

```python
import os
import httpx
from fastmcp import FastMCP

mcp = FastMCP("server-name")
API_KEY = os.environ["API_KEY"]
BASE_URL = os.environ.get("API_BASE_URL", "https://api.example.com")

@mcp.tool()
def call_api(endpoint: str, payload: dict) -> dict:
    """Call the external API endpoint with payload."""
    with httpx.Client() as client:
        response = client.post(f"{BASE_URL}/{endpoint}", json=payload,
                               headers={"Authorization": f"Bearer {API_KEY}"})
        response.raise_for_status()
        return response.json()
```

## requirements.txt

```
fastmcp>=2.0.0
httpx>=0.27.0   # if making HTTP requests
```

## Registration in ~/.claude.json (stdio, user scope)

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "python3",
      "args": ["~/mcp-servers/server-name/main.py"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

## Notes

- Tool docstring is what Claude reads to understand when/how to call the tool — make it precise
- FastMCP maps Python type hints to JSON schema automatically
- Use `raise ToolError(msg)` to return user-visible errors without crashing the server
- Env vars are passed via the `env` block in the MCP config; read them with `os.environ`
- For async tools: `async def my_tool(...) -> ...:` works with `await` inside
