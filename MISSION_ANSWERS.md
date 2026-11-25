# Mission Answers — Day 14

## Part 1 — Localhost vs Production

### Exercise 1.1–1.2

Bản develop có API key và URL database giả lập ghi trực tiếp trong source, bật debug, dùng `print` để ghi câu hỏi và cả key, cố định host/port, bật reload và thiếu health probe. Nếu áp dụng các thói quen này với secret thật, log có thể làm lộ credential. Host loopback cũng khiến dịch vụ khó truy cập từ bên ngoài container.

Thử với FastAPI TestClient. Bản develop trả `200` cho `POST /ask?question=What+is+Docker%3F` và `404` cho `GET /health`. Bản production trả `200` trên `/health`, `/ready` và `/metrics` ở lần chạy local.

### Exercise 1.3

| Hạng mục | Develop | Production | Ý nghĩa |
|---|---|---|---|
| Config | Host, port và debug viết trong code | Đọc env, xác thực một số cấu hình khi khởi động | Dùng cùng mã nguồn cho nhiều môi trường |
| Log | `print`, kể cả key giả | Dùng Python logging, mức log và format hướng tới JSON | Dễ lọc sự kiện và giảm lộ thông tin |
| Liveness và readiness | Thiếu endpoint | Có `/health` và `/ready` | Phân biệt tiến trình còn sống với khả năng nhận tải |
| Metrics | Thiếu endpoint | Có `/metrics` | Theo dõi trạng thái agent qua HTTP |
| Shutdown | Không có lifecycle riêng | Có startup/shutdown lifecycle | Có điểm dọn tài nguyên trước khi app thoát |

## Part 2 — Docker

### Exercise 2.1

Bản develop dùng `python:3.11`, thư mục làm việc `/app`. Copy `requirements.txt` trước giúp Docker tái sử dụng layer cài thư viện khi chỉ sửa code. `ENTRYPOINT` xác định chương trình chạy chính. `CMD` cung cấp lệnh mặc định hoặc các tham số mặc định cho entrypoint và có thể bị thay bằng đối số của `docker run`.

### Exercise 2.2–2.3

Đo bằng docker image inspect và đổi byte sang MiB.

| Cặp image | Single-stage | Multi-stage | Giảm |
| --- | --- | --- | --- |
| FastAPI develop / production | 1590.5 MiB | 228.7 MiB | 85.6% |
| Go demo multi-stages | 1246.0 MiB | 21.6 MiB | 98.3% |

Container develop trả 200 trên /health và POST /ask với question ở query string.

Single-stage giữ lại toolchain Go. Multi-stage biên dịch ở stage builder rồi copy binary vào Alpine, giảm nội dung runtime. Trong demo cache, copy `go.mod` và xử lý dependency trước khi copy source giúp giữ layer dependency khi chỉ đổi source.

### Exercise 2.4

Compose kết nối agent, Redis, Qdrant và Nginx theo tên service trong mạng nội bộ. Thử qua Nginx tại localhost:18804 bằng port override dành riêng cho lần chạy. /health, /ready và POST /ask JSON đều trả 200.

~~~mermaid
flowchart LR
    C[Client] --> N[Nginx]
    N --> A[FastAPI agent]
    A -. kết nối qua mạng Compose .-> R[Redis]
    A -. kết nối qua mạng Compose .-> Q[Qdrant]
~~~

Redis và Qdrant cùng tham gia stack. Ví dụ FastAPI dùng mock LLM để trả lời.

## Part 3 — Cloud Deployment

### Exercise 3.1–3.2

URL cloud đã triển khai trên Render: `https://day14-agent-j9w7.onrender.com`. Hai endpoint `/health` và `/ready` đã được xác minh trả về HTTP 200. Xem cấu hình và lệnh xác minh trong [DEPLOYMENT.md](DEPLOYMENT.md).

`railway.toml` chọn Dockerfile builder và đặt `healthcheckPath` trong cấu hình deploy. Render Blueprint dùng YAML để mô tả web service, runtime Docker, thư mục gốc, health check và cách cấp biến môi trường. Railway đặt API key và URL Redis ở môi trường service. Blueprint hiện tạo API key và lấy URL nội bộ từ dịch vụ Render Key Value.

### Exercise 3.3

Cloud Build cài dependencies và chạy test trước khi build image Docker.
Image được gắn tag theo commit rồi push lên registry.
Bước deploy cập nhật dịch vụ Cloud Run sang image vừa build.
`service.yaml` mô tả cấu hình runtime như image, biến môi trường, tài nguyên, probes và scale.

## Part 4 — API Security

### Exercise 4.1–4.3

Ở bản develop, `APIKeyHeader` lấy `X-API-Key` và dependency `verify_api_key` xác thực trước khi gọi agent. Bản demo trả 401 khi thiếu key và 403 khi key sai. Part 6 trả 401 cho cả hai trường hợp. Cập nhật secret trên nền tảng rồi đồng bộ client khi rotate. Trong bản JWT, endpoint thực tế là `POST /auth/token`. Server ký token có `sub`, `role`, `iat` và `exp`. Client gửi token qua `Authorization: Bearer`.

Thử bằng FastAPI TestClient ở bản JWT. Thiếu Bearer trả `401`, đăng nhập tài khoản demo thành công trả `200`, 10 lần gọi hợp lệ trả `200`, lần thứ 11 trả `429`. Rate limiter dùng sliding window 60 giây. User có 10 request/phút, admin đi qua limiter riêng có 100 request/phút.

Output curl -i, trích các dòng status và header liên quan.

~~~http
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
HTTP/1.1 200 OK
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795594968
retry-after: 59
~~~

### Exercise 4.4

Part 6 kiểm tra chi phí tích lũy trong Redis trước khi gọi mock LLM. Sau khi có câu trả lời, app ước lượng token, cộng chi phí nguyên theo đơn vị một phần tỷ USD và đặt TTL đến nửa đêm UTC. Khi chi phí đã chạm ngưỡng, app trả `402`. Chi phí của các request đã được nhận xử lý có thể khiến tổng vượt ngưỡng trước khi request tiếp theo bị chặn.

## Part 5 — Scaling & Reliability

- **5.1** Liveness cho biết tiến trình còn trả HTTP. Readiness kiểm tra Redis và trả `503` khi Redis lỗi.
- **5.2** Uvicorn nhận SIGTERM, dừng nhận kết nối và chờ request đang chạy. Lifespan đóng kết nối Redis sau khi server xử lý xong request.
- **5.3** Part 5 lưu session có TTL trong Redis. Part 6 dùng Redis cho rate limit và ngân sách. Lua xử lý cửa sổ rate limit trong một thao tác để các worker dùng chung quota. Thử 32 lượt lấy quota đồng thời với giới hạn 5/phút cho một key. Có 5 lượt được nhận và 27 lượt bị từ chối kèm Retry-After.
- **5.4–5.5** Nginx chuyển request đến nhiều instance trong mạng Docker. Kiểm tra bằng trường `served_by` và đối chiếu số message trong history của cùng session. Đo local với 3 replica: 5 request ban đầu đi qua đủ 3 instance. Sau khi restart một agent và gửi request thứ 6, history cùng session có đủ 12 message.

## Part 6 — Production Readiness Check

Chạy python check_production_ready.py với Docker và hai Uvicorn worker. Image Part 6 được trình chấm báo 273 MiB.

~~~text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
~~~

## AI log

- Yêu cầu Codex khảo sát repo, đối chiếu checkpoint, hoàn thiện Part 6, bổ sung knowledge base Part 7 và chạy các phép đo. Codex thực hiện thay đổi, chạy lệnh và tổng hợp kết quả quan sát được trong các tài liệu của repo.
- Những phần cần người nộp tự kiểm tra là lý do dùng Redis, cách phân biệt liveness với readiness, cách trình chấm kiểm tra SIGTERM, giới hạn của cost guard, cùng việc đối chiếu từng bảng số liệu với JSON hoặc CSV. Chưa có xác nhận kiểm tra độc lập của người nộp.
