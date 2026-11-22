from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="laban-test-")
atexit.register(shutil.rmtree, _TMP, True)
os.environ["LABAN_DATA_DIR"] = _TMP
os.environ["LABAN_DB"] = os.path.join(_TMP, "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from laban.analytics import _comparable  # noqa: E402
from laban.company import classify_company_type  # noqa: E402
from laban.geo import parse_locations  # noqa: E402
from laban.taxonomy import (  # noqa: E402
    classify_role,
    detect_level,
    extract_facets,
    extract_skills,
    find_evidence,
    load_skills,
)
from laban.text import monthly_vnd, normalize, parse_salary  # noqa: E402
from laban.config import FX_TO_VND  # noqa: E402
from laban.sources import (  # noqa: E402
    SOURCES,
    UNAVAILABLE_SOURCES,
    amazon,
    careerviet,
    itjobs,
    joboko,
    netflix,
    nvidia,
    vieclam123,
)
from laban.social import author_hash, parse_rss  # noqa: E402
from laban.web import app  # noqa: E402


class SalaryTests(unittest.TestCase):
    def test_vietnamese_range_shares_suffix(self):
        self.assertEqual(parse_salary("20 - 30 triệu"), (20_000_000.0, 30_000_000.0, None, "month"))

    def test_dot_thousands(self):
        self.assertEqual(
            parse_salary("50.000.000 - 70.000.000 VND"),
            (50_000_000.0, 70_000_000.0, "VND", "month"),
        )

    def test_us_salary(self):
        self.assertEqual(
            parse_salary("$120,000 - $160,000 a year"),
            (120_000.0, 160_000.0, "USD", "year"),
        )

    def test_negotiable(self):
        self.assertEqual(parse_salary("Thương lượng"), (None, None, None, None))

    def test_decimal_comma(self):
        self.assertEqual(parse_salary("1,5 triệu"), (1_500_000.0, None, None, None))

    def test_hourly_conversion(self):
        value = monthly_vnd(26.63, "USD", "hourly", FX_TO_VND)
        self.assertEqual(value, 121_163_837.0)


class TaxonomyTests(unittest.TestCase):
    def test_normalize_strips_diacritics(self):
        self.assertEqual(normalize("Kỹ năng Tiếng Anh"), "ky nang tieng anh")

    def test_extract_skills_prefers_detail_evidence(self):
        found = extract_skills("Senior Python Developer", [], "Kinh nghiệm Python và AWS", "Docker")
        self.assertEqual(found.get("python"), 4)
        self.assertEqual(found.get("aws"), 4)
        self.assertEqual(found.get("docker"), 4)

    def test_title_is_only_a_signal(self):
        found = extract_skills("Senior Python Developer")
        self.assertEqual(found.get("python"), 3)

    def test_role_labels_are_not_skills(self):
        skills, _ = load_skills()
        for skill_id in ("sales", "accounting", "hr", "qa", "devops"):
            self.assertNotIn(skill_id, skills)
        found = extract_skills("Kế toán tổng hợp", ["Kế toán"], "Lập báo cáo tài chính")
        self.assertNotIn("accounting", found)
        self.assertIn("financial_reporting", found)

    def test_multi_city_location(self):
        self.assertEqual(
            set(parse_locations("Hồ Chí Minh, Hà Nội")),
            {"TP. Hồ Chí Minh", "Hà Nội"},
        )
        self.assertEqual(parse_locations("Việt Nam"), [])

    def test_company_ownership(self):
        self.assertEqual(classify_company_type("Viettel Group"), "state")
        self.assertEqual(classify_company_type("LG CNS Việt Nam"), "fdi")
        self.assertEqual(classify_company_type("Navigos Search's Client"), "agency")
        self.assertEqual(classify_company_type("ACME Ltd"), "unknown")

    def test_role_classification(self):
        self.assertEqual(classify_role("Kế toán tổng hợp"), "finance")
        self.assertEqual(classify_role("Kỹ sư xây dựng cầu đường"), "civil")
        self.assertEqual(classify_role("Chuyên viên nhân sự"), "hr")
        self.assertEqual(classify_role("IP Network Engineer"), "devops")
        self.assertEqual(classify_role("Radio Network Planning Engineer"), "devops")
        self.assertEqual(classify_role("Remote - Cyber-Security Manager"), "security")
        self.assertEqual(classify_role("Senior DBA", "Database Administrator"), "data")
        self.assertEqual(classify_role("Kỹ Thuật Điện/Điện Tử"), "mech_elec")
        self.assertEqual(classify_role("Tư Vấn Pháp Lý"), "legal")
        self.assertEqual(classify_role("Nhân Viên QC", "Đảm Bảo Chất Lượng/Kiểm Soát Chất Lượng"), "quality")
        self.assertEqual(classify_role("Thiết Kế Kiến Trúc", "Thiết Kế Kiến Trúc/Họa Viên Kiến Trúc"), "civil")
        self.assertEqual(classify_role("Anthropic Research Resident"), "ai_ml")
        self.assertEqual(classify_role("Research Assistant"), "research")
        self.assertEqual(classify_role("Senior Quantitative Researcher"), "research")
        self.assertEqual(classify_role("Strategy & Operations Lead, France"), "strategy")
        self.assertEqual(classify_role("Head of PMO, Workplace"), "strategy")
        self.assertEqual(classify_role("Senior Engineering Manager"), "software")
        self.assertEqual(classify_role("Data Engineering Manager, IO/Devices"), "data")
        self.assertEqual(classify_role("HR-Manager"), "hr")
        self.assertEqual(classify_role("Accounting Manager"), "finance")
        self.assertEqual(classify_role("Recruiter, Communications"), "hr")
        self.assertEqual(classify_role("Controls Engineer, BMS & EPMS"), "mech_elec")
        self.assertEqual(classify_role("HR Director Vietnam", "Nhân Sự Tổng Hợp"), "hr")
        self.assertEqual(classify_role("Restaurant Manager", "Quản Lý F&B"), "other")
        self.assertEqual(classify_role("Manager, Forward Deployed Engineering"), "software")
        self.assertEqual(classify_role("Product Delivery Manager (EdTech)"), "product")
        self.assertEqual(classify_role("Điều Phối Chương Trình ESL Mầm Non", "Nghiên Cứu Học Thuật"), "other")
        self.assertEqual(classify_role("Digital Customer Experience Advisor", "Chuyển Đổi Số"), "customer")
        self.assertEqual(classify_role("Đầu Tư (Chuyên Viên - Phó Phòng)", "Kế hoạch/Tư Vấn Doanh Nghiệp"), "finance")

    def test_discipline_is_knowledge_not_skill(self):
        facets = extract_facets(
            "Kỹ sư điện",
            [],
            "Tốt nghiệp chuyên ngành Điện/Điện tử. Thành thạo PLC và SCADA.",
            "",
        )
        self.assertNotIn("electrical", facets["skills"])
        self.assertEqual(facets["knowledge"].get("electrical"), 4)
        self.assertEqual(facets["skills"].get("plc"), 4)

    def test_product_context_does_not_create_skill(self):
        facets = extract_facets(
            "Category Manager - Trading Cards",
            [],
            "",
            "STOCKX is a leader focused on sneakers, apparel, accessories, electronics, collectibles and trading cards.",
        )
        self.assertEqual(facets["skills"], {})
        self.assertEqual(facets["knowledge"], {})

    def test_product_category_is_not_knowledge(self):
        for text in (
            "Requirements: sales experience within consumer electronics or premium hardware retail.",
            "Requirements: 5 years of experience in electronic warfare procurement.",
        ):
            facets = extract_facets("Senior Buyer", [], text, "")
            self.assertNotIn("electrical", facets["knowledge"])
            self.assertNotIn("electrical", facets["skills"])

    def test_degree_field_is_knowledge(self):
        facets = extract_facets(
            "Embedded Software Engineer",
            [],
            "Bachelor degree in Electrical Engineering. 3 years experience with Python and C/C++.",
            "",
        )
        self.assertNotIn("electrical", facets["skills"])
        self.assertIn("electrical", facets["knowledge"])
        self.assertEqual(facets["skills"].get("python"), 4)

    def test_level_detection(self):
        self.assertEqual(detect_level("Senior Backend Engineer"), "senior")
        self.assertEqual(detect_level("Thực tập sinh Marketing"), "intern")

    def test_evidence_comes_from_sentences(self):
        text = "Mô tả chung.\nỨng viên có kinh nghiệm Python và SQL. Ưu tiên biết Docker."
        self.assertTrue(any("Python" in line for line in find_evidence("python", text)))
        self.assertEqual(find_evidence("python", "Không có kỹ năng này"), [])


class SocialTests(unittest.TestCase):
    FORUM = {"forum_id": "91", "label": "Lập trình / CNTT", "topic": "it"}

    RSS = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0" xmlns:slash="http://purl.org/rss/1.0/modules/slash/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <title>Tuyển dụng Backend Python, SQL</title>
          <link>https://voz.vn/t/tuyen-dung-backend-python.12345/</link>
          <description><![CDATA[<p>Yêu cầu Python và SQL, làm việc tại Hà Nội.</p>]]></description>
          <pubDate>Wed, 19 Nov 2026 10:00:00 +0000</pubDate>
          <slash:comments>7</slash:comments>
          <dc:creator>alice</dc:creator>
        </item>
        <item>
          <title>Hỏi về lộ trình học tiếng Anh cho người mất gốc</title>
          <link>https://voz.vn/t/hoi-lo-trinh-hoc-tieng-anh.67890/</link>
          <description><![CDATA[<p>Mình mất gốc tiếng Anh, nên bắt đầu từ đâu?</p>]]></description>
          <pubDate>Tue, 18 Nov 2026 09:00:00 +0000</pubDate>
          <slash:comments>3</slash:comments>
          <dc:creator>bob</dc:creator>
        </item>
      </channel>
    </rss>"""

    def test_parse_rss_separates_job_ads_and_hashes_authors(self):
        records = parse_rss(self.RSS, self.FORUM)
        self.assertEqual(len(records), 2)
        job, question = records
        self.assertEqual(job["thread_id"], 12345)
        self.assertEqual(job["is_job_ad"], 1)
        self.assertEqual(question["is_job_ad"], 0)
        self.assertIn("python", job["skills"])
        self.assertIn("it", job["topics"])
        self.assertNotEqual(job["author_hash"], "alice")
        self.assertEqual(len(job["author_hash"]), 16)
        self.assertNotIn("alice", json.dumps(records, ensure_ascii=False))

    def test_author_hash_is_stable_and_salted(self):
        self.assertEqual(author_hash("alice"), author_hash("alice"))
        self.assertNotEqual(author_hash("alice"), "alice")


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_pages_render(self):
        for path in ("/", "/ky-nang", "/vi-tri", "/cntt", "/tin-hieu-cong-dong", "/nguon", "/bao-cao", "/sach-lat"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("La Bàn Nghề", response.text)

    def test_flipbook_page_has_reader_controls(self):
        response = self.client.get("/sach-lat")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fb-book", response.text)
        self.assertIn("Sách lật", response.text)

    def test_method_lists_unavailable_sources(self):
        response = self.client.get("/api/method")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["source_list"]), len(SOURCES))
        self.assertTrue(data["unavailable_sources"])

    def test_it_page_and_api_shape(self):
        response = self.client.get("/cntt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("it-matrix", response.text)
        data = self.client.get("/api/it", params={"scope": "vn", "days": 30}).json()
        self.assertEqual(len(data["roles"]), 7)
        self.assertIn("kpis", data)
        self.assertIn("matrix", data)
        self.assertIn("contents", data)
        self.assertIn("evidence", data)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_empty_overview_shape(self):
        response = self.client.get("/api/overview", params={"scope": "vn", "days": 30})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpis", data)
        self.assertIn("top_skills", data)
        self.assertIn("latest_jobs", data)

    def test_export_is_json(self):
        response = self.client.get("/api/export", params={"scope": "vn", "days": 30})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.text)
        self.assertEqual(data["scope"], "vn")

    def test_invalid_scope_falls_back(self):
        response = self.client.get("/api/overview", params={"scope": "../etc", "days": 9999})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["days"], 365)

    def test_social_overview_shape(self):
        response = self.client.get("/api/social/overview", params={"days": 30, "forum": "all"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpis", data)
        self.assertIn("topics", data)
        self.assertIn("hot_threads", data)
        self.assertEqual(len(data["forums_meta"]), 4)


class AnalyticsTests(unittest.TestCase):
    def test_growth_is_hidden_when_previous_window_is_too_thin(self):
        self.assertFalse(_comparable(1350, 38))
        self.assertTrue(_comparable(100, 60))
        self.assertFalse(_comparable(100, 10))


class SourceTests(unittest.TestCase):
    def test_registry_count(self):
        self.assertEqual(len(SOURCES), 17)
        self.assertEqual(len(SOURCES) - 6, 11)

    def test_unavailable_platforms_are_documented(self):
        ids = {item["id"] for item in UNAVAILABLE_SOURCES}
        self.assertTrue(
            {"topcv", "vieclam24h", "jobsgo", "careerlink", "microsoft", "google", "apple"} <= ids
        )
        for item in UNAVAILABLE_SOURCES:
            self.assertTrue(item["label"] and item["url"].startswith("https://") and item["reason"])

    def test_amazon_posted_date(self):
        self.assertEqual(amazon._posted_date("November 20, 2026"), "2026-11-20")
        self.assertEqual(amazon._posted_date("Nov 3, 2026"), "2026-11-03")
        self.assertIsNone(amazon._posted_date("Posted 3 Days Ago"))

    def test_netflix_posting_date(self):
        self.assertEqual(netflix._posting_date("11-20-2026"), "2026-11-20")
        self.assertIsNone(netflix._posting_date("2026-11-20"))

    def test_careerviet_card_and_detail(self):
        from bs4 import BeautifulSoup

        card_html = """
        <div class="job-item">
          <div class="title"><h2><a class="job_link" data-id="ABC123"
            href="/vi/tim-viec-lam/ky-su.ABC123.html" title="Kỹ sư phần mềm">Kỹ sư phần mềm</a></h2></div>
          <a class="company-name">Công ty ABC</a>
          <div class="salary">Lương: 20 - 30 Triệu VND</div>
          <div class="location"><ul><li>Hà Nội</li></ul></div>
          <div class="time"><ul><li><time>31-12-2026</time></li><li><time>20-11-2026</time></li></ul></div>
          <ul class="welfare"><li>CNTT / Phần mềm</li></ul>
        </div>
        """
        card = careerviet._parse_card(BeautifulSoup(card_html, "lxml").select_one(".job-item"))
        self.assertEqual(card["id"], "ABC123")
        self.assertEqual(card["posted"], "2026-11-20")
        self.assertEqual(card["location"], "Hà Nội")
        self.assertEqual(card["category"], "CNTT / Phần mềm")

        detail_html = """
        <section class="job-detail-content">
          <div class="detail-row"><h2 class="detail-title">Mô tả Công việc</h2><div><ul><li>Viết API</li></ul></div></div>
          <div class="detail-row"><h2 class="detail-title">Yêu Cầu Công Việc</h2><div><ul><li>Python</li><li>SQL</li></ul></div></div>
        </section>
        """
        detail = careerviet._parse_detail(detail_html)
        self.assertIn("Viết API", detail["description"])
        self.assertIn("Python", detail["requirements"])

    def test_itjobs_card_and_detail(self):
        from bs4 import BeautifulSoup

        card_html = """
        <a class="jp_job_post_link" href="/vi/job/88817/head-of-information-security">
          <div class="jp_job_post_detail_cont">
            <h3>Head of Information Security</h3>
            <p>VPBank Securities (VPBS)</p>
            <ul>
              <li><i class="fa fa-map-marker"></i><span class="color-black font-size-20">Hai Bà Trưng, Hà Nội</span></li>
              <li><i class="fa fa-usd j-usd"></i><span class="color-black font-size-20">Thỏa Thuận</span></li>
              <li><i class="fa fa-clock-o j-clock"></i><span>Toàn thời gian</span></li>
              <li><i class="fa fa-suitcase j-suitcase"></i><span>Quản lý</span></li>
            </ul>
          </div>
          <div class="color-orange"><i class="fa fa-calendar j-calendar"></i> Ngày Đăng: 21/11/2026</div>
          <div class="jp_job_post_keyword_wrapper">
            <span class="color-black skills-hover">Kỹ năng:</span>
            SIEM, Cyber Security, Information Security, API
          </div>
        </a>
        """
        job = itjobs._card(BeautifulSoup(card_html, "lxml").select_one("a.jp_job_post_link"))
        self.assertEqual(job["external_id"], "88817")
        self.assertEqual(job["title"], "Head of Information Security")
        self.assertEqual(job["location"], "Hai Bà Trưng, Hà Nội")
        self.assertEqual(job["posted_at"], "2026-11-21")
        self.assertEqual(job["level"], "manager")
        self.assertIn("SIEM", job["tags"])
        self.assertIn("API", job["tags"])

        detail_html = """
        <div class="job-description-section">
          <h2>Mô tả công việc</h2>
          <div class="jp_overview_wrapper"><p>Thiết kế hệ thống bảo mật.</p></div>
        </div>
        <div class="job-requirement-section">
          <h2>Yêu cầu công việc</h2>
          <div class="jp_overview_wrapper"><ul><li>Python</li><li>SIEM</li></ul></div>
        </div>
        <ul class="tech-skills-detail-page"><li>SIEM</li><li>API</li></ul>
        """
        detail = itjobs._parse_detail(detail_html)
        self.assertIn("Thiết kế hệ thống bảo mật", detail["description"])
        self.assertIn("Python", detail["requirements"])
        self.assertIn("API", detail["tags"])

    def test_vieclam123_detail(self):
        html = """
        <div class="q-detail-job-left-header">
          <p class="q-detail-job-left-header-title">Kỹ sư phần mềm</p>
          <a class="q-detail-job-left-header-com">Công ty ABC</a>
          <p class="q-detail-job-left-header-date-v2">31/12/2026</p>
        </div>
        <div class="q-detail-job-left-info">
          <div class="q-detail-job-left-div">
            <p class="q-detail-job-left-div-title">MÔ TẢ CÔNG VIỆC</p>
            <p class="q-detail-job-left-div-content">Viết API</p>
          </div>
          <div class="q-detail-job-left-div">
            <p class="q-detail-job-left-div-title">YÊU CẦU CÔNG VIỆC</p>
            <p class="q-detail-job-left-div-content">Python và SQL</p>
          </div>
        </div>
        <div class="q-detail-job-info-v2-column">
          <p class="q-detail-job-info-title">Mức lương</p>
          <p class="q-detail-job-info-des">20 - 30 triệu</p>
        </div>
        <div class="q-detail-job-info-v2-column">
          <p class="q-detail-job-info-title">Ngày đăng tin</p>
          <p class="q-detail-job-info-des">20/11/2026</p>
        </div>
        """
        detail = vieclam123._parse_detail(html)
        self.assertEqual(detail["title"], "Kỹ sư phần mềm")
        self.assertEqual(detail["expires"], "31/12/2026")
        self.assertEqual(detail["info"]["ngay dang tin"], "20/11/2026")
        self.assertIn("Viết API", detail["description"])
        self.assertIn("Python", detail["requirements"])

    def test_joboko_detail(self):
        html = """
        <html><body>
        <script type="application/ld+json">{
          "@type": "JobPosting",
          "title": "Kỹ sư AI",
          "description": "<h3>Mô tả công việc</h3><ul><li>Huấn luyện mô hình</li></ul><h3>Yêu cầu</h3><ul><li>Python</li></ul>",
          "datePosted": "2026-11-20",
          "validThrough": "2026-12-20T17:00:00+07:00",
          "hiringOrganization": {"name": "Công ty ABC"},
          "baseSalary": {"currency": "VND", "value": {"value": "20 - 30 triệu VND", "unitText": "MONTH"}},
          "jobLocation": [{"address": {"addressLocality": "Hà Nội"}}]
        }</script>
        <div class="int-job-detail-right">
          <div class="item-content"><div class="item-label">Vị trí:</div><div class="item-text">Nhân viên</div></div>
          <div class="item-content"><div class="item-label">Hình thức làm việc:</div><div class="item-text">Toàn thời gian</div></div>
        </div>
        </body></html>
        """
        detail = joboko._parse_detail(html)
        self.assertEqual(detail["title"], "Kỹ sư AI")
        self.assertEqual(detail["company"], "Công ty ABC")
        self.assertEqual(detail["posted"], "2026-11-20")
        self.assertEqual(detail["expires"], "2026-12-20")
        self.assertEqual(detail["location"], "Hà Nội")
        self.assertEqual(detail["level"], "Nhân viên")
        self.assertEqual(detail["salary"][:2], (20000000.0, 30000000.0))
        self.assertIn("Huấn luyện", detail["description"])
        self.assertIn("Python", detail["requirements"])

    def test_nvidia_relative_date(self):
        from datetime import date, timedelta

        today = date.today()
        self.assertEqual(nvidia._relative_date("Posted Today"), today.isoformat())
        self.assertEqual(
            nvidia._relative_date("Posted 3 Days Ago"),
            (today - timedelta(days=3)).isoformat(),
        )
        self.assertIsNone(nvidia._relative_date(""))


if __name__ == "__main__":
    unittest.main()
