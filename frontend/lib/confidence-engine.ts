export interface ParagraphScore {
  text: string;
  confidence: number;
  signals: ConfidenceSignal[];
}

export interface ConfidenceSignal {
  type: "citation" | "hedge" | "speculation" | "factual" | "quantified" | "source_ref";
  label: string;
  strength: -1 | 1;
}

function extractSignals(paragraph: string): ConfidenceSignal[] {
  const signals: ConfidenceSignal[] = [];

  const lower = paragraph.toLowerCase();

  if (/\[\d+(?:,\s*\d+)*\]/.test(paragraph)) {
    signals.push({ type: "citation", label: "Has citations", strength: 1 });
  }

  if (lower.includes("no evidence") || lower.includes("fallback mode") || lower.includes("research could not be completed") || lower.includes("no relevant web sources")) {
    signals.push({ type: "factual", label: "No evidence available", strength: -1 });
    return signals;
  }

  const hedgeWords = [
    "may", "might", "could", "possibly", "perhaps", "likely",
    "unlikely", "suggests", "indicates", "appears", "seems",
    "potentially", "arguably", "presumably",
  ];
  const hedgeCount = hedgeWords.filter((w) =>
    new RegExp(`\\b${w}\\b`, "i").test(paragraph),
  ).length;
  if (hedgeCount > 1) {
    signals.push({ type: "hedge", label: "Hedging language", strength: -1 });
  }

  const speculationWords = [
    "might be", "could be", "would be", "if true", "assuming",
    "hypothetical", "in theory", "speculative",
  ];
  const specCount = speculationWords.filter((w) =>
    paragraph.toLowerCase().includes(w),
  ).length;
  if (specCount > 0) {
    signals.push({ type: "speculation", label: "Speculative", strength: -1 });
  }

  const quantified = paragraph.match(/\d+[%×]|\d+\.\d+|\d+,\d{3}/);
  if (quantified) {
    signals.push({ type: "quantified", label: "Quantified data", strength: 1 });
  }

  const sourceRefs = paragraph.match(
    /according to|per |reported by|sourced from|cite|source|study by|research from/i,
  );
  if (sourceRefs) {
    signals.push({ type: "source_ref", label: "Source referenced", strength: 1 });
  }

  return signals;
}

function computeConfidence(signals: ConfidenceSignal[]): number {
  let base = 70;
  for (const s of signals) {
    base += s.strength * 10;
  }
  if (signals.some((s) => s.type === "factual" && s.label === "No evidence available")) {
    return 15;
  }
  return Math.max(10, Math.min(99, base));
}

export function scoreParagraph(paragraph: string): ParagraphScore {
  const signals = extractSignals(paragraph);
  const confidence = computeConfidence(signals);
  return { text: paragraph, confidence, signals };
}

export function splitIntoParagraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 20);
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 80) return "bg-emerald-400";
  if (confidence >= 60) return "bg-amber-400";
  return "bg-rose-400";
}

export function confidenceLabel(confidence: number): string {
  if (confidence >= 80) return "High";
  if (confidence >= 60) return "Medium";
  return "Lower";
}
