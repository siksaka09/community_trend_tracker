"""
หน้าเรียกดู/แก้ไขโพสต์ดิบในฐานข้อมูล — เอาไว้ตรวจสอบว่า AI จำแนก relevance ผิดพลาดหรือไม่
(ตามที่ README เดิมของโปรเจกต์เตือนไว้ว่าควรสุ่มเช็คเป็นระยะ)
"""
import pandas as pd
import streamlit as st

from db import get_all_posts_df, update_post_relevance
from secrets_sync import sync_secrets_to_env

sync_secrets_to_env()

st.set_page_config(page_title="Raw Data", page_icon="📋", layout="wide")
st.title("📋 ข้อมูลดิบทั้งหมด")


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    df = get_all_posts_df()
    if df.empty:
        return df
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    return df


df = load_data()
if df.empty:
    st.info("ยังไม่มีข้อมูลในฐานข้อมูล")
    st.stop()

col1, col2, col3 = st.columns(3)
search = col1.text_input("ค้นหาในข้อความ/สรุป")
platform_filter = col2.multiselect("แพลตฟอร์ม", sorted(df["platform"].dropna().unique().tolist()))
relevance_filter = col3.selectbox(
    "สถานะ relevance", ["ทั้งหมด", "เกี่ยวข้อง", "ไม่เกี่ยวข้อง", "ยังไม่วิเคราะห์"]
)

filtered = df.copy()
if search:
    mask = filtered["text"].fillna("").str.contains(search, case=False) | filtered["summary"].fillna(
        ""
    ).str.contains(search, case=False)
    filtered = filtered[mask]
if platform_filter:
    filtered = filtered[filtered["platform"].isin(platform_filter)]
if relevance_filter == "เกี่ยวข้อง":
    filtered = filtered[filtered["is_relevant"] == 1]
elif relevance_filter == "ไม่เกี่ยวข้อง":
    filtered = filtered[filtered["is_relevant"] == 0]
elif relevance_filter == "ยังไม่วิเคราะห์":
    filtered = filtered[filtered["is_relevant"].isna()]

st.caption(f"พบ {len(filtered)} โพสต์ (จากทั้งหมด {len(df)})")

row_limit = st.slider("จำนวนแถวที่แสดง", 20, 500, 100, step=20)
display_df = filtered.sort_values("posted_at", ascending=False).head(row_limit).copy()
display_df["is_relevant_bool"] = display_df["is_relevant"].map({1: True, 0: False})

edited = st.data_editor(
    display_df[
        ["uid", "source_name", "posted_at", "text", "summary", "sentiment", "is_relevant_bool", "post_url"]
    ],
    use_container_width=True,
    hide_index=True,
    disabled=["uid", "source_name", "posted_at", "text", "summary", "sentiment", "post_url"],
    column_config={
        "is_relevant_bool": st.column_config.CheckboxColumn("เกี่ยวข้องกับ FC27?"),
        "post_url": st.column_config.LinkColumn("ลิงก์", display_text="เปิด"),
    },
    key="raw_data_editor",
)

if st.button("💾 บันทึกการแก้ไข is_relevant"):
    changed = 0
    original = display_df.set_index("uid")["is_relevant_bool"]
    edited_indexed = edited.set_index("uid")["is_relevant_bool"]
    for uid, new_val in edited_indexed.items():
        if bool(original.get(uid)) != bool(new_val):
            update_post_relevance(uid, bool(new_val))
            changed += 1
    st.success(f"บันทึกแล้ว {changed} รายการ")
    st.cache_data.clear()
    st.rerun()
