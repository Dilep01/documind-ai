import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  FileSearch,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  Users,
  X,
} from "lucide-react";
import { api, label, money, setCsrf } from "./api";
import "./styles.css";

type User = { id: string; username: string; role: string };
type Item = {
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
};
type Data = Record<string, string | null | Item[]> & { line_items: Item[] };
type Doc = {
  id: string;
  name: string;
  status: string;
  review_status: string;
  vendor_name: string | null;
  invoice_number: string | null;
  total: string | null;
  issue_count: number;
  version: number;
  kind: string;
  created_at: string;
  duplicate_of: string | null;
  index_status: string;
  job: { stage: string; state: string; error: string | null } | null;
};
type Evidence = {
  page_number: number;
  box: { x0: number; top: number; x1: number; bottom: number };
  quote: string;
};
type Detail = Doc & {
  data: Data | null;
  issues: {
    code: string;
    message: string;
    field: string | null;
    severity: string;
  }[];
  extraction: {
    pages: {
      width: number;
      height: number;
      status: string;
      extraction_method: string;
    }[];
    invoice: Record<string, { evidence: Evidence[] }>;
    line_items: { evidence: Evidence[] }[];
  } | null;
  revisions: { version: number; reason: string; created_at: string }[];
};
type Source = {
  id: string;
  document_id: string;
  name: string;
  page_number: number;
  text: string;
};
const nav = [
  { id: "overview", title: "Overview", icon: LayoutDashboard },
  { id: "documents", title: "Documents", icon: FolderOpen },
  { id: "search", title: "Search & ask", icon: FileSearch },
  { id: "exports", title: "Exports", icon: ArrowDownToLine },
  { id: "activity", title: "Activity", icon: Clock3 },
];
const fieldNames = [
  "vendor_name",
  "customer_name",
  "invoice_number",
  "invoice_date",
  "due_date",
  "currency",
  "subtotal",
  "discount",
  "tax",
  "shipping",
  "total",
  "amount_due",
];

function Badge({ value }: { value: string }) {
  return <span className={"badge " + value}>{label(value)}</span>;
}
function App() {
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true);
  const [screen, setScreen] = useState("overview"),
    [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [docs, setDocs] = useState<Doc[]>([]),
    [stats, setStats] = useState({
      documents: 0,
      approved: 0,
      needs_review: 0,
      approved_total_inr: "0",
    });
  const [filter, setFilter] = useState(""),
    [query, setQuery] = useState(""),
    [uploading, setUploading] = useState(false);
  const [checked, setChecked] = useState<string[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => {
    if (!user) return;
    const [list, dashboard] = await Promise.all([
      api("/documents?q=" + encodeURIComponent(query)),
      api("/dashboard"),
    ]);
    setDocs(list.items);
    setStats(dashboard);
  }, [user, query]);
  useEffect(() => {
    api("/auth/me")
      .then((result) => {
        setCsrf(result.csrf_token);
        setUser(result.user);
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(() => refresh().catch(() => {}), 4000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(""), 6000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  async function upload(files: FileList | File[]) {
    setUploading(true);
    setError("");
    let count = 0;
    try {
      for (const file of Array.from(files)) {
        if (file.size > 20 * 1024 * 1024)
          throw new Error("Each file must be 20 MB or smaller.");
        const form = new FormData();
        form.append("file", file);
        await api("/documents", { method: "POST", body: form });
        count++;
      }
      setNotice(
        `${count} document${count === 1 ? "" : "s"} uploaded. Processing has started.`,
      );
      setScreen("documents");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }
  async function exportSelected(format = "csv", ids = checked) {
    setError("");
    try {
      const result = await api("/exports", {
        method: "POST",
        body: JSON.stringify({
          document_ids: ids,
          format,
          idempotency_key: crypto.randomUUID(),
        }),
      });
      window.location.assign(`/api/v1/exports/${result.id}/download`);
      setNotice("Approved revisions exported.");
      setChecked([]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (checking)
    return (
      <div className="loading">
        <FileText size={32} />
        <p>Opening your workspace…</p>
      </div>
    );
  if (!user)
    return (
      <Login
        onLogin={(result) => {
          setCsrf(result.csrf_token);
          setUser(result.user);
        }}
      />
    );
  const canReview = user.role !== "uploader";
  const shown = docs.filter(
    (doc) => !filter || doc.review_status === filter || doc.status === filter,
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setSelected(null);
            setScreen("overview");
          }}
        >
          <span className="brand-mark">
            <FileText size={23} />
          </span>
          <span>
            DocuMind<span className="brand-ai">AI</span>
          </span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav>
          {nav
            .filter((item) => canReview || item.id !== "exports")
            .map((item) => (
              <button
                key={item.id}
                className={
                  screen === item.id && !selected
                    ? "nav-item active"
                    : "nav-item"
                }
                onClick={() => {
                  setSelected(null);
                  setScreen(item.id);
                  setError("");
                }}
              >
                <item.icon size={19} />
                {item.title}
                {item.id === "documents" && (
                  <span className="nav-count">{stats.documents}</span>
                )}
              </button>
            ))}
          {user.role === "admin" && (
            <button
              className={"nav-item " + (screen === "users" ? "active" : "")}
              onClick={() => {
                setSelected(null);
                setScreen("users");
              }}
            >
              <Users size={19} />
              Team access
            </button>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="status-dot" />
            <strong>Runs on your computer</strong>
            <p>Your documents stay in your local workspace.</p>
          </div>
          <div className="profile">
            <span className="avatar">
              {user.username.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.username}</strong>
              <small>{label(user.role)}</small>
            </div>
            <button
              title="Sign out"
              className="icon-button"
              onClick={async () => {
                await api("/auth/logout", { method: "POST" });
                setUser(null);
                setCsrf("");
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={13} />
            <span>
              {selected
                ? "Document review"
                : screen === "search"
                  ? "Search & ask"
                  : screen === "users"
                    ? "Team access"
                    : label(screen)}
            </span>
          </div>
          <div className="topbar-right">
            <span className="local-pill">
              <span className="status-dot" />
              Local edition
            </span>
            <span className="top-avatar">{user.username[0].toUpperCase()}</span>
          </div>
        </header>
        <div className="content">
          {error && (
            <div role="alert" className="alert error">
              <CircleAlert size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <CheckCheck size={18} />
              {notice}
            </div>
          )}
          {selected ? (
            <Review
              id={selected}
              user={user}
              onBack={() => {
                setSelected(null);
                refresh();
              }}
              onError={setError}
              onNotice={setNotice}
              onExport={(id) => exportSelected("csv", [id])}
            />
          ) : screen === "search" ? (
            <SearchPage onOpen={setSelected} onError={setError} />
          ) : screen === "exports" ? (
            <History kind="exports" />
          ) : screen === "activity" ? (
            <History kind="audit" />
          ) : screen === "users" ? (
            <Team onError={setError} onNotice={setNotice} />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">DOCUMENT INTELLIGENCE</div>
                  <h1>
                    {screen === "overview"
                      ? "A clearer view of your paperwork."
                      : "Your document inbox."}
                  </h1>
                  <p>
                    {screen === "overview"
                      ? "From uploaded files to checked, organized invoice records."
                      : "Upload, check, and approve documents in one place."}
                  </p>
                </div>
                <button
                  className="button primary"
                  onClick={() => input.current?.click()}
                  disabled={uploading}
                >
                  <Plus size={18} />
                  {uploading ? "Uploading…" : "Upload documents"}
                </button>
              </div>
              {screen === "overview" && (
                <>
                  <section className="stats-grid">
                    <Stat
                      title="Documents"
                      value={String(stats.documents)}
                      icon={<FileText />}
                      note="In your workspace"
                    />
                    <Stat
                      title="Awaiting review"
                      value={String(stats.needs_review)}
                      icon={<Clock3 />}
                      note="Ready for a closer look"
                    />
                    <Stat
                      title="Approved invoices"
                      value={String(stats.approved)}
                      icon={<FileCheck2 />}
                      note="Checked and ready to export"
                    />
                    <Stat
                      title="Approved value"
                      value={money(stats.approved_total_inr)}
                      icon={<ShieldCheck />}
                      note="INR · current approved revisions"
                    />
                  </section>
                  <section className="intro-grid">
                    <div
                      className={"upload-zone " + (uploading ? "busy" : "")}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        if (!uploading) upload(e.dataTransfer.files);
                      }}
                    >
                      <div className="upload-icon">
                        <UploadCloud size={28} />
                      </div>
                      <div>
                        <h2>Give your documents a place to land.</h2>
                        <p>
                          Drop invoices here, or{" "}
                          <button
                            className="text-button"
                            onClick={() => input.current?.click()}
                          >
                            browse files
                          </button>
                        </p>
                        <small>
                          PDF, PNG, JPG · Up to 20 MB per file · 20 pages
                        </small>
                      </div>
                    </div>
                    <div className="process-card">
                      <span className="subtle-icon">
                        <Sparkles size={18} />
                      </span>
                      <h3>Extract. Check. Approve.</h3>
                      <p>We find the details. You make the final call.</p>
                      <div className="process-steps">
                        <span>01 Upload</span>
                        <ArrowRight size={13} />
                        <span>02 Review</span>
                        <ArrowRight size={13} />
                        <span>03 Export</span>
                      </div>
                    </div>
                  </section>
                </>
              )}
              <section className="panel documents-panel">
                <div className="panel-title">
                  <div>
                    <h2>
                      {screen === "overview"
                        ? "Recent documents"
                        : "All documents"}
                    </h2>
                    <p>Every record starts with a human review.</p>
                  </div>
                  {checked.length > 0 && canReview && (
                    <button
                      className="button secondary"
                      onClick={() => exportSelected()}
                    >
                      <ArrowDownToLine size={16} />
                      Export {checked.length} approved
                    </button>
                  )}
                </div>
                <div className="table-tools">
                  <div className="tabs">
                    {[
                      ["", "All documents"],
                      ["needs_review", "Needs review"],
                      ["approved", "Approved"],
                      ["failed", "Failed"],
                    ].map(([value, title]) => (
                      <button
                        key={value}
                        className={filter === value ? "active" : ""}
                        onClick={() => setFilter(value)}
                      >
                        {title}
                      </button>
                    ))}
                  </div>
                  <label className="search-input">
                    <Search size={16} />
                    <input
                      aria-label="Find a document"
                      placeholder="Find a document…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th className="check-col"></th>
                        <th>Document</th>
                        <th>Vendor</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((doc) => (
                        <tr key={doc.id}>
                          <td>
                            <input
                              type="checkbox"
                              aria-label={"Select " + doc.name}
                              disabled={
                                doc.review_status !== "approved" || !canReview
                              }
                              checked={checked.includes(doc.id)}
                              onChange={(e) =>
                                setChecked(
                                  e.target.checked
                                    ? [...checked, doc.id]
                                    : checked.filter((id) => id !== doc.id),
                                )
                              }
                            />
                          </td>
                          <td>
                            <button
                              className="document-link"
                              onClick={() => setSelected(doc.id)}
                            >
                              <span className="file-icon">
                                <FileText size={19} />
                              </span>
                              <span>
                                <strong>{doc.name}</strong>
                                <small>
                                  {doc.invoice_number ||
                                    new Date(
                                      doc.created_at,
                                    ).toLocaleDateString()}
                                  {doc.duplicate_of
                                    ? " · Possible duplicate"
                                    : ""}
                                </small>
                              </span>
                            </button>
                          </td>
                          <td>{doc.vendor_name || "Awaiting extraction"}</td>
                          <td className="amount">{money(doc.total)}</td>
                          <td>
                            <Badge
                              value={
                                [
                                  "queued",
                                  "processing",
                                  "failed",
                                  "partial",
                                  "needs_ocr",
                                ].includes(doc.status)
                                  ? doc.status
                                  : doc.review_status
                              }
                            />
                          </td>
                          <td>
                            <button
                              aria-label={"Review " + doc.name}
                              className="icon-button"
                              onClick={() => setSelected(doc.id)}
                            >
                              <ArrowRight size={17} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {shown.length === 0 && (
                  <div className="empty">
                    <FolderOpen size={32} />
                    <h3>
                      {docs.length
                        ? "No documents match this view."
                        : "Your first document starts here."}
                    </h3>
                    <p>Upload a sample invoice to try extraction and review.</p>
                    <button
                      className="button secondary"
                      onClick={() => input.current?.click()}
                    >
                      Choose a document
                    </button>
                  </div>
                )}
                <div className="table-footer">
                  {shown.length} document{shown.length !== 1 ? "s" : ""} shown ·
                  Latest 50 records
                  <span>
                    <ShieldCheck size={13} />
                    Approval required before export
                  </span>
                </div>
              </section>
              <div className="bottom-note">
                <span>Built for careful document work.</span>
                <span>
                  Local processing <span>•</span> Source-linked fields{" "}
                  <span>•</span> Review history
                </span>
              </div>
            </>
          )}
          <input
            ref={input}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            hidden
            onChange={(e) => e.target.files && upload(e.target.files)}
          />
        </div>
      </main>
    </div>
  );
}

function Stat({
  title,
  value,
  note,
  icon,
}: {
  title: string;
  value: string;
  note: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="stat">
      <div className="stat-top">
        <span>{title}</span>
        <span className="stat-icon">{icon}</span>
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function Login({
  onLogin,
}: {
  onLogin: (result: { user: User; csrf_token: string }) => void;
}) {
  const [username, setUsername] = useState("admin"),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="login-shell">
      <div className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <FileText />
          </span>
          DocuMind AI
        </div>
        <div>
          <div className="eyebrow">A LOCAL DOCUMENT WORKSPACE</div>
          <h1>
            Less searching.
            <br />
            More understanding.
          </h1>
          <p>
            Turn invoices into organized records, with the original always close
            at hand.
          </p>
          <div className="login-features">
            <span>
              <Check size={17} /> Local OCR and extraction
            </span>
            <span>
              <Check size={17} /> Evidence beside every field
            </span>
            <span>
              <Check size={17} /> Your review, your final decision
            </span>
          </div>
        </div>
        <small>Document processing · Invoice review · Search</small>
      </div>
      <div className="login-form-wrap">
        <form
          className="login-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              onLogin(
                await api("/auth/login", {
                  method: "POST",
                  body: JSON.stringify({ username, password }),
                }),
              );
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <span className="local-pill">
            <span className="status-dot" />
            Local workspace
          </span>
          <h2>Welcome to DocuMind.</h2>
          <p>Sign in to open your document workspace.</p>
          {error && (
            <div className="alert error" role="alert">
              {error}
            </div>
          )}
          <label>
            Username
            <input
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? "Signing in…" : "Open workspace"}
            <ArrowRight size={17} />
          </button>
          <small className="login-help">
            First run? Your local administrator password is in the .env file
            created during setup.
          </small>
        </form>
      </div>
    </div>
  );
}

function Review({
  id,
  user,
  onBack,
  onError,
  onNotice,
  onExport,
}: {
  id: string;
  user: User;
  onBack: () => void;
  onError: (m: string) => void;
  onNotice: (m: string) => void;
  onExport: (id: string) => void;
}) {
  const [doc, setDoc] = useState<Detail | null>(null),
    [form, setForm] = useState<Data | null>(null),
    [page, setPage] = useState(1),
    [evidence, setEvidence] = useState<Evidence | null>(null),
    [reason, setReason] = useState(""),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false),
    [suggestions, setSuggestions] = useState<
      { field: string; value: string; page_number: number; quote: string }[]
    >([]);
  const load = useCallback(async () => {
    const result = await api("/documents/" + id);
    setDoc(result);
    setForm(result.data);
    setDirty(false);
  }, [id]);
  useEffect(() => {
    load().catch((e) => onError(e.message));
  }, [load]);
  useEffect(() => {
    if (doc && ["queued", "processing"].includes(doc.status)) {
      const timer = setTimeout(
        () => load().catch((e) => onError(e.message)),
        2500,
      );
      return () => clearTimeout(timer);
    }
  }, [doc, load]);
  if (!doc) return <div className="loading-inline">Opening document…</div>;
  const canReview = user.role !== "uploader";
  const pages = doc.extraction?.pages || [],
    current = pages[page - 1];
  function change(key: string, value: string | null) {
    if (form) {
      setForm({ ...form, [key]: value });
      setDirty(true);
    }
  }
  function itemChange(index: number, key: keyof Item, value: string) {
    if (form) {
      const items = [...form.line_items];
      items[index] = { ...items[index], [key]: value };
      setForm({ ...form, line_items: items });
      setDirty(true);
    }
  }
  async function save() {
    if (!form || !doc) return;
    setBusy(true);
    try {
      await api("/invoices/" + id, {
        method: "PATCH",
        body: JSON.stringify({
          expected_version: doc.version,
          reason,
          data: form,
        }),
      });
      await load();
      setReason("");
      onNotice("Saved a new revision. Review its validation before approving.");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function decide(decision: string) {
    if (!doc) return;
    setBusy(true);
    try {
      await api("/invoices/" + id + "/approvals", {
        method: "POST",
        body: JSON.stringify({
          expected_version: doc.version,
          decision,
          reason,
          acknowledge_warnings: ack,
        }),
      });
      await load();
      setReason("");
      onNotice("Review decision recorded.");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back-link" onClick={onBack}>
        <ArrowLeft size={16} />
        Back to documents
      </button>
      <div className="page-heading review-heading">
        <div>
          <div className="eyebrow">DOCUMENT REVIEW</div>
          <h1>{doc.name}</h1>
          <p>
            {doc.kind} · Revision {doc.version || "pending"} ·{" "}
            {label(doc.index_status)}
          </p>
        </div>
        <div className="heading-actions">
          <Badge value={doc.review_status} />
          <a
            className="button secondary"
            href={"/api/v1/documents/" + id + "/original"}
          >
            <ArrowDownToLine size={16} />
            Original
          </a>
          {canReview && (
            <button
              className="button secondary"
              disabled={busy || ["queued", "processing"].includes(doc.status)}
              onClick={async () => {
                try {
                  await api("/documents/" + id + "/reprocess", {
                    method: "POST",
                  });
                  await load();
                  onNotice(
                    "New processing run queued. Existing review revisions are preserved.",
                  );
                } catch (e) {
                  onError((e as Error).message);
                }
              }}
            >
              <RefreshCw size={15} />
              Reprocess
            </button>
          )}
        </div>
      </div>
      {!form ? (
        <section className="panel empty">
          <Clock3 size={32} />
          <h2>
            {doc.status === "failed"
              ? "Processing needs attention."
              : "Your document is being prepared."}
          </h2>
          <p>
            {doc.job?.error ||
              "Extraction runs locally. This view refreshes automatically."}
          </p>
          <Badge value={doc.status} />
        </section>
      ) : (
        <div className="review-grid">
          <section className="panel preview-panel">
            <div className="preview-toolbar">
              <span>
                <FileText size={16} />
                Original document
              </span>
              <div>
                <button
                  aria-label="Previous page"
                  className="icon-button"
                  disabled={page <= 1}
                  onClick={() => {
                    setPage(page - 1);
                    setEvidence(null);
                  }}
                >
                  <ChevronLeft size={18} />
                </button>
                <span>
                  {page} / {pages.length}
                </span>
                <button
                  aria-label="Next page"
                  className="icon-button"
                  disabled={page >= pages.length}
                  onClick={() => {
                    setPage(page + 1);
                    setEvidence(null);
                  }}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
            <div className="page-canvas">
              {current && (
                <div className="page-image">
                  <img
                    src={`/api/v1/documents/${id}/pages/${page}`}
                    alt={`Original document page ${page}`}
                  />
                  {evidence && evidence.page_number === page && (
                    <svg
                      className="source-overlay"
                      viewBox={`0 0 ${current.width} ${current.height}`}
                      aria-label="Highlighted source"
                    >
                      <rect
                        x={evidence.box.x0 - 2}
                        y={evidence.box.top - 2}
                        width={evidence.box.x1 - evidence.box.x0 + 4}
                        height={evidence.box.bottom - evidence.box.top + 4}
                      />
                    </svg>
                  )}
                </div>
              )}
            </div>
            <div className="preview-note">
              {current?.extraction_method === "ocr"
                ? "OCR text · Check digits against the image"
                : "Native PDF text"}
              {evidence && <p>{evidence.quote}</p>}
            </div>
          </section>
          <section className="panel field-panel">
            <div className="panel-title">
              <div>
                <h2>Invoice details</h2>
                <p>Check each value against the original.</p>
              </div>
              {canReview ? (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const result = await api(
                        "/documents/" + id + "/suggestions",
                        { method: "POST" },
                      );
                      setSuggestions(result.suggestions);
                      onNotice(
                        result.suggestions.length
                          ? "Check suggestions against the original before applying."
                          : "The local model found no supported suggestions.",
                      );
                    } catch (e) {
                      onError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Sparkles size={14} />
                  Suggest details
                </button>
              ) : (
                <span className="small-pill">Human review</span>
              )}
            </div>
            {suggestions.length > 0 && (
              <div className="suggestions">
                <h3>Local model suggestions</h3>
                <p>
                  Source quotes are checked. You still need to verify the
                  meaning.
                </p>
                {suggestions.map((suggestion, index) => (
                  <div key={index}>
                    <strong>
                      {label(suggestion.field)}: {suggestion.value}
                    </strong>
                    <small>
                      Page {suggestion.page_number} · {suggestion.quote}
                    </small>
                    <button
                      className="text-button"
                      onClick={() => {
                        change(suggestion.field, suggestion.value);
                        setPage(suggestion.page_number);
                      }}
                    >
                      Apply to review form
                    </button>
                  </div>
                ))}
              </div>
            )}
            {doc.issues.length > 0 && (
              <div className="issue-list">
                {doc.issues.map((issue, i) => (
                  <div key={i} className={"issue " + issue.severity}>
                    <CircleAlert size={15} />
                    <span>
                      <strong>
                        {issue.field ? label(issue.field) + ": " : ""}
                      </strong>
                      {issue.message}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="field-grid">
              {fieldNames.map((key) => (
                <label key={key}>
                  <span>
                    {label(key)}
                    {doc.extraction?.invoice[key]?.evidence?.[0] && (
                      <button
                        type="button"
                        className="evidence-button"
                        aria-label={"Show source for " + label(key)}
                        onClick={() => {
                          const source =
                            doc.extraction!.invoice[key].evidence[0];
                          setPage(source.page_number);
                          setEvidence(source);
                        }}
                      >
                        <FileSearch size={13} />
                        Source
                      </button>
                    )}
                  </span>
                  <input
                    aria-label={label(key)}
                    disabled={!canReview}
                    type={key.endsWith("date") ? "date" : "text"}
                    value={String(form[key] ?? "")}
                    onChange={(e) => change(key, e.target.value || null)}
                  />
                </label>
              ))}
              <label className="full-width">
                Totals calculation
                <select
                  disabled={!canReview}
                  value={String(form.totals_mode)}
                  onChange={(e) => change("totals_mode", e.target.value)}
                >
                  <option value="unknown">Not yet checked</option>
                  <option value="tax_exclusive">
                    Subtotal − discount + tax + shipping
                  </option>
                  <option value="tax_inclusive">
                    Subtotal − discount + shipping (tax included)
                  </option>
                </select>
              </label>
            </div>
            <div className="items-heading">
              <h3>Line items</h3>
              {canReview && (
                <button
                  className="text-button"
                  onClick={() => {
                    setForm({
                      ...form,
                      line_items: [
                        ...form.line_items,
                        {
                          description: "",
                          quantity: "1",
                          unit_price: "0.00",
                          amount: "0.00",
                        },
                      ],
                    });
                    setDirty(true);
                  }}
                >
                  <Plus size={14} />
                  Add row
                </button>
              )}
            </div>
            <div className="items-scroll">
              <table className="items-table">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit price</th>
                    <th>Amount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {form.line_items.map((item, index) => (
                    <tr key={index}>
                      {(
                        [
                          "description",
                          "quantity",
                          "unit_price",
                          "amount",
                        ] as const
                      ).map((key) => (
                        <td key={key}>
                          <input
                            aria-label={`Row ${index + 1} ${label(key)}`}
                            disabled={!canReview}
                            value={item[key]}
                            onChange={(e) =>
                              itemChange(index, key, e.target.value)
                            }
                          />
                        </td>
                      ))}
                      <td>
                        {canReview && (
                          <button
                            className="icon-button"
                            aria-label={`Remove row ${index + 1}`}
                            onClick={() => {
                              setForm({
                                ...form,
                                line_items: form.line_items.filter(
                                  (_, i) => i !== index,
                                ),
                              });
                              setDirty(true);
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="table-caution">
              Verify every row. Complex or wrapped tables may need manual
              correction.
            </p>
            {canReview && (
              <div className="review-actions">
                <label>
                  Review note
                  <textarea
                    value={reason}
                    placeholder="What did you check or correct?"
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={ack}
                    onChange={(e) => setAck(e.target.checked)}
                  />
                  I checked the warnings against the source.
                </label>
                <div>
                  <button
                    className="button secondary"
                    disabled={busy || !dirty || reason.length < 3}
                    onClick={save}
                  >
                    Save revision
                  </button>
                  <button
                    className="button primary"
                    disabled={
                      busy ||
                      dirty ||
                      reason.length < 5 ||
                      doc.review_status === "approved"
                    }
                    onClick={() => decide("approved")}
                  >
                    <CheckCheck size={16} />
                    Approve
                  </button>
                  <button
                    className="button danger-text"
                    disabled={
                      busy ||
                      dirty ||
                      reason.length < 5 ||
                      doc.review_status === "rejected"
                    }
                    onClick={() => decide("rejected")}
                  >
                    Reject
                  </button>
                </div>
                {dirty && (
                  <small>
                    Save changes before making an approval decision.
                  </small>
                )}
                {doc.review_status === "approved" && !dirty && (
                  <button
                    className="button secondary"
                    onClick={() => onExport(id)}
                  >
                    <ArrowDownToLine size={16} />
                    Export approved revision
                  </button>
                )}
              </div>
            )}
            <details className="revision-history">
              <summary>Revision history ({doc.revisions.length})</summary>
              {doc.revisions.map((revision) => (
                <div key={revision.version}>
                  <strong>Revision {revision.version}</strong>
                  <p>{revision.reason}</p>
                  <small>
                    {new Date(revision.created_at).toLocaleString()}
                  </small>
                </div>
              ))}
            </details>
          </section>
        </div>
      )}
    </>
  );
}

function SearchPage({
  onOpen,
  onError,
}: {
  onOpen: (id: string) => void;
  onError: (m: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [mode, setMode] = useState("keyword"),
    [results, setResults] = useState<Source[]>([]),
    [answer, setAnswer] = useState<{
      answer: string;
      citations: Source[];
      abstained: boolean;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [searched, setSearched] = useState(false);
  async function submit(ask = false) {
    setBusy(true);
    setAnswer(null);
    try {
      if (ask) {
        setAnswer(
          await api("/questions", {
            method: "POST",
            body: JSON.stringify({ question: query }),
          }),
        );
      } else {
        const result = await api(
          "/search?q=" + encodeURIComponent(query) + "&mode=" + mode,
        );
        setResults(result.items);
        setSearched(true);
      }
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">FIND THE EVIDENCE</div>
          <h1>Answers start with your documents.</h1>
          <p>
            Search extracted text, or ask a question using the optional local
            model.
          </p>
        </div>
        <FileSearch className="heading-icon" size={42} />
      </div>
      <section className="panel search-panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label className="large-search">
            <Search size={21} />
            <input
              aria-label="Search documents"
              placeholder="Try a vendor, invoice number, or service description…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              minLength={2}
              maxLength={500}
            />
          </label>
          <div className="search-actions">
            <div className="tabs">
              {["keyword", "semantic"].map((value) => (
                <button
                  type="button"
                  key={value}
                  className={mode === value ? "active" : ""}
                  onClick={() => setMode(value)}
                >
                  {label(value)} search
                </button>
              ))}
            </div>
            <div>
              <button
                className="button secondary"
                type="button"
                disabled={busy || query.length < 3}
                onClick={() => submit(true)}
              >
                <Sparkles size={16} />
                Ask local AI
              </button>
              <button
                className="button primary"
                disabled={busy || query.length < 2}
              >
                {busy ? "Working locally…" : "Search"}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </form>
        <p className="search-note">
          AI answers are experimental. Check cited pages. Use approved records
          for financial totals.
        </p>
      </section>
      {answer && (
        <section className="panel answer-card">
          <span className="eyebrow">
            {answer.abstained ? "INSUFFICIENT EVIDENCE" : "LOCAL MODEL ANSWER"}
          </span>
          <p>{answer.answer}</p>
          {answer.citations.map((source) => (
            <button
              className="citation"
              key={source.id}
              onClick={() => onOpen(source.document_id)}
            >
              <FileText size={15} />
              {source.name} · page {source.page_number}
            </button>
          ))}
        </section>
      )}
      <div className="search-results">
        {results.map((source) => (
          <article className="panel result-card" key={source.id}>
            <div>
              <span className="file-icon">
                <FileText size={18} />
              </span>
              <div>
                <h3>{source.name}</h3>
                <small>Page {source.page_number}</small>
              </div>
              <button
                className="icon-button"
                aria-label={"Open " + source.name}
                onClick={() => onOpen(source.document_id)}
              >
                <ArrowRight size={18} />
              </button>
            </div>
            <p>{source.text}</p>
          </article>
        ))}
        {searched && !results.length && !busy && (
          <div className="empty">
            <Search size={32} />
            <h3>No matching evidence found.</h3>
            <p>Try a specific phrase or a different search mode.</p>
          </div>
        )}
      </div>
    </>
  );
}

function History({ kind }: { kind: "exports" | "audit" }) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api("/" + kind)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [kind]);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORKSPACE HISTORY</div>
          <h1>
            {kind === "exports"
              ? "Approved records, ready to use."
              : "Every decision has a history."}
          </h1>
          <p>
            {kind === "exports"
              ? "Exports preserve the revision that was approved."
              : "A record of processing, changes, and review decisions."}
          </p>
        </div>
      </div>
      <section className="panel">
        {error && <div className="alert error">{error}</div>}
        {rows.length ? (
          rows.map((row) => (
            <div className="history-row" key={String(row.id)}>
              <span className="file-icon">
                {kind === "exports" ? (
                  <ArrowDownToLine size={19} />
                ) : (
                  <Clock3 size={19} />
                )}
              </span>
              <div>
                <strong>
                  {kind === "exports"
                    ? `${row.count} approved invoice(s) · ${String(row.format).toUpperCase()}`
                    : label(String(row.action))}
                </strong>
                <small>
                  {new Date(String(row.created_at)).toLocaleString()}
                </small>
                {kind === "audit" && (
                  <small>{JSON.stringify(row.details)}</small>
                )}
              </div>
              {kind === "exports" && (
                <a
                  className="button secondary"
                  href={"/api/v1/exports/" + row.id + "/download"}
                >
                  Download
                  <ArrowDownToLine size={15} />
                </a>
              )}
            </div>
          ))
        ) : (
          <div className="empty">
            <Clock3 size={32} />
            <h3>No history yet.</h3>
            <p>Your workspace activity will appear here.</p>
          </div>
        )}
      </section>
    </>
  );
}

function Team({
  onError,
  onNotice,
}: {
  onError: (m: string) => void;
  onNotice: (m: string) => void;
}) {
  const [rows, setRows] = useState<User[]>([]),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [role, setRole] = useState("uploader");
  const refresh = () =>
    api("/users")
      .then(setRows)
      .catch((e) => onError(e.message));
  useEffect(() => {
    refresh();
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">TEAM ACCESS</div>
          <h1>A clear role for every reviewer.</h1>
          <p>
            Uploaders see their own documents. Reviewers and admins review the
            workspace.
          </p>
        </div>
      </div>
      <section className="panel team-panel">
        <h2>Add a local account</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("/users", {
                method: "POST",
                body: JSON.stringify({ username, password, role }),
              });
              setUsername("");
              setPassword("");
              refresh();
              onNotice("Local account created.");
            } catch (err) {
              onError((err as Error).message);
            }
          }}
        >
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={3}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={12}
              autoComplete="new-password"
              required
            />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="uploader">Uploader</option>
              <option value="reviewer">Reviewer</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <button className="button primary">Create account</button>
        </form>
        {rows.map((row) => (
          <div className="history-row" key={row.id}>
            <span className="avatar">
              {row.username.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{row.username}</strong>
              <small>{label(row.role)}</small>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
