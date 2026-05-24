import time
import random
from monitor import main

while True:
    delay = random.randint(60, 300)   # 1~5分钟
    print(f"等待 {delay} 秒...")
    time.sleep(delay)
    try:
        main()
    except Exception as e:
        print(f"监控出错: {e}")
