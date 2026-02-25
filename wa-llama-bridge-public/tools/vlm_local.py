#!/usr/bin/env python3
import json
import os
import sys
import warnings


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


def parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def parse_int(value, default=128, min_value=1, max_value=4096):
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def pick_device_and_dtype(torch, force_cpu):
    if force_cpu:
        return "cpu", torch.float32
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def resolve_model_class(transformers_module):
    for class_name in (
        "Qwen2_5_VLForConditionalGeneration",
        "Qwen2VLForConditionalGeneration",
        "AutoModelForVision2Seq",
    ):
        if hasattr(transformers_module, class_name):
            return getattr(transformers_module, class_name), class_name
    return None, ""


def move_to_device(batch, device):
    out = {}
    for key, value in batch.items():
        if hasattr(value, "to"):
            out[key] = value.to(device)
        else:
            out[key] = value
    return out


def decode_generated(processor, generated_ids, input_ids):
    if generated_ids is None:
        return ""

    try:
        if input_ids is not None:
            prompt_len = int(input_ids.shape[1])
            trimmed = generated_ids[:, prompt_len:]
            text = processor.batch_decode(
                trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
        else:
            text = processor.batch_decode(
                generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
    except Exception:
        text = ""
    return str(text).strip()


def main():
    warnings.filterwarnings("ignore")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

    payload = read_payload()
    image_path = str(payload.get("image_path", "")).strip()
    if not image_path or not os.path.isfile(image_path):
        fail("image_path missing or not found")

    model_dir = str(payload.get("model_dir", "")).strip()
    if not model_dir or not os.path.isdir(model_dir):
        fail("model_dir missing or not found")

    prompt = str(payload.get("prompt", "")).strip() or (
        "Describe brevemente la imagen en español: escena, personas/objetos, acción, "
        "contexto y tono."
    )
    max_new_tokens = parse_int(payload.get("max_new_tokens"), default=220, min_value=8, max_value=2048)
    force_cpu = parse_bool(payload.get("force_cpu"), default=False)

    try:
        from PIL import Image
        import torch
        import transformers
        from transformers import AutoProcessor
        from transformers.utils import logging as hf_logging
    except Exception as exc:
        fail(f"missing deps for local VLM (transformers/torch/pillow): {exc}")

    hf_logging.set_verbosity_error()

    model_cls, model_class_name = resolve_model_class(transformers)
    if model_cls is None:
        fail("this transformers build does not expose a compatible VLM model class")

    device, torch_dtype = pick_device_and_dtype(torch, force_cpu)
    model_kwargs = {
        "local_files_only": True,
        "trust_remote_code": True,
    }
    if torch_dtype is not None:
        model_kwargs["torch_dtype"] = torch_dtype

    try:
        processor = AutoProcessor.from_pretrained(
            model_dir, trust_remote_code=True, local_files_only=True
        )
    except Exception as exc:
        fail(f"failed loading VLM processor: {exc}")

    try:
        try:
            model = model_cls.from_pretrained(model_dir, **model_kwargs)
        except Exception:
            # retry without dtype hint for compatibility in some setups
            model_kwargs.pop("torch_dtype", None)
            model = model_cls.from_pretrained(model_dir, **model_kwargs)
        model = model.to(device)
        model.eval()
    except Exception as exc:
        fail(f"failed loading VLM model: {exc}")

    try:
        with Image.open(image_path) as img:
            image = img.convert("RGB")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        try:
            text_input = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            text_input = prompt

        image_inputs = [image]
        video_inputs = None
        try:
            from qwen_vl_utils import process_vision_info

            image_inputs, video_inputs = process_vision_info(messages)
        except Exception:
            pass

        try:
            if video_inputs is not None:
                inputs = processor(
                    text=[text_input],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                )
            else:
                inputs = processor(
                    text=[text_input],
                    images=image_inputs,
                    padding=True,
                    return_tensors="pt",
                )
        except Exception as exc:
            fail(f"failed preparing VLM inputs: {exc}")

        inputs = move_to_device(inputs, device)
        input_ids = inputs.get("input_ids")

        try:
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        except Exception as exc:
            fail(f"failed running VLM generation: {exc}")

        output_text = decode_generated(processor, generated_ids, input_ids)
        if not output_text:
            fail("local VLM returned empty text")

        emit(
            {
                "ok": True,
                "text": output_text,
                "meta": {
                    "model_dir": model_dir,
                    "device": device,
                    "dtype": str(torch_dtype),
                    "model_class": model_class_name,
                    "max_new_tokens": max_new_tokens,
                },
            }
        )
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"local VLM failed: {exc}")


if __name__ == "__main__":
    main()
