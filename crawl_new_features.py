"""
구글플레이 스토어 페이지에서 앱별 최신 업데이트 날짜/버전을 가져온다.
(구글플레이가 "새 소식" 텍스트 필드 자체를 더 이상 내려주지 않아,
 실제 변경 내용은 analyze_reviews.py의 feature_mentions — 리뷰에서 포착된
 신규 기능/변경사항 언급 — 으로 보완한다.)

data/new_features.json 으로 저장한다.
"""

import json
from datetime import datetime

from google_play_scraper import app as gp_app

APPS = {
    "duolingo": ("듀오링고", "com.duolingo"),
    "speak": ("스픽", "com.selabs.speak"),
    "langflix": ("랭플릭스", "com.thetaone.languagepilotmobile"),
}


def fetch_app_meta(app_id: str) -> dict:
    info = gp_app(app_id, lang="ko", country="kr")
    updated_ts = info.get("updated")
    return {
        "version": info.get("version"),
        "updated": datetime.fromtimestamp(updated_ts).strftime("%Y-%m-%d") if updated_ts else None,
        "recent_changes": info.get("recentChanges"),
    }


def main():
    result = {}
    for key, (name, app_id) in APPS.items():
        meta = fetch_app_meta(app_id)
        result[key] = {"app_name": name, **meta}
        print(f"[{key}] version={meta['version']} updated={meta['updated']}")

    with open("data/new_features.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("-" * 40)
    print("data/new_features.json 저장 완료")


if __name__ == "__main__":
    main()
