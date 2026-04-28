/**
 * SeverityBadge — coloured pill for High / Medium / Low findings.
 */

interface Props {
  severity: string
  size?: "sm" | "md"
}

const STYLES: Record<string, string> = {
  High:   "bg-red-900/40 text-red-300 border border-red-700/60",
  Medium: "bg-amber-900/40 text-amber-300 border border-amber-700/60",
  Low:    "bg-blue-900/30 text-blue-300 border border-blue-700/50",
}

const DOTS: Record<string, string> = {
  High:   "bg-red-400",
  Medium: "bg-amber-400",
  Low:    "bg-blue-400",
}

export function SeverityBadge({ severity, size = "sm" }: Props) {
  const style = STYLES[severity] ?? "bg-gray-800 text-gray-300 border border-gray-700"
  const dot   = DOTS[severity] ?? "bg-gray-500"
  const textSize = size === "sm" ? "text-xs" : "text-sm"

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-medium ${textSize} ${style}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {severity}
    </span>
  )
}
