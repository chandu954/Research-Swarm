import Link from "next/link";
import {
  ArrowRight,
  Bot,
  Check,
  Database,
  FileSearch,
  Github,
  Globe2,
  Layers3,
  Search,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

const capabilities = [
  {
    icon: Globe2,
    title: "Live web research",
    description:
      "Search, compare, and synthesize current information with traceable sources.",
    accent: "cyan",
  },
  {
    icon: FileSearch,
    title: "Document intelligence",
    description:
      "Upload PDFs and retrieve the most relevant evidence with a local RAG pipeline.",
    accent: "emerald",
  },
  {
    icon: Layers3,
    title: "Multi-agent reasoning",
    description:
      "A planner coordinates research, document, and answer agents through LangGraph.",
    accent: "violet",
  },
] as const;

const workflow = [
  { label: "Plan research", time: "52ms", color: "violet" },
  { label: "Search sources", time: "2.1s", color: "cyan" },
  { label: "Retrieve evidence", time: "640ms", color: "emerald" },
  { label: "Synthesize answer", time: "3.4s", color: "orange" },
] as const;

const stack = [
  { label: "LangGraph", icon: Bot },
  { label: "FastAPI", icon: Zap },
  { label: "ChromaDB", icon: Database },
  { label: "Ollama", icon: Sparkles },
] as const;

export default function LandingPage() {
  return (
    <main className="landing-shell min-h-screen overflow-hidden">
      <div className="landing-grid" aria-hidden="true" />
      <div className="landing-glow landing-glow-left" aria-hidden="true" />
      <div className="landing-glow landing-glow-right" aria-hidden="true" />

      <nav className="relative z-10 mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-3">
          <span className="brand-mark">
            <Sparkles className="h-5 w-5" />
          </span>
          <span className="text-sm font-semibold tracking-tight text-white">
            ResearchSwarm
          </span>
          <span className="hidden rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] font-medium text-slate-400 sm:inline">
            LOCAL AI
          </span>
        </Link>

        <div className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
          <a href="#platform" className="transition-colors hover:text-white">
            Platform
          </a>
          <a href="#workflow" className="transition-colors hover:text-white">
            Workflow
          </a>
          <a href="#architecture" className="transition-colors hover:text-white">
            Architecture
          </a>
        </div>

        <Link href="/app" className="nav-launch">
          Open workspace
          <ArrowRight className="h-4 w-4" />
        </Link>
      </nav>

      <section className="relative z-10 mx-auto max-w-7xl px-5 pb-20 pt-20 text-center sm:px-8 sm:pt-28">
        <div className="hero-badge">
          <span className="status-pulse" />
          Powered by LangGraph + Ollama
        </div>

        <h1 className="mx-auto mt-7 max-w-5xl text-balance text-5xl font-semibold leading-[1.02] tracking-[-0.055em] text-white sm:text-7xl lg:text-[88px]">
          Research at the speed of
          <span className="hero-gradient block">a coordinated swarm.</span>
        </h1>
        <p className="mx-auto mt-7 max-w-2xl text-balance text-base leading-7 text-slate-400 sm:text-lg">
          A local-first research workspace that plans complex questions, searches
          the web, understands your PDFs, and returns cited answers you can trust.
        </p>

        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/app" className="hero-primary">
            Start researching
            <ArrowRight className="h-4 w-4" />
          </Link>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="hero-secondary"
          >
            <Github className="h-4 w-4" />
            View source
          </a>
        </div>

        <div className="mt-7 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-slate-500">
          {["Runs locally", "No API key required", "Open-source models"].map(
            (item) => (
              <span key={item} className="flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                {item}
              </span>
            ),
          )}
        </div>
      </section>

      <section
        id="workflow"
        className="relative z-10 mx-auto max-w-6xl px-5 pb-28 sm:px-8"
      >
        <div className="product-window">
          <div className="product-window-bar">
            <div className="flex gap-1.5">
              <span className="window-dot bg-rose-400/70" />
              <span className="window-dot bg-amber-300/70" />
              <span className="window-dot bg-emerald-400/70" />
            </div>
            <div className="flex items-center gap-2 rounded-md border border-white/[0.06] bg-black/20 px-4 py-1.5 text-[10px] text-slate-500">
              <ShieldCheck className="h-3 w-3 text-emerald-400" />
              localhost / research
            </div>
            <div className="h-3 w-12" />
          </div>

          <div className="grid min-h-[480px] lg:grid-cols-[220px_1fr_290px]">
            <aside className="hidden border-r border-white/[0.06] p-5 text-left lg:block">
              <div className="mb-7 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/15 text-violet-300">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <span className="text-xs font-semibold text-slate-200">
                  ResearchSwarm
                </span>
              </div>
              <button className="w-full rounded-lg bg-white/[0.06] px-3 py-2.5 text-left text-xs text-slate-200">
                + &nbsp; New research
              </button>
              <p className="mb-3 mt-7 text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Recent
              </p>
              {["AI agent frameworks", "RAG architecture", "Local LLM stack"].map(
                (item) => (
                  <p
                    key={item}
                    className="truncate rounded-lg px-2 py-2 text-[11px] text-slate-500"
                  >
                    {item}
                  </p>
                ),
              )}
            </aside>

            <div className="flex flex-col justify-between p-7 text-left sm:p-10">
              <div>
                <div className="mb-12 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium text-slate-200">
                      New research
                    </p>
                    <p className="mt-1 text-[10px] text-slate-600">
                      Multi-agent workspace
                    </p>
                  </div>
                  <span className="connected-badge">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    Ollama connected
                  </span>
                </div>
                <div className="mx-auto max-w-lg py-8 text-center">
                  <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-300">
                    <Search className="h-5 w-5" />
                  </span>
                  <h2 className="mt-5 text-xl font-semibold text-white">
                    What do you want to research?
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    Ask a complex question or bring your own evidence.
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.035] p-3 shadow-2xl shadow-black/20">
                <p className="px-2 pb-7 pt-2 text-sm text-slate-500">
                  Compare the leading frameworks for building AI agents...
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    <span className="demo-chip">Web</span>
                    <span className="demo-chip">Deep research</span>
                  </div>
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500 text-white">
                    <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </div>
            </div>

            <aside className="border-t border-white/[0.06] bg-black/10 p-6 text-left lg:border-l lg:border-t-0">
              <div className="mb-5 flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-200">AI workflow</p>
                <span className="text-[9px] text-emerald-400">Complete</span>
              </div>
              <div>
                {workflow.map((item, index) => (
                  <div key={item.label} className="relative flex gap-3 pb-6 last:pb-0">
                    {index < workflow.length - 1 && (
                      <span className="absolute left-[11px] top-6 h-full w-px bg-white/[0.07]" />
                    )}
                    <span
                      className={`workflow-check workflow-check-${item.color}`}
                    >
                      <Check className="h-3 w-3" />
                    </span>
                    <div className="flex flex-1 items-center justify-between pt-0.5">
                      <div>
                        <p className="text-[11px] font-medium text-slate-300">
                          {item.label}
                        </p>
                        <p className="mt-1 text-[9px] text-slate-600">
                          Agent completed
                        </p>
                      </div>
                      <span className="font-mono text-[9px] text-slate-600">
                        {item.time}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-7 grid grid-cols-2 gap-2">
                <div className="metric-tile">
                  <span>Sources</span>
                  <strong>12</strong>
                </div>
                <div className="metric-tile">
                  <span>Execution</span>
                  <strong>6.2s</strong>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>

      <section
        id="platform"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-28 sm:px-8"
      >
        <div className="mb-10 max-w-2xl">
          <p className="section-kicker">BUILT FOR DEEP WORK</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Every research tool, one focused workspace.
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {capabilities.map(({ icon: Icon, title, description, accent }) => (
            <article key={title} className="feature-card">
              <span className={`feature-icon feature-icon-${accent}`}>
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-8 text-lg font-medium text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-500">
                {description}
              </p>
              <div className="mt-8 flex items-center gap-2 text-xs text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Ready locally
              </div>
            </article>
          ))}
        </div>
      </section>

      <section
        id="architecture"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-24 sm:px-8"
      >
        <div className="architecture-strip">
          <div>
            <p className="section-kicker">OPEN ARCHITECTURE</p>
            <h2 className="mt-3 text-2xl font-semibold text-white">
              Serious engineering behind a calm interface.
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {stack.map(({ label, icon: Icon }) => (
              <span key={label} className="stack-pill">
                <Icon className="h-3.5 w-3.5" />
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.06] px-5 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 text-xs text-slate-600 sm:flex-row">
          <span>ResearchSwarm AI · Multi-agent research platform</span>
          <span>Built with local models and open tools.</span>
        </div>
      </footer>
    </main>
  );
}
