// Recommendations page — W4-T6
import { api } from "@/lib/api"

export const revalidate = 300

export default async function RecommendationsPage() {
  let summary
  try { summary = await api.getSummary() }
  catch { summary = { executive: null, steward: null } }

  const DEMO_ACTIONS = [
    { title:"Assign owners to all unowned critical assets",    impact:"High",   effort:"Low",    type:"quick",   count:15, rule:"R1/GG1" },
    { title:"Add stewards to all CDE assets",                  impact:"High",   effort:"Medium", type:"quick",   count:8,  rule:"R4/GG4" },
    { title:"Map lineage for all KPI assets",                  impact:"High",   effort:"High",   type:"complex", count:6,  rule:"GG2"    },
    { title:"Tag all PII assets in Collibra",                  impact:"High",   effort:"Low",    type:"quick",   count:4,  rule:"GG3"    },
    { title:"Add business descriptions to undocumented assets",impact:"Medium", effort:"High",   type:"complex", count:22, rule:"R2"     },
    { title:"Review and refresh stale assets (>180 days)",     impact:"Medium", effort:"Medium", type:"complex", count:11, rule:"R3"     },
    { title:"Resolve duplicate asset names per domain",        impact:"Low",    effort:"Low",    type:"quick",   count:3,  rule:"R6"     },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Recommendations</h1>
        <p className="text-gray-400 text-sm mt-1">AI-generated priority actions from the latest governance scan</p>
      </div>

      {/* Executive summary */}
      {summary.executive && (
        <div className="bg-brand-700/20 border border-brand-600/30 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-brand-100 text-xs font-semibold uppercase tracking-wider">AI Executive Briefing</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-brand-600/30 text-brand-100 border border-brand-600/40">Claude Sonnet 4</span>
          </div>
          {summary.executive.split("\n\n").map((p, i) => (
            <p key={i} className="text-gray-200 text-sm leading-relaxed mb-3">{p}</p>
          ))}
        </div>
      )}

      {/* Priority action cards */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Priority Actions</h2>
        <div className="space-y-3">
          {DEMO_ACTIONS.map((action, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-start gap-4">
              <div className="text-gray-600 font-mono text-sm w-6 mt-0.5 flex-shrink-0">{i + 1}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-white text-sm font-medium leading-snug">{action.title}</p>
                  <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full border font-medium ${action.type==="quick"?"bg-emerald-900/30 text-emerald-300 border-emerald-700/40":"bg-amber-900/30 text-amber-300 border-amber-700/40"}`}>
                    {action.type === "quick" ? "⚡ Quick win" : "🔧 Complex fix"}
                  </span>
                </div>
                <div className="flex items-center gap-4 mt-2">
                  <span className="text-gray-500 text-xs">{action.count} instances</span>
                  <span className={`text-xs ${action.impact==="High"?"text-red-400":action.impact==="Medium"?"text-amber-400":"text-gray-400"}`}>
                    {action.impact} impact
                  </span>
                  <span className="text-gray-500 text-xs">{action.effort} effort</span>
                  <span className="text-gray-600 text-xs font-mono">Rule {action.rule}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Steward guidance */}
      {summary.steward && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Steward Remediation Guide</h2>
          <div className="prose prose-sm prose-invert max-w-none">
            {summary.steward.split("\n\n").map((p, i) => (
              <p key={i} className="text-gray-300 text-sm leading-relaxed mb-3">{p}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
