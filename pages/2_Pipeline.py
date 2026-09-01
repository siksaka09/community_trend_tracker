"""
หน้าควบคุม pipeline: ดึงทวีต / วิเคราะห์ AI / สรุปเทรนด์
รันแต่ละสคริปต์เดิม (scrape_x.py / ai_analyze.py / analyze.py / run_all.py) เป็น subprocess แยก
เพื่อให้เห็น log แบบ real-time โดยไม่ต้องแก้โค้ดสคริปต์เดิมเลย
"""
import subprocess
import sys
from pathlib import Path

import streamlit as st

from db import get_summary_stats
from secrets_sync import sync_secrets_to_env

# subprocess ที่เรียกด้านล่างนี้จะสืบทอด os.environ ของโปรเซสหลักไปด้วยอัตโนมัติ
# ดังนั้นถ้า sync ค่าจาก st.secrets เข้า os.environ ก่อน สคริปต์เดิม (scrape_x.py ฯลฯ)
# ที่อ่านค่าด้วย os.getenv() ก็จะเห็นค่าพวกนี้เหมือนกันโดยไม่ต้องแก้โค้ดสคริปต์เดิมเลย
sync_secrets_to_env()

st.set_page_config(page_title="Pipeline", page_icon="⚙️", layout="wide")
st.title("⚙️ ควบคุม Pipeline")

PROJECT_DIR = Path(__file__).parent.parent

stats = get_summary_stats()
unanalyzed_count = stats.get("total", 0) - stats.get("analyzed", 0)

col1, col2 = st.columns(2)
col1.metric("โพสต์ทั้งหมดในฐานข้อมูล", stats.get("total", 0))
col2.metric("รอวิเคราะห์ AI", unanalyzed_count)

st.caption(
    "การรันแต่ละขั้นตอนจะบล็อกหน้าเว็บจนกว่าจะเสร็จ (เหมาะกับใช้งานคนเดียวบนเครื่องตัวเอง) "
    "อย่ากดปุ่มซ้ำระหว่างที่กำลังรันอยู่"
)


def run_script(script_name: str, label: str):
    """รันสคริปต์ python เป็น subprocess แล้วสตรีม log ออกมาทีละบรรทัดแบบ real-time"""
    st.write(f"**กำลังรัน `{script_name}` ...**")
    log_box = st.empty()
    log_lines = []

    process = subprocess.Popen(
        [sys.executable, script_name],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in iter(process.stdout.readline, ""):
        log_lines.append(line.rstrip())
        log_box.code("\n".join(log_lines[-200:]))  # แสดงแค่ 200 บรรทัดล่าสุดกันหน้าเว็บหนักเกินไป
    process.wait()

    if process.returncode == 0:
        st.success(f"{label} เสร็จสิ้น ✅")
    else:
        st.error(f"{label} จบด้วย error (exit code {process.returncode}) — ดู log ด้านบน")

    st.cache_data.clear()


st.divider()
st.subheader("1) ดึงทวีตจาก X")
if st.button("▶️ รัน scrape_x.py"):
    run_script("scrape_x.py", "ดึงทวีต")

st.subheader("2) วิเคราะห์ AI (relevance / sentiment / หัวข้อ)")
if st.button("▶️ รัน ai_analyze.py"):
    run_script("ai_analyze.py", "วิเคราะห์ AI")

st.subheader("3) สรุปเทรนด์ + export CSV")
if st.button("▶️ รัน analyze.py"):
    run_script("analyze.py", "สรุปเทรนด์")

st.divider()
st.subheader("รันทั้ง pipeline ในคำสั่งเดียว")
if st.button("🚀 รัน run_all.py (ดึง → วิเคราะห์ → สรุป)"):
    run_script("run_all.py", "Pipeline ทั้งหมด")
