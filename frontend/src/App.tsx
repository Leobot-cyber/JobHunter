import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, streamChat } from "./api";
import type { AgentEvent, ChatMessage, Job, Provider, Settings } from "./types";

/* ── types ── */
interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
}

/* ── helpers ── */
function mergeJobs(prev: Job[], incoming: Job[]): Job[] {
  const map = new Map(prev.map((j) => [j.id, j]));
  for (const job of incoming) map.set(job.id, { ...map.get(job.id), ...job });
  return [...map.values()].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
}

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "新对话",
    messages: [],
    createdAt: Date.now(),
  };
}

function deriveTitle(msg: string): string {
  return msg.length > 24 ? msg.slice(0, 24) + "…" : msg;
}

/* ── component ── */
export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [sources, setSources] = useState<{ id: string; label: string }[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);

  // Conversations
  const [conversations, setConversations] = useState<Conversation[]>(() => [newConversation()]);
  const [activeId, setActiveId] = useState(conversations[0].id);
  const active = conversations.find((c) => c.id === activeId)!;

  // UI state
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keyword, setKeyword] = useState("python");
  const [location, setLocation] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<{ name: string; size: number; modified_at: string }[]>([]);
  const [pullingModel, setPullingModel] = useState("");
  const [pullProgress, setPullProgress] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载 Ollama 模型列表
  useEffect(() => {
    if (showSettings) {
      api.listOllamaModels().then((d) => setOllamaModels(d.models)).catch(() => setOllamaModels([]));
    }
  }, [showSettings]);

  // 拉取 Ollama 模型
  async function onPullModel(modelName: string) {
    setPullingModel(modelName);
    setPullProgress("开始下载...");
    try {
      const res = await api.pullOllamaModel(modelName);
      if (!res.body) throw new Error("无响应");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              if (data.status) setPullProgress(data.status);
              if (data.completed && data.total) {
                const pct = Math.round((data.completed / data.total) * 100);
                setPullProgress(`下载中... ${pct}%`);
              }
            } catch {
              /* ignore */
            }
          }
        }
      }
      setPullProgress("✅ 下载完成！");
      // 刷新模型列表
      const d = await api.listOllamaModels();
      setOllamaModels(d.models);
    } catch (err) {
      setPullProgress(`❌ 错误: ${err}`);
    } finally {
      setPullingModel("");
    }
  }

  // 快捷切换到已安装的 Ollama 模型
  function onSwitchOllamaModel(modelName: string) {
    if (!settings) return;
    setSettings({
      ...settings,
      provider: "ollama",
      base_url: "http://127.0.0.1:11434/v1",
      model: modelName,
    });
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [active.messages]);

  useEffect(() => {
    api.settings().then(setSettings).catch((e) => setError(String(e)));
    api.providers().then((d) => {
      setProviders(d.providers);
      setSources(d.sources);
    });
    api.jobs().then((d) => setJobs(d.jobs)).catch(() => undefined);
  }, []);

  const savedCount = useMemo(() => jobs.filter((j) => j.saved).length, [jobs]);

  /* ── conversation actions ── */
  function createConversation() {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
  }

  function deleteConversation(id: string) {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (next.length === 0) next.push(newConversation());
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
  }

  /* ── send message ── */
  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || busy) return;
    const text = draft.trim();
    setDraft("");
    setBusy(true);
    setError("");

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };

    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId
          ? {
              ...c,
              title: c.messages.length === 0 ? deriveTitle(text) : c.title,
              messages: [...c.messages, userMsg, assistantMsg],
            }
          : c,
      ),
    );

    let assistantText = "";
    try {
      await streamChat(text, "ui-thread", (event: AgentEvent) => {
        const p = event.payload || {};
        if (event.type === "workflow/start") {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === activeId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: assistantText + `\n\n📋 **${(p.meta as { name?: string })?.name || "workflow"}** 启动` }
                        : m,
                    ),
                  }
                : c,
            ),
          );
        } else if (event.type === "workflow/phase") {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === activeId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantId ? { ...m, content: assistantText + `\n\n▸ ${p.title}` } : m,
                    ),
                  }
                : c,
            ),
          );
        } else if (event.type === "workflow/log") {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === activeId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantId ? { ...m, content: assistantText + `\n${p.message}` } : m,
                    ),
                  }
                : c,
            ),
          );
        } else if (event.type === "jobs" && Array.isArray(p.jobs)) {
          setJobs((prev) => mergeJobs(prev, p.jobs as Job[]));
        } else if (event.type === "assistant") {
          assistantText = String(p.content || "");
          setConversations((prev) =>
            prev.map((c) =>
              c.id === activeId
                ? { ...c, messages: c.messages.map((m) => (m.id === assistantId ? { ...m, content: assistantText } : m)) }
                : c,
            ),
          );
        } else if (event.type === "error") {
          setError(String(p.message || "error"));
        }
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  /* ── job actions ── */
  async function onSearch() {
    setBusy(true);
    setError("");
    try {
      const res = await api.search(keyword, location, settings?.sources);
      setJobs((prev) => mergeJobs(prev, res.jobs));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleSave(job: Job) {
    const updated = await api.saveJob(job.id, !job.saved);
    setJobs((prev) => mergeJobs(prev, [updated]));
  }

  /* ── settings ── */
  async function saveSettings(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setBusy(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        provider: settings.provider,
        base_url: settings.base_url,
        model: settings.model,
        temperature: settings.temperature,
        sources: settings.sources,
      };
      if (apiKey.trim()) body.api_key = apiKey.trim();
      const next = await api.saveSettings(body);
      setSettings(next);
      setApiKey("");
      setShowSettings(false);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  function toggleSource(id: string) {
    if (!settings) return;
    const has = settings.sources.includes(id);
    setSettings({
      ...settings,
      sources: has ? settings.sources.filter((s) => s !== id) : [...settings.sources, id],
    });
  }

  /* ── render ── */
  return (
    <div className="app">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
            <span>JobHunter</span>
          </div>
          <button className="sidebar-new" onClick={createConversation} title="新对话">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        <div className="sidebar-conversations">
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`sidebar-item ${c.id === activeId ? "active" : ""}`}
              onClick={() => setActiveId(c.id)}
            >
              <span className="sidebar-item-title">{c.title}</span>
              <span className="sidebar-item-count">{c.messages.length}</span>
              {conversations.length > 1 && (
                <button
                  className="sidebar-item-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(c.id);
                  }}
                  title="删除"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <button className="sidebar-settings-btn" onClick={() => setShowSettings(true)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
            模型设置
          </button>
          {settings && (
            <span className="sidebar-model">
              {settings.provider} · {settings.model}
            </span>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        {/* Top bar */}
        <header className="topbar">
          <button className="topbar-toggle" onClick={() => setSidebarOpen((v) => !v)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="topbar-title">
            <h1>{active.title}</h1>
            <span className="topbar-status">{busy ? "思考中…" : "就绪"}</span>
          </div>
          <div className="topbar-actions">
            <span className="topbar-jobs">岗位 {jobs.length} · 收藏 {savedCount}</span>
          </div>
        </header>

        {/* Messages */}
        <div className="messages">
          {active.messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <h2>开始找工作</h2>
              <p>描述你想找的方向，例如「远程 Python 后端，偏 FastAPI」</p>
              <div className="empty-suggestions">
                <button onClick={() => setDraft("远程 Python 后端，关键词 FastAPI, LangGraph")}>
                  远程 Python 后端
                </button>
                <button onClick={() => setDraft("前端 React 工程师，旧金山湾区")}>前端 React 工程师</button>
                <button onClick={() => setDraft("数据科学，远程，Python")}>数据科学</button>
              </div>
            </div>
          ) : (
            active.messages.map((m) => (
              <div key={m.id} className={`message ${m.role}`}>
                <div className="message-avatar">
                  {m.role === "user" ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                    </svg>
                  )}
                </div>
                <div className="message-content">
                  <div className="message-role">{m.role === "user" ? "你" : "JobHunter"}</div>
                  <div className="message-text">{m.content || "…"}</div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Jobs strip */}
        {jobs.length > 0 && (
          <div className="jobs-strip">
            <div className="jobs-strip-header">
              <span>最新岗位</span>
              <span className="jobs-strip-count">{jobs.length} 个</span>
            </div>
            <div className="jobs-strip-scroll">
              {jobs.slice(0, 6).map((job) => (
                <div key={job.id} className="job-card">
                  <div className="job-card-source">{job.source}</div>
                  <div className="job-card-title">
                    <a href={job.url} target="_blank" rel="noreferrer">
                      {job.title}
                    </a>
                  </div>
                  <div className="job-card-company">
                    {job.company} · {job.location || "Remote"}
                  </div>
                  <button className="job-card-save" onClick={() => toggleSave(job)}>
                    {job.saved ? "★" : "☆"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search bar */}
        <div className="search-bar">
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="关键词"
            className="search-input"
          />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="地点（可选）"
            className="search-input"
          />
          <button className="search-btn" onClick={onSearch} disabled={busy}>
            筛选岗位
          </button>
        </div>

        {/* Composer */}
        <form className="composer" onSubmit={onSend}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="描述你想找的工作方向…"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend(e);
              }
            }}
          />
          <button disabled={busy || !settings?.has_model} type="submit">
            {busy ? (
              <span className="spinner" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </form>

        {error && <div className="error-toast">{error}</div>}
      </main>

      {/* Settings modal */}
      {showSettings && settings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>模型设置</h2>
              <button className="modal-close" onClick={() => setShowSettings(false)}>
                ×
              </button>
            </div>
            <form className="modal-form" onSubmit={saveSettings}>
              <label>
                Provider
                <select
                  value={settings.provider}
                  onChange={(e) => {
                    const p = providers.find((x) => x.id === e.target.value);
                    setSettings({
                      ...settings,
                      provider: e.target.value,
                      base_url: p?.default_base_url || settings.base_url,
                      model: p?.default_model || settings.model,
                    });
                  }}
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="hint">{providers.find((p) => p.id === settings.provider)?.hint}</p>
              <label>
                Base URL
                <input
                  value={settings.base_url}
                  onChange={(e) => setSettings({ ...settings, base_url: e.target.value })}
                />
              </label>
              <label>
                Model
                <input value={settings.model} onChange={(e) => setSettings({ ...settings, model: e.target.value })} />
              </label>
              <label>
                API Key（留空则不覆盖已保存的值）
                <input
                  type="password"
                  value={apiKey}
                  placeholder={settings.api_key_set ? "已保存，输入新值以替换" : "sk-..."}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </label>
              <label>
                Temperature {settings.temperature}
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.temperature}
                  onChange={(e) => setSettings({ ...settings, temperature: Number(e.target.value) })}
                />
              </label>
              <div>
                <p className="hint">启用的公开招聘源</p>
                <div className="chips">
                  {sources.map((s) => (
                    <button
                      type="button"
                      key={s.id}
                      className={settings.sources.includes(s.id) ? "on" : ""}
                      onClick={() => toggleSource(s.id)}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Ollama 本地模型管理 */}
              <div style={{ borderTop: "1px solid var(--border-light)", paddingTop: 16 }}>
                <p className="hint" style={{ fontWeight: 500, marginBottom: 8 }}>本地模型 (Ollama)</p>
                {ollamaModels.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {ollamaModels.map((m) => (
                      <div key={m.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: "var(--bg)", borderRadius: "var(--radius-sm)" }}>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 500 }}>{m.name}</div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{(m.size / 1073741824).toFixed(1)} GB</div>
                        </div>
                        <button
                          type="button"
                          className="btn ghost"
                          style={{ fontSize: 12, padding: "4px 10px" }}
                          onClick={() => onSwitchOllamaModel(m.name)}
                          disabled={settings.provider === "ollama" && settings.model === m.name}
                        >
                          {settings.provider === "ollama" && settings.model === m.name ? "当前" : "切换"}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="hint">未检测到已安装的模型</p>
                )}

                {pullProgress && (
                  <div style={{ marginTop: 8, padding: "8px 12px", background: "var(--accent-light)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "var(--accent)" }}>
                    {pullProgress}
                  </div>
                )}

                <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {["qwen2.5:7b", "qwen2.5:14b", "llama3.2:3b", "llama3.1:8b"].map((m) => (
                    <button
                      key={m}
                      type="button"
                      className="btn ghost"
                      style={{ fontSize: 12, padding: "6px 12px" }}
                      onClick={() => onPullModel(m)}
                      disabled={pullingModel === m}
                    >
                      {pullingModel === m ? "下载中..." : `安装 ${m}`}
                    </button>
                  ))}
                </div>
              </div>

              <button className="modal-save" disabled={busy} type="submit">
                保存
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
