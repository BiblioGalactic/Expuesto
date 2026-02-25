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


def flatten_ocr_result(result):
    lines = []
    if result is None:
        return lines

    def pick_rec_texts(container):
        if container is None:
            return []
        rec = None
        if isinstance(container, dict):
            rec = container.get("rec_texts")
        else:
            try:
                rec = container["rec_texts"]  # dict-like object
            except Exception:
                rec = getattr(container, "rec_texts", None)

        out = []
        if isinstance(rec, (list, tuple)):
            for text in rec:
                s = str(text).strip()
                if s:
                    out.append(s)
        return out

    # PaddleOCR 3.x predict() output.
    if isinstance(result, list):
        for item in result:
            lines.extend(pick_rec_texts(item))
        if lines:
            return lines

    # Single dict/object with rec_texts.
    lines.extend(pick_rec_texts(result))
    if lines:
        return lines

    # PaddleOCR <=2.x usual output: [[box], (text, score)].
    if isinstance(result, list):
        for item in result:
            if not item:
                continue
            if isinstance(item, list):
                for line in item:
                    if (
                        isinstance(line, list)
                        and len(line) >= 2
                        and isinstance(line[1], (list, tuple))
                        and len(line[1]) >= 1
                    ):
                        text = str(line[1][0]).strip()
                        if text:
                            lines.append(text)
    return lines


def is_paddleocr_vl_dir(model_dir):
    cfg_path = os.path.join(model_dir, "config.json")
    if not os.path.isfile(cfg_path):
        return False
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return False

    model_type = str(cfg.get("model_type", "")).strip().lower()
    architectures = [str(x) for x in (cfg.get("architectures") or [])]
    return model_type == "paddleocr_vl" or any("PaddleOCRVL" in x for x in architectures)


def main():
    payload = read_payload()
    image_path = str(payload.get("image_path", "")).strip()
    if not image_path or not os.path.isfile(image_path):
        fail("image_path missing or not found")

    model_dir = str(payload.get("model_dir", "")).strip()
    det_model_name = str(payload.get("det_model_name", "")).strip()
    rec_model_name = str(payload.get("rec_model_name", "")).strip()
    cls_model_name = str(payload.get("cls_model_name", "")).strip()
    det_model_dir = str(payload.get("det_model_dir", "")).strip()
    rec_model_dir = str(payload.get("rec_model_dir", "")).strip()
    cls_model_dir = str(payload.get("cls_model_dir", "")).strip()
    use_textline_orientation = parse_bool(payload.get("use_textline_orientation"), default=False)
    lang = str(payload.get("lang", "es")).strip() or "es"

    try:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        import inspect
        from paddleocr import PaddleOCR
    except Exception as exc:
        fail(f"missing deps for local OCR (paddleocr/paddle): {exc}")

    if model_dir and os.path.isdir(model_dir):
        if is_paddleocr_vl_dir(model_dir) and not (det_model_dir and rec_model_dir):
            fail(
                "LOCAL_OCR_MODEL_DIR apunta a PaddleOCR-VL (transformers). "
                "Define LOCAL_OCR_DET_MODEL_DIR y LOCAL_OCR_REC_MODEL_DIR para OCR clasico."
            )
        os.environ.setdefault("PADDLEOCR_HOME", model_dir)

    for key, candidate in (
        ("det_model_dir", det_model_dir),
        ("rec_model_dir", rec_model_dir),
        ("cls_model_dir", cls_model_dir),
    ):
        if candidate and not os.path.isdir(candidate):
            fail(f"{key} no encontrado: {candidate}")

    try:
        ctor_params = {}
        try:
            sig = inspect.signature(PaddleOCR.__init__)
            if "lang" in sig.parameters:
                ctor_params["lang"] = lang
            if "show_log" in sig.parameters:
                ctor_params["show_log"] = False
            if "use_doc_orientation_classify" in sig.parameters:
                ctor_params["use_doc_orientation_classify"] = False
            if "use_doc_unwarping" in sig.parameters:
                ctor_params["use_doc_unwarping"] = False
            if "text_detection_model_name" in sig.parameters and det_model_name:
                ctor_params["text_detection_model_name"] = det_model_name
            if "text_recognition_model_name" in sig.parameters and rec_model_name:
                ctor_params["text_recognition_model_name"] = rec_model_name
            if "textline_orientation_model_name" in sig.parameters and cls_model_name:
                ctor_params["textline_orientation_model_name"] = cls_model_name
            if "text_detection_model_dir" in sig.parameters and det_model_dir:
                ctor_params["text_detection_model_dir"] = det_model_dir
            if "text_recognition_model_dir" in sig.parameters and rec_model_dir:
                ctor_params["text_recognition_model_dir"] = rec_model_dir
            if "textline_orientation_model_dir" in sig.parameters and cls_model_dir:
                ctor_params["textline_orientation_model_dir"] = cls_model_dir
            if "use_textline_orientation" in sig.parameters:
                ctor_params["use_textline_orientation"] = bool(use_textline_orientation and cls_model_dir)

            if "det_model_dir" in sig.parameters and det_model_dir:
                ctor_params["det_model_dir"] = det_model_dir
            if "rec_model_dir" in sig.parameters and rec_model_dir:
                ctor_params["rec_model_dir"] = rec_model_dir
            if "cls_model_dir" in sig.parameters and cls_model_dir:
                ctor_params["cls_model_dir"] = cls_model_dir
            if "use_angle_cls" in sig.parameters:
                ctor_params["use_angle_cls"] = bool(use_textline_orientation and cls_model_dir)
        except Exception:
            ctor_params = {"lang": lang}

        ocr = PaddleOCR(**ctor_params)
        use_cls_in_ocr = bool(use_textline_orientation and cls_model_dir)
        if hasattr(ocr, "predict"):
            try:
                result = ocr.predict(image_path, use_textline_orientation=use_cls_in_ocr)
            except TypeError:
                result = ocr.predict(image_path)
        else:
            try:
                result = ocr.ocr(image_path, cls=use_cls_in_ocr)
            except TypeError:
                result = ocr.ocr(image_path)
        lines = flatten_ocr_result(result)
        text = "\n".join(lines).strip()
        if not text:
            fail("OCR returned empty text")

        emit(
            {
                "ok": True,
                "text": text,
                "lines": lines,
                "meta": {
                    "lang": lang,
                    "line_count": len(lines),
                },
            }
        )
    except Exception as exc:
        fail(f"local OCR failed: {exc}")


if __name__ == "__main__":
    main()
