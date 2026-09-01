"""
Local Web Dashboard สำหรับ Community Trend Tracker (EA FC 27)

วิธีรัน:
    streamlit run app.py

หน้านี้เป็นหน้าแรก (Dashboard) แสดงภาพรวมเทรนด์จากข้อมูลที่เก็บไว้ใน SQLite
หน้าอื่นๆ (สร้างรายงานคาดการณ์ / ควบคุม pipeline / ตั้งค่า / ดูข้อมูลดิบ) อยู่ในโฟลเดอร์ pages/
ไม่ได้แก้ตรรกะของ scrape_x.py / ai_analyze.py / analyze.py เลย — หน้านี้แค่อ่านข้อมูลจาก db.py
"""
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from db import get_all_posts_df, get_summary_stats
from secrets_sync import sync_secrets_to_env

sync_secrets_to_env()  # ให้ทำงานได้ทั้งตอนรันในเครื่อง (.env) และตอน deploy บน Streamlit Cloud (secrets.toml)

FORECAST_FILE = Path(__file__).parent / "data" / "report_trend_forecast.md"

st.set_page_config(page_title="EA FC 27 Trend Tracker", page_icon="⚽", layout="wide")

st.title("⚽ EA FC 27 — Community Trend Dashboard")
st.caption("ภาพรวมกระแส/เทรนด์จากทวีต X (Twitter) ที่เก็บไว้ในฐานข้อมูล")


@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    df = get_all_posts_df()
    if df.empty:
        return df
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    return df


df_all = load_data()

if df_all.empty:
    st.info("ยังไม่มีข้อมูลในฐานข้อมูล ไปที่หน้า **Pipeline** (แถบด้านซ้าย) เพื่อดึงทวีตและวิเคราะห์ก่อน")
    st.stop()

stats = get_summary_stats()
col1, col2, col3, col4 = st.columns(4)
col1.metric("โพสต์ทั้งหมด", stats.get("total", 0))
col2.metric("วิเคราะห์แล้ว", stats.get("analyzed", 0))
col3.metric("เกี่ยวกับ FC27", stats.get("relevant", 0))
col4.metric("บัญชีที่ติดตาม", stats.get("accounts", 0))

st.divider()

# ---------- ตัวกรอง ----------
with st.sidebar:
    st.header("ตัวกรอง")
    df_dated = df_all.dropna(subset=["posted_at"])
    date_range = None
    if not df_dated.empty:
        min_date = df_dated["posted_at"].min().date()
        max_date = df_dated["posted_at"].max().date()
        date_range = st.date_input(
            "ช่วงวันที่", (min_date, max_date), min_value=min_date, max_value=max_date
        )

    platforms = sorted(df_all["platform"].dropna().unique().tolist())
    selected_platforms = st.multiselect("แพลตฟอร์ม", platforms, default=platforms)

    sentiments = sorted(df_all["sentiment"].dropna().unique().tolist())
    selected_sentiments = st.multiselect("Sentiment", sentiments, default=sentiments)

    relevant_only = st.checkbox("เฉพาะโพสต์ที่เกี่ยวกับ FC27 (is_relevant = 1)", value=True)

df = df_all.copy()
if relevant_only:
    df = df[df["is_relevant"] == 1]
if selected_platforms:
    df = df[df["platform"].isin(selected_platforms)]
if selected_sentiments:
    df = df[df["sentiment"].isin(selected_sentiments)]
if date_range and len(date_range) == 2:
    start, end = date_range
    df = df.dropna(subset=["posted_at"])
    df = df[(df["posted_at"].dt.date >= start) & (df["posted_at"].dt.date <= end)]

if df.empty:
    st.warning("ไม่มีโพสต์ที่ตรงกับตัวกรองที่เลือก")
    st.stop()

# ---------- ปริมาณโพสต์ตามเวลา ----------
st.subheader("📈 ปริมาณโพสต์ตามเวลา")
vol_df = df.dropna(subset=["posted_at"]).copy()
if not vol_df.empty:
    vol_df["date"] = vol_df["posted_at"].dt.date
    volume = vol_df.groupby(["date", "platform"]).size().reset_index(name="post_count")
    fig_vol = px.line(volume, x="date", y="post_count", color="platform", markers=True)
    st.plotly_chart(fig_vol, use_container_width=True)
else:
    st.caption("ไม่มีข้อมูลวันที่ให้แสดงกราฟ")

# ---------- Sentiment + หัวข้อ ----------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("😊 สัดส่วน Sentiment")
    sent_counts = df["sentiment"].value_counts().reset_index()
    sent_counts.columns = ["sentiment", "count"]
    if not sent_counts.empty:
        fig_sent = px.pie(sent_counts, names="sentiment", values="count", hole=0.4)
        st.plotly_chart(fig_sent, use_container_width=True)
    else:
        st.caption("ไม่มีข้อมูล sentiment")

with col_right:
    st.subheader("🏷️ หัวข้อที่พูดถึงบ่อยที่สุด")
    counter = Counter()
    for topics_json in df["topics"].dropna():
        try:
            counter.update(json.loads(topics_json))
        except json.JSONDecodeError:
            continue
    if counter:
        topics_df = pd.DataFrame(counter.most_common(15), columns=["topic", "mentions"])
        fig_topics = px.bar(topics_df, x="mentions", y="topic", orientation="h")
        fig_topics.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_topics, use_container_width=True)
    else:
        st.caption("ไม่มีข้อมูลหัวข้อ")

# ---------- โพสต์ engagement สูงสุด ----------
st.subheader("🔥 โพสต์ที่มี Engagement สูงสุด")
top_df = df.copy()
top_df["engagement"] = (
    pd.to_numeric(top_df["score"], errors="coerce").fillna(0)
    + pd.to_numeric(top_df["comments"], errors="coerce").fillna(0)
)
top_df = top_df.sort_values("engagement", ascending=False).head(20)
st.dataframe(
    top_df[["platform", "source_name", "posted_at", "summary", "sentiment", "engagement", "post_url"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "post_url": st.column_config.LinkColumn("ลิงก์ทวีต", display_text="เปิดทวีต"),
        "posted_at": st.column_config.DatetimeColumn("เวลาโพสต์", format="D MMM YYYY, HH:mm"),
    },
)

# ---------- คาดการณ์แนวโน้มจาก AI ----------
st.divider()
st.subheader("🤖 คาดการณ์แนวโน้มจาก AI")
if FORECAST_FILE.exists():
    st.caption(
        "รายงานนี้เป็นการอนุมานจากรูปแบบข้อมูล ไม่ใช่การพยากรณ์ที่แม่นยำหรือข้อเท็จจริง "
        "— ไปที่หน้า **Forecast** เพื่อสร้างรายงานใหม่"
    )
    with st.expander("ดูรายงานคาดการณ์ล่าสุด", expanded=False):
        st.markdown(FORECAST_FILE.read_text(encoding="utf-8"))
else:
    st.caption("ยังไม่มีรายงานคาดการณ์ที่บันทึกไว้ — ไปที่หน้า **Forecast** เพื่อสร้างรายงานแรก")
