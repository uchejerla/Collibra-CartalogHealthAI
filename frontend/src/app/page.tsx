// Overview page — W4-T3
import { api } from "@/lib/api"
import { HealthGauge } from "@/components/HealthGauge"
import { ScoreTrendChart } from "@/components/ScoreTrendChart"
import { SeverityBadge } from "@/components/SeverityBadge"
import { format } from "date-fns"

export const revalidate = 60   // ISR: refresh every 60s

export default async function OverviewPage() {
  let health, summary
  try {
    [health, summary] = await Promise.all([api.getHealthScore(), api.getSummary()])
  } catch {
    health  = { health_score:0, audit_score:0, high_count:0, medium_count:0, low_count:0, total_findings:0, total_assets:0, scanned_at:null, breakdown:{} }
    summary = { executive: null }
  }

  const scannedAt = health.scanned_at
    ? format(new Date(health.scanned_at), "MMM d, yyyy 'at' HH:mm 'UTC'")
    : "No scan yet"

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Governance Overview</h1>
          <p className="text-gray-400 text-sm mt-1">Last scan: {scannedAt}</p>
        </div>
        <span className="text-xs px-3 py-1 rounded-full bg-brand-600/30 text-brand-100 border border-brand-600/50">
          {health.total_assets} assets monitored
        </span>
      </div>

      {/* Score row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 flex flex-col items-center">
          <HealthGauge score={health.health_score} />
          <p className="text-gray-400 text-xs mt-3">Governance Health Score</p>
        </div>
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 flex flex-col items-center justify-center">
          <span className={`text-5xl font-bold ${health.audit_score >= 80 ? "text-emerald-400" : health.audit_score >= 60 ? "text-amber-400" : "text-red-400"}`}>
            {health.audit_score?.toFixed(0) ?? "—"}
          </span>
          <p className="text-gray-400 text-xs mt-3">Audit Readiness Score</p>
        </div>
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-4">
          <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Findings Breakdown</p>
          <div className="space-y-3">
            {[["High", health.high_count], ["Medium", health.medium_count], ["Low", health.low_count]].map(([sev, count]) => (
              <div key={sev as string} className="flex items-center justify-between">
                <SeverityBadge severity={sev as string} />
                <span className="text-white font-semibold">{count as number}</span>
              </div>
            ))}
            <div className="border-t border-gray-700 pt-2 flex justify-between text-gray-400 text-sm">
              <span>Total</span>
              <span className="text-white font-semibold">{health.total_findings}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Agent breakdown */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Findings by Agent</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(health.breakdown).map(([agent, counts]) => (
            <div key={agent} className="bg-gray-800 rounded-lg p-4">
              <p className="text-xs text-gray-400 capitalize mb-2">{agent.replace("_", " ")}</p>
              <div className="space-y-1 text-xs">
                {Object.entries(counts as Record<string,number>).map(([sev, n]) => (
                  <div key={sev} className="flex justify-between">
                    <span className="text-gray-500">{sev}</span>
                    <span className="text-white font-medium">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Executive summary */}
      {summary.executive && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">AI Executive Summary</h2>
          <div className="prose prose-sm prose-invert max-w-none">
            {summary.executive.split("\n\n").map((para, i) => (
              <p key={i} className="text-gray-300 text-sm leading-relaxed mb-3">{para}</p>
            ))}
          </div>
          {summary.from_cache && (
            <p className="text-gray-600 text-xs mt-4">Cached · Generated {summary.generated_at ? format(new Date(summary.generated_at), "MMM d 'at' HH:mm") : ""}</p>
          )}
        </div>
      )}
    </div>
  )
}
