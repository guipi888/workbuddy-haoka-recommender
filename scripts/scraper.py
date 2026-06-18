#!/usr/bin/env python3
"""
好卡流量卡数据抓取器
从 haokawx.lot-ml.com 鸣日科技店铺抓取全部流量卡产品数据。

抓取策略：agent-browser 实时抓取（最多3次重试）→ 失败回退本地缓存
实时抓取同时提取每张卡的办理链接（shareUrl），用户点击可直接办理。

Usage:
    python3 scraper.py                      # 实时抓取+缓存兜底，输出JSON
    python3 scraper.py --cache-only          # 仅读缓存
    python3 scraper.py --output cards.json   # 保存到文件
    python3 scraper.py --format text         # 文本格式输出
"""

import json
import re
import subprocess
import sys
import time
import os
import urllib.request
import urllib.parse
import ssl
from html.parser import HTMLParser

SHOP_ID = "8eabe44066833227"
BASE_URL = "https://haokawx.lot-ml.com"
PAGE_URL = f"{BASE_URL}/ProductEn/Index/{SHOP_ID}"
API_URL = f"{BASE_URL}/ProductEn/Index2/{SHOP_ID}"

# 缓存路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
CACHE_PATH = os.path.join(SKILL_DIR, "assets", "cards_cache.json")

MAX_RETRIES = 3


# ═══════════════════════════════════════════════════════════
#  Snapshot 文本解析器（从 agent-browser snapshot 输出中提取卡片）
# ═══════════════════════════════════════════════════════════

def parse_snapshot(snapshot_text):
    """
    从 agent-browser snapshot 文本中提取结构化卡片数据。
    状态机解析，支持 "StaticText" 格式的输出。
    """
    lines = snapshot_text.split('\n')
    card_starts = []

    # 找到所有产品卡片的 listitem
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '- listitem [level=1]':
            next_few = '\n'.join(lines[idx:idx + 8])
            if 'StaticText' in next_few and ('¥' in next_few or '月租' in next_few):
                card_starts.append(idx)

    cards = []
    for start_idx in card_starts:
        end_idx = start_idx + 1
        while end_idx < len(lines):
            stripped = lines[end_idx].strip()
            if stripped == '- listitem [level=1]' and end_idx != start_idx:
                break
            if stripped.startswith('- heading '):
                break
            end_idx += 1

        block = lines[start_idx:end_idx]
        block_text = '\n'.join(block)
        texts = re.findall(r'StaticText "([^"]*)"', block_text)

        phase = 'name'
        card = {
            'name': '', 'taocan': '', 'isp': '',
            'nowPrice': '', 'priceUnitStr': '月租费用',
            'tyLiuliang': '', 'dxLiuliang': '',
            'tonghua': '0', 'age': '',
            'isSelectNum': '', 'isPhotos': '',
            'keywords': [], 'sales': '', 'zhutui': False
        }

        for t in texts:
            if phase == 'name':
                if '【' in t and '】' in t:
                    card['name'] = t
                    phase = 'taocan'
                continue

            if phase == 'taocan':
                if '选号' in t:
                    card['isSelectNum'] = t
                    phase = 'select_photo'
                    continue
                if '照片' in t:
                    card['isPhotos'] = t
                    continue
                if not t.startswith('¥'):
                    card['taocan'] = t
                continue

            if phase == 'select_photo':
                if '选号' in t:
                    card['isSelectNum'] = t
                    continue
                if '照片' in t:
                    card['isPhotos'] = t
                    continue
                if t.startswith('¥'):
                    card['nowPrice'] = t
                    phase = 'price_details'
                    continue

            if phase == 'price_details':
                if t.startswith('¥') or t == '月租费用':
                    continue
                if t in ('通用流量', '定向流量', '通话分钟'):
                    continue
                if '年龄' in t:
                    card['age'] = t
                    phase = 'keywords'
                    continue
                if not card['tyLiuliang'] and re.match(r'^[\d.]+G$', t):
                    card['tyLiuliang'] = t
                elif not card['dxLiuliang'] and re.match(r'^[\d.]+G$', t):
                    card['dxLiuliang'] = t
                elif re.match(r'^\d+$', t):
                    card['tonghua'] = t
                continue

            if phase == 'keywords':
                skip = {'分享', '立即办理', '通用流量', '定向流量', '月租费用', '通话分钟'}
                if t in skip:
                    continue
                if t == card['name'] or t == card['taocan']:
                    continue
                if t.startswith('¥'):
                    continue
                if re.match(r'^[\d.]+G$', t):
                    continue
                if re.match(r'^\d+$', t) and '领取' not in t:
                    continue
                card['keywords'].append(t)

        # ISP
        if '电信' in card['name']: card['isp'] = '电信'
        elif '联通' in card['name']: card['isp'] = '联通'
        elif '移动' in card['name']: card['isp'] = '移动'
        elif '广电' in card['name']: card['isp'] = '广电'

        # 从 keywords 中分离销量
        clean_kw = []
        for kw in card['keywords']:
            if '领取' in kw:
                num = kw.replace('领取', '').strip()
                if num.isdigit():
                    card['sales'] = num
                    continue
            clean_kw.append(kw)
        card['keywords'] = clean_kw

        cards.append(card)

    return cards


# ═══════════════════════════════════════════════════════════
#  agent-browser 实时抓取（主数据源）
# ═══════════════════════════════════════════════════════════

def _run_agent_browser(cmd_args, timeout=60):
    """运行 agent-browser 命令并返回 stdout。"""
    try:
        result = subprocess.run(
            ['agent-browser'] + cmd_args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode == 0
    except Exception as e:
        return str(e), False


def _is_valid_cards(cards):
    """判断抓取的卡片数据是否有效。"""
    if not cards or len(cards) < 10:
        return False
    # 至少有一张卡有名称和价格
    valid_count = sum(1 for c in cards if c.get('name') and c.get('nowPrice'))
    return valid_count >= 10


def fetch_via_agent_browser(max_retries=MAX_RETRIES):
    """
    通过 playwright 实时抓取卡片数据（含 shareUrl 办理链接）。
    最多重试 max_retries 次，返回 (cards, success)。
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[实时抓取] playwright 未安装，回退缓存", file=sys.stderr)
        return [], False

    for attempt in range(1, max_retries + 1):
        print(f"[实时抓取] 第 {attempt}/{max_retries} 次尝试...", file=sys.stderr)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(PAGE_URL, wait_until='networkidle', timeout=30000)

                # 提取所有卡片的名称和 shareUrl
                cards_data = page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('#jingxuan li');
                        return Array.from(items).map(li => {
                            const nameEl = li.querySelector('.spantitle');
                            const linkEl = li.querySelector('a[href]');
                            const priceEl = li.querySelector('.span_g.red');
                            const tyEl = li.querySelectorAll('.span_g');
                            let ty = '', dx = '', calls = '0';
                            const allSpan = Array.from(li.querySelectorAll('.span_g'));
                            let trafficIdx = 0;
                            for (const s of allSpan) {
                                const t = s.textContent.trim();
                                if (/^\\d+G$/.test(t)) {
                                    if (trafficIdx == 0) ty = t;
                                    else if (trafficIdx == 1) dx = t;
                                    else if (trafficIdx == 2) calls = t;
                                    trafficIdx++;
                                }
                            }
                            const selectEl = li.querySelectorAll('.b6li_text');
                            let isSelect = '', isPhotos = '';
                            for (const el of selectEl) {
                                const t = el.textContent.trim();
                                if (t.includes('选号')) isSelect = t;
                                if (t.includes('照片')) isPhotos = t;
                            }
                            const keywords = [];
                            const tagEls = li.querySelectorAll('.b1 span');
                            for (const el of tagEls) {
                                const t = el.textContent.trim();
                                if (t && !['分享','立即办理'].includes(t)) keywords.push(t);
                            }
                            return {
                                name: nameEl ? nameEl.textContent.trim() : '',
                                shareUrl: linkEl ? linkEl.href : '',
                                nowPrice: priceEl ? priceEl.textContent.trim() : '',
                                tyLiuliang: ty,
                                dxLiuliang: dx,
                                tonghua: calls,
                                isSelectNum: isSelect || '',
                                isPhotos: isPhotos || '',
                                keywords: keywords
                            };
                        }).filter(c => c.name);
                    }
                """)

                browser.close()

            if not cards_data or len(cards_data) < 10:
                print(f"[实时抓取] 第{attempt}次：只解析出 {len(cards_data) if cards_data else 0} 张卡片（不足10张）", file=sys.stderr)
                continue

            # 补全 ISP、销量等字段
            cards = []
            for item in cards_data:
                card = {
                    'name': item.get('name', ''),
                    'taocan': '',
                    'isp': '',
                    'nowPrice': item.get('nowPrice', ''),
                    'priceUnitStr': '月租费用',
                    'tyLiuliang': item.get('tyLiuliang', ''),
                    'dxLiuliang': item.get('dxLiuliang', ''),
                    'tonghua': item.get('tonghua', '0'),
                    'age': '',
                    'isSelectNum': item.get('isSelectNum', ''),
                    'isPhotos': item.get('isPhotos', ''),
                    'keywords': item.get('keywords', []),
                    'sales': '',
                    'shareUrl': item.get('shareUrl', ''),
                    'zhutui': False
                }
                # ISP
                if '电信' in card['name']: card['isp'] = '电信'
                elif '联通' in card['name']: card['isp'] = '联通'
                elif '移动' in card['name']: card['isp'] = '移动'
                elif '广电' in card['name']: card['isp'] = '广电'
                # 销量
                for kw in card['keywords']:
                    if '领取' in kw:
                        num = kw.replace('领取', '').strip()
                        if num.isdigit():
                            card['sales'] = num
                            break
                cards.append(card)

            print(f"[实时抓取] 第{attempt}次成功：解析出 {len(cards)} 张卡片（含办理链接）", file=sys.stderr)
            _update_cache(cards)
            return cards, True

        except Exception as e:
            print(f"[实时抓取] 第{attempt}次失败：{e}", file=sys.stderr)
            continue

    return [], False


def _update_cache(cards):
    """实时抓取成功后更新本地缓存。"""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
        print(f"[缓存更新] 已写入 {len(cards)} 张卡片到 {CACHE_PATH}", file=sys.stderr)
    except Exception as e:
        print(f"[缓存更新] 写入失败: {e}", file=sys.stderr)


def load_cache():
    """从本地缓存加载卡片数据。"""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            if _is_valid_cards(cards):
                return cards, True
        except Exception as e:
            print(f"[缓存] 读取失败: {e}", file=sys.stderr)
    return [], False


# ═══════════════════════════════════════════════════════════
#  筛选 & 格式化（从旧版保留）
# ═══════════════════════════════════════════════════════════

def filter_cards(cards, **filters):
    """
    Filter cards by user criteria.

    Supported filters:
        province: str - 省份名（如"广东"、"全国"）
        city: str - 城市名
        isp: str - 运营商（电信/联通/移动/广电）
        max_price: int - 最高月租
        min_traffic: int - 最低通用流量(GB)
        max_traffic: int - 最高通用流量(GB)
        need_calls: bool - 是否需要通话分钟
        min_calls: int - 最低通话分钟
        min_age: int - 最低年龄
        max_age: int - 最高年龄
        need_select_num: bool - 是否需要支持选号
        keyword: str - 名称关键词搜索
        exclude_photos: bool - 排除需要传照片的
    """
    results = []
    for card in cards:
        if filters.get("isp") and card["isp"] != filters["isp"]:
            continue

        price_val = int(re.sub(r"[¥\s]", "", card["nowPrice"])) if card["nowPrice"] else 0
        if filters.get("max_price") and price_val > filters["max_price"]:
            continue

        ty_val = int(re.sub(r"[G\s]", "", card["tyLiuliang"])) if card["tyLiuliang"] else 0
        if filters.get("min_traffic") and ty_val < filters["min_traffic"]:
            continue
        if filters.get("max_traffic") and ty_val > filters["max_traffic"]:
            continue

        call_val = int(card["tonghua"]) if card["tonghua"] and card["tonghua"].isdigit() else 0
        if filters.get("need_calls") and call_val == 0:
            continue
        if filters.get("min_calls") and call_val < filters["min_calls"]:
            continue

        age_match = re.search(r"(\d+)[-~](\d+)", card.get("age", ""))
        if age_match:
            age_min, age_max = int(age_match.group(1)), int(age_match.group(2))
            if filters.get("min_age") and age_max < filters["min_age"]:
                continue
            if filters.get("max_age") and age_min > filters["max_age"]:
                continue

        if filters.get("province"):
            province = filters["province"]
            all_text = card["name"] + " " + " ".join(card["keywords"])
            if province == "全国":
                if not any(w in all_text for w in ["全国", "发全国", "全国可发", "全国发货"]):
                    continue
            else:
                if province not in all_text:
                    continue

        if filters.get("city"):
            city = filters["city"]
            all_text = card["name"] + " " + " ".join(card["keywords"])
            if city not in all_text:
                continue

        if filters.get("keyword"):
            if filters["keyword"] not in card["name"]:
                continue

        if filters.get("need_select_num") and "支持" not in card.get("isSelectNum", ""):
            continue

        if filters.get("exclude_photos") and "需传" in card.get("isPhotos", ""):
            continue

        results.append(card)

    results.sort(key=lambda c: (
        not c.get("zhutui", False),
        -int(c.get("sales", "0")) if c.get("sales", "").isdigit() else 0
    ))
    return results


def format_cards_table(cards):
    """将多张卡片格式化为 Markdown 表格。"""
    header = "| # | 卡片名称 | 运营商 | 月租 | 通用流量 | 通话 | 年龄要求 | 适用地区 | 已办理 | 办理 |"
    sep    = "|---|---------|--------|------|---------|------|---------|---------|--------|------|"
    rows = []
    for i, card in enumerate(cards, 1):
        name = card.get('name', '')
        isp = card.get('isp', '')
        price = card.get('nowPrice', '')
        ty = card.get('tyLiuliang', '')
        calls = f"{card.get('tonghua', '0')}分钟"
        age = card.get('age', '').replace('年龄：', '').replace('周岁', '岁')
        # Extract region from keywords
        region_kws = [kw for kw in card.get('keywords', []) if any(w in kw for w in ['全国', '广东', '发货', '可发', '仅发', '仅限'])]
        region = region_kws[0] if region_kws else '见标签'
        sales = f"{int(card['sales']):,}人" if card.get('sales', '').isdigit() else '-'
        zhutui = "🔥" if card.get('zhutui') else ""
        # Link
        if card.get('shareUrl'):
            link = f"[办理]({card['shareUrl']})"
        else:
            link = f"[店铺]({SHOP_URL})"
        rows.append(f"| {i} | {zhutui}{name} | {isp} | {price} | {ty} | {calls} | {age} | {region} | {sales} | {link} |")
    return "\n".join([header, sep] + rows)


def format_card(card, index=None):
    """Format a single card for display (legacy, used for single card detail)."""
    prefix = f"**{index}.** " if index else ""

    lines = [
        f"{prefix}**{card['name']}**",
        f"   📡 运营商：{card['isp']}",
        f"   💰 月租：{card['nowPrice']}（{card['priceUnitStr']}）",
        f"   📱 套餐：{card['taocan']}",
        f"   📶 通用流量：{card['tyLiuliang']} | 定向流量：{card['dxLiuliang']}",
        f"   📞 通话：{card['tonghua']}分钟",
        f"   👤 {card['age']}",
        f"   ✅ 选号：{card['isSelectNum']} | 照片：{card['isPhotos']}",
    ]

    if card.get("keywords"):
        lines.append(f"   🏷️ 标签：{' | '.join(card['keywords'])}")

    if card.get("sales"):
        lines.append(f"   📊 已办理：{card['sales']}人")

    # 办理链接（用户可直接点击办理）
    if card.get("shareUrl"):
        lines.append(f"   👉 **[点击立即办理]({card['shareUrl']})**")
    else:
        lines.append(f"   👉 **[前往店铺办理]({SHOP_URL})**")

    if card.get("zhutui"):
        lines.insert(0, "   🔥 **主推产品**")

    return "\n".join(lines)


SHOP_URL = "https://haokawx.lot-ml.com/ProductEn/Index/8eabe44066833227"


def format_results_footer():
    """推荐结果末尾的引流信息（整组推荐结束后输出一次）。"""
    return (
        f"\n🏪 **查看店铺全部卡片**：{SHOP_URL}\n"
        "💡 更多实用 AI 效率工具和技能，关注公众号「桂皮AI实战」\n"
        "📱 加入自媒体&AI 副业变现交流群：https://e418e2e692454bfaa8b6206e3f0ba789.app.codebuddy.work"
    )


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="好卡流量卡数据抓取器")
    parser.add_argument("--output", "-o", help="输出JSON文件路径")
    parser.add_argument("--cache-only", action="store_true", help="仅使用缓存")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="输出格式")
    parser.add_argument("--province", default="全部", help="省份筛选")
    parser.add_argument("--city", default="全部", help="城市筛选")
    parser.add_argument("--keyword", default="", help="关键词搜索")
    args = parser.parse_args()

    cards = []
    from_cache = False

    if args.cache_only:
        print("[模式] 仅使用缓存", file=sys.stderr)
        cards, ok = load_cache()
        from_cache = True
        if not ok:
            print("[错误] 缓存不可用", file=sys.stderr)
            cards = []
    else:
        # 实时抓取优先（最多3次重试）
        cards, ok = fetch_via_agent_browser(max_retries=MAX_RETRIES)
        if ok:
            from_cache = False
        else:
            # 回退缓存
            print("[回退] 实时抓取失败3次，回退到本地缓存", file=sys.stderr)
            cards, ok = load_cache()
            from_cache = True
            if not ok:
                print("[错误] 缓存也不可用，无数据返回", file=sys.stderr)
                cards = []

    # 关闭 agent-browser（如果之前打开过）
    _run_agent_browser(['close'], timeout=10)

    if args.format == "text":
        for i, card in enumerate(cards, 1):
            print(format_card(card, i))
            print()
    else:
        output = json.dumps({
            "cards": cards,
            "total": len(cards),
            "from_cache": from_cache,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        }, ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Saved {len(cards)} cards to {args.output}", file=sys.stderr)
        else:
            print(output)


if __name__ == "__main__":
    main()
