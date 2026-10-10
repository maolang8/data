# 제주 크루즈 날씨 기반 인도어 관광 대시보드

SQLite를 중심으로 크루즈 입항 실적, 시간별 기상, 관광상품 규칙을 결합하는 marimo MVP입니다.
원본 CSV는 `data/raw`, 통합 분석 DB는 `data/cruise_dashboard.db`에서 관리합니다.

## 로컬 실행

```powershell
cd ".2차 프로젝트/temp/dashboard"
python scripts/build_db.py
marimo run app.py --host 127.0.0.1 --port 2718
```

브라우저에서 `http://127.0.0.1:2718`을 엽니다.

## 현재 구현 범위

- 홈: 오늘/선택일 크루즈 브리핑
- 데이터·EDA: 데이터 현황과 핵심 입항 분석
- 영업 의사결정: 비·바람 복합 위험 판정 및 상품 추천
- 관리·검증: 데이터 기준일, 상태, 한계

기존 분석 보고서와 차트는 `analysis/`에서 확인할 수 있습니다.

`data/cruise_dashboard.db`는 `scripts/build_db.py`로 다시 생성할 수 있습니다.
