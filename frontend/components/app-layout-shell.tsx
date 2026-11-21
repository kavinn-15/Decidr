"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { isAuthenticated } from "@/lib/auth";

export function AppLayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Routes that do not require authentication or application sidebar
  const isPublicRoute =
    pathname === "/" ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/forgot-password");

  useEffect(() => {
    if (!isPublicRoute) {
      if (!isAuthenticated()) {
        const redirectParam = encodeURIComponent(pathname);
        router.push(`/login?redirect=${redirectParam}`);
        return;
      }
    }
    setIsCheckingAuth(false);
  }, [pathname, isPublicRoute, router]);

  // If public/auth route, render children directly without app sidebar
  if (isPublicRoute) {
    return <>{children}</>;
  }

  // If checking authentication on protected route, show a minimal loading spinner
  if (isCheckingAuth) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-400">Verifying session...</p>
        </div>
      </div>
    );
  }

  // Authenticated application dashboard layout
  return (
    <div className="flex min-h-screen bg-slate-100/50 antialiased font-sans">
      <Sidebar />
      <main className="flex-1 ml-64 p-8">
        <div className="max-w-6xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
