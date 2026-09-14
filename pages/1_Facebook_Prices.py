"""
หน้าเทียบราคา/โปรโมชั่น/engagement ระหว่างเพจ Facebook — แยกออกมาจากหน้า Dashboard หลัก
เพราะเป็นคนละโฟกัสกัน (หน้าแรกดูกระแส community จาก X/Reddit, หน้านี้เจาะจงเทียบเพจร้านค้า)

แสดง engagement แบบละเอียด: ไลค์, คอมเมนต์, แชร์, ยอดวิว — ทั้งค่าเฉลี่ยต่อโพสต์และยอดรวม
ไม่ได้แก้ตรรกะของ analyze.py / db.py เลย — หน้านี้เรียกใช้ฟังก์ชันเดิมหรือคำนวณจาก DataFrame ตรงๆ
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import analyze  # ใช้ load_data / filter_relevant / facebook_price_trend / facebook_promotion_summary /
                 # facebook_engagement_comparison เดิม ไม่เขียนตรรกะซ้ำ
from secrets_sync import sync_secrets_to_env

sync_secrets_to_env()

st.set_page_config(page_title="Facebook Prices", page_icon="📘", layout="wide")
st.title("📘 เทียบราคา/โปรโมชั่น/Engagement ระหว่างเพจ Facebook")
st.caption(
    "ใช้สำหรับกรณีติดตามเพจร้านค้าที่รู้จักตายตัว (เช่น เพจเราเอง + เพจคู่แข่ง) — ต่างจาก X/Reddit "
    "ที่เน้นตามกระแส community กว้างๆ (ดูที่หน้า Dashboard หลักแทน)"
)

df_all = analyze.load_data()
if df_all.empty:
    st.info("ยังไม่มีข้อมูลในฐานข้อมูล ไปที่หน้า **Pipeline** เพื่อดึงข้อมูลก่อน")
    st.stop()

df = analyze.filter_relevant(df_all)
fb_df = df[df["platform"] == "facebook_page"].copy()

if fb_df.empty:
    st.info(
        "ยังไม่มีโพสต์จากเพจ Facebook — ไปที่หน้า **Settings** เพื่อตั้งค่า `FB_PAGE_URLS` "
        "แล้วไปที่หน้า **Pipeline** เพื่อดึงข้อมูล"
    )
    st.stop()

# ---------- ตัวกรองเพจ ----------
with st.sidebar:
    st.header("ตัวกรอง")
    pages = sorted(fb_df["source_name"].dropna().unique().tolist())
    selected_pages = st.multiselect("เลือกเพจ", pages, default=pages)

if selected_pages:
    fb_df = fb_df[fb_df["source_name"].isin(selected_pages)]

if fb_df.empty:
    st.warning("ไม่มีโพสต์ที่ตรงกับตัวกรองที่เลือก")
    st.stop()

st.caption(f"ใช้ {len(fb_df)} โพสต์จาก {len(selected_pages)} เพจในการวิเคราะห์")

# ============================================================
# 1) Metric สรุปภาพรวมต่อเพจ (การ์ดตัวเลขใหญ่ อ่านง่ายในแวบเดียว)
# ============================================================
st.subheader("📊 สรุปภาพรวมต่อเพจ")
engagement = analyze.facebook_engagement_comparison(df)  # ใช้ df เต็ม (ไม่กรอง sidebar) ให้ตรงกับ analyze.py
if selected_pages:
    engagement = engagement[engagement["source_name"].isin(selected_pages)]

if engagement.empty:
    st.caption("ไม่มีข้อมูล engagement")
else:
    for _, row in engagement.iterrows():
        st.markdown(f"**{row['source_name']}** ({int(row['total_posts'])} โพสต์)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👍 ไลค์เฉลี่ย/โพสต์", f"{row['avg_likes']:.1f}", help=f"รวม {int(row['total_likes'])} ไลค์")
        c2.metric("💬 คอมเมนต์เฉลี่ย/โพสต์", f"{row['avg_comments']:.1f}", help=f"รวม {int(row['total_comments'])} คอมเมนต์")
        c3.metric("🔁 แชร์เฉลี่ย/โพสต์", f"{row['avg_shares']:.1f}", help=f"รวม {int(row['total_shares'])} แชร์")
        c4.metric("👁️ ยอดวิวเฉลี่ย/โพสต์", f"{row['avg_views']:.1f}", help=f"รวม {int(row['total_views'])} วิว")
        st.divider()

# ============================================================
# 2) กราฟเทียบ engagement แบบละเอียด (ไลค์/คอมเมนต์/แชร์/ยอดวิว แยกแท่ง)
# ============================================================
st.subheader("📈 เปรียบเทียบ Engagement แบบละเอียด")
if not engagement.empty:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**ไลค์ / คอมเมนต์ / แชร์ เฉลี่ยต่อโพสต์**")
        melted = engagement.melt(
            id_vars="source_name",
            value_vars=["avg_likes", "avg_comments", "avg_shares"],
            var_name="metric", value_name="value",
        )
        melted["metric"] = melted["metric"].map({
            "avg_likes": "ไลค์", "avg_comments": "คอมเมนต์", "avg_shares": "แชร์",
        })
        fig_eng = px.bar(melted, x="source_name", y="value", color="metric", barmode="group")
        st.plotly_chart(fig_eng, use_container_width=True)

    with col_b:
        st.markdown("**ยอดวิวเฉลี่ยต่อโพสต์**")
        fig_views = px.bar(engagement, x="source_name", y="avg_views")
        st.plotly_chart(fig_views, use_container_width=True)

    st.markdown("**ตารางเต็ม (ค่าเฉลี่ย + ยอดรวม)**")
    st.dataframe(engagement, use_container_width=True, hide_index=True)
else:
    st.caption("ไม่มีข้อมูล engagement ให้แสดง")

# ============================================================
# 3) Engagement ตามเวลา (ดูแนวโน้มว่าเพจไหนกระแสขึ้น/ลงตอนไหน)
# ============================================================
st.subheader("📉 Engagement ตามเวลา")
fb_time = fb_df.dropna(subset=["posted_at"]).copy()
if not fb_time.empty:
    for col in ["score", "comments", "shares", "views"]:
        if col not in fb_time.columns:
            fb_time[col] = 0
        fb_time[col] = pd.to_numeric(fb_time[col], errors="coerce").fillna(0)
    fb_time["date"] = fb_time["posted_at"].dt.date

    metric_choice = st.radio(
        "เลือกตัวชี้วัด", ["ไลค์", "คอมเมนต์", "แชร์", "ยอดวิว"], horizontal=True, key="fb_metric_radio"
    )
    metric_col = {"ไลค์": "score", "คอมเมนต์": "comments", "แชร์": "shares", "ยอดวิว": "views"}[metric_choice]

    daily = fb_time.groupby(["date", "source_name"])[metric_col].sum().reset_index()
    fig_time = px.line(daily, x="date", y=metric_col, color="source_name", markers=True)
    st.plotly_chart(fig_time, use_container_width=True)
else:
    st.caption("ไม่มีข้อมูลวันที่ให้แสดงกราฟ")

# ============================================================
# 4) แนวโน้มราคา
# ============================================================
st.subheader("💰 แนวโน้มราคาตามเวลา")
fb_prices = analyze.facebook_price_trend(df)
if selected_pages:
    fb_prices = fb_prices[fb_prices["page_name"].isin(selected_pages)] if not fb_prices.empty else fb_prices

if fb_prices.empty:
    st.caption("ยังไม่มีข้อมูลราคา — รัน `ai_analyze.py` เพื่อให้ AI ดึงราคาจากข้อความ/รูปภาพก่อน")
else:
    fig_price = px.line(fb_prices, x="posted_at", y="price", color="page_name", markers=True,
                         hover_data=["quantity", "currency", "price_source"])
    st.plotly_chart(fig_price, use_container_width=True)
    with st.expander("ดูตารางราคาทั้งหมด"):
        st.dataframe(
            fb_prices, use_container_width=True, hide_index=True,
            column_config={"post_url": st.column_config.LinkColumn("ลิงก์", display_text="เปิด")},
        )

# ============================================================
# 5) โปรโมชั่นที่พบ
# ============================================================
st.subheader("🎁 โปรโมชั่นที่พบ")
fb_promos = analyze.facebook_promotion_summary(df)
if selected_pages:
    fb_promos = fb_promos[fb_promos["page_name"].isin(selected_pages)] if not fb_promos.empty else fb_promos

if fb_promos.empty:
    st.caption("ยังไม่พบโปรโมชั่น หรือยังไม่ได้รัน `ai_analyze.py`")
else:
    st.dataframe(
        fb_promos.sort_values("posted_at", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={"post_url": st.column_config.LinkColumn("ลิงก์", display_text="เปิด")},
    )

# ============================================================
# 6) โพสต์ engagement สูงสุด (รวมทุกตัวชี้วัด)
# ============================================================
st.subheader("🔥 โพสต์ที่มี Engagement สูงสุด")
fb_top = fb_df.copy()
for col in ["score", "comments", "shares", "views"]:
    if col not in fb_top.columns:
        fb_top[col] = 0
    fb_top[col] = pd.to_numeric(fb_top[col], errors="coerce").fillna(0)
fb_top["total_engagement"] = fb_top["score"] + fb_top["comments"] + fb_top["shares"]
fb_top = fb_top.sort_values("total_engagement", ascending=False).head(20)

st.dataframe(
    fb_top[["source_name", "posted_at", "summary", "score", "comments", "shares", "views",
            "total_engagement", "post_url"]].rename(columns={
                "source_name": "เพจ", "score": "ไลค์", "comments": "คอมเมนต์",
                "shares": "แชร์", "views": "ยอดวิว", "total_engagement": "engagement รวม",
            }),
    use_container_width=True, hide_index=True,
    column_config={
        "post_url": st.column_config.LinkColumn("ลิงก์", display_text="เปิด"),
        "posted_at": st.column_config.DatetimeColumn("เวลาโพสต์", format="D MMM YYYY, HH:mm"),
    },
)
