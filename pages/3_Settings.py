"""
หน้าตั้งค่า

- ถ้ารันในเครื่องและมีไฟล์ .env: แก้ไขค่าที่ไม่ใช่ความลับได้ตรงนี้เหมือนเดิม
  (X: handles/keywords/filter/limit, Reddit: search terms/subreddits/limit/เปิดปิด)
- ถ้า deploy บน Streamlit Community Cloud (ไม่มี .env แต่มี st.secrets): แสดงค่าปัจจุบันแบบอ่านอย่างเดียว
  พร้อมคำแนะนำให้ไปแก้ที่หน้าตั้งค่า secrets ของแอปบน cloud แทน (เพราะเขียนไฟล์บน cloud ฟรีไม่ persistent)
- ทุกกรณี: มีปุ่มดาวน์โหลด/กู้คืนไฟล์ฐานข้อมูล เพราะพื้นที่เก็บไฟล์บน cloud ฟรีมักไม่ถาวร
  (แอปรีสตาร์ทเมื่อไหร่ไฟล์ .db มีสิทธิ์หาย) แนะนำดาวน์โหลดสำรองไว้เป็นระยะถ้าใช้งานบน cloud
"""
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

if cloud_mode:
    st.info(
        "ตรวจพบว่ากำลังรันแบบไม่มีไฟล์ `.env` แต่มีการตั้งค่าผ่าน Secrets ของแพลตฟอร์ม (เช่น Streamlit "
        "Community Cloud) — หน้านี้จะแสดงค่าปัจจุบันแบบอ่านอย่างเดียว **แก้ไขได้ที่หน้า "
        "'Manage app' > 'Settings' > 'Secrets' ของแอปบนคลาวด์เท่านั้น** เพราะการเขียนไฟล์บนคลาวด์ฟรี "
        "มักไม่ถาวร"
    )
    st.subheader("ค่าปัจจุบัน (จาก Secrets)")

    col1, col2 = st.columns(2)
    apify_set = bool(st.secrets.get("APIFY_API_TOKEN"))
    anthropic_set = bool(st.secrets.get("ANTHROPIC_API_KEY"))
    col1.metric("APIFY_API_TOKEN", "ตั้งค่าแล้ว ✅" if apify_set else "ยังไม่ได้ตั้งค่า ⚠️")
    col2.metric("ANTHROPIC_API_KEY", "ตั้งค่าแล้ว ✅" if anthropic_set else "ยังไม่ได้ตั้งค่า ⚠️")

    st.markdown("**X (Twitter)**")
    st.write(f"TWITTER_HANDLES: {st.secrets.get('TWITTER_HANDLES', '(ยังไม่ตั้งค่า)')}")
    st.write(f"TWITTER_KEYWORDS: {st.secrets.get('TWITTER_KEYWORDS', '(ยังไม่ตั้งค่า)')}")
    st.write(f"FILTER_BY_KEYWORD: {st.secrets.get('FILTER_BY_KEYWORD', 'false')}")
    st.write(f"TWITTER_RESULTS_LIMIT: {st.secrets.get('TWITTER_RESULTS_LIMIT', '40')}")

    st.markdown("**Reddit**")
    st.write(f"ENABLE_REDDIT_SOURCE: {st.secrets.get('ENABLE_REDDIT_SOURCE', 'true')}")
    st.write(f"REDDIT_SEARCH_TERMS: {st.secrets.get('REDDIT_SEARCH_TERMS', '(ยังไม่ตั้งค่า)')}")
    st.write(f"REDDIT_SUBREDDITS: {st.secrets.get('REDDIT_SUBREDDITS', '(ยังไม่ตั้งค่า)')}")
    st.write(f"REDDIT_RESULTS_LIMIT: {st.secrets.get('REDDIT_RESULTS_LIMIT', '40')}")

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

    with st.form("settings_form"):
        st.subheader("🐦 การตั้งค่าดึงทวีต (X / Twitter)")

        handles = st.text_area(
            "TWITTER_HANDLES (คั่นด้วย , ไม่ต้องมี @)",
            value=env_values.get("TWITTER_HANDLES", ""),
        )
        limit = st.number_input(
            "TWITTER_RESULTS_LIMIT (จำนวนทวีตสูงสุดต่อบัญชีต่อรอบ)",
            min_value=1,
            max_value=1000,
            value=int(env_values.get("TWITTER_RESULTS_LIMIT") or 40),
        )
        filter_by_keyword = st.checkbox(
            "FILTER_BY_KEYWORD (กรองตั้งแต่ตอนดึง แทนที่จะกรองทีหลังด้วย AI)",
            value=str(env_values.get("FILTER_BY_KEYWORD", "false")).strip().lower() in ("1", "true", "yes"),
        )
        keywords = st.text_area(
            "TWITTER_KEYWORDS (คั่นด้วย , มีผลเฉพาะตอนเปิด FILTER_BY_KEYWORD)",
            value=env_values.get("TWITTER_KEYWORDS", ""),
        )

        st.divider()
        st.subheader("👽 การตั้งค่าดึงโพสต์ (Reddit)")

        enable_reddit = st.toggle(
            "ENABLE_REDDIT_SOURCE — เปิดใช้งานแหล่งข้อมูล Reddit",
            value=str(env_values.get("ENABLE_REDDIT_SOURCE", "true")).strip().lower() in ("1", "true", "yes"),
            help="ปิดไว้ = ข้ามขั้นตอนดึง Reddit ไปเลยตอนรัน run_all.py หรือกดปุ่มในหน้า Pipeline "
                 "(ไม่ error แม้ยังไม่ได้ตั้งค่าคีย์เวิร์ด/subreddit)",
        )
        reddit_search_terms = st.text_area(
            "REDDIT_SEARCH_TERMS — คีย์เวิร์ดค้นหาข้ามทั้ง Reddit (คั่นด้วย ,)",
            value=env_values.get("REDDIT_SEARCH_TERMS", ""),
            help='ค้นหาแบบข้ามทุก subreddit เช่น "FC27,FC 27,EAFC27,EA FC 27" — ใส่หลายแบบเผื่อคนสะกดไม่เหมือนกัน',
        )
        reddit_subreddits = st.text_area(
            "REDDIT_SUBREDDITS — subreddit ที่รู้จักอยู่แล้ว (คั่นด้วย , ไม่ต้องมี r/)",
            value=env_values.get("REDDIT_SUBREDDITS", ""),
            help='เช่น "EASportsFC,FIFA" — ดึงโพสต์ล่าสุดจากชุมชนนี้ตรงๆ (AI จะกรอง relevance ทีหลัง)',
        )
        reddit_limit = st.number_input(
            "REDDIT_RESULTS_LIMIT (จำนวนโพสต์สูงสุดต่อคีย์เวิร์ด/ต่อ subreddit ต่อรอบ)",
            min_value=1,
            max_value=1000,
            value=int(env_values.get("REDDIT_RESULTS_LIMIT") or 40),
        )

        submitted = st.form_submit_button("💾 บันทึกการตั้งค่า", type="primary")

    if submitted:
        updates = {
            "TWITTER_HANDLES": handles.strip(),
            "TWITTER_RESULTS_LIMIT": str(int(limit)),
            "FILTER_BY_KEYWORD": "true" if filter_by_keyword else "false",
            "TWITTER_KEYWORDS": keywords.strip(),
            "ENABLE_REDDIT_SOURCE": "true" if enable_reddit else "false",
            "REDDIT_SEARCH_TERMS": reddit_search_terms.strip(),
            "REDDIT_SUBREDDITS": reddit_subreddits.strip(),
            "REDDIT_RESULTS_LIMIT": str(int(reddit_limit)),
        }

        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        seen = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            matched_key = None
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    matched_key = key
            if matched_key:
                new_lines.append(f"{matched_key}={updates[matched_key]}")
                seen.add(matched_key)
            else:
                new_lines.append(line)

        for key, value in updates.items():
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
