# Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning

Mini-research project về việc so sánh Multi-Agent Debate (MAD) với Majority Voting, Self-Consistency và các baseline reasoning khác. Repo này ưu tiên tính tái lập: mọi model response được lưu JSONL, cấu hình nằm trong YAML/env, và chế độ `dry-run` cho phép kiểm thử pipeline mà không gọi API.

Prompt cho các agent được viết bằng tiếng Việt có dấu. Các giá trị chuỗi trong output JSON cũng được yêu cầu viết bằng tiếng Việt có dấu; tên field JSON vẫn giữ tiếng Anh để ổn định schema và đúng quy ước code.

## Kế Hoạch Theo Giai Đoạn

1. Research Design: khóa RQ/Hypotheses, chọn LogiQA và CommonsenseQA, lập baseline/ablation/fair-compute.
2. System Design: thiết kế Solver, Critic, Skeptic, Evidence Checker, Revision, Judge; JSON contracts; logging/caching.
3. Implementation: viết loader, agent client, baseline, debate protocol, evaluator, scripts CLI, unit tests.
4. Pilot Experiment: chạy 20 mẫu ở `dry-run` hoặc API thật với `runtime.pilot_samples`.
5. Main Experiment: chạy 2 dataset, 200-300 mẫu/dataset, 3 seed, baseline và MAD.
6. Ablation: rounds, role specialization, remove-one-role, decision protocol, number of agents.
7. Evaluation: accuracy, diversity, correction/degradation, token, latency, calibration, CI, McNemar.
8. Behavioral/Error Analysis: phân loại successful correction, resistant error, harmful revision, minority-correct, taxonomy lỗi.
9. Report Writing: báo cáo tiếng Việt, IEEE references, bảng/hình sinh từ output thật.

## Giả Định Và Thông Tin Còn Thiếu

- API key chỉ đọc từ `.env`; không ghi vào code/log/report.
- `configs/experiment.yaml` mặc định `runtime.dry_run: true` để tránh phát sinh chi phí.
- Main experiment thật chưa nên chạy tự động nếu chưa có ngân sách token/chi phí được xác nhận.
- Dataset được tải qua HuggingFace; cần kiểm tra license/dataset card trước khi phân phối lại dữ liệu đầy đủ.
- Báo cáo không điền số liệu thật cho đến khi `outputs/raw/*.jsonl` đến từ model thật.

## Cấu Trúc Repository

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── configs/
├── prompts/
├── src/
│   ├── agents/
│   ├── protocols/
│   ├── datasets/
│   ├── evaluation/
│   ├── analysis/
│   ├── schemas/
│   └── utils/
├── scripts/
├── tests/
├── outputs/
└── report/
```

## Kiến Trúc Hệ Thống

```text
Input Question
  -> Independent Solver Responses
  -> Disagreement Detection / trace logging
  -> Critic
  -> Skeptic
  -> Evidence Checker
  -> Solver Revision
  -> repeat for rounds 0,1,2,3
  -> Majority Vote or Blind Judge
  -> Final Answer
  -> Metrics, Raw JSONL, Tables, Behavioral/Error Analysis
```

Judge nhận các reasoning đã xáo trộn bằng `shuffle_for_blind_judge` để giảm position/identity bias.

## RQ, Hypotheses, Experiments, Metrics

| RQ | Hypothesis | Experiment | Metrics |
|---|---|---|---|
| RQ1 Diversity | H1 | B3/B4 vs homogeneous/specialized MAD | Answer disagreement, semantic diversity |
| RQ2 Effectiveness | H2 | Fair-compute: Self-Consistency vs MAD | Accuracy, tokens, latency, accuracy/1k tokens |
| RQ3 Rounds | H4 | Rounds 0/1/2/3 | Accuracy, correction, degradation, cost, latency |
| RQ4 Roles | H3 | Homogeneous vs specialized, remove-one-role | Accuracy, diversity, error taxonomy |
| RQ5 Failure Modes | H5 | Behavioral/error analysis | Successful correction, resistant error, harmful revision |

## Cài Đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Tạo `.env` từ mẫu:

```bash
copy .env.example .env
```

Điền:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
OPENAI_PROVIDER=openai
```

## Chạy Dry-Run

Dry-run không gọi model thật và chỉ dùng mock samples/mock responses.

```bash
python scripts/prepare_data.py --config configs/experiment.yaml --dry-run
python scripts/run_baselines.py --config configs/experiment.yaml --dry-run
python scripts/run_debate.py --config configs/experiment.yaml --dry-run
python scripts/run_ablations.py --config configs/experiment.yaml --dry-run
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

## Chạy Thí Nghiệm Thật

1. Đặt `runtime.dry_run: false` trong `configs/experiment.yaml`.
2. Đặt `runtime.overwrite: true` nếu muốn ghi lại output cũ.
3. Kiểm tra `sample_size_per_dataset`, `self_consistency_k`, `default_agents`, `debate_rounds`.
4. Chạy:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml
python scripts/run_baselines.py --config configs/experiment.yaml
python scripts/run_debate.py --config configs/experiment.yaml
python scripts/run_ablations.py --config configs/experiment.yaml
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

## Output

- `outputs/raw/response_cache.jsonl`: cache model responses.
- `outputs/raw/baselines.jsonl`: raw baseline records.
- `outputs/raw/debate.jsonl`: raw debate records.
- `outputs/raw/ablations.jsonl`: raw ablation records.
- `outputs/processed/samples.jsonl`: locked canonical samples.
- `outputs/processed/sample_ids.json`: sample IDs for reproducibility.
- `outputs/processed/predictions.csv`: flattened predictions.
- `outputs/tables/main_results.csv`: bảng tổng hợp chính.
- `outputs/tables/reasoning_diversity.csv`: diversity per prediction.
- `outputs/tables/error_taxonomy_counts.csv`: thống kê lỗi từ critique outputs.
- `report/report.md`: báo cáo tiếng Việt.

## Kiểm Thử

```bash
pytest
```

## Ghi Chú Trung Thực Nghiên Cứu

Repo không tự tạo số liệu giả. Dry-run chỉ kiểm tra luồng xử lý và được ghi nhãn bằng mock outputs. Các kết luận trong báo cáo chỉ nên hoàn thiện sau khi bảng được sinh từ raw output thật.
