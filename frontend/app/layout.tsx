import type { Metadata } from "next";
import "./globals.css";
import { AppLayoutShell } from "@/components/app-layout-shell";

export const metadata: Metadata = {
  title: "Decidr — Decisions don't fail. Their assumptions do.",
  description: "AI-powered decision intelligence platform that monitors the reasoning behind team decisions and prevents zombie work.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased font-sans">
        <AppLayoutShell>{children}</AppLayoutShell>
      </body>
    </html>
  );
}
