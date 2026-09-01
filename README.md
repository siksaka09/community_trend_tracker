# Community Trend Tracker — จับกระแสเกม EA FC 27 จาก X (Twitter)

โปรเจกต์นี้**แยกต่างหากจาก `fb_competitor_tracker`** เพราะเป้าหมายต่างกัน:
ตัวนั้นเทียบราคาระหว่างสองเพจร้านค้าที่รู้จักตายตัว ส่วนตัวนี้**ตามกระแส/เทรนด์**ของเกม EA FC 27
จากบัญชี X (Twitter) ที่ระบุไว้ (เช่น บัญชีข่าวเกม, บัญชีทางการ, ผู้มีอิทธิพลในวงการ)

ใช้ **Claude API** วิเคราะห์ทวีตแต่ละอันว่า:
1. **เกี่ยวกับเกม EA FC 27 จริงไหม** (กรองทวีตอื่นที่หลุดเข้ามา)
2. **โทนของโพสต์เป็นอย่างไร** (positive / negative / neutral / mixed)
3. **พูดถึงหัวข้ออะไร** (เกมเพลย์, ราคา, วันวางจำหน่าย, บั๊ก, ความตื่นเต้น ฯลฯ)

แล้วสรุปออกมาเป็นรายงาน: ปริมาณทวีตตามเวลา, สัดส่วน sentiment, หัวข้อฮิต, และทวีตที่กำลังไวรัล

## โครงสร้างไฟล์
```
community_trend_tracker/
├── .env.example    # แม่แบบไฟล์ config (คัดลอกเป็น .env)
├── requirements.txt # รายชื่อ library ที่ต้องติดตั้ง
├── db.py            # จัดการฐานข้อมูล SQLite (เก็บที่ data/community_trends.db)
├── scrape_x.py      # ดึงทวีตจากบัญชี X ที่ระบุ ผ่าน Apify
├── ai_analyze.py     # ให้ Claude เช็ค relevance/sentiment/หัวข้อ
├── analyze.py        # สรุปเทรนด์ + export เป็น CSV
└── run_all.py        # รันทั้ง 3 ขั้นตอนในคำสั่งเดียว
```

## ขั้นตอนติดตั้ง (ทำครั้งเดียว)

### 1. ติดตั้ง library
```bash
cd community_trend_tracker
pip install -r requirements.txt
```

### 2. เอา Apify token
ถ้าเคยทำโปรเจกต์อื่นมาก่อน ใช้ token เดิมได้เลย ไม่ต้องสมัครใหม่
(ถ้ายังไม่มี: https://console.apify.com/account/integrations)

### 3. เอา Claude API key
1. สมัคร/เข้า https://console.anthropic.com/settings/keys คัดลอก key
2. เติมเครดิตที่ https://console.anthropic.com/settings/billing (ขั้นต่ำ ~$5)
   **งบ $5 เพียงพอมากสำหรับทดสอบและใช้งานจริง** เพราะระบบวิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request
   และใช้โมเดล Haiku 4.5 (ถูกสุด) เป็นค่าเริ่มต้น — วิเคราะห์ 200 โพสต์ ใช้เงินประมาณ $0.20-0.30 เท่านั้น
   ($5 รันได้หลายสิบรอบ)

### 4. ตั้งค่าไฟล์ .env
```bash
cp .env.example .env
```
แล้วเปิดไฟล์ `.env` ใส่ค่า:
- `APIFY_API_TOKEN` — token จากขั้นตอนที่ 2
- `ANTHROPIC_API_KEY` — key จากขั้นตอนที่ 3
- `TWITTER_HANDLES` — บัญชี X ที่ต้องการติดตาม (ไม่ต้องมี @ นำหน้า) คั่นด้วย comma เช่น
  ```
  TWITTER_HANDLES=EASPORTSFC,eafootball_news,some_fc_influencer
  ```
  แนะนำให้ผสมทั้งบัญชีทางการ (ข่าวจริง) และบัญชีชุมชน/ผู้มีอิทธิพล (ฟีดแบ็ก/กระแส) เพื่อเห็นภาพครบ
- `FILTER_BY_KEYWORD` — เลือกว่าจะกรองตั้งแต่ตอนดึงข้อมูลหรือไม่ (ดูรายละเอียดหัวข้อถัดไป)
- `TWITTER_KEYWORDS` — คีย์เวิร์ดที่ใช้กรอง (มีผลเฉพาะตอน `FILTER_BY_KEYWORD=true`)

## เลือกโหมดการกรอง: ดึงทั้งหมด vs กรองตั้งแต่ตอนดึง

**`scrape_x.py` มี 2 โหมด ตั้งค่าได้ที่ `FILTER_BY_KEYWORD` ใน `.env`:**

| | `FILTER_BY_KEYWORD=false` (ค่าเริ่มต้น) | `FILTER_BY_KEYWORD=true` |
|---|---|---|
| วิธีทำงาน | ดึง**ทุกทวีต**จากบัญชีที่ระบุ (timeline ทั้งหมด) | ค้นหาเฉพาะทวีตที่มีคีย์เวิร์ดตรงกับ `TWITTER_KEYWORDS` จากบัญชีนั้นๆ (`from:handle (keyword1 OR keyword2 ...)`) |
| กรอง FC27 ตอนไหน | ทีหลัง ในขั้นตอน `ai_analyze.py` (AI เช็คทีละโพสต์) | ตั้งแต่ตอนดึงเลย |
| ความครอบคลุม | สูงกว่า (ไม่พลาดทวีตที่พูดถึงเกมแบบอ้อมๆ ไม่ใช้คำตรงเป๊ะ) | อาจพลาดทวีตที่ไม่ได้ใช้คำในลิสต์ `TWITTER_KEYWORDS` |
| ค่าใช้จ่าย | สูงกว่า (ถ้าบัญชีนั้นทวีตเรื่องอื่นเยอะ จะเสีย Apify credit + Claude token ไปกับทวีตที่ไม่เกี่ยว) | ประหยัดกว่ามาก เพราะดึงมาน้อยกว่าตั้งแต่ต้น |

**คำแนะนำ:** เริ่มจาก `false` ก่อนเพื่อดูภาพรวมกว้างๆ ว่าบัญชีที่ติดตามทวีตอะไรบ้าง แล้วค่อยสลับเป็น
`true` เมื่อรู้แล้วว่าอยากประหยัด credit/token และยอมรับความเสี่ยงที่จะพลาดทวีตที่ใช้คำแปลกๆ ได้

## วิธีรัน

รันทีเดียวครบทุกขั้นตอน:
```bash
python run_all.py
```

หรือรันแยกทีละขั้น:
```bash
python scrape_x.py     # ดึงทวีตจากบัญชีที่ระบุ
python ai_analyze.py   # ให้ Claude เช็ค relevance/sentiment/หัวข้อ
python analyze.py      # พิมพ์สรุปเทรนด์ + export CSV
```

ผลลัพธ์ CSV จะอยู่ที่:
- `data/report_volume_over_time.csv` — ปริมาณทวีตตามวัน (ดูว่าวันไหนกระแสแรง)
- `data/report_sentiment.csv` — สัดส่วน positive/negative/neutral/mixed
- `data/report_top_topics.csv` — หัวข้อที่พูดถึงบ่อยที่สุด (เกมเพลย์, ราคา, บั๊ก ฯลฯ)
- `data/report_top_posts.csv` — ทวีต engagement สูงสุด 20 อันดับ (กำลังเป็นกระแส)

## การใช้งานระยะยาว

แนะนำรันทุกวันเพื่อเห็นกราฟกระแสที่เปลี่ยนไปตามเวลา (เช่น กระแสพุ่งขึ้นตอนมีข่าวเปิดตัว/รั่วไหล)
ตั้งเป็น cron job ได้:
```bash
0 0 * * * cd /path/to/community_trend_tracker && /usr/bin/python3 run_all.py >> data/log.txt 2>&1
```

## ข้อควรระวัง

1. **Terms of Service** — การดึงข้อมูลอัตโนมัติจาก X อาจขัดกับ ToS ของแพลตฟอร์ม ควรดึงเฉพาะเนื้อหา
   public, เว้นระยะเวลาที่เหมาะสม ไม่ดึงถี่เกินจำเป็น
2. **Apify credit** — `apidojo/twitter-scraper-lite` เป็น actor ของ community คิดค่าใช้จ่ายแบบ
   event-based (ประมาณ $0.40 ต่อ 1,000 ทวีต) ปรับ `TWITTER_RESULTS_LIMIT` ให้พอดีกับที่ใช้จริง
3. **X (Twitter) ต้องระบุบัญชีเอง** — ต่างจาก Reddit ที่ค้นด้วยคีย์เวิร์ดได้ ตัว X จำกัดการค้นหาแบบ
   ไม่ login มาก จึงต้องรู้ล่วงหน้าว่าจะติดตามบัญชีไหน (`TWITTER_HANDLES`) แนะนำเริ่มจากบัญชีทางการ
   ของ EA Sports FC และบัญชีข่าวเกม/ผู้มีอิทธิพลที่มักพูดถึงเกมนี้ ส่วนการกรองว่าทวีตไหนเกี่ยวกับ FC27
   จริงๆ เลือกได้ 2 โหมด ดูหัวข้อ "เลือกโหมดการกรอง" ด้านบน
4. **Actor เป็นของ community** — `apidojo/twitter-scraper-lite` ไม่ใช่ actor ที่ Apify ทำเอง ถ้า field
   ไม่ตรงหรือ error ให้เช็ค input schema ล่าสุดที่ https://apify.com/apidojo/twitter-scraper-lite/input-schema
   แล้วปรับ `run_input` ใน `scrape_x.py` — สคริปต์จะพิมพ์ชื่อ field ทั้งหมดของทวีตแรกที่ดึงมาให้ดูด้วย
5. **โมเดล Claude และค่าใช้จ่าย** — ค่าเริ่มต้นคือ `claude-haiku-4-5-20251001` (ถูกสุด เหมาะกับงาน
   จำแนกประเภท/สรุปสั้นๆ) ถ้าอยากได้คุณภาพสูงขึ้น (เข้าใจบริบทซับซ้อนกว่า) ปรับ `MODEL_NAME` ใน
   `ai_analyze.py` เป็น `"claude-sonnet-5"` ได้ (แพงขึ้นประมาณ 4 เท่า) ระบบมี retry อัตโนมัติสำหรับ
   rate limit (429) และ server error ชั่วคราว (500/503/529) อยู่แล้ว
6. **ความแม่นยำของ relevance filter** — AI อาจกรองผิดพลาดได้บ้าง (false positive/negative)
   ควรสุ่มเช็คทวีตที่ถูกกรองออก/เข้า เทียบกับเนื้อหาจริงเป็นระยะ

## ขั้นตอนถัดไปที่ต่อยอดได้
- เพิ่มบัญชี X อื่นๆ ที่เกี่ยวข้องใน `TWITTER_HANDLES` เพื่อขยายมุมมอง (เช่น นักข่าวเกม, ช่อง YouTube)
- ทำ dashboard ด้วย Streamlit อ่านจาก `data/community_trends.db` โดยตรง แทนที่จะดู CSV
- ให้ AI สรุปเป็นรายงานภาษาไทยทุกสัปดาห์ (ส่ง CSV เข้า Claude อีกรอบ ให้เขียนสรุปเชิง insight)
- เชื่อมกับโปรเจกต์ `fb_competitor_tracker` เพื่อดูว่าช่วงที่กระแสเกม EA FC 27 พุ่ง เพจขายเหรียญ
  ปรับราคา/โพสต์ถี่ขึ้นตามไหม
