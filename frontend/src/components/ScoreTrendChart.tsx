"use client"
/**
 * ScoreTrendChart — lightweight sparkline-style SVG line chart.
 *
 * Renders up to N historical health scores over time.
 * No external charting library — pure SVG so it stays bundle-light.
 */

interface DataPoint {
  date:  string   // ISO date string
  score: number
}

interface Props {
  data:   DataPoint[]
  height?: number
  width?:  number
}

export function ScoreTrendChart({ data, height = 80, width = 300 }: Props) {
  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-gray-600 text-xs"
        style={{ width, height }}
      >
        Not enough scan history yet
      </div>
    )
  }

  const padX = 8
  const padY = 8
  const W    = width  - padX * 2
  const H    = height - padY * 2

  const scores = data.map(d => d.score)
  const minS   = Math.max(0,   Math.min(...scores) - 5)
  const maxS   = Math.min(100, Math.max(...scores) + 5)

  const toX = (i: number) => padX + (i / (data.length - 1)) * W
  const toY = (s: number) => padY + H - ((s - minS) / (maxS - minS)) * H

  const points   = data.map((d, i) => `${toX(i)},${toY(d.score)}`)
  const polyline = points.join(" ")

  // Filled area path
  const area = [
    `M ${toX(0)},${toY(data[0].score)}`,
    ...data.map((d, i) => `L ${toX(i)},${toY(d.score)}`),
    `L ${toX(data.length - 1)},${padY + H}`,
    `L ${padX},${padY + H}`,
    "Z",
  ].join(" ")

  const lastScore = data[data.length - 1].score
  const lineCol   = lastScore >= 75 ? "#34d399" : lastScore >= 50 ? "#fbbf24" : "#f87171"
  const areaCol   = lastScore >= 75 ? "#34d39920" : lastScore >= 50 ? "#fbbf2420" : "#f8717120"

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
      {/* Area fill */}
      <path d={area} fill={areaCol} />
      {/* Line */}
      <polyline
        points={polyline}
        fill="none"
        stroke={lineCol}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Dots */}
      {data.map((d, i) => (
        <circle key={i} cx={toX(i)} cy={toY(d.score)} r={3} fill={lineCol} />
      ))}
    </svg>
  )
}
