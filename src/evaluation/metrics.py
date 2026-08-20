"""Evaluation metrics for debate experiments."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def accuracy(df: pd.DataFrame) -> float:
    return float(df["correct"].mean()) if len(df) else 0.0


def semantic_diversity(traces: list[str]) -> float:
    traces = [trace for trace in traces if trace.strip()]
    if len(traces) < 2:
        return 0.0
    matrix = TfidfVectorizer().fit_transform(traces)
    sims = cosine_similarity(matrix)
    pairs = [sims[i, j] for i, j in combinations(range(len(traces)), 2)]
    return float(1.0 - np.mean(pairs)) if pairs else 0.0


def answer_disagreement(answers: Iterable[str]) -> bool:
    normalized = {answer.strip().upper()[:1] for answer in answers if answer}
    return len(normalized) >= 2


def brier_score(df: pd.DataFrame) -> float:
    if len(df) == 0:
        return 0.0
    y = df["correct"].astype(float).to_numpy()
    p = df["confidence"].astype(float).clip(0, 1).to_numpy()
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(df: pd.DataFrame, bins: int = 10) -> float:
    if len(df) == 0:
        return 0.0
    confidences = df["confidence"].astype(float).clip(0, 1).to_numpy()
    correct = df["correct"].astype(float).to_numpy()
    ece = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (confidences >= low) & (confidences < high if high < 1 else confidences <= high)
        if mask.any():
            ece += mask.mean() * abs(confidences[mask].mean() - correct[mask].mean())
    return float(ece)


def bootstrap_ci(values: list[float], samples: int = 1000, confidence: float = 0.95, seed: int = 42) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(samples)]
    alpha = 1 - confidence
    return (float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2)))


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]) -> float:
    b01 = sum((not a) and b for a, b in zip(a_correct, b_correct))
    b10 = sum(a and (not b) for a, b in zip(a_correct, b_correct))
    total = b01 + b10
    if total == 0:
        return 1.0
    return float(binomtest(min(b01, b10), total, 0.5).pvalue)


def summarize_predictions(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dataset, method), group in df.groupby(["dataset", "method"]):
        acc_values = group["correct"].astype(float).tolist()
        ci_low, ci_high = bootstrap_ci(acc_values)
        rows.append(
            {
                "dataset": dataset,
                "method": method,
                "n": len(group),
                "accuracy": accuracy(group),
                "accuracy_ci_low": ci_low,
                "accuracy_ci_high": ci_high,
                "mean_total_tokens": float(group["total_tokens"].mean()),
                "accuracy_per_1000_tokens": accuracy(group) / max(float(group["total_tokens"].mean()), 1.0) * 1000,
                "mean_latency_seconds": float(group["latency_seconds"].mean()),
                "median_latency_seconds": float(group["latency_seconds"].median()),
                "p95_latency_seconds": float(group["latency_seconds"].quantile(0.95)),
                "brier_score": brier_score(group),
                "ece": expected_calibration_error(group),
            }
        )
    return pd.DataFrame(rows)


def correction_degradation(before: pd.DataFrame, after: pd.DataFrame) -> dict[str, float]:
    merged = before[["sample_id", "correct"]].merge(after[["sample_id", "correct"]], on="sample_id", suffixes=("_before", "_after"))
    wrong_before = merged[~merged["correct_before"]]
    right_before = merged[merged["correct_before"]]
    correction = float((wrong_before["correct_after"]).mean()) if len(wrong_before) else 0.0
    degradation = float((~right_before["correct_after"]).mean()) if len(right_before) else 0.0
    return {"correction_rate": correction, "degradation_rate": degradation}


def error_type_counts(records: list[dict]) -> pd.DataFrame:
    counter: Counter[tuple[str, str]] = Counter()
    for record in records:
        method = record.get("method", "unknown")
        for item in record.get("raw", []):
            for issue in item.get("issues", []) if isinstance(item, dict) else []:
                counter[(method, issue.get("type", "UNCATEGORIZED"))] += 1
    rows = [{"method": method, "error_type": error_type, "count": count} for (method, error_type), count in counter.items()]
    df = pd.DataFrame(rows)
    if len(df):
        totals = df.groupby("method")["count"].transform("sum")
        df["rate"] = df["count"] / totals
    return df
