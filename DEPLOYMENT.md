# Triển khai agent Day 14

## URL public

Render service đã triển khai thành công và được xác minh:

`https://day14-agent-j9w7.onrender.com`

Health checks trả về `200` cho cả `/health` và `/ready`.

Nền tảng chính là Render. Web service `day14-agent` chạy Docker, kết nối Key Value `day14-redis` qua mạng nội bộ.

## Cấu hình nền tảng

- **Render.** Tạo Blueprint từ fork đã có bài làm và đặt Blueprint Path là `06-lab-complete/render.yaml`. Blueprint khai báo web service Docker và Key Value cùng gói free. Web service nhận `REDIS_URL` từ kết nối nội bộ và Render tự sinh `AGENT_API_KEY`. [Render Blueprint](https://render.com/docs/infrastructure-as-code) · [Tham chiếu cấu hình](https://render.com/docs/blueprint-spec)
- **Railway.** Đặt Root Directory là `/06-lab-complete` và đường dẫn config là `/06-lab-complete/railway.toml` nếu service hỗ trợ Config as Code. Tạo Redis trong cùng project, đặt `REDIS_URL` của web service trỏ đến Redis, thêm `AGENT_API_KEY`, rồi tạo domain public cho web service. Có thể đặt Dockerfile builder và health check `/health` trực tiếp trong dashboard nếu service không dùng Config as Code. [Railway monorepo](https://docs.railway.com/deployments/monorepo) · [Railway Config as Code](https://docs.railway.com/config-as-code/reference)

Cả hai nền tảng dùng `/health` cho liveness. Xác minh thêm `/ready` sau khi Redis sẵn sàng.

| Biến | Giá trị cần đặt |
|---|---|
| `AGENT_API_KEY` | Secret riêng của dịch vụ |
| `REDIS_URL` | URL kết nối Redis của dự án |
| `PORT` | Do nền tảng cấp. Dockerfile đọc giá trị này |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | Mặc định 10 |
| `DAILY_BUDGET_USD` | Mặc định 1 USD, dùng giá token mô phỏng |

## Xác minh URL

Đặt `AGENT_API_KEY` trong môi trường của terminal trước khi chạy. Các lệnh chỉ in mã HTTP.

```bash
BASE=https://day14-agent-j9w7.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
printf 'X-API-Key: %s\n' "$AGENT_API_KEY" | curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H @- -d '{"question":"Hello"}'
```

Kết quả mong đợi là `200`, `200`, `401`, `200`. Ba kiểm tra đầu đã đạt trên Render. Lượt thử có khóa trên Render trả `401`; cần xác minh lại với khóa đang dùng của service. Trình chấm chạy local đã xác minh `/ask` trả `200` với khóa đúng.

## Ảnh minh chứng

- [Render Blueprint đồng bộ thành công và tạo web service cùng Redis](screenshots/dashboard.png)
- [Render Deploys hiển thị service Live và URL công khai](screenshots/running.png)
- [Kết quả curl với API công khai trên Render](screenshots/test.png)
