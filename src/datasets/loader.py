"""Dataset preparation and canonicalization."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from datasets import load_dataset

from src.schemas.dataset import Choice, Sample
from src.utils.config import load_yaml


def prepare_datasets(config_path: str, output_dir: str, dry_run: bool = False) -> list[Sample]:
    dataset_cfg = load_yaml(config_path)
    samples: list[Sample] = []
    sample_ids: dict[str, list[str]] = {}
    for name, spec in dataset_cfg["datasets"].items():
        if dry_run:
            dataset_samples = _mock_samples(name)
        else:
            raw = _load_hf_split(spec["hf_name"], spec.get("split", "validation"))
            dataset_samples = [_canonicalize(name, row, index) for index, row in enumerate(raw)]
        dataset_samples = [s for s in dataset_samples if s.answer]
        rng = random.Random(dataset_cfg.get("selection", {}).get("seeds", [42])[0])
        rng.shuffle(dataset_samples)
        selected = dataset_samples[: int(spec.get("sample_size", 250))]
        samples.extend(selected)
        sample_ids[name] = [sample.sample_id for sample in selected]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "samples.jsonl").write_text(
        "\n".join(sample.model_dump_json() for sample in samples) + "\n",
        encoding="utf-8",
    )
    lock_file = Path(dataset_cfg.get("selection", {}).get("lock_file", "outputs/processed/sample_ids.json"))
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps(sample_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return samples


def load_prepared_samples(path: str | Path) -> list[Sample]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [Sample.model_validate_json(line) for line in handle if line.strip()]


def _canonicalize(name: str, row: dict[str, Any], index: int) -> Sample:
    if name == "commonsense_qa":
        labels = row["choices"]["label"]
        texts = row["choices"]["text"]
        return Sample(
            sample_id=str(row.get("id", f"commonsense_qa_{index}")),
            dataset=name,
            question=row["question"],
            choices=[Choice(label=str(label), text=str(text)) for label, text in zip(labels, texts)],
            answer=str(row.get("answerKey", "")),
            metadata={"source_index": str(index)},
        )
    options = row.get("options") or row.get("choices") or []
    labels = ["A", "B", "C", "D", "E"]
    if isinstance(options, dict):
        labels = list(options.get("label", labels))
        texts = list(options.get("text", []))
    else:
        texts = list(options)
    answer = row.get("answer") or row.get("label") or row.get("correct_option") or ""
    if isinstance(answer, int):
        answer = labels[answer]
    return Sample(
        sample_id=str(row.get("id", f"{name}_{index}")),
        dataset=name,
        question=str(row.get("question") or row.get("query") or ""),
        context=str(row.get("context") or row.get("passage") or row.get("text") or ""),
        choices=[Choice(label=labels[i], text=str(text)) for i, text in enumerate(texts)],
        answer=str(answer).strip(),
        metadata={"source_index": str(index)},
    )


def _mock_samples(name: str) -> list[Sample]:
    return [
        Sample(
            sample_id=f"{name}_dry_{idx:03d}",
            dataset=name,
            context="Tiền đề: Nếu chuông báo động reo, tòa nhà sẽ được sơ tán. Chuông báo động đang reo.",
            question="Điều gì suy ra từ tiền đề trên?",
            choices=[
                Choice(label="A", text="Tòa nhà được sơ tán."),
                Choice(label="B", text="Chuông báo động im lặng."),
                Choice(label="C", text="Không có kết luận nào suy ra được."),
                Choice(label="D", text="Tòa nhà bị đóng cửa vĩnh viễn."),
            ],
            answer="A",
            metadata={"dry_run": "true"},
        )
        for idx in range(5)
    ]


def _load_hf_split(hf_name: str, split: str):
    try:
        return load_dataset(hf_name, split=split)
    except RuntimeError as exc:
        if "Dataset scripts are no longer supported" not in str(exc):
            raise
        data_files = f"hf://datasets/{hf_name}@refs/convert/parquet/default/{split}/*.parquet"
        return load_dataset("parquet", data_files=data_files, split="train")
