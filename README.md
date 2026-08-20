# Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning

## 1. Giới thiệu đề tài

Dự án nghiên cứu câu hỏi: **Multi-Agent Debate (MAD) có làm cho suy luận NLP đáng tin cậy hơn Majority Voting hay không?**

Thay vì mặc định nhiều agent tranh luận luôn tốt hơn, dự án so sánh có kiểm soát giữa một agent, Self-Consistency, nhiều agent bỏ phiếu và nhiều biến thể debate. Hệ thống lưu toàn bộ phản hồi, token, latency và quyết định cuối để có thể kiểm tra lại kết quả mà không phải gọi API lần nữa.

Notebook dùng để tạo kết quả cuối cho báo cáo là [`KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb`](KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb): 100 mẫu holdout, ba seed, bốn baseline, MAD-v2 và bốn nhóm ablation. [`KAGGLE_MAD_V2_PIPELINE.ipynb`](KAGGLE_MAD_V2_PIPELINE.ipynb) là pilot nhỏ hơn. Cả hai đều **standalone**: chỉ cần upload đúng một file lên Kaggle, bật Internet, thêm API key bằng Kaggle Secrets và chạy toàn bộ cell.

MAD-v2 dùng cùng ngân sách 10 `protocol_calls` với Majority Voting N=10. Sáu Solver đầu được chia sẻ giữa hai phương pháp; câu có đồng thuận mạnh đi tiếp theo MV, còn câu bất định dùng bốn lượt cho Critic, Evidence Checker, Revision và Blind Judge. Việc đổi đáp án chỉ được chấp nhận khi Critic, Evidence Checker, Revision và Judge cùng tạo ra chuỗi bằng chứng nhất quán. Notebook dùng holdout mới và loại toàn bộ sample ID đã dùng trong giai đoạn phát triển giao thức; vì vậy không được cam kết MAD sẽ thắng trước khi chạy kết quả thật.

Các prompt và nội dung giải thích do agent sinh ra được yêu cầu viết bằng **tiếng Việt có dấu**. Tên field JSON, nhãn đáp án và enum giữ tiếng Anh để schema ổn định.

## 2. Pain point của đề tài

### 2.1. Một câu trả lời đúng chưa chắc đến từ reasoning đáng tin cậy

LLM có thể chọn đúng đáp án nhưng phần giải thích chứa giả định không có trong đề, bỏ sót điều kiện hoặc suy luận không hợp lệ. Nếu chỉ đo Accuracy, những lỗi này bị che khuất.

### 2.2. Majority Voting chỉ đếm đáp án

Majority Voting chọn nhãn xuất hiện nhiều nhất nhưng không đánh giá chất lượng lập luận. Một agent thiểu số có thể đúng và có bằng chứng tốt hơn, trong khi nhiều agent còn lại cùng lặp lại một lỗi tương quan.

### 2.3. Nhiều mẫu không đồng nghĩa với reasoning diversity

Self-Consistency hoặc nhiều agent có thể tạo ra các câu chữ khác nhau nhưng vẫn dùng cùng một chiến lược sai. Vì vậy dự án đo riêng:

- Mức bất đồng đáp án.
- Khoảng cách ngữ nghĩa giữa reasoning trace.
- Quan hệ giữa diversity và độ chính xác.

### 2.4. Debate cũng có thể làm kết quả xấu đi

Trao đổi giữa agent có thể sửa lỗi, nhưng cũng có thể tạo ra majority pressure, conformity, sycophancy, lan truyền lỗi hoặc Judge bias. Dự án vì thế đo cả:

- **Correction Rate:** sai trước debate, đúng sau debate.
- **Degradation Rate:** đúng trước debate, sai sau debate.
- **Resistant Error:** sai trước và vẫn sai sau debate.
- **Minority-Correct Case:** agent đúng thuộc nhóm thiểu số.

### 2.5. So sánh không công bằng về compute

So sánh một lần gọi Single Agent với hàng chục lần gọi Debate sẽ không cho biết lợi ích đến từ protocol hay đơn giản từ compute lớn hơn. Notebook có cấu hình call-matched để so sánh Specialized Debate + Judge với Self-Consistency và Majority Voting dùng 10 model calls.

### 2.6. Output của LLM không luôn tuân thủ JSON

Model có thể trả sai tên field, sai enum, bọc JSON trong văn bản hoặc trả confidence ngoài kiểu mong đợi. Pipeline sử dụng Pydantic, normalization và schema retry có giới hạn để tránh làm hỏng cả thí nghiệm.

### 2.7. Thí nghiệm API khó tái lập

API có chi phí, rate limit và độ trễ; phiên Kaggle cũng có thể bị ngắt. Notebook giải quyết bằng seed control, khóa sample ID, JSONL append-only, response cache và checkpoint theo từng cấu hình.

## 3. Câu hỏi nghiên cứu

| Mã | Câu hỏi | Thí nghiệm chính | Chỉ số |
|---|---|---|---|
| RQ1 | Debate có tạo reasoning diversity thực sự không? | Self-Consistency, Majority Voting, Homogeneous và Specialized Debate | Answer Disagreement, Semantic Diversity |
| RQ2 | Debate có tốt hơn voting khi compute tương đương không? | Specialized Debate + Judge so với K=10/N=10 | Accuracy, calls, token, latency, Accuracy/1.000 token |
| RQ3 | Số vòng debate ảnh hưởng thế nào? | Rounds 0, 1, 2, 3 | Accuracy, correction, degradation, diversity, cost |
| RQ4 | Role specialization có ích không? | Homogeneous, Specialized, remove-one-role | Accuracy, error taxonomy, cost |
| RQ5 | Debate thất bại trong trường hợp nào? | Behavioral và error analysis | Successful Correction, Resistant Error, Harmful Revision, Minority-Correct |

Các giả thuyết H1-H5 chỉ được kết luận sau khi có dữ liệu thật. Notebook không có logic ép kết quả phải ủng hộ MAD.

## 4. Ý tưởng giải pháp

### 4.1. Nguyên tắc thiết kế

Mỗi câu hỏi trước tiên được nhiều Solver giải **độc lập**. Sau đó hệ thống ghi nhận bất đồng, cho các role chuyên biệt kiểm tra lập luận, yêu cầu Solver sửa câu trả lời và cuối cùng dùng Majority Voting hoặc Blind Judge để quyết định.

```text
Input Question
    |
    v
Independent Solver Responses
    |
    v
Disagreement Detection
    |
    +--> Critic: tìm lỗi logic và giả định thiếu căn cứ
    +--> Skeptic: tìm phản ví dụ và cách hiểu khác
    +--> Evidence Checker: đối chiếu claim với đề bài
    |
    v
Solver Revision
    |
    v
Lặp theo số vòng debate
    |
    +--> Majority Voting
    +--> Blind Judge
    +--> Evidence-Aware Judge
    |
    v
Final Answer + Metrics + Raw JSONL
```

### 4.2. Các role trong hệ thống

| Role | Trách nhiệm |
|---|---|
| Solver | Chọn đáp án, viết rationale ngắn, liệt kê evidence và confidence |
| Critic | Tìm lỗi logic, hiểu sai, giả định thiếu căn cứ và bằng chứng bị bỏ sót |
| Skeptic | Thử bác bỏ kết luận, tìm phản ví dụ, cách hiểu khác và trường hợp biên |
| Evidence Checker | Gắn nhãn claim là `SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED` hoặc `UNCERTAIN` |
| Judge | So sánh reasoning và evidence, chọn đáp án cuối, không chỉ đếm phiếu |

Trong notebook có **5 loại role**. Cấu hình pilot mặc định tạo 3 Solver độc lập; ở Specialized Debate, mỗi vòng có thêm một Critic, một Skeptic và một Evidence Checker; Judge được gọi ở bước quyết định. Solver đồng thời đảm nhiệm bước Revision.

### 4.3. Blind Judge

Danh sách lời giải được xáo trộn bằng seed trước khi đưa cho Judge. Prompt không yêu cầu Judge ưu tiên agent theo tên hoặc thứ tự, đồng thời nhắc không đánh giá cao một lời giải chỉ vì nó dài hơn.

### 4.4. Structured output

Mọi role trả JSON. Ví dụ output Solver:

```json
{
  "sample_id": "logiqa_001",
  "agent_role": "solver",
  "round": 0,
  "answer": "B",
  "rationale_summary": ["Điều kiện thứ nhất loại phương án A."],
  "evidence": [
    {
      "claim": "Phương án A mâu thuẫn với điều kiện 1.",
      "source": "đề bài",
      "status": "SUPPORTED"
    }
  ],
  "confidence": 0.78
}
```

Pydantic kiểm tra nhãn đáp án, confidence, issue taxonomy, evidence status và kiểu dữ liệu. `sample_id`, `agent_role` và `round` được pipeline gán lại từ context để model không làm sai metadata của thí nghiệm.

## 5. Phạm vi pilot trong notebook

Notebook mặc định chạy `RUN_MODE = "pilot"` với cấu hình:

| Thành phần | Giá trị |
|---|---:|
| Model | `gpt-4o-mini` |
| Dataset | LogiQA và CommonsenseQA |
| Split | Validation |
| Số mẫu | 10 mẫu mỗi dataset, tổng 20 |
| Seed chính | 42, 123, 2026 |
| Solver mặc định | 3 |
| Main debate rounds | 1 |
| Self-Consistency | K=3 |
| Fair-compute | K/N=10 |
| Ablation subset | 4 mẫu mỗi dataset |
| Ablation seed | 42 |
| Ablation rounds | 0, 1, 2, 3 |
| Max output | 700 token mỗi response |

Đây là **exploratory pilot**, không phải kết quả đại diện cho toàn bộ benchmark. Mẫu ít giúp kiểm soát chi phí nhưng làm khoảng tin cậy rộng và statistical power thấp.

### Ước lượng model calls

| Nhóm | Cách tính | Model calls khái niệm |
|---|---:|---:|
| Baseline | 20 mẫu x 3 seed x 28 calls | 1.680 |
| Main Debate | 20 mẫu x 3 seed x 25 calls | 1.500 |
| Ablation | 8 mẫu x 223 calls | 1.784 |
| **Tổng tối đa trước retry** | | **4.964** |

Response cache tái sử dụng các request trùng nhau nên số request API thực tế có thể thấp hơn. Schema retry hoặc API retry có thể làm số request tăng. Chi phí thực phải đọc từ `input_tokens`, `output_tokens` và `total_tokens`, không suy ra chỉ từ số calls.

## 6. Các phương pháp được triển khai

### Baseline

| Method trong output | Ý nghĩa |
|---|---|
| `single_direct` | Một Solver, yêu cầu trả lời trực tiếp |
| `single_cot` | Một Solver với structured rationale |
| `self_consistency` | Ba reasoning path độc lập, chọn majority answer |
| `multi_agent_majority` | Ba Solver độc lập, không xem reasoning của nhau |
| `self_consistency_k10_call_matched` | Self-Consistency với 10 calls |
| `multi_agent_majority_n10_call_matched` | Majority Voting với 10 agent calls |

### Main Debate

| Method trong output | Calls dự kiến/mẫu | Ý nghĩa |
|---|---:|---|
| `homogeneous_debate_r1_majority` | 6 | 3 Solver ban đầu + 3 Solver revision, quyết định bằng majority |
| `specialized_debate_r1_majority` | 9 | Thêm Critic, Skeptic, Evidence Checker, quyết định bằng majority |
| `specialized_debate_r1_judge` | 10 | Cùng transcript debate và thêm Blind Judge |

M2 và M3 dùng cùng communication protocol để tách ảnh hưởng của **cách trao đổi** khỏi ảnh hưởng của **cách quyết định**.

### Ablation

Notebook chạy bốn nhóm ablation trên subset cố định:

- Rounds: 0, 1, 2 và 3.
- Remove-one-role: full, không Critic, không Skeptic, không Evidence Checker, không Judge.
- Decision protocol: Majority, Judge và Evidence-Aware Judge.
- Number of Solver agents: 2, 3 và 5.

## 7. Cách chạy trên Kaggle

### Bước 1: Upload notebook

Tạo Kaggle Notebook mới và import [`KAGGLE_PILOT_PIPELINE.ipynb`](KAGGLE_PILOT_PIPELINE.ipynb).

### Bước 2: Bật Internet

Mở **Notebook settings** và bật **Internet**. Internet cần cho ba việc: cài package, tải dataset từ Hugging Face và gọi OpenAI API.

### Bước 3: Tạo Kaggle Secret

Mở **Add-ons -> Secrets**, tạo secret:

```text
Name: OPENAI_API_KEY
Value: <API key của bạn>
```

Bật quyền truy cập secret cho notebook. Không ghi key trực tiếp vào cell, output, Git hoặc ảnh chụp màn hình. Nếu key đã từng bị công khai, hãy thu hồi key cũ và tạo key mới.

### Bước 4: Chọn chế độ chạy

Trong cell cấu hình:

```python
RUN_MODE = "pilot"
```

`pilot` gọi API thật với cấu hình trong Bảng phạm vi pilot. Để kiểm tra nhanh kết nối trước, có thể đổi thành:

```python
RUN_MODE = "smoke"
```

`smoke` cũng gọi API thật, không phải mock; nó chỉ giảm số mẫu, seed, agent và ablation.

### Bước 5: Chạy

Chọn **Run All**. Không cần upload repository, YAML, prompt hoặc dataset thủ công.

### Bước 6: Tải kết quả

Cell cuối tạo file:

```text
/kaggle/working/mad_pilot_real_results.zip
```

Mở panel **Output/Files** của Kaggle và tải ZIP về. Chỉ dùng kết quả trong báo cáo khi các cell baseline, debate, ablation, evaluation và integrity check đều hoàn tất.

## 8. Giải thích từng cell trong notebook

### Cell 0 - Mô tả pilot

Giới thiệu phạm vi, yêu cầu Kaggle Secret, quy mô thí nghiệm và cảnh báo rằng pilot không đại diện cho toàn benchmark.

### Cell 1 - Cài dependency

Cài `openai`, `datasets`, `pydantic`, `pandas`, `numpy`, `scipy`, `scikit-learn`, `matplotlib`, `sentence-transformers` và `tabulate`. Nếu Kaggle yêu cầu restart session sau khi đổi package, restart rồi chạy lại từ đầu.

### Cell 2 - Import và đọc API key

`UserSecretsClient().get_secret("OPENAI_API_KEY")` đọc key từ Kaggle Secrets. Nếu code chạy ngoài Kaggle, notebook dùng `getpass` để nhập key ẩn. Giá trị key không được in và bị xóa khỏi biến cục bộ sau khi khởi tạo biến môi trường.

### Cell 3 - Cấu hình

Dictionary `CFG` chứa model, temperature, retry, dataset, seed, sample size, số agent, số vòng, embedding model và thư mục output. Mọi tham số chính được đặt tập trung tại đây thay vì rải hard-code trong protocol.

`resume=True` cho phép bỏ qua prediction đã có. `overwrite=False` ngăn ghi đè kết quả cũ. `run_manifest.json` lưu cấu hình nhưng loại mọi field có tên chứa `key`.

### Cell 4 - Pydantic JSON contracts

Các class chính:

- `EvidenceItem`: claim, source và evidence status.
- `SolverOutput`: answer, rationale, evidence, confidence và reasoning ID.
- `Issue`: một lỗi thuộc taxonomy nghiên cứu.
- `CritiqueOutput`: output cho Critic và Skeptic.
- `EvidenceCheckerOutput`: kết quả kiểm tra bằng chứng.
- `JudgeOutput`: đáp án cuối, reasoning được chọn, lý do và confidence.

Validator chuẩn hóa enum, severity, role, list/string và chỉ chấp nhận đáp án A-E. Output sai schema được gửi lại tối đa theo `schema_attempts`.

### Cell 5 - Prompt, OpenAI client, cache và retry

`PROMPTS` chứa system prompt tiếng Việt cho từng role.

`complete_json()` thực hiện một model call với `response_format={"type": "json_object"}`. Hàm tạo SHA-256 cache key từ model, prompt, role, temperature, seed và token limit. Response mới được append vào `response_cache.jsonl`.

`parse_json_object()` thử parse toàn bộ response; nếu model bọc JSON trong văn bản, hàm thử trích object từ dấu `{` đầu đến `}` cuối.

`run_agent()` gọi model, cộng token/latency, kiểm tra Pydantic schema và retry nếu JSON không hợp lệ. Pipeline gán lại metadata cấu trúc trước validation.

### Cell 6 - Dataset preparation

`load_hf()` tải LogiQA và CommonsenseQA. Nếu Hugging Face không còn hỗ trợ dataset script, hàm fallback sang parquet conversion.

`canonicalize()` đưa hai schema khác nhau về một dạng chung:

```text
sample_id, dataset, context, question, choices, answer, source_index
```

Các mẫu được shuffle bằng seed 42, lấy đúng số lượng cấu hình và lưu vào:

```text
processed/samples.jsonl
processed/sample_ids.json
```

Danh sách ID đã khóa giúp lần chạy sau dùng đúng subset.

### Cell 7 - Protocol và record

Các hàm quan trọng:

| Hàm | Chức năng |
|---|---|
| `norm_answer()` | Chuẩn hóa nhãn đáp án |
| `majority_vote()` | Đếm phiếu và trả consensus score |
| `make_record()` | Tạo record chung gồm correctness, calls, token, latency, traces và raw output |
| `run_single()` | Chạy Single Direct hoặc Single CoT |
| `run_independent_vote()` | Chạy Self-Consistency hoặc Multi-Agent Majority |
| `debate_one()` | Điều phối Solver, role phản biện, revision và decision protocol |
| `checkpoint_keys()` | Đọc các khóa đã hoàn thành từ JSONL |
| `append_record()` | Append và flush từng prediction ngay sau khi hoàn tất |

`debate_one()` lưu riêng initial answer, initial correctness, initial consensus và initial disagreement. Đây là cơ sở tính Correction/Degradation đúng theo trạng thái **trước và sau debate**, không dùng một baseline khác làm trạng thái ban đầu.

Confidence được gắn loại rõ ràng:

- `self_reported_solver` cho Single Agent.
- `consensus_score` cho Majority Voting.
- `self_reported_judge` cho Judge.

Consensus score không được diễn giải như xác suất đúng.

### Cell 8 - Chạy baseline thật

Vòng lặp chạy 20 mẫu x 3 seed cho sáu cấu hình baseline. Mỗi record dùng khóa `(seed, sample_id, method)`; nếu khóa đã có và `resume=True`, notebook bỏ qua để tránh gọi API lại.

### Cell 9 - Chạy main debate thật

Chạy Homogeneous Debate + Majority, Specialized Debate + Majority và Specialized Debate + Judge. Transcript dùng chung được response cache tái sử dụng khi request giống nhau.

### Cell 10 - Chạy ablation thật

Chọn bốn mẫu đầu đã khóa của mỗi dataset và chạy ablation rounds, roles, decision protocol và số agent. Ablation chỉ dùng seed 42 để giới hạn chi phí; giới hạn này phải được nêu trong báo cáo.

### Cell 11 - Evaluation

Cell này không gọi OpenAI API. Nó đọc ba file prediction và sinh bảng/biểu đồ.

Các nhóm tính toán gồm:

- Accuracy theo dataset, method và seed.
- Mean/std qua seed và bootstrap 95% CI theo sample.
- Input/output/total token, model calls và latency mean/median/P95.
- Answer Disagreement Rate.
- Semantic Reasoning Diversity.
- Correction Rate và Degradation Rate.
- Brier Score, ECE và reliability diagram.
- McNemar exact test và win/loss/tie theo seed.
- Fair-compute call-matched và post-hoc nearest token budget.
- Behavioral cases và agent-reported error taxonomy.

Semantic diversity dùng model cố định:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Nếu model embedding không tải được, code fallback sang TF-IDF và ghi backend thật vào `embedding_metadata.json`. Không được trình bày kết quả fallback như embedding semantic mà không ghi chú.

Error taxonomy từ Critic/Skeptic được lưu dưới nhãn **agent-reported**. Các prediction sai của mọi phương pháp được xuất sang `error_cases_for_manual_annotation.csv`; notebook không tự bịa nhãn lỗi cho baseline khi không có bằng chứng.

### Cell 12 - Integrity check và đóng gói

Kiểm tra ba file raw chính tồn tại và có record. Sau đó notebook quét toàn bộ output bằng regex để chắc chắn không có chuỗi giống OpenAI API key.

Cuối cùng `shutil.make_archive()` đóng gói thư mục kết quả thành ZIP.

### Cell 13 - Ghi chú trung thực nghiên cứu

Nhắc lại giới hạn về sample size, statistical power, fair-compute và cách diễn giải diversity/confidence.

## 9. Chỉ số đánh giá

### Accuracy

$$
\text{Accuracy}
=
\frac{\text{Số dự đoán đúng}}
{\text{Tổng số dự đoán}}
$$

### Correction Rate

$$
\text{Correction Rate}
=
\frac{\text{Sai trước debate và đúng sau debate}}
{\text{Tổng số mẫu sai trước debate}}
$$

### Degradation Rate

$$
\text{Degradation Rate}
=
\frac{\text{Đúng trước debate và sai sau debate}}
{\text{Tổng số mẫu đúng trước debate}}
$$

### Answer Disagreement Rate

$$
\text{Disagreement Rate}
=
\frac{\text{Mẫu có ít nhất hai đáp án ban đầu khác nhau}}
{\text{Tổng số mẫu}}
$$

### Semantic Reasoning Diversity

Với các vector reasoning đã chuẩn hóa:

$$
\text{Semantic Diversity}
=
1-
\frac{1}{\binom{n}{2}}
\sum_{i<j}\cos(\mathbf{e}_i,\mathbf{e}_j)
$$

Diversity cao chỉ cho biết các trace khác nhau hơn về biểu diễn; nó không chứng minh trace đúng hơn.

## 10. Cấu trúc output của notebook

```text
mad_pilot_real/
├── run_manifest.json
├── raw/
│   ├── response_cache.jsonl
│   ├── baselines.jsonl
│   ├── debate.jsonl
│   └── ablations.jsonl
├── processed/
│   ├── samples.jsonl
│   ├── sample_ids.json
│   ├── predictions.csv
│   ├── embedding_metadata.json
│   ├── behavioral_cases.jsonl
│   └── error_cases_for_manual_annotation.csv
├── tables/
│   ├── main_results.csv
│   ├── per_seed_results.csv
│   ├── ablation_results.csv
│   ├── fair_compute_comparison.csv
│   ├── reasoning_diversity.csv
│   ├── diversity_accuracy_correlation.csv
│   ├── correction_degradation.csv
│   ├── mcnemar_win_loss_tie.csv
│   ├── behavioral_summary.csv
│   └── error_taxonomy_agent_reported.csv
└── figures/
    ├── accuracy_<dataset>.png
    ├── mean_total_tokens_<dataset>.png
    └── reliability_<dataset>.png
```

### File cần dùng cho báo cáo

| Nội dung báo cáo | File nguồn |
|---|---|
| Kết quả tổng thể | `tables/main_results.csv` |
| Mean/std qua seed | `tables/per_seed_results.csv` |
| Fair-compute | `tables/fair_compute_comparison.csv` |
| Rounds/roles/decision/agents | `tables/ablation_results.csv` |
| Correction/Degradation | `tables/correction_degradation.csv` |
| Reasoning diversity | `tables/reasoning_diversity.csv` |
| Calibration | `main_results.csv` và `figures/reliability_*.png` |
| Statistical test | `tables/mcnemar_win_loss_tie.csv` |
| Behavioral cases | `processed/behavioral_cases.jsonl` |
| Error analysis | `tables/error_taxonomy_agent_reported.csv` và file manual annotation |

## 11. Resume, cache và chống ghi đè

`response_cache.jsonl` lưu response theo hash của request. Các file prediction được append từng dòng, vì vậy kết quả đã hoàn thành vẫn còn nếu một cell bị dừng giữa chừng.

Khi chạy lại trong cùng môi trường còn thư mục output:

```python
"resume": True,
"overwrite": False,
```

Notebook sẽ bỏ qua các record hoàn tất. Nếu tạo Kaggle session hoàn toàn mới và `/kaggle/working` đã bị xóa, cần khôi phục output cũ trước thì resume mới có tác dụng. Hãy tải ZIP hoặc Save Version để bảo toàn kết quả sau phiên chạy.

Không đặt đồng thời `overwrite=True` nếu muốn tiếp tục checkpoint cũ.

## 12. Xử lý lỗi thường gặp

### Không đọc được API key

Kiểm tra secret có đúng tên `OPENAI_API_KEY` và đã được bật quyền cho notebook hay chưa. Không sửa code để in key ra kiểm tra.

### Không tải được dataset hoặc embedding model

Kiểm tra Internet của Kaggle. Dataset loader có parquet fallback; embedding có TF-IDF fallback và ghi lại backend.

### Rate limit hoặc lỗi mạng

`complete_json()` retry có giới hạn và tăng thời gian chờ theo số lần thử. Chờ quota khả dụng rồi chạy lại cell; cache/checkpoint sẽ bỏ qua phần đã hoàn thành.

### JSON validation error

Pipeline tự gửi format correction theo `schema_attempts`. Nếu vẫn thất bại, exception dừng cell để tránh âm thầm ghi một record sai.

### Không tạo được ZIP

Cell integrity yêu cầu `baselines.jsonl`, `debate.jsonl` và `ablations.jsonl` đều có dữ liệu. Xem cell nào dừng lỗi, chạy lại cell đó rồi chạy lại evaluation và đóng gói.

### Kaggle hết thời gian phiên

Pilot có hàng nghìn model calls và có thể mất nhiều giờ. Chạy smoke thật trước để kiểm tra key/schema. Với pilot, theo dõi progress log và lưu version/output định kỳ theo khả năng của phiên Kaggle.

## 13. Repository và notebook standalone

Repository vẫn chứa pipeline module hóa trong `src/`, `scripts/`, `configs/` và `tests/`. Cách đó phù hợp khi phát triển local hoặc chạy main experiment lớn. Notebook standalone đóng gói lại các thành phần cốt lõi để thuận tiện chạy trên Kaggle.

Hai cách chạy không nên ghi chung output rồi giả định chúng là cùng một experiment nếu config, sample IDs hoặc phiên bản prompt khác nhau. Luôn lưu `run_manifest.json`, raw JSONL và commit/notebook version tương ứng.

Kiểm thử code repository:

```bash
pytest
```

Sinh lại notebook từ source builder:

```bash
python scripts/build_kaggle_notebook.py
```

## 14. Nguyên tắc trung thực nghiên cứu

- Không điền số liệu giả vào báo cáo.
- Không dùng smoke output làm main result.
- Không gọi pilot 20 mẫu là kết quả toàn benchmark.
- Không đồng nhất consensus score với xác suất đúng.
- Không đồng nhất reasoning diversity với reasoning correctness.
- Không chỉ chọn case study có lợi cho Debate.
- Phải báo cáo trường hợp Majority Voting tốt hơn Debate.
- Phải nêu rõ khi semantic diversity dùng TF-IDF fallback.
- Phải trình bày Accuracy cùng token, latency, CI và số mẫu.
- Chỉ kết luận giả thuyết được hỗ trợ, hỗ trợ một phần hoặc không được hỗ trợ dựa trên output thật.

Notebook tạo dữ liệu và bảng phục vụ Chương 3-4 của báo cáo. Nội dung thảo luận cuối cùng chỉ nên viết sau khi ZIP kết quả đã được kiểm tra đầy đủ.
