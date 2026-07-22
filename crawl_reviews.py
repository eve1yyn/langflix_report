"""
경쟁앱(듀오링고, 스픽) + 자사앱(랭플릭스) 구글플레이 한국어 리뷰 수집 스크립트
data/{key}_reviews_raw.csv 로 각각 저장한다.
"""

import time

import pandas as pd
from google_play_scraper import Sort, reviews

APPS = {
    "duolingo": "com.duolingo",
    "speak": "com.selabs.speak",
    "langflix": "com.thetaone.languagepilotmobile",
}

TARGET_COUNT = 800          # 목표 수집 건수 (없으면 있는 만큼만 수집)
BATCH_SIZE = 200            # 한 번에 요청할 건수


def crawl_app(app_key: str, app_id: str) -> None:
    output_path = f"data/{app_key}_reviews_raw.csv"
    all_reviews = []
    continuation_token = None

    print(f"[{app_key}] 수집 시작 ({app_id})")

    while len(all_reviews) < TARGET_COUNT:
        batch, continuation_token = reviews(
            app_id,
            lang="ko",
            country="kr",
            sort=Sort.NEWEST,
            count=BATCH_SIZE,
            continuation_token=continuation_token,
        )

        if not batch:
            print(f"[{app_key}] 더 이상 가져올 리뷰가 없습니다.")
            break

        all_reviews.extend(batch)
        print(f"[{app_key}] 수집 진행: {len(all_reviews)}건")

        if continuation_token is None:
            break

        time.sleep(1)  # 서버에 부담 주지 않기 위한 대기

    all_reviews = all_reviews[:TARGET_COUNT]

    df = pd.DataFrame(all_reviews)
    df = df[["content", "score", "at", "thumbsUpCount", "reviewCreatedVersion"]]
    df.columns = ["review_text", "score", "date", "thumbs_up_count", "app_version"]

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[{app_key}] 총 {len(df)}건의 리뷰를 저장했습니다 -> {output_path}")
    print("-" * 40)


if __name__ == "__main__":
    for key, app_id in APPS.items():
        crawl_app(key, app_id)
