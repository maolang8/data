import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="제주 크루즈 날씨 기반 관광 대시보드")


@app.cell
def __():
    import json
    import sqlite3
    import urllib.parse
    import urllib.request
    from datetime import date, datetime, timedelta
    from functools import lru_cache
    from pathlib import Path

    import marimo as mo
    import folium
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    DB_PATH = Path(__file__).parent / "data" / "cruise_dashboard.db"
    DATA_DIR = Path(__file__).parent / "data"
    ANALYSIS_DIR = Path(__file__).parent / "analysis"
    with open(DATA_DIR / "risk_rules.json", encoding="utf-8") as rules_file:
        RISK_RULES = json.load(rules_file)

    def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def fmt_int(value) -> str:
        return f"{int(value):,}" if pd.notna(value) else "-"

    def footer(tools: str, sources: str, as_of: str):
        return mo.Html(
            f"""
            <div style="border-top:1px solid #334155;color:#94a3b8;font-size:10px;margin-top:24px;padding-top:10px;display:flex;flex-wrap:wrap;gap:18px">
              <span><b>도구</b> {tools}</span>
              <span><b>자료</b> {sources}</span>
              <span><b>기준</b> {as_of}</span>
            </div>
            """
        )

    def status_badge(text: str, tone: str = "info") -> str:
        colors = {
            "info": ("#e5f2fb", "#0e5e9a"), "green": ("#e3f5ed", "#146849"),
            "amber": ("#fff0d4", "#8a5305"), "red": ("#fde4e5", "#9d272c"),
            "gray": ("#edf0f3", "#586676"),
        }
        bg, fg = colors.get(tone, colors["info"])
        return f'<span style="display:inline-block;padding:3px 7px;border-radius:4px;font-size:11px;font-weight:700;background:{bg};color:{fg}">{text}</span>'

    def metric_card(label: str, value: str, caption: str, tone: str = "blue"):
        accent = {"blue": "#38bdf8", "green": "#10b981", "amber": "#f59e0b", "red": "#f43f5e", "gray": "#64748b"}.get(tone, "#38bdf8")
        return mo.Html(
            f"""
            <div style="background:#1e293b;border:1px solid #334155;border-top:3px solid {accent};border-radius:6px;padding:14px 16px;min-height:112px">
              <div style="color:#94a3b8;font-size:12px;font-weight:700">{label}</div>
              <div style="color:#f8fafc;font-size:25px;font-weight:800;margin:8px 0 5px">{value}</div>
              <div style="color:#94a3b8;font-size:12px;line-height:1.4">{caption}</div>
            </div>
            """
        )

    @lru_cache(maxsize=128)
    def fetch_open_meteo(day: str, latitude: float, longitude: float) -> dict:
        target = date.fromisoformat(day)
        today = date.today()
        base = (
            "https://archive-api.open-meteo.com/v1/archive"
            if target < today - timedelta(days=5)
            else "https://api.open-meteo.com/v1/forecast"
        )
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": day,
            "end_date": day,
            "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
            "wind_speed_unit": "ms",
            "timezone": "Asia/Seoul",
        }
        url = base + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.load(response)
        hourly = pd.DataFrame(payload.get("hourly", {}))
        if hourly.empty:
            raise ValueError("시간별 기상자료가 없습니다.")
        hourly["time"] = pd.to_datetime(hourly["time"])
        tour = hourly[hourly["time"].dt.hour.between(9, 18)]
        return {
            "rain_mm": float(tour["precipitation"].fillna(0).sum()),
            "max_wind_ms": float(tour["wind_speed_10m"].fillna(0).max()),
            "max_gust_ms": float(tour["wind_gusts_10m"].fillna(0).max()),
            "avg_temp_c": float(tour["temperature_2m"].mean()),
            "status": "관측" if target < today else "예보",
            "source": "Open-Meteo",
        }

    def weather_for_day(day: str, port: str) -> dict:
        station_map = {"제주항": ["제주"], "강정항": ["서귀포"], "전체": ["제주", "서귀포"]}
        stations = station_map[port]
        placeholders = ",".join("?" for _ in stations)
        observed = query_df(
            f"""
            SELECT station, observed_at, temperature_c, precipitation_mm, wind_speed_ms
            FROM weather_hourly
            WHERE station IN ({placeholders})
              AND DATE(observed_at) = ?
              AND CAST(strftime('%H', observed_at) AS INTEGER) BETWEEN 9 AND 18
            """,
            tuple(stations) + (day,),
        )
        if not observed.empty:
            return {
                "rain_mm": float(observed["precipitation_mm"].fillna(0).sum()),
                "max_wind_ms": float(observed["wind_speed_ms"].fillna(0).max()),
                "max_gust_ms": None,
                "avg_temp_c": float(observed["temperature_c"].mean()),
                "status": "관측",
                "source": "제주·서귀포 ASOS CSV",
            }
        coordinates = {
            "제주항": [(33.516, 126.527)],
            "강정항": [(33.227, 126.475)],
            "전체": [(33.516, 126.527), (33.227, 126.475)],
        }
        try:
            results = [fetch_open_meteo(day, lat, lon) for lat, lon in coordinates[port]]
            return {
                "rain_mm": max(item["rain_mm"] for item in results),
                "max_wind_ms": max(item["max_wind_ms"] for item in results),
                "max_gust_ms": max(item["max_gust_ms"] for item in results),
                "avg_temp_c": sum(item["avg_temp_c"] for item in results) / len(results),
                "status": results[0]["status"],
                "source": "Open-Meteo API",
            }
        except Exception as exc:
            return {
                "rain_mm": None,
                "max_wind_ms": None,
                "max_gust_ms": None,
                "avg_temp_c": None,
                "status": "조회 불가",
                "source": f"API 응답 없음: {type(exc).__name__}",
            }

    def risk_for(weather: dict) -> dict:
        rain = weather["rain_mm"]
        wind = weather["max_wind_ms"]
        gust = weather["max_gust_ms"]
        if rain is None or wind is None:
            return {"level": "판정 대기", "tone": "gray", "reason": "기상자료 확인 필요", "score": None}
        high = RISK_RULES["high"]
        caution = RISK_RULES["caution"]
        if rain >= high["rain_mm"] or wind >= high["wind_ms"] or (gust is not None and gust >= high["gust_ms"]):
            return {"level": "높음", "tone": "red", "reason": "해양·야외상품 중단 검토", "score": 3}
        if rain >= caution["rain_mm"] or wind >= caution["wind_ms"] or (gust is not None and gust >= caution["gust_ms"]):
            return {"level": "주의", "tone": "amber", "reason": "조건부 운영 및 대체상품 준비", "score": 2}
        return {"level": "낮음", "tone": "green", "reason": "기본상품 운영 가능", "score": 1}

    return (
        DB_PATH,
        DATA_DIR,
        ANALYSIS_DIR,
        date,
        datetime,
        footer,
        folium,
        fmt_int,
        go,
        metric_card,
        mo,
        pd,
        px,
        query_df,
        risk_for,
        status_badge,
        weather_for_day,
    )


@app.cell
def __(mo):
    mo.Html(
        """
        <style>
        :root {
          --navy:#13243a; --ink:#172234; --muted:#65758b; --line:#dce3eb;
          --paper:#f5f7fa; --blue:#1677c8; --cyan:#16a6a1; --amber:#d88918;
          --red:#c7474b; --green:#208a64;
        }
        body { background:var(--paper); color:var(--ink); }
        main { max-width:1500px !important; padding:20px 28px 48px !important; }
        h1,h2,h3,p { letter-spacing:0 !important; }
        .hero { background:var(--navy); color:white; padding:22px 26px; border-radius:6px; margin-bottom:16px; }
        .hero h1 { font-size:24px; margin:0 0 6px; }
        .hero p { color:#c7d5e7; margin:0; font-size:14px; }
        .section-head { margin:18px 0 10px; }
        .section-head h2 { font-size:19px; margin:0 0 4px; }
        .section-head p { color:var(--muted); margin:0; font-size:13px; }
        .metric-card { background:white; border:1px solid var(--line); border-top:3px solid var(--blue); border-radius:6px; padding:14px 16px; min-height:112px; }
        .metric-card.green { border-top-color:var(--green); }
        .metric-card.amber { border-top-color:var(--amber); }
        .metric-card.red { border-top-color:var(--red); }
        .metric-card.gray { border-top-color:#8b98a8; }
        .metric-label { color:var(--muted); font-size:12px; font-weight:700; }
        .metric-value { color:var(--ink); font-size:25px; font-weight:800; margin:8px 0 5px; }
        .metric-caption { color:var(--muted); font-size:12px; line-height:1.4; }
        .notice { background:#edf5fb; border-left:4px solid var(--blue); padding:12px 14px; margin:12px 0; font-size:13px; }
        .notice.warning { background:#fff6e8; border-left-color:var(--amber); }
        .notice.danger { background:#fff0f0; border-left-color:var(--red); }
        .badge { display:inline-block; padding:3px 7px; border-radius:4px; font-size:11px; font-weight:700; }
        .badge.info { color:#0e5e9a; background:#e5f2fb; }
        .badge.green { color:#146849; background:#e3f5ed; }
        .badge.amber { color:#8a5305; background:#fff0d4; }
        .badge.red { color:#9d272c; background:#fde4e5; }
        .badge.gray { color:#586676; background:#edf0f3; }
        .decision { background:white; border:1px solid var(--line); border-radius:6px; padding:16px; }
        .decision h3 { font-size:16px; margin:0 0 8px; }
        .decision p { color:var(--muted); font-size:13px; margin:5px 0; }
        .page-footer { border-top:1px solid var(--line); color:#77869a; font-size:10px; margin-top:24px; padding-top:10px; display:flex; flex-wrap:wrap; gap:18px; }
        .page-footer b { color:#59687b; margin-right:4px; }
        .marimo-tabs { border-radius:6px !important; }
        @media (max-width:700px) { main { padding:12px !important; } .hero h1 { font-size:20px; } }
        </style>
        """
    )
    return


@app.cell
def __(ANALYSIS_DIR, DATA_DIR, DB_PATH, date, mo, pd, query_df):
    if not DB_PATH.exists():
        raise FileNotFoundError("SQLite DB가 없습니다. python scripts/build_db.py를 먼저 실행하세요.")
    cruise = query_df("SELECT * FROM cruise_calls")
    products = query_df("SELECT * FROM tour_products")
    sources = query_df("SELECT * FROM data_sources")
    logs = query_df("SELECT * FROM update_logs ORDER BY executed_at DESC")
    attractions = pd.read_csv(DATA_DIR / "attractions.csv", encoding="utf-8-sig")
    survey_dir = ANALYSIS_DIR / "cruise_passenger"
    nationality = pd.read_csv(survey_dir / "국적_구성.csv", encoding="utf-8-sig")
    activities = pd.read_csv(survey_dir / "관광활동.csv", encoding="utf-8-sig")
    shopping = pd.read_csv(survey_dir / "쇼핑품목.csv", encoding="utf-8-sig")
    pain_points = pd.read_csv(survey_dir / "불편사항.csv", encoding="utf-8-sig")
    cruise_as_of = cruise["arrival_date"].max()
    weather_as_of = sources.loc[sources["table_name"] == "weather_hourly", "data_as_of"].iloc[0]
    selected_date = mo.ui.date(
        value=date.today(),
        start=date.fromisoformat(cruise["arrival_date"].min()),
        stop=date.today().replace(year=date.today().year + 1),
        label="",
        full_width=True,
    )
    selected_port = mo.ui.dropdown(
        options=["전체", "제주항", "강정항"], value="전체", label="", full_width=True
    )
    return (
        cruise,
        cruise_as_of,
        logs,
        products,
        selected_date,
        selected_port,
        sources,
        weather_as_of,
        activities,
        attractions,
        nationality,
        pain_points,
        shopping,
    )


@app.cell
def __(
    activities,
    attractions,
    cruise,
    cruise_as_of,
    pd,
    products,
    risk_for,
    selected_date,
    selected_port,
    weather_for_day,
):
    day = selected_date.value.isoformat()
    port = selected_port.value
    day_calls = cruise[cruise["arrival_date"] == day].copy()
    if port != "전체":
        day_calls = day_calls[(day_calls["port"] == port) | (day_calls["port"] == "전체 항구")]
    published = day <= cruise_as_of
    passenger_records = day_calls[day_calls["total_passengers"] > 0]
    total_passengers = int(passenger_records["total_passengers"].sum())
    detailed_calls = day_calls[day_calls["record_status"] != "aggregate"]
    weather = weather_for_day(day, port)
    risk = risk_for(weather)

    if risk["score"] == 3:
        matched_products = products[products["available_in_bad_weather"] == 1].copy()
        sales_action = "야외·해양상품 판매를 멈추고 실내 대체상품으로 즉시 전환"
    elif risk["score"] == 2:
        matched_products = products[products["environment"] == "indoor"].copy()
        sales_action = "해양상품은 조건부 판매하고 실내 대체상품을 함께 제안"
    elif risk["score"] == 1:
        matched_products = products.copy()
        sales_action = "해양·야외상품 우선 판매, 실내상품은 선택형으로 제안"
    else:
        matched_products = products[products["environment"] == "indoor"].copy()
        sales_action = "기상자료 확인 전까지 취소 위험이 낮은 실내상품 중심으로 안내"

    passenger_state = (
        "실적 확인"
        if not passenger_records.empty
        else "입항 실적 없음"
        if published
        else "자료 미공개"
    )
    return (
        day,
        day_calls,
        detailed_calls,
        matched_products,
        passenger_state,
        port,
        published,
        risk,
        sales_action,
        total_passengers,
        weather,
    )


@app.cell
def __(
    cruise,
    cruise_as_of,
    day,
    day_calls,
    detailed_calls,
    footer,
    folium,
    fmt_int,
    go,
    logs,
    matched_products,
    metric_card,
    mo,
    passenger_state,
    pain_points,
    pd,
    port,
    published,
    px,
    query_df,
    risk,
    sales_action,
    selected_date,
    selected_port,
    sources,
    status_badge,
    nationality,
    shopping,
    total_passengers,
    weather,
    weather_as_of,
):
    hero = mo.Html(
        """
        <div style="background:#172033;color:white;padding:22px 26px;border:1px solid #334155;border-radius:6px;margin-bottom:16px">
          <h1 style="font-size:24px;margin:0 0 6px;letter-spacing:0;color:#38bdf8">제주 크루즈 날씨 기반 인도어 관광 대시보드</h1>
          <p style="color:#c7d5e7;margin:0;font-size:14px">입항 실적과 시간대별 비·바람을 결합해 영업 대응과 대체 관광상품을 제안합니다.</p>
        </div>
        """
    )
    date_control = mo.vstack(
        [mo.Html('<div style="color:#e2e8f0;font-size:12px;font-weight:700">조회 날짜</div>'), selected_date.style({"color": "#172234"})],
        gap=0.25,
    )
    port_control = mo.vstack(
        [mo.Html('<div style="color:#e2e8f0;font-size:12px;font-weight:700">항구</div>'), selected_port.style({"color": "#172234"})],
        gap=0.25,
    )
    filters = mo.hstack([date_control, port_control], widths="equal", gap=1)

    weather_label = weather["status"]
    rain_text = "-" if weather["rain_mm"] is None else f'{weather["rain_mm"]:.1f} mm'
    wind_text = "-" if weather["max_wind_ms"] is None else f'{weather["max_wind_ms"]:.1f} m/s'
    gust_text = "돌풍 자료 없음" if weather["max_gust_ms"] is None else f'돌풍 {weather["max_gust_ms"]:.1f} m/s'
    passenger_caption = (
        f"{len(detailed_calls)}척 · {passenger_state}"
        if published
        else f"승객 실적 기준일 {cruise_as_of}"
    )
    passenger_value = f"{fmt_int(total_passengers)}명" if total_passengers else passenger_state

    kpis = mo.hstack(
        [
            metric_card("입항 승객", passenger_value, passenger_caption, "blue"),
            metric_card("관광시간 강수", rain_text, f"{weather_label} · 09~18시", "blue"),
            metric_card("최대 풍속", wind_text, gust_text, "amber" if risk["score"] in (2, 3) else "green"),
            metric_card("운영 위험", risk["level"], risk["reason"], risk["tone"]),
        ],
        widths="equal",
        gap=1,
    )

    if not published:
        data_notice = mo.Html(
            f'<div style="background:#28271f;color:#f8fafc;border-left:4px solid #f59e0b;padding:12px 14px;margin:12px 0;font-size:13px"><b>{day}</b>은 승객 실적 기준일({cruise_as_of}) 이후입니다. '
            "0명이 아니라 <b>아직 공개 자료로 확인할 수 없는 상태</b>입니다.</div>"
        )
    elif day_calls.empty:
        data_notice = mo.Html(
            f'<div style="background:#172b3b;color:#f8fafc;border-left:4px solid #38bdf8;padding:12px 14px;margin:12px 0;font-size:13px"><b>{day}</b>은 현재 SQLite 일별자료에서 입항 실적이 확인되지 않습니다.</div>'
        )
    else:
        data_notice = mo.Html(
            f'<div style="background:#172b3b;color:#f8fafc;border-left:4px solid #38bdf8;padding:12px 14px;margin:12px 0;font-size:13px"><b>{day} · {port}</b> 조회 결과입니다. '
            f'{status_badge(passenger_state, "green")} {status_badge(weather_label, "info")}</div>'
        )

    call_view = day_calls[
        ["arrival_date", "ship_name", "port", "total_passengers", "record_status", "source_note"]
    ].rename(
        columns={
            "arrival_date": "입항일",
            "ship_name": "선박",
            "port": "항구",
            "total_passengers": "승객 수",
            "record_status": "자료 상태",
            "source_note": "비고",
        }
    )
    call_table = mo.ui.table(call_view, selection=None, pagination=True, page_size=8) if not call_view.empty else mo.md("조회된 입항 자료가 없습니다.")

    recommendations = matched_products[["product_name", "category", "environment", "scenario", "description"]].rename(
        columns={"product_name": "추천상품", "category": "유형", "environment": "환경", "scenario": "적용상황", "description": "판매 포인트"}
    )
    recommendation_table = mo.ui.table(recommendations, selection=None, pagination=False)

    home_page = mo.vstack(
        [
            hero,
            filters,
            data_notice,
            kpis,
            mo.Html('<div class="section-head"><h2>오늘의 영업 대응</h2><p>비와 바람을 함께 고려한 1차 운영 판단입니다.</p></div>'),
            mo.Html(f'<div style="background:#1e293b;color:#f8fafc;border:1px solid #334155;border-radius:6px;padding:16px"><h3 style="font-size:16px;margin:0 0 8px;color:#38bdf8">{risk["level"]} 위험 · {sales_action}</h3><p style="color:#cbd5e1;font-size:13px;margin:5px 0">{risk["reason"]}</p><p style="color:#94a3b8;font-size:13px;margin:5px 0">기상 출처: {weather["source"]}</p></div>'),
            mo.Html('<div class="section-head"><h2>입항 세부</h2><p>예정·실적·합계 자료 상태를 구분합니다.</p></div>'),
            call_table,
            footer("marimo · SQLite · pandas", "크루즈 일별자료 · ASOS · Open-Meteo", f"승객 {cruise_as_of} · 기상 {weather_label}"),
        ],
        gap=1,
    )

    cruise_eda = cruise[cruise["total_passengers"] > 0].copy()
    cruise_eda["month"] = cruise_eda["arrival_date"].str[:7]
    monthly = cruise_eda.groupby("month", as_index=False).agg(
        입항건수=("ship_name", "size"), 승객수=("total_passengers", "sum")
    )
    port_summary = cruise_eda.groupby("port", as_index=False).agg(
        입항건수=("ship_name", "size"), 승객수=("total_passengers", "sum")
    )
    fig_month = px.line(monthly, x="month", y="승객수", markers=True, title="월별 확인 승객 수")
    fig_month.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0")
    fig_port = px.bar(port_summary, x="port", y="승객수", color="port", title="항구별 확인 승객 수")
    fig_port.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0")
    eda_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>데이터·EDA</h2><p>상품 의사결정에 필요한 입항 규모와 자료 범위를 먼저 확인합니다.</p></div>'),
            mo.hstack(
                [
                    metric_card("크루즈 레코드", f"{len(cruise):,}건", f"{cruise['arrival_date'].min()} ~ {cruise_as_of}"),
                    metric_card("확인 승객", f"{cruise_eda['total_passengers'].sum():,.0f}명", "0명·미공개 기록 제외"),
                    metric_card("데이터 소스", f"{len(sources)}종", "SQLite 통합 관리"),
                ], widths="equal", gap=1
            ),
            mo.hstack([fig_month, fig_port], widths="equal", gap=1),
            mo.Html('<div class="section-head"><h2>데이터 카탈로그</h2><p>기준일과 갱신 주기를 함께 관리합니다.</p></div>'),
            mo.ui.table(sources.rename(columns={"table_name":"테이블", "source_name":"자료", "source_location":"위치", "data_as_of":"기준일", "update_cycle":"갱신주기"}), selection=None, pagination=False),
            footer("marimo · SQLite · pandas · Plotly", "크루즈 일별자료 · ASOS", f"DB 승객 기준 {cruise_as_of}"),
        ], gap=1
    )

    # Survey EDA turns the existing cruise-passenger analysis into product evidence.
    fig_activity = px.bar(
        activities.head(8).sort_values("percent"), x="percent", y="category",
        orientation="h", title="크루즈 승객 주요 관광활동 (%)",
        color="percent", color_continuous_scale=["#38bdf8", "#10b981"],
    )
    fig_activity.update_layout(height=390, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0", coloraxis_showscale=False)
    fig_nationality = px.pie(
        nationality.head(7), names="category", values="percent", hole=0.55,
        title="크루즈 승객 국적 구성",
        color_discrete_sequence=["#38bdf8", "#10b981", "#f59e0b", "#f43f5e", "#a78bfa", "#22d3ee", "#94a3b8"],
    )
    fig_nationality.update_layout(height=390, paper_bgcolor="#1e293b", font_color="#e2e8f0", legend_orientation="h")
    fig_shopping = px.bar(
        shopping.head(7).sort_values("percent"), x="percent", y="category",
        orientation="h", title="주요 쇼핑 품목 (%)", color_discrete_sequence=["#f59e0b"],
    )
    fig_shopping.update_layout(height=360, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0")
    survey_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>크루즈 승객 EDA</h2><p>2025 제주 방문관광객 실태조사 중 크루즈 응답자를 분석한 결과입니다.</p></div>'),
            mo.hstack([
                metric_card("분석 표본", "1,014명", "크루즈 응답자 · 가중치 적용"),
                metric_card("실제 관광시간", "5.11시간", "정박시간이 아닌 응답 기준"),
                metric_card("강정항 이용", "81.3%", "표본 내 항구 구성"),
                metric_card("중국 국적", "78.0%", "선박별 국적 자료 아님", "amber"),
            ], widths="equal", gap=1),
            mo.hstack([fig_activity, fig_nationality], widths="equal", gap=1),
            fig_shopping,
            mo.Html('<div style="background:#1e293b;border:1px solid #334155;padding:16px;border-radius:6px"><b style="color:#38bdf8">상품 시사점</b><p style="color:#cbd5e1">자연경관 87.0%, 쇼핑 82.3%, 식도락 69.2%가 핵심 수요입니다. 악천후 상품도 경관 경험을 완전히 버리기보다 미디어아트·전망형 실내시설에 쇼핑과 로컬 F&B를 결합해야 합니다.</p></div>'),
            footer("SQLite · pandas · Plotly", "2025 제주 방문관광객 실태조사 크루즈 표본", "표본 1,014명"),
        ], gap=1
    )

    # Join cruise calls to port-nearest hourly observations during touring hours.
    daily_weather = query_df(
        """
        SELECT station, DATE(observed_at) AS arrival_date,
               SUM(COALESCE(precipitation_mm, 0)) AS rain_mm,
               MAX(COALESCE(wind_speed_ms, 0)) AS max_wind_ms,
               AVG(temperature_c) AS avg_temp_c
        FROM weather_hourly
        WHERE CAST(strftime('%H', observed_at) AS INTEGER) BETWEEN 9 AND 18
        GROUP BY station, DATE(observed_at)
        """
    )
    fusion = cruise_eda.copy()
    fusion["station"] = fusion["port"].map({"제주항": "제주", "강정항": "서귀포"})
    fusion = fusion.merge(daily_weather, on=["station", "arrival_date"], how="inner")
    fusion["risk_level"] = "낮음"
    fusion.loc[(fusion["rain_mm"] >= 1) | (fusion["max_wind_ms"] >= 8), "risk_level"] = "주의"
    fusion.loc[(fusion["rain_mm"] >= 5) | (fusion["max_wind_ms"] >= 10), "risk_level"] = "높음"
    risk_order = ["낮음", "주의", "높음"]
    risk_summary = fusion.groupby("risk_level", as_index=False).agg(
        입항건수=("ship_name", "size"), 노출승객=("total_passengers", "sum")
    )
    risk_summary["risk_level"] = pd.Categorical(risk_summary["risk_level"], risk_order, ordered=True)
    risk_summary = risk_summary.sort_values("risk_level")
    fig_risk = px.bar(
        risk_summary, x="risk_level", y="노출승객", color="risk_level",
        title="관광시간대 기상 위험별 크루즈 승객",
        color_discrete_map={"낮음":"#10b981", "주의":"#f59e0b", "높음":"#f43f5e"},
    )
    fig_risk.update_layout(height=370, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0", showlegend=False)
    port_risk = fusion.groupby(["port", "risk_level"], as_index=False)["total_passengers"].sum()
    fig_port_risk = px.bar(
        port_risk, x="port", y="total_passengers", color="risk_level", barmode="stack",
        title="항구별 기상 위험 노출 승객",
        color_discrete_map={"낮음":"#10b981", "주의":"#f59e0b", "높음":"#f43f5e"},
    )
    fig_port_risk.update_layout(height=370, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font_color="#e2e8f0")
    exposed = fusion[fusion["risk_level"].isin(["주의", "높음"])]["total_passengers"].sum()
    fusion_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>융합분석</h2><p>입항일·항구와 09~18시 관측 기상을 결합해 상품 전환 필요 규모를 계산합니다.</p></div>'),
            mo.hstack([
                metric_card("결합 입항", f"{len(fusion):,}건", "크루즈 × 항구 인근 관측소"),
                metric_card("악천후 노출 승객", f"{exposed:,.0f}명", "주의·높음 시나리오", "amber"),
                metric_card("실내 전환 기준", "비 1mm / 바람 8m/s", "프로젝트 운영 시나리오"),
            ], widths="equal", gap=1),
            mo.hstack([fig_risk, fig_port_risk], widths="equal", gap=1),
            mo.Html('<div style="background:#1e293b;border:1px solid #334155;padding:16px;border-radius:6px"><b style="color:#38bdf8">해석</b><p style="color:#cbd5e1">크루즈의 실제 관광시간은 평균 5.11시간으로 짧습니다. 같은 날짜라도 항구 인근 기상과 체류시간에 따라 해양상품을 실내상품으로 전환할 대상 규모가 달라집니다.</p></div>'),
            footer("SQLite JOIN · pandas · Plotly", "크루즈 입항실적 · 제주/서귀포 ASOS", f"기상 DB {weather_as_of[:10]}"),
        ], gap=1
    )

    decision_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>영업 의사결정</h2><p>날짜와 항구를 선택해 운영 가능성과 대체상품을 확인합니다.</p></div>'),
            filters,
            data_notice,
            kpis,
            mo.Html(f'<div style="background:#1e293b;color:#f8fafc;border:1px solid #334155;border-radius:6px;padding:16px"><h3 style="font-size:16px;margin:0 0 8px;color:#38bdf8">권장 조치</h3><p style="color:#e2e8f0;font-size:13px;margin:5px 0"><b>{sales_action}</b></p><p style="color:#94a3b8;font-size:13px;margin:5px 0">강수 {rain_text} · 풍속 {wind_text} · {gust_text}</p></div>'),
            mo.Html('<div class="section-head"><h2>추천 상품</h2><p>현재는 설명 가능한 규칙 기반 1차 매칭입니다.</p></div>'),
            recommendation_table,
            footer("marimo · SQLite · Python 규칙 엔진", "입항 실적 · 시간별 기상 · 팀 상품 시나리오", f"선택일 {day}"),
        ], gap=1
    )

    product_rows = matched_products.head(3).to_dict("records")
    sales_cards = []
    customer_cards = []
    for idx, item in enumerate(product_rows, start=1):
        accent = ["#38bdf8", "#10b981", "#f59e0b"][idx - 1]
        sales_cards.append(
            mo.Html(
                f'<div style="background:#1e293b;border:1px solid #334155;border-top:3px solid {accent};padding:16px;border-radius:6px;min-height:190px">'
                f'<div style="color:{accent};font-size:11px;font-weight:800">추천 {idx} · {item["scenario"]}</div>'
                f'<h3 style="font-size:17px;color:#f8fafc;margin:8px 0">{item["product_name"]}</h3>'
                f'<p style="color:#cbd5e1;font-size:13px">{item["description"]}</p>'
                f'<p style="color:#94a3b8;font-size:12px">유형 {item["category"]} · 운영환경 {item["environment"]}</p></div>'
            )
        )
        customer_cards.append(
            mo.Html(
                f'<div style="background:#f8fafc;color:#172234;border-left:4px solid {accent};padding:18px;border-radius:6px;min-height:190px">'
                f'<div style="color:#526276;font-size:11px;font-weight:800">WEATHER-FIT COURSE {idx}</div>'
                f'<h3 style="font-size:18px;margin:8px 0;color:#172234">{item["product_name"]}</h3>'
                f'<p style="font-size:13px;color:#526276">{item["description"]}</p>'
                f'<p style="font-size:12px;color:#1677c8"><b>{risk["level"]} 위험에 맞춘 추천</b></p></div>'
            )
        )
    sales_view = mo.vstack(
        [
            mo.Html(f'<div style="background:#172b3b;border-left:4px solid #38bdf8;padding:14px"><b>{day} · {port}</b><br><span style="color:#cbd5e1">{sales_action}</span></div>'),
            mo.hstack(sales_cards, widths="equal", gap=1),
            mo.Html('<div style="background:#28271f;border-left:4px solid #f59e0b;padding:14px;color:#e2e8f0"><b>영업 사용 원칙</b><br>실제 가격·정원·취소조건은 제휴사 확인 후 확정합니다. 현재 추천은 수업 프로젝트의 기상 시나리오입니다.</div>'),
        ], gap=1
    )
    customer_view = mo.vstack(
        [
            mo.Html(f'<div style="background:#f8fafc;color:#172234;padding:18px;border-radius:6px"><h2 style="margin:0 0 6px">{day} 제주 추천 여행</h2><p style="margin:0;color:#526276">날씨와 크루즈 체류시간을 고려해 이동 부담이 낮은 코스를 골랐습니다.</p></div>'),
            mo.hstack(customer_cards, widths="equal", gap=1),
            mo.Html('<div style="background:#f8fafc;color:#526276;padding:14px;border-radius:6px;font-size:12px">기상과 현장 운영 상황에 따라 방문 순서 또는 장소가 변경될 수 있습니다. 출항 시간 전 항구 복귀를 우선합니다.</div>'),
        ], gap=1
    )
    product_tabs = mo.ui.tabs({"영업직원용": sales_view, "고객·관광객용": customer_view})
    product_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>관광상품 제안</h2><p>같은 분석 결과를 영업직원과 관광객에게 맞는 언어로 나누어 제공합니다.</p></div>'),
            filters,
            product_tabs,
            footer("marimo · 규칙 기반 추천", "승객 EDA · 기상 위험 · 상품 시나리오", f"선택일 {day}"),
        ], gap=1
    )

    zone_attractions = attractions[attractions["port_zone"] == (port if port != "전체" else "강정항")].copy()
    if risk["score"] in (2, 3) or risk["score"] is None:
        zone_attractions = zone_attractions[zone_attractions["environment"].isin(["indoor", "mixed"])]
    origin_name = port if port != "전체" else "강정항"
    origin = attractions[attractions["name"] == origin_name].iloc[0]
    jeju_map = folium.Map(location=[33.37, 126.55], zoom_start=10, tiles="OpenStreetMap")
    color_map = {"indoor": "blue", "outdoor": "green", "mixed": "orange", "port": "red"}
    for _, place in attractions.iterrows():
        folium.Marker(
            [place["latitude"], place["longitude"]],
            tooltip=place["name"],
            popup=f'<b>{place["name"]}</b><br>{place["category"]}<br>{place["scenario_note"]}',
            icon=folium.Icon(color=color_map.get(place["environment"], "gray"), icon="info-sign"),
        ).add_to(jeju_map)
    route_points = [[origin["latitude"], origin["longitude"]]]
    route_points += zone_attractions.head(3)[["latitude", "longitude"]].values.tolist()
    route_points += [[origin["latitude"], origin["longitude"]]]
    if len(route_points) > 2:
        folium.PolyLine(route_points, color="#1677c8", weight=4, opacity=0.8, tooltip="추천 시나리오 동선").add_to(jeju_map)
    map_html = mo.iframe(jeju_map.get_root().render(), height="600px").style({"background": "white", "border-radius": "6px", "overflow": "hidden"})
    map_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>지도·동선 탐색</h2><p>항구와 실내·혼합형 관광자원을 비교하고 추천 시나리오 동선을 확인합니다.</p></div>'),
            filters,
            map_html,
            mo.ui.table(zone_attractions[["name", "category", "environment", "duration_hours", "scenario_note"]].rename(columns={"name":"관광지", "category":"유형", "environment":"환경", "duration_hours":"권장 체류시간", "scenario_note":"활용 시나리오"}), selection=None, pagination=False),
            footer("Folium · SQLite · marimo", "관광지 후보 좌표 · 프로젝트 상품 시나리오", "실제 이동시간·영업시간 별도 확인 필요"),
        ], gap=1
    )

    limitations = pd.DataFrame(
        [
            ("승객 수", "기준일 이후 0명 표시 금지", "자료 미공개로 표시"),
            ("날씨", "과거 관측과 미래 예보의 성격이 다름", "관측/예보 상태 표시"),
            ("돌풍", "ASOS CSV에 순간풍속 컬럼 없음", "API 제공 시에만 표시"),
            ("추천", "운영사별 실제 취소기준 미확보", "프로젝트 시나리오 기준으로 명시"),
            ("매출", "크루즈 직접 매출자료 미확보", "실제 매출이 아닌 시나리오로 제한"),
        ], columns=["항목", "한계", "표시 원칙"]
    )
    validation_page = mo.vstack(
        [
            mo.Html('<div class="section-head"><h2>데이터 관리·검증</h2><p>최신성, 자동화 상태, 분석 한계를 투명하게 공개합니다.</p></div>'),
            mo.hstack(
                [
                    metric_card("승객 데이터 기준", cruise_as_of, "이후 날짜는 미공개"),
                    metric_card("기상 DB 기준", weather_as_of[:10], "이후 API 조회"),
                    metric_card("최근 DB 빌드", logs.iloc[0]["executed_at"][:19], logs.iloc[0]["status"], "green"),
                ], widths="equal", gap=1
            ),
            mo.Html('<div class="section-head"><h2>분석 한계와 표시 원칙</h2></div>'),
            mo.ui.table(limitations, selection=None, pagination=False),
            mo.Html('<div class="section-head"><h2>최근 업데이트 로그</h2></div>'),
            mo.ui.table(logs.rename(columns={"executed_at":"실행시각", "job_name":"작업", "processed_rows":"처리건수", "status":"상태", "message":"메시지"}), selection=None, pagination=False),
            footer("marimo · SQLite", "data_sources · update_logs", "MVP 수동 빌드"),
        ], gap=1
    )

    page_style = {
        "background": "#0f172a",
        "color": "#f8fafc",
        "padding": "18px",
        "border": "1px solid #334155",
        "border-radius": "6px",
        "min-height": "760px",
    }
    home_page = home_page.style(page_style)
    eda_page = eda_page.style(page_style)
    survey_page = survey_page.style(page_style)
    fusion_page = fusion_page.style(page_style)
    decision_page = decision_page.style(page_style)
    product_page = product_page.style(page_style)
    map_page = map_page.style(page_style)
    validation_page = validation_page.style(page_style)

    navigation = mo.ui.tabs(
        {
            "홈": home_page,
            "데이터 EDA": eda_page,
            "승객 분석": survey_page,
            "융합 분석": fusion_page,
            "영업 판단": decision_page,
            "상품 제안": product_page,
            "지도 동선": map_page,
            "관리 검증": validation_page,
        },
        orientation="vertical",
    )
    mo.vstack([navigation], gap=1).style({"background": "#0b1220", "padding": "10px", "border-radius": "6px"})
    return


if __name__ == "__main__":
    app.run()
