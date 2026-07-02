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
}

export interface UploadedDocument {
  document_id: string;
  filename: string;
  size: number;
  status: string;
}
