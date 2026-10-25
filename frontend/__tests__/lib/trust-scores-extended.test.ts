import { describe, expect, it } from "vitest";
import {
  authorityStars,
  classifySourceType,
  confidenceLabel,
  faviconUrl,
  getConfidence,
  getHallucinationRisk,
  getTrustScore,
  verdictStars,
} from "@/lib/trust-scores";

describe("trust scores and source classification", () => {
  it("uses known domain ratings, article freshness, and topical relevance", () => {
    const score = getTrustScore("https://www.nature.com/articles/ai", "2026 research survey and analysis");
    expect(score).toMatchObject({ authority: 95, bias: "low", freshness: "Current", relevance: 95, domain: "nature.com" });
    expect(getTrustScore("university.edu", "2025 report").authority).toBe(88);
    expect(getTrustScore("unknown.example", "old note").freshness).toBe("Unknown");
  });

  it("falls back for malformed and unknown URLs without inventing a high score", () => {
    expect(getTrustScore("not a url").authority).toBe(50);
    expect(getTrustScore("https://mywiki.org").authority).toBe(65);
    expect(getTrustScore("https://blogspot.com").bias).toBe("high");
    expect(faviconUrl(undefined)).toBeNull();
    expect(faviconUrl("https://example.com/path")).toContain("domain=example.com");
  });

  it("classifies source types from provider, host, TLD, subdomain, and path", () => {
    expect(classifySourceType({ provider: "GitHub search", url: "https://host.test" })).toBe("GitHub");
    expect(classifySourceType({ url: "https://arxiv.org/abs/123" })).toBe("Paper");
    expect(classifySourceType({ url: "https://blog.medium.com/post" })).toBe("Blog");
    expect(classifySourceType({ url: "https://agency.gov/page" })).toBe("Official");
    expect(classifySourceType({ url: "https://docs.example.com/api" })).toBe("Docs");
    expect(classifySourceType({ url: "https://example.com/documentation" })).toBe("Docs");
    expect(classifySourceType({ url: "https://openai.com" })).toBe("Official");
    expect(classifySourceType({ url: "https://ordinary.example.net" })).toBe("Web");
  });

  it("maps confidence thresholds to labels, stars, and hallucination risk", () => {
    expect(getConfidence(90, 70)).toBe(82);
    expect(confidenceLabel(75)).toBe("High");
    expect(confidenceLabel(55)).toBe("Medium");
    expect(confidenceLabel(54)).toBe("Low");
    expect(authorityStars(80)).toBe("★★★★☆");
    expect(getHallucinationRisk(95)).toBe(3);
    expect(getHallucinationRisk(85)).toBe(5);
    expect(getHallucinationRisk(75)).toBe(8);
    expect(getHallucinationRisk(65)).toBe(12);
    expect(getHallucinationRisk(50)).toBe(18);
    expect(getHallucinationRisk(20)).toBe(25);
    expect(verdictStars(0)).toBe(1);
    expect(verdictStars(100)).toBe(5);
  });
});
