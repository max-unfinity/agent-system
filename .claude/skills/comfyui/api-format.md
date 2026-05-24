# Writing Workflows in API Format

## UI format vs API format

ComfyUI has two JSON formats:

- **UI format**: Used by the web editor. Has `nodes` array (with positions, sizes, visual metadata) and `links` array. **Cannot be submitted to `/prompt`.**
- **API format**: Flat dict of `node_id → {class_type, inputs}`. This is what `/prompt` accepts.

To export API format from the UI: **File → Export (API)**.

## API format structure

```json
{
  "node_id": {
    "class_type": "NodeClassName",
    "inputs": {
      "widget_input": "literal_value",
      "connected_input": ["source_node_id", output_slot_index]
    }
  }
}
```

- `node_id`: any unique string (typically numeric: `"1"`, `"2"`, etc.)
- `class_type`: exact node class name (case-sensitive, e.g. `"KSampler"`, `"CLIPTextEncode"`)
- Literal inputs: strings, ints, floats directly
- Connected inputs: `["source_node_id", output_index]` — references another node's output slot (0-based)

## Minimal txt2img example

```json
{
  "4": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": "SDXL/sd_xl_base_1.0.safetensors"}
  },
  "5": {
    "class_type": "EmptyLatentImage",
    "inputs": {"width": 1024, "height": 1024, "batch_size": 1}
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {"clip": ["4", 1], "text": "a horse on a snowy road"}
  },
  "7": {
    "class_type": "CLIPTextEncode",
    "inputs": {"clip": ["4", 1], "text": "blurry, low quality"}
  },
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["4", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0],
      "seed": 42, "steps": 20, "cfg": 7.0,
      "sampler_name": "euler", "scheduler": "karras", "denoise": 1.0
    }
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {"images": ["8", 0], "filename_prefix": "output"}
  }
}
```

## Output slot indices for common loaders

| Node | Output 0 | Output 1 | Output 2 |
|------|----------|----------|----------|
| `CheckpointLoaderSimple` | MODEL | CLIP | VAE |
| `LoadImage` | IMAGE | MASK |  |
| `VAEEncode` | LATENT |  |  |
| `KSampler` | LATENT |  |  |
| `VAEDecode` | IMAGE |  |  |

When unsure about output slots, query: `curl -s http://127.0.0.1:8188/object_info/NodeName | python3 -c "import json,sys; d=json.load(sys.stdin); n=list(d.values())[0]; print('outputs:', list(zip(n['output_name'],n['output'])))"`

## Converting UI format → API format

The UI format cannot be submitted directly. To convert programmatically:

1. Parse the `nodes` array and `links` array from UI JSON
2. Skip nodes with `mode: 4` (bypassed/muted)
3. For each node, build `{class_type, inputs}`:
   - Connected inputs: look up the link in the `links` array to find `[link_id, from_node, from_slot, to_node, to_slot, type]`
   - Widget inputs: map from `widgets_values` to input names (tricky — widget ordering includes UI-only controls like `control_after_generate`)
4. Best practice: open the workflow in the UI once, then **File → Export (API)** to get the clean format

## Tips

- Only nodes reachable from an output node (`output_node: true`, like `SaveImage`) are executed. Disconnected subgraphs are silently skipped.
- Node IDs are strings in API format, even when numeric.
- `seed` fields with `control_after_generate` in the UI are just plain integers in API format — the "randomize"/"fixed" behavior is UI-only.
- For randomized seeds in headless mode, generate them yourself: `random.randint(0, 2**64 - 1)`.
