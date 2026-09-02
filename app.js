/**
 * Seoul Bike Summary Dashboard Logic
 * Core Metrics Count-up Animation & Interactions
 */

// Target verified values from bike_station_hourly.csv
const METRICS_DATA = {
  totalRentals: 41649637,
  activeStations: 2824,
  weekdayRentals: 31414681,
  weekendRentals: 10234956
};

// Easing function for smooth counting acceleration & deceleration
function easeOutExpo(x) {
  return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}

/**
 * Animate numbers counting up smoothly
 * @param {HTMLElement} element - Target DOM element
 * @param {number} targetValue - Final value to reach
 * @param {number} durationMs - Duration of animation in ms
 */
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

/**
 * Run all animations
 */
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

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  runAllAnimations();

  const replayBtn = document.getElementById('btnReplayAnimation');
  if (replayBtn) {
    replayBtn.addEventListener('click', () => {
      runAllAnimations();
    });
  }
});
