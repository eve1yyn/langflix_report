"""
{app_key}_reviews_raw.csv 를 읽어서
- 별점 분포 / 월별 추이
- 불만 리뷰(별점 3점 이하) 키워드 빈도
- 카테고리별 불만 집계
를 계산하고, 앱별 엑셀 요약 리포트를 output/ 에 저장한다.
동시에 리포트(HTML) 생성에 쓸 수 있도록 앱별 요약 결과를 output/summary.json 에 모아 저장한다.
"""

import json
from collections import Counter

import pandas as pd
from kiwipiepy import Kiwi

APPS = {
    "duolingo": "듀오링고",
    "speak": "스픽",
    "langflix": "랭플릭스",
}

# ── 필요시 여기 두 목록만 수정하면 분석 결과를 바로 조정할 수 있습니다 ──

# 키워드 빈도에서 제외할 의미 없는 단어들
STOPWORDS = {
    "앱", "정말", "진짜", "그냥", "너무", "정도", "사용", "때문",
    "이거", "저거", "그것", "우리", "제가", "생각", "그거", "이제",
}

# 카테고리별 매칭 키워드 (리뷰 원문에 포함되면 해당 카테고리로 집계)
CATEGORY_KEYWORDS = {
    "가격/구독": ["가격", "구독", "비싸", "결제", "프리미엄", "슈퍼", "유료"],
    "광고": ["광고"],
    "버그/오류": ["버그", "오류", "튕김", "튕겨", "렉", "멈춤", "멈춰", "크래시", "로딩", "먹통"],
    "UX/사용성": ["불편", "복잡", "헷갈", "어렵", "인터페이스", "버튼", "오작동"],
    "학습효과": ["실력", "효과", "안늘", "늘지", "실용성", "쓸모"],
    "스트릭/동기부여": ["스트릭", "연속", "알림", "푸시", "지루", "재미없", "동기", "에너지", "하트"],
    "AI/튜터": ["ai", "튜터", "선생", "인공지능", "발음", "교정", "피드백"],
    "고객지원": ["문의", "고객센터", "환불", "답변", "cs"],
}

# 신규 기능/변경사항 언급 감지용 키워드 (전체 리뷰 대상, 불만 여부 무관)
FEATURE_MENTION_KEYWORDS = [
    "업데이트", "새로운", "새롭게", "추가되", "추가됐", "리뉴얼", "개편",
    "이벤트", "출시", "신기능", "새기능",
]

kiwi = Kiwi()


def matched_categories(text: str) -> str:
    """리뷰 원문이 어떤 카테고리에 해당하는지 콤마로 나열한 문자열을 반환한다."""
    hits = [cat for cat, kws in CATEGORY_KEYWORDS.items() if any(kw in text.lower() for kw in kws)]
    return ", ".join(hits) if hits else "-"


def analyze_app(app_key: str) -> dict:
    input_path = f"data/{app_key}_reviews_raw.csv"
    excel_output = f"output/{app_key}_review_summary.xlsx"

    df = pd.read_csv(input_path)
    df["date"] = pd.to_datetime(df["date"])
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df["is_complaint"] = df["score"] <= 3

    complaints = df[df["is_complaint"]].copy()

    # 별점 분포 & 월별 추이
    rating_dist = df["score"].value_counts().sort_index()
    monthly_complaint_count = complaints.groupby("year_month").size()

    # 키워드 빈도 분석 (불만 리뷰 대상, 명사만 추출)
    keyword_counter = Counter()
    for text in complaints["review_text"].astype(str):
        for token in kiwi.tokenize(text):
            if token.tag in ("NNG", "NNP") and len(token.form) > 1 and token.form not in STOPWORDS:
                keyword_counter[token.form] += 1
    keyword_freq = pd.DataFrame(keyword_counter.most_common(30), columns=["keyword", "count"])

    # 카테고리 태깅 & 집계 (건수 + 공감수 가중치)
    category_counts, total_thumbs_up, avg_thumbs_up = {}, [], []
    for category, keywords in CATEGORY_KEYWORDS.items():
        matched = complaints["review_text"].astype(str).apply(
            lambda text: any(kw in text.lower() for kw in keywords)
        )
        category_counts[category] = int(matched.sum())
        thumbs = complaints.loc[matched, "thumbs_up_count"]
        total_thumbs_up.append(int(thumbs.sum()))
        avg_thumbs_up.append(round(thumbs.mean(), 1) if len(thumbs) > 0 else 0.0)

    category_summary = pd.DataFrame(
        sorted(category_counts.items(), key=lambda x: x[1], reverse=True),
        columns=["category", "complaint_count"],
    )
    # total_thumbs_up/avg_thumbs_up 순서를 category_summary 정렬 순서에 맞춰 재배열
    order = list(CATEGORY_KEYWORDS.keys())
    tmap = dict(zip(order, total_thumbs_up))
    amap = dict(zip(order, avg_thumbs_up))
    category_summary["total_thumbs_up"] = category_summary["category"].map(tmap)
    category_summary["avg_thumbs_up"] = category_summary["category"].map(amap)

    # 공감수 상위 불만 리뷰 Top 15
    top_complaints = complaints.sort_values("thumbs_up_count", ascending=False).head(15).copy()
    top_complaints["matched_categories"] = top_complaints["review_text"].astype(str).apply(matched_categories)
    top_complaints = top_complaints[["review_text", "score", "date", "thumbs_up_count", "matched_categories"]]

    # 전체 불만 리뷰(카테고리 태깅 포함) — 리포트의 키워드 클릭 필터용
    complaints_all = complaints.copy()
    complaints_all["matched_categories"] = complaints_all["review_text"].astype(str).apply(matched_categories)
    complaints_all = complaints_all.sort_values("thumbs_up_count", ascending=False)
    complaints_all = complaints_all[["review_text", "score", "date", "thumbs_up_count", "matched_categories"]]

    # 신규 기능/변경사항 언급 리뷰 (불만 여부 무관, 전체 리뷰 대상)
    feature_mask = df["review_text"].astype(str).apply(
        lambda text: any(kw in text for kw in FEATURE_MENTION_KEYWORDS)
    )
    feature_mentions = (
        df.loc[feature_mask]
        .sort_values(["date", "thumbs_up_count"], ascending=[False, False])
        .head(8)[["review_text", "score", "date", "thumbs_up_count", "app_version"]]
    )

    # 앱 버전별 불만 추이
    version_trend = (
        complaints.groupby("app_version")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .reset_index(name="complaint_count")
    )

    # 엑셀 저장
    with pd.ExcelWriter(excel_output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="raw_data", index=False)
        complaints.to_excel(writer, sheet_name="complaints", index=False)
        keyword_freq.to_excel(writer, sheet_name="keyword_frequency", index=False)
        category_summary.to_excel(writer, sheet_name="category_summary", index=False)
        top_complaints.to_excel(writer, sheet_name="top_complaints", index=False)
        version_trend.to_excel(writer, sheet_name="version_trend", index=False)

    print(f"[{app_key}] 전체 {len(df)}건 / 불만 {len(complaints)}건 -> {excel_output}")

    return {
        "app_key": app_key,
        "app_name": APPS[app_key],
        "total_count": int(len(df)),
        "complaint_count": int(len(complaints)),
        "avg_score": round(float(df["score"].mean()), 2),
        "rating_dist": {int(k): int(v) for k, v in rating_dist.items()},
        "monthly_complaint_count": {k: int(v) for k, v in monthly_complaint_count.items()},
        "keyword_freq": keyword_freq.to_dict(orient="records"),
        "category_summary": category_summary.to_dict(orient="records"),
        "top_complaints": top_complaints.to_dict(orient="records"),
        "complaints_all": complaints_all.to_dict(orient="records"),
        "feature_mentions": feature_mentions.to_dict(orient="records"),
        "version_trend": version_trend.to_dict(orient="records"),
        "date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
    }


if __name__ == "__main__":
    summary = {}
    for app_key in APPS:
        summary[app_key] = analyze_app(app_key)

    with open("output/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print("-" * 40)
    print("분석 완료. output/summary.json 에 리포트용 데이터 저장됨")
