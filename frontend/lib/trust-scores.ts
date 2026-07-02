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

  const authority = rating?.authority ?? estimateAuthority(domain, title);
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

function estimateAuthority(domain: string, title?: string): number {
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
    const currentYear = 2026;
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
  if (authority >= 80) return Math.round(Math.random() * 5 + 2);
  if (authority >= 60) return Math.round(Math.random() * 10 + 5);
  return Math.round(Math.random() * 15 + 10);
}
