"use client"
/**
 * HealthGauge — SVG semi-circle gauge for the governance health score.
 *
 * Score range: 0 – 100
 * Colour zones: red (0–49) → amber (50–74) → emerald (75–100)
 */

interface Props {
  score: number
  size?: number
}

function scoreToColour(score: number): string {
  if (score >= 75) return "#34d399"  // emerald-400
  if (score >= 50) return "#fbbf24"  // amber-400
  return "#f87171"                   // red-400
}

export function HealthGauge({ score, size = 160 }: Props) {
  const clamped = Math.min(100, Math.max(0, score))
  const colour  = scoreToColour(clamped)

  // SVG semi-circle maths
  const r     = 60
  const cx    = 80
  const cy    = 85
  const circ  = Math.PI * r          // half circumference
  const fill  = (clamped / 100) * circ

  // Stroke dasharray trick for semi-circle fill
  const trackPath = `M ${cx - r},${cy} A ${r},${r} 0 0 1 ${cx + r},${cy}`

  return (
    <div className="flex flex-col items-center select-none" style={{ width: size }}>
      <svg viewBox="0 0 160 95" width={size} height={(size / 160) * 95}>
        {/* Track */}
        <path
          d={trackPath}
          fill="none"
          stroke="#374151"    // gray-700
          strokeWidth={12}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d={trackPath}
          fill="none"
          stroke={colour}
          strokeWidth={12}
          strokeLinecap="round"
          strokeDasharray={`${fill} ${circ}`}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        {/* Score label */}
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          fontSize={28}
          fontWeight={700}
          fill={colour}
          fontFamily="ui-sans-serif, system-ui, sans-serif"
        >
          {clamped.toFixed(0)}
        </text>
        {/* "/100" sub-label */}
        <text
          x={cx}
          y={cy + 10}
          textAnchor="middle"
          fontSize={11}
          fill="#6b7280"
          fontFamily="ui-sans-serif, system-ui, sans-serif"
        >
          / 100
        </text>
      </svg>
    </div>
  )
}
