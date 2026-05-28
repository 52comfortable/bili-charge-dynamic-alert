import time
import random
from datetime import datetime, timedelta
from monitor import main
import exchange_calendars as xcals

# 监控时段定义: (开始小时, 开始分钟, 结束小时, 结束分钟, 最小延迟秒, 最大延迟秒)
PERIODS = [
    (9, 0, 10, 30, 60, 300),      # 9:00-10:30  1~5分钟
    (10, 30, 11, 30, 600, 1200),  # 10:30-11:30 10~20分钟
    (11, 30, 13, 0, 1800, 1800),  # 11:30-13:00 固定30分钟
    (13, 30, 15, 0, 60, 300),     # 13:30-15:00 1~5分钟
    (15, 0, 16, 30, 1800, 1800)   # 15:00-16:30 固定30分钟
]

def _time_to_seconds(h, m, s=0):
    return h * 3600 + m * 60 + s

def get_delay():
    """根据当前时间返回合适的睡眠秒数，保证不会越过时段边界"""
    now = datetime.now()
    current_sec = _time_to_seconds(now.hour, now.minute, now.second)

    # 检查是否处于某个监控时段
    for sh, sm, eh, em, min_d, max_d in PERIODS:
        start_sec = _time_to_seconds(sh, sm)
        end_sec = _time_to_seconds(eh, em)
        if start_sec <= current_sec < end_sec:
            remain = end_sec - current_sec
            actual_max = min(max_d, remain)
            actual_min = min(min_d, remain)
            return random.randint(actual_min, actual_max)

    # 不在任何监控时段，寻找下一个时段的开始时间
    for sh, sm, eh, em, _, _ in PERIODS:
        start_sec = _time_to_seconds(sh, sm)
        if start_sec > current_sec:
            return start_sec - current_sec

    # 所有今天的时段都已过，等到明天第一个时段
    first_start_sec = _time_to_seconds(PERIODS[0][0], PERIODS[0][1])
    return (24 * 3600 - current_sec) + first_start_sec

def is_trading_day(date_to_check=None):
    """判断是否为 A 股交易日（以上交所 XSHG 为准）"""
    if date_to_check is None:
        date_to_check = datetime.now()
    try:
        cal = xcals.get_calendar("XSHG")
        return cal.is_session(date_to_check.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"交易日判断失败: {e}，默认按非交易日处理")
        return False

while True:
    if not is_trading_day():
        now = datetime.now()
        next_check = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now.hour >= 6:
            next_check += timedelta(days=1)
        wait_seconds = (next_check - now).total_seconds()
        print(f"今日非交易日，休眠 {wait_seconds:.0f} 秒至明日 6:00...")
        time.sleep(wait_seconds)
        continue

    delay = get_delay()
    print(f"等待 {delay} 秒...")
    time.sleep(delay)
    try:
        main()
    except Exception as e:
        print(f"监控出错: {e}")
