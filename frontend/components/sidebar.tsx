"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Video, 
  CheckSquare, 
  AlertTriangle, 
  Layers, 
  CalendarCheck2, 
  ShieldCheck,
  BarChart3
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Meetings", icon: Video },
  { href: "/review", label: "Review Queue", icon: CheckSquare },
  { href: "/affected", label: "Affected Work", icon: AlertTriangle },
  { href: "/ledger", label: "Decision Ledger", icon: Layers },
  { href: "/my-week", label: "My Week", icon: CalendarCheck2 },
  { href: "/audit", label: "Audit Log", icon: ShieldCheck },
  { href: "/eval", label: "Evaluation", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50 flex flex-col h-screen fixed left-0 top-0 text-slate-800">
      <div className="h-16 flex items-center px-6 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
            D
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight tracking-tight text-slate-900">Decidr</h1>
            <p className="text-xs text-slate-500 font-medium">ChangeGuard Agent</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-50 text-indigo-700 shadow-sm border border-indigo-100/60"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
            >
              <Icon className={cn("w-4 h-4", isActive ? "text-indigo-600" : "text-slate-500")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-200 text-xs text-slate-500 space-y-1">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-600">Execution Safety</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium text-[10px]">Active</span>
        </div>
        <p className="text-[11px] text-slate-400">Zero writes without human approval</p>
      </div>
    </aside>
  );
}
