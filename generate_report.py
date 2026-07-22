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
          <div class="row"><span>수집 리뷰</span><b>{app['total_count']}건</b></div>
          <div class="row"><span>불만율(★≤3)</span><span class="pill {pill}">{rate}%</span></div>
          <div class="row"><span>수집 기간</span><span>{fmt_range(app['date_range'])}</span></div>
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
        f'        <span class="chip"><b>{escape_html(k["keyword"])}</b> {k["count"]}</span>'
        for k in kws
    )


def build_quote_cards(app, n):
    cards = []
    for q in app["top_complaints"][:n]:
        score = int(q["score"])
        score_cls = "score mid" if score == 3 else "score"
        date_str = str(q["date"])[:10]
        cats = q["matched_categories"]
        tags = ""
        if cats and cats != "-":
            tags = '<div class="tags">' + "".join(
                f'<span class="tag">{escape_html(c.strip())}</span>' for c in cats.split(",")
            ) + "</div>"
        cards.append(f"""        <div class="quote-card">
          <div class="qmeta"><span class="{score_cls}">{score}점</span><span>{date_str}</span><span>· 공감 {q['thumbs_up_count']}</span></div>
          <p>{escape_html(truncate(q['review_text']))}</p>
          {tags}
        </div>""")
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


def build_version_table(app, n=5):
    rows = app["version_trend"][:n]
    return "\n".join(
        f"        <tr><td>{escape_html(v['app_version'])}</td><td>{v['complaint_count']}건</td></tr>"
        for v in rows
    )


def main():
    summary = load_summary()

    stat_cards = build_stat_cards(summary)
    cat_rows, domain_max = build_cat_data(summary)
    rating_rows = build_rating_data(summary)
    trend_json, poly_str, area_str, labels_svg, marks_svg, trend_note, baseline_y = build_trend(
        summary[OWN_APP]
    )

    with open("report_template.html", encoding="utf-8") as f:
        template = f.read()

    own = summary[OWN_APP]
    meta_ranges = " · ".join(
        f"{summary[k]['app_name']} {fmt_range(summary[k]['date_range'])}" for k in APP_ORDER
    )

    html = (
        template.replace("__GEN_DATE__", date.today().isoformat())
        .replace("__META_RANGES__", meta_ranges)
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
        .replace("__DUO_QUOTES__", build_quote_cards(summary["duolingo"], QUOTE_COUNT["duolingo"]))
        .replace("__SPEAK_QUOTES__", build_quote_cards(summary["speak"], QUOTE_COUNT["speak"]))
        .replace("__LANG_QUOTES__", build_quote_cards(own, QUOTE_COUNT["langflix"]))
        .replace("__VERSION_ROWS__", build_version_table(own))
        .replace(
            "__FOOTER_COUNTS__",
            " · ".join(
                f"{summary[k]['app_name']} {summary[k]['total_count']}건"
                for k in APP_ORDER
            ),
        )
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html 생성 완료")


if __name__ == "__main__":
    main()
