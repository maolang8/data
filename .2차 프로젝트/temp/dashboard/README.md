# 제주 크루즈 날씨 기반 관광상품 의사결정 대시보드

SQLite를 중심으로 크루즈 입항 실적, 시간별 기상, 관광상품 규칙을 결합하는 marimo 대시보드입니다.
원본 CSV는 `data/raw`, 통합 분석 DB는 `data/cruise_dashboard.db`에서 관리합니다.

## 로컬 실행

```powershell
cd ".2차 프로젝트/temp/dashboard"
python scripts/build_db.py
marimo run app.py --host 127.0.0.1 --port 2718
```

브라우저에서 `http://127.0.0.1:2718`을 엽니다.

## 메뉴

- 홈: 오늘/선택일 입항·기상·상품 브리핑
- 데이터 EDA: 자료 구조, 기준일, 항구·선박별 분포
- 승객 분석: 2025 외국인 조사 중 크루즈 표본 분석
- 융합 분석: 입항 실적과 시간별 기상의 결합 결과
- 영업 판단: 비·바람 복합 위험과 전환 규모
- 상품 제안: 영업직원용·관광객용 상품 카드
- 지도 동선: Folium 기반 항구·관광지·추천 동선
- 관리 검증: 데이터 최신성, 품질검사, 한계

기존 분석 보고서와 차트는 `analysis/`에서 확인할 수 있습니다.

## 데이터 갱신

원본 CSV 또는 `data/manual_cruise_updates.csv`를 수정한 뒤 DB를 다시 생성합니다.

```powershell
python scripts/build_db.py
python scripts/validate_db.py
```

GitHub Actions는 매주 월요일 오전(KST) DB를 재생성하고 품질검사를 수행합니다. 현재 크루즈 원천은 자동 API가 없어 원본 다운로드까지는 수동이며, 업로드 이후의 정제·검증·DB 생성이 자동화됩니다. Actions의 `Run workflow`로 즉시 실행할 수도 있습니다.

`data/cruise_dashboard.db`는 `scripts/build_db.py`로 다시 생성할 수 있습니다.
