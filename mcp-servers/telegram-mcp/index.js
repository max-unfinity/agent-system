#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { readFileSync } from "fs";
import { basename } from "path";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;

if (!BOT_TOKEN || !CHAT_ID) {
  process.stderr.write("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars are required\n");
  process.exit(1);
}

const API = `https://api.telegram.org/bot${BOT_TOKEN}`;

async function tgRequest(method, body) {
  const res = await fetch(`${API}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  if (!json.ok) throw new Error(json.description ?? "Telegram API error");
  return json.result;
}

async function sendDocument(filePath, caption) {
  const fileData = readFileSync(filePath);
  const name = basename(filePath);
  const form = new FormData();
  form.append("chat_id", String(CHAT_ID));
  form.append("document", new Blob([fileData]), name);
  if (caption) form.append("caption", caption);

  const res = await fetch(`${API}/sendDocument`, { method: "POST", body: form });
  const json = await res.json();
  if (!json.ok) throw new Error(json.description ?? "Telegram API error");
  return json.result;
}

const server = new Server(
  { name: "telegram-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_message",
      description: "Send a text message to the user via Telegram",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", description: "Message text (Markdown supported)" },
          parse_mode: { type: "string", enum: ["Markdown", "HTML"], description: "Optional formatting mode" },
        },
        required: ["text"],
      },
    },
    {
      name: "send_file",
      description: "Send a file to the user via Telegram",
      inputSchema: {
        type: "object",
        properties: {
          file_path: { type: "string", description: "Absolute path to the file to send" },
          caption: { type: "string", description: "Optional caption for the file" },
        },
        required: ["file_path"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;

  if (name === "send_message") {
    await tgRequest("sendMessage", {
      chat_id: CHAT_ID,
      text: args.text,
      parse_mode: args.parse_mode,
    });
    return { content: [{ type: "text", text: "Message sent" }] };
  }

  if (name === "send_file") {
    await sendDocument(args.file_path, args.caption);
    return { content: [{ type: "text", text: `File sent: ${basename(args.file_path)}` }] };
  }

  throw new Error(`Unknown tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
