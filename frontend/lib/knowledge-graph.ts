export interface GraphEntity {
  id: string;
  label: string;
  type: "concept" | "technology" | "company" | "person" | "paper" | "topic";
  color: string;
}

export interface GraphRelation {
  source: string;
  target: string;
  label: string;
}

export const ENTITY_TYPE_CONFIG: { keywords: string[]; type: GraphEntity["type"]; color: string }[] = [
  { keywords: ["gpt", "claude", "gemini", "llama", "mistral", "qwen", "deepseek"], type: "technology", color: "#06b6d4" },
  { keywords: ["openai", "anthropic", "google", "meta", "microsoft", "apple", "amazon"], type: "company", color: "#8b5cf6" },
  { keywords: ["rag", "llm", "ai", "ml", "nlp", "transformer", "attention", "embedding", "token"], type: "concept", color: "#10b981" },
  { keywords: ["paper", "research", "study", "survey", "benchmark"], type: "paper", color: "#f59e0b" },
];

export function parseEntities(text: string): GraphEntity[] {
  const entities: Map<string, GraphEntity> = new Map();
  const words = text.split(/\s+/);

  for (let i = 0; i < words.length; i++) {
    const word = words[i].replace(/[^a-zA-Z0-9-]/g, "");
    if (word.length < 3) continue;

    const lower = word.toLowerCase();
    for (const { keywords, type, color } of ENTITY_TYPE_CONFIG) {
      if (keywords.some((k) => lower.includes(k) || k.includes(lower))) {
        const id = word.toLowerCase();
        if (!entities.has(id)) {
          entities.set(id, { id, label: word, type, color });
        }
        break;
      }
    }

    if (/^[A-Z][a-z]+/.test(word) && word.length > 4) {
      const id = word.toLowerCase();
      if (!entities.has(id)) {
        entities.set(id, { id, label: word, type: "concept", color: "#10b981" });
      }
    }
  }

  return Array.from(entities.values()).slice(0, 30);
}

export function buildGraph(text: string, sources: { title?: string; url?: string }[]): { entities: GraphEntity[]; relations: GraphRelation[] } {
  const entities = parseEntities(text);
  const relations: GraphRelation[] = [];
  const seen = new Set<string>();

  for (const source of sources) {
    if (!source.title) continue;
    const related = entities.find((e) =>
      source.title!.toLowerCase().includes(e.id)
    );
    if (related) {
      const sourceId = "src-" + source.title.toLowerCase().replace(/\s+/g, "-").slice(0, 40);
      if (!entities.find((e) => e.id === sourceId)) {
        entities.push({
          id: sourceId,
          label: source.title.length > 30 ? source.title.slice(0, 30) + "..." : source.title,
          type: "paper",
          color: "#f59e0b",
        });
      }
      const relKey = `${sourceId}-${related.id}`;
      if (!seen.has(relKey)) {
        seen.add(relKey);
        relations.push({ source: sourceId, target: related.id, label: "cites" });
      }
    }
  }

  return { entities, relations };
}
