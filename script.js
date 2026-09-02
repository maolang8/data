document.addEventListener('DOMContentLoaded', () => {
    // Exact Values from CSV analysis
    const TOTAL_USAGE = 41649637;
    const TOTAL_STATIONS = 2824;

    // Number Count-Up Animation
    animateValue('totalUsage', 0, TOTAL_USAGE, 2000, true);
    animateValue('totalStations', 0, TOTAL_STATIONS, 1800, true);

    // Chart.js Pie Chart Initialization
    initPieChart();
});

function animateValue(id, start, end, duration, formatCommas = false) {
    const obj = document.getElementById(id);
    if (!obj) return;

    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        // EaseOutExpo easing
        const easedProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        const currentValue = Math.floor(easedProgress * (end - start) + start);

        obj.textContent = formatCommas ? currentValue.toLocaleString() : currentValue;

        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.textContent = formatCommas ? end.toLocaleString() : end;
        }
    };
    window.requestAnimationFrame(step);
}

function initPieChart() {
    const ctx = document.getElementById('usagePieChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['평일 (75.4%)', '주말 (24.6%)'],
            datasets: [{
                data: [31414681, 10234956],
                backgroundColor: [
                    '#10b981',
                    '#06b6d4'
                ],
                borderColor: '#0b0f19',
                borderWidth: 3,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94a3b8',
                        font: {
                            family: 'Inter',
                            size: 12,
                            weight: '500'
                        },
                        padding: 15
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            let value = context.parsed || 0;
                            return ` ${label}: ${value.toLocaleString()}건`;
                        }
                    }
                }
            },
            cutout: '68%'
        }
    });
}
