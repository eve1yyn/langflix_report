"""
output/summary.json (analyze_reviews.py 결과) 을 읽어서 index.html 정적 리포트를 생성한다.
Vercel에 그대로 올릴 수 있도록 저장소 루트에 index.html 로 출력한다.

사용법:
    python crawl_reviews.py
    python analyze_reviews.py
    python generate_report.py
    git add index.html && git commit -m "chore: weekly review report" && git push
"""

import json
import math
import urllib.parse
from datetime import date, datetime

APP_ORDER = ["duolingo", "speak", "langflix"]
APP_VAR = {"duolingo": "--duo", "speak": "--speak", "langflix": "--lang"}
OWN_APP = "langflix"

CATEGORY_ORDER = [
    "가격/구독", "버그/오류", "고객지원", "UX/사용성",
    "AI/튜터", "광고", "스트릭/동기부여", "학습효과",
]

QUOTE_COUNT = {"duolingo": 3, "speak": 3, "langflix": 4}
CHIP_COUNT = 8

ICON_CHAT = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 4.5h14v9H7.5L4 16.5V13.5H3z" stroke-linejoin="round"/></svg>'
ICON_ALERT = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M10 3 L18 17 H2 Z"/><line x1="10" y1="8" x2="10" y2="11.5"/><circle cx="10" cy="14" r="0.9" fill="currentColor" stroke="none"/></svg>'
ICON_CALENDAR = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="4" width="14" height="13" rx="1.5"/><line x1="3" y1="8" x2="17" y2="8"/><line x1="7" y1="2.5" x2="7" y2="5.5"/><line x1="13" y1="2.5" x2="13" y2="5.5"/></svg>'


def load_summary():
    with open("output/summary.json", encoding="utf-8") as f:
        return json.load(f)


def complaint_pill(rate: float) -> str:
    if rate < 15:
        return "good"
    if rate <= 25:
        return "warning"
    return "critical"


def truncate(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt_range(date_range):
    start, end = date_range
    return f"{start} ~ {end}"


def build_stat_cards(summary):
    cards = []
    for key in APP_ORDER:
        app = summary[key]
        rate = round(app["complaint_count"] / app["total_count"] * 100, 1)
        pill = complaint_pill(rate)
        own_tag = " (자사)" if key == OWN_APP else ""
        cards.append(f"""
      <div class="stat-card" style="--app-color:var({APP_VAR[key]})">
        <div class="app-name"><span class="dot"></span>{escape_html(app['app_name'])}{own_tag}</div>
        <div class="hero">{app['avg_score']}<small>/5</small></div>
        <div class="rows">
          <div class="row"><span class="lbl">{ICON_CHAT}<span>수집 리뷰</span></span><b>{app['total_count']}건</b></div>
          <div class="row"><span class="lbl">{ICON_ALERT}<span>불만율(★≤3)</span></span><span class="pill {pill}">{rate}%</span></div>
          <div class="row"><span class="lbl">{ICON_CALENDAR}<span>수집 기간</span></span><span>{fmt_range(app['date_range'])}</span></div>
        </div>
      </div>""")
    return "\n".join(cards)


def build_cat_data(summary):
    all_pcts = []
    rows = []
    for cat in CATEGORY_ORDER:
        pcts, counts = [], []
        for key in APP_ORDER:
            app = summary[key]
            cmap = {c["category"]: c["complaint_count"] for c in app["category_summary"]}
            total = app["complaint_count"] or 1
            pct = round(cmap.get(cat, 0) / total * 100, 1)
            pcts.append(pct)
            counts.append(cmap.get(cat, 0))
            all_pcts.append(pct)
        rows.append([cat, pcts, counts])
    domain_max = max(5, math.ceil(max(all_pcts) / 5) * 5) if all_pcts else 5
    return rows, domain_max


def build_rating_data(summary):
    rows = []
    for key in APP_ORDER:
        app = summary[key]
        total = app["total_count"] or 1
        pcts, counts = [], []
        for star in range(1, 6):
            c = app["rating_dist"].get(str(star), app["rating_dist"].get(star, 0))
            pcts.append(round(c / total * 100, 1))
            counts.append(c)
        rows.append([app["app_name"], APP_VAR[key], pcts, counts])
    return rows


def build_chips(app):
    self_name = app["app_name"]
    kws = [k for k in app["keyword_freq"] if k["keyword"] != self_name][:CHIP_COUNT]
    return "\n".join(
        f'        <button type="button" class="chip" data-keyword="{escape_html(k["keyword"])}">'
        f'<b>{escape_html(k["keyword"])}</b> {k["count"]}</button>'
        for k in kws
    )


def build_complaints_json(app, limit=400):
    items = []
    for q in app["complaints_all"]:
        items.append({
            "review_text": truncate(q["review_text"], limit),
            "score": int(q["score"]),
            "date": str(q["date"])[:10],
            "thumbs_up_count": q["thumbs_up_count"],
            "matched_categories": q["matched_categories"],
        })
    return json.dumps(items, ensure_ascii=False)


def build_new_features(summary, features_meta):
    blocks = []
    for key in APP_ORDER:
        app = summary[key]
        meta = features_meta.get(key, {})
        version = meta.get("version") or "정보 없음"
        updated = meta.get("updated") or "정보 없음"

        blocks.append(f"""
      <div class="stat-card" style="--app-color:var({APP_VAR[key]})">
        <div class="app-name"><span class="dot"></span>{escape_html(app['app_name'])}</div>
        <div class="rows">
          <div class="row"><span class="lbl">{ICON_CALENDAR}<span>최근 업데이트</span></span><b>{updated}</b></div>
          <div class="row"><span class="lbl">{ICON_ALERT}<span>현재 버전</span></span><span>{escape_html(str(version))}</span></div>
        </div>
      </div>""")
    return "\n".join(blocks)


def favicon_url(link: str) -> str:
    domain = urllib.parse.urlparse(link).netloc
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def build_news(news_items):
    if not news_items:
        return '      <p class="empty-note">최근 90일 내 수집된 뉴스가 없습니다.</p>'
    cards = []
    for n in news_items:
        cards.append(f"""      <a class="news-card" href="{escape_html(n['link'])}" target="_blank" rel="noopener noreferrer">
        <img class="favicon" src="{escape_html(favicon_url(n['link']))}" alt="" loading="lazy">
        <div class="news-body">
          <div class="news-title">{escape_html(n['title'])}</div>
          <div class="news-meta">{escape_html(n['source'])} · {n['date']}</div>
        </div>
      </a>""")
    return "\n".join(cards)


def build_youtube(videos):
    if not videos:
        return '      <p class="empty-note">최근 수집된 영상이 없습니다.</p>'
    cards = []
    for v in videos:
        likes = f"{v['likes']:,}" if v.get("likes") is not None else "-"
        cards.append(f"""      <a class="yt-card" href="{escape_html(v['url'])}" target="_blank" rel="noopener noreferrer">
        <img class="thumb" src="{escape_html(v['thumbnail'])}" alt="" loading="lazy">
        <div class="yt-body">
          <div class="news-title">{escape_html(v['title'])}</div>
          <div class="news-meta">{escape_html(v['channel'])} · 조회 {v['views']:,} · 좋아요 {likes} · {v['published_at']}</div>
        </div>
      </a>""")
    return "\n".join(cards)


def month_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{y[2:]}.{m}"


def build_trend(app):
    months = list(app["monthly_complaint_count"].keys())
    values = [app["monthly_complaint_count"][m] for m in months]
    n = len(months)
    if n == 0:
        return "[]", "", "", "", ""
    left, right, width = 30, 30, 600
    plot_w = width - left - right
    step = plot_w / (n - 1) if n > 1 else 0
    top_pad, bottom_pad, height = 20, 30, 160
    baseline_y = height - bottom_pad
    plot_h = baseline_y - top_pad
    max_val = max(values)
    y_domain_max = max_val * 1.15 if max_val > 0 else 1

    points = []
    for i, (m, v) in enumerate(zip(months, values)):
        x = round(left + i * step, 2)
        y = round(baseline_y - (v / y_domain_max) * plot_h, 2)
        points.append((month_label(m), v, x, y))

    poly_str = " ".join(f"{x},{y}" for _, _, x, y in points)
    area_str = (
        f"M{points[0][2]},{baseline_y} L"
        + " L".join(f"{x},{y}" for _, _, x, y in points)
        + f" L{points[-1][2]},{baseline_y} Z"
    )
    labels_svg = "\n".join(
        f'          <text x="{x}" y="{height - 13}" text-anchor="middle">{lbl}</text>'
        for lbl, _, x, _ in points
    )

    peak_idx = max(range(n), key=lambda i: values[i])
    peak_lbl, peak_val, peak_x, peak_y = points[peak_idx]
    last_lbl, last_val, last_x, last_y = points[-1]
    is_partial = date.today().strftime("%Y-%m") == months[-1] and date.today().day < 25
    last_suffix = "*" if is_partial else ""

    marks_svg = f'<text x="{peak_x}" y="{max(peak_y - 10, 14)}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ink)">{peak_val}건 (최고)</text>'
    if last_idx_is_different := (peak_idx != n - 1):
        marks_svg += f'\n        <text x="{last_x}" y="{max(last_y - 10, 14)}" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ink)">{last_val}건{last_suffix}</text>'

    trend_json = json.dumps(
        [[lbl, v, x, y] for lbl, v, x, y in points], ensure_ascii=False
    )
    note = (
        f"* {months[-1]}은 {app['date_range'][1]}까지 수집된 부분 데이터입니다."
        if is_partial else ""
    )
    return trend_json, poly_str, area_str, labels_svg, marks_svg, note, baseline_y


def build_summary_paragraphs(summary):
    own = summary[OWN_APP]
    own_rate = round(own["complaint_count"] / own["total_count"] * 100, 1)
    own_top = own["category_summary"][0]
    own_top_pct = (
        round(own_top["complaint_count"] / own["complaint_count"] * 100, 1)
        if own["complaint_count"] else 0
    )

    comp_sentences = []
    for key in ["duolingo", "speak"]:
        app = summary[key]
        rate = round(app["complaint_count"] / app["total_count"] * 100, 1)
        pill = complaint_pill(rate)
        top = app["category_summary"][0]
        top_pct = (
            round(top["complaint_count"] / app["complaint_count"] * 100, 1)
            if app["complaint_count"] else 0
        )
        comp_sentences.append(
            f"<p>{app['app_name']}은 평균 <b>{app['avg_score']}점</b>, 불만율 "
            f"<span class=\"hl {pill}\">{rate}%</span>이며 "
            f"최다 불만 카테고리는 <b>'{top['category']}'({top_pct}%)</b>입니다.</p>"
        )

    own_pill = complaint_pill(own_rate)
    paragraphs = [
        "<p>이번 리포트는 구글플레이 최신 리뷰를 기준으로 랭플릭스와 경쟁 앱(스픽, 듀오링고)의 리뷰 동향을 정리한 것입니다.</p>",
        (
            f"<p>랭플릭스는 평균 별점 <b>{own['avg_score']}점</b>, 불만율 "
            f"<span class=\"hl {own_pill}\">{own_rate}%</span>이며, "
            f"가장 많이 제기된 불만은 <b>'{own_top['category']}'({own_top_pct}%)</b>입니다.</p>"
        ),
        *comp_sentences,
    ]
    return "\n".join(paragraphs)


def build_period_note(summary):
    parts = [
        f"{summary[k]['app_name']} {fmt_range(summary[k]['date_range'])} ({summary[k]['total_count']}건)"
        for k in APP_ORDER
    ]
    ranges_str = " · ".join(parts)
    return (
        f"수집 기준은 앱별 최신 리뷰 최대 800건입니다(랭플릭스는 리뷰 수가 적어 전체 "
        f"{summary[OWN_APP]['total_count']}건을 모두 포함). 리뷰가 자주 달리는 앱일수록 800건이 더 짧은 "
        f"기간에 몰려 있어 앱마다 실제 수집 기간이 다릅니다 — {ranges_str}."
    )


def build_version_table(app, n=5):
    rows = app["version_trend"][:n]
    if not rows:
        return '                <tr><td colspan="3" class="empty-note">표본이 충분한 버전이 없습니다.</td></tr>'
    return "\n".join(
        f"        <tr><td>{escape_html(v['app_version'])}</td>"
        f"<td>{v['complaint_rate']}%</td>"
        f"<td>{v['total_count']}건</td></tr>"
        for v in rows
    )


def load_json_if_exists(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def main():
    summary = load_summary()
    features_meta = load_json_if_exists("data/new_features.json") or {}
    news_items = load_json_if_exists("data/industry_news.json") or []
    youtube_items = load_json_if_exists("data/youtube_trends.json") or []

    stat_cards = build_stat_cards(summary)
    cat_rows, domain_max = build_cat_data(summary)
    rating_rows = build_rating_data(summary)
    trend_json, poly_str, area_str, labels_svg, marks_svg, trend_note, baseline_y = build_trend(
        summary[OWN_APP]
    )

    with open("report_template.html", encoding="utf-8") as f:
        template = f.read()

    own = summary[OWN_APP]

    html = (
        template.replace("__GEN_DATE__", date.today().isoformat())
        .replace("__SUMMARY_PARAGRAPHS__", build_summary_paragraphs(summary))
        .replace("__PERIOD_NOTE__", build_period_note(summary))
        .replace("__STAT_CARDS__", stat_cards)
        .replace("__CAT_DATA_JSON__", json.dumps(cat_rows, ensure_ascii=False))
        .replace("__DOMAIN_MAX__", str(domain_max))
        .replace(
            "__RATING_DATA_JSON__",
            json.dumps(
                [[name, var, pcts, counts] for name, var, pcts, counts in rating_rows],
                ensure_ascii=False,
            ),
        )
        .replace("__TREND_JSON__", trend_json)
        .replace("__TREND_POLY__", poly_str)
        .replace("__TREND_AREA__", area_str)
        .replace("__TREND_LABELS_SVG__", labels_svg)
        .replace("__TREND_MARKS_SVG__", marks_svg)
        .replace("__TREND_NOTE__", trend_note)
        .replace("__TREND_BASELINE_Y__", str(baseline_y))
        .replace("__DUO_CHIPS__", build_chips(summary["duolingo"]))
        .replace("__SPEAK_CHIPS__", build_chips(summary["speak"]))
        .replace("__LANG_CHIPS__", build_chips(own))
        .replace("__DUO_COMPLAINTS_JSON__", build_complaints_json(summary["duolingo"]))
        .replace("__SPEAK_COMPLAINTS_JSON__", build_complaints_json(summary["speak"]))
        .replace("__LANG_COMPLAINTS_JSON__", build_complaints_json(own))
        .replace("__DUO_DEFAULT_N__", str(QUOTE_COUNT["duolingo"]))
        .replace("__SPEAK_DEFAULT_N__", str(QUOTE_COUNT["speak"]))
        .replace("__LANG_DEFAULT_N__", str(QUOTE_COUNT["langflix"]))
        .replace("__VERSION_ROWS__", build_version_table(own))
        .replace("__NEW_FEATURES_HTML__", build_new_features(summary, features_meta))
        .replace("__NEWS_HTML__", build_news(news_items))
        .replace("__YOUTUBE_HTML__", build_youtube(youtube_items))
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html 생성 완료")


if __name__ == "__main__":
    main()
