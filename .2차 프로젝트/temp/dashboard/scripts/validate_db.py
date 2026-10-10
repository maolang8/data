from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "cruise_dashboard.db"
REQUIRED_TABLES = {
    "cruise_calls",
    "weather_hourly",
    "tour_products",
    "data_sources",
    "update_logs",
}


def scalar(conn: sqlite3.Connection, sql: str):
    return conn.execute(sql).fetchone()[0]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Missing database: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = REQUIRED_TABLES - tables
        if missing:
            raise SystemExit(f"Missing tables: {sorted(missing)}")
        checks = {
            "cruise_rows": scalar(conn, "SELECT COUNT(*) FROM cruise_calls"),
            "weather_rows": scalar(conn, "SELECT COUNT(*) FROM weather_hourly"),
            "negative_passengers": scalar(conn, "SELECT COUNT(*) FROM cruise_calls WHERE total_passengers < 0"),
            "duplicate_calls": scalar(
                conn,
                """SELECT COUNT(*) FROM (
                       SELECT arrival_date, ship_name, port, COUNT(*) n
                       FROM cruise_calls GROUP BY 1,2,3 HAVING n > 1
                   )""",
            ),
        }
    if checks["cruise_rows"] == 0 or checks["weather_rows"] == 0:
        raise SystemExit(f"Empty core table: {checks}")
    if checks["negative_passengers"] or checks["duplicate_calls"]:
        raise SystemExit(f"Data quality failure: {checks}")
    print(f"Data quality checks passed: {checks}")


if __name__ == "__main__":
    main()
