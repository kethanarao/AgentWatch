import numpy as np


def features(trace):
    return {
        "query_length": len(trace["query"]),
        "retrieval_similarity": max(trace["retrieval_scores"], default=0),
        "tool_call_count": len(trace["tool_calls"]),
        "latency_ms": trace["duration_ms"],
        "answer_length": len(trace["answer"]),
        "quality_score": trace["evaluation"]["quality_score"],
    }


def detect_drift(baseline: list[dict], recent: list[dict]):
    if len(baseline) < 10 or len(recent) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "drift_score": 0,
            "metrics": [],
            "baseline_count": len(baseline),
            "recent_count": len(recent),
            "explanation": "At least 10 independent observations are needed in each window.",
        }
    rows = []
    for name in features(baseline[0]):
        a = np.array([features(t)[name] for t in baseline], dtype=float)
        b = np.array([features(t)[name] for t in recent], dtype=float)
        mean_a, mean_b = float(a.mean()), float(b.mean())
        denominator = max(float(a.std()), abs(mean_a) * 0.1, 0.01)
        z = abs(mean_b - mean_a) / denominator
        percent = (mean_b - mean_a) / max(abs(mean_a), 0.01) * 100
        score = min(100, z * 25)
        rows.append(
            {
                "name": name,
                "baseline": mean_a,
                "recent": mean_b,
                "change_percent": percent,
                "z_score": z,
                "score": score,
                "status": "CRITICAL" if score > 70 else "WARNING" if score > 40 else "NORMAL",
            }
        )
    a = np.array([t["query_embedding"] for t in baseline]).mean(axis=0)
    b = np.array([t["query_embedding"] for t in recent]).mean(axis=0)
    distance = float(1 - np.dot(a, b) / max(float(np.linalg.norm(a) * np.linalg.norm(b)), 1e-10))
    score = min(100, max(0, distance) * 200)
    rows.append(
        {
            "name": "embedding_centroid_distance",
            "baseline": 0,
            "recent": distance,
            "change_percent": None,
            "z_score": None,
            "score": score,
            "status": "CRITICAL" if score > 70 else "WARNING" if score > 40 else "NORMAL",
        }
    )
    drift_score = round(max(r["score"] for r in rows), 1)
    return {
        "status": "CRITICAL" if drift_score > 70 else "WARNING" if drift_score > 40 else "NORMAL",
        "drift_score": drift_score,
        "metrics": rows,
        "baseline_count": len(baseline),
        "recent_count": len(recent),
        "explanation": "Effect-size heuristic: baseline-normalized mean shifts and centroid distance. These are not statistical significance tests.",
        "embedding_source": baseline[0].get("embedding_source", "hashed lexical demo vectors"),
    }
