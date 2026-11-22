from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

from .config import TAXONOMY_DIR, TOP_COMPANIES, TOP_LEVEL_COMPANIES
from .text import normalize

_WORD_START = r"(?<![a-z0-9])"
_ALIAS_TAIL = r"s?(?![a-z0-9])"


def _alias_pattern(alias: str) -> str:
    alias = alias.strip()
    escaped = re.escape(alias)
    pre = _WORD_START if alias and alias[0].isalnum() else ""
    post = ""
    if alias and alias[-1].isalnum():
        post = _ALIAS_TAIL if len(alias) >= 3 else r"(?![a-z0-9])"
    return pre + escaped + post


class Skill:
    __slots__ = ("id", "label", "group", "kind", "patterns")

    def __init__(
        self,
        id: str,
        label: str,
        group: str,
        kind: str,
        patterns: List[re.Pattern],
    ):
        self.id = id
        self.label = label
        self.group = group
        self.kind = kind
        self.patterns = patterns


@lru_cache(maxsize=1)
def load_skills() -> Tuple[Dict[str, Skill], Dict[str, str]]:
    data = json.loads((TAXONOMY_DIR / "skills.json").read_text(encoding="utf-8"))
    groups = data["groups"]
    skills = {}
    for item in data["skills"]:
        patterns = []
        for alias in item.get("aliases", []):
            alias = alias.strip()
            if not alias or len(alias) < 2:
                continue
            patterns.append(re.compile(_alias_pattern(normalize(alias))))
        for raw in item.get("patterns", []):
            patterns.append(re.compile(raw))
        skills[item["id"]] = Skill(
            item["id"], item["label"], item["group"], item.get("kind", "skill"), patterns
        )
    return skills, groups


_BULLET_RE = re.compile(r"^[#>*•▪◦·\-–—]+\s*")
_HEADING_RE = re.compile(
    r"^(?:(?:your|required|job|key|minimum|preferred|basic)\s+)*"
    r"(?:requirements?|qualifications?|skills?(?:/traits/abilities)?(?: (?:and|&) experience)?"
    r"|education(?:/training)?(?: required)?|experience(?: required)?"
    r"|what you(?:'|’)ll need|what we(?:'|’)re looking for|about you"
    r"|must haves?|nice to haves?|yeu cau(?: cong viec)?|ky nang(?: va kinh nghiem)?"
    r"|kinh nghiem|trinh do(?: chuyen mon)?|chuyen mon)$"
)
_STOP_HEADING_RE = re.compile(
    r"^(?:benefits?|what we offer|we offer|about (?:us|the company|the team)"
    r"|our (?:mission|product|products|team)|company overview|who we are"
    r"|phuc loi|quyen loi|gioi thieu(?: cong ty)?|ve chung toi|ve cong ty|mo ta cong viec)$"
)
_BOILERPLATE_CUES = (
    "equal opportunity",
    "all qualified applicants",
    "we offer",
    "benefits include",
    "health insurance",
    "401(k)",
    "about us",
    "our mission",
    "our products",
    "products include",
    "company overview",
    "who we are",
    "phuc loi",
    "quyen loi",
    "gioi thieu cong ty",
    "ve chung toi",
)
_REQUIREMENT_CUES = (
    "requirement",
    "qualification",
    "experience",
    "proficient",
    "proficiency",
    "knowledge of",
    "familiar",
    "ability to",
    "degree",
    "bachelor",
    "master",
    "tot nghiep",
    "chuyen nganh",
    "kinh nghiem",
    "thanh thao",
    "su dung",
    "hieu biet",
    "nam vung",
    "you have",
    "you bring",
    "must have",
    "yeu cau",
    "ky nang",
)
_EDUCATION_CUES = (
    "bachelor",
    "master",
    "degree",
    "tot nghiep",
    "chuyen nganh",
    "bang cap",
    "university",
    "college",
    "cao dang",
    "dai hoc",
    "thac si",
    "tien si",
    "major in",
    "majoring in",
    "education",
)
_KNOWLEDGE_CUES = _EDUCATION_CUES + (
    "knowledge of",
    "background in",
    "understanding of",
    "training in",
    "studied",
    "kien thuc",
    "hieu biet",
    "chuyen mon",
    "chuyen nganh",
    "trinh do",
    "nganh",
    "linh vuc",
    "nam vung",
)
_PRACTICE_CUES = (
    "experience with",
    "proficient",
    "proficiency",
    "knowledge of",
    "familiar",
    "hands-on",
    "thanh thao",
    "su dung",
    "kinh nghiem voi",
    "lam viec voi",
    "lap trinh",
    "cau hinh",
    "trien khai",
    "thiet ke",
    "van hanh",
    "bao tri",
)


def _line_variants(text: str) -> List[str]:
    lines: List[str] = []
    for raw in re.split(r"[\n\r]+", text or ""):
        line = _BULLET_RE.sub("", raw.strip()).strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?;])\s+", line) if len(line) > 500 else [line]
        lines.extend(part.strip() for part in parts if part.strip())
    return lines


def _is_boilerplate(text_norm: str) -> bool:
    return any(cue in text_norm for cue in _BOILERPLATE_CUES)


def _is_short_skill_line(line: str, text_norm: str) -> bool:
    if len(text_norm) > 60 or re.search(r"[.!?;:]", line):
        return False
    company_context = ("cong ty", "chung toi", "khach hang", "san pham", "dich vu", "platform", "leader", "market")
    return not any(cue in text_norm for cue in company_context)


def _requirement_lines(requirements: str, description: str) -> List[Tuple[str, str, int]]:
    found: List[Tuple[str, str, int]] = []
    seen = set()

    def add(line: str, weight: int) -> None:
        norm = normalize(line)
        if len(norm) < 2 or norm in seen or _is_boilerplate(norm):
            return
        seen.add(norm)
        found.append((line, norm, weight))

    for line in _line_variants(requirements):
        add(line, 4)

    in_section = False
    for line in _line_variants(description):
        heading = normalize(line).strip(" :")
        if _STOP_HEADING_RE.match(heading):
            in_section = False
            continue
        if _HEADING_RE.match(heading):
            in_section = True
            continue
        if in_section:
            add(line, 4)
            continue
        norm = normalize(line)
        if any(cue in norm for cue in _REQUIREMENT_CUES):
            add(line, 3)
        elif _is_short_skill_line(line, norm):
            add(line, 4)
    return found


_KNOWLEDGE_BAD_CONTEXTS = (
    "thuong mai dien tu",
    "consumer electronics",
    "electronic warfare",
)


def _knowledge_context_ok(skill: Skill, text_norm: str) -> bool:
    for pattern in skill.patterns:
        for match in pattern.finditer(text_norm):
            start = max(0, match.start() - 30)
            end = min(len(text_norm), match.end() + 30)
            context = text_norm[start:end]
            if not any(bad in context for bad in _KNOWLEDGE_BAD_CONTEXTS):
                return True
    return False


def _match_allowed(skill: Skill, text_norm: str) -> bool:
    if _is_boilerplate(text_norm):
        return False
    if skill.kind == "knowledge":
        # A discipline mentioned as a degree, major or body of knowledge
        # counts; a product category ("consumer electronics") does not.
        if not any(cue in text_norm for cue in _KNOWLEDGE_CUES):
            return False
        return _knowledge_context_ok(skill, text_norm)
    is_education = any(cue in text_norm for cue in _EDUCATION_CUES)
    has_practice = any(cue in text_norm for cue in _PRACTICE_CUES)
    if is_education and not has_practice:
        return False
    return True


def find_evidence(skill_id: str, text: str, limit: int = 2) -> List[str]:
    skills, _ = load_skills()
    skill = skills.get(skill_id)
    if not skill or not text:
        return []
    found = []
    for sentence in _line_variants(text):
        norm = normalize(sentence)
        if len(norm) < 10 or not _match_allowed(skill, norm):
            continue
        if any(p.search(norm) for p in skill.patterns):
            found.append(sentence[:300])
            if len(found) >= limit:
                break
    return found


def extract_facets(
    title: str,
    tags: Iterable[str] = (),
    requirements: str = "",
    description: str = "",
) -> Dict[str, Dict[str, int]]:
    skills, _ = load_skills()
    title_norm = normalize(title)
    tag_norm = normalize(" ".join(tags or []))
    lines = _requirement_lines(requirements or "", description or "")
    found: Dict[str, Dict[str, int]] = {"skills": {}, "knowledge": {}}
    for skill in skills.values():
        bucket = found["knowledge" if skill.kind == "knowledge" else "skills"]
        weight = 0
        # Tiêu đề chỉ đủ tín hiệu cho kỹ năng thao tác; kiến thức nền phải có
        # bằng chứng trong thẻ hoặc câu yêu cầu, tránh gắn ngành của sản phẩm.
        if skill.kind == "skill" and any(p.search(title_norm) for p in skill.patterns):
            weight = 3
        if tag_norm and any(p.search(tag_norm) for p in skill.patterns):
            if skill.kind != "knowledge" or _knowledge_context_ok(skill, tag_norm):
                weight = max(weight, 4)
        for _, norm, line_weight in lines:
            if line_weight <= weight:
                continue
            if not _match_allowed(skill, norm):
                continue
            if any(p.search(norm) for p in skill.patterns):
                weight = line_weight
                if weight >= 4:
                    break
        if weight:
            bucket[skill.id] = weight
    return found


def extract_skills(
    title: str,
    tags: Iterable[str] = (),
    requirements: str = "",
    description: str = "",
) -> Dict[str, int]:
    return extract_facets(title, tags, requirements, description)["skills"]


def extract_knowledge(
    title: str,
    tags: Iterable[str] = (),
    requirements: str = "",
    description: str = "",
) -> Dict[str, int]:
    return extract_facets(title, tags, requirements, description)["knowledge"]


@lru_cache(maxsize=1)
def load_roles() -> List[dict]:
    data = json.loads((TAXONOMY_DIR / "roles.json").read_text(encoding="utf-8"))
    return data["roles"]


@lru_cache(maxsize=1)
def role_index() -> Dict[str, dict]:
    return {r["id"]: r for r in load_roles()}


# Thứ tự quan trọng: nghề chuyên biệt trước, phần mềm chung sau.
_ROLE_ORDER = [
    "ai_ml", "data", "mobile", "qa", "quality", "devops", "security", "it_support",
    "software", "research", "strategy", "product", "design", "hr", "marketing", "sales",
    "finance", "legal", "civil", "environment", "mech_elec", "manufacturing",
    "logistics", "customer", "admin",
]

_NON_ROLE_CATEGORY_KEYS = {
    "quan ly f&b",
}

_CATEGORY_MAP = {
    "it phần mềm": "software",
    "it phan mem": "software",
    "it phần cứng & mạng": "devops",
    "it phan cung & mang": "devops",
    "phân tích dữ liệu": "data",
    "phan tich du lieu": "data",
    "phân tích thống kê dữ liệu": "data",
    "xây dựng": "civil",
    "xay dung": "civil",
    "kiến trúc/xây dựng": "civil",
    "kien truc/xay dung": "civil",
    "kỹ thuật xây dựng/cơ sở hạ tầng": "civil",
    "ky thuat xay dung/co so ha tang": "civil",
    "môi trường": "environment",
    "moi truong": "environment",
    "điện - điện tử": "mech_elec",
    "dien - dien tu": "mech_elec",
    "cơ khí & tự động hóa": "mech_elec",
    "co khi & tu dong hoa": "mech_elec",
    "cơ khí & điện lạnh": "mech_elec",
    "co khi & dien lanh": "mech_elec",
    "điện/điện tử": "mech_elec",
    "dien/dien tu": "mech_elec",
    "năng lượng & địa chất": "civil",
    "nang luong & dia chat": "civil",
    "quản lý dự án": "product",
    "quan ly du an": "product",
    "kế toán": "finance",
    "ke toan": "finance",
    "kế toán/kiểm toán": "finance",
    "ke toan/kiem toan": "finance",
    "kế toán thuế": "finance",
    "ke toan thue": "finance",
    "kiểm soát viên tài chính": "finance",
    "kiem soat vien tai chinh": "finance",
    "nhân sự/tuyển dụng": "hr",
    "nhan su/tuyen dung": "hr",
    "tuyển dụng": "hr",
    "tuyen dung": "hr",
    "công nghệ thông tin": "software",
    "cong nghe thong tin": "software",
    "marketing": "marketing",
    "thiết kế & sáng tạo": "design",
    "thiet ke & sang tao": "design",
    "nhân sự": "hr",
    "nhan su": "hr",
    "thực tập sinh": "other",
    "thuc tap sinh": "other",
    "software development": "software",
    "data analysis": "data",
    "data science": "ai_ml",
    "design": "design",
    "marketing": "marketing",
    "sales": "sales",
    "customer support": "customer",
    "finance": "finance",
    "human resources": "hr",
    "product": "product",
    "project management": "product",
    "business development": "sales",
    "writing": "marketing",
    "all others": "other",
}

# Danh mục nguồn là nhãn ngành, không phải kỹ năng. Bảng này chỉ dùng để gán nghề.
_CATEGORY_MAP.update({
    "ky thuat dien/dien tu": "mech_elec",
    "co khi tu dong hoa": "mech_elec",
    "bao tri/bao duong": "mech_elec",
    "dam bao chat luong/kiem soat chat luong/quan ly chat luong": "quality",
    "hoach dinh & quan ly san xuat": "manufacturing",
    "quy trinh & lap rap": "manufacturing",
    "nghien cuu & phat trien": "manufacturing",
    "thiet ke kien truc/hoa vien kien truc": "civil",
    "tu van phap ly": "legal",
    "quan ly quan he khach hang": "sales",
    "it support/help desk": "it_support",
    "it support": "it_support",
    "quan tri co so du lieu": "data",
    "database administrator": "data",
    "network engineer": "devops",
    "software/technical architect": "software",
    "solutions architect": "software",
    "cntt - phan mem": "software",
    "cntt - phan cung & mang": "devops",
    "phan mem may tinh": "software",
    "tiep thi truc tuyen": "marketing",
    "quan ly chuoi cung ung": "logistics",
    "project manager": "product",
    "project management": "product",
    "full-stack programming": "software",
    "front-end programming": "software",
    "software development": "software",
    "software engineering": "software",
    "devops & infrastructure": "devops",
    "applied ai": "ai_ml",
    "data science": "ai_ml",
    "data & insights": "data",
    "operations, it, & support engineering": "it_support",
    "systems, quality, & security engineering": "security",
    "customer service": "customer",
    "customer support & success": "customer",
    "user operations": "customer",
    "go to market": "sales",
    "security": "security",
    "robotics": "mech_elec",
    "consumer devices": "mech_elec",
    "technical program management": "product",
    "project/program/product management--technical": "product",
    "project/program/product management--non-tech": "product",
    "people": "hr",
    "legal": "legal",
    "finance": "finance",
    "finance & accounting": "finance",
    "product design": "design",
    "facilities, maintenance, & real estate": "mech_elec",
    "fulfillment & operations management": "logistics",
    "fulfillment / warehouse associate": "logistics",
    "marketing": "marketing",
    "partnerships": "sales",
    "product partnerships": "sales",
    "sales, advertising, & account management": "sales",
    "forward deployed engineering": "software",
    "corporate operations": "admin",
    "strategy & operations": "strategy",
    "business operations": "strategy",
    "executive operations": "strategy",
    "research": "research",
    "global affairs": "strategy",
    "product policy": "strategy",
    "openai for gov": "sales",
    "intelligence & investigations": "security",
    "product operations": "product",
    "program management": "product",
    "scrum master / agile coach": "product",
    "erp consultant": "software",
    "back-end programming": "software",
    "administrative support": "admin",
    "quan ly cong nghe thong tin": "devops",
    "quan he cong chung": "marketing",
    "quan ly & phat trien san pham": "product",
    "quan ly du an cong nghe": "product",
    "phat trien bat dong san": "civil",
    "quan ly co so vat chat": "civil",
    "thu mua": "logistics",
    "thu mua & quan tri hang ton kho": "logistics",
    "quan ly kho & phan phoi": "logistics",
    "ke hoach/tu van doanh nghiep": "strategy",
    "chung khoan": "finance",
    "quan ly quy": "finance",
    "boi thuong bao hiem": "finance",
    "luong thuong & phuc loi": "hr",
    "dao tao va phat trien": "hr",
    "dich vu khach hang": "customer",
    "dich vu sinh vien/ho tro hoc vien": "customer",
    "nghien cuu & phan tich thi truong": "marketing",
    "ky thuat hoa hoc": "manufacturing",
    "hoa hoc": "manufacturing",
    "thiet ke cong nghiep/ky thuat": "mech_elec",
    "thiet ke noi that": "design",
    "chinh sua video": "design",
    "bien tap / bao chi / truyen hinh": "marketing",
    "feature animation": "design",
})


def _role_text(value: str) -> str:
    # Titles such as "Cyber-Security" or "Network & Security" must match
    # their space-separated keywords.
    text = normalize(value)
    text = re.sub(r"[-/&,+()\[\]]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_role(title: str, category: str = "", tags: Iterable[str] = (), description: str = "") -> str:
    roles = role_index()
    title_norm = _role_text(title)
    cat_norm = _role_text(category)
    cat_key = normalize(category)
    tag_norm = _role_text(" ".join(tags or []))
    desc_norm = normalize(description[:1200]) if description else ""

    for role_id in _ROLE_ORDER:
        role = roles.get(role_id)
        if not role:
            continue
        for kw in role.get("keywords", []):
            kw_norm = _role_text(kw)
            if not kw_norm:
                continue
            if re.search(_WORD_START + re.escape(kw_norm) + r"(?![a-z0-9])", title_norm):
                return role_id

    if cat_key in _NON_ROLE_CATEGORY_KEYS:
        return "other"

    if cat_key in _CATEGORY_MAP:
        mapped = _CATEGORY_MAP[cat_key]
        if mapped != "other":
            return mapped

    for role_id in _ROLE_ORDER:
        role = roles.get(role_id)
        if not role:
            continue
        for kw in role.get("keywords", []):
            kw_norm = _role_text(kw)
            if not kw_norm:
                continue
            if re.search(_WORD_START + re.escape(kw_norm) + r"(?![a-z0-9])", cat_norm + " " + tag_norm):
                return role_id

    if any(x in desc_norm for x in ("software", "developer", "lap trinh", "backend", "frontend")):
        return "software"
    return "other"


def detect_level(title: str, raw_level: str = "") -> str:
    text = normalize(" ".join([title or "", raw_level or ""]))
    if any(x in text for x in ("thuc tap", "intern", "internship", "co-op")):
        return "intern"
    if any(x in text for x in ("fresher", "moi tot nghiep", "graduate")):
        return "fresher"
    if any(x in text for x in ("junior", "jr ")):
        return "junior"
    if any(x in text for x in ("senior", "sr ", "chuyen gia", "expert", "principal", "staff")):
        return "senior"
    if any(x in text for x in ("manager", "truong phong", "giam doc", "director", "head of", "lead ", "truong nhom")):
        return "manager"
    return "mid"


LEVEL_LABELS = {
    "intern": "Thực tập",
    "fresher": "Fresher",
    "junior": "Junior",
    "mid": "Mid",
    "senior": "Senior",
    "manager": "Quản lý",
}


def company_tier(company: str) -> int:
    name = normalize(company)
    for top in TOP_LEVEL_COMPANIES:
        if top in name:
            return 2
    for known in TOP_COMPANIES:
        if known in name:
            return 1
    return 0


def plan_for(role_id: str) -> List[str]:
    role = role_index().get(role_id)
    if not role:
        return []
    return role.get("plan", [])[:3]
