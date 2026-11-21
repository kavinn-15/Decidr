"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Shield,
  FileText,
  AlertTriangle,
  Layers,
  Sparkles,
  Clock,
  CheckCircle2,
  Lock,
  GitBranch,
  RefreshCw,
  Users,
  Eye,
  Server,
  Zap,
  ChevronRight,
  Terminal,
} from "lucide-react";
import { isAuthenticated, getUser, AuthUser } from "@/lib/auth";
import { buildApiUrl } from "@/lib/config";

export default function LandingPage() {
  const [authedUser, setAuthedUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (isAuthenticated()) {
      setAuthedUser(getUser());
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#070B14] text-slate-100 selection:bg-cyan-500 selection:text-white font-sans antialiased overflow-x-hidden">
      {/* Background glow effects */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[20%] w-[500px] h-[500px] bg-cyan-600/10 rounded-full blur-[140px]" />
        <div className="absolute top-[30%] right-[10%] w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[160px]" />
        <div className="absolute bottom-[10%] left-[10%] w-[500px] h-[500px] bg-sky-600/10 rounded-full blur-[140px]" />
      </div>

      {/* ========================================================= */}
      {/* SECTION A: NAVIGATION */}
      {/* ========================================================= */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#070B14]/80 border-b border-slate-800/80">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-sky-500 to-blue-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
              D
            </div>
            <div>
              <span className="font-bold text-xl tracking-tight text-white flex items-center gap-1.5">
                Decidr
                <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-500/30">
                  Agent
                </span>
              </span>
              <p className="text-[11px] text-slate-400 font-medium">Decision Intelligence</p>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#how-it-works" className="hover:text-cyan-400 transition-colors">How It Works</a>
            <a href="#problem" className="hover:text-cyan-400 transition-colors">The Problem</a>
            <a href="#features" className="hover:text-cyan-400 transition-colors">Features</a>
            <a href="#security" className="hover:text-cyan-400 transition-colors">Security</a>
          </nav>

          <div className="flex items-center gap-4">
            {authedUser ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-sm shadow-lg shadow-cyan-500/25 hover:from-cyan-400 hover:to-blue-500 transition-all hover:scale-[1.02]"
              >
                Go to Dashboard
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-4 py-2 text-sm font-semibold text-slate-300 hover:text-white transition-colors"
                >
                  Log in
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold text-sm shadow-lg shadow-cyan-500/25 hover:from-cyan-400 hover:to-blue-500 transition-all hover:scale-[1.02]"
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ========================================================= */}
      {/* SECTION B: HERO */}
      {/* ========================================================= */}
      <section className="relative z-10 pt-20 pb-28 px-6 max-w-7xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-xs font-semibold uppercase tracking-wider mb-8 shadow-inner">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          Continuous Decision Intelligence & Premise Monitoring
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold text-white tracking-tight leading-[1.1] max-w-5xl mx-auto">
          Decisions don&apos;t fail. <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-500">
            Their assumptions do.
          </span>
        </h1>

        <p className="mt-8 text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto font-normal leading-relaxed">
          Decidr monitors the reasoning behind your team&apos;s decisions, detects when assumptions stop being true, and identifies the work that needs attention before another sprint is wasted.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/register"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-base shadow-xl shadow-cyan-500/30 hover:from-cyan-400 hover:to-blue-500 hover:scale-[1.02] transition-all"
          >
            Get Started Free
            <ArrowRight className="w-5 h-5" />
          </Link>
          <Link
            href="/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-slate-900/90 text-slate-200 border border-slate-700 font-semibold text-base hover:bg-slate-800 hover:text-white transition-all"
          >
            Explore Platform
          </Link>
        </div>

        {/* ========================================================= */}
        {/* FAITHFUL PRODUCT DASHBOARD PREVIEW */}
        {/* ========================================================= */}
        <div className="mt-16 rounded-2xl border border-slate-800 bg-[#0C1222]/90 shadow-2xl shadow-cyan-950/50 p-4 sm:p-6 text-left max-w-5xl mx-auto backdrop-blur-xl">
          {/* Mock Browser Header */}
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-4 mb-5">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500/80" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="ml-3 text-xs text-slate-400 font-mono">decidr.ai/affected?alert_id=102</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-500/30 font-medium flex items-center gap-1.5">
                <CheckCircle2 className="w-3 h-3" /> Invariant 2 Enforced (Zero Unapproved Writes)
              </span>
            </div>
          </div>

          {/* Active Premise Break Banner */}
          <div className="p-4 rounded-xl bg-red-950/30 border border-red-500/40 mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-red-500/20 text-red-400 flex items-center justify-center shrink-0 mt-0.5">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-red-400 uppercase tracking-wider">Premise Invalidation Detected</span>
                  <span className="text-xs text-slate-400">Meeting M2 &bull; Sam (00:04:22)</span>
                </div>
                <p className="text-sm font-semibold text-white mt-1">
                  Vendor A standard tier does NOT support international recurring billing
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Undermines Premise P1 behind Decision D1 (Payments Architecture Kickoff)
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="px-3 py-1.5 rounded-lg bg-red-950/80 text-red-300 border border-red-500/40 text-xs font-bold font-mono">
                42h + 8 pts Zombie Work
              </span>
            </div>
          </div>

          {/* Side-by-side Grounded Evidence Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-cyan-400" /> Original Assumption (Meeting M1)
              </p>
              <blockquote className="text-xs italic text-slate-300 border-l-2 border-cyan-500/60 pl-3 py-1">
                &ldquo;Vendor A supports international recurring payments right out of the box on their standard API tier.&rdquo;
              </blockquote>
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                <span>Cited in Decision D1</span>
                <span className="text-emerald-400 font-medium">Exact Substring Match</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" /> New Dialogue (Meeting M2)
              </p>
              <blockquote className="text-xs italic text-slate-300 border-l-2 border-red-500/60 pl-3 py-1">
                &ldquo;Vendor A informed us yesterday that recurring international billing requires their custom enterprise tier, which is unavailable until Q3.&rdquo;
              </blockquote>
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                <span>Sam &bull; Utterance #42</span>
                <span className="text-red-400 font-medium">Verdict: Undermines</span>
              </div>
            </div>
          </div>

          {/* Blast Radius & Repair Plan Preview */}
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Automated Repair Plan Formulated
              </p>
              <p className="text-xs text-slate-400 mt-1">
                3 Actions Prepared: Pause reminders for T1 & T2 &bull; Mark tickets at risk &bull; Notify owner (Ravi)
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-amber-400 font-medium">Requires Human Approval</span>
              <span className="px-4 py-2 rounded-lg bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 text-xs font-semibold">
                Preview Proposal
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION C: THE PROBLEM */}
      {/* ========================================================= */}
      <section id="problem" className="py-24 px-6 border-t border-slate-800/80 bg-[#090E1B]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center max-w-3xl mx-auto">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">The Core Vulnerability</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-3">
              The Silent Invalidation Crisis
            </h2>
            <p className="text-slate-300 mt-4 text-base sm:text-lg">
              Decisions rarely fail because the original choice was reckless. They fail because the hidden premises they were founded upon quietly stop being true weeks later.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="p-8 rounded-2xl bg-slate-900/40 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-red-500/10 text-red-400 flex items-center justify-center font-bold text-lg mb-6">
                  ✕
                </div>
                <h3 className="text-xl font-bold text-white">Traditional Meeting & Task Tools</h3>
                <p className="text-sm text-slate-400 mt-3 leading-relaxed">
                  Summarizers extract action items and dump bullet points into Slack or Jira. Once tickets are assigned, teams sprint forward blindly—even when a vendor API change or budget freeze in another meeting invalidated the entire project premise.
                </p>
              </div>
              <ul className="mt-6 space-y-2.5 text-xs text-slate-400 border-t border-slate-800 pt-6">
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Zero awareness of decision reasoning
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Zombie tasks continue burning sprint budget
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Failures discovered only at release deployment
                </li>
              </ul>
            </div>

            <div className="p-8 rounded-2xl bg-gradient-to-b from-cyan-950/20 to-blue-950/20 border border-cyan-500/30 flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-lg mb-6">
                  ✓
                </div>
                <h3 className="text-xl font-bold text-white">The Decidr Approach</h3>
                <p className="text-sm text-slate-300 mt-3 leading-relaxed">
                  Decidr binds foundational premises directly to decisions and downstream tasks. When dialogue in any future meeting challenges an assumption, Decidr detects the break, computes the affected blast radius, and prepares an actionable repair plan for human approval.
                </p>
              </div>
              <ul className="mt-6 space-y-2.5 text-xs text-cyan-200 border-t border-cyan-900/40 pt-6">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" /> Continuous background premise monitoring
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" /> Deterministic BFS dependency graph traversal
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" /> Zero unapproved external writes guaranteed
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION D: HOW IT WORKS */}
      {/* ========================================================= */}
      <section id="how-it-works" className="py-24 px-6 border-t border-slate-800/80 bg-[#070B14]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">The End-to-End Pipeline</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-3">
              How Decidr Protects Execution
            </h2>
            <p className="text-slate-300 mt-4 text-base">
              A 6-stage intelligent pipeline running from dialogue evidence to human-in-the-loop repair.
            </p>
          </div>

          <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                step: "01",
                title: "Import Meeting Transcripts",
                desc: "Ingests TXT, WebVTT, SRT subtitles, and JSON diarization. Automatically normalizes speaker identities against your company roster.",
                icon: FileText,
              },
              {
                step: "02",
                title: "Extract Decisions & Premises",
                desc: "Two-pass structured extraction: Pass 1 discovers decisions & tasks; Pass 2 isolates foundational premises backed by exact verbatim substring quotes.",
                icon: Layers,
              },
              {
                step: "03",
                title: "Continuous Premise Monitoring",
                desc: "A background watchdog listens across every future conversation, matching active premises against dialogue remarks without needing decision citations.",
                icon: Eye,
              },
              {
                step: "04",
                title: "Detect Quiet Invalidation",
                desc: "Four-verdict classification (supports, undermines, unrelated, uncertain). Ambiguous remarks surface reviewer confirmation cards; breaks alert instantly.",
                icon: AlertTriangle,
              },
              {
                step: "05",
                title: "Deterministic Impact Analysis",
                desc: "Pure application code graph traversal walks confirmed dependencies, isolates disjoint scopes (e.g. India vs Europe), and tallies wasted hours and story points.",
                icon: GitBranch,
              },
              {
                step: "06",
                title: "Human-Approved Repair Plan",
                desc: "Generates typed repair proposals: pause reminders, notify assignees, mark tickets at risk. Zero external writes occur until approved.",
                icon: Shield,
              },
            ].map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.step}
                  className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-cyan-500/40 transition-all hover:bg-slate-900/60 group"
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-mono font-bold text-cyan-400 px-2 py-1 rounded bg-cyan-950/60 border border-cyan-500/30">
                      STEP {card.step}
                    </span>
                    <Icon className="w-5 h-5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                  </div>
                  <h3 className="text-base font-bold text-white group-hover:text-cyan-300 transition-colors">
                    {card.title}
                  </h3>
                  <p className="text-xs text-slate-400 mt-2.5 leading-relaxed">
                    {card.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION E: CORE FEATURES */}
      {/* ========================================================= */}
      <section id="features" className="py-24 px-6 border-t border-slate-800/80 bg-[#090E1B]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Platform Capabilities</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-3">
              Engineered for Enterprise Safety
            </h2>
            <p className="text-slate-300 mt-4 text-base">
              Decidr is built on immutable software invariants, not fragile chatbot prompts.
            </p>
          </div>

          <div className="mt-16 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[
              {
                title: "AI Decision Extraction",
                desc: "Two-pass pipeline discovering commitments and work items with confidence scores and timestamps.",
                badge: "2-Pass",
              },
              {
                title: "Evidence-Backed Premises",
                desc: "Every premise links to an exact verbatim transcript quote. Hallucinated quotes are dropped and logged.",
                badge: "Invariant 6",
              },
              {
                title: "Silent Invalidation Detection",
                desc: "Catches premise contradictions in later meetings even when the speaker never mentions the original decision.",
                badge: "Watchdog",
              },
              {
                title: "Premise Expiry Monitoring",
                desc: "Tracks sandbox tokens, temporary waivers, and date-bounded assumptions that expire with simulated time.",
                badge: "Temporal",
              },
              {
                title: "Deterministic Impact Analysis",
                desc: "BFS graph traversal handles circular links, deduplicates tasks, and isolates disjoint project regions.",
                badge: "Pure Code",
              },
              {
                title: "Zombie-Work Cost Quantification",
                desc: "Calculates engineering hours and sprint story points at risk without guessing missing estimates.",
                badge: "Invariant 10",
              },
              {
                title: "Human-Approved Repair",
                desc: "Changes execute only upon approval. Double-clicks are protected with SHA-256 idempotency.",
                badge: "Invariant 2 & 3",
              },
              {
                title: "Append-Only Audit Logging",
                desc: "Every state transition writes an immutable audit row with actor, before/after states, and CSV export.",
                badge: "Invariant 7",
              },
            ].map((feat, idx) => (
              <div
                key={idx}
                className="p-5 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-slate-700 transition-all"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] uppercase font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/20">
                    {feat.badge}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">{feat.title}</h4>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION F: SECURITY */}
      {/* ========================================================= */}
      <section id="security" className="py-24 px-6 border-t border-slate-800/80 bg-[#070B14]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center max-w-2xl mx-auto">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Enterprise Governance</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white mt-3">
              Zero Unapproved External Writes
            </h2>
            <p className="text-slate-300 mt-4 text-base">
              Security is not a feature toggle in Decidr; it is an architectural invariant.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Multi-Tenant User & Project Isolation</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                  Every project has an authorized owner or membership relationship. API endpoints enforce authorization on the backend: User A cannot view User B&apos;s transcripts, decisions, or approve User B&apos;s repairs.
                </p>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center shrink-0">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Approval-Gated External Integrations</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                  Proposals in draft or rejected states produce zero calls to issue trackers, SMTP, or Slack. Every external action carries a unique SHA-256 idempotency key: double-clicks create zero duplicate tickets.
                </p>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Evidence Traceability (Invariant 6)</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                  Every extracted decision, task, and premise is validated against the raw transcript text. If an LLM fabricates a quote, the quote verification engine immediately drops it and logs the anomaly.
                </p>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center shrink-0">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">GDPR Article 17 Right-to-Erasure</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                  Endpoint <code className="text-cyan-400 bg-slate-800 px-1 py-0.5 rounded font-mono text-[11px]">DELETE /meetings/&#123;id&#125;</code> securely purges raw transcripts, audio, and derived items, keeping only an append-only non-content audit record.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION G: FINAL CTA */}
      {/* ========================================================= */}
      <section className="py-24 px-6 border-t border-slate-800/80 bg-gradient-to-b from-[#070B14] to-[#0A1020] text-center relative">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
            Stop working on decisions that no longer make sense.
          </h2>
          <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl mx-auto">
            Give your engineering and product teams continuous assumption monitoring and prevent wasted sprint cycles.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-base shadow-xl shadow-cyan-500/25 hover:from-cyan-400 hover:to-blue-500 transition-all hover:scale-[1.02]"
            >
              Get Started with Decidr
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-slate-900 border border-slate-700 text-slate-200 font-semibold text-base hover:bg-slate-800 hover:text-white transition-all"
            >
              Explore Live Demo
            </Link>
          </div>
        </div>
      </section>

      {/* ========================================================= */}
      {/* SECTION H: FOOTER */}
      {/* ========================================================= */}
      <footer className="border-t border-slate-800/80 bg-[#050811] py-14 px-6 text-sm text-slate-400">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white font-bold text-sm">
                D
              </div>
              <span className="font-bold text-base text-white">Decidr</span>
            </div>
            <p className="text-xs text-slate-500 mt-3 leading-relaxed">
              Decisions don&apos;t fail. Their assumptions do.
              Continuous decision intelligence and premise monitoring for modern engineering organizations.
            </p>
          </div>

          <div>
            <h5 className="font-semibold text-white text-xs uppercase tracking-wider mb-3">Product</h5>
            <ul className="space-y-2 text-xs">
              <li><Link href="/dashboard" className="hover:text-cyan-400 transition-colors">Meeting Hub</Link></li>
              <li><Link href="/review" className="hover:text-cyan-400 transition-colors">Review Queue</Link></li>
              <li><Link href="/affected" className="hover:text-cyan-400 transition-colors">Affected Work</Link></li>
              <li><Link href="/ledger" className="hover:text-cyan-400 transition-colors">Decision Ledger</Link></li>
              <li><Link href="/my-week" className="hover:text-cyan-400 transition-colors">My Week</Link></li>
              <li><Link href="/eval" className="hover:text-cyan-400 transition-colors">Evaluation Harness</Link></li>
            </ul>
          </div>

          <div>
            <h5 className="font-semibold text-white text-xs uppercase tracking-wider mb-3">Documentation</h5>
            <ul className="space-y-2 text-xs">
              <li><a href="#how-it-works" className="hover:text-cyan-400 transition-colors">Architecture Overview</a></li>
              <li><a href="#security" className="hover:text-cyan-400 transition-colors">Security Invariants</a></li>
              <li><Link href="/audit" className="hover:text-cyan-400 transition-colors">Audit Trail</Link></li>
              <li><a href={buildApiUrl("/docs")} target="_blank" rel="noopener noreferrer" className="hover:text-cyan-400 transition-colors">FastAPI Swagger Docs</a></li>
            </ul>
          </div>

          <div>
            <h5 className="font-semibold text-white text-xs uppercase tracking-wider mb-3">Governance</h5>
            <ul className="space-y-2 text-xs">
              <li><span className="text-slate-400">GDPR Article 17 Compliant</span></li>
              <li><span className="text-slate-400">NIST SP 800-132 PBKDF2</span></li>
              <li><span className="text-slate-400">Zero Unapproved Writes</span></li>
              <li><span className="text-slate-500">&copy; 2026 Decidr Inc. All rights reserved.</span></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}
