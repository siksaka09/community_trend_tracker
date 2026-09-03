"""
Utility เดียว ใช้ sync ค่าจาก st.secrets (ตอน deploy บน Streamlit Community Cloud) เข้า os.environ
เพื่อให้ db.py / scrape_x.py / ai_analyze.py / analyze.py ที่อ่านค่าด้วย os.getenv() เดิมทำงานได้เหมือนกัน
ทั้งตอนรันในเครื่อง (อ่านจาก .env ผ่าน python-dotenv) และตอนรันบน cloud (อ่านจาก secrets.toml)
ไม่ต้องแก้โค้ด scrape_x.py / ai_analyze.py / analyze.py แม้แต่บรรทัดเดียว

วิธีใช้: import แล้วเรียก sync_secrets_to_env() ก่อนจุดที่ต้องใช้ค่าพวกนี้ (ต้นไฟล์ของแต่ละหน้าก็พอ)
"""
import os

import streamlit as st

_SECRET_KEYS = [
    "ANTHROPIC_API_KEY",
    "APIFY_API_TOKEN",
    "TWITTER_HANDLES",
    "TWITTER_KEYWORDS",
    "FILTER_BY_KEYWORD",
    "TWITTER_RESULTS_LIMIT",
    "ENABLE_REDDIT_SOURCE",
    "REDDIT_SEARCH_TERMS",
    "REDDIT_SUBREDDITS",
    "REDDIT_RESULTS_LIMIT",
]


def sync_secrets_to_env():
    """คัดลอกค่าจาก st.secrets เข้า os.environ เฉพาะคีย์ที่ os.environ ยังไม่มีค่า
    (ถ้ารันในเครื่องและมี .env อยู่แล้ว จะไม่ทับค่าจาก .env)"""
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in _SECRET_KEYS:
        try:
            value = secrets[key]
        except (KeyError, FileNotFoundError):
            continue
        if not os.environ.get(key):
            os.environ[key] = str(value)


def running_on_cloud_without_env(env_path) -> bool:
    """เช็คคร่าวๆ ว่ากำลังรันแบบไม่มีไฟล์ .env แต่มี st.secrets ให้ใช้แทน (เช่นตอน deploy บน cloud)"""
    if env_path.exists():
        return False
    try:
        return len(st.secrets) > 0
    except Exception:
        return False
