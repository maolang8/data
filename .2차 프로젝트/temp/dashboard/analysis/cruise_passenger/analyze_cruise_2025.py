from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "2025 제주특별자치도 방문관광객 실태조사_분석편"
OUTPUT_DIR = ROOT / "크루즈_승객_분석_결과"
OUTPUT_DIR.mkdir(exist_ok=True)


def find_source() -> Path:
    matches = list(SOURCE_DIR.glob("*크루즈_DATA.xlsx"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one cruise data file, found {len(matches)}")
    return matches[0]


def load_data():
    source = find_source()
    data = pd.read_excel(source, sheet_name="데이터")
    labels = pd.read_excel(source, sheet_name="값라벨")
    label_map = {}
    for variable, group in labels.groupby("변수명", sort=False):
        label_map[str(variable)] = {
            row["값"]: str(row["값 라벨"])
            .replace("① ", "")
            .replace("② ", "")
            .replace("③ ", "")
            .replace("④ ", "")
            .replace("⑤ ", "")
            .replace("ⓞ ", "")
            for _, row in group.iterrows()
            if row["값"] != 999999999
        }
    return data, label_map


DATA, LABELS = load_data()
WEIGHT = DATA["WT"].astype(float)


def weighted_share(mask, base=None):
    if base is None:
        base = pd.Series(True, index=DATA.index)
    valid = base & mask.fillna(False)
    return 100 * WEIGHT[valid].sum() / WEIGHT[base].sum()


def categorical_share(variable, base=None):
    if base is None:
        base = pd.Series(True, index=DATA.index)
    rows = []
    for value, label in LABELS[variable].items():
        rows.append((label, weighted_share(DATA[variable].eq(value), base)))
    return pd.DataFrame(rows, columns=["category", "percent"]).sort_values(
        "percent", ascending=False
    )


def multi_response_share(prefix, count, label_variable, base=None):
    if base is None:
        base = pd.Series(True, index=DATA.index)
    columns = [f"{prefix}_{i}" for i in range(1, count + 1)]
    answers = DATA[columns]
    rows = []
    for value, label in LABELS[label_variable].items():
        selected = answers.eq(value).any(axis=1)
        rows.append((label, weighted_share(selected, base)))
    return pd.DataFrame(rows, columns=["category", "percent"]).sort_values(
        "percent", ascending=False
    )


def setup_plotting():
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    sns.set_theme(style="whitegrid", font="Malgun Gothic")


def horizontal_bar(frame, title, filename, color="#167C80", limit=None):
    plot = frame.head(limit).sort_values("percent") if limit else frame.sort_values("percent")
    height = max(4.4, len(plot) * 0.48)
    fig, ax = plt.subplots(figsize=(10, height))
    bars = ax.barh(plot["category"], plot["percent"], color=color)
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=14)
    ax.set_xlabel("가중 비율 (%)")
    ax.set_ylabel("")
    ax.set_xlim(0, max(plot["percent"]) * 1.17)
    ax.bar_label(bars, labels=[f"{x:.1f}%" for x in plot["percent"]], padding=4)
    sns.despine(left=True, bottom=True)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def create_charts():
    setup_plotting()

    port = categorical_share("SQ3")
    nationality = categorical_share("SQ4").head(6)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    for ax, frame, title, color in [
        (axes[0], port.sort_values("percent"), "조사 항구", "#167C80"),
        (axes[1], nationality.sort_values("percent"), "주요 국적", "#D86B3C"),
    ]:
        bars = ax.barh(frame["category"], frame["percent"], color=color)
        ax.set_title(title, loc="left", fontsize=15, fontweight="bold")
        ax.set_xlabel("가중 비율 (%)")
        ax.set_ylabel("")
        ax.set_xlim(0, max(frame["percent"]) * 1.2)
        ax.bar_label(bars, labels=[f"{x:.1f}%" for x in frame["percent"]], padding=3)
        sns.despine(ax=ax, left=True, bottom=True)
    fig.suptitle("2025 제주 크루즈 승객 구성", x=0.03, ha="left", fontsize=18, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_01_port_nationality.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    activities = multi_response_share("Q12", 16, "Q12_1")
    horizontal_bar(activities, "제주 기항 중 실제 참여 활동", "chart_02_activities.png", limit=10)

    products = multi_response_share("Q15", 12, "Q15_1").head(8)
    places = multi_response_share("Q16", 7, "Q16_1").head(7)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, frame, title, color in [
        (axes[0], products.sort_values("percent"), "구매 품목", "#D86B3C"),
        (axes[1], places.sort_values("percent"), "쇼핑 장소", "#167C80"),
    ]:
        bars = ax.barh(frame["category"], frame["percent"], color=color)
        ax.set_title(title, loc="left", fontsize=15, fontweight="bold")
        ax.set_xlabel("가중 비율 (%)")
        ax.set_ylabel("")
        ax.set_xlim(0, max(frame["percent"]) * 1.22)
        ax.bar_label(bars, labels=[f"{x:.1f}%" for x in frame["percent"]], padding=3)
        sns.despine(ax=ax, left=True, bottom=True)
    fig.suptitle("크루즈 승객의 쇼핑 행동", x=0.03, ha="left", fontsize=18, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_03_shopping.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    purchased = weighted_share(DATA["Q10"].eq(1))
    purchase_source = categorical_share("Q10_1")
    purchase_source["percent"] = purchase_source["percent"] / purchased * 100
    purchase_source = purchase_source[purchase_source["percent"] > 0.1]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    axes[0].pie(
        [purchased, 100 - purchased],
        labels=["구매", "미구매"],
        autopct="%1.1f%%",
        startangle=90,
        colors=["#167C80", "#D9E1E2"],
        wedgeprops={"width": 0.42, "edgecolor": "white"},
    )
    axes[0].set_title("기항지 관광상품 구매 여부", fontsize=15, fontweight="bold")
    frame = purchase_source.sort_values("percent")
    bars = axes[1].barh(frame["category"], frame["percent"], color="#D86B3C")
    axes[1].set_title("구매자 중 상품 구매 경로", loc="left", fontsize=15, fontweight="bold")
    axes[1].set_xlabel("구매자 기준 비율 (%)")
    axes[1].set_xlim(0, max(frame["percent"]) * 1.2)
    axes[1].bar_label(bars, labels=[f"{x:.1f}%" for x in frame["percent"]], padding=3)
    sns.despine(ax=axes[1], left=True, bottom=True)
    fig.suptitle("기항지 관광상품 시장 구조", x=0.03, ha="left", fontsize=18, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_04_excursion_purchase.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    pain = multi_response_share("Q17", 16, "Q17_1")
    pain = pain[pain["category"] != "불만족하거나 불편한 점이 없다"]
    horizontal_bar(pain, "크루즈 승객의 주요 불편사항", "chart_05_pain_points.png", color="#B24C3D", limit=9)

    nationality_codes = [2, 1, 10, 12]
    activity_codes = [1, 4, 2, 3, 13, 5, 8, 10]
    activity_columns = [f"Q12_{i}" for i in range(1, 17)]
    rows = []
    for nationality_code in nationality_codes:
        base = DATA["SQ4"].eq(nationality_code)
        for activity_code in activity_codes:
            rows.append(
                {
                    "국적": LABELS["SQ4"][nationality_code],
                    "활동": LABELS["Q12_1"][activity_code],
                    "비율": weighted_share(
                        DATA[activity_columns].eq(activity_code).any(axis=1), base
                    ),
                }
            )
    heat = pd.DataFrame(rows).pivot(index="국적", columns="활동", values="비율")
    heat = heat[[LABELS["Q12_1"][x] for x in activity_codes]]
    fig, ax = plt.subplots(figsize=(13, 4.8))
    sns.heatmap(heat, annot=True, fmt=".1f", cmap="YlGnBu", cbar_kws={"label": "%"}, ax=ax)
    ax.set_title("주요 국적별 관광활동 차이", loc="left", fontsize=17, fontweight="bold", pad=14)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_06_nationality_activity.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def create_summary_tables():
    tables = {
        "항구_구성.csv": categorical_share("SQ3"),
        "국적_구성.csv": categorical_share("SQ4"),
        "관광활동.csv": multi_response_share("Q12", 16, "Q12_1"),
        "쇼핑품목.csv": multi_response_share("Q15", 12, "Q15_1"),
        "쇼핑장소.csv": multi_response_share("Q16", 7, "Q16_1"),
        "불편사항.csv": multi_response_share("Q17", 16, "Q17_1"),
    }
    for filename, frame in tables.items():
        frame.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    create_charts()
    create_summary_tables()
    print(f"Created outputs in: {OUTPUT_DIR}")
