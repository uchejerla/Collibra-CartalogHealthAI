"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"

const NAV = [
  { href: "/",               label: "Overview",        icon: "◈" },
  { href: "/issues",         label: "Issues",          icon: "⚠" },
  { href: "/lineage",        label: "Lineage",         icon: "⬡" },
  { href: "/recommendations",label: "Recommendations", icon: "✦" },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#3C3489] flex items-center justify-center text-white text-xs font-bold">
            CΗ
          </div>
          <div>
            <p className="text-white text-sm font-semibold leading-none">Catalog Health</p>
            <p className="text-gray-500 text-[10px] mt-0.5">AI Governance</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-[#3C3489]/30 text-white border border-[#3C3489]/50"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <span className={`text-base ${active ? "text-[#8479e4]" : "text-gray-600"}`}>{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800">
        <Link
          href="/landing"
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          ↗ About
        </Link>
      </div>
    </aside>
  )
}
