import React, { useState } from 'react';
import { ForecastPoint } from '../types/telemetry';

interface ForecastChartProps {
  currentLoad: number;
  points: ForecastPoint[];
  thresholdPct?: number;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({
  currentLoad,
  points,
  thresholdPct = 85.0
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!points || points.length === 0) {
    return <div className="text-slate-500 text-xs py-10 text-center">No forecast points available.</div>;
  }

  // Chart dimensions
  const width = 640;
  const height = 240;
  const paddingLeft = 40;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 35;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // X scale: index 0 (Now) to points.length (24 hours)
  const totalSteps = points.length;
  const getX = (idx: number) => paddingLeft + (idx / totalSteps) * chartWidth;
  // Y scale: 0 to 100%
  const getY = (val: number) => paddingTop + (1.0 - Math.min(100, Math.max(0, val)) / 100.0) * chartHeight;

  // Construct points including "Now" as point 0
  const allPoints = [
    { forecast_load_pct: currentLoad, lower_bound_pct: currentLoad, upper_bound_pct: currentLoad, timestamp: 'Now' },
    ...points
  ];

  // Predictive curve path
  const curvePath = allPoints.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)},${getY(pt.forecast_load_pct)}`).join(' ');

  // 95% Uncertainty Band polygon
  const upperPath = allPoints.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)},${getY(pt.upper_bound_pct)}`).join(' ');
  const lowerPathReversed = allPoints.slice().reverse().map((pt, i) => {
    const realIdx = allPoints.length - 1 - i;
    return `L ${getX(realIdx)},${getY(pt.lower_bound_pct)}`;
  }).join(' ');
  const bandPolygon = `${upperPath} ${lowerPathReversed} Z`;

  // Capacity threshold Y
  const thresholdY = getY(thresholdPct);

  // Find peak point
  let peakIdx = 0;
  let peakVal = 0;
  points.forEach((pt, idx) => {
    if (pt.forecast_load_pct > peakVal) {
      peakVal = pt.forecast_load_pct;
      peakIdx = idx + 1; // +1 because index 0 is "Now"
    }
  });

  return (
    <div className="relative w-full bg-slate-950 rounded-xl p-3 border border-slate-800">
      <div className="flex items-center justify-between text-xs mb-2">
        <span className="font-semibold text-slate-300">24-Hour AI Predictive Load Curve</span>
        <div className="flex items-center space-x-3 text-[11px]">
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-0.5 bg-cyan-400 inline-block" />
            <span className="text-slate-400">Prediction</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 bg-cyan-500/20 rounded inline-block" />
            <span className="text-slate-400">95% Uncertainty</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-0.5 border-t border-dashed border-rose-500 inline-block" />
            <span className="text-rose-400">85% Overload Line</span>
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto overflow-visible select-none"
      >
        {/* Horizontal Gridlines */}
        {[20, 40, 60, 80, 100].map((level) => {
          const y = getY(level);
          return (
            <g key={level}>
              <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#1e293b" strokeDasharray="2,2" />
              <text x={paddingLeft - 6} y={y + 3} textAnchor="end" fill="#64748b" fontSize="9" fontFamily="monospace">
                {level}%
              </text>
            </g>
          );
        })}

        {/* 85% Overload Threshold line */}
        <line
          x1={paddingLeft}
          y1={thresholdY}
          x2={width - paddingRight}
          y2={thresholdY}
          stroke="#ef4444"
          strokeWidth="1.5"
          strokeDasharray="4,3"
        />
        <text
          x={width - paddingRight}
          y={thresholdY - 5}
          textAnchor="end"
          fill="#ef4444"
          fontSize="9"
          fontWeight="bold"
        >
          85% Capacity Limit
        </text>

        {/* 95% Uncertainty Confidence Band */}
        <path d={bandPolygon} fill="rgba(6, 182, 212, 0.15)" stroke="none" />

        {/* Forecast Curve */}
        <path d={curvePath} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinecap="round" />

        {/* "Now" Marker */}
        <line
          x1={getX(0)}
          y1={paddingTop}
          x2={getX(0)}
          y2={height - paddingBottom}
          stroke="#3b82f6"
          strokeWidth="1"
          strokeDasharray="2,2"
        />
        <circle cx={getX(0)} cy={getY(currentLoad)} r="4" fill="#3b82f6" stroke="#ffffff" strokeWidth="1.5" />
        <text x={getX(0)} y={height - paddingBottom + 14} textAnchor="middle" fill="#60a5fa" fontSize="10" fontWeight="bold">
          Now
        </text>

        {/* Peak Prediction Marker */}
        {peakIdx > 0 && (
          <g>
            <circle cx={getX(peakIdx)} cy={getY(peakVal)} r="5" fill="#f43f5e" stroke="#ffffff" strokeWidth="2" />
            <text
              x={getX(peakIdx)}
              y={getY(peakVal) - 10}
              textAnchor="middle"
              fill="#fda4af"
              fontSize="10"
              fontWeight="bold"
            >
              Peak: {peakVal.toFixed(1)}%
            </text>
          </g>
        )}

        {/* Time X-axis Labels (every 4 hours) */}
        {allPoints.map((pt, i) => {
          if (i === 0 || i % 4 !== 0) return null;
          const label = `${i}h`;
          return (
            <text
              key={i}
              x={getX(i)}
              y={height - paddingBottom + 14}
              textAnchor="middle"
              fill="#64748b"
              fontSize="9"
              fontFamily="monospace"
            >
              +{label}
            </text>
          );
        })}

        {/* Hover detection vertical rule */}
        {hoverIdx !== null && allPoints[hoverIdx] && (
          <g>
            <line
              x1={getX(hoverIdx)}
              y1={paddingTop}
              x2={getX(hoverIdx)}
              y2={height - paddingBottom}
              stroke="#94a3b8"
              strokeWidth="1"
              strokeDasharray="2,2"
            />
            <circle
              cx={getX(hoverIdx)}
              cy={getY(allPoints[hoverIdx].forecast_load_pct)}
              r="4.5"
              fill="#06b6d4"
              stroke="#ffffff"
              strokeWidth="2"
            />
          </g>
        )}

        {/* Invisible overlay rects for hover */}
        {allPoints.map((_, i) => (
          <rect
            key={i}
            x={getX(i) - (chartWidth / totalSteps) / 2}
            y={paddingTop}
            width={chartWidth / totalSteps}
            height={chartHeight}
            fill="transparent"
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
            className="cursor-crosshair"
          />
        ))}
      </svg>

      {/* Hover Tooltip Box */}
      {hoverIdx !== null && allPoints[hoverIdx] && (
        <div className="mt-2 p-2 bg-slate-900 border border-slate-700 rounded-lg text-xs flex items-center justify-between font-mono">
          <span className="text-cyan-300 font-semibold">
            {hoverIdx === 0 ? 'Current Live Reading' : `Hour +${hoverIdx} Projection`}
          </span>
          <span className="text-white">
            Predicted Load: <strong className="text-cyan-400">{allPoints[hoverIdx].forecast_load_pct.toFixed(1)}%</strong>
          </span>
          <span className="text-slate-400 text-[11px]">
            Uncertainty: [{allPoints[hoverIdx].lower_bound_pct.toFixed(1)}% - {allPoints[hoverIdx].upper_bound_pct.toFixed(1)}%]
          </span>
        </div>
      )}
    </div>
  );
};

