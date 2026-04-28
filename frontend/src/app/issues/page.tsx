// Issues page — W4-T4: filterable findings table
"use client"
import { useEffect, useState, useCallback } from "react"
import { api, Finding } from "@/lib/api"
import { SeverityBadge } from "@/components/SeverityBadge"
import { format } from "date-fns"

const AGENTS = ["metadata_curator","lineage_guardian","governance_gap","executive_risk"]
const SEVERITIES = ["High","Medium","Low"]
const STATUSES = ["Open","In Progress","Resolved","Suppressed"]

export default function IssuesPage() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [severity, setSeverity] = useState("")
  const [agent, setAgent] = useState("")
  const [status, setStatus] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.getIssues({ severity: severity||undefined, agent: agent||undefined, status: status||undefined, page, page_size: 50 })
      setFindings(res.findings)
      setTotal(res.total)
    } finally { setLoading(false) }
  }, [severity, agent, status, page])

  useEffect(() => { load() }, [load])

  const Select = ({ value, onChange, options, placeholder }: any) => (
    <select value={value} onChange={e => { onChange(e.target.value); setPage(1) }}
      className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-600 outline-none">
      <option value="">{placeholder}</option>
      {options.map((o: string) => <option key={o} value={o}>{o}</option>)}
    </select>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Issues</h1>
          <p className="text-gray-400 text-sm mt-1">{total} findings from latest scan</p>
        </div>
        <button onClick={load} className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 transition-colors">
          ↺ Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={severity} onChange={setSeverity} options={SEVERITIES} placeholder="All severities" />
        <Select value={agent} onChange={setAgent} options={AGENTS} placeholder="All agents" />
        <Select value={status} onChange={setStatus} options={STATUSES} placeholder="All statuses" />
        {(severity||agent||status) && (
          <button onClick={() => { setSeverity(""); setAgent(""); setStatus(""); setPage(1) }}
            className="text-xs px-3 py-2 text-gray-400 hover:text-white transition-colors">
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              {["Severity","Asset","Agent","Issue Type","Message","Status","Date"].map(h => (
                <th key={h} className="text-left text-gray-400 font-medium text-xs uppercase tracking-wider px-4 py-3 first:pl-5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center text-gray-500 py-12">Loading findings…</td></tr>
            ) : findings.length === 0 ? (
              <tr><td colSpan={7} className="text-center text-gray-500 py-12">No findings match your filters.</td></tr>
            ) : findings.map(f => (
              <tr key={f.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-3 first:pl-5"><SeverityBadge severity={f.severity} /></td>
                <td className="px-4 py-3 text-gray-200 font-medium max-w-[140px] truncate">{f.asset_name ?? "—"}</td>
                <td className="px-4 py-3 text-gray-400 text-xs capitalize">{f.agent.replace("_"," ")}</td>
                <td className="px-4 py-3 text-gray-400 text-xs font-mono">{f.issue_type}</td>
                <td className="px-4 py-3 text-gray-300 max-w-xs">{f.message}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${f.status==="Open"?"bg-gray-800 text-gray-300 border-gray-700":f.status==="Done"||f.status==="Resolved"?"bg-green-900/30 text-green-300 border-green-700/50":"bg-blue-900/30 text-blue-300 border-blue-700/50"}`}>
                    {f.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{format(new Date(f.created_at),"MMM d")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center gap-3 justify-end text-sm">
          <button disabled={page===1} onClick={() => setPage(p=>p-1)} className="px-3 py-1.5 rounded border border-gray-700 text-gray-300 disabled:opacity-40 hover:bg-gray-800 transition-colors">← Prev</button>
          <span className="text-gray-400">Page {page} of {Math.ceil(total/50)}</span>
          <button disabled={page>=Math.ceil(total/50)} onClick={() => setPage(p=>p+1)} className="px-3 py-1.5 rounded border border-gray-700 text-gray-300 disabled:opacity-40 hover:bg-gray-800 transition-colors">Next →</button>
        </div>
      )}
    </div>
  )
}
