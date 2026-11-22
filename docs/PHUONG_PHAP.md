# Phương pháp

Tài liệu này mô tả cách La Bàn Nghề biến tin tuyển dụng thô thành số liệu dùng được trong bài giảng và cho sinh viên tra cứu.

## 1. Phạm vi

- Đơn vị phân tích: một tin tuyển dụng đang hoạt động, có ngày đăng trong khoảng thời gian đã chọn.
- Phạm vi địa lý: `vn` (tin Việt Nam), `global` (tin quốc tế), `all`.
- Cửa sổ thời gian mặc định: 30 ngày; hỗ trợ 7, 30, 90 ngày và tối đa 365 ngày.
- Đơn vị kỹ năng: một mục trong `taxonomy/skills.json` (kỹ năng thao tác hoặc kiến thức nền; xem mục 4).
- Đơn vị vị trí: một mục trong `taxonomy/roles.json` (25 nhóm) hoặc `other`.
- Đơn vị địa bàn: một tỉnh/thành trong `taxonomy/locations.json`; một tin có thể thuộc nhiều địa bàn.
- Đơn vị loại hình doanh nghiệp: `state`, `fdi`, `private`, `agency`, `unknown` trong `taxonomy/company_types.json`.

## 2. Thu thập

Mỗi nguồn là một module trong `laban/sources/`, có hàm `fetch()` trả về danh sách bản ghi chuẩn hoá. Có 11 nguồn quốc tế: sáu bảng việc làm remote dùng API/RSS công khai (Remotive, Arbeitnow, RemoteOK, Jobicy, Himalayas, WeWorkRemotely), và năm trang sự nghiệp big tech (Amazon, NVIDIA, Netflix, OpenAI, Anthropic) dùng API công khai của chính trang. Amazon và OpenAI/Anthropic giới hạn tin trong 45/30 ngày gần nhất; NVIDIA và Netflix lấy danh sách rồi mở trang chi tiết để có mô tả.

Sáu nguồn Việt Nam: VietnamWorks dùng API tìm kiếm công khai, sắp xếp theo ngày đăng mới nhất và lấy tối đa 30 trang mỗi lần chạy. ITviec đọc trang danh sách công khai, chuyển ngày tương đối ("3 days ago") thành ngày tuyệt đối, tối đa 10 trang, rồi mở tối đa 200 trang chi tiết để lấy mô tả công việc và yêu cầu. ITJobs đọc trang tìm kiếm công khai (10 tin mỗi truy vấn), gom theo 15 từ khóa công nghệ, chỉ giữ tin đăng trong 60 ngày và mở tối đa 120 trang chi tiết để lấy mô tả, yêu cầu và thẻ kỹ năng. CareerViet gom tin từ 25 nhóm ngành trong sitemap danh mục công khai, lọc tin cập nhật trong 30 ngày, rồi mở tối đa 200 trang chi tiết. Vieclam123 lấy tin mới từ trang tổng hợp và 5 thành phố lớn, đọc ngày đăng thật trên trang chi tiết, lọc 30 ngày và giữ tối đa 150 tin có mô tả/yêu cầu. JobOKO đọc 118 tin mới nhất từ danh mục công khai và lấy lương, ngày đăng, công ty, mô tả/yêu cầu từ JSON-LD của trang chi tiết. Lỗi ở một trang chi tiết không làm dừng cả nguồn.

Nguyên tắc:

- Không đăng nhập, không dùng tài khoản trả phí, không lách chặn truy cập.
- Giữ `source`, `external_id`, `url` gốc để truy vết và dẫn nguồn.
- Nguồn trả 403 hoặc yêu cầu JavaScript sẽ bị loại, không giả trình duyệt để vượt chặn.
- Request cách nhau 1,2 giây mặc định; lỗi 429/5xx được thử lại tối đa 2 lần.

## 3. Chuẩn hoá và gộp trùng

Mỗi tin được đưa về một cấu trúc chung: tiêu đề, công ty, loại hình doanh nghiệp, địa điểm gốc, danh sách tỉnh/thành chuẩn hoá, vùng, hình thức làm việc, cấp bậc, mô tả, yêu cầu, thẻ, lương, ngày đăng, hạn nộp. Quan hệ nhiều-nhiều giữa tin và địa bàn nằm trong bảng `job_locations`.

Khoá gộp trùng:

```text
sha1(normalize(title) | normalize(company) | normalize(location) | YYYY-MM)
```

`normalize` chuyển về chữ thường, bỏ dấu tiếng Việt và gộp khoảng trắng. Hai tin cùng tiêu đề, cùng công ty, cùng địa điểm trong cùng tháng được coi là một việc làm; các lần xuất hiện ở nguồn khác nhau vẫn được lưu trong bảng `job_sources`.

Hệ quả: một số tin cùng công ty, cùng chức danh nhưng tuyển nhiều đợt trong tháng sẽ bị gộp. Cách này ưu tiên độ phủ việc làm hơn là đếm số lượt đăng.

## 4. Tách kỹ năng, kiến thức và kinh nghiệm

`taxonomy/skills.json` chứa nhóm, nhãn, alias tiếng Việt/Anh, pattern bổ sung và trường `kind`:

- `kind: "skill"` — kỹ năng thao tác hoặc kỹ năng mềm có thể luyện và kiểm chứng: Python, SQL, AutoCAD, PLC, HEC-RAS, giao tiếp, thuyết trình, quản lý dự án.
- `kind: "knowledge"` — kiến thức nền, ngành học hoặc lĩnh vực chuyên môn: điện - điện tử, cơ khí, kết cấu, địa kỹ thuật, thuỷ lợi, môi trường.

Cùng một nhãn không được tính vừa là kỹ năng vừa là kiến thức. “Điện - Điện tử” vì vậy chỉ xuất hiện ở bảng kiến thức nền, không còn nằm trong bảng kỹ năng.

Alias được chuẩn hoá bỏ dấu rồi biên dịch thành regex có ranh giới từ, tránh khớp nhầm chuỗi con. Bộ tách chỉ đọc các dòng có khả năng là yêu cầu:

1. Dòng nằm dưới tiêu đề yêu cầu: `Requirements`, `Qualifications`, `Your Qualifications`, `Required Job Skills`, `Education/Training Required`, `What you'll need`, `Yêu cầu`, `Kỹ năng`, `Kinh nghiệm`, `Trình độ chuyên môn`...
2. Dòng có cụm tín hiệu yêu cầu: `experience with`, `knowledge of`, `proficient`, `familiar`, `hands-on`, `kinh nghiệm`, `thành thạo`...
3. Dòng mô tả ngắn chỉ gồm tên công cụ/phương pháp, không có ngữ cảnh công ty/sản phẩm.

Bộ tách dừng ở các tiêu đề phúc lợi/giới thiệu công ty (`Benefits`, `What we offer`, `About us`, `Phúc lợi`, `Giới thiệu công ty`...) và loại các câu boilerplate tuyển dụng. Mô tả sản phẩm, danh mục hàng hoá hay câu giới thiệu công ty không tạo ra kỹ năng.

Mỗi mục nhận trọng số cao nhất theo vị trí xuất hiện:

| Vị trí | Trọng số |
|---|---|
| Thẻ kỹ năng của nguồn | 4 |
| Dòng trong mục yêu cầu | 4 |
| Dòng mô tả ngắn chỉ là tên công cụ | 4 |
| Dòng có cụm tín hiệu yêu cầu, ngoài mục yêu cầu | 3 |
| Tiêu đề (chỉ áp dụng cho `kind: "skill"`) | 3 |

Tiêu đề không tạo ra kiến thức nền: một tin "Nhân viên kinh doanh thiết bị điện tử" không được gán kiến thức `electrical` chỉ vì tiêu đề. Kiến thức phải có bằng chứng trong thẻ, hoặc trong một dòng nêu bằng cấp/ngành học/khối kiến thức (`tốt nghiệp`, `chuyên ngành`, `bằng cấp`, `kiến thức`, `hiểu biết`, `knowledge of`, `degree in`, `background in`...). Cụm chỉ mô tả sản phẩm hoặc ngành hàng như `thương mại điện tử`, `consumer electronics` hay `electronic warfare` không được tính là kiến thức điện - điện tử. Với kỹ năng, dòng chỉ nói về bằng cấp/ngành học (ví dụ "Bachelor's degree in Electrical Engineering") không được tính là bằng chứng thao tác, trừ khi cùng dòng có cụm thực hành như `experience with` hoặc `proficient`.

Kinh nghiệm (số năm, lịch sử dự án) không phải một nhãn trong taxonomy. Các dòng kinh nghiệm vẫn được đọc để tìm kỹ năng/kiến thức, nhưng bản thân "3 năm kinh nghiệm" không tạo ra một mục kỹ năng.

Một tin có thể có nhiều kỹ năng và nhiều kiến thức nền. Cùng một mục chỉ tính một lần cho mỗi tin, lấy trọng số cao nhất. Dashboard hiển thị hai bảng riêng: kỹ năng thao tác và kiến thức nền.

“Bằng chứng mạnh” (`strong_jobs`, `strong_share`) là số tin mà mục xuất hiện trong thẻ, mục yêu cầu hoặc dòng yêu cầu — tức trọng số 4. Tiêu đề (trọng số 3) không đủ để tạo thành tiêu chuẩn nghề. Với mỗi vị trí, dashboard lấy các mục có nhiều bằng chứng mạnh nhất và trích câu yêu cầu/mô tả làm dẫn chứng.

“Độ phủ chi tiết” (`detail_coverage`) là tỷ lệ tin có ít nhất một trong hai trường mô tả hoặc yêu cầu. Tỷ lệ này thấp nghĩa là tiêu chuẩn nghề dựa trên ít văn bản gốc hơn và cần đọc thận trọng.

Khi taxonomy thay đổi, chạy `python3 -m laban.cli reclassify` để tính lại nghề, kỹ năng, kiến thức nền, địa bàn và loại hình doanh nghiệp cho toàn bộ kho mà không cần tải lại nguồn.

## 5. Địa bàn và loại hình doanh nghiệp

Địa bàn được chuẩn hoá từ trường địa điểm của tin qua `taxonomy/locations.json`. Bộ phân tích nhận diện tên tỉnh/thành có dấu, không dấu, tên tiếng Anh và các cách viết tách bằng dấu phẩy, gạch nối hoặc gạch chéo. Ví dụ "Hồ Chí Minh, Hà Nội" được ghi thành hai địa bàn. Một tin nhiều địa điểm vì vậy được tính cho từng địa bàn; tổng tỷ lệ theo tỉnh/thành có thể lớn hơn 100%.

Loại hình doanh nghiệp là phân loại tham chiếu theo tên, không phải dữ liệu đăng ký kinh doanh:

- `state`: doanh nghiệp nhà nước hoặc có vốn nhà nước rõ ràng (Viettel, EVN, PVN, VNPT, các ngân hàng 100% vốn nhà nước...).
- `fdi`: công ty nước ngoài hoặc thương hiệu quốc tế (Samsung, LG, Bosch, Fujikin, Shinhan...).
- `private`: doanh nghiệp tư nhân/cổ phần trong nước, bao gồm các tên có hình thức "công ty cổ phần", "CTCP", "ngân hàng TMCP" nhưng không thuộc hai nhóm trên.
- `agency`: trung gian tuyển dụng hoặc nhãn ẩn danh như "Client", "Navigos Search", "ITviec Recruitment Consulting".
- `unknown`: không đủ căn cứ. Nhóm này được giữ riêng và không bị gán thành tư nhân.

Các nhóm `agency` bị loại khỏi bảng doanh nghiệp nổi bật nhưng vẫn xuất hiện trong cơ cấu loại hình để người đọc thấy phần dữ liệu qua trung gian. Tỷ lệ phủ (`coverage`) cho biết bao nhiêu tin xác định được loại hình; phần còn lại là `unknown`.

## 6. Phân loại vị trí

Có 25 nhóm nghề: `ai_ml`, `data`, `mobile`, `qa`, `quality`, `devops`, `security`, `it_support`, `software`, `research`, `strategy`, `product`, `design`, `marketing`, `sales`, `finance`, `legal`, `hr`, `civil`, `environment`, `mech_elec`, `manufacturing`, `logistics`, `customer`, `admin`; tin không đủ căn cứ xếp vào `other`.

Hai nhóm được tách riêng để không trộn chức danh quản lý với chuyên môn:

- `research`: research scientist, research engineer, research assistant, research economist, research operations, postdoc, nghiên cứu viên. Chức danh điều phối chương trình, giảng dạy hoặc trợ giảng không tự động vào nhóm này.
- `strategy`: strategy & operations, business operations, chuyển đổi doanh nghiệp, PMO, hoạch định chiến lược, chính sách và đối ngoại. Chức danh "manager" chỉ vào nhóm này khi tiêu đề hoặc danh mục nêu rõ chức năng chiến lược/vận hành, không dựa vào một nhãn phụ chung.

Chức danh quản lý được xếp theo miền chuyên môn, không theo chữ "manager": HR Director vào `hr`, Engineering Manager vào `software`, QA Manager vào `qa`, Accounting Manager vào `finance`, Restaurant Manager không đủ căn cứ nên ở `other`.

Quy tắc ưu tiên:

1. Khớp từ khoá trong tiêu đề theo thứ tự nghề chuyên biệt trước, nghề chung sau.
2. Khớp danh mục nguồn qua bảng ánh xạ Việt/Anh.
3. Khớp từ khoá trong danh mục và thẻ.
4. Nếu mô tả có dấu hiệu phần mềm/lập trình, xếp vào `software`; còn lại `other`.

Trước khi so khớp, dấu câu trong tiêu đề được đổi thành khoảng trắng để `Cyber-Security` khớp `cyber security`, `Network & Security` khớp `network security`, và `UI/UX` khớp `ui ux`.

Thứ tự này hạn chế việc một tin "Kỹ sư phần mềm xây dựng" bị xếp nhầm vào xây dựng chỉ vì từ "xây dựng", và giúp "Thiết kế kiến trúc" vào nhóm xây dựng thay vì nhóm thiết kế đồ hoạ.

## 7. Cấp bậc

Nhận diện theo tiêu đề và trường cấp bậc của nguồn: `intern`, `fresher`, `junior`, `mid`, `senior`, `manager`. Mặc định là `mid` khi không có tín hiệu.

## 8. Lương

Chuỗi lương tự do được tách thành `(min, max, currency, period)`. Các dạng hỗ trợ:

- `20 - 30 triệu` → 20.000.000–30.000.000 VND/tháng.
- `50.000.000 - 70.000.000 VND` → nhận dấu chấm là phân cách nghìn.
- `$120,000 - $160,000 a year` → USD/năm.

Quy đổi về VND/tháng:

```text
VND/tháng = amount × tỷ giá × hệ số kỳ hạn
```

Hệ số: năm chia 12; giờ nhân 173; ngày nhân 21. Tỷ giá nằm trong `laban/config.py`, chỉ dùng để so sánh tương đối.

Trung vị lương dùng midpoint của khoảng lương mỗi tin. Chỉ tin có công bố lương mới được tính. Vì nhiều tin Việt Nam ẩn lương, trung vị không đại diện cho toàn bộ thị trường.

## 9. Chỉ số trên dashboard

- **Tỷ lệ kỹ năng**: số tin trong phạm vi có kỹ năng / tổng tin trong phạm vi.
- **Tỷ lệ có bằng chứng**: số tin mà mục xuất hiện trong thẻ, mô tả hoặc yêu cầu / tổng tin trong phạm vi.
- **Tiêu chuẩn nghề**: các kỹ năng và kiến thức nền có nhiều bằng chứng mạnh nhất trong một vị trí, kèm câu mô tả/yêu cầu làm dẫn chứng. Hai loại được hiển thị riêng.
- **Chênh lệch kỳ trước**: so sánh tỷ lệ hiện tại với cửa sổ liền trước cùng độ dài; chỉ hiện khi kỳ trước có ít nhất 30 tin và đạt tối thiểu 20% độ phủ của kỳ hiện tại. Quy tắc này ẩn các mức tăng ảo ngay sau khi bổ sung nguồn mới.
- **Kỹ năng đang lên**: chênh lệch điểm phần trăm trong 14 ngày so với 14 ngày trước.
- **Lương theo kỹ năng**: trung vị lương của các tin có kỹ năng; premium là chênh lệch so với trung vị chung.
- **Phân bố vị trí**: số tin và tỷ lệ theo 25 nhóm; nhóm `other` xếp cuối.
- **Xu hướng tuần**: số tin theo tuần đăng trong 12 tuần gần nhất.
- **Địa bàn tuyển dụng**: số tin theo tỉnh/thành, chỉ tính tin Việt Nam; một tin nhiều địa điểm được đếm ở từng địa bàn.
- **Cơ cấu loại hình doanh nghiệp**: số tin, tỷ lệ và lương trung vị theo `state/fdi/private/agency/unknown`; kèm tỷ lệ tin xác định được loại hình.

## 10. Tín hiệu cộng đồng

Nguồn là RSS công khai của bốn chuyên mục Voz: Tuyển dụng - Tìm việc, Lập trình / CNTT, AI và Ngoại ngữ. Mỗi chuyên mục trả tối đa 20 chủ đề mới nhất, gồm tiêu đề, liên kết, ngày đăng, số phản hồi/lượt xem và một đoạn trích. Nền tảng không tải toàn bộ bình luận, không đăng nhập, không vượt Cloudflare.

Quy trình:

1. Đọc RSS trực tiếp nếu được; nếu bị chặn, dùng snapshot công khai trong `data/voz_rss/` (chế độ `auto`/`file`).
2. Chuẩn hoá liên kết về `https://voz.vn/t/<slug>.<id>/`, lấy `thread_id` làm khoá.
3. Băm tên tác giả bằng SHA-256 với muối (`LABAN_VOZ_SALT`), chỉ lưu 16 ký tự; không lưu tên gốc.
4. Tách tin tuyển dụng khỏi thảo luận bằng quy tắc tiêu đề/đoạn trích (ví dụ “Tuyển dụng…”, “Cần tuyển…” so với “Hỏi…”, “Review…”, “Xin review…”).
5. Gắn nhãn chủ đề, vấn đề và kỹ năng bằng cùng bộ từ điển với tin tuyển dụng; mỗi chủ đề có thể có nhiều nhãn.
6. Lưu tối đa 700 ký tự đoạn trích; mọi chủ đề đều có liên kết về bài gốc.

Chỉ số:

- **Chủ đề/thảo luận**: tổng số chủ đề, đã tách tin tuyển dụng.
- **Lượt phản hồi**: tổng `slash:comments` từ RSS, không phải số người tham gia.
- **Tỷ lệ cộng đồng**: số chủ đề có nhãn / tổng số chủ đề trong phạm vi.
- **Khoảng cách**: tỷ lệ cộng đồng trừ tỷ lệ tin tuyển dụng cần kỹ năng tương ứng. Khoảng cách dương gợi ý cộng đồng quan tâm nhiều hơn mức xuất hiện trong tin; khoảng cách âm gợi ý nhà tuyển dụng nhắc nhiều hơn thảo luận công khai.
- **Hoạt động theo ngày**: số chủ đề mới ghi nhận mỗi ngày.

Giới hạn: RSS chỉ là mẫu 20 chủ đề mới nhất mỗi chuyên mục, không đại diện cho toàn bộ diễn đàn hay toàn bộ người học; nhãn vấn đề là tín hiệu ngôn ngữ, không phải chẩn đoán tâm lý hay kết luận về cá nhân.

## 11. Kiểm soát chất lượng

- Bỏ qua bản ghi thiếu tiêu đề.
- Gộp trùng theo khoá tháng; loại tin trùng lặp trong cùng một lần tải.
- Chỉ tính chênh lệch khi mẫu đủ lớn.
- Loại tên công ty là đại lý tuyển dụng hoặc nhãn ẩn danh khỏi bảng "doanh nghiệp nổi bật".
- Không suy đoán loại hình doanh nghiệp khi chỉ có tên mơ hồ; ghi `unknown` và báo tỷ lệ phủ.
- Địa bàn không nhận diện được (ví dụ "Việt Nam", "Quốc tế") không được gán vào tỉnh/thành nào.
- Smoke test chạy trên DB tạm, kiểm tra bộ tách lương, tách kỹ năng, phân loại và render.
- Ngày đăng được ưu tiên hơn ngày thu thập khi tính "tin mới hôm nay".

## 12. Cách dùng cho sinh viên

1. Chọn phạm vi Việt Nam hoặc Toàn cầu, cửa sổ 30 hoặc 90 ngày.
2. Chọn một vị trí gần với mục tiêu nghề nghiệp.
3. Đọc 5 kỹ năng xuất hiện nhiều nhất và 3 kỹ năng đang lên; mở tin mẫu để đối chiếu ngữ cảnh.
4. Mở một vị trí và đọc mục “Tiêu chuẩn nghề”: chỉ chọn kỹ năng có tỷ lệ bằng chứng cao, rồi đọc câu mô tả/yêu cầu được trích để hiểu ngữ cảnh.
5. Xem địa bàn và loại hình doanh nghiệp để biết nhu cầu đang tập trung ở đâu, nhưng không coi đó là danh sách ưu tiên cá nhân.
6. Mở “Tín hiệu cộng đồng” để đối chiếu điều người học đang bàn với kỹ năng nhà tuyển dụng yêu cầu; chú ý khoảng cách và giới hạn mẫu RSS.
7. Đối chiếu với kế hoạch 90 ngày của vị trí: chọn 3 kỹ năng, mỗi kỹ năng tạo một bằng chứng (dự án, chứng chỉ, bài viết, sản phẩm).
8. Ghi lại mốc thời gian và phạm vi số liệu khi trích dẫn.

## 13. Giới hạn

- Mẫu không ngẫu nhiên: chỉ gồm các nguồn đã chọn.
- Một số nền tảng lớn chưa thu thập được vì chặn truy cập tự động hoặc không có API ổn định: TopCV (Cloudflare 403), Vieclam24h (chặn User-Agent không phải trình duyệt), JobsGO (danh sách 403), CareerLink (trang xác nhận robot), Microsoft Careers (API không trả JSON, chứng chỉ TLS không khớp), Google Careers (tải bằng JavaScript), Apple Jobs (API 401). Danh sách và lý do hiển thị công khai ở trang `/nguon`; nền tảng không giả User-Agent để vượt chặn.
- Tin big tech lấy từ trang sự nghiệp toàn cầu, không phải toàn bộ tin đăng trên các nền tảng tuyển dụng địa phương; vị trí tại Việt Nam chỉ xuất hiện khi công ty đăng trực tiếp.
- Với CareerViet, ngày dùng để lọc và hiển thị là ngày cập nhật trên thẻ tin, không phải ngày đăng gốc; tin được làm mới có thể trông mới hơn thực tế.
- Từ khoá tiếng Việt có thể khớp nhầm khi viết tắt hoặc viết không dấu.
- Tin ẩn lương và tin không ghi kỹ năng làm giảm độ chính xác.
- Lịch sử mới bắt đầu từ ngày triển khai; biểu đồ 12 tuần sẽ dần đầy.
- Số liệu quốc tế phụ thuộc tỷ giá tham khảo, không phải tỷ giá kế toán.
- Loại hình doanh nghiệp là heuristic theo tên, có thể nhầm với công ty con, liên doanh hoặc tên viết tắt; cần đối chiếu trước khi dùng cho kết luận mạnh.
- Địa bàn phản ánh nơi tin ghi, không phải nơi làm việc thực tế của từng vị trí.
- Tín hiệu cộng đồng chỉ dựa trên RSS công khai, tối đa 20 chủ đề mới nhất mỗi chuyên mục; không phải khảo sát đại diện và không phản ánh toàn bộ bình luận.
- Không sử dụng dữ liệu để đánh giá cá nhân hay ra quyết định tuyển dụng tự động.
