# Benchmark & Observability Report — Day 14

**Họ tên:** Trần Việt Tiến
**Ngày chạy:** 25/11/2026, GMT+7
**Môi trường:** Linux x86_64. Docker daemon báo 8 CPU và khoảng 14,9 GiB RAM. Giới hạn mỗi replica production là 0,5 CPU và 256 MiB.

## 1. SLO

| SLI | Mục tiêu | Lý do |
| --- | --- | --- |
| p95 của request thành công | ≤ 500 ms | Phản ánh thời gian chờ ở đuôi phân phối |
| Tỷ lệ response khác 200 | ≤ 2% | Đếm lỗi quan sát được từ client |
| Accuracy trên golden dataset | 100% | Đáp ứng yêu cầu 23/23 và kiểm tra regression |

Alert Prometheus dùng các ngưỡng sự cố riêng trong alert_rules.yml.

## 2. Benchmark hiệu năng

### Exercise 7.1. Đọc metrics

- Counter http_requests_total tích lũy số request.
- Gauge agent_in_flight_requests lên hoặc xuống theo số request đang xử lý.
- Histogram agent_question_length_chars ghi phân bố độ dài câu hỏi hợp lệ. Kiểm tra bằng một request mẫu, sau đó đọc count và sum qua /metrics.

Middleware dùng route template hoặc unmatched để hạn chế số tổ hợp label. Dùng URL thô sẽ sinh thêm time series theo từng URL, tăng CPU và RAM khi nhiều đường dẫn riêng biệt xuất hiện.

### 2.1. Concurrency

Mỗi phép đo dùng 300 request, slow rate 0,03 và error rate bằng 0 để cô lập ảnh hưởng của concurrency.

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Tỷ lệ lỗi | SLO |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.16 | 192.0 | 223.0 | 1692.4 | 0.00% | PASS |
| 10 | 36.6 | 191.6 | 222.4 | 1682.9 | 0.00% | PASS |
| 50 | 101.84 | 203.2 | 376.0 | 1691.7 | 0.00% | PASS |
| 100 | 42.3 | 799.0 | 4764.0 | 5151.0 | 0.00% | FAIL |

RPS cao nhất trong lần đo này ở concurrency 50. Khi tăng lên concurrency 100, RPS giảm và p95 vượt ngưỡng. Kết quả có cả thời gian chờ upstream mô phỏng, xử lý HTTP và chi phí lập lịch của client và server. Một số phép đo local diễn ra khi máy cũng đang build hoặc tải Docker image, nên hạn chế suy rộng từ lần đo này.

### 2.2. Tail latency

Giữ concurrency ở 20, 300 request mỗi lần và error injection bằng 0.

| MOCK_SLOW_RATE | Trung bình ms | p95 ms | p99 ms | SLO |
| --- | --- | --- | --- | --- |
| 0 | 193.6 | 223.6 | 232.3 | PASS |
| 0.03 | 264.6 | 262.8 | 1711.3 | PASS |
| 0.1 | 340.5 | 1695.1 | 1717.6 | FAIL |

p99 phát hiện request chậm ở tỷ lệ injection thấp. p95 tăng rõ khi có đủ request chậm nằm trong 5% cuối. Trung bình pha trộn hai nhóm nên khó diễn đạt trải nghiệm ở đuôi phân phối.

## 3. Benchmark chất lượng

Tắt lỗi và slow injection trong cả ba lần eval. v1 và v2 gốc dùng gate 80%. v2 sau sửa dùng gate 100% và baseline của v2 gốc.

| Chỉ số | v1 | v2 gốc | v2 sau sửa |
| --- | --- | --- | --- |
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Token trung bình/câu | 57.9 | 109.1 | 113.6 |
| p95 ms | 189.0 | 212.3 | 216.2 |
| Tổng chi phí mô phỏng | $0.00041500 | $0.00076200 | $0.00079000 |
| Chi phí/câu đạt | $0.00041475 | $0.00003627 | $0.00003435 |
| Quality gate | FAIL | PASS | PASS |

| ID | Keyword còn thiếu ở v2 gốc | Thay đổi |
| --- | --- | --- |
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu so sánh JWT với API key |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu về các chỉ số đầu vào của HPA |

v2 thêm token ngữ cảnh và bước retrieval nên tăng latency và tổng chi phí. Chi phí trên mỗi câu đạt giảm nhờ nhiều câu vượt ngưỡng keyword. Accuracy phản ánh bộ câu hỏi và cách chấm keyword của lab.

Trong CI, chạy run_eval.py với --min-accuracy 1.0 và --baseline trỏ tới báo cáo chuẩn sau khi app sẵn sàng. Đặt job là required check. Exit code 1 khi accuracy dưới ngưỡng hoặc có regression sẽ làm job fail và chặn merge. Lần chạy cuối quan sát được không có regression.

## 4. Observability stack

### 4.1. Bằng chứng

- [Grafana Golden Signals có tải](screenshots/grafana-dashboard.png)
- [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [Trace lỗi 503 có event exception](screenshots/jaeger-error-trace.png)
- [Hai alert firing đồng thời trong Prometheus](screenshots/prometheus-alert-firing.png)

### 4.2. Fault injection

Promtool trả SUCCESS. Prometheus API được poll mỗi 3 giây, nên thời gian dưới đây là từ thao tác thay đổi tới lần poll đầu thấy firing.

| Thí nghiệm | Alert quan sát | Thời gian | Panel |
| --- | --- | --- | --- |
| A — MOCK_ERROR_RATE=0.2 | AgentHighErrorRate | 97 giây | Error rate |
| D — Pause một replica, giữ A đang chạy | AgentInstanceDown | 39 giây | Instances up |

Ảnh cũng ghi nhận LLMCostBurnRateHigh đang firing từ tải trước đó. Hai thời gian bên trên được đo riêng cho A và D.

Thí nghiệm A khiến mock upstream trả thêm 503. Container bị pause vẫn có mặt trong DNS nhưng scrape không thành công. Lỗi từ reverse proxy có thể thiếu trong metric HTTP do agent tự ghi, nên cần quan sát thêm tầng proxy.

Chuyển về v1 có thể giảm chất lượng dù HTTP vẫn trả 200 và latency ổn. Dùng eval định kỳ theo phiên bản và kiểm tra regression trước khi phát hành.

### 4.3. Trace và log

**Trace chậm** 686bb90bdd57b73ab27535db84bef05f. Tổng 1720.47 ms. Span chat mock-llm-small mất 1696.35 ms, chiếm 98.6% tổng thời gian.

~~~json
{"ts": "2026-11-25T08:17:33.983041+00:00", "level": "INFO", "service": "observable-agent", "instance": "994d23ac9547", "event": "llm_call", "trace_id": "686bb90bdd57b73ab27535db84bef05f", "span_id": "824c9b66694efd05", "request_id": "327275db886a", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 4e-05, "llm_ms": 1695.7}
~~~

**Trace lỗi** d7681049bce643c34921641c7766cfba. Tổng 954.29 ms. Span chat mock-llm-small mất 851.28 ms, chiếm 89.2% tổng thời gian.

~~~json
{"ts": "2026-11-25T08:17:33.136349+00:00", "level": "INFO", "service": "observable-agent", "instance": "994d23ac9547", "event": "llm_error", "trace_id": "d7681049bce643c34921641c7766cfba", "span_id": "03e93909c4b4aa68", "request_id": "a59912104576", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
~~~


## 5. Benchmark scaling

Locust headless, 100 users, ramp-up 10 users/s trong 2 phút mỗi cấu hình. Dùng run --no-deps để Compose không tự áp lại số replica mặc định. Xác minh số container và upstream trước mỗi lần đo. Số liệu lấy từ dòng Aggregated, gồm cả /ask và /health.

| Replica | RPS | p50 ms | p95 ms | p99 ms | Failures |
| --- | --- | --- | --- | --- | --- |
| 1 | 64.38 | 200 | 540 | 1700 | 68 |
| 3 | 65.80 | 190 | 250 | 1700 | 68 |

Khi tăng từ một lên ba replica, RPS đổi từ 64.38 lên 65.80 req/s và p95 đổi từ 540 sang 250 ms. Locust có thời gian nghỉ giữa các request và độ trễ chủ yếu đến từ mô phỏng LLM. Thêm replica không loại bỏ phần chờ trong một request. Hai lần đo độc lập cũng chịu slow/error injection ngẫu nhiên.


## 6. Kết luận

1. Đọc percentile cùng tỷ lệ lỗi để thấy cả đuôi chậm và request thất bại.
2. Accuracy và chi phí trên mỗi câu đạt giúp định lượng trade-off khi thêm retrieval.
3. Dashboard xác định thời điểm có sự cố. Span và log cùng trace ID giúp tìm bước gây chậm hoặc lỗi.

Với production, bổ sung latency và lỗi ở reverse proxy, synthetic check từ bên ngoài, tỷ lệ timeout upstream và quality gate định kỳ trên tập dữ liệu đại diện cho traffic thực tế.
