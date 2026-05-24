---
name: comfyui
description: ComfyUI project management, server starting, API execution, image generation, and node discovery. Use this skill whenever you get any mention of ComfyUI.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Agent
  - WebFetch
  - WebSearch
effort: high
---

# ComfyUI Skill

This skill covers headless ComfyUI operation: server management, workflow authoring in API format, single and batch execution, and node discovery.

## Quick reference files

Load these supporting docs as needed — don't read them all upfront:

| File | When to load |
|------|-------------|
| [server.md](server.md) | Starting/stopping the headless server, CLI flags, health checks |
| [api-format.md](api-format.md) | Writing workflows in API JSON format, node wiring, converting UI→API |
| [run-single.md](run-single.md) | Submitting a single workflow, polling, downloading results |
| [batch.md](batch.md) | Generating many images in a loop, queue management, parallelism |
| [nodes.md](nodes.md) | Discovering nodes, inspecting inputs/outputs, searching by category |
| [api-endpoints.md](api-endpoints.md) | Full REST API reference (all endpoints, methods, payloads) |

## Standing instructions

- Always use the API format (flat dict of `node_id -> {class_type, inputs}`) when building workflows programmatically. Never submit the UI format (with `nodes`/`links` arrays) to `/prompt`.
- Use `SaveImage` instead of `PreviewImage` for headless runs — `PreviewImage` only sends data over WebSocket.
- Before building a workflow, inspect unfamiliar nodes via `/object_info/{NodeClass}` to get exact input names, types, defaults, and allowed values.
- When the user asks about a specific node, always query `/object_info/{NodeClass}` live rather than guessing — node signatures change across versions and custom node updates.
- For batch runs, queue all prompts upfront and track `prompt_id`s. ComfyUI processes its queue sequentially per-GPU; models stay loaded between runs.
- Use `/free` with `{"unload_models": true}` to reclaim VRAM between different model workflows.

## Discovering what's available

```bash
# List all node categories
`curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json,sys; data=json.load(sys.stdin)
for c in sorted(set(v.get('category','') for v in data.values())): print(c)
"`

# List nodes in a category (e.g. sampling)
`curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json,sys; data=json.load(sys.stdin)
cat='sampling'
for n,v in sorted(data.items()):
    if v.get('category','').startswith(cat): print(f'{n}: {v.get(\"description\",\"\")[:80]}')
"`

# Inspect a specific node
`curl -s http://127.0.0.1:8188/object_info/KSampler | python3 -m json.tool`
```

## Finding node definitions locally (server not running)

When the server is not running, search node source files directly:

```bash
# Built-in nodes
grep -r "class.*:" ~/ComfyUI/nodes.py | grep "INPUT_TYPES\|RETURN_TYPES\|CATEGORY"
# Extra built-in nodes
grep -rl "NODE_CLASS_MAPPINGS" ~/ComfyUI/comfy_extras/
# Custom nodes
grep -rl "NODE_CLASS_MAPPINGS" ~/ComfyUI/custom_nodes/

# Find a specific node class
grep -rn "class KSampler" ~/ComfyUI/nodes.py ~/ComfyUI/comfy_extras/ ~/ComfyUI/custom_nodes/

# Find all nodes with a keyword
grep -rn "INPUT_TYPES" ~/ComfyUI/custom_nodes/comfyui_essentials/ | head -20
```

## Available models (live query)

```bash
# List model folder types
`curl -s http://127.0.0.1:8188/models | python3 -m json.tool`

# List checkpoints
`curl -s http://127.0.0.1:8188/models/checkpoints | python3 -m json.tool`

# List LoRAs, controlnets, etc.
`curl -s http://127.0.0.1:8188/models/loras | python3 -m json.tool`
`curl -s http://127.0.0.1:8188/models/controlnet | python3 -m json.tool`
```
