# Beyond Majority Voting: Multi-Agent Debate for Reliable NLP Reasoning

**Ngôn ngữ báo cáo:** Tiếng Việt  
**Chuẩn trích dẫn:** IEEE  
**Trạng thái thực nghiệm:** pipeline đã hỗ trợ dry-run/mock; kết quả chính chỉ được kết luận sau khi chạy model thật từ `outputs/raw/*.jsonl`.

## Mở Đầu

Các mô hình ngôn ngữ lớn đạt kết quả mạnh trên nhiều bài toán NLP reasoning, nhưng độ tin cậy của câu trả lời vẫn là vấn đề mở. Một câu trả lời có thể đúng vì mô hình suy luận tốt, vì may mắn trong lựa chọn đáp án, hoặc vì tín hiệu bề mặt trong lựa chọn trắc nghiệm. Majority Voting và Self-Consistency thường được dùng để giảm phương sai bằng cách lấy nhiều mẫu độc lập rồi chọn đáp án phổ biến. Multi-Agent Debate đi xa hơn: nhiều agent không chỉ trả lời độc lập mà còn phản biện, kiểm tra bằng chứng và sửa đáp án qua nhiều vòng.

Bài toán nghiên cứu của dự án này là đánh giá liệu Multi-Agent Debate có thực sự cải thiện độ tin cậy của NLP reasoning so với Majority Voting hay không. Nghiên cứu không giả định debate luôn tốt hơn. Ngược lại, thiết kế thực nghiệm buộc hệ thống báo cáo cả trường hợp debate sửa lỗi, không sửa lỗi, hoặc làm hỏng đáp án đúng ban đầu.

Mục tiêu nghiên cứu gồm ba trọng tâm. Thứ nhất, đo reasoning diversity: các agent có tạo khác biệt ngữ nghĩa và chiến lược giải thật sự hay chỉ diễn đạt khác nhau. Thứ hai, đánh giá hiệu quả khi kiểm soát inference budget theo số model call và token budget. Thứ ba, kiểm tra role specialization: Solver, Critic, Skeptic, Evidence Checker và Judge có đem lại lợi ích so với các agent đồng nhất hay không.

Các Research Questions:

- RQ1: Multi-Agent Debate có tạo reasoning diversity cao hơn Self-Consistency và Multi-Agent Majority Voting không?
- RQ2: Khi ngân sách suy luận tương đương, Debate có cải thiện Accuracy và reliability so với Majority Voting không?
- RQ3: Số vòng debate ảnh hưởng thế nào đến Accuracy, Correction Rate, Degradation Rate, Token Cost và Latency?
- RQ4: Role specialization có hiệu quả hơn homogeneous agents không?
- RQ5: Failure modes nào khiến debate sửa đúng, không sửa được lỗi, hoặc làm đáp án đúng thành sai?

Các giả thuyết được khóa trước thực nghiệm:

- H1: Diversity(MAD) > Diversity(Majority Voting).
- H2: Accuracy(MAD) > Accuracy(Majority Voting), đặc biệt ở mẫu có bất đồng ban đầu cao.
- H3: Performance(Specialized) > Performance(Homogeneous).
- H4: Accuracy không tăng tuyến tính theo số vòng debate; token cost và latency tiếp tục tăng.
- H5: Debate sửa được một phần lỗi nhưng có degradation do majority pressure, sycophancy, error propagation và Judge bias.

Đóng góp chính của dự án là một benchmark mini-research tái lập được, gồm source code, prompts, raw logging, fair-compute comparison, ablation study, behavioral analysis và error analysis.

## Chương 1. Tổng Quan Và Cơ Sở Lý Thuyết

### 1.1. Large Language Models Và NLP Reasoning

NLP reasoning yêu cầu mô hình không chỉ khớp mẫu ngôn ngữ mà còn kết nối dữ kiện, loại trừ lựa chọn sai, xử lý commonsense hoặc suy luận logic. LogiQA được xây dựng để kiểm tra machine reading comprehension với logical reasoning từ các câu hỏi chuyên gia [1]. CommonsenseQA kiểm tra khả năng dùng tri thức thường thức để phân biệt các lựa chọn gần nhau [2]. Hai benchmark này bổ sung nhau: một bên nhấn mạnh lập luận logic dựa trên premise, bên kia nhấn mạnh commonsense QA.

### 1.2. Chain-of-Thought Và Self-Consistency

Chain-of-Thought prompting khuyến khích mô hình sinh các bước giải trung gian có thể quan sát được [5]. Self-Consistency lấy nhiều reasoning paths độc lập và chọn đáp án xuất hiện thường xuyên nhất [3]. Điểm mạnh của Self-Consistency là đơn giản và thường cải thiện độ chính xác. Điểm yếu là các reasoning path không giao tiếp với nhau; nếu nhiều path mắc cùng lỗi tương quan, Majority Voting có thể củng cố sai lầm.

### 1.3. Hệ Thống Đa Tác Tử Sử Dụng LLM

Hệ đa tác tử dùng nhiều lời gọi mô hình với vai trò hoặc prompt khác nhau. Mỗi agent có thể đóng vai trò solver, critic, verifier hoặc judge. Lợi ích kỳ vọng là phân tách trách nhiệm nhận thức: một agent giải, agent khác tìm lỗi, agent khác kiểm tra evidence. Tuy nhiên, nếu tất cả agent dùng cùng model và cùng prior, lỗi có thể vẫn tương quan.

### 1.4. Majority Voting

Majority Voting chọn đáp án có nhiều phiếu nhất. Với $K$ output độc lập:

$$
\hat{y}
= 
\arg\max_y
\sum_{i=1}^{K}
\mathbf{1}(y_i = y)
$$

Phương pháp này không xem xét chất lượng reasoning, mức evidence support, hoặc khả năng thiểu số đúng. Vì vậy, trong các minority-correct case, voting có thể thua Judge nếu Judge nhận ra lập luận tốt hơn.

### 1.5. Multi-Agent Debate

Multi-Agent Debate cho phép nhiều mô hình đề xuất và tranh luận câu trả lời qua nhiều vòng [4]. Protocol debate có thể cải thiện factuality và reasoning, nhưng cũng có nguy cơ tạo áp lực đồng thuận, lan truyền lỗi hoặc khiến Judge thiên vị câu trả lời dài hơn. Nghiên cứu này tách hai yếu tố: communication protocol và decision protocol bằng cách so sánh Debate + Majority Voting với Debate + Judge.

### 1.6. Độ Tin Cậy Trong NLP Reasoning

Độ tin cậy không chỉ là Accuracy. Một hệ thống đáng tin cần có chi phí đo được, confidence được calibration, khả năng sửa lỗi, và minh bạch về failure modes. Do đó, nghiên cứu đo thêm Correction Rate, Degradation Rate, Semantic Reasoning Diversity, Token Cost, Latency, Brier Score và Expected Calibration Error.

### 1.7. Các Công Trình Liên Quan

Các hướng liên quan gồm Chain-of-Thought [5], Self-Consistency [3], Multi-Agent Debate [4], Self-Refine [11], Reflexion [12], StrategyQA [7], GSM8K [6], TruthfulQA [10], bootstrap confidence interval [15] và McNemar test [14].

### 1.8. Khoảng Trống Nghiên Cứu

Nhiều nghiên cứu báo cáo lợi ích của debate nhưng chưa luôn kiểm soát fair compute. Nếu debate dùng nhiều lời gọi model hơn baseline, lợi thế accuracy có thể đến từ ngân sách lớn hơn thay vì protocol tốt hơn. Ngoài ra, diversity thường bị đo bằng khác biệt đáp án, trong khi khác biệt reasoning trace và chiến lược giải cũng quan trọng.

## Chương 2. Phương Pháp Multi-Agent Debate Đề Xuất

### 2.1. Phát Biểu Bài Toán

Với mỗi mẫu $x$ gồm context, question và tập lựa chọn $C$, hệ thống cần dự đoán đáp án $\hat{y} \in C$. Mục tiêu là tối đa hóa accuracy trong khi báo cáo chi phí và độ tin cậy.

$$
\text{Accuracy}
=
\frac{\text{Number of correct predictions}}
{\text{Total number of predictions}}
$$

### 2.2. Kiến Trúc Tổng Thể

Luồng xử lý:

```text
Input Question
-> Independent Solver Responses
-> Disagreement Detection
-> Critic
-> Skeptic
-> Evidence Checker
-> Solver Revision
-> Repeat by Debate Rounds
-> Judge or Majority Aggregator
-> Final Answer
-> Metrics and Logging
```

### 2.3. Thiết Kế Role

Solver sinh đáp án ban đầu, rationale_summary ngắn, evidence và confidence. Critic kiểm tra lỗi logic và thiếu evidence. Skeptic tìm phản ví dụ và cách hiểu khác. Evidence Checker gắn nhãn claim theo SUPPORTED, UNSUPPORTED, CONTRADICTED hoặc UNCERTAIN. Judge đánh giá reasoning quality và evidence support, không chỉ đếm phiếu.

### 2.4. Debate Protocol

Ở vòng 0, $N$ solver trả lời độc lập. Ở mỗi vòng $r > 0$, Critic/Skeptic/Evidence Checker đọc trạng thái debate, sau đó Solver sửa đáp án. Protocol lưu tất cả raw JSON để phân tích lại mà không gọi API.

### 2.5. Decision Protocol

Ba decision protocol được hỗ trợ:

- Debate + Majority Voting.
- Debate + Judge.
- Debate + Evidence-Aware Judge.

Judge nhận danh sách câu trả lời đã xáo trộn và ẩn nhãn agent để giảm identity bias.

### 2.6. JSON Contract

Mọi agent phải trả JSON hợp lệ và được kiểm tra bằng Pydantic. Nếu model trả JSON lỗi, client có thể mở rộng retry. Các schema chính nằm ở `src/schemas/agent_outputs.py`.

### 2.7. Chi Phí Tính Toán

Token cost được ghi riêng input/output/total. Với $N$ solver, $R$ vòng, và $A_r$ role phản biện mỗi vòng, số lời gọi xấp xỉ:

$$
\text{Calls}
=
N
+
R(N + A_r)
+
\mathbf{1}_{\text{Judge}}
$$

Fair-compute comparison so sánh Self-Consistency với Debate theo số call hoặc token budget tương đương.

### 2.8. Cơ Chế Hạn Chế Failure Mode

Các cơ chế gồm blind judge, evidence labels, role-specific prompts, bounded confidence, raw logs và phân tích harmful revision. Hệ thống không coi consensus là xác suất đúng.

## Chương 3. Thiết Kế Thực Nghiệm Và Đánh Giá

### 3.1. Dataset

Dataset 1 là LogiQA, gồm 8.678 câu hỏi logical reasoning từ nguồn expert-written [1]. Dataset 2 là CommonsenseQA, gồm khoảng 12 nghìn câu hỏi multiple-choice commonsense QA [2]. Subset được chọn bằng seed khóa trong `outputs/processed/sample_ids.json`. Prompt development phải thực hiện trên development set; test subset được khóa trước khi đánh giá cuối cùng.

### 3.2. Mô Hình

Model provider đọc từ biến môi trường, model name đọc từ YAML. Mặc định cấu hình dùng `gpt-4o-mini`, nhưng code không hard-code key hoặc provider. API key chỉ đọc từ `OPENAI_API_KEY`.

### 3.3. Baseline

- B1 Single Agent Direct Answer.
- B2 Single Agent with structured rationale.
- B3 Self-Consistency với $K$ configurable.
- B4 Multi-Agent Majority Voting.

### 3.4. Main Experiment

Main experiment chạy 2 dataset, 200-300 mẫu/dataset nếu giới hạn chi phí, 3 seed: 42, 123, 2026. Các round khảo sát là 0, 1, 2, 3.

### 3.5. Fair-Compute Comparison

Fair-compute được báo cáo theo:

- Accuracy không kiểm soát chi phí.
- Accuracy match số model call.
- Accuracy match token budget.
- Accuracy trên mỗi 1.000 token.
- Token tăng thêm để đạt thêm 1% Accuracy.

Nếu lợi thế của debate biến mất sau kiểm soát chi phí, kết luận phải nói rõ.

### 3.6. Ablation Study

Ablation gồm:

- A1 Rounds = 0, 1, 2, 3.
- A2 Homogeneous vs Specialized.
- A3 Remove-one-role: no Critic, no Skeptic, no Evidence Checker, no Judge.
- A4 Decision Protocol: Majority, Judge, Evidence-Aware Judge.
- A5 Number of Agents: 2, 3, 5.

### 3.7. Metrics

Correction Rate:

$$
\text{Correction Rate}
=
\frac{\text{Wrong before debate but correct after debate}}
{\text{Wrong before debate}}
$$

Degradation Rate:

$$
\text{Degradation Rate}
=
\frac{\text{Correct before debate but wrong after debate}}
{\text{Correct before debate}}
$$

Semantic Diversity:

$$
\text{Semantic Diversity}
=
1
-
\text{mean pairwise cosine similarity}
$$

Calibration dùng Brier Score và Expected Calibration Error. Statistical analysis dùng bootstrap 95% CI và McNemar test.

### 3.8. Behavioral Và Error Analysis

Behavioral classes gồm Successful Correction, Resistant Error, Harmful Revision, Productive Disagreement và Minority-Correct Case. Error taxonomy gồm LOGICAL_ERROR, MISINTERPRETATION, MISSING_EVIDENCE, UNSUPPORTED_ASSUMPTION, ARITHMETIC_ERROR, HALLUCINATION, CONFORMITY_ERROR, JUDGE_ERROR, ANSWER_EXTRACTION_ERROR, CONTEXT_OVERLOAD.

### 3.9. Reproducibility

Tất cả config nằm trong YAML. Sample IDs được khóa. Raw outputs lưu JSONL. Cache response cho phép evaluate lại không gọi API. Scripts CLI tái tạo toàn bộ pipeline.

## Chương 4. Kết Quả Và Thảo Luận

### 4.1. Trạng Thái Kết Quả

Tại thời điểm tạo báo cáo này, main experiment thật chưa được chạy trong lượt hiện tại để tránh phát sinh chi phí API lớn. Vì vậy, báo cáo chưa đưa ra kết luận thực nghiệm định lượng. Sau khi chạy workflow thật, bảng tự động được sinh ở `outputs/tables/main_results.csv` và có thể chèn vào phần này bằng `report/generated_tables.md`.

### 4.2. Bảng Kết Quả Tổng Thể

Xem `report/generated_tables.md` sau khi chạy:

```bash
python scripts/evaluate.py --config configs/experiment.yaml
python scripts/generate_report_tables.py --config configs/experiment.yaml
```

Không diễn giải bảng dry-run như kết quả khoa học.

### 4.3. So Sánh Baseline

Phân tích cần báo cáo Accuracy trung bình và độ lệch chuẩn qua 3 seed cho B1-B4. Self-Consistency và Multi-Agent Majority Voting phải được so sánh với số call rõ ràng.

### 4.4. Fair-Compute Results

Phần này kiểm tra liệu MAD còn lợi thế khi số model call hoặc token budget tương đương. Nếu không, giả thuyết H2 chỉ được hỗ trợ trong bối cảnh không kiểm soát chi phí hoặc không được hỗ trợ.

### 4.5. Ablation

Round ablation cần cho thấy đường cong accuracy/cost. Kỳ vọng của H4 là accuracy bão hòa hoặc giảm sau một ngưỡng, nhưng kết luận chỉ được đưa ra từ số liệu thật.

### 4.6. Reasoning Diversity Analysis

Semantic diversity được tính bằng TF-IDF cosine trong bản offline mặc định. Nếu dùng embedding model thật, cần ghi rõ model embedding tách biệt với model sinh đáp án. Diversity cao không được đồng nhất với correctness.

### 4.7. Cost-Performance Analysis

Chi phí được đọc từ usage của API hoặc ước lượng mock trong dry-run. Các báo cáo chính cần tách input tokens, output tokens, total tokens, latency trung bình, median và P95.

### 4.8. Calibration

Self-reported confidence của model, consensus score và Judge confidence là ba đại lượng khác nhau. Brier Score và ECE được báo cáo để đánh giá calibration.

### 4.9. Behavioral Analysis

Mỗi nhóm hành vi cần chọn case study tiêu biểu từ `outputs/tables/behavioral_transitions.csv`. Cần trình bày câu hỏi, gold answer, đáp án ban đầu, phản biện, đáp án sau revision, quyết định Judge và nhận xét.

### 4.10. Error Analysis

Thống kê lỗi được sinh từ critique outputs trong `outputs/tables/error_taxonomy_counts.csv`. Cần phân tích cả trường hợp Majority Voting tốt hơn MAD.

### 4.11. Trả Lời RQ Và Kiểm Định Hypotheses

Phần này chỉ hoàn thiện sau main experiment thật. Mỗi hypothesis phải được gán một trong ba nhãn: được hỗ trợ, được hỗ trợ một phần, hoặc không được hỗ trợ.

### 4.12. Threats To Validity

Các nguy cơ gồm model-specific bias, prompt sensitivity, correlated errors giữa agent cùng model, Judge bias, subset size nhỏ, token budget không hoàn toàn tương đương và việc dùng rationale_summary thay cho hidden reasoning.

## Kết Luận Và Hướng Phát Triển

Dự án đã triển khai một framework tái lập để kiểm tra Multi-Agent Debate vượt ra ngoài Majority Voting. Kết luận khoa học cuối cùng cần dựa trên raw outputs thật. Hướng phát triển gồm thêm embedding diversity bằng model cố định, chạy thêm GSM8K, dùng human annotation cho error taxonomy, và so sánh nhiều model provider.

## Tài Liệu Tham Khảo

Tài liệu tham khảo BibTeX nằm trong `report/references.bib`. Các trích dẫn chính gồm LogiQA [1], CommonsenseQA [2], Self-Consistency [3], Multi-Agent Debate [4] và Chain-of-Thought [5].
