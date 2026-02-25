#!/usr/bin/env python3
import json
import os
import sys


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def fail(message):
    emit({"ok": False, "error": str(message)})
    raise SystemExit(1)


def read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception as exc:
        fail(f"invalid input JSON: {exc}")


def pick_device():
    import torch

    if torch.cuda.is_available():
        return "cuda", torch.float16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def main():
    payload = read_payload()
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        fail("prompt is required")

    output_path = str(payload.get("output_path", "")).strip()
    if not output_path:
        fail("output_path is required")

    model_dir = str(payload.get("model_dir", "")).strip()
    checkpoint = str(payload.get("checkpoint", "")).strip()
    steps = int(payload.get("steps", 28))
    guidance = float(payload.get("guidance", 6.5))
    width = int(payload.get("width", 1024))
    height = int(payload.get("height", 1024))

    if not model_dir and not checkpoint:
        fail("model_dir or checkpoint is required")

    try:
        import torch
        from diffusers import StableDiffusionXLPipeline
    except Exception as exc:
        fail(f"missing deps for image generation (diffusers/torch): {exc}")

    device, dtype = pick_device()

    try:
        if checkpoint and os.path.isfile(checkpoint):
            pipe = StableDiffusionXLPipeline.from_single_file(checkpoint, torch_dtype=dtype)
            model_name = checkpoint
        else:
            if not model_dir or not os.path.isdir(model_dir):
                fail("model_dir not found for SDXL pipeline")
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_dir,
                torch_dtype=dtype,
                use_safetensors=True,
                local_files_only=True,
            )
            model_name = model_dir

        pipe = pipe.to(device)
        image = pipe(
            prompt=prompt,
            num_inference_steps=steps,
            guidance_scale=guidance,
            width=width,
            height=height,
        ).images[0]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        image.save(output_path)

        emit(
            {
                "ok": True,
                "image_path": output_path,
                "meta": {
                    "model": model_name,
                    "device": device,
                    "steps": steps,
                    "guidance": guidance,
                    "width": width,
                    "height": height,
                },
            }
        )
    except Exception as exc:
        fail(f"local image generation failed: {exc}")


if __name__ == "__main__":
    main()
