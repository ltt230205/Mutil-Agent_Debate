"""Behavioral analysis utilities."""

from __future__ import annotations

import pandas as pd


def classify_transitions(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    merged = before.merge(after, on=["sample_id", "dataset", "gold"], suffixes=("_before", "_after"))
    labels = []
    for row in merged.itertuples():
        if (not row.correct_before) and row.correct_after:
            labels.append("SUCCESSFUL_CORRECTION")
        elif (not row.correct_before) and (not row.correct_after):
            labels.append("RESISTANT_ERROR")
        elif row.correct_before and (not row.correct_after):
            labels.append("HARMFUL_REVISION")
        elif row.answer_before != row.answer_after:
            labels.append("PRODUCTIVE_OR_NEUTRAL_DISAGREEMENT")
        else:
            labels.append("STABLE_CORRECT")
    merged["behavior"] = labels
    return merged


ERROR_TAXONOMY = [
    "LOGICAL_ERROR",
    "MISINTERPRETATION",
    "MISSING_EVIDENCE",
    "UNSUPPORTED_ASSUMPTION",
    "ARITHMETIC_ERROR",
    "HALLUCINATION",
    "CONFORMITY_ERROR",
    "JUDGE_ERROR",
    "ANSWER_EXTRACTION_ERROR",
    "CONTEXT_OVERLOAD",
]
