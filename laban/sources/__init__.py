from . import (
    amazon,
    anthropic,
    arbeitnow,
    careerviet,
    himalayas,
    itjobs,
    itviec,
    jobicy,
    joboko,
    netflix,
    nvidia,
    openai,
    remoteok,
    remotive,
    vieclam123,
    vietnamworks,
    weworkremotely,
)

SOURCES = {
    "remotive": remotive,
    "arbeitnow": arbeitnow,
    "remoteok": remoteok,
    "jobicy": jobicy,
    "himalayas": himalayas,
    "weworkremotely": weworkremotely,
    "amazon": amazon,
    "nvidia": nvidia,
    "netflix": netflix,
    "openai": openai,
    "anthropic": anthropic,
    "vietnamworks": vietnamworks,
    "itviec": itviec,
    "itjobs": itjobs,
    "careerviet": careerviet,
    "vieclam123": vieclam123,
    "joboko": joboko,
}

VN_SOURCES = {"vietnamworks", "itviec", "itjobs", "careerviet", "vieclam123", "joboko"}

UNAVAILABLE_SOURCES = [
    {
        "id": "topcv",
        "label": "TopCV",
        "url": "https://www.topcv.vn",
        "reason": "Cloudflare trả 403 cho mọi truy cập tự động; không giả User-Agent để vượt chặn.",
    },
    {
        "id": "vieclam24h",
        "label": "Vieclam24h",
        "url": "https://vieclam24h.vn",
        "reason": "Chặn User-Agent không phải trình duyệt (403); không giả trình duyệt để vượt chặn.",
    },
    {
        "id": "jobsgo",
        "label": "JobsGO",
        "url": "https://jobsgo.vn",
        "reason": "Trang danh sách trả 403 với truy cập tự động; không giả trình duyệt để vượt chặn.",
    },
    {
        "id": "careerlink",
        "label": "CareerLink",
        "url": "https://www.careerlink.vn",
        "reason": "Danh sách và trang chi tiết trả trang xác nhận robot với truy cập tự động; không lách kiểm tra.",
    },
    {
        "id": "microsoft",
        "label": "Microsoft Careers",
        "url": "https://jobs.careers.microsoft.com",
        "reason": "API công khai không trả JSON và tên miền API không khớp chứng chỉ TLS; chưa có nguồn ổn định.",
    },
    {
        "id": "google",
        "label": "Google Careers",
        "url": "https://www.google.com/about/careers/applications/jobs/results/",
        "reason": "Danh sách việc làm tải bằng JavaScript, không có API công khai ổn định.",
    },
    {
        "id": "apple",
        "label": "Apple Jobs",
        "url": "https://jobs.apple.com",
        "reason": "API tìm kiếm trả 401, cần phiên trình duyệt.",
    },
    {
        "id": "topdev",
        "label": "TopDev",
        "url": "https://topdev.vn",
        "reason": "Trang danh sách không phản hồi truy cập tự động (timeout, kết nối bị đóng); không giả trình duyệt để vượt chặn.",
    },
    {
        "id": "glints",
        "label": "Glints",
        "url": "https://glints.com",
        "reason": "Trang danh sách trả 403 với truy cập tự động; không giả trình duyệt để vượt chặn.",
    },
    {
        "id": "linkedin",
        "label": "LinkedIn Jobs",
        "url": "https://www.linkedin.com/jobs/",
        "reason": "Kết nối tự động bị đóng, trang yêu cầu đăng nhập; không dùng tài khoản hoặc lách chặn.",
    },
    {
        "id": "indeed",
        "label": "Indeed",
        "url": "https://www.indeed.com",
        "reason": "Trang danh sách trả 403 với truy cập tự động; không giả trình duyệt để vượt chặn.",
    },
]

