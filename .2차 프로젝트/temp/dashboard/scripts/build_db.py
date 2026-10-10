from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


APP_DIR = Path(__file__).resolve().parents[1]
DB_PATH = APP_DIR / "data" / "cruise_dashboard.db"
CRUISE_CSV = APP_DIR / "data" / "raw" / "제주_크루즈 입도객(일별)240101-260914.csv"
WEATHER_CSV = APP_DIR / "data" / "raw" / "제주_서귀포_시간별기상_2024_2026.csv"
MANUAL_CSV = APP_DIR / "data" / "manual_cruise_updates.csv"


def load_cruise() -> pd.DataFrame:
    source = pd.read_csv(CRUISE_CSV, encoding="utf-8-sig")
    cruise = pd.DataFrame(
        {
            "arrival_date": pd.to_datetime(
                source["입항일자(YYYYMMDD)"].astype(str), format="%Y%m%d"
            ).dt.strftime("%Y-%m-%d"),
            "ship_name": source["선박명"].astype(str).str.strip(),
            "port": source["입항항구"].astype(str).str.strip(),
            "total_passengers": pd.to_numeric(source["총승객수"], errors="coerce").fillna(0).astype(int),
            "chinese_passengers": pd.to_numeric(source["중국인승객수"], errors="coerce").fillna(0).astype(int),
            "japanese_passengers": pd.to_numeric(source["일본인승객수"], errors="coerce").fillna(0).astype(int),
            "western_passengers": (
                pd.to_numeric(source["미국인승객수"], errors="coerce").fillna(0)
                + pd.to_numeric(source["유럽인승객수"], errors="coerce").fillna(0)
                + pd.to_numeric(source["미주인승객수"], errors="coerce").fillna(0)
                + pd.to_numeric(source["오세아니아인승객수"], errors="coerce").fillna(0)
            ).astype(int),
            "record_status": "actual",
            "source_note": "제주 크루즈 입도객 일별 원본",
        }
    )
    manual = pd.read_csv(MANUAL_CSV, encoding="utf-8-sig")
    combined = pd.concat([cruise, manual], ignore_index=True)
    return combined.drop_duplicates(
        subset=["arrival_date", "ship_name", "port"], keep="last"
    ).sort_values(["arrival_date", "port", "ship_name"])


def load_weather() -> pd.DataFrame:
    source = pd.read_csv(WEATHER_CSV, encoding="utf-8-sig", low_memory=False)
    weather = pd.DataFrame(
        {
            "station": source["지점명"].astype(str),
            "observed_at": pd.to_datetime(source["일시"], errors="coerce"),
            "temperature_c": pd.to_numeric(source["기온(°C)"], errors="coerce"),
            "precipitation_mm": pd.to_numeric(source["강수량(mm)"], errors="coerce").fillna(0),
            "wind_speed_ms": pd.to_numeric(source["풍속(m/s)"], errors="coerce"),
            "wind_direction": pd.to_numeric(source["풍향(16방위)"], errors="coerce"),
            "humidity_pct": pd.to_numeric(source["습도(%)"], errors="coerce"),
        }
    ).dropna(subset=["observed_at"])
    weather["observed_at"] = weather["observed_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    weather["data_status"] = "observed"
    return weather


def seed_products() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("해안 절경·요트 투어", "해양", "outdoor", 6, 8, 1, "맑음·약풍", "제주 해안과 요트를 결합한 프리미엄 코스"),
            ("서귀포 미디어아트·아쿠아리움", "문화", "indoor", 0, 99, 1, "비·강풍", "강정항 중심의 전천후 실내 코스"),
            ("제주 로컬 미식·면세 쇼핑", "쇼핑·미식", "indoor", 0, 99, 1, "비·강풍", "제주항 중심의 쇼핑과 미식 코스"),
            ("K-뷰티 스파·티 클래스", "체험", "indoor", 0, 99, 1, "비·강풍", "소규모 고부가가치 실내 체험"),
            ("오름·해안 트레킹", "자연", "outdoor", 3, 8, 0, "맑음·약풍", "활동형 고객을 위한 자연 코스"),
        ],
        columns=[
            "product_name", "category", "environment", "max_rain_mm",
            "max_wind_ms", "available_in_bad_weather", "scenario", "description",
        ],
    )


def build_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cruise = load_cruise()
    weather = load_weather()
    products = seed_products()
    built_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    sources = pd.DataFrame(
        [
            ("cruise_calls", "제주 크루즈 입도객(일별)", str(CRUISE_CSV.name), cruise["arrival_date"].max(), "주 1회"),
            ("weather_hourly", "제주·서귀포 ASOS 시간별 기상", str(WEATHER_CSV.name), weather["observed_at"].max(), "수동 원본 + API"),
            ("tour_products", "프로젝트 상품 시나리오", "팀 정의", built_at[:10], "수시"),
        ],
        columns=["table_name", "source_name", "source_location", "data_as_of", "update_cycle"],
    )
    logs = pd.DataFrame(
        [(built_at, "build_database", len(cruise) + len(weather), "success", "초기 SQLite 생성")],
        columns=["executed_at", "job_name", "processed_rows", "status", "message"],
    )

    with sqlite3.connect(DB_PATH) as conn:
        cruise.to_sql("cruise_calls", conn, if_exists="replace", index=False)
        weather.to_sql("weather_hourly", conn, if_exists="replace", index=False)
        products.to_sql("tour_products", conn, if_exists="replace", index=False)
        sources.to_sql("data_sources", conn, if_exists="replace", index=False)
        logs.to_sql("update_logs", conn, if_exists="replace", index=False)
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_cruise_date_port
                ON cruise_calls(arrival_date, port);
            CREATE INDEX IF NOT EXISTS idx_weather_station_time
                ON weather_hourly(station, observed_at);
            """
        )
    print(f"Built {DB_PATH}")
    print(f"cruise_calls={len(cruise):,}, weather_hourly={len(weather):,}")


if __name__ == "__main__":
    build_database()
