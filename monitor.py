#!/usr/bin/env python3
"""
B站充电专属动态监控 - 本地版
每执行一次检查最新充电动态，有新的就推送并记录ID
"""
import os
import re
import time
import random
import base64
import hashlib
import requests
import urllib.parse
from datetime import datetime

# ==================== 配置 ====================
UP_MID = os.environ.get("UP_MID", "11473291")     # 要监控的UP主MID
SESSDATA = os.environ.get("SESSDATA", "") #Cookie中的SESSDATA
BILI_JCT = os.environ.get("BILI_JCT", "") #Cookie中的bili_jct
BUVID3 = os.environ.get("BUVID3", "")     #Cookie中的buvid3
SCKEY = os.environ.get("SCKEY", "")       # 留空则不推送，支持多个Key，用英文逗号分隔，例如 "key1,key2,key3"
# =============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Referer": f"https://space.bilibili.com/{UP_MID}/dynamic",
    "Origin": "https://space.bilibili.com",
}

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]

LAST_ID_FILE = "last_dyn_id.txt"

# 解析多个 Server酱 Key
SCKEY_LIST = [k.strip() for k in SCKEY.split(",") if k.strip()] if SCKEY else []


class BiliWbi:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self._cache = None

    @staticmethod
    def get_mixin_key(img_key, sub_key):
        raw_key = img_key + sub_key
        if len(raw_key) < 64:
            raw_key = raw_key.ljust(64, ' ')
        return ''.join(raw_key[i] for i in MIXIN_KEY_ENC_TAB)

    def _get_wbi_keys(self):
        url = "https://api.bilibili.com/x/web-interface/nav"
        resp = self.session.get(url, timeout=10)
        data = resp.json()
        if data.get('code') != 0:
            raise Exception(f"获取WBI密钥失败: {data.get('message')}")
        wbi_img = data.get('data', {}).get('wbi_img')
        if not wbi_img:
            raise Exception("wbi_img字段不存在")
        img_url = wbi_img.get('img_url')
        sub_url = wbi_img.get('sub_url')
        if not img_url or not sub_url:
            raise Exception("缺少img_url或sub_url")
        img_key = re.search(r'/([^/]+)\.png', img_url).group(1)
        sub_key = re.search(r'/([^/]+)\.png', sub_url).group(1)
        return img_key, sub_key

    def _get_cache_key(self):
        today = time.strftime("%Y%m%d")
        if self._cache and self._cache.get('date') == today:
            return self._cache['key']
        img_key, sub_key = self._get_wbi_keys()
        mixin_key = self.get_mixin_key(img_key, sub_key)
        self._cache = {'key': mixin_key, 'date': today}
        return mixin_key

    def enc_wbi(self, params):
        mixin_key = self._get_cache_key()
        new_params = {k: v for k, v in params.items() if k not in ('w_rid', 'wts')}
        new_params['wts'] = int(time.time())
        sorted_keys = sorted(new_params.keys())
        query_parts = []
        for k in sorted_keys:
            v = new_params[k]
            if isinstance(v, bool):
                v = str(v).lower()
            else:
                v = str(v)
            encoded_value = urllib.parse.quote(v, safe='')
            query_parts.append(f"{k}={encoded_value}")
        query_str = "&".join(query_parts)
        sign_str = query_str + mixin_key
        new_params['w_rid'] = hashlib.md5(sign_str.encode()).hexdigest()
        return new_params


def random_base64_str(min_len=16, max_len=64):
    length = random.randint(min_len, max_len)
    return base64.b64encode(os.urandom(length)).decode('utf-8')


def create_session():
    session = requests.Session()
    session.cookies.set("SESSDATA", SESSDATA, domain=".bilibili.com")
    session.cookies.set("bili_jct", BILI_JCT, domain=".bilibili.com")
    if BUVID3:
        session.cookies.set("buvid3", BUVID3, domain=".bilibili.com")
    session.headers.update(HEADERS)

    # 预热请求（可选，减少首次风控概率）
    try:
        session.get("https://www.bilibili.com/", timeout=10)
        time.sleep(random.uniform(2, 5))
        session.get(f"https://space.bilibili.com/{UP_MID}/dynamic", timeout=10)
        time.sleep(random.uniform(1, 3))
    except:
        pass
    return session


def fetch_dynamics(session):
    wbi = BiliWbi(session)
    base_params = {
        "host_mid": UP_MID,
        "platform": "web",
        "timezone_offset": "-480",
        "web_location": "333.1387",
        "dm_img_list": "[]",
        "dm_img_str": random_base64_str(16, 64),
        "dm_cover_img_str": random_base64_str(32, 128),
        "dm_img_inter": '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}',
        "x-bili-device-req-json": '{"platform":"web","device":"pc","spmid":"333.1387"}',
        "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,avatarAutoTheme,sunflowerStyle,cardsEnhance,eva3CardOpus,eva3CardVideo,eva3CardComment,eva3CardUser"
    }
    signed_params = wbi.enc_wbi(base_params)
    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    resp = session.get(url, params=signed_params, timeout=15)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text}")
        return []
    data = resp.json()
    if data.get("code") != 0:
        print(f"API错误: {data.get('message')}")
        return []
    return data.get("data", {}).get("items", [])


def is_charge_exclusive(item):
    badge = item.get("modules", {}).get("module_author", {}).get("icon_badge")
    if badge and badge.get("text") == "充电专属":
        return True

    major = item.get("modules", {}).get("module_dynamic", {}).get("major")
    if major and major.get("type") == "MAJOR_TYPE_BLOCKED":
        if major.get("blocked", {}).get("blocked_type") == 3:
            return True
    return False


def extract_content(item):
    major = item.get("modules", {}).get("module_dynamic", {}).get("major", {})
    t = major.get("type")
    if t == "MAJOR_TYPE_OPUS":
        nodes = major.get("opus", {}).get("summary", {}).get("rich_text_nodes", [])
        return "".join(n.get("text", "") for n in nodes)
    elif t == "MAJOR_TYPE_BLOCKED":
        return major.get("blocked", {}).get("hint_message", "需充电解锁")
    elif t == "MAJOR_TYPE_ARCHIVE":
        return major.get("archive", {}).get("title", "")
    elif t == "MAJOR_TYPE_DRAW":
        nodes = major.get("draw", {}).get("summary", {}).get("rich_text_nodes", [])
        return "".join(n.get("text", "") for n in nodes)
    return ""

def extract_all_image_urls(item):
    """提取动态中所有图片的URL"""
    major = item.get("modules", {}).get("module_dynamic", {}).get("major", {})
    t = major.get("type")
    urls = []

    if t == "MAJOR_TYPE_OPUS":
        pics = major.get("opus", {}).get("pics", [])
        for pic in pics:
            if pic.get("url"):
                urls.append(pic["url"])

    elif t == "MAJOR_TYPE_DRAW":
        items = major.get("draw", {}).get("items", [])
        for img in items:
            if img.get("src"):
                urls.append(img["src"])

    elif t == "MAJOR_TYPE_ARCHIVE":
        cover = major.get("archive", {}).get("cover")
        if cover:
            urls.append(cover)

    return urls


def push_to_wechat_multi(title, content, sc_keys):
    """
    使用多个 Server酱 Key 推送消息
    返回 True 表示至少有一个推送成功，False 表示全部失败
    """
    if not sc_keys:
        print("未配置 SCKEY，跳过推送")
        return False

    success = False
    for idx, key in enumerate(sc_keys, 1):
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = {"title": title, "desp": content}
        try:
            r = requests.post(url, data=data, timeout=10)
            if r.status_code == 200 and r.json().get("code") == 0:
                print(f"微信推送成功 (Key {idx}/{len(sc_keys)})")
                success = True
            else:
                print(f"微信推送失败 (Key {idx}): {r.text}")
        except Exception as e:
            print(f"微信推送异常 (Key {idx}): {e}")
    return success


def read_last_id():
    try:
        with open(LAST_ID_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def write_last_id(dyn_id):
    with open(LAST_ID_FILE, 'w') as f:
        f.write(dyn_id)


def main():
    print(f"[{datetime.now()}] 开始扫描...")
    session = create_session()
    items = fetch_dynamics(session)

    if not items:
        print("未获取到动态")
        return

    charge_items = [item for item in items if is_charge_exclusive(item)]
    print(f"共获取 {len(items)} 条动态，其中充电专属 {len(charge_items)} 条")

    if not charge_items:
        print("无充电专属动态")
        return

    latest = charge_items[0]
    dyn_id = latest["id_str"]
    last_id = read_last_id()
    print(f"上次推送动态ID: {last_id}, 当前最新充电专属ID: {dyn_id}")

    if dyn_id == last_id:
        print("已推送过，跳过")
        return

    # 构造推送内容
    author = latest.get("modules", {}).get("module_author", {})
    content = extract_content(latest)
    img_urls = extract_all_image_urls(latest)

    # 使用 Markdown 双回车换行（\n\n）
    msg = (
        f"⚡ 充电专属动态\n\n"
        f"UP主：{author.get('name', '未知')}\n\n"
        f"时间：{author.get('pub_time', '未知')}\n\n"
        f"内容：{content}\n\n"
    )

    if img_urls:
        for idx, url in enumerate(img_urls, 1):
            msg += f"![图{idx}]({url})\n\n"

    msg += f"链接：https://t.bilibili.com/{dyn_id}"
    
    # 推送（支持多个 Key）
    if push_to_wechat_multi("B站充电动态提醒", msg, SCKEY_LIST):
        write_last_id(dyn_id)
        print(f"新动态 {dyn_id} 已推送并记录")
    else:
        print(f"推送失败（所有 Key 均失败），动态 {dyn_id} 未记录，下次会重试")

if __name__ == "__main__":
    main()
