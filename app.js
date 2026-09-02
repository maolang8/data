/**
 * Seoul Bike Summary & Peak Time Dashboard Logic
 */

const METRICS_DATA = {
  totalRentals: 41649637,
  activeStations: 2824,
  weekdayRentals: 31414681,
  weekendRentals: 10234956
};

// 24-Hour Total Usage Array from bike_station_hourly.csv
const HOURLY_DATA = [
  803541, 561175, 378137, 276262, 238539, 470064, 989391, 2263077, 
  3236294, 1852187, 1463265, 1658868, 1801385, 1812774, 1859516, 2101214, 
  2553022, 3403323, 4017557, 2762090, 2315545, 2088862, 1687743, 1055806
];

// Top Stations Verified List for Search & Inspector
const TOP_STATIONS = [
  { id: 2715, name: "2715. 마곡나루역 2번 출구", total: 173645, peak: "오전 08:00 (출근 피크)" },
  { id: 1210, name: "1210. 롯데월드타워(잠실역2번출구 쪽)", total: 122673, peak: "오후 18:00 (퇴근 피크)" },
  { id: 2728, name: "2728. 마곡나루역 3번 출구", total: 121698, peak: "오후 18:00 (퇴근 피크)" },
  { id: 2701, name: "2701. 마곡나루역 5번출구 뒤편", total: 114953, peak: "오전 08:00 (출근 피크)" },
  { id: 5515, name: "5515. 한강버스 망원 선착장", total: 97178, peak: "오후 18:00 (퇴근 피크)" },
  { id: 1153, name: "1153. 발산역 1번, 9번 인근 대여소", total: 96067, peak: "오후 18:00 (퇴근 피크)" },
  { id: 230, name: "230. 영등포구청역 7번출구", total: 90789, peak: "오전 08:00 (출근 피크)" },
  { id: 502, name: "502. 자양(뚝섬한강공원)역 1번출구 앞", total: 88882, peak: "오후 18:00 (퇴근 피크)" },
  { id: 2622, name: "2622. 올림픽공원역 3번출구", total: 79556, peak: "오후 18:00 (퇴근 피크)" },
  { id: 2608, name: "2608. 송파구청", total: 79455, peak: "오후 18:00 (퇴근 피크)" },
  { id: 1124, name: "1124. 발산역 6번 출구 뒤", total: 72977, peak: "오후 18:00 (퇴근 피크)" },
  { id: 1911, name: "1911. 구로디지털단지역 앞", total: 70484, peak: "오후 18:00 (퇴근 피크)" },
  { id: 792, name: "792. 목동트라팰리스 웨스턴에비뉴", total: 70074, peak: "오후 18:00 (퇴근 피크)" },
  { id: 769, name: "769. CBS방송국 앞", total: 69556, peak: "오후 18:00 (퇴근 피크)" },
  { id: 4217, name: "4217. 한강공원 망원나들목", total: 69466, peak: "오후 20:00 (야간 레저)" }
];

function easeOutExpo(x) {
  return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}

function animateValue(element, targetValue, durationMs = 1800) {
  let startTime = null;
  element.innerText = "0";

  function step(timestamp) {
    if (!startTime) startTime = timestamp;
    const progress = Math.min((timestamp - startTime) / durationMs, 1);
    const easedProgress = easeOutExpo(progress);
    const currentVal = Math.floor(easedProgress * targetValue);

    element.innerText = currentVal.toLocaleString('ko-KR');

    if (progress < 1) {
      window.requestAnimationFrame(step);
    } else {
      element.innerText = targetValue.toLocaleString('ko-KR');
    }
  }

  window.requestAnimationFrame(step);
}

function runAllAnimations() {
  const rentalsEl = document.getElementById('totalRentalsCount');
  const stationsEl = document.getElementById('activeStationsCount');

  if (rentalsEl) {
    animateValue(rentalsEl, METRICS_DATA.totalRentals, 2000);
  }
  if (stationsEl) {
    animateValue(stationsEl, METRICS_DATA.activeStations, 1500);
  }
}

// Render 24-Hour Peak Time Chart
let trendChartInstance = null;
function initHourlyChart() {
  const ctx = document.getElementById('hourlyTrendChart');
  if (!ctx) return;

  const hoursLabels = Array.from({length: 24}, (_, i) => `${String(i).padStart(2, '0')}시`);

  const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, 'rgba(56, 189, 248, 0.45)');
  gradient.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: hoursLabels,
      datasets: [{
        label: '대여건수',
        data: HOURLY_DATA,
        fill: true,
        backgroundColor: gradient,
        borderColor: '#38bdf8',
        borderWidth: 3,
        tension: 0.35,
        pointBackgroundColor: function(context) {
          const index = context.dataIndex;
          if (index === 8 || index === 18) return '#f59e0b'; // Highlight 8 AM & 6 PM
          return '#38bdf8';
        },
        pointRadius: function(context) {
          const index = context.dataIndex;
          if (index === 8 || index === 18) return 6;
          return 3;
        },
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#38bdf8',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              const val = context.parsed.y;
              const hour = context.dataIndex;
              let tag = '';
              if (hour === 8) tag = ' 🌅 [출근 피크]';
              if (hour === 18) tag = ' 🌆 [퇴근 피크]';
              return ` 이용량: ${val.toLocaleString('ko-KR')}건${tag}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: { color: '#94a3b8', font: { family: 'Pretendard', size: 11 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: {
            color: '#64748b',
            font: { family: 'Outfit', size: 11 },
            callback: function(value) {
              return (value / 10000).toFixed(0) + '만';
            }
          }
        }
      }
    }
  });
}

// Station Inspector & Search Logic
function initStationSearch() {
  const selectEl = document.getElementById('stationSelect');
  const inputEl = document.getElementById('stationSearchInput');

  if (!selectEl || !inputEl) return;

  // Populate dropdown
  TOP_STATIONS.forEach(st => {
    const opt = document.createElement('option');
    opt.value = st.id;
    opt.textContent = `${st.name} (총 ${st.total.toLocaleString()}건)`;
    selectEl.appendChild(opt);
  });

  function updateDisplay(st) {
    document.getElementById('resStationId').textContent = `대여소 #${st.id}`;
    document.getElementById('resStationName').textContent = st.name;
    document.getElementById('resTotalCount').textContent = `${st.total.toLocaleString('ko-KR')}건`;
    document.getElementById('resPeakHour').textContent = st.peak;
  }

  selectEl.addEventListener('change', (e) => {
    const val = parseInt(e.target.value);
    const found = TOP_STATIONS.find(s => s.id === val);
    if (found) updateDisplay(found);
  });

  inputEl.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    if (!q) return;
    const found = TOP_STATIONS.find(s => s.name.toLowerCase().includes(q) || String(s.id).includes(q));
    if (found) {
      updateDisplay(found);
      selectEl.value = found.id;
    }
  });
}

// DOM Init
document.addEventListener('DOMContentLoaded', () => {
  runAllAnimations();
  initHourlyChart();
  initStationSearch();

  const replayBtn = document.getElementById('btnReplayAnimation');
  if (replayBtn) {
    replayBtn.addEventListener('click', () => {
      runAllAnimations();
    });
  }
});
