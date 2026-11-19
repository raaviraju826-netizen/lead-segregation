import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, GitMerge, ListChecks, ShieldAlert, X } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, EmptyState, ErrorBox, Loading } from "../components/ui";
import { StatusBadge, RiskBadge, TrustBadge, PriorityBadge, IndustryBadge, fmtDate, pct } from "../components/badges";

export default function ReviewQueue() {
  const nav = useNavigate();
  const { source } = useSource();
  const queue = useApi(() => api.reviewQueue({ source, page_size: 100 }), [source]);
  const dups = useApi(() => api.duplicates(), [source]);
  const [err, setErr] = useState(null);

  const handleDup = async (id, action) => {
    setErr(null);
    try {
      await api.resolveDuplicate(id, action);
      dups.reload();
    } catch (e) {
      setErr(errorMessage(e));
    }
  };

  if (queue.loading && !queue.data) return <Loading label="Loading review queue…" />;
  if (queue.error) return <ErrorBox message={queue.error} onRetry={queue.reload} />;

  const items = queue.data?.items || [];
  const dupItems = dups.data || [];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 p-5 text-white shadow-lg shadow-orange-500/20">
        <div className="flex items-center gap-3.5">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
            <ListChecks className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold">Human Review &amp; Trust Verification Queue</h1>
            <p className="text-xs text-white/95">
              Emails with classification confidence below 0.75, conflicting company evidence, or suspicious email signals. Human-confirmed classifications are added to the ChromaDB RAG example store.
            </p>
          </div>
        </div>
      </div>

      {err && <ErrorBox message={err} />}

      <Card title={`Emails Requiring Human Review (${items.length})`} subtitle="Click any card to inspect full evidence, scores, and submit a review decision">
        {items.length === 0 ? (
          <EmptyState title="Review queue is clear" hint="No unreviewed items require human attention in this data source." />
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const isSusp = item.status.startsWith("Suspicious");
              return (
                <div
                  key={item.id}
                  onClick={() => nav(`/leads/${item.id}`)}
                  className={`flex cursor-pointer flex-wrap items-start justify-between gap-4 rounded-2xl border p-4 shadow-xs transition-all hover:-translate-y-0.5 hover:shadow-md ${
                    isSusp
                      ? "border-rose-200 bg-gradient-to-r from-rose-50/80 via-pink-50/50 to-orange-50/60"
                      : "border-amber-200 bg-gradient-to-r from-amber-50/70 via-yellow-50/40 to-indigo-50/50"
                  }`}
                >
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-extrabold text-slate-900">{item.company_name || "Unknown Company"}</span>
                      <span className="text-xs font-medium text-indigo-700">({item.email})</span>
                      <IndustryBadge industry={item.industry} />
                      <StatusBadge status={item.status} />
                      <RiskBadge risk={item.email_risk} />
                      <TrustBadge label={item.company_trust_label} />
                      <PriorityBadge priority={item.priority} />
                    </div>
                    <div className="text-sm font-semibold text-slate-800">{item.subject || "(no subject)"}</div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                      <span>Suggested: <b className="text-indigo-900">{item.industry}</b>{item.sub_industry ? ` → ${item.sub_industry}` : ""} ({pct(item.confidence)})</span>
                      {item.interest_area && <span>· Interest: <b className="text-fuchsia-700">{item.interest_area}</b></span>}
                      <span>· {fmtDate(item.email_date)}</span>
                    </div>
                    {item.status_reasons?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {item.status_reasons.map((r, idx) => (
                          <span key={idx} className="inline-flex items-center gap-1 rounded-full bg-white/90 px-2.5 py-0.5 text-xs font-semibold text-amber-950 ring-1 ring-inset ring-amber-300">
                            {isSusp ? <ShieldAlert className="h-3.5 w-3.5 text-rose-600" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />}
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button variant="primary" onClick={(e) => { e.stopPropagation(); nav(`/leads/${item.id}`); }}>
                    Inspect &amp; Review
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card
        title={`Uncertain Duplicate Company Candidates (${dupItems.length})`}
        subtitle="Fuzzy company-name matches (RapidFuzz >= threshold) where domains differ or a free-mail address was used — never merged automatically"
      >
        {dupItems.length === 0 ? (
          <p className="text-sm text-slate-500">No open duplicate candidates waiting for review.</p>
        ) : (
          <div className="space-y-2.5">
            {dupItems.map((d) => (
              <div key={d.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-violet-200 bg-gradient-to-r from-violet-50/70 to-indigo-50/60 p-3.5">
                <div className="text-sm">
                  <div className="font-bold text-slate-900">
                    {d.company?.name} <span className="text-xs font-normal text-slate-600">({d.company?.domain || "free-mail / no domain"})</span>
                    {" "}↔{" "}
                    {d.other_company?.name} <span className="text-xs font-normal text-slate-600">({d.other_company?.domain || "free-mail / no domain"})</span>
                  </div>
                  <div className="text-xs text-slate-600">{d.reason} · <button onClick={() => nav(`/leads/${d.email_id}`)} className="font-semibold text-indigo-700 underline">View triggering email</button></div>
                </div>
                <div className="flex gap-2">
                  <Button variant="primary" onClick={() => handleDup(d.id, "merge")}><GitMerge className="h-3.5 w-3.5" /> Confirm &amp; Merge</Button>
                  <Button variant="secondary" onClick={() => handleDup(d.id, "dismiss")}><X className="h-3.5 w-3.5" /> Keep Separate</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
