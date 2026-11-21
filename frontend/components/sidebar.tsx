"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  Video, 
  CheckSquare, 
  AlertTriangle, 
  Layers, 
  CalendarCheck2, 
  ShieldCheck,
  BarChart3,
  LogOut,
  User as UserIcon,
  Globe,
  Ticket
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getUser, clearAuth, AuthUser } from "@/lib/auth";
import { logoutUser } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Meetings", icon: Video },
  { href: "/review", label: "Review Queue", icon: CheckSquare },
  { href: "/affected", label: "Affected Work", icon: AlertTriangle },
  { href: "/ledger", label: "Decision Ledger", icon: Layers },
  { href: "/my-week", label: "My Week", icon: CalendarCheck2 },
  { href: "/mock-tracker", label: "Issue Tracker", icon: Ticket },
  { href: "/audit", label: "Audit Log", icon: ShieldCheck },
  { href: "/eval", label: "Evaluation", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUserState] = useState<AuthUser | null>(null);

  useEffect(() => {
    setUserState(getUser());
  }, []);

  const handleLogout = async () => {
    await logoutUser();
    clearAuth();
    router.push("/login");
  };

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50 flex flex-col h-screen fixed left-0 top-0 text-slate-800 z-40">
      <div className="h-16 flex items-center justify-between px-6 border-b border-slate-200 bg-white">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
            D
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight tracking-tight text-slate-900">Decidr</h1>
            <p className="text-[11px] text-cyan-600 font-medium">ChangeGuard Agent</p>
          </div>
        </Link>
        <Link
          href="/"
          title="View Landing Page"
          className="text-slate-400 hover:text-slate-700 p-1 rounded-md transition-colors"
        >
          <Globe className="w-4 h-4" />
        </Link>
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
                  ? "bg-cyan-50 text-cyan-800 shadow-sm border border-cyan-200/60"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              )}
            >
              <Icon className={cn("w-4 h-4", isActive ? "text-cyan-600" : "text-slate-500")} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Safety Badge */}
      <div className="px-4 py-2 border-t border-slate-200 bg-slate-100/50 text-xs text-slate-500">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-700">Safety Guard</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium text-[10px]">Active</span>
        </div>
        <p className="text-[10px] text-slate-400 mt-0.5">Zero unapproved external writes</p>
      </div>

      {/* User Profile & Sign Out Footer */}
      <div className="p-3 border-t border-slate-200 bg-white flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600 shrink-0">
            <UserIcon className="w-4 h-4 text-slate-500" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-900 truncate">
              {user?.full_name || "Active Session"}
            </p>
            <p className="text-[10px] text-slate-500 truncate">
              {user?.email || "demo@decidr.ai"}
            </p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          title="Sign Out"
          className="p-1.5 rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
