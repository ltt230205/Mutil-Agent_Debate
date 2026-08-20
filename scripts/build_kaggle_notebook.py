"""Build the standalone Kaggle pilot notebook."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


def source(text: str) -> list[str]:
    cleaned = textwrap.dedent(text).strip("\n") + "\n"
    return cleaned.splitlines(keepends=True)


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source(text)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source(text),
    }


cells = [
    markdown(
        r"""
        # Pilot thật trên Kaggle: Multi-Agent Debate

        Notebook này **tự chứa toàn bộ pipeline** và gọi OpenAI API thật. Không cần upload repo hay file phụ.

        Trước khi chạy:

        1. Trong Kaggle Notebook, bật **Internet**.
        2. Vào **Add-ons → Secrets**, tạo secret tên `OPENAI_API_KEY`.
        3. Chọn **Run All**. Notebook mặc định chạy pilot compact, không dùng mock.

        Pilot gồm 10 mẫu LogiQA + 10 mẫu CommonsenseQA, ba seed cho thí nghiệm chính, fair-compute theo 10 model calls và full ablation trên subset 4 mẫu mỗi dataset. Cấu hình có tối đa khoảng 4.964 model calls khái niệm trước schema retry; cache tái sử dụng các transcript trùng nhau nên số request API thực tế thường thấp hơn. Kết quả này phải được báo cáo là **exploratory pilot**, không phải bằng chứng khái quát trên toàn benchmark.
        """
    ),
    code(
        r"""
        # 1) Cài dependency. Kaggle có thể yêu cầu restart session nếu thay đổi phiên bản lớn.
        !pip -q install "openai>=1.40.0" "datasets>=2.19.0" "pydantic>=2.7.0" "pandas>=2.2.0" "numpy>=1.26.0" "scikit-learn>=1.4.0" "scipy>=1.12.0" "matplotlib>=3.8.0" "sentence-transformers>=3.0.0" "tabulate>=0.9.0"
        """
    ),
    code(
        r"""
        # 2) Import và đọc API key an toàn từ Kaggle Secrets.
        import hashlib
        import json
        import os
        import random
        import re
        import shutil
        import time
        from collections import Counter
        from dataclasses import dataclass
        from getpass import getpass
        from itertools import combinations
        from pathlib import Path
        from typing import Any, Literal

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        from datasets import load_dataset
        from openai import OpenAI
        from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
        from sentence_transformers import SentenceTransformer
        from scipy.stats import binomtest
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        try:
            from kaggle_secrets import UserSecretsClient
            api_key = UserSecretsClient().get_secret("OPENAI_API_KEY")
        except Exception:
            api_key = getpass("Nhập OPENAI_API_KEY (ký tự sẽ được ẩn): ")

        if not api_key:
            raise RuntimeError("Chưa cấu hình OPENAI_API_KEY.")
        os.environ["OPENAI_API_KEY"] = api_key
        del api_key
        print("Đã đọc API key an toàn; giá trị key không được in ra.")
        """
    ),
    code(
        r"""
        # 3) Cấu hình pilot thật.
        RUN_MODE = "pilot"  # Đổi thành "smoke" nếu chỉ muốn kiểm tra nhanh trước.

        CFG = {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "max_output_tokens": 700,
            "max_attempts": 3,
            "schema_attempts": 2,
            "backoff_seconds": 2.0,
            "min_delay_seconds": 0.2,
            "datasets": ["logiqa", "commonsense_qa"],
            "hf_names": {"logiqa": "lucasmccabe/logiqa", "commonsense_qa": "tau/commonsense_qa"},
            "splits": {"logiqa": "validation", "commonsense_qa": "validation"},
            "seeds": [42, 123, 2026],
            "sample_size_per_dataset": 10,
            "default_agents": 3,
            "debate_rounds": [1],
            "self_consistency_k": 3,
            "fair_compute_k": 10,
            "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "ablation_sample_size_per_dataset": 4,
            "ablation_seeds": [42],
            "ablation_rounds": [0, 1, 2, 3],
            "full_ablations": True,
            "resume": True,
            "overwrite": False,
            "output_dir": "/kaggle/working/mad_pilot_real",
        }

        if RUN_MODE == "smoke":
            CFG.update({
                "seeds": [42],
                "sample_size_per_dataset": 1,
                "default_agents": 2,
                "debate_rounds": [0],
                "self_consistency_k": 2,
                "fair_compute_k": 2,
                "ablation_sample_size_per_dataset": 1,
                "ablation_seeds": [42],
                "ablation_rounds": [0],
                "full_ablations": False,
                "output_dir": "/kaggle/working/mad_smoke_real",
            })
        elif RUN_MODE != "pilot":
            raise ValueError("RUN_MODE chỉ nhận 'smoke' hoặc 'pilot'.")

        OUT = Path(CFG["output_dir"])
        for folder in ["raw", "processed", "tables", "figures", "logs"]:
            (OUT / folder).mkdir(parents=True, exist_ok=True)

        manifest = {key: value for key, value in CFG.items() if "key" not in key.lower()}
        (OUT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        """
    ),
    code(
        r"""
        # 4) JSON contracts và chuẩn hóa các biến thể định dạng thường gặp.
        EvidenceStatus = Literal["SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN"]
        IssueType = Literal[
            "LOGICAL_ERROR", "MISINTERPRETATION", "MISSING_EVIDENCE", "UNSUPPORTED_ASSUMPTION",
            "ARITHMETIC_ERROR", "HALLUCINATION", "CONFORMITY_ERROR", "JUDGE_ERROR",
            "ANSWER_EXTRACTION_ERROR", "CONTEXT_OVERLOAD",
        ]

        class EvidenceItem(BaseModel):
            claim: str
            source: str = "question"
            status: EvidenceStatus = "UNCERTAIN"

            @field_validator("status", mode="before")
            @classmethod
            def normalize_status(cls, value):
                value = str(value or "UNCERTAIN").strip().upper().replace("-", "_").replace(" ", "_")
                value = {"UNKNOWN": "UNCERTAIN", "NOT_SUPPORTED": "UNSUPPORTED", "PARTIALLY_SUPPORTED": "UNCERTAIN"}.get(value, value)
                return value if value in {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN"} else "UNCERTAIN"

        class SolverOutput(BaseModel):
            sample_id: str
            agent_role: str = "solver"
            round: int = 0
            answer: str
            rationale_summary: list[str] = Field(default_factory=list)
            evidence: list[EvidenceItem] = Field(default_factory=list)
            confidence: float = Field(ge=0.0, le=1.0)
            reasoning_id: str | None = None

            @field_validator("answer", mode="before")
            @classmethod
            def answer_label(cls, value):
                text = str(value or "").strip().upper()
                match = re.search(r"\b([A-E])\b", text)
                if not match:
                    raise ValueError("answer phải là một nhãn từ A đến E")
                return match.group(1)

            @field_validator("rationale_summary", mode="before")
            @classmethod
            def rationale_list(cls, value):
                if value is None: return []
                return [value] if isinstance(value, str) else value

            @field_validator("evidence", mode="before")
            @classmethod
            def evidence_list(cls, value):
                if value is None: return []
                if isinstance(value, str): return [{"claim": value, "source": "đề bài", "status": "UNCERTAIN"}]
                if isinstance(value, dict): return [value]
                if isinstance(value, list):
                    return [{"claim": x, "source": "đề bài", "status": "UNCERTAIN"} if isinstance(x, str) else x for x in value]
                return value

        class Issue(BaseModel):
            type: IssueType
            target_step: int | None = None
            description: str
            severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"

            @model_validator(mode="before")
            @classmethod
            def coerce_issue(cls, value):
                if isinstance(value, str):
                    return {"type": "MISINTERPRETATION", "description": value, "severity": "MEDIUM"}
                if isinstance(value, dict) and "issue" in value:
                    value = dict(value)
                    issue_text = value.pop("issue")
                    value.setdefault("description", str(issue_text))
                    value.setdefault("type", "MISINTERPRETATION")
                    value.setdefault("severity", "MEDIUM")
                if isinstance(value, dict) and "description" not in value and "explanation" in value:
                    value = dict(value); value["description"] = str(value.pop("explanation"))
                return value

            @field_validator("type", mode="before")
            @classmethod
            def issue_type(cls, value):
                value = str(value or "MISINTERPRETATION").strip().upper().replace("-", "_").replace(" ", "_")
                known = {"LOGICAL_ERROR", "MISINTERPRETATION", "MISSING_EVIDENCE", "UNSUPPORTED_ASSUMPTION", "ARITHMETIC_ERROR", "HALLUCINATION", "CONFORMITY_ERROR", "JUDGE_ERROR", "ANSWER_EXTRACTION_ERROR", "CONTEXT_OVERLOAD"}
                aliases = {"LOGIC_ERROR": "LOGICAL_ERROR", "EVIDENCE_SUPPORT": "MISSING_EVIDENCE", "UNSUPPORTED_CLAIM": "UNSUPPORTED_ASSUMPTION", "MISSING_INFORMATION": "MISSING_EVIDENCE", "AMBIGUITY": "MISINTERPRETATION", "FACTUAL_ERROR": "HALLUCINATION", "FORMAT_ERROR": "ANSWER_EXTRACTION_ERROR"}
                value = aliases.get(value, value)
                if value in known: return value
                if "EVIDENCE" in value: return "MISSING_EVIDENCE"
                if "LOGIC" in value or "INCONSIST" in value: return "LOGICAL_ERROR"
                if "ASSUMPT" in value: return "UNSUPPORTED_ASSUMPTION"
                if "ARITH" in value or "MATH" in value: return "ARITHMETIC_ERROR"
                if "CONFORM" in value or "SYCOPH" in value: return "CONFORMITY_ERROR"
                if "CONTEXT" in value: return "CONTEXT_OVERLOAD"
                return "MISINTERPRETATION"

            @field_validator("severity", mode="before")
            @classmethod
            def severity_value(cls, value):
                value = str(value or "MEDIUM").strip().upper()
                return {"CRITICAL": "HIGH", "MODERATE": "MEDIUM", "MINOR": "LOW"}.get(value, value)

            @field_validator("target_step", mode="before")
            @classmethod
            def target_value(cls, value):
                try: return int(value) if value not in (None, "") else None
                except (TypeError, ValueError): return None

        class CritiqueOutput(BaseModel):
            sample_id: str
            agent_role: Literal["critic", "skeptic"]
            round: int
            issues: list[Issue] = Field(default_factory=list)
            recommended_revision: str = ""

            @field_validator("agent_role", mode="before")
            @classmethod
            def role_value(cls, value):
                value = str(value).strip().lower()
                if "skeptic" in value: return "skeptic"
                if "critic" in value: return "critic"
                return value

            @field_validator("issues", mode="before")
            @classmethod
            def issues_list(cls, value):
                if value is None: return []
                return [value] if isinstance(value, (str, dict)) else value

            @field_validator("recommended_revision", mode="before")
            @classmethod
            def revision_text(cls, value):
                return " ".join(map(str, value)) if isinstance(value, list) else str(value or "")

        class EvidenceCheckerOutput(BaseModel):
            sample_id: str
            agent_role: str = "evidence_checker"
            round: int
            evidence: list[EvidenceItem] = Field(default_factory=list)
            recommended_revision: str = ""

            @field_validator("evidence", mode="before")
            @classmethod
            def evidence_list(cls, value):
                if value is None: return []
                if isinstance(value, str): return [{"claim": value, "source": "đề bài", "status": "UNCERTAIN"}]
                if isinstance(value, dict): return [value]
                if isinstance(value, list): return [{"claim": x, "source": "đề bài", "status": "UNCERTAIN"} if isinstance(x, str) else x for x in value]
                return value

            @field_validator("recommended_revision", mode="before")
            @classmethod
            def revision_text(cls, value):
                return " ".join(map(str, value)) if isinstance(value, list) else str(value or "")

        class JudgeOutput(BaseModel):
            sample_id: str
            final_answer: str
            selected_reasoning_id: str | None = None
            decision_reason: str
            confidence: float = Field(ge=0.0, le=1.0)

            @field_validator("final_answer", mode="before")
            @classmethod
            def answer_label(cls, value):
                text = str(value or "").strip().upper()
                match = re.search(r"\b([A-E])\b", text)
                if not match:
                    raise ValueError("final_answer phải là một nhãn từ A đến E")
                return match.group(1)

            @field_validator("selected_reasoning_id", mode="before")
            @classmethod
            def reasoning_id_text(cls, value):
                return None if value in (None, "") else str(value)

            @field_validator("decision_reason", mode="before")
            @classmethod
            def reason_text(cls, value):
                return " ".join(map(str, value)) if isinstance(value, list) else str(value or "")
        """
    ),
    code(
        r"""
        # 5) Prompt tiếng Việt, cache JSONL, API retry và schema retry.
        PROMPTS = {
            "solver": '''Bạn là Solver cẩn trọng cho bài toán NLP reasoning. Chỉ trả về một JSON object hợp lệ. Trả lời câu hỏi trắc nghiệm bằng structured rationale ngắn, evidence và confidence từ 0 đến 1. Các field bắt buộc: sample_id, agent_role, round, answer, rationale_summary, evidence, confidence. Giá trị chuỗi viết bằng tiếng Việt có dấu, trừ nhãn đáp án và enum.''',
            "critic": '''Bạn là Critic. Kiểm tra lỗi logic, hiểu sai, giả định thiếu căn cứ và bằng chứng bị bỏ sót. Không mặc định Solver sai. Chỉ trả về JSON với sample_id, agent_role, round, issues, recommended_revision. issue type chỉ được là LOGICAL_ERROR, MISINTERPRETATION, MISSING_EVIDENCE, UNSUPPORTED_ASSUMPTION, ARITHMETIC_ERROR, HALLUCINATION, CONFORMITY_ERROR, JUDGE_ERROR, ANSWER_EXTRACTION_ERROR hoặc CONTEXT_OVERLOAD.''',
            "skeptic": '''Bạn là Skeptic. Tìm phản ví dụ, cách hiểu khác và trường hợp biên; không lặp lại Critic. Chỉ trả về JSON với sample_id, agent_role, round, issues, recommended_revision. Dùng cùng taxonomy issue type của Critic.''',
            "evidence_checker": '''Bạn là Evidence Checker. Đối chiếu claim với đề bài và gắn SUPPORTED, UNSUPPORTED, CONTRADICTED hoặc UNCERTAIN. Chỉ trả về JSON với sample_id, agent_role, round, evidence, recommended_revision.''',
            "judge": '''Bạn là Blind Judge. Không chỉ đếm phiếu, không ưu tiên câu dài hay vị trí đầu. Đánh giá reasoning và evidence; nếu decision_protocol là evidence_aware_judge, ưu tiên coverage và phạt claim unsupported. Chỉ trả về JSON với sample_id, final_answer, selected_reasoning_id, decision_reason, confidence.''',
        }

        @dataclass
        class Usage:
            input_tokens: int = 0
            output_tokens: int = 0

        @dataclass
        class Response:
            content: str
            usage: Usage
            latency: float
            cached: bool = False

        CACHE_PATH = OUT / "raw" / "response_cache.jsonl"
        CACHE = {}
        if CACHE_PATH.exists():
            for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    CACHE[item["cache_key"]] = item

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        last_call_time = 0.0

        def cache_key(payload):
            return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

        def parse_json_object(text):
            text = text.strip()
            try: return json.loads(text)
            except json.JSONDecodeError:
                start, end = text.find("{"), text.rfind("}")
                if start >= 0 and end > start: return json.loads(text[start:end + 1])
                raise

        def complete_json(system_prompt, user_prompt, role, seed):
            global last_call_time
            request = {"model": CFG["model"], "system": system_prompt, "user": user_prompt, "role": role, "temperature": CFG["temperature"], "max_tokens": CFG["max_output_tokens"], "seed": seed}
            key = cache_key(request)
            if key in CACHE:
                item = CACHE[key]
                return Response(item["content"], Usage(**item["usage"]), item["latency"], True)
            for attempt in range(1, CFG["max_attempts"] + 1):
                try:
                    elapsed = time.time() - last_call_time
                    if elapsed < CFG["min_delay_seconds"]: time.sleep(CFG["min_delay_seconds"] - elapsed)
                    start = time.time()
                    result = client.chat.completions.create(
                        model=CFG["model"], temperature=CFG["temperature"], max_tokens=CFG["max_output_tokens"], seed=seed,
                        response_format={"type": "json_object"},
                        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    )
                    last_call_time = time.time()
                    usage = result.usage
                    response = Response(
                        result.choices[0].message.content or "{}",
                        Usage(getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)),
                        time.time() - start,
                    )
                    item = {"cache_key": key, "content": response.content, "usage": response.usage.__dict__, "latency": response.latency, "model": CFG["model"], "role": role, "seed": seed}
                    CACHE[key] = item
                    with CACHE_PATH.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(item, ensure_ascii=False) + "\n"); handle.flush()
                    return response
                except Exception as exc:
                    if attempt == CFG["max_attempts"]: raise
                    print(f"API retry {attempt}/{CFG['max_attempts']} ({type(exc).__name__})", flush=True)
                    time.sleep(CFG["backoff_seconds"] * attempt)

        def sample_prompt(sample):
            choices = "\n".join(f"{x['label']}. {x['text']}" for x in sample["choices"])
            return f"Ngữ cảnh:\n{sample.get('context','')}\n\nCâu hỏi:\n{sample['question']}\n\nLựa chọn:\n{choices}"

        SCHEMAS = {"solver": SolverOutput, "critic": CritiqueOutput, "skeptic": CritiqueOutput, "evidence_checker": EvidenceCheckerOutput, "judge": JudgeOutput}

        def run_agent(role, sample, round_id, context, seed):
            total_in = total_out = 0; total_latency = 0.0; last_error = None
            for schema_attempt in range(1, CFG["schema_attempts"] + 1):
                state = dict(context or {})
                if last_error:
                    state["format_correction"] = "Phản hồi trước sai JSON contract. Hãy trả về đúng field, kiểu dữ liệu và enum bắt buộc."
                    state["schema_retry"] = schema_attempt
                user_prompt = f"sample_id={sample['sample_id']}\ndataset={sample['dataset']}\nround={round_id}\n\n{sample_prompt(sample)}"
                if state: user_prompt += "\n\nTrạng thái debate trước đó ở dạng JSON:\n" + json.dumps(state, ensure_ascii=False)
                response = complete_json(PROMPTS[role], user_prompt, role, seed)
                total_in += response.usage.input_tokens; total_out += response.usage.output_tokens; total_latency += response.latency
                try:
                    payload = parse_json_object(response.content)
                    payload["sample_id"] = sample["sample_id"]
                    if role in {"solver", "critic", "skeptic", "evidence_checker"}:
                        payload["agent_role"] = role
                        payload["round"] = round_id
                    obj = SCHEMAS[role].model_validate(payload).model_dump()
                    return obj, Usage(total_in, total_out), total_latency
                except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                    last_error = exc
            raise ValueError(f"Invalid {role} output after schema retry: {last_error}")
        """
    ),
    code(
        r"""
        # 6) Tải, chuẩn hóa và khóa sample IDs. Bước này không gọi OpenAI API.
        SAMPLES_PATH = OUT / "processed" / "samples.jsonl"
        IDS_PATH = OUT / "processed" / "sample_ids.json"

        def load_hf(name, split):
            try: return load_dataset(name, split=split)
            except RuntimeError as exc:
                if "Dataset scripts are no longer supported" not in str(exc): raise
                data_files = f"hf://datasets/{name}@refs/convert/parquet/default/{split}/*.parquet"
                return load_dataset("parquet", data_files=data_files, split="train")

        def canonicalize(dataset, row, index):
            if dataset == "commonsense_qa":
                return {"sample_id": str(row.get("id", f"commonsense_qa_{index}")), "dataset": dataset, "context": "", "question": row["question"], "choices": [{"label": str(a), "text": str(b)} for a, b in zip(row["choices"]["label"], row["choices"]["text"])], "answer": str(row.get("answerKey", "")), "source_index": index}
            options = row.get("options") or row.get("choices") or []
            labels = ["A", "B", "C", "D", "E"]
            if isinstance(options, dict): labels, texts = list(options.get("label", labels)), list(options.get("text", []))
            else: texts = list(options)
            answer = next((row[key] for key in ["answer", "label", "correct_option"] if key in row and row[key] is not None), "")
            if isinstance(answer, int): answer = labels[answer] if 0 <= answer < len(labels) else ""
            return {"sample_id": str(row.get("id", f"{dataset}_{index}")), "dataset": dataset, "context": str(row.get("context") or row.get("passage") or row.get("text") or ""), "question": str(row.get("question") or row.get("query") or ""), "choices": [{"label": str(labels[i]), "text": str(text)} for i, text in enumerate(texts)], "answer": str(answer).strip(), "source_index": index}

        if CFG["resume"] and SAMPLES_PATH.exists():
            samples = [json.loads(x) for x in SAMPLES_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
        else:
            samples = []; locked_ids = {}
            for dataset in CFG["datasets"]:
                raw = load_hf(CFG["hf_names"][dataset], CFG["splits"][dataset])
                candidates = [canonicalize(dataset, row, i) for i, row in enumerate(raw)]
                candidates = [x for x in candidates if x["answer"] and x["question"] and x["choices"]]
                random.Random(42).shuffle(candidates)
                selected = candidates[:CFG["sample_size_per_dataset"]]
                samples.extend(selected); locked_ids[dataset] = [x["sample_id"] for x in selected]
            SAMPLES_PATH.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in samples) + "\n", encoding="utf-8")
            IDS_PATH.write_text(json.dumps(locked_ids, ensure_ascii=False, indent=2), encoding="utf-8")

        counts = Counter(x["dataset"] for x in samples)
        assert all(counts[d] == CFG["sample_size_per_dataset"] for d in CFG["datasets"]), counts
        print("Đã khóa subset:", dict(counts), "| Tổng:", len(samples))
        """
    ),
    code(
        r"""
        # 7) Protocol: baseline, debate, decision và record.
        def norm_answer(value):
            value = str(value or "").strip().upper()
            return value[:1]

        def majority_vote(outputs):
            answers = [norm_answer(x.get("answer")) for x in outputs if norm_answer(x.get("answer"))]
            counts = Counter(answers)
            if not counts: return "", 0.0
            answer = sorted(counts, key=lambda x: (-counts[x], x))[0]
            return answer, counts[answer] / len(answers)

        def make_record(sample, method, seed, answer, confidence, usage, latency, solvers, raw):
            answer = norm_answer(answer); gold = norm_answer(sample["answer"])
            return {"sample_id": sample["sample_id"], "dataset": sample["dataset"], "method": method, "seed": seed, "answer": answer, "gold": gold, "correct": answer == gold, "confidence": float(confidence), "model_calls": len(raw), "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "total_tokens": usage.input_tokens + usage.output_tokens, "latency_seconds": latency, "traces": [" ".join(x.get("rationale_summary", [])) for x in solvers], "raw": raw}

        def run_single(sample, seed, method):
            out, usage, latency = run_agent("solver", sample, 0, {"method": method}, seed)
            out["reasoning_id"] = f"{method}_{sample['sample_id']}"
            record = make_record(sample, method, seed, out["answer"], out["confidence"], usage, latency, [out], [out])
            record["confidence_type"] = "self_reported_solver"
            return record

        def run_independent_vote(sample, seed, method, count):
            outputs = []; raw = []; usage = Usage(); latency = 0.0
            for index in range(count):
                key = "path" if method.startswith("self_consistency") else "agent_index"
                out, used, elapsed = run_agent("solver", sample, 0, {"method": method, key: index}, seed)
                out["reasoning_id"] = f"{method}_{index}_{sample['sample_id']}"
                outputs.append(out); raw.append(out); usage.input_tokens += used.input_tokens; usage.output_tokens += used.output_tokens; latency += elapsed
            answer, confidence = majority_vote(outputs)
            record = make_record(sample, method, seed, answer, confidence, usage, latency, outputs, raw)
            record["confidence_type"] = "consensus_score"
            return record

        def debate_one(sample, seed, method, rounds, n_agents, specialized=True, decision="judge", remove=None, record_method=None):
            solvers = []; raw = []; usage = Usage(); latency = 0.0
            for index in range(n_agents):
                out, used, elapsed = run_agent("solver", sample, 0, {"method": method, "agent_index": index}, seed)
                out["reasoning_id"] = f"solver_{index}_round_0"
                solvers.append(out); raw.append(out); usage.input_tokens += used.input_tokens; usage.output_tokens += used.output_tokens; latency += elapsed
            initial = [dict(x) for x in solvers]
            initial_answer, initial_consensus = majority_vote(initial)
            initial_disagreement = len({norm_answer(x.get("answer")) for x in initial}) > 1
            state = {"initial": initial, "disagreement_detected": initial_disagreement}
            for round_id in range(1, rounds + 1):
                critiques = []
                for role, flag in [("critic", "no_critic"), ("skeptic", "no_skeptic"), ("evidence_checker", "no_evidence_checker")]:
                    if specialized and remove != flag:
                        obj, used, elapsed = run_agent(role, sample, round_id, state, seed)
                        critiques.append(obj); raw.append(obj); usage.input_tokens += used.input_tokens; usage.output_tokens += used.output_tokens; latency += elapsed
                revised = []
                for index, previous in enumerate(solvers):
                    revision_state = {"previous_answer": previous, "critiques": critiques, "agent_index": index, "method": method}
                    if not specialized: revision_state["peer_answers"] = solvers
                    out, used, elapsed = run_agent("solver", sample, round_id, revision_state, seed)
                    out["reasoning_id"] = f"solver_{index}_round_{round_id}"
                    revised.append(out); raw.append(out); usage.input_tokens += used.input_tokens; usage.output_tokens += used.output_tokens; latency += elapsed
                solvers = revised; state = {"previous": solvers, "critiques": critiques}
            if decision == "majority" or remove == "no_judge":
                answer, confidence = majority_vote(solvers)
            else:
                blind = list(solvers); random.Random(seed).shuffle(blind)
                judged, used, elapsed = run_agent("judge", sample, rounds, {"answers": blind, "decision_protocol": decision}, seed)
                answer, confidence = judged["final_answer"], judged["confidence"]
                raw.append(judged); usage.input_tokens += used.input_tokens; usage.output_tokens += used.output_tokens; latency += elapsed
            output_method = record_method or f"{method}_r{rounds}_{decision}"
            record = make_record(sample, output_method, seed, answer, confidence, usage, latency, solvers, raw)
            record["confidence_type"] = "consensus_score" if decision == "majority" or remove == "no_judge" else "self_reported_judge"
            record["initial_answer"] = initial_answer
            record["initial_correct"] = initial_answer == norm_answer(sample["answer"])
            record["initial_consensus"] = initial_consensus
            record["initial_disagreement"] = initial_disagreement
            record["raw"].append({"initial_outputs": initial})
            return record

        def checkpoint_keys(path):
            if not path.exists(): return set()
            keys = set()
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip(): continue
                row = json.loads(line); keys.add((int(row["seed"]), row["sample_id"], row["method"]))
            return keys

        def append_record(path, row):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n"); handle.flush()
        """
    ),
    code(
        r"""
        # 8) Baseline thật + fair-compute call-matched.
        path = OUT / "raw" / "baselines.jsonl"
        if CFG["overwrite"] and path.exists(): path.unlink()
        completed = checkpoint_keys(path) if CFG["resume"] else set()
        total_records = len(samples) * len(CFG["seeds"]) * 6

        for seed in CFG["seeds"]:
            for sample in samples:
                jobs = [
                    ("single_direct", lambda: run_single(sample, seed, "single_direct")),
                    ("single_cot", lambda: run_single(sample, seed, "single_cot")),
                    ("self_consistency", lambda: run_independent_vote(sample, seed, "self_consistency", CFG["self_consistency_k"])),
                    ("multi_agent_majority", lambda: run_independent_vote(sample, seed, "multi_agent_majority", CFG["default_agents"])),
                    (f"self_consistency_k{CFG['fair_compute_k']}_call_matched", lambda: run_independent_vote(sample, seed, f"self_consistency_k{CFG['fair_compute_k']}_call_matched", CFG["fair_compute_k"])),
                    (f"multi_agent_majority_n{CFG['fair_compute_k']}_call_matched", lambda: run_independent_vote(sample, seed, f"multi_agent_majority_n{CFG['fair_compute_k']}_call_matched", CFG["fair_compute_k"])),
                ]
                for method, runner in jobs:
                    key = (seed, sample["sample_id"], method)
                    if key in completed: continue
                    print(f"[baseline {len(completed)+1}/{total_records}] seed={seed} sample={sample['sample_id']} method={method}", flush=True)
                    row = runner(); append_record(path, row); completed.add(key)
        print("Baseline hoàn tất:", len(completed), "records")
        """
    ),
    code(
        r"""
        # 9) Multi-Agent Debate thật.
        path = OUT / "raw" / "debate.jsonl"
        if CFG["overwrite"] and path.exists(): path.unlink()
        completed = checkpoint_keys(path) if CFG["resume"] else set()
        total_records = len(samples) * len(CFG["seeds"]) * len(CFG["debate_rounds"]) * 3

        for seed in CFG["seeds"]:
            for sample in samples:
                for rounds in CFG["debate_rounds"]:
                    jobs = [
                        (f"homogeneous_debate_r{rounds}_majority", lambda: debate_one(sample, seed, "homogeneous_debate", rounds, CFG["default_agents"], False, "majority")),
                        (f"specialized_debate_r{rounds}_majority", lambda: debate_one(sample, seed, "specialized_debate", rounds, CFG["default_agents"], True, "majority")),
                        (f"specialized_debate_r{rounds}_judge", lambda: debate_one(sample, seed, "specialized_debate", rounds, CFG["default_agents"], True, "judge")),
                    ]
                    for method, runner in jobs:
                        key = (seed, sample["sample_id"], method)
                        if key in completed: continue
                        print(f"[debate {len(completed)+1}/{total_records}] seed={seed} sample={sample['sample_id']} method={method}", flush=True)
                        row = runner(); append_record(path, row); completed.add(key)
        print("Debate hoàn tất:", len(completed), "records")
        """
    ),
    code(
        r"""
        # 10) Ablation thật trên subset cân bằng.
        ablation_samples = []
        for dataset in CFG["datasets"]:
            ablation_samples.extend([x for x in samples if x["dataset"] == dataset][:CFG["ablation_sample_size_per_dataset"]])

        path = OUT / "raw" / "ablations.jsonl"
        if CFG["overwrite"] and path.exists(): path.unlink()
        completed = checkpoint_keys(path) if CFG["resume"] else set()
        configs_per_sample = 1 if not CFG["full_ablations"] else len(CFG["ablation_rounds"]) + 5 + 3 + 3
        total_records = len(ablation_samples) * len(CFG["ablation_seeds"]) * configs_per_sample

        for seed in CFG["ablation_seeds"]:
            for sample in ablation_samples:
                jobs = []
                if not CFG["full_ablations"]:
                    jobs.append(("ablation_rounds_r0_judge", lambda: debate_one(sample, seed, "ablation_rounds", 0, CFG["default_agents"], True, "judge")))
                else:
                    for rounds in CFG["ablation_rounds"]:
                        jobs.append((f"ablation_rounds_r{rounds}_judge", lambda rounds=rounds: debate_one(sample, seed, "ablation_rounds", rounds, CFG["default_agents"], True, "judge")))
                    for remove in [None, "no_critic", "no_skeptic", "no_evidence_checker", "no_judge"]:
                        name = "full" if remove is None else remove
                        record_method = f"ablation_roles_{name}_r2_judge"
                        jobs.append((record_method, lambda remove=remove, record_method=record_method: debate_one(sample, seed, "ablation_roles", 2, CFG["default_agents"], True, "judge", remove, record_method)))
                    for decision in ["majority", "judge", "evidence_aware_judge"]:
                        record_method = f"ablation_decision_r2_{decision}"
                        jobs.append((record_method, lambda decision=decision, record_method=record_method: debate_one(sample, seed, "ablation_decision", 2, CFG["default_agents"], True, decision, None, record_method)))
                    for n_agents in [2, 3, 5]:
                        record_method = f"ablation_agents_{n_agents}_r2_judge"
                        jobs.append((record_method, lambda n_agents=n_agents, record_method=record_method: debate_one(sample, seed, "ablation_agents", 2, n_agents, True, "judge", None, record_method)))
                for method, runner in jobs:
                    key = (seed, sample["sample_id"], method)
                    if key in completed: continue
                    print(f"[ablation {len(completed)+1}/{total_records}] seed={seed} sample={sample['sample_id']} method={method}", flush=True)
                    row = runner(); append_record(path, row); completed.add(key)
        print("Ablation hoàn tất:", len(completed), "records | subset:", len(ablation_samples))
        """
    ),
    code(
        r"""
        # 11) Evaluation, statistical tests, behavioral/error analysis và figures. Không gọi API.
        def read_jsonl(path):
            return [] if not path.exists() else [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

        records = []
        for filename in ["baselines.jsonl", "debate.jsonl", "ablations.jsonl"]:
            records.extend(read_jsonl(OUT / "raw" / filename))
        if not records: raise RuntimeError("Không có raw prediction để đánh giá.")
        df = pd.DataFrame(records)
        df.to_csv(OUT / "processed" / "predictions.csv", index=False)

        def bootstrap_ci(values, n=1000, seed=42):
            values = np.asarray(values, dtype=float)
            if not len(values): return 0.0, 0.0
            rng = np.random.default_rng(seed)
            means = [rng.choice(values, size=len(values), replace=True).mean() for _ in range(n)]
            return float(np.quantile(means, .025)), float(np.quantile(means, .975))

        def brier(group):
            return float(np.mean((group["confidence"].astype(float).clip(0, 1) - group["correct"].astype(float)) ** 2))

        def ece(group, bins=10):
            conf = group["confidence"].astype(float).clip(0, 1).to_numpy(); correct = group["correct"].astype(float).to_numpy(); score = 0.0
            for low, high in zip(np.linspace(0, 1, bins + 1)[:-1], np.linspace(0, 1, bins + 1)[1:]):
                mask = (conf >= low) & (conf < high if high < 1 else conf <= high)
                if mask.any(): score += mask.mean() * abs(conf[mask].mean() - correct[mask].mean())
            return float(score)

        def initial_outputs(record):
            for item in reversed(record.get("raw", [])):
                if isinstance(item, dict) and isinstance(item.get("initial_outputs"), list):
                    return item["initial_outputs"]
            return [x for x in record.get("raw", []) if isinstance(x, dict) and x.get("agent_role") == "solver" and int(x.get("round", 0)) == 0]

        def has_answer_disagreement(record):
            answers = {norm_answer(x.get("answer")) for x in initial_outputs(record) if norm_answer(x.get("answer"))}
            return len(answers) > 1

        df["answer_disagreement"] = [has_answer_disagreement(record) for record in records]
        df.to_csv(OUT / "processed" / "predictions.csv", index=False)

        rows = []
        per_seed = df.groupby(["dataset", "method", "seed"], as_index=False).agg(
            accuracy=("correct", "mean"), answer_disagreement_rate=("answer_disagreement", "mean"),
            mean_model_calls=("model_calls", "mean"), mean_tokens=("total_tokens", "mean"),
            mean_latency=("latency_seconds", "mean"), n=("correct", "size"),
        )
        per_seed.to_csv(OUT / "tables" / "per_seed_results.csv", index=False)
        for (dataset, method), group in df.groupby(["dataset", "method"]):
            sample_scores = group.groupby("sample_id")["correct"].mean().to_numpy()
            low, high = bootstrap_ci(sample_scores)
            seed_acc = group.groupby("seed")["correct"].mean()
            mean_tokens = float(group["total_tokens"].mean())
            rows.append({
                "dataset": dataset, "method": method, "n": len(group),
                "unique_samples": group["sample_id"].nunique(), "seeds": group["seed"].nunique(),
                "accuracy": float(group["correct"].mean()), "accuracy_seed_mean": float(seed_acc.mean()),
                "accuracy_seed_std": float(seed_acc.std(ddof=1)) if len(seed_acc) > 1 else 0.0,
                "accuracy_ci_low": low, "accuracy_ci_high": high,
                "answer_disagreement_rate": float(group["answer_disagreement"].mean()),
                "mean_model_calls": float(group["model_calls"].mean()),
                "mean_input_tokens": float(group["input_tokens"].mean()),
                "mean_output_tokens": float(group["output_tokens"].mean()),
                "mean_total_tokens": mean_tokens,
                "accuracy_per_1000_tokens": float(group["correct"].mean()) / max(mean_tokens, 1) * 1000,
                "mean_latency_seconds": float(group["latency_seconds"].mean()),
                "median_latency_seconds": float(group["latency_seconds"].median()),
                "p95_latency_seconds": float(group["latency_seconds"].quantile(.95)),
                "confidence_type": ",".join(sorted(group["confidence_type"].dropna().unique())),
                "brier_score": brier(group), "ece": ece(group),
            })
        summary = pd.DataFrame(rows).sort_values(["dataset", "method"])
        summary.to_csv(OUT / "tables" / "main_results.csv", index=False)
        summary[summary["method"].str.startswith("ablation")].to_csv(OUT / "tables" / "ablation_results.csv", index=False)

        trace_texts = sorted({text for record in records for text in record.get("traces", []) if isinstance(text, str) and text.strip()})
        embedding_backend = CFG["embedding_model"]
        try:
            embedding_model = SentenceTransformer(CFG["embedding_model"])
            vectors = embedding_model.encode(trace_texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
        except Exception as exc:
            print(f"Cảnh báo: embedding model không tải được ({type(exc).__name__}); dùng TF-IDF fallback và ghi rõ trong metadata.")
            embedding_backend = "tfidf_fallback"
            vectors = TfidfVectorizer().fit_transform(trace_texts).toarray() if trace_texts else np.empty((0, 0))
            norms = np.linalg.norm(vectors, axis=1, keepdims=True) if len(vectors) else np.empty((0, 1))
            if len(vectors): vectors = vectors / np.maximum(norms, 1e-12)
        vector_map = {text: vectors[index] for index, text in enumerate(trace_texts)}
        (OUT / "processed" / "embedding_metadata.json").write_text(json.dumps({"backend": embedding_backend, "n_unique_traces": len(trace_texts)}, ensure_ascii=False, indent=2), encoding="utf-8")

        def semantic_diversity(traces):
            traces = [x for x in traces if isinstance(x, str) and x.strip()]
            if len(traces) < 2: return 0.0
            matrix = np.vstack([vector_map[x] for x in traces])
            similarities = matrix @ matrix.T
            pair_values = [similarities[i, j] for i, j in combinations(range(len(traces)), 2)]
            return float(1 - np.mean(pair_values)) if pair_values else 0.0

        diversity_rows = [{
            "sample_id": r["sample_id"], "dataset": r["dataset"], "method": r["method"], "seed": r["seed"],
            "semantic_diversity": semantic_diversity(r.get("traces", [])), "correct": bool(r["correct"]),
        } for r in records]
        diversity_df = pd.DataFrame(diversity_rows)
        diversity_df.to_csv(OUT / "tables" / "reasoning_diversity.csv", index=False)
        diversity_correlations = []
        for (dataset, method), group in diversity_df.groupby(["dataset", "method"]):
            corr = group["semantic_diversity"].corr(group["correct"].astype(float)) if group["semantic_diversity"].nunique() > 1 and group["correct"].nunique() > 1 else np.nan
            diversity_correlations.append({"dataset": dataset, "method": method, "diversity_accuracy_correlation": corr, "n": len(group)})
        pd.DataFrame(diversity_correlations).to_csv(OUT / "tables" / "diversity_accuracy_correlation.csv", index=False)

        transitions = []
        debate_df = df[df["initial_correct"].notna()].copy()
        debate_df["initial_correct"] = debate_df["initial_correct"].astype(bool)
        for (dataset, method), group in debate_df.groupby(["dataset", "method"]):
            wrong = group[~group["initial_correct"]]; right = group[group["initial_correct"]]
            transitions.append({"dataset": dataset, "method": method, "n_pairs": len(group), "n_initially_wrong": len(wrong), "n_initially_correct": len(right), "correction_rate": float(wrong["correct"].mean()) if len(wrong) else np.nan, "degradation_rate": float((~right["correct"]).mean()) if len(right) else np.nan})
        pd.DataFrame(transitions).to_csv(OUT / "tables" / "correction_degradation.csv", index=False)

        fair_rows = []
        target = "specialized_debate_r1_judge"
        comparators = [f"self_consistency_k{CFG['fair_compute_k']}_call_matched", f"multi_agent_majority_n{CFG['fair_compute_k']}_call_matched"]
        for dataset in CFG["datasets"]:
            target_row = summary[(summary["dataset"] == dataset) & (summary["method"] == target)]
            if target_row.empty: continue
            target_row = target_row.iloc[0]
            for comparator in comparators:
                base_row = summary[(summary["dataset"] == dataset) & (summary["method"] == comparator)]
                if base_row.empty: continue
                base_row = base_row.iloc[0]
                gain_points = (target_row["accuracy"] - base_row["accuracy"]) * 100
                fair_rows.append({"dataset": dataset, "control": "model_call_matched", "debate_method": target, "comparator": comparator, "debate_calls": target_row["mean_model_calls"], "comparator_calls": base_row["mean_model_calls"], "debate_tokens": target_row["mean_total_tokens"], "comparator_tokens": base_row["mean_total_tokens"], "debate_accuracy": target_row["accuracy"], "comparator_accuracy": base_row["accuracy"], "accuracy_difference": target_row["accuracy"] - base_row["accuracy"], "extra_tokens_per_1_accuracy_point": (target_row["mean_total_tokens"] - base_row["mean_total_tokens"]) / gain_points if gain_points > 0 else np.nan})
            candidates = summary[(summary["dataset"] == dataset) & (summary["method"].isin(["self_consistency", "multi_agent_majority"] + comparators))].copy()
            if len(candidates):
                candidates["token_gap"] = (candidates["mean_total_tokens"] - target_row["mean_total_tokens"]).abs()
                nearest = candidates.sort_values("token_gap").iloc[0]
                fair_rows.append({"dataset": dataset, "control": "post_hoc_nearest_token_budget", "debate_method": target, "comparator": nearest["method"], "debate_calls": target_row["mean_model_calls"], "comparator_calls": nearest["mean_model_calls"], "debate_tokens": target_row["mean_total_tokens"], "comparator_tokens": nearest["mean_total_tokens"], "debate_accuracy": target_row["accuracy"], "comparator_accuracy": nearest["accuracy"], "accuracy_difference": target_row["accuracy"] - nearest["accuracy"], "extra_tokens_per_1_accuracy_point": np.nan})
        pd.DataFrame(fair_rows).to_csv(OUT / "tables" / "fair_compute_comparison.csv", index=False)

        comparisons = [(target, f"multi_agent_majority_n{CFG['fair_compute_k']}_call_matched"), ("specialized_debate_r1_majority", "multi_agent_majority"), (target, "homogeneous_debate_r1_majority")]
        mcnemar_rows = []
        for left, right in comparisons:
            for dataset in CFG["datasets"]:
                for seed in sorted(df["seed"].unique()):
                    a = df[(df["dataset"] == dataset) & (df["method"] == left) & (df["seed"] == seed)][["sample_id", "correct"]]
                    b = df[(df["dataset"] == dataset) & (df["method"] == right) & (df["seed"] == seed)][["sample_id", "correct"]]
                    paired = a.merge(b, on="sample_id", suffixes=("_left", "_right"))
                    if paired.empty: continue
                    b01 = int(((~paired["correct_left"]) & paired["correct_right"]).sum())
                    b10 = int((paired["correct_left"] & (~paired["correct_right"])).sum())
                    ties = len(paired) - b01 - b10
                    pvalue = float(binomtest(b01, b01 + b10, .5).pvalue) if b01 + b10 else 1.0
                    mcnemar_rows.append({"dataset": dataset, "seed": int(seed), "left": left, "right": right, "n_pairs": len(paired), "left_loss_right_win": b01, "left_win_right_loss": b10, "ties": ties, "p_value": pvalue})
        pd.DataFrame(mcnemar_rows).to_csv(OUT / "tables" / "mcnemar_win_loss_tie.csv", index=False)

        sample_lookup = {(sample["dataset"], sample["sample_id"]): sample for sample in samples}
        behavioral_cases = []
        for record in records:
            if "initial_correct" not in record: continue
            if not record["initial_correct"] and record["correct"]: transition = "SUCCESSFUL_CORRECTION"
            elif not record["initial_correct"] and not record["correct"]: transition = "RESISTANT_ERROR"
            elif record["initial_correct"] and not record["correct"]: transition = "HARMFUL_REVISION"
            else: transition = "STABLE_CORRECT"
            initial = initial_outputs(record); initial_answers = [norm_answer(x.get("answer")) for x in initial]
            counts = Counter(initial_answers); gold = norm_answer(record["gold"])
            minority_correct = bool(counts.get(gold, 0) and counts[gold] < max(counts.values())) if counts else False
            item = sample_lookup.get((record["dataset"], record["sample_id"]), {})
            behavioral_cases.append({"sample_id": record["sample_id"], "dataset": record["dataset"], "seed": record["seed"], "method": record["method"], "transition": transition, "productive_disagreement": bool(record.get("initial_disagreement")) and not bool(record["initial_correct"]) and bool(record["correct"]), "minority_correct_case": minority_correct, "judge_selected_correct_minority": minority_correct and bool(record["correct"]), "question": item.get("question", ""), "choices": item.get("choices", []), "gold": gold, "answer_before": record.get("initial_answer", ""), "initial_answers": initial_answers, "answer_after": record["answer"], "raw_after": record.get("raw", [])})
        with (OUT / "processed" / "behavioral_cases.jsonl").open("w", encoding="utf-8") as handle:
            for row in behavioral_cases: handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        behavior_df = pd.DataFrame([{key: value for key, value in row.items() if key not in {"choices", "raw_after"}} for row in behavioral_cases])
        behavior_df.groupby(["dataset", "method", "transition"], as_index=False).size().to_csv(OUT / "tables" / "behavioral_summary.csv", index=False)

        taxonomy = ["LOGICAL_ERROR", "MISINTERPRETATION", "MISSING_EVIDENCE", "UNSUPPORTED_ASSUMPTION", "ARITHMETIC_ERROR", "HALLUCINATION", "CONFORMITY_ERROR", "JUDGE_ERROR", "ANSWER_EXTRACTION_ERROR", "CONTEXT_OVERLOAD"]
        errors = Counter()
        for record in records:
            for item in record.get("raw", []):
                if isinstance(item, dict):
                    for issue in item.get("issues", []) if isinstance(item.get("issues", []), list) else []:
                        if isinstance(issue, dict) and issue.get("type") in taxonomy: errors[(record["method"], issue["type"])] += 1
        error_rows = []
        for method in sorted(df["method"].unique()):
            total = sum(errors[(method, error_type)] for error_type in taxonomy)
            for error_type in taxonomy:
                count = errors[(method, error_type)]
                error_rows.append({"method": method, "error_type": error_type, "agent_reported_count": count, "agent_reported_rate": count / total if total else np.nan})
        pd.DataFrame(error_rows).to_csv(OUT / "tables" / "error_taxonomy_agent_reported.csv", index=False)
        manual_rows = [{"sample_id": r["sample_id"], "dataset": r["dataset"], "seed": r["seed"], "method": r["method"], "answer": r["answer"], "gold": r["gold"], "error_type": "", "annotation_status": "NEEDS_MANUAL_REVIEW"} for r in records if not r["correct"]]
        pd.DataFrame(manual_rows).to_csv(OUT / "processed" / "error_cases_for_manual_annotation.csv", index=False)

        for dataset, group in summary.groupby("dataset"):
            main = group[~group["method"].str.startswith("ablation")].sort_values("accuracy", ascending=False)
            for metric, ylabel in [("accuracy", "Accuracy"), ("mean_total_tokens", "Mean total tokens")]:
                plt.figure(figsize=(12, 5)); plt.bar(main["method"], main[metric]); plt.xticks(rotation=45, ha="right", fontsize=8); plt.ylabel(ylabel); plt.title(f"{ylabel} - {dataset}"); plt.tight_layout(); plt.savefig(OUT / "figures" / f"{metric}_{dataset}.png", dpi=160); plt.close()
            plt.figure(figsize=(7, 6))
            selected = df[(df["dataset"] == dataset) & (df["method"].isin(["single_cot", "multi_agent_majority", target]))]
            for method, values in selected.groupby("method"):
                values = values.copy(); values["bin"] = pd.cut(values["confidence"].clip(0, 1), bins=np.linspace(0, 1, 6), include_lowest=True)
                calibration = values.groupby("bin", observed=False).agg(confidence=("confidence", "mean"), accuracy=("correct", "mean")).dropna()
                plt.plot(calibration["confidence"], calibration["accuracy"], marker="o", label=method)
            plt.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1); plt.xlabel("Mean confidence"); plt.ylabel("Empirical accuracy"); plt.title(f"Reliability diagram - {dataset}"); plt.legend(fontsize=8); plt.tight_layout(); plt.savefig(OUT / "figures" / f"reliability_{dataset}.png", dpi=160); plt.close()

        (OUT / "tables" / "main_results.md").write_text(summary.to_markdown(index=False), encoding="utf-8")
        print("Evaluation hoàn tất:", len(df), "prediction records | embedding:", embedding_backend)
        display(summary[summary["method"].isin(["single_direct", "single_cot", "multi_agent_majority", f"multi_agent_majority_n{CFG['fair_compute_k']}_call_matched", "specialized_debate_r1_majority", "specialized_debate_r1_judge"])])
        """
    ),
    code(
        r"""
        # 12) Kiểm tra tính toàn vẹn và đóng gói toàn bộ output để tải về.
        raw_counts = {}
        for filename in ["baselines.jsonl", "debate.jsonl", "ablations.jsonl", "response_cache.jsonl"]:
            path = OUT / "raw" / filename
            raw_counts[filename] = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        assert raw_counts["baselines.jsonl"] > 0 and raw_counts["debate.jsonl"] > 0 and raw_counts["ablations.jsonl"] > 0
        secret_pattern = re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
        assert not any(secret_pattern.search(path.read_text(encoding="utf-8", errors="ignore")) for path in OUT.rglob("*") if path.is_file())

        archive_base = Path("/kaggle/working") / f"{OUT.name}_results"
        archive = shutil.make_archive(str(archive_base), "zip", root_dir=OUT)
        print("Raw counts:", raw_counts)
        print("Đã tạo:", archive)
        print("Trong Kaggle, mở panel Output/Files để tải file ZIP về.")
        """
    ),
    markdown(
        r"""
        ## Ghi chú trung thực nghiên cứu

        - Chỉ dùng kết quả khi cả ba file `baselines.jsonl`, `debate.jsonl`, `ablations.jsonl` đã hoàn tất và evaluation chạy thành công.
        - Pilot có 20 mẫu chính và 8 mẫu ablation nên statistical power thấp; khoảng tin cậy và p-value phải được trình bày cùng Accuracy.
        - Không gọi pilot là đánh giá đầy đủ trên benchmark, không đồng nhất consensus với confidence, và không kết luận diversity cao đồng nghĩa reasoning đúng.
        - Fair-compute trong notebook này match theo số model calls; token usage thực tế vẫn phải báo cáo riêng.
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kaggle": {"accelerator": "none", "dataSources": [], "dockerImageVersionId": None, "isGpuEnabled": False, "isInternetEnabled": True, "language": "python", "sourceType": "notebook"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

output = Path(__file__).resolve().parents[1] / "KAGGLE_PILOT_PIPELINE.ipynb"
output.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(output)
