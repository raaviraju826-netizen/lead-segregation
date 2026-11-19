import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Search, X, ShieldCheck, ShieldAlert } from "lucide-react";
import { api, errorMessage } from "../services/api";
import { Score, StatusBadge, fmtDate, pct, PriorityBadge, IndustryBadge } from "./badges";
import { EmptyState, ErrorBox, Loading } from "./ui";

const STATUSES = ["Classified", "Needs Review", "Other / Unknown", "Not a Lead", "Suspicious — Review Required"];
const INDUSTRIES = [
  ["manufacturing", "Manufacturing"],
  ["education", "Education & EdTech"],
  ["it-software", "IT & Software"],
  ["logistics", "Logistics & Transportation"],
];
const SUB_INDUSTRIES = [
  "Automotive Manufacturing", "Textile Manufacturing", "Electronics Manufacturing", "Industrial Machinery", "Chemical Manufacturing", "Other Manufacturing",
  "Schools", "Colleges and Universities", "Coaching Institutes", "EdTech Platforms", "Training Institutes",
  "Custom Software Development", "SaaS", "Cloud and DevOps", "AI and Data", "Cybersecurity", "IT Services",
  "Freight Transportation", "Courier Services", "Warehousing", "Fleet Management", "Supply Chain Management", "General",
];

const SORT_KEYS = {
  email_date: "date", company_name: "company", industry: "industry", status: "status", confidence: "confidence",
  company_trust_score: "company_trust", email_trust_score: "email_trust", relevance_score: "relevance", subject: "subject",
};

function VerdictCell({ row }) {
  const isFake = row.verdict === "FAKE";
  const kws = isFake ? row.fake_keywords || [] : row.real_keywords || [];
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        {isFake ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-rose-500 to-red-600 px-2.5 py-0.5 text-xs font-extrabold text-white shadow-2xs">
            <ShieldAlert className="h-3.5 w-3.5" /> FAKE ({row.real_fake_score}%)
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-emerald-500 to-teal-600 px-2.5 py-0.5 text-xs font-extrabold text-white shadow-2xs">
            <ShieldCheck className="h-3.5 w-3.5" /> REAL ({row.real_fake_score}%)
          </span>
        )}
      </div>
      {kws.length > 0 && (
        <div className="max-w-[210px] truncate text-[11px] font-medium text-slate-600" title={kws.join(", ")}>
          Keywords: <b className={isFake ? "text-rose-700" : "text-emerald-700"}>{kws.slice(0, 3).join(", ")}</b>
        </div>
      )}
    </div>
  );
}

function buildColumns(showIndustry) {
  const cols = [
    { accessorKey: "verdict", header: "Real / Fake & Keywords", enableSorting: false, cell: (c) => <VerdictCell row={c.row.original} /> },
    { accessorKey: "company_name", header: "Company", cell: (c) => <div><div className="font-bold text-slate-900">{c.getValue() || <span className="text-slate-400">Unknown</span>}</div><div className="text-xs text-indigo-600">{c.row.original.website?.replace(/^https?:\/\//, "")}</div></div> },
    { accessorKey: "contact_name", header: "Contact", enableSorting: false, cell: (c) => <div><div className="font-medium text-slate-800">{c.getValue() || "—"}</div><div className="text-xs text-slate-500">{c.row.original.email}</div></div> },
    { accessorKey: "subject", header: "Subject", cell: (c) => <div className="max-w-[220px] truncate font-medium text-slate-800" title={c.getValue()}>{c.getValue() || "(no subject)"}</div> },
  ];
  if (showIndustry) cols.push({ accessorKey: "industry", header: "Industry", cell: (c) => <IndustryBadge industry={c.getValue()} /> });
  cols.push(
    { accessorKey: "sub_industry", header: "Sub-industry", enableSorting: false, cell: (c) => c.getValue() || "—" },
    { accessorKey: "confidence", header: "Accuracy %", cell: (c) => <span className="rounded-lg bg-indigo-50 px-2 py-1 text-xs font-extrabold text-indigo-700 ring-1 ring-inset ring-indigo-200">{pct(c.getValue())}</span> },
    { accessorKey: "company_trust_score", header: "Company trust", cell: (c) => <Score value={c.getValue()} title={c.row.original.company_trust_label} /> },
    { accessorKey: "email_trust_score", header: "Email trust", cell: (c) => <Score value={c.getValue()} title={`${c.row.original.email_risk} risk`} /> },
    { accessorKey: "relevance_score", header: "Relevance", cell: (c) => <div className="space-y-1"><Score value={c.getValue()} /><PriorityBadge priority={c.row.original.priority} /></div> },
    { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue()} /> },
    { accessorKey: "email_date", header: "Date", cell: (c) => <span className="whitespace-nowrap text-xs text-slate-600">{fmtDate(c.getValue())}</span> },
  );
  return cols;
}

function Select({ value, onChange, label, options }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="rounded-xl border border-indigo-200 bg-white px-2.5 py-2 text-xs font-medium text-slate-700 shadow-2xs">
      <option value="">{label}</option>
      {options.map((o) => (Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o} value={o}>{o}</option>))}
    </select>
  );
}

/** Server-side paginated / sorted / filtered lead table (TanStack Table). */
export default function LeadsTable({ fetcher, deps = [], filters = [], emptyHint, pageSize = 15, exportContext = {} }) {
  const nav = useNavigate();
  const [q, setQ] = useState({
    search: "", verdict: "", industry: "", sub_industry: "", status: "", priority: "", company_trust: "", email_risk: "", date_from: "", date_to: "",
  });
  const [debounced, setDebounced] = useState("");
  const [sort, setSort] = useState({ id: "email_date", desc: true });
  const [page, setPage] = useState(1);
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => { const t = setTimeout(() => setDebounced(q.search), 300); return () => clearTimeout(t); }, [q.search]);
  useEffect(() => setPage(1), [debounced, q.verdict, q.industry, q.sub_industry, q.status, q.priority, q.company_trust, q.email_risk, q.date_from, q.date_to, ...deps]);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetcher({ ...q, search: debounced, page, page_size: pageSize, sort: SORT_KEYS[sort.id] || "date", order: sort.desc ? "desc" : "asc" })
      .then((data) => !cancelled && setState({ loading: false, error: null, data }))
      .catch((e) => !cancelled && setState({ loading: false, error: errorMessage(e), data: null }));
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced, q.verdict, q.industry, q.sub_industry, q.status, q.priority, q.company_trust, q.email_risk, q.date_from, q.date_to, page, sort, pageSize, ...deps]);

  const showIndustry = filters.includes("industry");
  const columns = useMemo(() => buildColumns(showIndustry), [showIndustry]);
  const table = useReactTable({ data: state.data?.items || [], columns, getCoreRowModel: getCoreRowModel(), manualSorting: true, manualPagination: true });
  const set = (k) => (v) => setQ((s) => ({ ...s, [k]: v }));
  const active = Object.values(q).some(Boolean);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-indigo-400" />
          <input value={q.search} onChange={(e) => set("search")(e.target.value)} placeholder="Search company, contact, email, subject, keyword…" aria-label="Search" className="w-full rounded-xl border border-indigo-200 py-2 pl-9 pr-3 text-sm shadow-2xs" />
        </div>
        <Select value={q.verdict} onChange={set("verdict")} label="Real & Fake (All)" options={[["REAL", "✓ Only REAL Mails"], ["FAKE", "✗ Only FAKE Mails"]]} />
        {filters.includes("industry") && <Select value={q.industry} onChange={set("industry")} label="All industries" options={INDUSTRIES} />}
        <Select value={q.sub_industry} onChange={set("sub_industry")} label="All sub-industries" options={SUB_INDUSTRIES} />
        {filters.includes("status") && <Select value={q.status} onChange={set("status")} label="All statuses" options={STATUSES} />}
        {filters.includes("priority") && <Select value={q.priority} onChange={set("priority")} label="All priorities" options={["High", "Medium", "Low"]} />}
        <input type="date" value={q.date_from} onChange={(e) => set("date_from")(e.target.value)} title="From date" aria-label="From date" className="rounded-xl border border-indigo-200 bg-white px-2.5 py-1.5 text-xs text-slate-700" />
        <input type="date" value={q.date_to} onChange={(e) => set("date_to")(e.target.value)} title="To date" aria-label="To date" className="rounded-xl border border-indigo-200 bg-white px-2.5 py-1.5 text-xs text-slate-700" />
        {active && (
          <button onClick={() => setQ({ search: "", verdict: "", industry: "", sub_industry: "", status: "", priority: "", company_trust: "", email_risk: "", date_from: "", date_to: "" })} className="inline-flex cursor-pointer items-center gap-1 rounded-xl bg-rose-50 px-2.5 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100">
            <X className="h-3.5 w-3.5" /> Reset
          </button>
        )}
        {exportContext?.source && (
          <div className="ml-auto flex items-center gap-1.5">
            <button onClick={() => api.download("csv", { source: exportContext.source, industry: exportContext.industry || q.industry || undefined })} className="inline-flex cursor-pointer items-center gap-1 rounded-xl border border-indigo-200 bg-white px-2.5 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-50">
              <Download className="h-3.5 w-3.5" /> CSV
            </button>
            <button onClick={() => api.download("excel", { source: exportContext.source, industry: exportContext.industry || q.industry || undefined })} className="inline-flex cursor-pointer items-center gap-1 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-2.5 py-1.5 text-xs font-bold text-white shadow-xs hover:opacity-95">
              <Download className="h-3.5 w-3.5" /> Excel
            </button>
          </div>
        )}
      </div>

      {state.error && <ErrorBox message={state.error} onRetry={() => setPage((p) => p)} />}
      <div className="overflow-x-auto rounded-2xl border border-indigo-100 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-gradient-to-r from-indigo-50/90 via-sky-50/80 to-fuchsia-50/80 text-xs uppercase tracking-wide text-indigo-900">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const can = h.column.columnDef.enableSorting !== false;
                  const s = sort.id === h.column.id;
                  return (
                    <th key={h.id} className="whitespace-nowrap px-3.5 py-3 font-bold">
                      {can ? (
                        <button className="inline-flex cursor-pointer items-center gap-1 hover:text-indigo-600" onClick={() => setSort((p) => (p.id === h.column.id ? { id: p.id, desc: !p.desc } : { id: h.column.id, desc: true }))}>
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {s && (sort.desc ? <ArrowDown className="h-3.5 w-3.5 text-fuchsia-600" /> : <ArrowUp className="h-3.5 w-3.5 text-fuchsia-600" />)}
                        </button>
                      ) : flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-indigo-50">
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} onClick={() => nav(`/leads/${r.original.id}`)} className="cursor-pointer transition-colors hover:bg-gradient-to-r hover:from-indigo-50/70 hover:via-sky-50/50 hover:to-fuchsia-50/60">
                {r.getVisibleCells().map((c) => <td key={c.id} className="px-3.5 py-3 align-top">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {state.loading && !state.data && <Loading />}
        {!state.loading && !state.error && state.data?.items.length === 0 && (
          <EmptyState title={active ? "No leads match these filters" : "No leads yet"} hint={active ? "Try clearing a filter." : emptyHint} />
        )}
      </div>

      {state.data && (
        <div className="flex items-center justify-between text-sm text-slate-600">
          <span>{state.data.total} result{state.data.total === 1 ? "" : "s"}{state.loading && " · updating…"}</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-lg border border-slate-300 bg-white p-1.5 disabled:opacity-40" aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
            <span>Page {state.data.page} / {state.data.pages}</span>
            <button disabled={page >= state.data.pages} onClick={() => setPage(page + 1)} className="rounded-lg border border-slate-300 bg-white p-1.5 disabled:opacity-40" aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}
