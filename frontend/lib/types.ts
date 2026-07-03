export interface SourceCitation {
  source_type: string;
  title: string;
  url?: string;
  relevance?: string;
}

export interface AgentLog {
  timestamp: number;
  agent: string;
  action: string;
  status: string;
  details?: string;
}

export interface DebatePerspective {
  perspective_id: string;
  label: string;
  emoji: string;
  color: string;
  argument: string;
  latency_ms: number;
  status: string;
}

export interface DebateData {
  query: string;
  perspectives: DebatePerspective[];
  judge_verdict: string | null;
  judge_latency_ms: number;
  status: string;
  errors: string[];
}

export interface ResearchResult {
  task_id: string;
  conversation_id?: string;
  query: string;
  answer: string | null;
  sources: SourceCitation[];
  plan: ExecutionStep[];
  logs: AgentLog[];
  status: string;
  errors: string[];
  execution_time: number;
  plan_reasoning?: string;
  agent_metrics?: Record<string, AgentMetric>;
  debate?: DebateData;
  answer_mode?: string;
  evidence_summary?: {
    web_count: number;
    document_chunks_count: number;
    has_web_sources: boolean;
    has_documents: boolean;
    source_count?: number;
  };
  has_evidence?: boolean;
}

export interface AgentMetric {
  latency_ms?: number;
  model?: string;
  status?: string;
  result_count?: number;
  chunks_retrieved?: number;
  pdfs_processed?: number;
  source_count?: number;
  error?: string;
}

export interface ExecutionStep {
  step_id: number;
  action: string;
  agent: string;
  status: string;
  description?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  sources?: SourceCitation[];
  logs?: AgentLog[];
  status?: string;
  debate?: DebateData;
  answerMode?: string;
  evidenceSummary?: ResearchResult["evidence_summary"];
  hasEvidence?: boolean;
}

export interface UploadedDocument {
  document_id: string;
  filename: string;
  size: number;
  status: string;
}
