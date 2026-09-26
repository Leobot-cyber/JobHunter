import type { AgentEvent, Job, Provider, Settings } from "./types";

function extractError(text: string, fallback: string): string {
  try {
    const data = JSON.parse(text);
    if (data && typeof data.detail === "string") return data.detail;
  } catch {
    /* not JSON */
  }
  return text || fallback;
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(extractError(text, res.statusText));
  }
  return res.json() as Promise<T>;
}

/** 把底层报错翻译成用户能看懂的提示 */
export function friendlyError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (
    msg.includes("Failed to fetch") ||
    msg.includes("NetworkError") ||
    msg.includes("ECONNREFUSED") ||
    msg.includes("Internal Server Error")
  ) {
    return "后端服务未连接。请运行 ./start.sh 启动，或安装常驻服务：scripts/install_backend_service.sh";
  }
  return msg;
}

export const api = {
  health: () => fetch("/api/health").then((r) => r.ok),
  settings: () => fetch("/api/settings").then((r) => parseJson<Settings>(r)),
  providers: () =>
    fetch("/api/providers").then((r) =>
      parseJson<{ providers: Provider[]; sources: { id: string; label: string }[] }>(r),
    ),
  saveSettings: (body: Record<string, unknown>) =>
    fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => parseJson<Settings>(r)),
  jobs: () => fetch("/api/jobs").then((r) => parseJson<{ jobs: Job[] }>(r)),
  search: (keywords: string, location = "", sources?: string[]) =>
    fetch("/api/jobs/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords, location, sources, limit: 30 }),
    }).then((r) => parseJson<{ jobs: Job[] }>(r)),
  saveJob: (id: string, saved: boolean) =>
    fetch(`/api/jobs/${encodeURIComponent(id)}/save?saved=${saved}`, { method: "POST" }).then((r) =>
      parseJson<Job>(r),
    ),
  // Ollama 模型管理
  listOllamaModels: () =>
    fetch("/api/ollama/models").then((r) => parseJson<{ models: { name: string; size: number; modified_at: string }[] }>(r)),
  pullOllamaModel: (modelName: string) =>
    fetch("/api/ollama/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    }),
};

export async function streamChat(
  message: string,
  threadId: string,
  onEvent: (event: AgentEvent) => void,
  onLog?: (msg: string) => void,
): Promise<void> {
  onLog?.(`[SSE] POST /api/chat/stream  message="${message.slice(0, 40)}..."`);
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!res.ok || !res.body) {
    const text = await res.text();
    const err = text || "stream failed";
    onLog?.(`[SSE] ERROR ${res.status} ${err}`);
    throw new Error(err);
  }
  onLog?.(`[SSE] connected status=${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE uses \r\n\r\n (CRLF) or \n\n (LF) as chunk separator.
    // Normalize to \n\n for splitting.
    const normalized = buffer.replace(/\r\n/g, "\n");
    const chunks = normalized.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const dataLine = chunk
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim())
        .join("");
      if (!dataLine) continue;
      try {
        const evt = JSON.parse(dataLine) as AgentEvent;
        onLog?.(`[SSE] ← ${evt.type}  ${JSON.stringify(evt.payload || {})}`);
        onEvent(evt);
      } catch {
        onLog?.(`[SSE] malformed: ${dataLine.slice(0, 80)}`);
      }
    }
  }
  // Flush remaining buffer on stream end
  if (buffer.trim()) {
    const normalized = buffer.replace(/\r\n/g, "\n");
    const dataLine = normalized
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim())
      .join("");
    if (dataLine) {
      try {
        const evt = JSON.parse(dataLine) as AgentEvent;
        onLog?.(`[SSE] ← ${evt.type} (flush)  ${JSON.stringify(evt.payload || {})}`);
        onEvent(evt);
      } catch {
        onLog?.(`[SSE] flush malformed: ${dataLine.slice(0, 80)}`);
      }
    }
  }
  onLog?.(`[SSE] stream ended`);
}
