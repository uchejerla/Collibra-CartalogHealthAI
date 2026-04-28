export default function LandingPage() {
  return (
    <div style={{marginLeft:0}} className="min-h-screen bg-gray-950 text-white -ml-8 -mt-8 -mr-8">
      <nav className="border-b border-gray-800 px-8 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <div><div className="text-brand-100 text-[10px] font-semibold tracking-widest uppercase">Catalog Health</div><div className="text-white font-semibold text-sm">AI</div></div>
        <div className="flex items-center gap-6 text-sm">
          <a href="#features" className="text-gray-400 hover:text-white">Features</a>
          <a href="#pricing" className="text-gray-400 hover:text-white">Pricing</a>
          <a href="/" className="px-4 py-2 bg-brand-600 hover:bg-brand-700 rounded-lg font-medium">Dashboard</a>
        </div>
      </nav>
      <section className="max-w-4xl mx-auto px-8 py-24 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-600/20 border border-brand-600/40 text-brand-100 text-xs font-medium mb-8">✦ Built for Collibra customers</div>
        <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">Your Collibra is installed.<br/><span className="text-brand-400">We make it work.</span></h1>
        <p className="text-gray-400 text-xl mb-10 max-w-2xl mx-auto leading-relaxed">24/7 AI agents that detect metadata decay, broken lineage, and governance gaps—automatically.</p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a href="#upload" className="px-8 py-4 bg-brand-600 hover:bg-brand-700 rounded-xl font-semibold text-lg">Get Free Collibra Health Assessment →</a>
          <a href="/" className="px-8 py-4 border border-gray-700 hover:border-gray-500 rounded-xl font-medium text-gray-300">View Demo Dashboard</a>
        </div>
        <p className="text-gray-600 text-sm mt-4">Upload your Collibra export · Receive your governance health report in 24 hours</p>
      </section>
      <section id="features" className="max-w-5xl mx-auto px-8 py-16">
        <h2 className="text-2xl font-semibold text-center mb-12 text-gray-200">Four AI agents. One mission.</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[["📋","Metadata Curator","Detects missing descriptions, stale assets, wrong ownership and duplicates.","bg-purple-900/30 border-purple-700/40"],["⇌","Lineage Guardian","Traverses your lineage graph to find broken paths, orphan nodes and low-confidence edges.","bg-teal-900/30 border-teal-700/40"],["⚖","Governance Gap","Checks your operating model: every CDE has an owner, every KPI has lineage, every PII asset is classified.","bg-amber-900/30 border-amber-700/40"],["📊","Executive Risk","Aggregates all findings into a health score, audit readiness score and board-ready risk briefing.","bg-blue-900/30 border-blue-700/40"]].map(([icon,name,desc,cls])=>(
            <div key={name as string} className={`border rounded-xl p-6 ${cls as string}`}><div className="text-2xl mb-3">{icon as string}</div><h3 className="text-white font-semibold mb-2">{name as string} Agent</h3><p className="text-gray-300 text-sm leading-relaxed">{desc as string}</p></div>
          ))}
        </div>
      </section>
      <section id="pricing" className="max-w-4xl mx-auto px-8 py-16">
        <h2 className="text-2xl font-semibold text-center mb-12 text-gray-200">Simple pricing. Serious ROI.</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[{tier:"Starter",price:"$60k/yr",features:["5,000 assets","4 AI agents","Weekly reports"],hi:false},{tier:"Growth",price:"$150k/yr",features:["25,000 assets","Trend analysis","Slack alerts"],hi:true},{tier:"Enterprise",price:"Custom",features:["Unlimited assets","API access","SLA + support"],hi:false}].map(p=>(
            <div key={p.tier} className={`rounded-xl p-6 border ${p.hi?"bg-brand-700 border-brand-500":"bg-gray-900 border-gray-800"}`}>
              <div className="text-sm font-semibold text-gray-300 mb-2">{p.tier}</div>
              <div className="text-2xl font-bold text-white mb-4">{p.price}</div>
              <ul className="space-y-2 mb-6">{p.features.map(f=><li key={f} className="text-sm text-gray-300 flex gap-2"><span className="text-emerald-400">✓</span>{f}</li>)}</ul>
              <a href="#upload" className={`block text-center py-2.5 rounded-lg text-sm font-medium ${p.hi?"bg-white text-brand-700":"border border-gray-700 text-gray-300"}`}>Get started</a>
            </div>
          ))}
        </div>
        <p className="text-center text-gray-500 text-sm mt-6">🎯 Pilot offer: $5,000 for 30 days · No commitment</p>
      </section>
      <section id="upload" className="max-w-xl mx-auto px-8 py-16 text-center">
        <h2 className="text-3xl font-bold mb-4">Get your free Collibra health report</h2>
        <p className="text-gray-400 mb-8">Upload your Collibra assets CSV. We'll run all 4 agents and deliver your governance health report within 24 hours.</p>
        <div className="bg-gray-900 border border-dashed border-gray-600 rounded-xl p-10 mb-6 hover:border-brand-600 cursor-pointer">
          <div className="text-4xl mb-3">📤</div>
          <p className="text-gray-300 font-medium mb-1">Drop your Collibra export CSV here</p>
          <p className="text-gray-500 text-sm">assets.csv · lineage.csv</p>
        </div>
        <button className="w-full py-4 bg-brand-600 hover:bg-brand-700 rounded-xl font-semibold text-lg">Upload &amp; Get Free Health Report</button>
        <p className="text-gray-600 text-xs mt-3">No credit card · No account required · Results in 24h</p>
      </section>
      <footer className="border-t border-gray-800 py-8 text-center text-gray-600 text-sm">Catalog Health AI · Built for Collibra customers · Not affiliated with Collibra Inc.</footer>
    </div>
  )
}
