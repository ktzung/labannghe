from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LABAN_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("LABAN_DB", DATA_DIR / "laban.db"))
TAXONOMY_DIR = ROOT / "taxonomy"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
RAW_DIR = DATA_DIR / "raw"
VOZ_RSS_DIR = Path(os.environ.get("LABAN_VOZ_RSS_DIR", DATA_DIR / "voz_rss"))
VOZ_MODE = os.environ.get("LABAN_VOZ_MODE", "auto").lower()

USER_AGENT = os.environ.get(
    "LABAN_UA",
    "LaBanNghe/0.1 (student career research; +https://github.com/ktdung/labannghe)",
)
CONTACT = os.environ.get("LABAN_CONTACT", "ktdung@tlu.edu.vn")

REQUEST_DELAY = float(os.environ.get("LABAN_DELAY", "1.2"))
TIMEOUT = float(os.environ.get("LABAN_TIMEOUT", "40"))
MAX_RETRIES = int(os.environ.get("LABAN_RETRIES", "2"))
# httpx 0.27 misparses NO_PROXY entries such as "[::1]"; opt in only when a proxy is required.
TRUST_ENV = os.environ.get("LABAN_TRUST_ENV") == "1"

# Tỷ giá quy đổi tham khảo, chỉ dùng để so sánh tương đối.
FX_TO_VND = {
    "VND": 1.0,
    "USD": 26300.0,
    "EUR": 28500.0,
    "GBP": 33300.0,
    "AUD": 17000.0,
    "CAD": 19000.0,
    "SGD": 19500.0,
    "JPY": 170.0,
    "KRW": 18.5,
}

DEFAULT_WINDOW_DAYS = 30
RAW_KEEP_DAYS = 21

TOP_COMPANIES = [
    "vng", "fpt", "viettel", "vnpt", "vinai", "vinbigdata", "vinfast", "momo", "zalo",
    "tiki", "shopee", "grab", "lazada", "be group", "vib", "techcombank", "mb bank",
    "vietcombank", "bidv", "acb", "vpbank", "hoa phat", "coteccons", "ricons",
    "vinaconex", "evn", "petrovietnam", "vinamilk", "masan", "unilever", "nestle",
    "samsung", "lg", "bosch", "intel", "microsoft", "google", "amazon", "apple",
    "meta", "netflix", "stripe", "shopify", "gitlab", "automattic", "canonical",
    "mozilla", "reddit", "coinbase", "binance", "kms technology", "nashtech", "axon",
    "elca", "tma solutions", "sacombank", "vietinbank", "agribank", "vpbank",
    "dek technologies", "cmc global", "rikkeisoft", "bizfly", "base.vn", "got it",
    "topica", "edulive", "vus", "apollo", "iig", "nielsen", "grab", "foodpanda",
]

TOP_LEVEL_COMPANIES = {
    "vng", "fpt", "viettel", "vinai", "vinbigdata", "vinfast", "momo", "zalo",
    "shopee", "grab", "samsung", "bosch", "intel", "microsoft", "google", "amazon",
    "apple", "meta", "netflix", "stripe", "shopify", "gitlab", "canonical", "binance",
    "kms technology", "nashtech", "axon", "elca",
}
