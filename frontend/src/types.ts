export type Job = {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  url: string;
  salary: string;
  job_type: string;
  tags: string[];
  published_at: string;
  description: string;
  score: number | null;
  match_reasons: string[];
  saved: boolean;
};

export type Provider = {
  id: string;
  label: string;
  hint: string;
  needs_base_url: boolean;
  default_base_url: string;
  default_model: string;
};

export type Settings = {
  provider: string;
  base_url: string;
  model: string;
  temperature: number;
  sources: string[];
  api_key_masked: string;
  api_key_set: boolean;
  has_model: boolean;
};

export type AgentEvent = {
  type: string;
  payload: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
