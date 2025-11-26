import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. Load Environment Variables
load_dotenv()

# 2. Get the URL
url = os.getenv("DATABASE_URL")
print(f"\n--- DIAGNOSTIC REPORT ---")
print(f"1. Python sees DATABASE_URL: {url}")

if not url:
    print("❌ ERROR: DATABASE_URL is empty. Check your .env file location.")
    exit()

try:
    # 3. Attempt Connection
    engine = create_engine(url)
    with engine.connect() as conn:
        print("2. Connection to Postgres: SUCCESS ✅")
        
        # 4. Check Table Count
        result = conn.execute(text("SELECT count(*) FROM schemes"))
        count = result.scalar()
        print(f"3. Rows in 'schemes' table: {count}")
        
        if count > 0:
            print("✅ Data exists! Here are the first 3 titles:")
            rows = conn.execute(text("SELECT title FROM schemes LIMIT 3"))
            for row in rows:
                print(f"   - {row[0]}")
        else:
            print("❌ The table exists but is EMPTY.")
            print("   Please re-run the scraper/seeder ensuring it points to this SAME url.")

except Exception as e:
    print(f"❌ Connection FAILED: {e}")

print("-------------------------\n")