import Link from "next/link";
import {
  ArrowRight,
  Check,
  Github,
  Laptop2,
  Link2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import HeroPreview from "@/components/landing/HeroPreview";
import ResearchExamples from "@/components/landing/ResearchExamples";
import LandingBackground from "@/components/landing/LandingBackground";
import ArchitectureFlow from "@/components/landing/ArchitectureFlow";

const GITHUB_URL = "https://github.com/chandu954/Research-Swarm";

const trustItems = [
  { icon: Laptop2, label: "Runs locally" },
  { icon: Link2, label: "Citations included" },
  { icon: Github, label: "Open source" },
  { icon: ShieldCheck, label: "No cloud required" },
  { icon: Sparkles, label: "Ollama compatible" },
] as const;

const workflowSteps = [
  { num: "01", title: "Planner", detail: "Breaks the question into search and retrieval steps.", color: "violet" },
  { num: "02", title: "Web search", detail: "Queries 18+ sources and extracts claims.", color: "cyan" },
  { num: "03", title: "Document retrieval", detail: "Reads your PDFs with local RAG.", color: "emerald" },
  { num: "04", title: "Evidence verification", detail: "Drops weak and duplicate claims.", color: "orange" },
  { num: "05", title: "Answer synthesis", detail: "Writes the report with numbered citations.", color: "violet" },
  { num: "06", title: "Final report", detail: "Export to Markdown or PDF.", color: "emerald" },
] as const;

export default function LandingPage() {
  return (
    <main className="landing-shell min-h-screen overflow-hidden">
      <LandingBackground />

      <nav className="relative z-10 mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-3">
          <span className="brand-mark">
            <Sparkles className="h-5 w-5" />
          </span>
          <span className="text-sm font-semibold tracking-tight text-white">
            ResearchSwarm
          </span>
          <span className="hidden rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] font-medium text-slate-400 sm:inline">
            LOCAL · OPEN
          </span>
        </Link>

        <div className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
          <a href="#examples" className="transition-colors hover:text-white">
            Examples
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

      <section className="relative z-10 mx-auto max-w-7xl px-5 pb-24 pt-16 sm:px-8 lg:pt-24">
        <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-10">
          <div className="max-w-xl">
            <div className="hero-badge">
              <span className="status-pulse" />
              LangGraph multi-agent research
            </div>

            <h1 className="mt-6 max-w-md text-balance text-[40px] font-semibold leading-[1.05] tracking-[-0.045em] text-white sm:text-5xl lg:text-[58px]">
              Turn hours of research into one cited report.
            </h1>
            <p className="mt-6 max-w-lg text-balance text-base leading-7 text-slate-400 sm:text-lg">
              Ask a question. ResearchSwarm plans it, searches the web and your
              PDFs, ranks the evidence, and writes the answer — with every
              source linked.
            </p>

            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link href="/app" className="hero-primary">
                Start researching
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className="hero-secondary"
              >
                <Github className="h-4 w-4" />
                View source
              </a>
            </div>

            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2.5">
              {trustItems.map(({ icon: Icon, label }) => (
                <span key={label} className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Icon className="h-3.5 w-3.5 text-emerald-400" />
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="preview-glow" aria-hidden="true" />
            <HeroPreview />
          </div>
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-7xl px-5 pb-14 sm:px-8">
        <div className="credibility-strip">
          <span className="credibility-item">
            <Check className="h-3 w-3 text-emerald-400" />
            MIT-licensed open source
          </span>
          <span className="credibility-item">
            <Check className="h-3 w-3 text-emerald-400" />
            LangGraph · FastAPI · Ollama
          </span>
          <span className="credibility-item">
            <Check className="h-3 w-3 text-emerald-400" />
            Runs on macOS · Linux · Windows
          </span>
        </div>
      </section>

      <section
        id="examples"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-28 sm:px-8"
      >
        <div className="mb-12 max-w-2xl">
          <p className="section-kicker">REAL RUNS</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            What a research run looks like.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">
            Open a report to see the answer structure and the sources behind it.
          </p>
        </div>

        <ResearchExamples />
      </section>

      <section
        id="workflow"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-16 sm:px-8"
      >
        <div className="mb-12 max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Six agents, one pipeline.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">
            Each step is a dedicated agent. You see the plan, the progress, and
            the evidence — not just the final answer.
          </p>
        </div>

        <ol className="relative mx-auto max-w-2xl">
          <span
            className="absolute bottom-4 left-[22px] top-5 w-px bg-gradient-to-b from-violet-500/40 via-white/10 to-emerald-400/40"
            aria-hidden="true"
          />
          {workflowSteps.map(({ num, title, detail, color }) => (
            <li key={num} className="relative flex gap-5 pb-7 last:pb-0">
              <span className={`workflow-node workflow-node-${color}`}>{num}</span>
              <div className="pt-1">
                <h3 className="text-[15px] font-medium text-white">{title}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-400">{detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section
        id="features"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-28 sm:px-8"
      >
        <div className="mb-12 max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Built for people who care about evidence.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">
            Good research shouldn&apos;t require 40 browser tabs.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-6">
          <article className="feature-card lg:col-span-4">
            <p className="feature-label">SEARCH EVERYTHING</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              The web, your PDFs, and local files — one request.
            </h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
              No switching tools. Bring your documents and search the web in the
              same run.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {["18 websites", "5 PDFs", "Markdown", "Local files"].map((chip) => (
                <span key={chip} className="feature-chip">{chip}</span>
              ))}
            </div>
          </article>

          <article className="feature-card feature-card-tall lg:col-span-2">
            <p className="feature-label">RUNS LOCALLY</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              No API keys. No cloud.
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Ollama and open-source models. Your data never leaves the machine.
            </p>
          </article>

          <article className="feature-card lg:col-span-2">
            <p className="feature-label">EVIDENCE FIRST</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              Every claim links back.
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Verify any statement in one click.
            </p>
          </article>

          <article className="feature-card lg:col-span-4">
            <p className="feature-label">AUTONOMOUS RESEARCH</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              Plan → Search → Verify → Write.
            </h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
              The pipeline runs itself. You review the evidence, not the process.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              {["Plan", "Search", "Verify", "Write"].map((step, i, arr) => (
                <span key={step} className="flex items-center gap-2">
                  <span className="feature-chip feature-chip-step">{step}</span>
                  {i < arr.length - 1 && (
                    <ArrowRight className="h-3 w-3 text-slate-600" />
                  )}
                </span>
              ))}
            </div>
          </article>

          <article className="feature-card lg:col-span-3">
            <p className="feature-label">EXPORT REPORTS</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              Markdown or PDF.
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Structured reports with citations, ready to share.
            </p>
          </article>

          <article className="feature-card lg:col-span-3">
            <p className="feature-label">OPEN SOURCE</p>
            <h3 className="mt-3 text-lg font-medium text-white">
              Read it. Run it. Extend it.
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              A plugin registry for tools, providers, and search backends.
            </p>
          </article>
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-7xl px-5 pb-16 sm:px-8">
        <div className="why-panel">
          <h2 className="max-w-3xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Most AI tools return answers.
            <br />
            <span className="text-slate-400">ResearchSwarm shows the work.</span>
          </h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              ["Every claim is linked", "to a numbered source."],
              ["Every source is visible", "in the final report."],
              ["Every step is inspectable", "in the execution timeline."],
            ].map(([head, tail]) => (
              <div key={head} className="why-item">
                <Check className="h-4 w-4 shrink-0 text-emerald-400" />
                <p className="text-sm leading-6 text-slate-400">
                  <span className="text-slate-200">{head}</span> {tail}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-12 text-balance text-lg text-slate-400 sm:text-xl">
            Research shouldn&apos;t be a black box.
          </p>
        </div>
      </section>

      <section
        id="architecture"
        className="relative z-10 mx-auto max-w-7xl px-5 pb-28 sm:px-8"
      >
        <div className="mb-12 max-w-2xl">
          <p className="section-kicker">OPEN ARCHITECTURE</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            LangGraph orchestration, visible end to end.
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">
            Every node records its latency, model, and results.
          </p>
        </div>

        <ArchitectureFlow />
      </section>

      <section className="relative z-10 mx-auto max-w-7xl px-5 pb-28 sm:px-8">
        <div className="final-cta">
          <div className="landing-glow landing-glow-cta" aria-hidden="true" />
          <h2 className="relative text-balance text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Start your first cited research report in under a minute.
          </h2>
          <p className="relative mt-4 max-w-xl text-sm leading-7 text-slate-400 sm:text-base">
            No cloud. No API keys. No walls between search and your files.
          </p>
          <div className="relative mt-9 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/app" className="hero-primary">
              Start researching
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="hero-secondary"
            >
              <Github className="h-4 w-4" />
              Star on GitHub
            </a>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.06] px-5 py-12">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            <div className="lg:col-span-1">
              <div className="flex items-center gap-3">
                <span className="brand-mark">
                  <Sparkles className="h-5 w-5" />
                </span>
                <span className="text-sm font-semibold tracking-tight text-white">
                  ResearchSwarm
                </span>
              </div>
              <p className="mt-4 max-w-xs text-xs leading-5 text-slate-400">
                A local-first multi-agent research workspace. Every answer
                planned, verified, and cited.
              </p>
              <p className="footer-heading mt-6">BUILT BY</p>
              <div className="mt-3 flex flex-col gap-2.5">
                <p className="text-xs font-medium text-slate-300">
                  Ashish Chandan
                </p>
                <div className="flex items-center gap-3">
                  <a
                    href={GITHUB_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-xs text-slate-400 transition-colors hover:text-white"
                  >
                    <Github className="h-3.5 w-3.5" />
                    GitHub
                  </a>
                  <a
                    href="mailto:ashishchandan669@gmail.com"
                    className="text-xs text-slate-400 transition-colors hover:text-white"
                  >
                    Email
                  </a>
                </div>
              </div>
            </div>

            <div>
              <p className="footer-heading">PRODUCT</p>
              <div className="mt-4 flex flex-col gap-2.5">
                <a href="#examples" className="footer-link">Examples</a>
                <a href="#workflow" className="footer-link">Workflow</a>
                <a href="#features" className="footer-link">Features</a>
                <a href="#architecture" className="footer-link">Architecture</a>
              </div>
            </div>

            <div>
              <p className="footer-heading">OPEN SOURCE</p>
              <div className="mt-4 flex flex-col gap-2.5">
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">GitHub</a>
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">Documentation</a>
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">Roadmap</a>
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">License</a>
              </div>
            </div>

            <div>
              <p className="footer-heading">COMMUNITY</p>
              <div className="mt-4 flex flex-col gap-2.5">
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">Issues</a>
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">Discussions</a>
                <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="footer-link">Privacy</a>
              </div>
            </div>
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-white/[0.06] pt-6 text-xs text-slate-600 sm:flex-row">
            <span>Built with LangGraph, FastAPI, and local models.</span>
            <span>© {new Date().getFullYear()} ResearchSwarm</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
