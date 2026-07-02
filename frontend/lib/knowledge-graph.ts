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

const ENTITY_TYPES: { keywords: string[]; type: GraphEntity["type"]; color: string }[] = [
  { keywords: ["gpt", "claude", "gemini", "llama", "mistral", "qwen", "deepseek"], type: "technology", color: "#06b6d4" },
  { keywords: ["openai", "anthropic", "google", "meta", "microsoft", "apple", "amazon"], type: "company", color: "#8b5cf6" },
  { keywords: ["rag", "llm", "ai", "ml", "nlp", "transformer", "attention", "embedding", "token"], type: "concept", color: "#10b981" },
  { keywords: ["paper", "research", "study", "survey", "benchmark"], type: "paper", color: "#f59e0b" },
];

const DEFAULT_TOPICS = [
  "Retrieval Augmented Generation", "Large Language Models", "Vector Search",
  "Semantic Search", "Prompt Engineering", "Fine Tuning", "Model Architecture",
  "Natural Language Processing", "Knowledge Base", "Information Retrieval",
];

export function parseEntities(text: string): GraphEntity[] {
  const entities: Map<string, GraphEntity> = new Map();
  const words = text.split(/\s+/);

  for (let i = 0; i < words.length; i++) {
    const word = words[i].replace(/[^a-zA-Z0-9-]/g, "");
    if (word.length < 3) continue;

    const lower = word.toLowerCase();
    for (const { keywords, type, color } of ENTITY_TYPES) {
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

  for (const topic of DEFAULT_TOPICS) {
    if (text.toLowerCase().includes(topic.toLowerCase())) {
      const id = topic.toLowerCase().replace(/\s+/g, "-");
      if (!entities.has(id)) {
        entities.set(id, { id, label: topic, type: "topic", color: "#f59e0b" });
      }
    }
  }

  return Array.from(entities.values()).slice(0, 30);
}

export function buildGraph(text: string, sources: { title?: string; url?: string }[]): { entities: GraphEntity[]; relations: GraphRelation[] } {
  const entities = parseEntities(text);
  const relations: GraphRelation[] = [];

  for (const source of sources) {
    if (!source.title) continue;
    const related = entities.find((e) =>
      source.title!.toLowerCase().includes(e.id)
    );
    if (related) {
      const sourceId = source.title.toLowerCase().replace(/\s+/g, "-");
      if (!entities.find((e) => e.id === sourceId)) {
        entities.push({
          id: sourceId,
          label: source.title.length > 30 ? source.title.slice(0, 30) + "..." : source.title,
          type: "paper",
          color: "#f59e0b",
        });
      }
      relations.push({ source: sourceId, target: related.id, label: "cites" });
    }
  }

  for (let i = 0; i < entities.length; i++) {
    for (let j = i + 1; j < entities.length; j++) {
      if (Math.random() > 0.7) continue;
      if (entities[i].type === entities[j].type) continue;
      relations.push({
        source: entities[i].id,
        target: entities[j].id,
        label: entities[i].type === "technology" ? "relates to" : "connected to",
      });
    }
  }

  return { entities, relations };
}
