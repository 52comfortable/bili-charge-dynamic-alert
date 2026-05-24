import time
import random
from monitor import main   # 假设你的监控主函数在 monitor.py 中

while True:
    delay = random.randint(60, 300)   # 1~5分钟
    print(f"等待 {delay} 秒...")
    time.sleep(delay)
    try:
        main()
    except Exception as e:
        print(f"监控出错: {e}")
