"""Combine quarter-turn predictions in the original image coordinates."""
import math


def restore_box(box, rotation, width, height):
    x1, y1, x2, y2 = box
    if rotation == 90:
        box = [width - y2, x1, width - y1, x2]
    elif rotation == 180:
        box = [width - x2, height - y2, width - x1, height - y1]
    elif rotation == 270:
        box = [y1, height - x2, y2, height - x1]
    return [max(0.0, min(limit, value))
            for value, limit in zip(box, (width, height, width, height))]


def box_iou(left, right):
    intersection = (max(0, min(left[2], right[2]) - max(left[0], right[0]))
                    * max(0, min(left[3], right[3]) - max(left[1], right[1])))
    union = ((left[2] - left[0]) * (left[3] - left[1])
             + (right[2] - right[0]) * (right[3] - right[1]) - intersection)
    return intersection / union if union > 0 else 0.0


def fuse_detections(views, min_views=2):
    """Vote across views, keeping at most one vote per class per view.

    Matching is class independent: a car/truck disagreement must represent one
    physical object, rather than two detections. Confidence is the best actual
    score for the winning class, not a fabricated probability from vote counts.
    """
    groups = []
    for detection in sorted(views, key=lambda d: d["confidence"], reverse=True):
        best = max(groups, key=lambda g: box_iou(g[0]["box"], detection["box"]), default=None)
        if best is not None and box_iou(best[0]["box"], detection["box"]) >= 0.5:
            best.append(detection)
        else:
            groups.append([detection])

    fused = []
    for group in groups:
        votes = {}
        for detection in group:
            per_view = votes.setdefault(detection["class_name"], {})
            angle = detection["rotation"]
            if angle not in per_view or detection["confidence"] > per_view[angle]["confidence"]:
                per_view[angle] = detection
        ranked = sorted(votes, key=lambda name: sum(d["confidence"] for d in votes[name].values()), reverse=True)
        winner = ranked[0]
        class_votes = {name: sum(d["confidence"] for d in items.values()) for name, items in votes.items()}
        tied = len(ranked) > 1 and math.isclose(class_votes[winner], class_votes[ranked[1]], abs_tol=1e-6)
        evidence = list(votes[winner].values())
        total = sum(d["confidence"] for d in evidence)
        box = [sum(d["box"][i] * d["confidence"] for d in evidence) / total for i in range(4)]
        fused.append({"box": box, "confidence": max(d["confidence"] for d in evidence),
                      "class_name": "ambiguous" if tied else winner,
                      "support_views": len(evidence), "class_votes": class_votes,
                      "consistent": not tied and len(evidence) >= min_views})
    return fused


def select_cars(detections, confidence, image_size, edge_margin=0):
    """Select cars with evidence in enough views and an explicit border policy."""
    accepted, rejected = [], []
    width, height = image_size
    for detection in detections:
        reason = None
        if detection["class_name"] not in ("car", "ambiguous"):
            continue
        if not detection.get("consistent", True):
            reason = "ambiguous_class" if detection["class_name"] == "ambiguous" else "insufficient_views"
        elif detection["confidence"] < confidence:
            reason = "below_confidence"
        elif edge_margin > 0:
            x1, y1, x2, y2 = detection["box"]
            if x1 <= edge_margin or y1 <= edge_margin or x2 >= width - edge_margin or y2 >= height - edge_margin:
                reason = "truncated_at_border"
        if reason:
            rejected.append({**detection, "reason": reason})
        else:
            accepted.append(detection)
    return accepted, rejected
