# ComfyUI REST API Reference

Base URL: `http://127.0.0.1:8188` (default)

## Discovery & Metadata

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/object_info` | Full node catalog (all registered nodes with inputs/outputs/defaults) |
| GET | `/object_info/{node_class}` | Single node definition. Returns `{}` if not found. |
| GET | `/system_stats` | OS, RAM, VRAM, GPU name, versions |
| GET | `/models` | List model folder types (`checkpoints`, `loras`, `vae`, `controlnet`, ...) |
| GET | `/models/{folder}` | List filenames in a model folder |
| GET | `/embeddings` | List installed embeddings |
| GET | `/extensions` | Frontend JS extension paths |
| GET | `/view_metadata/{folder}?filename=X` | Read safetensors metadata header |

## Execution

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/prompt` | `{"prompt": {...}, "client_id": "uuid"}` | Queue a workflow. Returns `{"prompt_id": "uuid", "number": N, "node_errors": {}}` |
| GET | `/prompt` | — | Queue size: `{"exec_info": {"queue_remaining": N}}` |
| GET | `/queue` | — | Full queue: `{"queue_running": [...], "queue_pending": [...]}` |
| POST | `/queue` | `{"clear": true}` | Clear all pending items |
| POST | `/queue` | `{"delete": ["id1", "id2"]}` | Delete specific queue items by prompt_id |
| GET | `/history` | `?max_items=N&offset=N` | Execution history |
| GET | `/history/{prompt_id}` | — | Single prompt history with outputs |
| POST | `/history` | `{"clear": true}` or `{"delete": ["id"]}` | Manage history |

## Control

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/interrupt` | `{}` | Stop current execution |
| POST | `/interrupt` | `{"prompt_id": "uuid"}` | Stop specific prompt (if currently running) |
| POST | `/free` | `{"unload_models": true, "free_memory": true}` | Free VRAM. Flags are checked between queue items. |

## File I/O

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload/image` | Multipart upload. Fields: `image` (file), `type` (input/temp/output), `subfolder`, `overwrite` |
| POST | `/upload/mask` | Upload mask composited onto existing image |
| GET | `/view?filename=X&type=output&subfolder=` | Download output file |
| GET | `/view?filename=X&preview=webp;90` | Get preview thumbnail |

## WebSocket

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| WS | `/ws?clientId=uuid` | Real-time event stream |

WebSocket message types:
- `{"type": "status", "data": {"status": {"exec_info": {"queue_remaining": N}}}}` — queue status
- `{"type": "execution_start", "data": {"prompt_id": "uuid"}}` — prompt starts
- `{"type": "executing", "data": {"node": "node_id", "prompt_id": "uuid"}}` — node executing
- `{"type": "executing", "data": {"node": null, "prompt_id": "uuid"}}` — prompt finished
- `{"type": "progress", "data": {"value": 5, "max": 20, "prompt_id": "uuid", "node": "3"}}` — sampling progress
- Binary messages: latent preview images (8-byte header + image data)

## `/prompt` POST payload

```json
{
  "prompt": { "node_id": {"class_type": "...", "inputs": {...}}, ... },
  "client_id": "optional-uuid-for-websocket",
  "prompt_id": "optional-custom-id",
  "extra_data": {
    "extra_pnginfo": {"workflow": {...}},
    "api_key_comfy_org": "key-for-api-nodes"
  }
}
```

## `/history/{prompt_id}` response

```json
{
  "prompt_id": {
    "prompt": [queue_number, prompt_id, prompt_dict, extra_data, output_node_ids],
    "outputs": {
      "node_id": {
        "images": [{"filename": "output_00001_.png", "subfolder": "", "type": "output"}]
      }
    },
    "status": {
      "status_str": "success",
      "completed": true,
      "messages": [["execution_start", {...}], ["execution_cached", {...}], ...]
    }
  }
}
```
