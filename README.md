# La Bàn Nghề

Nền tảng thu thập tin tuyển dụng công khai ở Việt Nam và quốc tế, chuẩn hoá kỹ năng và phân tích xu hướng theo vị trí. Sản phẩm là phần thực hành đi kèm bài giảng **Cầm lái AI** (`../CAM_LAI_AI_Tai_lieu_sinh_vien_v2.pptx`), dùng trực tiếp cho Phần 6 "Hướng đi & việc làm".

## Bản công khai

Bản đọc công khai: **https://ktzung.github.io/labannghe/**

GitHub Pages chỉ chạy nội dung tĩnh, nên bản công khai là ảnh chụp (snapshot) của dashboard và API tại thời điểm build. Các trang, biểu đồ, sách lật và liên kết tải JSON hoạt động; bộ lọc phạm vi/thời gian và API trực tiếp không chạy trên Pages. Số liệu snapshot hiển thị ngày chụp ở đầu mỗi trang. Thông tin liên hệ cá nhân trong phần Case Study đã được ẩn khỏi bản công khai.

Tạo lại bản tĩnh sau khi cập nhật dữ liệu:

```bash
make pages
```

Lệnh này ghi vào `_site/` (không commit vào nhánh mã nguồn). Triển khai `_site/` lên nhánh `gh-pages`; GitHub Pages phục vụ nhánh đó tại đường dẫn trên.

## Tính năng

- Cập nhật hằng ngày từ 17 nguồn công khai: 11 nguồn quốc tế (6 bảng việc làm remote và 5 trang sự nghiệp big tech), 6 nguồn Việt Nam (VietnamWorks, ITviec, ITJobs, CareerViet, Vieclam123, JobOKO).
- Tách nghề khỏi kỹ năng và kiến thức nền: nghề dùng `roles.json`, kỹ năng thao tác/kỹ năng mềm và kiến thức nền (ngành học, lĩnh vực chuyên môn) lấy từ thẻ, mục yêu cầu và dòng yêu cầu chi tiết; phân loại 25 nhóm vị trí và cấp bậc.
- Dashboard: nhu cầu theo kỹ năng, tiêu chuẩn nghề có bằng chứng từ mô tả/yêu cầu, kỹ năng đang lên, lương trung vị, phân bố vị trí, địa bàn tỉnh/thành, cơ cấu doanh nghiệp nhà nước/FDI/tư nhân, xu hướng tuần.
- Tín hiệu cộng đồng từ RSS công khai của 4 chuyên mục Voz (tuyển dụng, CNTT, AI, ngoại ngữ): chủ đề, vấn đề, kỹ năng được bàn, hot thread và hoạt động theo ngày. Không lưu tên tác giả, không đọc bình luận đầy đủ.
- Tra cứu kỹ năng/vị trí kèm tin mẫu, công ty, mức lương, tiêu chuẩn nghề và gợi ý 90 ngày.
- Trang `/bao-cao`: một slide 16:9 in ra PDF để chèn vào bài giảng.
- Trang `/sach-lat`: bảy trang đọc dạng sách lật (bìa, thị trường, kỹ năng, vị trí, địa bàn, cộng đồng, kế hoạch 90 ngày), lật bằng nút, phím mũi tên hoặc vuốt ngang.
- Trang `/cntt`: phân tích riêng nhóm nghề CNTT — số tin và độ phủ mô tả, lương trung vị, ma trận kỹ năng × vai trò, nội dung công việc (xây dựng, dữ liệu/AI, hạ tầng, chất lượng, bảo mật, quy trình, khách hàng), nhóm kiến thức, cấp bậc, dẫn chứng trích từ tin gốc, địa bàn và công ty.
- Giao diện responsive; thanh điều hướng ngang trên đầu trang, tự xuống dòng trên màn hình hẹp và cuộn ngang trên điện thoại.
- API JSON và export toàn bộ số liệu.

## Chạy nhanh

Yêu cầu Python 3.9 trở lên.

```bash
cd labannghe
make setup
make init
make ingest
make serve
```

Mở http://127.0.0.1:8765. Nếu không dùng `make`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m laban.cli init
.venv/bin/python -m laban.cli ingest
.venv/bin/python -m laban.cli serve --port 8765
```

## Cập nhật hằng ngày

Chạy thủ công:

```bash
make ingest
```

Cập nhật thêm tín hiệu cộng đồng (RSS):

```bash
python3 -m laban.cli social-ingest --mode auto
```

Cài lịch launchd lúc 06:30 (macOS). Lệnh dưới đây sẽ hỏi xác nhận trước khi ghi vào `~/Library/LaunchAgents`:

```bash
scripts/install_scheduler.sh --dry-run   # xem plist sẽ tạo
scripts/install_scheduler.sh             # cài thật, hỏi y/N
```

Log: `data/logs/ingest.log`. Gỡ lịch:

```bash
launchctl bootout gui/$UID ~/Library/LaunchAgents/com.labannghe.daily.plist
rm ~/Library/LaunchAgents/com.labannghe.daily.plist
```

Cron tương đương:

```cron
30 6 * * * cd /duong/dan/labannghe && /bin/zsh scripts/run_daily.sh
```

## Nguồn dữ liệu

| Nguồn | Phạm vi | Cách lấy | Ghi chú |
|---|---|---|---|
| Remotive | Quốc tế | API công khai | Remote |
| Arbeitnow | Quốc tế | API công khai | Châu Âu, remote |
| Remote OK | Quốc tế | API công khai | Remote |
| Jobicy | Quốc tế | API công khai | Remote |
| Himalayas | Quốc tế | API công khai | Remote |
| WeWorkRemotely | Quốc tế | RSS | Remote |
| Amazon Careers | Quốc tế | API tìm kiếm công khai | Có lọc tin 45 ngày; lấy cả vị trí tại Việt Nam |
| NVIDIA Careers | Quốc tế | Workday API công khai | Danh sách + trang chi tiết |
| Netflix Jobs | Quốc tế | Eightfold API công khai | Danh sách + trang chi tiết |
| OpenAI Careers | Quốc tế | Ashby API công khai | Lọc tin 30 ngày |
| Anthropic Careers | Quốc tế | Greenhouse API công khai | Lọc tin 30 ngày |
| VietnamWorks | Việt Nam | API tìm kiếm công khai | Lấy sâu 30 trang mỗi lần chạy; tin mới nhất trước |
| ITviec | Việt Nam | Trang danh sách + trang chi tiết công khai | Tối đa 10 trang, 200 trang chi tiết mỗi lần chạy; nhiều tin ẩn lương |
| ITJobs | Việt Nam | Trang tìm kiếm + trang chi tiết công khai | 10 tin mỗi truy vấn; gom theo 15 từ khóa công nghệ, chỉ giữ tin đăng trong 60 ngày, lấy tối đa 120 trang chi tiết, không cần đăng nhập |
| CareerViet | Việt Nam | Danh mục + trang chi tiết công khai | Gom 25 nhóm ngành, lấy 200 tin mới nhất có mô tả/yêu cầu; ngày trên thẻ là ngày cập nhật |
| Vieclam123 | Việt Nam | Danh mục thành phố + trang chi tiết công khai | Lấy tin mới từ trang tổng hợp và 5 thành phố lớn, lọc ngày đăng 30 ngày, tối đa 150 tin có mô tả/yêu cầu |
| JobOKO | Việt Nam | Danh mục + JSON-LD công khai | 118 tin mới nhất; lương, ngày đăng, công ty và mô tả/yêu cầu lấy từ JSON-LD |

Chỉ dùng dữ liệu công khai, không đăng nhập, không vượt kiểm soát truy cập. Mỗi tin giữ liên kết về trang gốc. Nguồn chặn truy cập tự động sẽ bị loại khỏi danh sách thay vì giả User-Agent.

Các nền tảng lớn chưa thu thập được, kèm lý do, được nêu công khai ở trang `/nguon`: TopCV (Cloudflare 403), Vieclam24h (chặn User-Agent không phải trình duyệt), JobsGO (danh sách trả 403), CareerLink (trang xác nhận robot), TopDev (timeout/đóng kết nối), Glints (403), LinkedIn Jobs (kết nối bị đóng, yêu cầu đăng nhập), Indeed (403), Microsoft Careers (API không trả JSON, chứng chỉ TLS không khớp), Google Careers (danh sách tải bằng JavaScript), Apple Jobs (API trả 401).

## Trang và API

| Đường dẫn | Nội dung |
|---|---|
| `/` | Tổng quan thị trường |
| `/ky-nang` | Bảng kỹ năng thao tác và bảng kiến thức nền, lọc vai trò, tìm kiếm |
| `/vi-tri` | 25 nhóm vị trí, tiêu chuẩn nghề có dẫn chứng và kế hoạch 90 ngày |
| `/cntt` | Phân tích nhóm nghề CNTT: kỹ năng, nội dung công việc, cấp bậc, dẫn chứng |
| `/tin-hieu-cong-dong` | Dashboard tín hiệu cộng đồng từ RSS |
| `/nguon` | Trạng thái 17 nguồn tuyển dụng, nền tảng chưa thu thập được, RSS cộng đồng, lịch sử ingest |
| `/bao-cao` | Slide 16:9, nút In/Lưu PDF |
| `/sach-lat` | Sách lật 7 trang, đổi phạm vi/khung ngày, lật bằng phím hoặc vuốt |
| `/api/docs` | Swagger UI |

API chính: `/api/overview`, `/api/skills`, `/api/skill/{id}`, `/api/roles`, `/api/role/{id}`, `/api/jobs`, `/api/it`, `/api/social/overview`, `/api/method`, `/api/health`, `/api/export`. Các endpoint nhận `scope=vn|global|all`, `days=1..365`; `/api/overview` và `/api/export` trả thêm `top_locations`, `company_types`, độ phủ mô tả/yêu cầu và tiêu chuẩn nghề cho thị trường Việt Nam.

## Phương pháp

Tóm tắt pipeline và công thức trong [docs/PHUONG_PHAP.md](docs/PHUONG_PHAP.md). Các điểm cần nhớ khi trích dẫn:

- Kỹ năng được tính theo trọng số: thẻ 4, mục yêu cầu 4, mô tả 4, tiêu đề 3. Tiêu đề chỉ là tín hiệu phụ để tránh biến chức danh thành kỹ năng; tiêu chuẩn nghề chỉ dùng bằng chứng từ thẻ, mô tả hoặc yêu cầu.
- Trang `/cntt` chỉ tính kỹ năng kỹ thuật (lập trình, dữ liệu, web, cloud) cho ma trận và tiêu chuẩn vai trò; nhóm kỹ năng mềm/ngoại ngữ hiển thị riêng. Nhóm dưới 15 tin được đánh dấu "ít tin" thay vì so sánh ngang hàng. Nội dung công việc đếm theo từ khóa trên tối đa 800 tin có mô tả gần nhất, nên là chỉ báo tương đối chứ không phải phân loại tuyệt đối.
- Độ phủ chi tiết = tỷ lệ tin có mô tả hoặc yêu cầu; tỷ lệ này được hiển thị cạnh tiêu chuẩn nghề để biết mức độ đáng tin của mẫu văn bản.
- Địa bàn lấy từ bảng `job_locations`: một tin nhiều tỉnh/thành được tính cho từng địa bàn. Loại hình doanh nghiệp là phân loại tham chiếu theo tên, có nhóm `unknown` thay vì gán bừa.
- Lương quy đổi về VND/tháng bằng tỷ giá tham khảo; chỉ tính tin có công bố lương.
- Tỷ lệ kỹ năng = số tin trong phạm vi có nhắc kỹ năng / tổng tin trong phạm vi.
- Chênh lệch kỳ trước chỉ hiện khi mẫu kỳ trước đạt tối thiểu 30 tin và 20% độ phủ của kỳ hiện tại, để không tạo mức tăng ảo ngay sau khi bổ sung nguồn.
- Tin trùng giữa các nguồn được gộp theo khoá tiêu đề + công ty + địa điểm + tháng.

## Kiểm thử

```bash
make test
```

Smoke test kiểm tra bộ tách lương, chuẩn hoá tiếng Việt, tách kỹ năng, phân loại vị trí, phân cấp bậc, bộ phân tích ngày và HTML của nguồn big tech/CareerViet/Vieclam123/JobOKO, danh mục 17 nguồn và danh sách nền tảng chưa thu thập được, RSS và băm tên tác giả, render 8 trang và các API chính (gồm `/cntt`, `/api/it`). Test dùng DB tạm, không đụng dữ liệu thật.

## Vận hành

Biến môi trường:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LABAN_DB` | `data/laban.db` | Đường dẫn SQLite |
| `LABAN_DATA_DIR` | `data/` | Thư mục dữ liệu |
| `LABAN_DELAY` | `1.2` | Giãn cách request (giây) |
| `LABAN_TIMEOUT` | `40` | Timeout HTTP (giây) |
| `LABAN_RETRIES` | `2` | Số lần thử lại |
| `LABAN_TRUST_ENV` | `0` | Đặt `1` để dùng proxy hệ thống |
| `LABAN_VOZ_MODE` | `auto` | `auto`/`file`/`http` cho RSS cộng đồng |
| `LABAN_VOZ_RSS_DIR` | `data/voz_rss` | Thư mục snapshot RSS |
| `LABAN_VOZ_SALT` | `laban-voz-v1` | Muối băm tên tác giả; đổi khi triển khai công khai |

Dọn raw quá 21 ngày và VACUUM:

```bash
make prune
```

Xem thống kê kho:

```bash
make stats
```

Sau khi sửa `taxonomy/*.json`, phân loại lại toàn bộ kho mà không cần tải lại nguồn:

```bash
make reclassify
```

## Cấu trúc

```text
labannghe/
├── laban/            # thu thập, chuẩn hoá, analytics, web
│   ├── sources/      # module nguồn (17 nguồn đang hoạt động)
│   └── cli.py        # init/ingest/social-ingest/reclassify/serve/stats/prune/export
├── taxonomy/         # skills.json, roles.json, locations.json, company_types.json, social.json
├── templates/        # Jinja2, 7 trang
├── static/           # app.css, app.js, favicon
├── scripts/          # chạy hằng ngày, cài launchd
├── tests/            # smoke test
├── docs/             # phương pháp
└── data/             # DB, raw, log (không commit)
```

## Giới hạn

- Dữ liệu chỉ phản ánh các nguồn đã chọn, không đại diện toàn bộ thị trường.
- Tin ẩn lương làm lương trung vị chỉ dựa trên mẫu có công bố.
- Lịch sử 12 tuần cần thời gian tích luỹ; ngày đầu chỉ có một điểm dữ liệu.
- Phân loại vai trò, kỹ năng, địa bàn và loại hình doanh nghiệp là rule-based, có thể sai với tên viết tắt hoặc tiêu đề mơ hồ. Loại hình doanh nghiệp cần được đối chiếu trước khi dùng cho kết luận mạnh.
- Không thu thập thông tin cá nhân của nhà tuyển dụng hay ứng viên.

Dự án học thuật phục vụ sinh viên TLU. Khi trích dẫn số liệu, ghi rõ nguồn La Bàn Nghề, phạm vi ngày và thời điểm cập nhật.
