# ComfyUI Headless Server

## Starting the server

```bash
cd ~/ComfyUI && python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch
```

Key flags:

| Flag | Purpose |
|------|---------|
| `--listen 127.0.0.1` | Bind address. Use `0.0.0.0` for remote access. |
| `--port 8188` | HTTP port (default 8188) |
| `--disable-auto-launch` | Don't open browser |
| `--cuda-device N` | Select GPU index |
| `--gpu-only` | Keep everything on GPU (fast, needs VRAM) |
| `--highvram` | Keep models in VRAM between runs |
| `--lowvram` | Aggressive offloading for small GPUs |
| `--cpu` | CPU-only mode |
| `--disable-smart-memory` | Disable automatic memory management |
| `--preview-method auto` | Enable latent previews (auto/latent2rgb/taesd) |
| `--output-directory /path` | Custom output dir |
| `--input-directory /path` | Custom input dir |
| `--temp-directory /path` | Custom temp dir |

## Running in background

```bash
# With nohup
nohup python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch > comfyui.log 2>&1 &

# With tmux
tmux new-session -d -s comfyui 'cd ~/ComfyUI && python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch'
```

## Health check

```bash
curl -s http://127.0.0.1:8188/system_stats | python3 -m json.tool
```

Returns OS info, RAM, VRAM, GPU name, ComfyUI version, PyTorch version.

## Stopping

```bash
# Find and kill
pkill -f "python main.py.*8188"
```

## Freeing VRAM without restart

```bash
# Unload all models from VRAM
curl -s -X POST http://127.0.0.1:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

This sets a flag checked between queue items — takes effect after the current job finishes.
