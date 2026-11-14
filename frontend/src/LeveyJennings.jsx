import { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';

// Levey-Jennings chart: results in time order, plotted as SD from the
// target mean, with lines at the mean and at +/-1, 2 and 3 SD.
const STATUS_COLOR = { accept: '#2f6f4f', warning: '#c77d00', reject: '#c92a2a' };

export default function LeveyJennings({ results, control }) {
  const canvas = useRef(null);
  const chart = useRef(null);

  useEffect(() => {
    const labels = results.map((r) => new Date(r.measured_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
    const line = (sd) => labels.map(() => sd);
    const guide = (sd, color, dash) => ({
      data: line(sd), borderColor: color, borderWidth: 1, borderDash: dash, pointRadius: 0,
      label: sd === 0 ? 'Mean' : `${sd > 0 ? '+' : ''}${sd} SD`, fill: false, order: 2,
    });
    const data = {
      labels,
      datasets: [
        {
          label: control.analyte,
          data: results.map((r) => r.z),
          borderColor: '#5f6b73',
          borderWidth: 1.2,
          pointRadius: results.map((r) => (r.status === 'accept' ? 3.5 : 6)),
          pointBackgroundColor: results.map((r) => STATUS_COLOR[r.status]),
          pointBorderColor: results.map((r) => STATUS_COLOR[r.status]),
          order: 1,
        },
        guide(0, '#222', []),
        guide(1, '#bbb', [3, 3]), guide(-1, '#bbb', [3, 3]),
        guide(2, '#e0a800', [6, 4]), guide(-2, '#e0a800', [6, 4]),
        guide(3, '#e03131', []), guide(-3, '#e03131', []),
      ],
    };
    const options = {
      animation: false,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: (item) => item.datasetIndex === 0,
          callbacks: {
            label: (item) => {
              const r = results[item.dataIndex];
              const rules = r.violations.map((v) => v.rule).join(', ');
              return `${r.value} ${control.units} (z ${r.z.toFixed(2)}) · ${r.status}${rules ? ` · ${rules}` : ''}`;
            },
          },
        },
      },
      scales: {
        y: {
          min: -4, max: 4,
          ticks: {
            stepSize: 1,
            callback: (v) => (v === 0 ? `${control.target_mean}` : `${v > 0 ? '+' : ''}${v} SD`),
          },
          grid: { display: false },
        },
        x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } },
      },
    };
    if (chart.current) chart.current.destroy();
    chart.current = new Chart(canvas.current, { type: 'line', data, options });
    return () => chart.current?.destroy();
  }, [results, control]);

  return (
    <div className="chart">
      <canvas ref={canvas} aria-label={`Levey-Jennings chart for ${control.analyte} ${control.level}`} />
    </div>
  );
}
