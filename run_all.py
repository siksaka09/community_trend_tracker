"""รันทั้ง pipeline ในคำสั่งเดียว: ดึงทวีตจาก X -> ให้ AI วิเคราะห์ -> สรุปเทรนด์"""
import scrape_x
import ai_analyze
import analyze

if __name__ == "__main__":
    print("### STEP 1/3: ดึงทวีตจาก X (Twitter) ###")
    scrape_x.main()

    print("\n### STEP 2/3: ให้ AI วิเคราะห์ relevance/sentiment/หัวข้อ ###")
    ai_analyze.main()

    print("\n### STEP 3/3: สรุปเทรนด์ ###")
    analyze.main()
