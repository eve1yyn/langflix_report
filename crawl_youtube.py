"""
YouTube Data API v3로 "랭플릭스에 소스로 쓸만한" 영상 후보를 수집한다.
목표: 영어공부 앱/방법 콘텐츠가 아니라, 해외 셀럽·인플루언서 원본 채널의
인터뷰/토크쇼/브이로그성 영상 — 자연스러운 대화가 이어지는 콘텐츠.
.env 파일의 YOUTUBE_API_KEY를 사용한다 (git에는 커밋되지 않음).

주의: 한국어로 검색하면 한국 예능/밈 재탕 채널이 섞여 들어오고, 미국 종합
트렌딩 차트는 밈 재탕 채널 위주라 둘 다 제외했다. 영어 검색어 + 한글 제목
필터링으로 "원어민 원본 채널" 영상만 남긴다.
"""

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 원어민 원본 채널(토크쇼/인터뷰/인플루언서 브이로그)을 겨냥한 영어 검색어.
SEARCH_QUERIES = [
    "Jimmy Fallon interview",
    "Ellen show clip",
    "SNL sketch",
    "Graham Norton show",
    "celebrity interview funny",
    "viral influencer vlog",
]

PUBLISHED_AFTER_DAYS = 45  # 토크쇼/인플루언서 클립은 밈보다 트렌드 수명이 길어 여유를 둔다
RESULTS_PER_QUERY = 4
MAX_ITEMS = 12

HANGUL_RE = re.compile(r"[가-힯]")


def is_korean_title(title: str) -> bool:
    return bool(HANGUL_RE.search(title))


def api_get(path: str, params: dict) -> dict:
    params = {**params, "key": API_KEY}
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def parse_item(it, source: str):
    snippet = it["snippet"]
    thumb = snippet["thumbnails"].get("medium", snippet["thumbnails"]["default"])["url"]
    return {
        "video_id": it["id"]["videoId"] if isinstance(it["id"], dict) else it["id"],
        "title": html.unescape(snippet["title"]),
        "channel": html.unescape(snippet["channelTitle"]),
        "published_at": snippet["publishedAt"],
        "thumbnail": thumb,
        "default_audio_language": snippet.get("defaultAudioLanguage", ""),
        "source": source,
    }


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
            "relevanceLanguage": "en",
            "regionCode": "US",
        },
    )
    return [parse_item(it, f"search:{query}") for it in data.get("items", [])]


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

    for q in SEARCH_QUERIES:
        try:
            videos = search_videos(q, published_after)
        except Exception as e:
            print(f"[경고] '{q}' 검색 실패: {e}")
            continue
        print(f"[검색: {q}] {len(videos)}건")
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

    # 영어 검색어를 써도 한국 더빙/재업로드 채널이 섞여 들어올 수 있어 한글 제목은 제외.
    # (defaultAudioLanguage는 비어있는 경우가 많아 신뢰도가 낮음 — 제목의 한글 여부가 더 확실하다)
    all_videos = [v for v in all_videos if not is_korean_title(v["title"])]

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=PUBLISHED_AFTER_DAYS)
    all_videos = [
        v for v in all_videos
        if datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) >= cutoff_dt
    ]

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
            "thumbnail": v["thumbnail"],
        }
        for v in all_videos
    ]

    with open("data/youtube_trends.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("-" * 40)
    print(f"{len(out)}건 저장 -> data/youtube_trends.json")


if __name__ == "__main__":
    main()
