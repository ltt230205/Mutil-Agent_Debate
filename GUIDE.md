# GUIDE: Hướng Dẫn Chạy Và Hiểu Pipeline

Tài liệu này hướng dẫn chi tiết cách chạy toàn bộ project **Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning**. Mục tiêu là giúp bạn chạy được từ đầu đến cuối: chuẩn bị dữ liệu, chạy baseline, chạy Multi-Agent Debate, chạy ablation, đánh giá kết quả và sinh bảng cho báo cáo.

## 1. Ý Nghĩa Tổng Quát Của Project

Project này kiểm tra câu hỏi nghiên cứu: **Multi-Agent Debate có thật sự tốt hơn Majority Voting trong NLP reasoning hay không?**

Pipeline được thiết kế để so sánh nhiều phương pháp:

- `single_direct`: một agent trả lời trực tiếp.
- `single_cot`: một agent trả lời kèm tóm tắt lập luận có cấu trúc.
- `self_consistency`: một model sinh nhiều lời giải độc lập rồi chọn đáp án phổ biến nhất.
- `multi_agent_majority`: nhiều agent trả lời độc lập rồi majority vote.
- `homogeneous_debate`: nhiều agent cùng kiểu prompt tranh luận qua nhiều vòng.
- `specialized_debate`: các agent có vai trò khác nhau như Solver, Critic, Skeptic, Evidence Checker và Judge.
- `ablation`: bỏ bớt role, đổi số vòng debate, đổi decision protocol hoặc đổi số agent.

Điểm quan trọng: project **không giả định debate luôn tốt hơn voting**. Tất cả kết luận phải đến từ raw output thật trong `outputs/raw/`.

## 2. Luồng Pipeline

Pipeline đầy đủ gồm 6 bước chính:

```text
prepare_data
  -> run_baselines
  -> run_debate
  -> run_ablations
  -> evaluate
  -> generate_report_tables
```

Ý nghĩa từng bước:

| Bước | Script | Ý nghĩa |
|---|---|---|
| 1 | `prepare_data.py` | Tải hoặc tạo dữ liệu, chuẩn hóa sample, khóa sample IDs |
| 2 | `run_baselines.py` | Chạy các baseline đối chứng |
| 3 | `run_debate.py` | Chạy hệ thống Multi-Agent Debate chính |
| 4 | `run_ablations.py` | Chạy các thí nghiệm ablation |
| 5 | `evaluate.py` | Tính metrics, gom raw output thành CSV/tables |
| 6 | `generate_report_tables.py` | Sinh bảng Markdown để đưa vào báo cáo |

## 3. Cài Đặt Môi Trường

### 3.1. Tạo virtual environment

Trên Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Trên macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3.2. Cài dependencies

```bash
pip install -r requirements.txt
```

Lệnh này cài các thư viện cần thiết như `datasets`, `openai`, `pydantic`, `pandas`, `scikit-learn`, `pytest`, `PyYAML` và `matplotlib`.

Nếu không cài `matplotlib`, pipeline vẫn có thể sinh CSV/tables, nhưng biểu đồ PNG sẽ không được tạo.

## 4. Cấu Hình API Key Và Model

Tạo file `.env` từ `.env.example`:

Trên Windows:

```bash
copy .env.example .env
```

Trên macOS/Linux:

```bash
cp .env.example .env
```

Sau đó mở `.env` và điền:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_PROVIDER=openai
```

Lưu ý:

- Không commit `.env`.
- `.env` đã được ignore trong `.gitignore`.
- API key chỉ được đọc từ biến môi trường, không ghi vào code, log hoặc report.
- Model name chính nằm trong `configs/models.yaml`.

## 5. Chạy Chế Độ Dry-Run

Dry-run dùng dữ liệu mô phỏng và response mô phỏng. Chế độ này dùng để kiểm tra code, schema, output, evaluator và report pipeline mà không tốn tiền API.

Chạy lần lượt:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml --dry-run
```

Ý nghĩa:

- Tạo dữ liệu mẫu mô phỏng.
- Chuẩn hóa sample về schema chung.
- Ghi file `outputs/processed/samples.jsonl`.
- Ghi danh sách ID vào `outputs/processed/sample_ids.json`.

Tiếp theo:

```bash
python scripts/run_baselines.py --config configs/experiment.yaml --dry-run
```

Ý nghĩa:

- Chạy `single_direct`.
- Chạy `single_cot`.
- Chạy `self_consistency`.
- Chạy `multi_agent_majority`.
- Lưu kết quả thô vào `outputs/raw/baselines.jsonl`.
- Lưu cache response vào `outputs/raw/response_cache.jsonl`.

Tiếp theo:

```bash
python scripts/run_debate.py --config configs/experiment.yaml --dry-run
```

Ý nghĩa:

- Chạy debate với nhiều số vòng: `0, 1, 2, 3`.
- Chạy homogeneous debate.
- Chạy specialized debate với Majority Voting.
- Chạy specialized debate với Judge.
- Lưu kết quả vào `outputs/raw/debate.jsonl`.

Tiếp theo:

```bash
python scripts/run_ablations.py --config configs/experiment.yaml --dry-run
```

Ý nghĩa:

- Khảo sát số vòng debate.
- So sánh remove-one-role: bỏ Critic, Skeptic, Evidence Checker hoặc Judge.
- So sánh decision protocol: Majority, Judge, Evidence-Aware Judge.
- Khảo sát số agent: 2, 3, 5.
- Lưu kết quả vào `outputs/raw/ablations.jsonl`.

Tiếp theo:

```bash
python scripts/evaluate.py --config configs/experiment.yaml
```

Ý nghĩa:

- Đọc các file JSONL trong `outputs/raw/`.
- Tạo `outputs/processed/predictions.csv`.
- Tính Accuracy.
- Tính Semantic Reasoning Diversity.
- Tính token cost và latency.
- Tính Brier Score và Expected Calibration Error.
- Sinh bảng `outputs/tables/main_results.csv`.
- Sinh bảng `outputs/tables/reasoning_diversity.csv`.
- Sinh bảng `outputs/tables/error_taxonomy_counts.csv`.
- Nếu đủ dữ liệu, sinh `outputs/tables/behavioral_transitions.csv`.
- Nếu có `matplotlib`, sinh biểu đồ trong `outputs/figures/`.

Cuối cùng:

```bash
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

Ý nghĩa:

- Đọc `outputs/tables/main_results.csv`.
- Sinh bảng Markdown vào `report/generated_tables.md`.
- Bảng này có thể được chèn hoặc tham khảo khi viết `report/report.md`.

Lưu ý quan trọng: kết quả dry-run **không phải kết quả khoa học thật**. Nó chỉ chứng minh pipeline chạy được.

## 6. Chạy Toàn Bộ Dry-Run Bằng Một Chuỗi Lệnh

Trên Windows PowerShell:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml --dry-run
python scripts/run_baselines.py --config configs/experiment.yaml --dry-run
python scripts/run_debate.py --config configs/experiment.yaml --dry-run
python scripts/run_ablations.py --config configs/experiment.yaml --dry-run
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

Không nên chạy `evaluate.py` và `generate_report_tables.py` song song, vì `generate_report_tables.py` cần file do `evaluate.py` tạo ra trước.

## 7. Chạy Thí Nghiệm Thật Với API

Trước khi chạy thật, mở `configs/experiment.yaml` và chỉnh:

```yaml
runtime:
  dry_run: false
  overwrite: false
  resume: true
  max_samples_per_run:
  pilot_samples: 20
```

Nếu muốn chạy pilot nhỏ trước, đặt:

```yaml
runtime:
  dry_run: false
  max_samples_per_run: 20
```

Sau khi kiểm tra ổn, có thể đặt `max_samples_per_run` rỗng để chạy toàn bộ subset.

Chạy dữ liệu thật:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml
```

Script này sẽ tải dataset qua HuggingFace theo `configs/datasets.yaml`.

Chạy baseline thật:

```bash
python scripts/run_baselines.py --config configs/experiment.yaml
```

Chạy debate thật:

```bash
python scripts/run_debate.py --config configs/experiment.yaml
```

Chạy ablation thật:

```bash
python scripts/run_ablations.py --config configs/experiment.yaml
```

Đánh giá:

```bash
python scripts/evaluate.py --config configs/experiment.yaml
```

Sinh bảng báo cáo:

```bash
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

## 8. Ý Nghĩa Các File Cấu Hình

### 8.1. `configs/experiment.yaml`

Đây là file cấu hình chính.

Các tham số quan trọng:

- `random_seeds`: danh sách seed để chạy lặp lại.
- `datasets`: dataset dùng trong thí nghiệm.
- `sample_size_per_dataset`: số mẫu mỗi dataset.
- `default_agents`: số agent mặc định.
- `debate_rounds`: số vòng debate cần khảo sát.
- `self_consistency_k`: số reasoning path trong Self-Consistency.
- `baselines`: danh sách baseline cần chạy.
- `debate_methods`: danh sách phương pháp debate.
- `ablations`: cấu hình ablation.
- `runtime.dry_run`: bật/tắt chế độ chạy thử.
- `runtime.overwrite`: cho phép ghi đè output cũ hay không.
- `evaluation.semantic_diversity.method`: cách đo semantic diversity.

### 8.2. `configs/models.yaml`

File này chứa cấu hình model:

- `provider`: provider model, ví dụ `openai`.
- `default_model`: model sinh câu trả lời.
- `embedding_model`: model embedding nếu dùng semantic embedding.
- `temperature`: độ ngẫu nhiên khi sinh output.
- `max_output_tokens`: giới hạn output token.
- `retry.max_attempts`: số lần retry khi lỗi.
- `rate_limit.min_delay_seconds`: khoảng nghỉ tối thiểu giữa các lần gọi API.

### 8.3. `configs/datasets.yaml`

File này chứa cấu hình dataset:

- HuggingFace dataset name.
- Split dùng để đánh giá.
- Số mẫu cần chọn.
- File khóa sample IDs.
- Tiêu chí loại bỏ mẫu thiếu đáp án.

## 9. Ý Nghĩa Các Prompt

Prompt nằm trong thư mục `prompts/`.

- `solver.txt`: agent giải bài và đưa đáp án.
- `critic.txt`: agent tìm lỗi logic, thiếu evidence, giả định sai.
- `skeptic.txt`: agent tìm phản ví dụ, cách hiểu khác và trường hợp biên.
- `evidence_checker.txt`: agent gắn nhãn bằng chứng cho từng claim.
- `judge.txt`: agent chọn đáp án cuối dựa trên chất lượng lập luận và evidence.

Các prompt đã được viết bằng tiếng Việt có dấu. Output JSON vẫn giữ tên field tiếng Anh để ổn định schema, nhưng giá trị chuỗi được yêu cầu trả lời bằng tiếng Việt có dấu.

## 10. Ý Nghĩa Các Output

### 10.1. `outputs/raw/`

Chứa output thô.

- `baselines.jsonl`: kết quả từng sample cho baseline.
- `debate.jsonl`: kết quả từng sample cho debate.
- `ablations.jsonl`: kết quả từng sample cho ablation.
- `response_cache.jsonl`: cache response để không gọi API lại khi request trùng.

Mỗi dòng là một JSON object. Đây là dữ liệu quan trọng nhất để kiểm chứng nghiên cứu.

### 10.2. `outputs/processed/`

Chứa dữ liệu đã xử lý.

- `samples.jsonl`: sample chuẩn hóa.
- `sample_ids.json`: danh sách sample ID đã khóa.
- `predictions.csv`: toàn bộ prediction đã gom từ raw JSONL.

### 10.3. `outputs/tables/`

Chứa bảng tổng hợp.

- `main_results.csv`: bảng chính gồm accuracy, token cost, latency, calibration.
- `reasoning_diversity.csv`: semantic diversity theo từng prediction.
- `error_taxonomy_counts.csv`: thống kê loại lỗi.
- `behavioral_transitions.csv`: chuyển đổi hành vi trước/sau debate.
- `correction_degradation.json`: Correction Rate và Degradation Rate.

### 10.4. `outputs/figures/`

Chứa biểu đồ được sinh bởi `evaluate.py`, ví dụ:

- Accuracy theo method.
- Token cost theo method.

Nếu thiếu `matplotlib`, thư mục này sẽ có file `FIGURES_NOT_GENERATED.txt`.

### 10.5. `report/`

Chứa báo cáo:

- `report/report.md`: báo cáo tiếng Việt.
- `report/references.bib`: tài liệu tham khảo BibTeX.
- `report/generated_tables.md`: bảng Markdown sinh từ kết quả.

## 11. Các Metric Được Tính

### Accuracy

Tỷ lệ câu trả lời đúng:

```text
Accuracy = số câu đúng / tổng số câu
```

### Correction Rate

Tỷ lệ mẫu sai trước debate nhưng đúng sau debate:

```text
Correction Rate = wrong_before_correct_after / wrong_before
```

### Degradation Rate

Tỷ lệ mẫu đúng trước debate nhưng sai sau debate:

```text
Degradation Rate = correct_before_wrong_after / correct_before
```

### Semantic Reasoning Diversity

Đo mức khác nhau giữa các `rationale_summary`:

```text
Semantic Diversity = 1 - mean pairwise cosine similarity
```

Mặc định pipeline dùng TF-IDF để chạy offline. Có thể mở rộng sang embedding model cố định.

### Token Cost

Ghi:

- input tokens
- output tokens
- total tokens
- tokens trung bình mỗi sample

### Latency

Ghi:

- latency trung bình
- median latency
- P95 latency

### Calibration

Gồm:

- Brier Score
- Expected Calibration Error

Không được đồng nhất confidence tự báo cáo với xác suất đúng thật.

## 12. Kiểm Thử

Chạy:

```bash
pytest
```

Ý nghĩa:

- Kiểm tra schema Pydantic.
- Kiểm tra majority vote.
- Kiểm tra metric functions.
- Kiểm tra correction/degradation.

Nếu test pass, bạn có thể tự tin rằng các thành phần lõi đang hoạt động.

## 13. Khi Output Cũ Đã Tồn Tại

Các script `run_baselines.py`, `run_debate.py`, `run_ablations.py` không ghi đè output cũ nếu `runtime.overwrite: false`.

Nếu muốn chạy lại từ đầu:

1. Xóa các file trong `outputs/raw/`, `outputs/processed/`, `outputs/tables/`, `outputs/figures/`.
2. Hoặc chỉnh trong `configs/experiment.yaml`:

```yaml
runtime:
  overwrite: true
```

Khuyến nghị: khi chạy thí nghiệm thật, không nên xóa raw output nếu chưa backup.

## 14. Cách Đọc Kết Quả

Mở bảng chính:

```bash
outputs/tables/main_results.csv
```

Các cột quan trọng:

- `dataset`: dataset đang xét.
- `method`: phương pháp.
- `n`: số prediction.
- `accuracy`: độ chính xác.
- `accuracy_ci_low`, `accuracy_ci_high`: bootstrap confidence interval.
- `mean_total_tokens`: token trung bình.
- `accuracy_per_1000_tokens`: accuracy trên mỗi 1.000 token.
- `mean_latency_seconds`: latency trung bình.
- `brier_score`: lỗi calibration.
- `ece`: Expected Calibration Error.

Để xem diversity:

```bash
outputs/tables/reasoning_diversity.csv
```

Để xem behavioral analysis:

```bash
outputs/tables/behavioral_transitions.csv
```

Để xem error taxonomy:

```bash
outputs/tables/error_taxonomy_counts.csv
```

## 15. Quy Trình Khuyến Nghị Khi Làm Nghiên Cứu Thật

1. Chạy `pytest`.
2. Chạy dry-run đầy đủ.
3. Chạy pilot thật với `max_samples_per_run: 20`.
4. Kiểm tra raw JSONL xem agent có trả đúng schema không.
5. Kiểm tra chi phí token và latency.
6. Khóa prompt và config.
7. Chạy main experiment.
8. Chạy ablation.
9. Chạy evaluate.
10. Sinh bảng và cập nhật report.
11. Chỉ kết luận hypothesis dựa trên output thật.

## 16. Các Lỗi Thường Gặp

### Lỗi thiếu API key

Nếu chạy thật mà thiếu key, bạn sẽ gặp lỗi liên quan `OPENAI_API_KEY`.

Cách sửa:

- Kiểm tra file `.env`.
- Đảm bảo đã chạy trong đúng thư mục repo.
- Đảm bảo không commit `.env`.

### Lỗi output file đã tồn tại

Nếu thấy lỗi kiểu file đã tồn tại, có hai cách:

- Đổi tên hoặc backup file output cũ.
- Đặt `runtime.overwrite: true`.

### Lỗi thiếu dataset

Nếu HuggingFace dataset không tải được:

- Kiểm tra kết nối mạng.
- Kiểm tra tên dataset trong `configs/datasets.yaml`.
- Cài lại dependency bằng `pip install -r requirements.txt`.

### Lỗi không sinh biểu đồ

Nếu không có biểu đồ PNG:

- Cài `matplotlib`.
- Chạy lại:

```bash
python scripts/evaluate.py --config configs/experiment.yaml
```

### Tiếng Việt hiển thị sai trên PowerShell

Một số console Windows có thể hiển thị sai dấu dù file lưu đúng UTF-8.

Có thể kiểm tra bằng cách mở file trong VS Code hoặc chạy:

```bash
python -c "from pathlib import Path; print(Path('prompts/solver.txt').read_text(encoding='utf-8')[:100])"
```

## 17. Trước Khi Push Lên Git

Kiểm tra:

```bash
git status --short --ignored
```

Đảm bảo:

- `.env` bị ignore.
- `outputs/raw/*` bị ignore.
- `outputs/processed/*` bị ignore.
- `outputs/tables/*` bị ignore.
- cache Python bị ignore.
- source code, config, prompts, README, GUIDE và report chính vẫn được track.

## 18. Lệnh Tái Lập Nhanh

Dry-run:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml --dry-run
python scripts/run_baselines.py --config configs/experiment.yaml --dry-run
python scripts/run_debate.py --config configs/experiment.yaml --dry-run
python scripts/run_ablations.py --config configs/experiment.yaml --dry-run
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

Test:

```bash
pytest
```

Chạy thật:

```bash
python scripts/prepare_data.py --config configs/experiment.yaml
python scripts/run_baselines.py --config configs/experiment.yaml
python scripts/run_debate.py --config configs/experiment.yaml
python scripts/run_ablations.py --config configs/experiment.yaml
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

## 19. Nguyên Tắc Trung Thực Khi Viết Báo Cáo

- Không dùng dry-run làm kết quả nghiên cứu.
- Không bịa số liệu.
- Không bịa citation.
- Không chỉnh hypothesis sau khi thấy kết quả mà không ghi rõ.
- Không dùng test set để tối ưu prompt.
- Không nói debate tốt hơn voting nếu fair-compute không hỗ trợ.
- Không đồng nhất reasoning diversity với correctness.
- Không đồng nhất consensus score với xác suất đúng.

Khi chạy xong thí nghiệm thật, hãy cập nhật `report/report.md` dựa trên bảng thật trong `outputs/tables/`.
