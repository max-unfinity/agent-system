# Batch Generation (No User Interaction)

## Architecture

ComfyUI's queue is sequential per GPU. For batch generation:

1. Start the server once (models load into VRAM).
2. Submit all prompts to the queue — they execute one by one, reusing loaded models.
3. Track completion via `/history` or WebSocket.

Models stay in VRAM between runs when using the same checkpoint — only the first run pays the load cost.

## Strategy: queue-ahead with tracking

```python
import json, os, random, time, uuid, urllib.request

SERVER = "http://127.0.0.1:8188"

def queue_prompt(prompt):
    prompt_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt, "client_id": prompt_id}).encode("utf-8")
    req = urllib.request.Request(f"{SERVER}/prompt", data=payload)
    req.add_header("Content-Type", "application/json")
    resp = json.loads(urllib.request.urlopen(req).read())
    if "error" in resp:
        raise RuntimeError(f"Queue error: {resp['error']}")
    return resp["prompt_id"]

def build_prompt(seed, text, **overrides):
    """Build one prompt dict. Customize per your workflow."""
    p = {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": overrides.get("checkpoint", "SDXL/sd_xl_base_1.0.safetensors")}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["4", 1], "text": text}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["4", 1], "text": overrides.get("negative", "")}},
        "3": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["5", 0], "seed": seed,
                         "steps": overrides.get("steps", 20),
                         "cfg": overrides.get("cfg", 7.0),
                         "sampler_name": "dpmpp_2m_sde_gpu",
                         "scheduler": "karras", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0],
                         "filename_prefix": overrides.get("prefix", f"batch_{seed}")}},
    }
    return p

def batch_generate(prompts_config, max_queue_ahead=10):
    """
    prompts_config: list of dicts with keys like {seed, text, ...}
    max_queue_ahead: how many prompts to keep in the queue at once
    """
    submitted = {}   # prompt_id -> config
    completed = {}   # prompt_id -> history entry
    failed = []
    queue = list(prompts_config)

    def check_done():
        for pid in list(submitted):
            if pid in completed:
                continue
            try:
                hist = json.loads(urllib.request.urlopen(f"{SERVER}/history/{pid}").read())
                if pid in hist:
                    entry = hist[pid]
                    status = entry.get("status", {}).get("status_str", "")
                    if status == "error":
                        failed.append((pid, submitted[pid]))
                        del submitted[pid]
                    else:
                        completed[pid] = entry
            except Exception:
                pass

    total = len(queue)
    while queue or len(completed) + len(failed) < total:
        check_done()

        # Fill the queue up to max_queue_ahead
        pending = len(submitted) - len(completed) - len(failed)
        while queue and pending < max_queue_ahead:
            cfg = queue.pop(0)
            prompt = build_prompt(**cfg)
            try:
                pid = queue_prompt(prompt)
                submitted[pid] = cfg
                pending += 1
            except RuntimeError as e:
                print(f"Failed to queue: {e}")
                failed.append((None, cfg))

        done = len(completed) + len(failed)
        print(f"\rProgress: {done}/{total} done, {pending} in queue", end="", flush=True)
        time.sleep(2)

    print(f"\nBatch complete: {len(completed)} succeeded, {len(failed)} failed")
    return completed, failed


# --- Usage ---
if __name__ == "__main__":
    configs = [
        {"seed": random.randint(0, 2**64-1), "text": f"a horse in a field, variation {i}"}
        for i in range(1000)
    ]
    completed, failed = batch_generate(configs, max_queue_ahead=5)
```

## Key considerations

### Queue depth

Don't submit all 1000 prompts at once — ComfyUI stores the full prompt dict in memory for each queued item. Submit in rolling batches of 5–10.

### Randomizing seeds

In headless mode, the UI's "randomize" behavior doesn't apply. Generate seeds yourself:

```python
seed = random.randint(0, 2**64 - 1)
```

### Filename collisions

Use unique `filename_prefix` per prompt (e.g. include the seed or an index). ComfyUI appends a counter (`_00001_`), but prefixes avoid confusion.

### Interrupting a batch

```bash
# Clear all pending items from the queue
curl -s -X POST http://127.0.0.1:8188/queue \
  -H "Content-Type: application/json" -d '{"clear": true}'

# Interrupt the currently running item
curl -s -X POST http://127.0.0.1:8188/interrupt
```

### Monitoring queue state

```bash
# How many items remain
curl -s http://127.0.0.1:8188/prompt
# Returns: {"exec_info": {"queue_remaining": 42}}

# Detailed queue contents
curl -s http://127.0.0.1:8188/queue | python3 -m json.tool
```

### Memory management between different checkpoints

If your batch switches between checkpoints, the old model is evicted when the new one loads (if VRAM is insufficient). To force cleanup:

```bash
curl -s -X POST http://127.0.0.1:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

### Parallel execution (multi-GPU)

ComfyUI does not natively support multi-GPU parallel execution from a single server. For multi-GPU parallelism:

- Run separate ComfyUI instances on different ports, each pinned to a GPU: `--cuda-device 0 --port 8188`, `--cuda-device 1 --port 8189`
- Distribute prompts across instances in round-robin
