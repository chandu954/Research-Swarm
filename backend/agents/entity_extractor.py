"""Entity extraction service for knowledge graph enrichment."""
from __future__ import annotations
import json, re
from typing import Optional
from pydantic import BaseModel
from loguru import logger
from backend.llm.factory import get_llm_provider

EXTRACT_SYSTEM_PROMPT = """You are an entity extraction specialist. Extract structured entities and relationships from the given research text.

Return ONLY valid JSON with this exact schema:
{
  "entities": [
    {"id": "unique-id", "label": "Display Name", "type": "technology|company|person|concept|paper|topic", "description": "Brief description"}
  ],
  "relationships": [
    {"source": "entity-id-1", "target": "entity-id-2", "label": "relationship-type", "description": "How they relate"}
  ]
}

Rules:
- Extract 5-15 most important entities only
- IDs must be lowercase with hyphens (e.g., "retrieval-augmented-generation")
- Types: technology (tools, frameworks, models), company (organizations), person (researchers, authors), concept (abstract ideas), paper (publications, research papers), topic (broad subject areas)
- Relationships: connects related entities with clear labels like "uses", "develops", "improves", "part-of", "related-to"
- Be concise but accurate — only extract what is supported by the text
- Do NOT fabricate entities or relationships"""

class ExtractedEntity(BaseModel):
    id: str
    label: str
    type: str
    description: Optional[str] = None

class ExtractedRelationship(BaseModel):
    source: str
    target: str
    label: str
    description: Optional[str] = None

class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = []
    relationships: list[ExtractedRelationship] = []

def _fallback_extract(text: str) -> ExtractionResult:
    """Rule-based fallback when LLM extraction fails."""
    entities = []
    relationships = []
    seen = set()

    tech_patterns = [
        (r"(?i)\b(RAG|LLM|GPT|BERT|T5|LangChain|LangGraph|Transformers?|LoRA|QLoRA)\b", "technology"),
        (r"(?i)\b(OpenAI|Anthropic|Google|Meta|Microsoft|AWS|NVIDIA|Hugging[-\s]?Face)\b", "company"),
        (r"(?i)\b(Attention|Transformer|Embedding|Fine[-\s]?Tun(ing|ed)|Retrieval|Vector[-\s]?Search)\b", "concept"),
    ]

    for pattern, etype in tech_patterns:
        for match in re.finditer(pattern, text):
            label = match.group(1).strip()
            eid = label.lower().replace(" ", "-").replace("_", "-")
            if eid not in seen:
                seen.add(eid)
                entities.append(ExtractedEntity(id=eid, label=label, type=etype))

    ents = list(entities)
    for i in range(len(ents)):
        for j in range(i + 1, len(ents)):
            if ents[i].type != ents[j].type:
                relationships.append(ExtractedRelationship(
                    source=ents[i].id, target=ents[j].id, label="related-to"
                ))
                if len(relationships) >= 8:
                    break
        if len(relationships) >= 8:
            break

    return ExtractionResult(entities=entities[:12], relationships=relationships[:8])


async def extract_entities(
    text: str,
    llm_provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ExtractionResult:
    """Extract entities and relationships from text using LLM, with fallback."""
    if not text or len(text.strip()) < 20:
        return ExtractionResult()

    try:
        llm = get_llm_provider(llm_provider)
        resolved_model = model or "qwen/qwen3-32b" if llm_provider == "openrouter" else "qwen3:14b"

        raw = llm.generate(
            prompt=f"Extract entities and relationships from this research text:\n\n{text[:6000]}",
            model=resolved_model,
            system_prompt=EXTRACT_SYSTEM_PROMPT,
            options={"temperature": 0.1, "num_predict": 2048},
        )

        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            data = json.loads(json_match.group(0))
            entities = [ExtractedEntity(**e) for e in data.get("entities", [])]
            relationships = [ExtractedRelationship(**r) for r in data.get("relationships", [])]
            if entities:
                logger.info(f"LLM extracted {len(entities)} entities, {len(relationships)} relationships")
                return ExtractionResult(entities=entities[:15], relationships=relationships[:10])
    except Exception as e:
        logger.warning(f"LLM entity extraction failed, using fallback: {e}")

    fallback = _fallback_extract(text)
    logger.info(f"Fallback extracted {len(fallback.entities)} entities, {len(fallback.relationships)} relationships")
    return fallback
