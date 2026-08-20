# GUIDE: Chạy Thí Nghiệm Thật Bằng OpenAI API

Tài liệu này hướng dẫn cách chạy project **Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning** bằng **API key thật**, gọi tới **model thật**, và tạo output thật để phục vụ báo cáo nghiên cứu. Workflow chính trong tài liệu này **không dùng mock** và **không dùng dry-run**.

## 1. Trước Khi Chạy

Project này có nhiều lời gọi model vì phải chạy baseline, Multi-Agent Debate và ablation. Nếu chạy cấu hình đầy đủ trong `configs/experiment.yaml`, chi phí API có thể tăng nhanh.

Repo có hai cấu hình chạy thật:

- `configs/real_smoke.yaml`: chạy thật rất nhỏ để kiểm tra API, model, schema và evaluator.
- `configs/experiment.yaml`: chạy thí nghiệm chính với 2 dataset, 3 seed, 5 agent, nhiều vòng debate và nhiều ablation.

Config chính hiện đã đặt:

```yaml
runtime:
  dry_run: false
```

Nghĩa là các script chạy với `configs/experiment.yaml` sẽ gọi API thật.

## 2. Pipeline Tổng Thể

Pipeline đầy đủ:

```text
prepare_data
  -> run_baselines
  -> run_debate
  -> run_ablations
  -> evaluate
  -> generate_report_tables
```

| Bước | Script | Gọi OpenAI API? | Ý nghĩa |
|---|---|---:|---|
| 1 | `prepare_data.py` | Không | Tải dataset, chuẩn hóa sample, khóa sample IDs |
| 2 | `run_baselines.py` | Có | Chạy các baseline đối chứng |
| 3 | `run_debate.py` | Có | Chạy Multi-Agent Debate |
| 4 | `run_ablations.py` | Có | Chạy ablation study |
| 5 | `evaluate.py` | Không | Tính metrics từ raw output |
| 6 | `generate_report_tables.py` | Không | Sinh bảng Markdown cho báo cáo |

Các bước tốn tiền API là `run_baselines.py`, `run_debate.py` và `run_ablations.py`.

## 3. Cài Đặt

Tạo môi trường:

```bash
python -m venv .venv
```

Kích hoạt trên Windows PowerShell:

```bash
.venv\Scripts\activate
```

Kích hoạt trên macOS/Linux:

```bash
source .venv/bin/activate
```

Cài thư viện:

```bash
pip install -r requirements.txt
```

Kiểm tra phiên bản Python:

```bash
python --version
```

Yêu cầu: Python 3.10 trở lên.

## 4. Cấu Hình API Key Thật

Tạo `.env`:

```bash
copy .env.example .env
```

Trên macOS/Linux:

```bash
cp .env.example .env
```

Điền API key thật:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_PROVIDER=openai
```

Lưu ý:

- Không commit `.env`.
- `.env` đã được ignore trong `.gitignore`.
- API key chỉ đọc từ biến môi trường.
- Không có API key thật trong code, prompt, README, GUIDE, report hoặc log.

## 5. Chạy Smoke Test Thật

Smoke test vẫn gọi API thật, nhưng chỉ chạy 1 sample, 1 seed, 2 agent và số cấu hình rất nhỏ. Nên chạy smoke test trước để kiểm tra API/model/parser.

### 5.1. Chuẩn bị dữ liệu

```bash
python scripts/prepare_data.py --config configs/real_smoke.yaml
```

Lệnh này không gọi OpenAI API. Nó tải dataset từ HuggingFace, chuẩn hóa sample và ghi:

```text
outputs_real_smoke/processed/samples.jsonl
outputs_real_smoke/processed/sample_ids.json
```

### 5.2. Chạy baseline bằng API thật

```bash
python scripts/run_baselines.py --config configs/real_smoke.yaml
```

Lệnh này gọi model thật để chạy:

- `single_direct`
- `single_cot`
- `self_consistency`
- `multi_agent_majority`

Output:

```text
outputs_real_smoke/raw/baselines.jsonl
outputs_real_smoke/raw/response_cache.jsonl
```

### 5.3. Chạy debate bằng API thật

```bash
python scripts/run_debate.py --config configs/real_smoke.yaml
```

Lệnh này gọi model thật để chạy:

- `homogeneous_debate`
- `specialized_debate` + Majority Voting
- `specialized_debate` + Judge

Output:

```text
outputs_real_smoke/raw/debate.jsonl
```

### 5.4. Chạy ablation bằng API thật

```bash
python scripts/run_ablations.py --config configs/real_smoke.yaml
```

Lệnh này gọi model thật để kiểm tra đường ablation tối thiểu.

Output:

```text
outputs_real_smoke/raw/ablations.jsonl
```

### 5.5. Đánh giá smoke output

```bash
python scripts/evaluate.py --config configs/real_smoke.yaml
```

Lệnh này không gọi API. Nó sinh:

```text
outputs_real_smoke/processed/predictions.csv
outputs_real_smoke/tables/main_results.csv
outputs_real_smoke/tables/reasoning_diversity.csv
outputs_real_smoke/tables/error_taxonomy_counts.csv
```

### 5.6. Sinh bảng Markdown

```bash
python scripts/generate_report_tables.py --config configs/real_smoke.yaml
```

Lệnh này không gọi API. Nó sinh:

```text
report/generated_tables.md
```

Không chạy `evaluate.py` và `generate_report_tables.py` song song vì `generate_report_tables.py` cần file do `evaluate.py` tạo trước.

## 6. Chạy Main Experiment Thật

Sau khi smoke test thành công, chạy cấu hình chính:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml
python scripts/run_baselines.py --config configs/experiment.yaml
python scripts/run_debate.py --config configs/experiment.yaml
python scripts/run_ablations.py --config configs/experiment.yaml
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

Các lệnh gọi API thật:

- `run_baselines.py`
- `run_debate.py`
- `run_ablations.py`

Các lệnh không gọi API:

- `prepare_data.py`
- `evaluate.py`
- `generate_report_tables.py`

## 7. Ý Nghĩa Từng Script

### `prepare_data.py`

Tải và chuẩn hóa dữ liệu.

Output:

```text
outputs/processed/samples.jsonl
outputs/processed/sample_ids.json
```

Ý nghĩa:

- `samples.jsonl`: dữ liệu đã chuẩn hóa theo schema chung.
- `sample_ids.json`: danh sách sample ID đã khóa để tái lập.

### `run_baselines.py`

Chạy 4 baseline:

- B1 `single_direct`
- B2 `single_cot`
- B3 `self_consistency`
- B4 `multi_agent_majority`

Output:

```text
outputs/raw/baselines.jsonl
```

### `run_debate.py`

Chạy Multi-Agent Debate:

- Homogeneous Debate.
- Specialized Debate + Majority Voting.
- Specialized Debate + Judge.
- Rounds: 0, 1, 2, 3.

Output:

```text
outputs/raw/debate.jsonl
```

### `run_ablations.py`

Chạy ablation:

- Số vòng debate.
- Remove-one-role.
- Decision protocol.
- Số lượng agent.

Output:

```text
outputs/raw/ablations.jsonl
```

### `evaluate.py`

Tính metrics từ raw output.

Output:

```text
outputs/processed/predictions.csv
outputs/tables/main_results.csv
outputs/tables/reasoning_diversity.csv
outputs/tables/error_taxonomy_counts.csv
outputs/tables/behavioral_transitions.csv
outputs/tables/correction_degradation.json
outputs/figures/
```

### `generate_report_tables.py`

Sinh bảng Markdown cho report:

```text
report/generated_tables.md
```

## 8. Agent Trong Hệ Thống

Cấu hình chính:

```yaml
default_agents: 5
```

Nghĩa là mỗi sample có 5 Solver agent độc lập ở giai đoạn đầu.

Các role:

- `Solver`: giải câu hỏi, trả đáp án, rationale_summary, evidence và confidence.
- `Critic`: tìm lỗi logic, thiếu bằng chứng, giả định không có căn cứ.
- `Skeptic`: tìm phản ví dụ, cách hiểu khác và trường hợp biên.
- `Evidence Checker`: kiểm tra claim, gắn nhãn SUPPORTED/UNSUPPORTED/CONTRADICTED/UNCERTAIN.
- `Judge`: chọn final answer dựa trên reasoning quality và evidence support.

Số lần gọi API tăng theo số agent, số vòng debate và decision protocol.

## 9. Output Raw Và Vì Sao Quan Trọng

Raw output là dữ liệu kiểm chứng chính của nghiên cứu.

Các file:

```text
outputs/raw/baselines.jsonl
outputs/raw/debate.jsonl
outputs/raw/ablations.jsonl
outputs/raw/response_cache.jsonl
```

Mỗi dòng thường có:

- `sample_id`
- `dataset`
- `method`
- `seed`
- `answer`
- `gold`
- `correct`
- `confidence`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `latency_seconds`
- `traces`
- `raw`

Không sửa tay raw output. Nếu cần chạy lại, nên backup trước.

## 10. Metrics

`evaluate.py` tính:

- Accuracy.
- Bootstrap 95% confidence interval.
- Token cost.
- Accuracy trên mỗi 1.000 token.
- Latency trung bình, median, P95.
- Brier Score.
- Expected Calibration Error.
- Semantic Reasoning Diversity.
- Correction Rate.
- Degradation Rate.
- Error taxonomy counts.
- Behavioral transitions.

Semantic diversity mặc định:

```text
Semantic Diversity = 1 - mean pairwise cosine similarity
```

Không đồng nhất diversity cao với reasoning đúng. Diversity chỉ đo mức khác nhau giữa các reasoning trace.

## 11. Cách Đọc Bảng Kết Quả

Mở:

```text
outputs/tables/main_results.csv
```

Các cột quan trọng:

- `dataset`: dataset.
- `method`: phương pháp.
- `n`: số mẫu.
- `accuracy`: độ chính xác.
- `accuracy_ci_low`, `accuracy_ci_high`: khoảng tin cậy bootstrap.
- `mean_total_tokens`: token trung bình.
- `accuracy_per_1000_tokens`: hiệu quả theo token.
- `mean_latency_seconds`: độ trễ trung bình.
- `brier_score`: Brier Score.
- `ece`: Expected Calibration Error.

Khi viết báo cáo, cần so sánh Accuracy với token cost và latency, không chỉ nhìn Accuracy.

## 12. Test

Chạy:

```bash
pytest
```

Test kiểm tra:

- Schema Pydantic.
- Majority vote.
- Metric functions.
- Correction/degradation.

## 13. Chạy Lại Và Ghi Đè Output

Mặc định:

```yaml
runtime:
  overwrite: false
```

Nếu output đã tồn tại, script sẽ dừng để tránh ghi đè kết quả thật.

Muốn chạy lại cùng output path:

```yaml
runtime:
  overwrite: true
```

Khuyến nghị tốt hơn là dùng output_dir mới:

```yaml
output_dir: outputs_real_run_001
```

`outputs_real*/` đã được ignore để tránh push raw output thật.

## 14. Kiểm Tra Không Lộ API Key Trước Khi Push

Chạy:

```bash
rg "sk-proj|OPENAI_API_KEY=" -n --glob "!*.env" --glob "!.env"
```

Chạy thêm:

```bash
git status --short --ignored
```

Đảm bảo:

- `.env` bị ignore.
- `outputs/raw/*` bị ignore.
- `outputs_real*/` bị ignore.
- Không có API key thật trong source code, report, README hoặc GUIDE.

## 15. Lỗi Thường Gặp

### Thiếu API key

Kiểm tra `.env`:

```text
OPENAI_API_KEY=...
```

### Output đã tồn tại

Đặt `runtime.overwrite: true` hoặc đổi `output_dir`.

### Model trả JSON chưa đúng schema

Model thật đôi khi trả format hơi lệch. Parser đã xử lý các trường hợp phổ biến trong:

```text
src/schemas/agent_outputs.py
```

### LogiQA lỗi dataset script

Loader đã fallback sang bản Parquet auto-converted trong:

```text
src/datasets/loader.py
```

### Không sinh biểu đồ

Cài đủ requirements:

```bash
pip install -r requirements.txt
```

Rồi chạy lại:

```bash
python scripts/evaluate.py --config configs/experiment.yaml
```

## 16. Smoke Test Thật Đã Chạy

Project đã được kiểm tra bằng API thật với:

```text
config: configs/real_smoke.yaml
output_dir: outputs_real_smoke
model: gpt-4o-mini
dry_run: false
```

Kết quả smoke:

- `baselines.jsonl`: 4 dòng.
- `debate.jsonl`: 3 dòng.
- `ablations.jsonl`: 1 dòng.
- `response_cache.jsonl`: 18 response/cache entries.

Token ghi nhận:

- Baselines: 3,508 tokens.
- Debate: 4,355 tokens.
- Ablations: 2,039 tokens.

Smoke test xác nhận API key, model thật, dataset loader, parser, evaluator và report table generation đều hoạt động. Vì chỉ có 1 sample, không dùng kết quả này để kết luận khoa học.

## 17. Nguyên Tắc Khi Dùng Kết Quả Thật

- Chỉ kết luận từ raw output thật.
- Không dùng smoke 1 sample để kết luận.
- Không dùng mock/dry-run làm số liệu nghiên cứu.
- Không bịa số liệu còn thiếu.
- Không chỉnh hypothesis sau khi thấy kết quả nếu không ghi rõ.
- Không nói debate tốt hơn Majority Voting nếu fair-compute không hỗ trợ.
- Không đồng nhất consensus với xác suất đúng.
- Không đồng nhất reasoning diversity với correctness.

Sau khi chạy main experiment thật, cập nhật `report/report.md` bằng bảng thật trong `outputs/tables/`.
