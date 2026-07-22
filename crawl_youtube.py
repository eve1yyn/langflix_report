"""
YouTube Data API v3로 영어학습 콘텐츠 중 최근 화제되는 영상을 수집한다.
.env 파일의 YOUTUBE_API_KEY를 사용한다 (git에는 커밋되지 않음).

data/youtube_trends.json 으로 저장한다.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.environ.get("YOUTUBE_API_KEY")

QUERIES = [
    "영어공부 브이로그",
    "영어회화 앱 후기",
    "스픽 영어",
    "듀오링고",
    "AI 영어 학습",
    "영어 쇼츠",
]

PUBLISHED_AFTER_DAYS = 30
RESULTS_PER_QUERY = 4
MAX_ITEMS = 12


def api_get(path: str, params: dict) -> dict:
    params = {**params, "key": API_KEY}
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def search_videos(query: str, published_after: str):
    data = api_get(
        "search",
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "maxResults": RESULTS_PER_QUERY,
            "publishedAfter": published_after,
            "relevanceLanguage": "ko",
        },
    )
    return [
        {
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "published_at": it["snippet"]["publishedAt"],
            "query": query,
        }
        for it in data.get("items", [])
    ]


def fetch_stats(video_ids):
    if not video_ids:
        return {}
    data = api_get("videos", {"part": "statistics", "id": ",".join(video_ids)})
    return {
        item["id"]: {
            "views": int(item["statistics"].get("viewCount", 0)),
            "likes": int(item["statistics"].get("likeCount", 0)) if "likeCount" in item["statistics"] else None,
        }
        for item in data.get("items", [])
    }


def main():
    if not API_KEY:
        raise SystemExit("YOUTUBE_API_KEY가 .env에 없습니다.")

    published_after = (datetime.now(timezone.utc) - timedelta(days=PUBLISHED_AFTER_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    all_videos, seen = [], set()
    for q in QUERIES:
        try:
            videos = search_videos(q, published_after)
        except Exception as e:
            print(f"[경고] '{q}' 검색 실패: {e}")
            continue
        print(f"[{q}] {len(videos)}건")
        for v in videos:
            if v["video_id"] in seen:
                continue
            seen.add(v["video_id"])
            all_videos.append(v)

    stats = fetch_stats([v["video_id"] for v in all_videos])
    for v in all_videos:
        s = stats.get(v["video_id"], {})
        v["views"] = s.get("views", 0)
        v["likes"] = s.get("likes")

    # YouTube의 publishedAfter 필터가 가끔 오래된 영상을 흘려보내므로 한 번 더 걸러낸다.
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=PUBLISHED_AFTER_DAYS)
    all_videos = [
        v for v in all_videos
        if datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) >= cutoff_dt
    ]

    # 광범위한 검색어("영어 쇼츠")는 학습과 무관한 바이럴 영상을 섞어오기 쉬워 제목 기준으로 한 번 더 거른다.
    def is_relevant(v):
        if v["query"] != "영어 쇼츠":
            return True
        title = v["title"].lower()
        return "영어" in title or "english" in title

    all_videos = [v for v in all_videos if is_relevant(v)]

    all_videos.sort(key=lambda v: v["views"], reverse=True)
    all_videos = all_videos[:MAX_ITEMS]

    out = [
        {
            "title": v["title"],
            "channel": v["channel"],
            "views": v["views"],
            "likes": v["likes"],
            "published_at": v["published_at"][:10],
            "url": f"https://www.youtube.com/watch?v={v['video_id']}",
        }
        for v in all_videos
    ]

    with open("data/youtube_trends.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("-" * 40)
    print(f"{len(out)}건 저장 -> data/youtube_trends.json")


if __name__ == "__main__":
    main()
