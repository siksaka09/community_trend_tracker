"""
หน้าแสดง/สร้างรายงานคาดการณ์แนวโน้ม — เรียกใช้ฟังก์ชันจาก analyze.py ตรงๆ ไม่เขียนตรรกะซ้ำ
"""
from pathlib import Path

import streamlit as st

import analyze  # ใช้ load_data / filter_relevant / split_time_windows / compute_trend_stats / generate_forecast เดิม
from secrets_sync import sync_secrets_to_env

sync_secrets_to_env()

st.set_page_config(page_title="Forecast", page_icon="📈", layout="wide")
st.title("📈 รายงานคาดการณ์แนวโน้ม")
st.caption(
    "คาดการณ์นี้เป็นการอนุมานจากรูปแบบข้อมูลสถิติเชิงเปรียบเทียบ (ครึ่งแรก vs ครึ่งหลังของข้อมูลที่มี) "
    "ไม่ใช่การพยากรณ์ที่แม่นยำหรือข้อเท็จจริง"
)

OUT_DIR = Path(__file__).parent.parent / "data"
FORECAST_FILE = OUT_DIR / "report_trend_forecast.md"

df_all = analyze.load_data()
if df_all.empty:
    st.info("ยังไม่มีข้อมูล ไปที่หน้า Pipeline เพื่อดึงข้อมูลก่อน")
    st.stop()

df = analyze.filter_relevant(df_all)
if df.empty:
    st.info("ยังไม่มีโพสต์ที่วิเคราะห์แล้วว่าเกี่ยวข้องกับ FC27 — รันขั้นตอน AI วิเคราะห์ก่อน (หน้า Pipeline)")
    st.stop()

older_df, recent_df, span_days = analyze.split_time_windows(df)

if older_df is None:
    st.warning(
        f"ข้อมูลครอบคลุมช่วงเวลาแค่ {span_days} วัน สั้นเกินไปที่จะเทียบแนวโน้มได้อย่างมีความหมาย "
        f"— เก็บข้อมูลต่อเนื่องอย่างน้อย 2-3 วันขึ้นไปก่อนแล้วลองใหม่"
    )
elif len(older_df) == 0 or len(recent_df) == 0:
    st.warning("ช่วงเวลาใดช่วงเวลาหนึ่งไม่มีโพสต์เลย ข้อมูลไม่พอเทียบแนวโน้ม")
else:
    stats = analyze.compute_trend_stats(older_df, recent_df)
    st.markdown(
        f"เทียบช่วง **{older_df['posted_at'].min().date()} – {older_df['posted_at'].max().date()}** "
        f"({stats['older_post_count']} โพสต์) กับช่วง "
        f"**{recent_df['posted_at'].min().date()} – {recent_df['posted_at'].max().date()}** "
        f"({stats['recent_post_count']} โพสต์)"
    )

    if st.button("🔄 สร้างรายงานใหม่ (เรียก Claude API)"):
        with st.spinner("กำลังให้ Claude วิเคราะห์แนวโน้ม..."):
            forecast_text = analyze.generate_forecast(stats)
        if forecast_text:
            OUT_DIR.mkdir(exist_ok=True)
            with open(FORECAST_FILE, "w", encoding="utf-8") as f:
                f.write("# คาดการณ์แนวโน้ม EA FC 27\n\n")
                f.write(
                    f"เทียบช่วง {older_df['posted_at'].min().date()}–{older_df['posted_at'].max().date()} "
                    f"กับ {recent_df['posted_at'].min().date()}–{recent_df['posted_at'].max().date()}\n\n"
                )
                f.write(forecast_text)
            st.success("สร้างรายงานใหม่เรียบร้อย")
        else:
            st.error("สร้างรายงานไม่สำเร็จ เช็ค ANTHROPIC_API_KEY ในไฟล์ .env")

st.divider()

if FORECAST_FILE.exists():
    st.markdown(FORECAST_FILE.read_text(encoding="utf-8"))
else:
    st.caption("ยังไม่มีรายงานคาดการณ์ที่บันทึกไว้ — กดปุ่มด้านบนเพื่อสร้างรายงานแรก")
