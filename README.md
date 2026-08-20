# Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning

Mini-research project đánh giá liệu **Multi-Agent Debate (MAD)** có cải thiện độ chính xác và độ tin cậy của suy luận NLP so với **Majority Voting (MV)** khi hai phương pháp sử dụng inference budget tương đương hay không.

Dự án không giả định MAD luôn tốt hơn MV. Kết luận chỉ được đưa ra sau khi so sánh trên dữ liệu API thật, cùng sample ID, cùng seed và cùng ngân sách gọi model.

## 1. Trạng thái hiện tại

Pipeline chính dùng để tạo dữ liệu cho báo cáo là [`KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb`](KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb).

Notebook này là **standalone**: chỉ cần upload một file lên Kaggle, bật Internet, cấu hình Kaggle Secret và chọn **Run All**. Không cần upload repository, prompt, YAML hoặc dataset thủ công.

Cấu hình thực nghiệm báo cáo đang hướng tới:

| Thành phần | Giá trị |
|---|---:|
| Dataset | LogiQA và CommonsenseQA |
| Mẫu mỗi dataset | 25 |
| Tổng câu hỏi độc lập | 50 |
| Seed | 42, 123, 2026 |
| Số dự đoán cho mỗi phương pháp chính | 150 |
| Self-Consistency | K=10 |
| Majority Voting | N=10 |
| Adaptive MAD-v2 | 10 protocol calls |
| Ablation subset | 5 mẫu mỗi dataset |
| Ablation seed | 42 |
| Debate rounds khảo sát | 0, 1, 2, 3 |
| Model mặc định | `gpt-4o-mini` |

50 câu hỏi là quy mô giới hạn chi phí, không đại diện cho toàn bộ benchmark. Báo cáo phải nêu rõ hạn chế về statistical power và khoảng tin cậy.

## 2. Pain Point Nghiên Cứu

### 2.1. Majority Voting không đánh giá bằng chứng

Majority Voting chỉ đếm nhãn đáp án. Nhiều agent có thể cùng mắc một lỗi tương quan, trong khi một agent thiểu số lại có lập luận đúng và bằng chứng tốt hơn.

### 2.2. Nhiều câu trả lời chưa chắc tạo reasoning diversity

Các reasoning trace có thể khác cách diễn đạt nhưng vẫn dùng cùng một chiến lược hoặc shortcut. Vì vậy dự án đo riêng:

- Answer Disagreement Rate.
- Semantic Reasoning Diversity.
- Quan hệ giữa diversity và correctness.

### 2.3. Debate có thể sửa đúng hoặc làm hỏng đáp án

Trao đổi giữa agent có thể phát hiện lỗi, nhưng cũng có thể gây majority pressure, sycophancy, conformity, error propagation và Judge bias. Hệ thống phải đo cả:

- Successful Correction: sai trước debate, đúng sau debate.
- Harmful Revision: đúng trước debate, sai sau debate.
- Resistant Error: sai trước và vẫn sai sau debate.
- Minority-Correct Case: agent thiểu số đúng nhưng quyết định cuối có chọn được hay không.

### 2.4. So sánh không công bằng về compute

Không thể quy lợi ích cho debate nếu MAD dùng nhiều call hơn đáng kể. So sánh chính dùng:

```text
Self-Consistency K=10
Majority Voting N=10
Adaptive MAD-v2 B=10 protocol calls
```

Single Direct và Single CoT vẫn được giữ làm baseline tham chiếu một call, nhưng không được xem là fair-compute đối chứng trực tiếp của MAD.

### 2.5. Output API có thể sai JSON hoặc bị cắt

JSON mode không bảo đảm response hoàn tất nếu output chạm giới hạn token. Pipeline dùng Pydantic, schema retry, response cache và checkpoint JSONL. Một record chỉ được ghi sau khi toàn bộ method hoàn thành hợp lệ.

## 3. Câu Hỏi Nghiên Cứu

| Mã | Câu hỏi | Thí nghiệm | Chỉ số chính |
|---|---|---|---|
| RQ1 | MAD có tạo reasoning diversity cao hơn SC và MV không? | So sánh reasoning trace của các phương pháp | Disagreement, Semantic Diversity |
| RQ2 | MAD có tốt hơn MV khi cùng inference budget không? | SC-10, MV-10 và MAD-10 | Accuracy, token, latency, Accuracy/1.000 token |
| RQ3 | Số vòng debate ảnh hưởng thế nào? | Rounds 0, 1, 2, 3 | Accuracy, correction, degradation, cost |
| RQ4 | Role specialization có lợi không? | Homogeneous, specialized và remove-one-role | Accuracy, behavior, cost |
| RQ5 | MAD thất bại trong trường hợp nào? | Behavioral và error analysis | Correction, degradation, resistant error, Judge error |

## 4. Phương Pháp MAD-v2

### 4.1. Luồng chính

```text
Input Question
      |
      v
6 Independent Solver Responses
      |
      v
Majority Answer + Consensus Gate
      |
      +-------------------------------+
      |                               |
Consensus >= 5/6                Consensus < 5/6
      |                               |
4 Solver bổ sung                Critic
      |                               |
Majority Voting N=10            Evidence Checker
                                      |
                                  Revision
                                      |
                                  Blind Judge
                                      |
                              Change Authorization Gate
      |                               |
      +---------------+---------------+
                      |
                      v
            Final Answer + Raw JSONL
```

Hai nhánh đều có đúng 10 `protocol_calls`:

- Nhánh đồng thuận mạnh: 6 Solver ban đầu + 4 Solver bổ sung.
- Nhánh bất đồng: 6 Solver ban đầu + Critic + Evidence Checker + Revision + Judge.

### 4.2. Evidence-gated revision

MAD-v2 mặc định bảo lưu majority answer ban đầu. Một đáp án mới chỉ được chấp nhận khi đồng thời thỏa các điều kiện:

1. Judge đề xuất đáp án khác initial answer.
2. Revision chọn cùng đáp án với Judge.
3. Evidence Checker đặt `change_supported=true`.
4. `recommended_answer` của Evidence Checker trùng đáp án mới.
5. `support_level >= 0.75`.
6. Có ít nhất một claim `SUPPORTED`.
7. Critic phát hiện ít nhất một issue mức `HIGH`.

Nếu thiếu bất kỳ điều kiện nào, hệ thống giữ initial majority answer. Cơ chế này giảm harmful revision nhưng có thể bỏ lỡ một minority-correct case, nên không được xem là bảo đảm MAD tốt hơn MV.

### 4.3. Các role

| Role | Trách nhiệm |
|---|---|
| Solver | Chọn answer, viết rationale ngắn, evidence và confidence |
| Critic | Tìm lỗi logic, premise thiếu và giả định không có căn cứ |
| Skeptic | Tìm phản ví dụ và cách hiểu thay thế trong fixed-round ablation |
| Evidence Checker | Đối chiếu claim với đề bài và quyết định bằng chứng có đủ để đổi answer hay không |
| Revision | Mặc định bảo lưu answer, chỉ sửa khi có bằng chứng cụ thể |
| Blind Judge | So sánh candidate ẩn danh, không nhận gold answer |

Trong adaptive MAD-v2 chính, chức năng skeptical được gộp vào Critic để giữ ngân sách 10 calls. Skeptic độc lập vẫn xuất hiện trong fixed-round ablation.

## 5. Các Phương Pháp Được So Sánh

| Method trong output | Calls/mẫu | Ý nghĩa |
|---|---:|---|
| `single_direct_v2` | 1 | Trả lời trực tiếp, không rationale dài |
| `single_cot_v2` | 1 | Một Solver với structured rationale |
| `self_consistency_k10_v2` | 10 | Mười reasoning path, chọn majority answer |
| `majority_voting_n10_v2` | 10 | Mười Solver độc lập, không giao tiếp |
| `adaptive_mad_v2_max10` | 10 | MAD-v2 thích nghi với consensus gate và evidence gate |

Ablation gồm bốn nhóm:

- Rounds: 0, 1, 2, 3.
- Role specialization: homogeneous và specialized.
- Remove-one-role: full, no Critic, no Skeptic, no Evidence Checker, no Judge.
- Decision protocol: majority, judge và evidence-aware judge.

Ablation chỉ chạy trên 10 câu hỏi và một seed. Không gộp kết quả ablation với main holdout.

## 6. Cấu Hình Trước Khi Chạy Kaggle

Trong cell cấu hình của notebook, kiểm tra các trường sau:

```python
RUN_MODE = "report"

CFG = {
    # Các trường khác giữ nguyên.
    "sample_size_per_dataset": 25,
    "seeds": [42, 123, 2026],
    "fair_compute_k": 10,
    "initial_pool_size": 6,
    "schema_attempts": 4,
    "max_output_tokens": {
        "direct": 180,
        "solver": 600,
        "critic": 500,
        "skeptic": 500,
        "evidence_checker": 600,
        "revision": 600,
        "judge": 350,
    },
    "resume": True,
    "overwrite": False,
    "output_dir": "/kaggle/working/mad_v2_report_25x2_real",
}
```

Đây là phần minh họa các trường cần kiểm tra, không phải dictionary đầy đủ để thay nguyên cell. Giữ lại các trường dataset, temperature, threshold, ablation và embedding đang có trong notebook.

Nên giới hạn prompt Solver và Revision:

```text
Tối đa 3 mục rationale_summary và 3 evidence.
Mỗi mục không quá 25 từ.
```

Tăng `max_output_tokens` chỉ tăng giới hạn tối đa. API tính theo token thực tế sinh ra, nhưng response dài hơn vẫn có thể làm tăng chi phí và latency.

Không đổi model, prompt, token limit, threshold hoặc sample size giữa một run đang chạy. Các trường này tham gia cache key và có thể làm mất khả năng tái sử dụng response cũ.

## 7. Chạy Trên Kaggle

### Bước 1: Upload notebook

Tạo Kaggle Notebook và import [`KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb`](KAGGLE_MAD_V2_REPORT_EXPERIMENT.ipynb).

Không dùng `KAGGLE_PILOT_PIPELINE.ipynb` để tạo kết quả chính của báo cáo.

### Bước 2: Bật Internet

Trong **Notebook settings**, bật **Internet**. Internet cần để cài package, tải dataset/embedding model và gọi OpenAI API.

### Bước 3: Tạo Kaggle Secret

Trong **Add-ons > Secrets**, tạo:

```text
Name: OPENAI_API_KEY
Value: <API key của bạn>
```

Bật quyền truy cập secret cho notebook. Không ghi API key trực tiếp vào code, output, log, ảnh chụp hoặc Git. Nếu một key từng bị công khai, phải thu hồi key cũ và tạo key mới.

### Bước 4: Chạy smoke trước

Đặt:

```python
RUN_MODE = "smoke"
```

Chọn **Run All** để kiểm tra package, dataset, API, JSON schema và ZIP output. Smoke vẫn gọi API thật nhưng chỉ dùng một mẫu mỗi dataset, một seed và ablation tối thiểu. Không dùng smoke làm kết quả nghiên cứu.

### Bước 5: Chạy report

Sau khi smoke hoàn tất, đổi lại:

```python
RUN_MODE = "report"
```

Kiểm tra cấu hình 25 mẫu mỗi dataset và dùng output directory mới. Sau đó chọn **Restart Session and Run All**.

### Bước 6: Theo dõi các stage

```text
Dataset preparation
      -> Baselines
      -> Adaptive MAD-v2
      -> Ablations
      -> Evaluation
      -> Integrity check
      -> Final ZIP
```

Checkpoint ZIP được tạo sau baseline, MAD và ablation. Tải checkpoint sau mỗi stage dài hoặc dùng **Save Version** để tránh mất dữ liệu khi Kaggle kết thúc session.

## 8. Quy Mô Run 25+25 Mẫu

| Stage | Cách tính | Prediction records |
|---|---:|---:|
| Baseline | 50 câu × 3 seed × 4 method | 600 |
| Adaptive MAD-v2 | 50 câu × 3 seed | 150 |
| Ablation | 10 câu × 1 seed × 14 cấu hình | 140 |
| **Tổng** | | **890** |

Số `protocol_calls` danh nghĩa trước retry:

| Stage | Protocol calls |
|---|---:|
| Baseline | 3.300 |
| Adaptive MAD-v2 | 1.500 |
| Ablation | khoảng 1.440 |
| **Tổng** | **khoảng 6.240** |

Số request API thực tế có thể thấp hơn vì MV và MAD dùng chung Solver response qua cache. Schema retry có thể làm số model call và token tăng. Luôn đọc chi phí thật từ output thay vì suy ra chỉ từ giới hạn token.

## 9. Ý Nghĩa Từng Cell

| Cell | Chức năng |
|---:|---|
| 0 | Mô tả phạm vi và nguyên tắc trung thực nghiên cứu |
| 1 | Cài dependency |
| 2 | Import thư viện và đọc `OPENAI_API_KEY` từ Kaggle Secret |
| 3 | Cấu hình, khóa holdout và tạo `run_manifest.json` |
| 4 | Pydantic schema, prompt, OpenAI client, retry và response cache |
| 5 | Tải, chuẩn hóa và khóa sample ID |
| 6 | Baseline, adaptive MAD-v2, fixed-round ablation và checkpoint helpers |
| 7 | Chạy bốn baseline |
| 8 | Chạy Adaptive MAD-v2 |
| 9 | Chạy targeted ablations |
| 10 | Tính metric, kiểm định, behavioral analysis và sinh bảng/hình |
| 11 | Integrity check và đóng gói ZIP |
| 12 | Ghi chú cách sử dụng output |

### Cell baseline

Mỗi record có khóa `(seed, sample_id, method)`. Khi `resume=True`, record đã hoàn thành được bỏ qua. Một method chỉ được append sau khi tất cả model call của method đó hợp lệ.

### Cell Adaptive MAD-v2

MAD đọc lại shared Solver responses từ cache của Majority Voting khi cache key giống nhau. Record lưu `route`, `initial_answer`, `initial_consensus`, `proposed_answer`, `change_authorized`, token và latency.

### Cell evaluation

Cell này không gọi OpenAI API. Nó tạo:

- Accuracy, bootstrap 95% CI và mean/std qua seed.
- Token, protocol/model/schema-retry calls và latency.
- Brier Score và Expected Calibration Error.
- Semantic Reasoning Diversity và Answer Disagreement.
- Correction Rate và Degradation Rate.
- Paired MAD-vs-MV, McNemar và win/loss/tie.
- Behavioral cases và file chờ manual error annotation.

## 10. Output Quan Trọng

```text
mad_v2_report_25x2_real/
├── run_manifest.json
├── raw/
│   ├── response_cache.jsonl
│   ├── baselines_v2.jsonl
│   ├── adaptive_mad_v2.jsonl
│   └── ablations_v2.jsonl
├── processed/
│   ├── samples.jsonl
│   ├── sample_ids.json
│   ├── predictions_v2.csv
│   ├── behavioral_cases_v2.jsonl
│   ├── error_cases_for_manual_annotation_v2.csv
│   └── embedding_metadata.json
├── tables/
│   ├── main_results_v2.csv
│   ├── ablation_results_v2.csv
│   ├── paired_mad_vs_mv.csv
│   ├── reasoning_diversity_v2.csv
│   ├── answer_disagreement_v2.csv
│   └── correction_degradation_v2.csv
├── figures/
│   └── accuracy_v2_<dataset>.png
└── integrity_summary.json
```

| Nội dung | File nguồn |
|---|---|
| Kết quả phương pháp chính | `tables/main_results_v2.csv` |
| Fair-compute MAD-vs-MV | `tables/paired_mad_vs_mv.csv` |
| Ablation | `tables/ablation_results_v2.csv` |
| Reasoning diversity | `tables/reasoning_diversity_v2.csv` |
| Answer disagreement | `tables/answer_disagreement_v2.csv` |
| Correction/Degradation | `tables/correction_degradation_v2.csv` |
| Behavioral analysis | `processed/behavioral_cases_v2.jsonl` |
| Manual error analysis | `processed/error_cases_for_manual_annotation_v2.csv` |
| Kiểm tra tính đầy đủ | `integrity_summary.json` |

Chỉ sử dụng output khi integrity check hoàn tất. Không điền số liệu vào báo cáo từ progress log hoặc một stage chưa đủ record.

## 11. Resume Và Checkpoint

Giữ cấu hình:

```python
"resume": True,
"overwrite": False,
```

Nếu cell dừng giữa chừng, chạy lại chính cell đó. Notebook đọc JSONL và bỏ qua các khóa đã hoàn thành.

Resume chỉ hoạt động khi thư mục output cũ vẫn tồn tại. `/kaggle/working` có thể bị xóa khi session kết thúc, vì vậy cần tải checkpoint ZIP hoặc Save Version.

Không dùng cùng output directory cho hai cấu hình sample size khác nhau. Ví dụ, kết quả 100 câu hỏi và 50 câu hỏi phải nằm trong hai thư mục riêng.

## 12. Xử Lý Lỗi Thường Gặp

### 12.1. `Invalid solver output after schema retry`

Ví dụ:

```text
Expecting ',' delimiter
```

Đây là JSON sai cú pháp, thường do output bị cắt khi chạm token limit. Với một run mới, kiểm tra:

```python
CFG["schema_attempts"] = 4
CFG["max_output_tokens"]["solver"] = 600
CFG["max_output_tokens"]["revision"] = 600
```

Giữ rationale/evidence ngắn trong prompt. Sau đó chạy lại cell bị lỗi; checkpoint sẽ bỏ qua method đã hoàn thành.

Không đổi token limit giữa một run lớn đang chạy nếu vẫn cần tái sử dụng cache cũ, vì token limit tham gia cache key.

### 12.2. Integrity báo `(599, 1200)`

Điều này có nghĩa baseline chỉ có 599 record trong khi cấu hình cũ yêu cầu 1.200. Integrity check không phải nguyên nhân; nó chỉ phát hiện stage baseline chưa hoàn tất.

Với thiết kế mới 25+25 mẫu, baseline hợp lệ phải có:

```text
50 × 3 × 4 = 600 records
```

Không được coi 599 record của thiết kế 100 câu hỏi là 599/600 của thiết kế 50 câu hỏi. Hai run có tập sample khác nhau và phải dùng output directory khác nhau.

### 12.3. Đổi sample size nhưng vẫn thấy 100 mẫu

Khi `resume=True`, cell dataset có thể đọc lại `processed/samples.jsonl` cũ. Cách an toàn là đặt `output_dir` mới và chạy lại từ đầu.

### 12.4. Rate limit hoặc lỗi mạng

API client retry với backoff hữu hạn. Khi quota khả dụng trở lại, chạy lại cell đang dừng. Không xóa JSONL đã hoàn thành.

### 12.5. Không tải được dataset hoặc embedding

Kiểm tra Internet. Dataset loader có parquet fallback. Nếu sentence-transformers không tải được, evaluation có thể dùng TF-IDF fallback và phải ghi rõ backend trong báo cáo.

### 12.6. Integrity không tạo ZIP

Kiểm tra lần lượt số record của baseline, MAD và ablation. Chỉ chạy lại evaluation/integrity sau khi ba raw JSONL đã đủ.

## 13. Chạy Repository Cục Bộ

Notebook Kaggle là pipeline báo cáo độc lập. Repository vẫn có implementation module hóa để phát triển và kiểm thử.

```bash
python -m venv .venv
```

Kích hoạt trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Cài dependency:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Tạo `.env` từ `.env.example` và đặt API key cục bộ. `.env` đã được bỏ qua bởi Git và không được commit.

Chạy test:

```bash
pytest -q
```

Sinh lại notebook:

```bash
python scripts/build_kaggle_mad_v2.py
python scripts/build_kaggle_report_experiment.py
```

Workflow module hóa và từng câu lệnh chi tiết được giải thích trong [`GUIDE.md`](GUIDE.md).

## 14. Báo Cáo

Bản Word hiện tại: [`report/Bao_cao_Multi_Agent_Debate_Chuong_1_2.docx`](report/Bao_cao_Multi_Agent_Debate_Chuong_1_2.docx).

Chương 1 và Chương 2 trình bày cơ sở lý thuyết và phương pháp. Chương 3-4 chỉ nên hoàn thiện sau khi ZIP kết quả thật vượt qua integrity check.

Khi chuyển sang cấu hình 25 mẫu mỗi dataset, báo cáo phải ghi:

- 50 câu hỏi độc lập, gồm 25 LogiQA và 25 CommonsenseQA.
- 150 prediction cho mỗi phương pháp chính do lặp ba seed.
- Ablation trên 10 câu hỏi và một seed.
- Cỡ mẫu nhỏ là một threat to validity.
- Không tuyên bố quan hệ nhân quả từ chênh lệch quan sát được.

## 15. Nguyên Tắc Trung Thực Nghiên Cứu

- Không tạo hoặc điền số liệu giả.
- Không dùng smoke output làm kết quả chính.
- Không điều chỉnh prompt hoặc threshold sau khi xem holdout rồi che giấu thay đổi.
- Không đồng nhất consensus score với xác suất đúng.
- Không đồng nhất reasoning diversity với correctness.
- Không chỉ chọn case study có lợi cho MAD.
- Phải báo cáo trường hợp MV tốt hơn MAD.
- Phải báo cáo token, latency, confidence interval và số câu hỏi độc lập cùng Accuracy.
- Mỗi hypothesis phải được phân loại là được hỗ trợ, được hỗ trợ một phần hoặc không được hỗ trợ dựa trên dữ liệu thật.
- Nếu lợi thế MAD biến mất sau khi kiểm soát compute, báo cáo phải nói rõ điều đó.

Mục tiêu của dự án là kiểm tra MAD một cách có thể bác bỏ và tái lập, không phải thiết kế một thí nghiệm buộc MAD phải thắng Majority Voting.
