import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, ShieldAlert, Building2, Mail, Sparkles, UserCheck, XCircle, FileText, Paperclip } from "lucide-react";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, ErrorBox, Loading } from "../components/ui";
import { Badge, PriorityBadge, RiskBadge, Score, StatusBadge, TrustBadge, fmtDate, pct } from "../components/badges";

const TAXONOMY = {
  Manufacturing: ["Automotive Manufacturing", "Textile Manufacturing", "Electronics Manufacturing", "Industrial Machinery", "Chemical Manufacturing", "Other Manufacturing", "General"],
  Education: ["Schools", "Colleges and Universities", "Coaching Institutes", "EdTech Platforms", "Training Institutes", "General"],
  "IT & Software": ["Custom Software Development", "SaaS", "Cloud and DevOps", "AI and Data", "Cybersecurity", "IT Services", "General"],
  "Logistics & Transportation": ["Freight Transportation", "Courier Services", "Warehousing", "Fleet Management", "Supply Chain Management", "General"],
  "Other / Unknown": [],
};

export default function LeadDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: lead, loading, error, reload } = useApi(() => api.lead(id), [id]);

  const [industry, setIndustry] = useState("");
  const [subIndustry, setSubIndustry] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyDecision, setCompanyDecision] = useState("");
  const [reviewer, setReviewer] = useState("reviewer");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (lead) {
      setIndustry(lead.industry || "Other / Unknown");
      setSubIndustry(lead.sub_industry || "General");
      setCompanyName(lead.company_name || "");
      setCompanyDecision(lead.extracted?.company_review || "");
    }
  }, [lead]);

  const submitReview = async (extra = {}) => {
    setSaving(true); setMsg(null);
    try {
      const subs = TAXONOMY[industry] || [];
      const payload = {
        reviewer: reviewer || "reviewer",
        industry,
        sub_industry: subs.length ? (subs.includes(subIndustry) ? subIndustry : "General") : null,
        company_name: companyName || null,
        company_decision: companyDecision || null,
        notes: notes || null,
        ...extra,
      };
      await api.review(id, payload);
      setMsg({ type: "ok", text: "Review saved. Confirmed industry examples are indexed into the RAG knowledge base." });
      setNotes("");
      reload();
    } catch (e) {
      setMsg({ type: "err", text: errorMessage(e) });
    } finally {
      setSaving(false);
    }
  };

  if (loading && !lead) return <Loading label="Loading email & assessment details…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!lead) return null;

  const cls = lead.classification || {};
  const ct = lead.company_trust || {};
  const et = lead.email_trust || {};
  const lr = lead.lead_relevance || {};
  const ex = lead.extracted || {};
  const subs = TAXONOMY[industry] || [];

  const evByField = {};
  (ex.evidence || []).forEach((e) => { evByField[e.field] = e; });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button onClick={() => nav(-1)} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={lead.status} />
          <PriorityBadge priority={lead.priority} />
          <TrustBadge label={lead.company_trust_label} />
          <RiskBadge risk={lead.email_risk} />
          {lead.reviewed && <Badge color="green">Human Reviewed</Badge>}
        </div>
      </div>

      {/* Automatic REAL vs FAKE Verdict & Keyword Banner */}
      <div
        className={`rounded-2xl border p-5 shadow-md ${
          lead.verdict === "FAKE"
            ? "border-rose-300 bg-gradient-to-r from-rose-50 via-pink-50 to-orange-50 text-rose-950"
            : "border-emerald-300 bg-gradient-to-r from-emerald-50 via-teal-50 to-cyan-50 text-emerald-950"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1 text-sm font-extrabold text-white shadow-sm ${
                  lead.verdict === "FAKE" ? "bg-gradient-to-r from-rose-600 to-red-600" : "bg-gradient-to-r from-emerald-600 to-teal-600"
                }`}
              >
                {lead.verdict === "FAKE" ? "✗ FAKE / SCAM MAIL DETECTED" : "✓ REAL CLIENT MAIL VERIFIED"}
              </span>
              <span className="rounded-xl bg-white px-3 py-1 text-sm font-extrabold shadow-2xs">
                Real/Fake Score: {lead.real_fake_score}%
              </span>
              <span className="rounded-xl bg-indigo-600 px-3 py-1 text-sm font-extrabold text-white shadow-2xs">
                Industry: {lead.industry} · Accuracy: {lead.accuracy_score}%
              </span>
            </div>
            <p className="text-xs font-medium">{lead.verdict_reason}</p>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {lead.verdict === "FAKE"
                ? (lead.fake_keywords || []).map((kw, i) => (
                    <span key={i} className="rounded-full bg-rose-200/80 px-2.5 py-0.5 text-xs font-bold text-rose-900">
                      Fake Keyword: “{kw}”
                    </span>
                  ))
                : (lead.real_keywords || []).map((kw, i) => (
                    <span key={i} className="rounded-full bg-emerald-200/80 px-2.5 py-0.5 text-xs font-bold text-emerald-900">
                      Real Keyword: “{kw}”
                    </span>
                  ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              ["manufacturing", "Manufacturing"],
              ["education", "Education & EdTech"],
              ["it-software", "IT & Software"],
              ["logistics", "Logistics & Transport"],
            ].map(([s, label]) => (
              <button
                key={s}
                onClick={() => nav(`/industry/${s}`)}
                className="cursor-pointer rounded-xl border border-indigo-200 bg-white px-3 py-1.5 text-xs font-bold text-indigo-800 shadow-2xs hover:bg-indigo-50"
              >
                {label} (Real vs Fake)
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Header overview */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
              {lead.source === "demo" ? "Synthetic Demo Email" : "Authorized Gmail Message"} · {fmtDate(lead.email_date)}
            </div>
            <h1 className="text-lg font-bold text-slate-900">{lead.subject || "(no subject)"}</h1>
            <div className="text-sm text-slate-600">
              <div>
                From: <b>{lead.sender_name || "—"}</b> &lt;{lead.email}&gt;
                {lead.reply_to && lead.reply_to !== lead.email && <span className="ml-2 text-amber-700">(Reply-To: {lead.reply_to})</span>}
              </div>
              <div className="mt-0.5 text-xs text-slate-500">
                To: <b className="font-mono text-indigo-700">{lead.headers?.To || "rajurajuu970@gmail.com"}</b>
              </div>
            </div>
          </div>

          {/* 4 strictly separate colorful scores */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-violet-100/80 px-3.5 py-2.5 shadow-xs">
              <div className="text-[11px] font-bold uppercase text-indigo-700">Classification Conf.</div>
              <div className="text-xl font-extrabold text-indigo-950">{pct(cls.confidence || 0)}</div>
              <div className="text-[11px] font-medium text-indigo-700">{lead.industry}</div>
            </div>
            <div className="rounded-xl border border-sky-200 bg-gradient-to-br from-sky-50 to-cyan-100/80 px-3.5 py-2.5 shadow-xs">
              <div className="text-[11px] font-bold uppercase text-sky-700">Company Trust</div>
              <div className="text-xl font-extrabold text-sky-950">{ct.score ?? 0}/100</div>
              <div className="text-[11px] font-medium text-sky-700">{ct.label}</div>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-100/80 px-3.5 py-2.5 shadow-xs">
              <div className="text-[11px] font-bold uppercase text-emerald-700">Email Authenticity</div>
              <div className="text-xl font-extrabold text-emerald-950">{et.score ?? 0}/100</div>
              <div className="text-[11px] font-medium text-emerald-700">{et.risk} Risk</div>
            </div>
            <div className="rounded-xl border border-fuchsia-200 bg-gradient-to-br from-fuchsia-50 to-pink-100/80 px-3.5 py-2.5 shadow-xs">
              <div className="text-[11px] font-bold uppercase text-fuchsia-700">Lead Relevance</div>
              <div className="text-xl font-extrabold text-fuchsia-950">{lr.score ?? 0}/100</div>
              <div className="text-[11px] font-medium text-fuchsia-700">{lr.priority} Priority</div>
            </div>
          </div>
        </div>

        {lead.status_reasons?.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
            {lead.status_reasons.map((r, i) => (
              <span key={i} className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-900 ring-1 ring-inset ring-amber-200">
                <ShieldAlert className="h-3.5 w-3.5 text-amber-600" /> {r}
              </span>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Original Email Content */}
        <Card title="Original Email Content" subtitle={`Message ID: ${lead.gmail_message_id} · Thread: ${lead.thread_id || "—"}`}>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-800">
            {lead.body || "(empty body)"}
          </pre>
          {lead.attachments?.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <Paperclip className="h-3.5 w-3.5" /> Attachments (metadata only; never executed):
              {lead.attachments.map((a, i) => (
                <Badge key={i} color="amber">{a.filename} ({a.mime_type})</Badge>
              ))}
            </div>
          )}
        </Card>

        {/* Extracted Sender & Company Information + Evidence Source */}
        <Card title="Extracted Information & Evidence Sources" subtitle="Every field tracks where in the email it was found">
          <dl className="divide-y divide-slate-100 text-sm">
            {[
              ["Company Name", lead.company_name, evByField.company_name?.source],
              ["Contact Person", lead.contact_name, evByField.contact_name?.source],
              ["Job Title", lead.job_title, evByField.job_title?.source],
              ["Sender Email", lead.email, `domain: ${ex.sender_domain || "—"}${ex.free_mail ? " (free-mail)" : ""}`],
              ["Phone Number", lead.phone, evByField.phone?.source],
              ["Website", lead.website, evByField.website?.source],
              ["Requested Service / Product (what they want)", ex.requested_service || cls.interest_area, evByField.requested_service?.source],
              ["Sender Business Description (what they are)", ex.business_description, evByField.business_description?.source],
              ["Message Classification Type", lead.lead_type, ex.message_type_detail],
            ].map(([label, val, src]) => (
              <div key={label} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                <dt className="text-xs font-medium text-slate-500">{label}</dt>
                <dd className="text-right font-medium text-slate-900">
                  {val || <span className="text-slate-400">Not found</span>}
                  {src && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-normal text-slate-600">{src}</span>}
                </dd>
              </div>
            ))}
          </dl>
        </Card>

        {/* AI Industry Classification & RAG Evidence */}
        <Card
          title="AI Industry Classification & RAG Retrieval"
          subtitle={`Method: ${cls.method} (${cls.llm_used ? "LLM + RAG" : "Offline Heuristic + RAG — no LLM call claimed"})`}
        >
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3">
              <div>
                <div className="text-xs text-slate-500">Sender Industry</div>
                <div className="font-bold text-slate-900">{lead.industry}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Sub-industry</div>
                <div className="font-bold text-slate-900">{lead.sub_industry || "—"}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Requested Interest Area</div>
                <div className="font-medium text-indigo-700">{cls.interest_area || "—"}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Confidence Formula</div>
                <div className="text-xs text-slate-700">
                  0.6×{Number(cls.llm_confidence || 0).toFixed(2)} + 0.4×{Number(cls.retrieval_similarity || 0).toFixed(2)} = <b>{Number(cls.confidence || 0).toFixed(2)}</b>
                </div>
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold uppercase text-slate-500">Decision Reasoning</div>
              <p className="mt-1 text-slate-700">{cls.reason}</p>
            </div>

            {cls.evidence?.length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase text-slate-500">Supporting Evidence Phrases</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {cls.evidence.map((ev, i) => (
                    <Badge key={i} color="blue">{ev}</Badge>
                  ))}
                </div>
              </div>
            )}

            {cls.retrieved_chunks?.length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase text-slate-500">Top {cls.retrieved_chunks.length} ChromaDB Retrieved Knowledge Chunks</div>
                <div className="mt-1.5 max-h-48 space-y-1.5 overflow-y-auto pr-1">
                  {cls.retrieved_chunks.map((c, i) => (
                    <div key={c.id || i} className="rounded border border-slate-200 bg-slate-50 p-2 text-xs">
                      <div className="flex items-center justify-between font-medium text-slate-800">
                        <span>#{i + 1} · {c.industry}{c.sub_industry ? ` / ${c.sub_industry}` : " (Overview)"}</span>
                        <span className="tabular-nums text-indigo-700">sim {Number(c.similarity).toFixed(2)}</span>
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-slate-600">{c.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Lead Relevance Assessment */}
        <Card title={`Lead Relevance Score (${lr.score ?? 0}/100 · ${lr.priority} Priority)`} subtitle={`Classified message type: ${lr.lead_type}`}>
          <div className="space-y-2.5">
            {(lr.breakdown || []).map((b) => (
              <div key={b.name} className="rounded-lg border border-slate-100 p-2.5 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">{b.name}</span>
                  <span className="font-semibold tabular-nums text-slate-900">{b.points} / {b.weight}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{b.detail}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Company Trust Assessment */}
        <Card title={`Company Trust Score (${ct.score ?? 0}/100 · ${ct.label})`} subtitle={ct.note}>
          <div className="space-y-2">
            {(ct.signals || []).map((s) => (
              <div key={s.name} className="rounded-lg border border-slate-100 p-2.5 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-800">{s.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge color={s.status === "Pass" || s.status === "Verified" ? "green" : s.status === "Conflict" ? "red" : s.status === "Unknown" ? "slate" : "blue"}>
                      {s.status}
                    </Badge>
                    <span className="w-14 text-right font-semibold tabular-nums">{s.points} / {s.weight}</span>
                  </div>
                </div>
                <div className="mt-1 text-xs text-slate-500">{s.detail}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Email Authenticity Assessment */}
        <Card title={`Email Authenticity Score (${et.score ?? 0}/100 · ${et.risk} Risk)`} subtitle="SPF, DKIM & DMARC are only reported when present in trusted Gmail headers">
          <div className="space-y-2">
            {(et.signals || []).map((s, idx) => (
              <div key={idx} className="rounded-lg border border-slate-100 p-2.5 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-800">{s.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge color={s.status === "Pass" ? "green" : s.status === "Unknown" ? "slate" : s.status === "Fail" || s.status === "Warning" ? "red" : "amber"}>
                      {s.status}
                    </Badge>
                    {s.penalty > 0 && <span className="text-xs font-semibold text-red-600">−{s.penalty}</span>}
                  </div>
                </div>
                <div className="mt-1 text-xs text-slate-500">{s.detail}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Human Review & Correction Controls */}
      <Card
        title="Human Review & Correction Controls"
        subtitle="Confirm or override industry classification, company details, or lead validity. Only human-confirmed classifications are added to the RAG example store."
      >
        {msg && (
          <div className={`mb-4 rounded-lg border p-3 text-sm ${msg.type === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`}>
            {msg.text}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block text-xs font-medium text-slate-700">
            Industry
            <select value={industry} onChange={(e) => { setIndustry(e.target.value); setSubIndustry("General"); }} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
              {Object.keys(TAXONOMY).map((ind) => <option key={ind} value={ind}>{ind}</option>)}
            </select>
          </label>

          <label className="block text-xs font-medium text-slate-700">
            Sub-industry
            <select value={subIndustry} onChange={(e) => setSubIndustry(e.target.value)} disabled={subs.length === 0} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:bg-slate-100">
              {subs.length === 0 ? <option value="">N/A</option> : subs.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>

          <label className="block text-xs font-medium text-slate-700">
            Suggested Company Name
            <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Company name" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </label>

          <label className="block text-xs font-medium text-slate-700">
            Company Info Decision
            <select value={companyDecision} onChange={(e) => setCompanyDecision(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="">No change</option>
              <option value="confirm">Confirm suggested company info</option>
              <option value="reject">Reject suggested company info</option>
            </select>
          </label>
        </div>

        <div className="mt-3 grid gap-4 sm:grid-cols-3">
          <label className="block text-xs font-medium text-slate-700">
            Reviewer Name
            <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </label>
          <label className="block text-xs font-medium text-slate-700 sm:col-span-2">
            Review Notes
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional rationale for audit trail…" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button variant="primary" disabled={saving} onClick={() => submitReview({ is_genuine: true })}>
            <CheckCircle2 className="h-4 w-4" /> Confirm as Genuine Lead &amp; Save Classification
          </Button>
          <Button variant="danger" disabled={saving} onClick={() => submitReview({ is_genuine: false })}>
            <XCircle className="h-4 w-4" /> Mark as Not a Lead / Irrelevant
          </Button>
        </div>

        {lead.reviews?.length > 0 && (
          <div className="mt-5 border-t border-slate-100 pt-4">
            <div className="text-xs font-semibold uppercase text-slate-500">Review Audit History</div>
            <div className="mt-2 space-y-1.5 text-xs text-slate-600">
              {lead.reviews.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center justify-between rounded bg-slate-50 px-3 py-1.5">
                  <span><b>{r.reviewer}</b> · {r.action} {r.notes && `— “${r.notes}”`}</span>
                  <span className="text-slate-400">{fmtDate(r.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
