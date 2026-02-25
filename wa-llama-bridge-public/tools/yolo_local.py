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


def parse_float(value, default=0.25, min_value=0.0, max_value=1.0):
    try:
        parsed = float(value)
    except Exception:
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def parse_int(value, default=30, min_value=1, max_value=300):
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def resolve_label(names, cls_id):
    if isinstance(names, dict):
        return str(names.get(cls_id, cls_id))
    if isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
        return str(names[cls_id])
    return str(cls_id)


def main():
    warnings.filterwarnings("ignore")
    payload = read_payload()

    image_path = str(payload.get("image_path", "")).strip()
    if not image_path or not os.path.isfile(image_path):
        fail("image_path missing or not found")

    model_path = str(payload.get("model_path", "")).strip()
    if not model_path or not os.path.isfile(model_path):
        fail("model_path missing or not found")

    conf = parse_float(payload.get("conf"), default=0.25, min_value=0.0, max_value=1.0)
    iou = parse_float(payload.get("iou"), default=0.45, min_value=0.0, max_value=1.0)
    max_det = parse_int(payload.get("max_det"), default=30, min_value=1, max_value=300)

    try:
        from ultralytics import YOLO
    except Exception as exc:
        fail(f"missing deps for local YOLO (ultralytics): {exc}")

    try:
        model = YOLO(model_path)
        results = model.predict(
            source=image_path,
            conf=conf,
            iou=iou,
            max_det=max_det,
            verbose=False,
        )
    except Exception as exc:
        fail(f"local YOLO failed during predict: {exc}")

    detections = []
    summary = {}
    try:
        if not results:
            results = []

        first = results[0] if len(results) > 0 else None
        if first is not None and getattr(first, "boxes", None) is not None:
            boxes = first.boxes
            names = getattr(first, "names", None) or getattr(model, "names", None)

            cls_values = boxes.cls.tolist() if getattr(boxes, "cls", None) is not None else []
            conf_values = boxes.conf.tolist() if getattr(boxes, "conf", None) is not None else []
            xyxy_values = boxes.xyxy.tolist() if getattr(boxes, "xyxy", None) is not None else []

            for idx, cls_raw in enumerate(cls_values):
                cls_id = int(cls_raw)
                label = resolve_label(names, cls_id)
                confidence = float(conf_values[idx]) if idx < len(conf_values) else 0.0
                bbox = xyxy_values[idx] if idx < len(xyxy_values) else None

                detections.append(
                    {
                        "class_id": cls_id,
                        "label": label,
                        "confidence": confidence,
                        "bbox_xyxy": bbox,
                    }
                )
                summary[label] = int(summary.get(label, 0) + 1)
    except Exception as exc:
        fail(f"local YOLO failed parsing detections: {exc}")

    emit(
        {
            "ok": True,
            "detections": detections,
            "summary": summary,
            "meta": {
                "model_path": model_path,
                "count": len(detections),
                "conf": conf,
                "iou": iou,
                "max_det": max_det,
            },
        }
    )


if __name__ == "__main__":
    main()
