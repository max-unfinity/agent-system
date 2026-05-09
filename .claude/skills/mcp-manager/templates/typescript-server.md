# TypeScript MCP Server Template (Node.js SDK)

## Minimal server

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "server-name", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "my_tool",
      description: "One-line description Claude will use to decide when to call this.",
      inputSchema: {
        type: "object",
        properties: {
          param: { type: "string", description: "The input parameter" },
        },
        required: ["param"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "my_tool") {
    const { param } = request.params.arguments as { param: string };
    return { content: [{ type: "text", text: `result: ${param}` }] };
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

## package.json

```json
{
  "name": "server-name",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^22.0.0"
  }
}
```

## tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "strict": true
  },
  "include": ["src/**/*"]
}
```

## Registration in ~/.claude.json (stdio, user scope)

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "node",
      "args": ["~/mcp-servers/server-name/dist/index.js"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

## Notes

- Tool description is what Claude reads to decide when/how to call the tool — make it precise
- `inputSchema` uses JSON Schema; mark required fields in the `required` array
- Return errors by throwing — the SDK formats them correctly for MCP
- Build before registering: `npm run build`
- For dev without build step, use `tsx`: `command: "npx", args: ["tsx", "src/index.ts"]`
