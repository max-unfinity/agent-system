# Node Discovery and Inspection

## Live inspection via API (server running)

### Get full catalog

```bash
curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json, sys; data = json.load(sys.stdin)
print(f'Total nodes: {len(data)}')"
```

### Inspect a specific node

```bash
curl -s http://127.0.0.1:8188/object_info/KSampler | python3 -m json.tool
```

Response structure per node:

```
{
  "NodeName": {
    "input": {
      "required": { "input_name": ["TYPE", {constraints}], ... },
      "optional": { ... },
      "hidden":   { ... }
    },
    "input_order": { "required": ["input1", "input2", ...] },
    "output":      ["TYPE1", "TYPE2"],
    "output_name": ["name1", "name2"],
    "name":         "NodeName",
    "display_name": "Node Display Name",
    "description":  "What it does",
    "category":     "category/subcategory",
    "python_module": "nodes" | "comfy_extras.nodes_x" | "custom_nodes.pack_name",
    "output_node":  true/false
  }
}
```

Input type formats:
- `["MODEL", {}]` — typed socket (connects to another node's output)
- `["INT", {"default": 20, "min": 1, "max": 10000}]` — numeric widget
- `["FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}]` — float widget
- `["STRING", {"default": "", "multiline": true}]` — text widget
- `[["option_a", "option_b", ...], {}]` — dropdown/combo (first element is a list)

### Search nodes by category

```bash
# List all categories
curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json, sys; data = json.load(sys.stdin)
for c in sorted(set(v.get('category','') for v in data.values())): print(c)"

# List nodes in 'sampling' category
curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json, sys; data = json.load(sys.stdin)
cat = sys.argv[1]
for n, v in sorted(data.items()):
    if v.get('category','').startswith(cat):
        print(f'  {n}: {v.get(\"description\",\"\")[:80]}')
" sampling

# Search nodes by name substring
curl -s http://127.0.0.1:8188/object_info | python3 -c "
import json, sys; data = json.load(sys.stdin)
q = sys.argv[1].lower()
for n, v in sorted(data.items()):
    if q in n.lower() or q in v.get('display_name','').lower():
        print(f'  {n} ({v.get(\"category\",\"\")}): {v.get(\"description\",\"\")[:60]}')
" ipadapter
```

### Get allowed values for combo/dropdown inputs

```bash
# E.g., list all available sampler names
curl -s http://127.0.0.1:8188/object_info/KSampler | python3 -c "
import json, sys; d = json.load(sys.stdin)['KSampler']['input']['required']
for name, spec in d.items():
    if isinstance(spec[0], list):
        print(f'{name}: {spec[0]}')"
```

## Offline inspection (server not running)

### Node class pattern in source files

```python
class MyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {...}, "optional": {...}}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "process"
    CATEGORY = "image/filters"
    OUTPUT_NODE = False

# Bottom of file:
NODE_CLASS_MAPPINGS = {"MyNode": MyNode}
NODE_DISPLAY_NAME_MAPPINGS = {"MyNode": "My Node"}
```

### Finding nodes in source

```bash
# All node classes in built-in nodes
grep -n "class.*:" ~/ComfyUI/nodes.py | head -40

# All node files in comfy_extras
ls ~/ComfyUI/comfy_extras/nodes_*.py

# Custom node packs — list their registered nodes
for f in ~/ComfyUI/custom_nodes/*/; do
  echo "=== $(basename $f) ==="
  grep -h "NODE_CLASS_MAPPINGS" "$f"*.py "$f"**/*.py 2>/dev/null | head -5
done

# Find where a specific node class is defined
grep -rn "class KSampler" ~/ComfyUI/nodes.py ~/ComfyUI/comfy_extras/ ~/ComfyUI/custom_nodes/

# Find INPUT_TYPES for a specific node
grep -A 30 "class SetLatentNoiseMask" ~/ComfyUI/nodes.py
```

## Common node categories

| Category | Contains |
|----------|----------|
| `sampling` | KSampler, KSamplerAdvanced, SamplerCustom |
| `sampling/custom_sampling` | Noise, Sigmas, Guiders, SamplerCustomAdvanced |
| `conditioning` | CLIPTextEncode, ConditioningCombine, ConditioningSetArea |
| `conditioning/controlnet` | ControlNetApply, ControlNetApplyAdvanced |
| `latent` | EmptyLatentImage, LatentBlend, LatentComposite, SetLatentNoiseMask |
| `latent/inpaint` | VAEEncodeForInpaint |
| `image` | LoadImage, SaveImage, PreviewImage, ImageScale |
| `loaders` | CheckpointLoaderSimple, LoraLoader, VAELoader, CLIPLoader |
| `advanced/loaders` | UNETLoader, DualCLIPLoader |
| `mask` | MaskComposite, InvertMask, CropMask |
| `ipadapter` | IPAdapterAdvanced, IPAdapterModelLoader (from custom nodes) |
| `essentials/*` | ImageResize+, MaskFromColor+, InjectLatentNoise+ (from custom nodes) |
