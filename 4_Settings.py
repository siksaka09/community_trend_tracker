"""
หน้าตั้งค่า

- ถ้ารันในเครื่องและมีไฟล์ .env: แก้ไขค่าที่ไม่ใช่ความลับได้ตรงนี้เหมือนเดิม เขียนกลับลงไฟล์ .env จริง
  (ถาวร มีผลทุกครั้งที่รันใหม่)
- ถ้า deploy บน Streamlit Community Cloud (ไม่มี .env แต่มี st.secrets): แก้ค่าได้จากหน้านี้เช่นกัน
  แต่เป็นแบบ **session-only** — เขียนเข้า os.environ ของโปรเซสที่กำลังรันอยู่เท่านั้น (subprocess ที่ปุ่ม
  ในหน้า Pipeline เรียกจะสืบทอดค่านี้ไปด้วย เลยมีผลจริงตอนกด "รัน pipeline") แต่**ไม่ถาวร** — ถ้าแอป
  reboot/restart ค่าจะกลับไปเป็นของเดิมใน Secrets ของ Cloud เพราะ Streamlit Community Cloud ไม่มี API
  ให้แอปเขียนกลับเข้าไฟล์ secrets ของตัวเองได้ (ต้องไปตั้งถาวรที่หน้า "Manage app" > "Secrets" เท่านั้น)
  **ข้อควรระวังอีกอย่าง:** ถ้ามีคนอื่นเข้าใช้แอปเดียวกันพร้อมกัน การแก้ค่านี้จะมีผลกับทุกคนที่ใช้แอป
  อยู่ในขณะนั้น เพราะ os.environ เป็นของทั้งโปรเซส ไม่ได้แยกตามคนใช้
- ทุกกรณี: มีปุ่มดาวน์โหลด/กู้คืนไฟล์ฐานข้อมูล เพราะพื้นที่เก็บไฟล์บน cloud ฟรีมักไม่ถาวร
  (แอปรีสตาร์ทเมื่อไหร่ไฟล์ .db มีสิทธิ์หาย) แนะนำดาวน์โหลดสำรองไว้เป็นระยะถ้าใช้งานบน cloud
"""
import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values

from secrets_sync import sync_secrets_to_env, running_on_cloud_without_env

sync_secrets_to_env()

st.set_page_config(page_title="Settings", page_icon="🔧", layout="wide")
st.title("🔧 ตั้งค่า")

PROJECT_DIR = Path(__file__).parent.parent
ENV_PATH = PROJECT_DIR / ".env"
DB_PATH = PROJECT_DIR / "data" / "community_trends.db"

cloud_mode = running_on_cloud_without_env(ENV_PATH)


def _current_value(key: str, default: str = "") -> str:
    """ค่าปัจจุบันที่ 'มีผลจริง' ตอนนี้ — เช็ค os.environ ก่อน (เผื่อเคยแก้ไว้ใน session นี้แล้ว)
    ถ้าไม่มีค่อย fallback ไปที่ st.secrets (โหมด cloud) หรือ default"""
    env_val = os.environ.get(key)
    if env_val is not None and env_val != "":
        return env_val
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


def _render_settings_form(get_value):
    """เรนเดอร์ฟอร์มตั้งค่าทุกแพลตฟอร์ม ใช้ร่วมกันทั้งโหมด local และ cloud
    get_value(key, default) คือฟังก์ชันที่บอกว่าค่าปัจจุบันของแต่ละคีย์คืออะไร (ต่างกันตามโหมด)"""
    st.subheader("🐦 การตั้งค่าดึงทวีต (X / Twitter)")

    handles = st.text_area("TWITTER_HANDLES (คั่นด้วย , ไม่ต้องมี @)", value=get_value("TWITTER_HANDLES", ""))
    limit = st.number_input(
        "TWITTER_RESULTS_LIMIT (จำนวนทวีตสูงสุดต่อบัญชีต่อรอบ)",
        min_value=1, max_value=1000, value=int(get_value("TWITTER_RESULTS_LIMIT", "40") or 40),
    )
    filter_by_keyword = st.checkbox(
        "FILTER_BY_KEYWORD (กรองตั้งแต่ตอนดึง แทนที่จะกรองทีหลังด้วย AI)",
        value=str(get_value("FILTER_BY_KEYWORD", "false")).strip().lower() in ("1", "true", "yes"),
    )
    keywords = st.text_area(
        "TWITTER_KEYWORDS (คั่นด้วย , มีผลเฉพาะตอนเปิด FILTER_BY_KEYWORD)",
        value=get_value("TWITTER_KEYWORDS", ""),
    )

    st.divider()
    st.subheader("👽 การตั้งค่าดึงโพสต์ (Reddit)")

    enable_reddit = st.toggle(
        "ENABLE_REDDIT_SOURCE — เปิดใช้งานแหล่งข้อมูล Reddit",
        value=str(get_value("ENABLE_REDDIT_SOURCE", "true")).strip().lower() in ("1", "true", "yes"),
        help="ปิดไว้ = ข้ามขั้นตอนดึง Reddit ไปเลยตอนรัน run_all.py หรือกดปุ่มในหน้า Pipeline "
             "(ไม่ error แม้ยังไม่ได้ตั้งค่าคีย์เวิร์ด/subreddit)",
    )
    reddit_search_terms = st.text_area(
        "REDDIT_SEARCH_TERMS — คีย์เวิร์ดค้นหาข้ามทั้ง Reddit (คั่นด้วย ,)",
        value=get_value("REDDIT_SEARCH_TERMS", ""),
        help='ค้นหาแบบข้ามทุก subreddit เช่น "FC27,FC 27,EAFC27,EA FC 27" — ใส่หลายแบบเผื่อคนสะกดไม่เหมือนกัน',
    )
    reddit_subreddits = st.text_area(
        "REDDIT_SUBREDDITS — subreddit ที่รู้จักอยู่แล้ว (คั่นด้วย , ไม่ต้องมี r/)",
        value=get_value("REDDIT_SUBREDDITS", ""),
        help='เช่น "EASportsFC,FIFA" — ดึงโพสต์ล่าสุดจากชุมชนนี้ตรงๆ (AI จะกรอง relevance ทีหลัง)',
    )
    reddit_limit = st.number_input(
        "REDDIT_RESULTS_LIMIT (จำนวนโพสต์สูงสุดต่อคีย์เวิร์ด/ต่อ subreddit ต่อรอบ)",
        min_value=1, max_value=1000, value=int(get_value("REDDIT_RESULTS_LIMIT", "40") or 40),
    )

    st.divider()
    st.subheader("📘 การตั้งค่าดึงโพสต์ (Facebook Pages)")
    st.caption("ใช้เทียบราคา/โปรโมชั่น/engagement ระหว่างเพจร้านค้าที่รู้จักตายตัว "
               "(เช่น เพจเราเอง + เพจคู่แข่ง) ต่างจาก X/Reddit ที่ตามกระแส community กว้างๆ")

    enable_facebook = st.toggle(
        "ENABLE_FACEBOOK_SOURCE — เปิดใช้งานแหล่งข้อมูล Facebook Pages",
        value=str(get_value("ENABLE_FACEBOOK_SOURCE", "true")).strip().lower() in ("1", "true", "yes"),
        help="ปิดไว้ = ข้ามขั้นตอนดึง Facebook ไปเลยตอนรัน run_all.py หรือกดปุ่มในหน้า Pipeline "
             "(ไม่ error แม้ยังไม่ได้ตั้งค่า FB_PAGE_URLS)",
    )
    fb_page_urls = st.text_area(
        "FB_PAGE_URLS — URL เพจ Facebook ที่ต้องการติดตาม (คั่นด้วย , ต้องเป็นเพจ public)",
        value=get_value("FB_PAGE_URLS", ""),
        help='เช่น "https://www.facebook.com/mypage,https://www.facebook.com/competitorpage"',
    )
    fb_posts_per_page = st.number_input(
        "FB_POSTS_PER_PAGE (จำนวนโพสต์สูงสุดต่อเพจต่อรอบ)",
        min_value=1, max_value=500, value=int(get_value("FB_POSTS_PER_PAGE", "30") or 30),
    )

    return {
        "TWITTER_HANDLES": handles.strip(),
        "TWITTER_RESULTS_LIMIT": str(int(limit)),
        "FILTER_BY_KEYWORD": "true" if filter_by_keyword else "false",
        "TWITTER_KEYWORDS": keywords.strip(),
        "ENABLE_REDDIT_SOURCE": "true" if enable_reddit else "false",
        "REDDIT_SEARCH_TERMS": reddit_search_terms.strip(),
        "REDDIT_SUBREDDITS": reddit_subreddits.strip(),
        "REDDIT_RESULTS_LIMIT": str(int(reddit_limit)),
        "ENABLE_FACEBOOK_SOURCE": "true" if enable_facebook else "false",
        "FB_PAGE_URLS": fb_page_urls.strip(),
        "FB_POSTS_PER_PAGE": str(int(fb_posts_per_page)),
    }


if cloud_mode:
    apify_set = bool(st.secrets.get("APIFY_API_TOKEN"))
    anthropic_set = bool(st.secrets.get("ANTHROPIC_API_KEY"))
    col1, col2 = st.columns(2)
    col1.metric("APIFY_API_TOKEN", "ตั้งค่าแล้ว ✅" if apify_set else "ยังไม่ได้ตั้งค่า ⚠️")
    col2.metric("ANTHROPIC_API_KEY", "ตั้งค่าแล้ว ✅" if anthropic_set else "ยังไม่ได้ตั้งค่า ⚠️")
    st.caption("API key/token แก้ได้เฉพาะที่หน้า 'Manage app' > 'Settings' > 'Secrets' ของ Streamlit "
               "Cloud เท่านั้น (ไม่แสดง/แก้ผ่านหน้าเว็บนี้ เพื่อความปลอดภัย)")

    st.warning(
        "⚠️ **กำลังรันบน Streamlit Cloud** — ค่าที่แก้ในฟอร์มด้านล่างจะมีผล **เฉพาะช่วงที่แอปนี้ยังทำงาน "
        "อยู่เท่านั้น** (session ปัจจุบัน) เพราะ Streamlit Cloud ไม่มีทางให้แอปเขียนกลับเข้าไฟล์ Secrets "
        "ถาวรได้ ถ้าแอป **reboot/restart** ค่าจะกลับไปเป็นของเดิมที่ตั้งไว้ใน Secrets ทันที "
        "ถ้าอยากให้ค่าอยู่ถาวร ต้องไปแก้ที่หน้า Secrets ของ Cloud โดยตรง — และถ้ามีคนอื่นเข้าใช้แอปนี้ "
        "พร้อมกัน การแก้ค่าจะมีผลกับทุกคนที่ใช้อยู่ในตอนนั้นด้วย"
    )

    if "settings_overridden" in st.session_state and st.session_state["settings_overridden"]:
        st.success("✅ มีการแก้ไขค่าใน session นี้แล้ว (ใช้ได้จนกว่าแอปจะ reboot)")

    with st.form("settings_form_cloud"):
        new_values = _render_settings_form(_current_value)
        submitted = st.form_submit_button("💾 บันทึก (มีผลเฉพาะ session นี้)", type="primary")

    if submitted:
        for key, value in new_values.items():
            os.environ[key] = value
        st.session_state["settings_overridden"] = True
        st.success("บันทึกแล้ว (มีผลเฉพาะ session นี้) — กลับไปที่หน้า Pipeline แล้วกดรันได้เลย "
                   "ค่าใหม่จะถูกใช้ทันที")
        st.rerun()

elif ENV_PATH.exists():
    env_values = dotenv_values(ENV_PATH)

    st.subheader("สถานะ Key / Token")
    col1, col2 = st.columns(2)
    apify_set = (
        bool(env_values.get("APIFY_API_TOKEN")) and env_values.get("APIFY_API_TOKEN") != "your_apify_token_here"
    )
    anthropic_set = (
        bool(env_values.get("ANTHROPIC_API_KEY"))
        and env_values.get("ANTHROPIC_API_KEY") != "your_anthropic_key_here"
    )
    col1.metric("APIFY_API_TOKEN", "ตั้งค่าแล้ว ✅" if apify_set else "ยังไม่ได้ตั้งค่า ⚠️")
    col2.metric("ANTHROPIC_API_KEY", "ตั้งค่าแล้ว ✅" if anthropic_set else "ยังไม่ได้ตั้งค่า ⚠️")
    st.caption(
        "แก้ไข API key/token ได้โดยเปิดไฟล์ .env ในโปรเจกต์แล้วแก้ตรงๆ "
        "(ไม่แสดง/แก้ผ่านหน้าเว็บนี้ เพื่อความปลอดภัย)"
    )

    st.divider()

    with st.form("settings_form_local"):
        new_values = _render_settings_form(lambda key, default="": env_values.get(key, default))
        submitted = st.form_submit_button("💾 บันทึกการตั้งค่า (เขียนลงไฟล์ .env ถาวร)", type="primary")

    if submitted:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        seen = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            matched_key = None
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in new_values:
                    matched_key = key
            if matched_key:
                new_lines.append(f"{matched_key}={new_values[matched_key]}")
                seen.add(matched_key)
            else:
                new_lines.append(line)

        for key, value in new_values.items():
            if key not in seen:
                new_lines.append(f"{key}={value}")

        ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        st.success("บันทึกแล้ว — การตั้งค่าจะมีผลตั้งแต่การรัน pipeline ครั้งถัดไป")
        st.rerun()

else:
    st.error(
        f"ไม่พบไฟล์ .env ที่ {ENV_PATH} และไม่พบ Secrets — คัดลอกจาก .env.example ก่อน "
        f"(cp .env.example .env) หรือถ้ารันบน cloud ให้ตั้งค่าผ่าน Secrets ของแพลตฟอร์ม"
    )

# ============================================================
# สำรอง / กู้คืนฐานข้อมูล — สำคัญมากถ้ารันบน cloud ฟรี เพราะพื้นที่เก็บไฟล์มักไม่ถาวร
# ============================================================
st.divider()
st.subheader("💾 สำรอง / กู้คืนฐานข้อมูล")
st.caption(
    "ถ้าเว็บรันบน Cloud ฟรี (เช่น Streamlit Community Cloud) พื้นที่เก็บไฟล์อาจไม่ถาวร — "
    "ข้อมูลอาจหายได้เมื่อแอปรีสตาร์ทหรือ redeploy ใหม่ แนะนำดาวน์โหลดไฟล์นี้เก็บไว้เป็นระยะ"
)

if DB_PATH.exists():
    st.download_button(
        "⬇️ ดาวน์โหลดฐานข้อมูลปัจจุบัน (community_trends.db)",
        data=DB_PATH.read_bytes(),
        file_name="community_trends.db",
        mime="application/octet-stream",
    )
else:
    st.caption("ยังไม่มีไฟล์ฐานข้อมูล (ยังไม่เคยรัน pipeline)")

uploaded_db = st.file_uploader("⬆️ กู้คืนฐานข้อมูลจากไฟล์สำรอง (.db)", type=["db"])
if uploaded_db is not None:
    st.warning("การกู้คืนจะเขียนทับฐานข้อมูลปัจจุบันทั้งหมด")
    if st.button("ยืนยันการกู้คืน"):
        DB_PATH.parent.mkdir(exist_ok=True)
        DB_PATH.write_bytes(uploaded_db.getvalue())
        st.success("กู้คืนฐานข้อมูลเรียบร้อย")
        st.cache_data.clear()
        st.rerun()
