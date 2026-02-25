#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile


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


def parse_int(value, default=0, min_value=0, max_value=3600):
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def ensure_ffmpeg_in_path():
    if shutil.which("ffmpeg"):
        return
    candidates = [
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            current = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{os.path.dirname(candidate)}:{current}" if current else os.path.dirname(candidate)
            break
    if not shutil.which("ffmpeg"):
        fail("ffmpeg not found in PATH. Install it and verify with: which ffmpeg")


def normalize_audio_for_whisper(input_path):
    fd, output_path = tempfile.mkstemp(prefix="wa_stt_", suffix=".wav")
    os.close(fd)
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        input_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        output_path,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        last_line = err[-1] if err else "unknown ffmpeg error"
        fail(f"ffmpeg failed normalizing audio: {last_line}")
    return output_path


def resolve_model_id(model_dir):
    model_dir = str(model_dir or "").strip()
    if not model_dir:
        return "openai/whisper-large-v3-turbo", False
    if not os.path.isdir(model_dir):
        fail(f"LOCAL_STT_MODEL_DIR not found: {model_dir}")

    has_config = os.path.isfile(os.path.join(model_dir, "config.json"))
    has_weights = any(
        os.path.isfile(os.path.join(model_dir, name))
        for name in (
            "model.safetensors",
            "pytorch_model.bin",
            "pytorch_model.bin.index.json",
            "tf_model.h5",
            "flax_model.msgpack",
        )
    )
    if has_config and has_weights:
        return model_dir, True

    suspicious_bin = os.path.join(model_dir, "whisper-large-v3-turbo.bin")
    if os.path.isfile(suspicious_bin):
        size = os.path.getsize(suspicious_bin)
        if size < 2048:
            try:
                with open(suspicious_bin, "rb") as f:
                    head = f.read(256).decode("utf-8", errors="ignore")
                if "error_code" in head or "Bad Request" in head:
                    fail(
                        "El archivo whisper-large-v3-turbo.bin es un JSON de error, no un modelo Whisper valido."
                    )
            except Exception:
                pass

    fail(
        "Modelo STT local incompleto en LOCAL_STT_MODEL_DIR. Faltan pesos de Transformers "
        "(model.safetensors o pytorch_model.bin)."
    )


def main():
    payload = read_payload()
    audio_path = str(payload.get("audio_path", "")).strip()
    if not audio_path or not os.path.isfile(audio_path):
        fail("audio_path missing or not found")

    model_dir = str(payload.get("model_dir", "")).strip()
    language = str(payload.get("language", "")).strip()
    prompt = str(payload.get("prompt", "")).strip()
    task = str(payload.get("task", "transcribe")).strip() or "transcribe"
    force_cpu = parse_bool(payload.get("force_cpu"), default=True)
    chunk_length_s = parse_int(payload.get("chunk_length_s"), default=30, min_value=0, max_value=120)
    ensure_ffmpeg_in_path()

    try:
        import torch
        from transformers import pipeline
    except Exception as exc:
        fail(f"missing deps for local STT (transformers/torch): {exc}")

    model_id, is_local_model = resolve_model_id(model_dir)
    if force_cpu:
        device = -1
    elif torch.cuda.is_available():
        device = 0
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = -1

    try:
        # `local_files_only` on pipeline/model kwargs can break on newer transformers.
        # With a local absolute path in `model_id`, loading is already local.
        asr = pipeline(
            task="automatic-speech-recognition",
            model=model_id,
            device=device,
            chunk_length_s=chunk_length_s,
        )
        normalized_audio_path = normalize_audio_for_whisper(audio_path)
        try:
            generate_kwargs = {"task": task}
            if language:
                generate_kwargs["language"] = language
            if prompt:
                generate_kwargs["prompt"] = prompt

            try:
                result = asr(normalized_audio_path, generate_kwargs=generate_kwargs)
            except Exception as exc:
                # Some transformers/whisper combos raise this on specific media;
                # retry with minimal kwargs before failing.
                if (
                    isinstance(exc, OverflowError)
                    or "out of range integral type conversion attempted" in str(exc)
                ):
                    try:
                        result = asr(normalized_audio_path)
                    except Exception as exc2:
                        if (
                            isinstance(exc2, OverflowError)
                            or "out of range integral type conversion attempted" in str(exc2)
                        ):
                            # Last resort: call in smaller chunks.
                            result = asr(normalized_audio_path, chunk_length_s=10)
                        else:
                            raise
                else:
                    raise
        finally:
            try:
                os.remove(normalized_audio_path)
            except Exception:
                pass

        text = ""
        if isinstance(result, dict):
            text = str(result.get("text", "")).strip()
        else:
            text = str(result).strip()
        if not text:
            fail("local STT returned empty text")

        emit(
            {
                "ok": True,
                "text": text,
                "meta": {
                    "model": model_id,
                    "device": str(device),
                    "chunk_length_s": chunk_length_s,
                },
            }
        )
    except Exception as exc:
        fail(f"local STT failed: {exc} (type={type(exc).__name__})")


if __name__ == "__main__":
    main()
