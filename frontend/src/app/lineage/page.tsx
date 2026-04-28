// Lineage graph page — W4-T5: NetworkX-style graph visualisation
"use client"
import { useEffect, useState, useRef, useCallback } from "react"
import { api, Finding } from "@/lib/api"
import { SeverityBadge } from "@/components/SeverityBadge"

// ── Types ─────────────────────────────────────────────────────────────────────

interface Node {
  id:       string
  label:    string
  critical: boolean
  pii:      boolean
  domain:   string
  x:        number
  y:        number
  vx:       number   // velocity for force sim
  vy:       number
}

interface Edge {
  source:     string
  target:     string
  confidence: number
}

interface GraphData {
  nodes: Node[]
  edges: Edge[]
}

// ── Force-directed layout helpers ────────────────────────────────────────────

function buildGraphFromFindings(findings: Finding[]): GraphData {
  const nodeMap = new Map<string, Node>()
  const edges: Edge[] = []

  // Extract nodes from lineage-related findings
  for (const f of findings) {
    if (!f.asset_name) continue
    const id = f.asset_id ?? f.asset_name
    if (!nodeMap.has(id)) {
      nodeMap.set(id, {
        id,
        label:    f.asset_name,
        critical: f.issue_type.includes("critical") || f.severity === "High",
        pii:      f.issue_type.includes("pii"),
        domain:   "",
        x:        Math.random() * 600 + 100,
        y:        Math.random() * 300 + 100,
        vx: 0, vy: 0,
      })
    }
    // Low-confidence lineage → draw the edge
    if (f.issue_type === "low_confidence_lineage" && f.details) {
      const src = (f.details as Record<string, string>)["source"]
      const tgt = (f.details as Record<string, string>)["target"]
      if (src && tgt) {
        edges.push({ source: src, target: tgt, confidence: Number(f.details["confidence"] ?? 0.5) })
      }
    }
  }

  return { nodes: Array.from(nodeMap.values()), edges }
}

function applyForce(nodes: Node[], edges: Edge[], iterations = 50): Node[] {
  const n = nodes.map(nd => ({ ...nd }))
  const idx = new Map(n.map((nd, i) => [nd.id, i]))
  const k   = 80
  const W   = 760
  const H   = 500

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion
    for (let i = 0; i < n.length; i++) {
      for (let j = i + 1; j < n.length; j++) {
        const dx = n[i].x - n[j].x
        const dy = n[i].y - n[j].y
        const d  = Math.sqrt(dx * dx + dy * dy) || 1
        const f  = (k * k) / d
        n[i].vx += (dx / d) * f * 0.1
        n[i].vy += (dy / d) * f * 0.1
        n[j].vx -= (dx / d) * f * 0.1
        n[j].vy -= (dy / d) * f * 0.1
      }
    }
    // Attraction along edges
    for (const e of edges) {
      const si = idx.get(e.source)
      const ti = idx.get(e.target)
      if (si == null || ti == null) continue
      const dx = n[ti].x - n[si].x
      const dy = n[ti].y - n[si].y
      const d  = Math.sqrt(dx * dx + dy * dy) || 1
      const f  = (d * d) / k * 0.05
      n[si].vx += (dx / d) * f
      n[si].vy += (dy / d) * f
      n[ti].vx -= (dx / d) * f
      n[ti].vy -= (dy / d) * f
    }
    // Apply + clamp to canvas
    for (const nd of n) {
      nd.x = Math.min(W - 40, Math.max(40, nd.x + nd.vx))
      nd.y = Math.min(H - 40, Math.max(40, nd.y + nd.vy))
      nd.vx *= 0.85
      nd.vy *= 0.85
    }
  }
  return n
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function LineagePage() {
  const [graph,   setGraph]   = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const [stats,   setStats]   = useState({ nodes: 0, edges: 0, orphans: 0, lowConf: 0 })

  const W = 760
  const H = 500

  useEffect(() => {
    ;(async () => {
      setLoading(true)
      try {
        const res = await api.getIssues({ page_size: 200 })
        const lineageFindings = res.findings.filter(f =>
          ["orphan_node", "disconnected_cluster", "low_confidence_lineage",
           "critical_disconnected_lineage"].includes(f.issue_type)
        )

        const base = buildGraphFromFindings(lineageFindings)
        const laid = applyForce(base.nodes, base.edges, 80)
        const g    = { nodes: laid, edges: base.edges }
        setGraph(g)
        setStats({
          nodes:   g.nodes.length,
          edges:   g.edges.length,
          orphans: lineageFindings.filter(f => f.issue_type === "orphan_node").length,
          lowConf: lineageFindings.filter(f => f.issue_type === "low_confidence_lineage").length,
        })
      } catch (e: any) {
        setError(e.message ?? "Failed to load lineage data")
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  // Confidence → edge colour
  const edgeColour = (conf: number) => conf < 0.5 ? "#f87171" : conf < 0.8 ? "#fbbf24" : "#4b5563"

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Lineage Graph</h1>
          <p className="text-gray-400 text-sm mt-1">
            Visualises data flow issues detected by the Lineage Guardian agent
          </p>
        </div>
        {!loading && graph && (
          <div className="flex gap-4 text-xs text-gray-400">
            <span>{stats.nodes} nodes</span>
            <span>{stats.edges} edges</span>
            {stats.orphans > 0 && <span className="text-amber-400">{stats.orphans} orphans</span>}
            {stats.lowConf > 0  && <span className="text-red-400">{stats.lowConf} low-confidence</span>}
          </div>
        )}
      </div>

      {/* Graph canvas */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-[500px] text-gray-500 text-sm">
            Loading lineage data…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-[500px] text-red-400 text-sm">{error}</div>
        ) : graph && graph.nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[500px] gap-3 text-gray-500">
            <span className="text-4xl">✓</span>
            <p className="text-sm">No lineage issues detected in the latest scan.</p>
          </div>
        ) : graph ? (
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
            {/* Edges */}
            {graph.edges.map((e, i) => {
              const src = graph.nodes.find(n => n.id === e.source || n.label === e.source)
              const tgt = graph.nodes.find(n => n.id === e.target || n.label === e.target)
              if (!src || !tgt) return null
              return (
                <g key={`e${i}`}>
                  <line
                    x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                    stroke={edgeColour(e.confidence)}
                    strokeWidth={e.confidence < 0.5 ? 2 : 1.5}
                    strokeDasharray={e.confidence < 0.5 ? "6 3" : undefined}
                    opacity={0.7}
                    markerEnd="url(#arrow)"
                  />
                  {/* Confidence label at midpoint */}
                  <text
                    x={(src.x + tgt.x) / 2}
                    y={(src.y + tgt.y) / 2 - 4}
                    fill={edgeColour(e.confidence)}
                    fontSize={9}
                    textAnchor="middle"
                    opacity={0.8}
                  >
                    {(e.confidence * 100).toFixed(0)}%
                  </text>
                </g>
              )
            })}

            {/* Arrow marker */}
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L8,3 z" fill="#4b5563" />
              </marker>
            </defs>

            {/* Nodes */}
            {graph.nodes.map(nd => (
              <g
                key={nd.id}
                transform={`translate(${nd.x},${nd.y})`}
                onMouseEnter={() => setHovered(nd.id)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}
              >
                <circle
                  r={nd.critical ? 18 : 13}
                  fill={nd.critical ? "#3C3489" : "#1f2937"}
                  stroke={nd.critical ? "#8479e4" : hovered === nd.id ? "#6b7280" : "#374151"}
                  strokeWidth={nd.critical ? 2 : 1.5}
                />
                {nd.pii && (
                  <text y={-22} textAnchor="middle" fontSize={9} fill="#f87171">PII</text>
                )}
                <text
                  textAnchor="middle"
                  y={nd.critical ? 36 : 28}
                  fontSize={10}
                  fill={nd.critical ? "#c4b5fd" : "#9ca3af"}
                  style={{ pointerEvents: "none" }}
                >
                  {nd.label.length > 16 ? nd.label.slice(0, 14) + "…" : nd.label}
                </text>
              </g>
            ))}
          </svg>
        ) : null}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-6 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#3C3489] border border-[#8479e4]" />
          Critical asset
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-gray-800 border border-gray-600" />
          Standard asset
        </div>
        <div className="flex items-center gap-2">
          <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="#fbbf24" strokeWidth="1.5" /></svg>
          Medium confidence
        </div>
        <div className="flex items-center gap-2">
          <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="#f87171" strokeWidth="2" strokeDasharray="6 3" /></svg>
          Low confidence (&lt;50%)
        </div>
      </div>
    </div>
  )
}
