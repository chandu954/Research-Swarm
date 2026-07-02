# ResearchSwarm AI — Demo Video Script

**Duration:** 3–4 minutes
**Tone:** Professional, polished, concise
**Audio:** Voiceover + subtle background music (optional)

---

## Scene 1: Opening Hook (0:00–0:15)

**Visual:** Screen recording — browser opens to ResearchSwarm AI landing page. Dark theme, execution timeline visible on right, empty chat on left.

**Voiceover:**
"Meet ResearchSwarm AI — a production-grade multi-agent research system. It orchestrates four AI agents powered by local open-source models to search the web, analyze PDFs, and deliver cited answers. All with real-time visibility into every step."

**On-screen text:** *ResearchSwarm AI — Multi-Agent Research System*

---

## Scene 2: Login Flow (0:15–0:30)

**Visual:** Click "Settings" in sidebar → email/password fields appear → type credentials → click Login → brief loading spinner → "Welcome back" toast appears.

**Voiceover:**
"Start by logging in. JWT-based authentication with bcrypt password hashing keeps your research secure. Google OAuth one-click login is also supported."

**On-screen text:** *JWT Authentication • bcrypt Hashing • Google OAuth*

---

## Scene 3: Upload a PDF (0:30–0:50)

**Visual:** Drag a PDF (e.g., "attention-is-all-you-need.pdf") into the Documents panel → progress bar fills → document card appears with filename and size → checkbox is auto-selected. Zoom in on the success animation.

**Voiceover:**
"Upload research papers via drag-and-drop. PyMuPDF extracts the text, which gets chunked into overlapping segments and embedded using nomic-embed-text into ChromaDB — ready for semantic retrieval."

**On-screen text:** *PDF Upload • PyMuPDF • ChromaDB + nomic-embed-text*

---

## Scene 4: Ask a Question (0:50–1:15)

**Visual:** Type a question into the chat input: "What are the key contributions of the Transformer architecture?" → Press Enter → The message appears in the chat.

**Voiceover:**
"Now ask your research question. The frontend sends it to the FastAPI backend, which kicks off the LangGraph workflow."

**On-screen text:** *FastAPI • LangGraph StateGraph*

---

## Scene 5: Execution Timeline (1:15–1:50)

**Visual:** Focus on the right panel. Show the Execution Timeline component with four agent cards appearing one by one:

1. **Planner** — status dot turns cyan, label shows "analyze_query", latency bar animates to ~3.2s, then turns green.
2. **Web Research** — card appears, latency bar fills to ~5.1s, shows "Found 5 results".
3. **Document Analysis** — card appears, bar fills to ~2.4s, shows "Retrieved 8 chunks".
4. **Answer Synthesis** — card appears, bar fills to ~4.2s, turns green.

**Voiceover:**
"Watch the execution unfold in real-time. The Planner agent uses Qwen3 14B to decompose the query into steps. It fans out to two parallel branches: Web Research with Llama3 8B searches DuckDuckGo, while Document Analysis with Gemma3 12B runs cross-encoder reranking over the PDF chunks. Once both complete, the Answer Agent synthesizes everything into a cited response."

**On-screen text:** *Parallel Execution • Qwen3 14B • Llama3 8B • Gemma3 12B • Cross-Encoder Reranking*

---

## Scene 6: The Answer (1:50–2:15)

**Visual:** Switch focus to the chat area. The "Thinking..." indicator changes to a full markdown answer with headings, bullet points, and [Source N] citations.

**Voiceover:** (reading key parts of answer)
"The answer arrives with structured markdown — headings, bullet points, comparisons. Every factual claim includes a citation number. Let's scroll to the references section."

**Visual:** Scroll to the bottom of the answer to show "## References" with web URLs and document page numbers.

**Voiceover:**
"Each source is clickable — web links open in a new tab, document citations reference the relevant PDF page."

**On-screen text:** *Cited Answers • Markdown Rendering • Source References*

---

## Scene 7: Agent Metrics (2:15–2:30)

**Visual:** Show the Sources panel on the right updating with web results and document chunks. Then zoom into the API response (show a JSON snippet on screen overlay):

```json
"agent_metrics": {
  "planner": {"latency_ms": 3200, "model": "qwen3:14b"},
  "research_agent": {"latency_ms": 5100, "model": "llama3:8b", "result_count": 5},
  "document_agent": {"latency_ms": 2400, "model": "gemma3:12b", "chunks_retrieved": 8},
  "answer_agent": {"latency_ms": 4200, "model": "gemma3:12b", "source_count": 7},
  "total": {"latency_ms": 14900}
}
```

**Voiceover:**
"After execution, the API returns per-agent metrics — latency, model used, result counts. This gives you full observability into what each agent did and how long it took."

**On-screen text:** *Agent Metrics • Observability • Tool Registry*

---

## Scene 8: Light Mode (2:30–2:40)

**Visual:** Click the theme toggle icon in the sidebar → entire UI smoothly transitions to light mode. Show the same chat in light mode.

**Voiceover:**
"Prefer light mode? One click switches themes, with smooth CSS variable transitions across all components."

**On-screen text:** *Dark/Light Mode • CSS Variables • Framer Motion*

---

## Scene 9: Wrap Up (2:40–3:00)

**Visual:** Zoom out to full screen showing the complete layout — sidebar, chat with answer, right panel with timeline, logs, sources.

**Voiceover:**
"ResearchSwarm AI is fully open-source and ready to deploy. The backend runs on FastAPI with PostgreSQL and ChromaDB, the frontend is built with Next.js 15, and everything is containerized with Docker Compose including Ollama with GPU support."

**Visual:** Quick montage of:
- `docker-compose up -d` command running in terminal
- GitHub repo page showing the project
- CI pipeline with green checkmarks

**Voiceover:**
"Clone the repo, pull the models, and run `docker-compose up`. CI pipeline with linting, testing, and Docker build ensures production quality."

**On-screen text:** *Open Source • Docker Compose • CI/CD • MIT License*

---

## Scene 10: Call to Action (3:00–3:15)

**Visual:** End card with:
- GitHub repo URL
- Live demo URL
- "Star on GitHub" button animation

**Voiceover:**
"Check out the repository on GitHub, try the live demo, and star the project if you find it useful. Contributions welcome."

**On-screen text:**
```
ResearchSwarm AI
github.com/yourusername/research-swarm
researchswarm.vercel.app
```

---

## Production Notes

- **Screen recording:** Use CleanShot X or OBS at 2560x1600 resolution
- **Cursor:** Enable cursor highlight with a visible click effect
- **Sensitive data:** Blur/avoid any real credentials
- **Audio:** Record voiceover in a quiet environment; use a good dynamic mic
- **Pacing:** Keep each scene tight — no more than 15–25 seconds per major segment
- **Overlays:** Add subtle callout boxes and keyboard shortcuts for polish
- **Captions:** Include YouTube auto-captions as fallback

## Thumbnail Suggestion

Split screen: left side shows the chat with a cited answer, right side shows the four agent cards with green checkmarks. Overlay text: "4 AI Agents • 1 Question • Cited Answers"
