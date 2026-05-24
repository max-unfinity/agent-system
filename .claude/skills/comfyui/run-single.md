# Running a Single Workflow

## Submit → Poll → Collect pattern

### 1. Submit the prompt

```python
import json, uuid, urllib.request

SERVER = "http://127.0.0.1:8188"

def queue_prompt(prompt):
    prompt_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt, "client_id": prompt_id}).encode("utf-8")
    req = urllib.request.Request(f"{SERVER}/prompt", data=payload)
    req.add_header("Content-Type", "application/json")
    resp = json.loads(urllib.request.urlopen(req).read())
    if "error" in resp:
        raise RuntimeError(f"Prompt error: {resp['error']}")
    if resp.get("node_errors"):
        raise RuntimeError(f"Node errors: {resp['node_errors']}")
    return resp["prompt_id"]
```

### 2. Poll for completion

```python
import time

def wait_for_prompt(prompt_id, poll_interval=2):
    while True:
        time.sleep(poll_interval)
        resp = json.loads(urllib.request.urlopen(f"{SERVER}/queue").read())
        running_ids = [item[1] for item in resp.get("queue_running", [])]
        pending_ids = [item[1] for item in resp.get("queue_pending", [])]
        if prompt_id not in running_ids and prompt_id not in pending_ids:
            break

    hist = json.loads(urllib.request.urlopen(f"{SERVER}/history/{prompt_id}").read())
    entry = hist.get(prompt_id)
    if not entry:
        raise RuntimeError("Prompt vanished from history")
    if entry.get("status", {}).get("status_str") == "error":
        raise RuntimeError(f"Execution failed: {entry['status']}")
    return entry
```

### 3. Collect output files

```python
def get_output_paths(history_entry, comfyui_dir="~/ComfyUI"):
    import os
    paths = []
    for node_id, node_out in history_entry.get("outputs", {}).items():
        for img in node_out.get("images", []):
            subfolder = img.get("subfolder", "")
            folder_type = img.get("type", "output")
            rel = os.path.join(subfolder, img["filename"]) if subfolder else img["filename"]
            paths.append(os.path.join(os.path.expanduser(comfyui_dir), folder_type, rel))
    return paths
```

### 4. Full single-run example

```python
prompt = { ... }  # API-format dict (see api-format.md)
prompt_id = queue_prompt(prompt)
entry = wait_for_prompt(prompt_id)
for path in get_output_paths(entry):
    print(f"Saved: {path}")
```

## Alternative: download via API instead of reading files

```python
import urllib.parse

def download_image(filename, subfolder="", folder_type="output"):
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    return urllib.request.urlopen(f"{SERVER}/view?{params}").read()
```

## Uploading input images via API

If input images aren't already in ComfyUI's input directory:

```python
import io, mimetypes
from urllib.request import Request, urlopen

def upload_image(filepath, image_type="input", overwrite=True):
    filename = os.path.basename(filepath)
    mime = mimetypes.guess_type(filepath)[0] or "image/png"
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + open(filepath, "rb").read() + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="type"\r\n\r\n{image_type}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n{"true" if overwrite else "false"}\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = Request(f"{SERVER}/upload/image", data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return json.loads(urlopen(req).read())
```

## Error handling

Common `/prompt` errors:
- `"type": "prompt_no_outputs"` — no SaveImage/PreviewImage node, or all output nodes are disconnected
- `"type": "invalid_prompt"` — unknown node class, missing required input, type mismatch
- `node_errors` dict — per-node validation failures with details on which input failed

Check `node_errors` in the response even when HTTP 200 is returned — partial validation errors can appear there.
