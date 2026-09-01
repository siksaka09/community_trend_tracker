# Deploy ขึ้น Streamlit Community Cloud (ฟรี)

แนวทางนี้เป็นแบบ "ง่ายสุด" — ใช้โครงสร้างเดิม ไม่มี cron อัตโนมัติ ต้องเปิดเว็บแล้วกดปุ่มรัน
pipeline เองเวลาต้องการข้อมูลใหม่ เหมาะกับการทดลองใช้งานจริง/ใช้คนเดียว

## ข้อควรรู้ก่อนเริ่ม (สำคัญ)

- **พื้นที่เก็บไฟล์ไม่ถาวร 100%** — ถ้าแอป sleep/redeploy ไฟล์ `data/community_trends.db` มีสิทธิ์หาย
  แนะนำเข้าไปที่หน้า **Settings** ของแอปแล้วกด "ดาวน์โหลดฐานข้อมูลปัจจุบัน" เก็บไว้เป็นระยะ
  ถ้าข้อมูลหายก็อัปโหลดไฟล์สำรองกลับเข้าไปที่หน้าเดียวกันได้ (ช่อง "กู้คืนฐานข้อมูล")
- **ไม่มี cron ในตัว** — แอปจะรัน pipeline ก็ต่อเมื่อมีคนเปิดเว็บแล้วกดปุ่มที่หน้า Pipeline เท่านั้น
- **แอป sleep เมื่อไม่มีคนใช้นาน** — Streamlit Community Cloud จะพักแอปที่ไม่มีคนเข้าเป็นเวลานาน
  เปิดเข้าไปใหม่ครั้งแรกอาจรอสักครู่ให้แอปตื่น

## ขั้นตอน

### 1. เตรียมไฟล์ในโปรเจกต์
เอาไฟล์ที่แนบมาในนี้ (`app.py`, `pages/`, `db.py`, `secrets_sync.py`, `requirements.txt`, `.gitignore`)
ไปวางรวมกับไฟล์เดิมของโปรเจกต์ (`scrape_x.py`, `ai_analyze.py`, `analyze.py`, `run_all.py`)
ให้อยู่ในโฟลเดอร์เดียวกันทั้งหมด — **`requirements.txt` ในนี้เป็นตัวรวมทุกอย่างแล้ว ใช้แทนตัวเก่าได้เลย**

### 2. สร้าง GitHub repo แล้ว push ขึ้นไป
```bash
cd community_trend_tracker
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```
`.gitignore` ที่แนบมาจะกันไม่ให้ `.env` และไฟล์ฐานข้อมูลในเครื่องหลุดขึ้น GitHub โดยไม่ตั้งใจ
(repo จะเป็น public หรือ private ก็ได้ Streamlit Community Cloud รองรับทั้งคู่)

### 3. Deploy บน Streamlit Community Cloud
1. ไปที่ https://share.streamlit.io แล้ว sign in ด้วยบัญชี GitHub
2. กด "New app" เลือก repo / branch ที่เพิ่ง push ไป
3. ช่อง "Main file path" ใส่ `app.py`
4. ก่อนกด Deploy ให้เปิด "Advanced settings" เพื่อใส่ Secrets (ดูขั้นตอนที่ 4)

### 4. ตั้งค่า Secrets (แทนไฟล์ .env)
เปิดไฟล์ `secrets.toml.example` ที่แนบมา คัดลอกเนื้อหาไปวางในช่อง Secrets ตอน deploy
(หรือทีหลังที่ "Manage app" > "Settings" > "Secrets") แล้วแก้ค่าให้เป็นของจริง:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
APIFY_API_TOKEN = "apify_api_..."
TWITTER_HANDLES = "EASPORTSFC,eafootball_news"
TWITTER_KEYWORDS = "FC27,FC 27,EAFC27,EA FC 27,EA Sports FC 27"
FILTER_BY_KEYWORD = "false"
TWITTER_RESULTS_LIMIT = "40"
```

ไม่ต้องแก้โค้ด `scrape_x.py` / `ai_analyze.py` / `analyze.py` เลย — ไฟล์ `secrets_sync.py` ที่แนบมา
จะคัดลอกค่าจาก Secrets เข้า environment variable ให้อัตโนมัติ ทำให้สคริปต์เดิมที่อ่านค่าด้วย
`os.getenv()` มองเห็นค่าพวกนี้เหมือนตอนรันในเครื่องทุกประการ

### 5. Deploy แล้วทดสอบ
กด Deploy รอสักครู่ให้ระบบติดตั้ง `requirements.txt` เสร็จ แอปจะเปิดขึ้นมาอัตโนมัติ
ไปที่หน้า **Pipeline** แล้วกดรัน `scrape_x.py` → `ai_analyze.py` → `analyze.py` (หรือรันทั้งหมดทีเดียว)
เพื่อดึงข้อมูลชุดแรก

## เมื่ออยากอัปเดตโค้ด
แก้ไฟล์แล้ว `git push` ขึ้น branch เดิม — Streamlit Community Cloud จะ redeploy ให้อัตโนมัติ
(ข้อควรระวัง: การ redeploy อาจทำให้ไฟล์ฐานข้อมูลรีเซ็ต ดาวน์โหลดสำรองไว้ก่อนทุกครั้งถ้ามีข้อมูลสำคัญ)
