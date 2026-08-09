export interface TrustScore {
  authority: number;
  freshness: string;
  bias: "low" | "moderate" | "high";
  relevance: number;
  domain: string;
}

const DOMAIN_RATINGS: Record<string, { authority: number; bias: "low" | "moderate" | "high" }> = {
  "nature.com": { authority: 95, bias: "low" },
  "science.org": { authority: 94, bias: "low" },
  "arxiv.org": { authority: 88, bias: "low" },
  "scholar.google.com": { authority: 90, bias: "low" },
  "wikipedia.org": { authority: 75, bias: "moderate" },
  "reuters.com": { authority: 90, bias: "low" },
  "apnews.com": { authority: 89, bias: "low" },
  "bbc.com": { authority: 85, bias: "low" },
  "nytimes.com": { authority: 82, bias: "low" },
  "github.com": { authority: 70, bias: "low" },
  "medium.com": { authority: 45, bias: "moderate" },
  "substack.com": { authority: 40, bias: "moderate" },
  "blogspot.com": { authority: 25, bias: "high" },
  "wordpress.com": { authority: 20, bias: "high" },
  "reddit.com": { authority: 30, bias: "high" },
  "twitter.com": { authority: 25, bias: "high" },
  "x.com": { authority: 25, bias: "high" },
  "youtube.com": { authority: 40, bias: "moderate" },
  "linkedin.com": { authority: 55, bias: "moderate" },
  "facebook.com": { authority: 20, bias: "high" },
};

const TLD_RATINGS: Record<string, { authority: number; bias: "low" | "moderate" | "high" }> = {
  ".gov": { authority: 92, bias: "low" },
  ".edu": { authority: 88, bias: "low" },
  ".org": { authority: 65, bias: "moderate" },
};

export function getTrustScore(url?: string, title?: string): TrustScore {
  const domain = extractDomain(url || "");
  const rating = DOMAIN_RATINGS[domain] || TLD_RATINGS[`.${domain.split(".").pop()}`] || null;

  const authority = rating?.authority ?? estimateAuthority(domain);
  const bias = rating?.bias ?? "moderate";
  const freshness = estimateFreshness(title);
  const relevance = estimateRelevance(title);

  return { authority, freshness, bias, relevance, domain };
}

function extractDomain(url: string): string {
  try {
    const u = new URL(url.startsWith("http") ? url : `https://${url}`);
    return u.hostname.replace("www.", "");
  } catch {
    return url;
  }
}

function estimateAuthority(domain: string): number {
  const tld = `.${domain.split(".").pop()}`;
  if (tld === ".gov") return 92;
  if (tld === ".edu") return 88;
  if (tld === ".org") return 65;
  const parts = domain.split(".");
  if (parts.length >= 2) {
    const known = parts.slice(-2).join(".");
    const match = Object.keys(DOMAIN_RATINGS).find((k) => known.includes(k));
    if (match) return DOMAIN_RATINGS[match].authority;
  }
  return 50;
}

function estimateFreshness(title?: string): string {
  if (!title) return "Unknown";
  const yearMatch = title.match(/\b(20\d{2})\b/);
  if (yearMatch) {
    const year = parseInt(yearMatch[1]);
    const currentYear = new Date().getFullYear();
    if (year >= currentYear) return "Current";
    if (year >= currentYear - 1) return "Recent";
    if (year >= currentYear - 3) return "Moderate";
    return "Dated";
  }
  return "Unknown";
}

function estimateRelevance(title?: string): number {
  if (!title) return 50;
  const words = title.toLowerCase().split(/\s+/);
  const relevanceWords = ["survey", "review", "analysis", "study", "research", "benchmark", "comparison", "report", "guide", "introduction"];
  const matches = words.filter((w) => relevanceWords.includes(w)).length;
  return Math.min(95, 50 + matches * 15);
}

export function authorityStars(authority: number): string {
  const stars = Math.round(authority / 20);
  return "★".repeat(stars) + "☆".repeat(5 - stars);
}

export function getConfidence(authority: number, relevance: number): number {
  return Math.round((authority * 0.6 + relevance * 0.4));
}

export function getHallucinationRisk(authority: number): number {
  if (authority >= 90) return 3;
  if (authority >= 80) return 5;
  if (authority >= 70) return 8;
  if (authority >= 60) return 12;
  if (authority >= 40) return 18;
  return 25;
}

export type ConfidenceLabel = "High" | "Medium" | "Low";

export function confidenceLabel(confidence: number): ConfidenceLabel {
  if (confidence >= 75) return "High";
  if (confidence >= 55) return "Medium";
  return "Low";
}

export function faviconUrl(url?: string): string | null {
  const domain = getTrustScore(url, undefined).domain;
  if (!domain || domain.includes(".") === false) return null;
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
}

export type SourceType = "Official" | "Docs" | "Paper" | "Blog" | "GitHub" | "Web";

const PAPER_HOSTS = [
  "arxiv.org",
  "dl.acm.org",
  "acm.org",
  "ieee.org",
  "ieeexplore.ieee.org",
  "pubmed.ncbi.nlm.nih.gov",
  "nature.com",
  "science.org",
  "springer.com",
  "link.springer.com",
  "sciencedirect.com",
  "semanticscholar.org",
  "openreview.net",
  "jmlr.org",
  "ncbi.nlm.nih.gov",
];

const BLOG_HOSTS = [
  "medium.com",
  "substack.com",
  "blogspot.com",
  "wordpress.com",
  "dev.to",
  "hashnode.dev",
  "hashnode.com",
  "ghost.io",
];

const DOC_HOSTS = [
  "docs.python.org",
  "docs.openai.com",
  "platform.openai.com",
  "docs.anthropic.com",
  "docs.langchain.com",
  "langchain-ai.github.io",
  "developers.google.com",
  "developer.apple.com",
  "learn.microsoft.com",
  "docs.aws.amazon.com",
  "cloud.google.com",
  "docs.docker.com",
  "typescriptlang.org",
  "developer.mozilla.org",
];

const OFFICIAL_HOSTS = [
  "react.dev",
  "nextjs.org",
  "kubernetes.io",
  "docker.com",
  "nodejs.org",
  "python.org",
  "tailwindcss.com",
  "vercel.com",
  "openai.com",
  "anthropic.com",
  "langchain.com",
  "supabase.com",
  "graphql.org",
];

function hostMatches(host: string, list: string[]): boolean {
  return list.some((h) => host === h || host.endsWith(`.${h}`));
}

/**
 * Classifies a source into a human-readable type badge derived purely from
 * available metadata (hostname, URL path, provider). Falls back to "Web" when
 * nothing conclusive is found so metadata is never invented.
 */
export function classifySourceType(source: {
  url?: string;
  provider?: string | null;
}): SourceType {
  const url = source.url ?? "";
  const domain = extractDomain(url);
  const provider = (source.provider ?? "").toLowerCase();

  if (provider.includes("github") || domain === "github.com") return "GitHub";
  if (hostMatches(domain, PAPER_HOSTS)) return "Paper";
  if (hostMatches(domain, BLOG_HOSTS)) return "Blog";

  const tld = `.${domain.split(".").pop()}`.toLowerCase();
  if (tld === ".gov" || tld === ".edu") return "Official";

  let subdomain = "";
  try {
    subdomain =
      new URL(url.startsWith("http") ? url : `https://${url}`).hostname.split(".")[0] ?? "";
  } catch {
    subdomain = "";
  }
  if (/^(docs|developer|developers|help|learn|api)(\d*)$/i.test(subdomain)) return "Docs";
  if (/\/docs(\/|$)|documentation/i.test(url)) return "Docs";
  if (hostMatches(domain, DOC_HOSTS)) return "Docs";
  if (hostMatches(domain, OFFICIAL_HOSTS)) return "Official";
  return "Web";
}

/** Maps a 0-100 confidence score to a 1-5 star verdict. */
export function verdictStars(confidence: number): number {
  return Math.max(1, Math.min(5, Math.round(confidence / 20)));
}
