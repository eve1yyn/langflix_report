"""
Google 뉴스 RSS(공식 API 키 불필요)로 영어학습/에듀테크 업계 뉴스를 수집한다.
투자유치, 정책 변화 등 키워드로 여러 번 검색해 최신순으로 모으고 제목 기준 중복 제거.

data/industry_news.json 으로 저장한다.
"""

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

QUERIES = [
    "영어학습 투자유치",
    "에듀테크 투자",
    "영어교육 스타트업",
    "스픽 영어",
    "듀오링고",
    "AI 영어교육",
    "교육부 영어교육 정책",
]

MAX_AGE_DAYS = 90
MAX_ITEMS = 12


def fetch_query(query: str):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()

    root = ET.fromstring(data)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        items.append({"title": title, "link": link, "pub_date": pub_date, "source": source})
    return items


def parse_date(pub_date: str):
    try:
        return datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    seen_titles = set()
    all_items = []

    for q in QUERIES:
        try:
            items = fetch_query(q)
        except Exception as e:
            print(f"[경고] '{q}' 검색 실패: {e}")
            continue
        print(f"[{q}] {len(items)}건 조회")
        for it in items:
            key = it["title"].split(" - ")[0].strip()
            key = "".join(ch for ch in key if ch.isalnum())
            if key in seen_titles:
                continue
            seen_titles.add(key)
            it["parsed_date"] = parse_date(it["pub_date"])
            it["query"] = q
            all_items.append(it)

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    recent = [it for it in all_items if it["parsed_date"] and it["parsed_date"] >= cutoff]
    recent.sort(key=lambda x: x["parsed_date"], reverse=True)
    recent = recent[:MAX_ITEMS]

    out = [
        {
            "title": it["title"].rsplit(" - ", 1)[0].strip(),
            "source": it["source"] or (it["title"].rsplit(" - ", 1)[-1] if " - " in it["title"] else ""),
            "link": it["link"],
            "date": it["parsed_date"].strftime("%Y-%m-%d"),
        }
        for it in recent
    ]

    with open("data/industry_news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("-" * 40)
    print(f"최근 {MAX_AGE_DAYS}일 이내 {len(out)}건 저장 -> data/industry_news.json")


if __name__ == "__main__":
    main()
