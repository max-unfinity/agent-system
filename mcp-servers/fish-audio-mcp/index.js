#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { encode as msgpackEncode } from "@msgpack/msgpack";
import { readFileSync, writeFileSync } from "fs";
import { resolve } from "path";

const API_KEY = process.env.FISH_API_KEY;
if (!API_KEY) {
  process.stderr.write("FISH_API_KEY env var is required\n");
  process.exit(1);
}

const BASE = "https://api.fish.audio";

function authHeaders(extra = {}) {
  return { authorization: `Bearer ${API_KEY}`, ...extra };
}

async function apiGet(path, query = {}) {
  const url = new URL(path, BASE);
  for (const [k, v] of Object.entries(query)) {
    if (v != null) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(new URL(path, BASE), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}: ${await res.text()}`);
  return { success: true };
}

async function ttsRequest(body, model, outputPath) {
  const packed = msgpackEncode(body);
  const res = await fetch(new URL("/v1/tts", BASE), {
    method: "POST",
    headers: authHeaders({
      "content-type": "application/msgpack",
      model: model || "s2-pro",
    }),
    body: packed,
  });
  if (!res.ok) throw new Error(`TTS → ${res.status}: ${await res.text()}`);
  const buf = Buffer.from(await res.arrayBuffer());
  const out = resolve(outputPath);
  writeFileSync(out, buf);
  return { path: out, size_bytes: buf.length };
}

// --- Tool definitions ---

const TOOLS = [
  {
    name: "tts_generate",
    description:
      "Generate speech from text using Fish Audio TTS. Emotion tags can be embedded in the text: S2-Pro uses [bracket tags] like [excited], [whispering], [sad, slow]; S1 uses (parenthesis tags) like (happy), (angry). Returns path to the output audio file.",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string", description: "Text to synthesize (may include emotion tags)" },
        output_path: { type: "string", description: "Where to save the audio file" },
        reference_id: { type: "string", description: "Voice model ID (from Discovery or your clone)" },
        model: { type: "string", enum: ["s2-pro", "s1"], default: "s2-pro" },
        format: { type: "string", enum: ["mp3", "wav", "pcm", "opus"], default: "mp3" },
        mp3_bitrate: { type: "integer", enum: [64, 128, 192], default: 128 },
        latency: { type: "string", enum: ["low", "normal", "balanced"], default: "normal" },
        chunk_length: { type: "integer", minimum: 100, maximum: 300 },
        normalize: { type: "boolean", default: true },
        temperature: { type: "number", minimum: 0, maximum: 1 },
        top_p: { type: "number", minimum: 0, maximum: 1 },
        speed: { type: "number", minimum: 0.5, maximum: 2.0, description: "Prosody speed multiplier" },
      },
      required: ["text", "output_path"],
    },
  },
  {
    name: "tts_clone_inline",
    description:
      "Zero-shot voice cloning: synthesize text using an inline reference audio sample (no persistent model created). Use ONLY when the user explicitly requests inline/zero-shot cloning. For most cases, prefer creating a persistent voice model first.",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string", description: "Text to synthesize" },
        output_path: { type: "string", description: "Where to save the audio file" },
        reference_audio_path: { type: "string", description: "Path to reference audio file (WAV/MP3/FLAC, 10-30s recommended)" },
        reference_text: { type: "string", description: "Exact transcript of the reference audio" },
        model: { type: "string", enum: ["s2-pro", "s1"], default: "s2-pro" },
        format: { type: "string", enum: ["mp3", "wav", "pcm", "opus"], default: "mp3" },
        temperature: { type: "number", minimum: 0, maximum: 1 },
        top_p: { type: "number", minimum: 0, maximum: 1 },
      },
      required: ["text", "output_path", "reference_audio_path", "reference_text"],
    },
  },
  {
    name: "voice_model_create",
    description:
      "Create a persistent voice model (clone) from one or more audio samples. Returns the new model ID which can be used as reference_id in tts_generate.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Model name" },
        voice_audio_paths: {
          type: "array",
          items: { type: "string" },
          description: "Paths to audio files (MP3/WAV/FLAC, 10s+ each)",
        },
        voice_texts: {
          type: "array",
          items: { type: "string" },
          description: "Transcripts matching each audio file (improves quality). Count must match voice_audio_paths.",
        },
        description: { type: "string" },
        visibility: { type: "string", enum: ["private", "public", "unlist"], default: "private" },
        enhance_audio_quality: { type: "boolean", default: true },
      },
      required: ["title", "voice_audio_paths"],
    },
  },
  {
    name: "voice_model_list",
    description: "List voice models. Set self=true to list only your own models.",
    inputSchema: {
      type: "object",
      properties: {
        page_size: { type: "integer", default: 10 },
        page_number: { type: "integer", default: 1 },
        self: { type: "boolean", default: false, description: "If true, list only your own models" },
        title: { type: "string", description: "Filter by title" },
        language: { type: "string", description: "Filter by language" },
        sort_by: { type: "string", enum: ["score", "task_count", "created_at"], default: "created_at" },
      },
    },
  },
  {
    name: "voice_model_get",
    description: "Get details of a specific voice model by ID.",
    inputSchema: {
      type: "object",
      properties: {
        model_id: { type: "string", description: "The voice model ID" },
      },
      required: ["model_id"],
    },
  },
  {
    name: "voice_model_delete",
    description: "Delete a voice model by ID. Only works on your own models.",
    inputSchema: {
      type: "object",
      properties: {
        model_id: { type: "string", description: "The voice model ID to delete" },
      },
      required: ["model_id"],
    },
  },
  {
    name: "stt_transcribe",
    description:
      "Transcribe audio to text using Fish Audio ASR. Returns transcript text and optional timestamps.",
    inputSchema: {
      type: "object",
      properties: {
        audio_path: { type: "string", description: "Path to the audio file (MP3/WAV/M4A/OGG/FLAC/AAC, max 20MB, max 60min)" },
        language: { type: "string", description: "Language hint (e.g. 'en', 'zh', 'ja'). Auto-detected if omitted." },
        ignore_timestamps: { type: "boolean", default: true, description: "Set false to get word-level timestamps (slower for audio <30s)" },
      },
      required: ["audio_path"],
    },
  },
  {
    name: "wallet_get_credits",
    description: "Check your Fish Audio API credit balance.",
    inputSchema: { type: "object", properties: {} },
  },
];

// --- Tool handlers ---

async function handleTtsGenerate(args) {
  const body = { text: args.text, format: args.format || "mp3" };
  if (args.reference_id) body.reference_id = args.reference_id;
  if (args.chunk_length) body.chunk_length = args.chunk_length;
  if (args.normalize != null) body.normalize = args.normalize;
  if (args.mp3_bitrate) body.mp3_bitrate = args.mp3_bitrate;
  if (args.latency) body.latency = args.latency;
  if (args.temperature != null) body.temperature = args.temperature;
  if (args.top_p != null) body.top_p = args.top_p;
  if (args.speed) body.prosody = { speed: args.speed };
  return ttsRequest(body, args.model, args.output_path);
}

async function handleTtsCloneInline(args) {
  const audioData = readFileSync(resolve(args.reference_audio_path));
  const body = {
    text: args.text,
    format: args.format || "mp3",
    references: [{ audio: audioData, text: args.reference_text }],
  };
  if (args.temperature != null) body.temperature = args.temperature;
  if (args.top_p != null) body.top_p = args.top_p;
  return ttsRequest(body, args.model, args.output_path);
}

async function handleVoiceModelCreate(args) {
  const form = new FormData();
  form.append("title", args.title);
  form.append("type", "tts");
  form.append("train_mode", "fast");
  form.append("visibility", args.visibility || "private");
  if (args.description) form.append("description", args.description);
  form.append("enhance_audio_quality", String(args.enhance_audio_quality ?? true));

  for (const p of args.voice_audio_paths) {
    const data = readFileSync(resolve(p));
    const name = p.split("/").pop();
    form.append("voices", new Blob([data]), name);
  }
  if (args.voice_texts) {
    for (const t of args.voice_texts) {
      form.append("texts", t);
    }
  }

  const res = await fetch(new URL("/model", BASE), {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error(`POST /model → ${res.status}: ${await res.text()}`);
  const result = await res.json();
  return { model_id: result._id, title: result.title, state: result.state, visibility: result.visibility };
}

async function handleVoiceModelList(args) {
  return apiGet("/model", {
    page_size: args.page_size || 10,
    page_number: args.page_number || 1,
    self: args.self || false,
    title: args.title,
    language: args.language,
    sort_by: args.sort_by || "created_at",
  });
}

async function handleVoiceModelGet(args) {
  return apiGet(`/model/${args.model_id}`);
}

async function handleVoiceModelDelete(args) {
  return apiDelete(`/model/${args.model_id}`);
}

async function handleSttTranscribe(args) {
  const audioData = readFileSync(resolve(args.audio_path));
  const body = {
    audio: audioData,
    language: args.language || null,
    ignore_timestamps: args.ignore_timestamps ?? true,
  };
  const packed = msgpackEncode(body);
  const res = await fetch(new URL("/v1/asr", BASE), {
    method: "POST",
    headers: authHeaders({ "content-type": "application/msgpack" }),
    body: packed,
  });
  if (!res.ok) throw new Error(`ASR → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function handleWalletGetCredits() {
  return apiGet("/wallet/self/api-credit");
}

const HANDLERS = {
  tts_generate: handleTtsGenerate,
  tts_clone_inline: handleTtsCloneInline,
  voice_model_create: handleVoiceModelCreate,
  voice_model_list: handleVoiceModelList,
  voice_model_get: handleVoiceModelGet,
  voice_model_delete: handleVoiceModelDelete,
  stt_transcribe: handleSttTranscribe,
  wallet_get_credits: handleWalletGetCredits,
};

// --- Server setup ---

const server = new Server(
  { name: "fish-audio-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const handler = HANDLERS[name];
  if (!handler) {
    return { content: [{ type: "text", text: `Unknown tool: ${name}` }], isError: true };
  }
  try {
    const result = await handler(args || {});
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (err) {
    return { content: [{ type: "text", text: `Error: ${err.message}` }], isError: true };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
