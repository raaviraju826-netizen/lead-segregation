import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CopyCheck, GitMerge, X, History } from "lucide-react";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, EmptyState, ErrorBox, Loading } from "../components/ui";
import { Badge, fmtDate } from "../components/badges";

export default function DuplicatesPage() {
  const nav = useNavigate();
  const [filter, setFilter] = useState("all");
  const cands = useApi(() => api.duplicates(filter), [filter]);
  const logs = useApi(() => api.duplicateLogs(), []);
  const [err, setErr] = useState(null);

  const resolve = async (id, action) => {
    setErr(null);
    try {
      await api.resolveDuplicate(id, action);
      cands.reload();
      logs.reload();
    } catch (e) {
      setErr(errorMessage(e));
    }
  };

  if (cands.loading && !cands.data) return <Loading label="Loading duplicate candidates & logs…" />;

  const items = cands.data || [];
  const logRows = logs.data || [];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-fuchsia-600 via-purple-600 to-indigo-600 p-5 text-white shadow-lg shadow-fuchsia-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <CopyCheck className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold">Duplicate Detection &amp; Merge Audit Management</h1>
              <p className="text-xs text-white/90">
                Exact normalized email matching, corporate domain matching, and RapidFuzz token_set_ratio company-name matching (threshold 90%). Uncertain matches are never auto-merged.
              </p>
            </div>
          </div>
          <div className="flex gap-1.5 rounded-xl bg-white/15 p-1 text-xs font-bold">
            {["open", "merged", "dismissed", "all"].map((st) => (
              <button
                key={st}
                onClick={() => setFilter(st)}
                className={`cursor-pointer rounded-lg px-3 py-1.5 capitalize ${filter === st ? "bg-white text-purple-900 shadow-xs" : "text-white/80 hover:text-white"}`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </div>

      {err && <ErrorBox message={err} />}

      <Card
        title={`Fuzzy Company-Name Duplicate Candidates (${items.length})`}
        subtitle="Flagged when RapidFuzz token_set_ratio >= 90% across different or free-mail domains"
      >
        {items.length === 0 ? (
          <EmptyState title="No duplicate candidates in this view" hint="Switch the filter pill above to 'all' to view resolved candidates." />
        ) : (
          <div className="space-y-3">
            {items.map((d) => (
              <div key={d.id} className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-purple-200 bg-gradient-to-r from-purple-50/70 via-indigo-50/50 to-pink-50/50 p-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-extrabold text-slate-900">{d.company?.name || "Company A"}</span>
                    <span className="text-xs text-slate-500">({d.company?.domain || "free-mail"})</span>
                    <span className="font-bold text-fuchsia-600">↔</span>
                    <span className="font-extrabold text-slate-900">{d.other_company?.name || "Company B"}</span>
                    <span className="text-xs text-slate-500">({d.other_company?.domain || "free-mail"})</span>
                    <Badge color="violet">{Math.round(d.similarity)}% match</Badge>
                    <Badge color={d.status === "merged" ? "green" : d.status === "dismissed" ? "slate" : "amber"}>{d.status}</Badge>
                  </div>
                  <div className="text-xs text-slate-600">
                    {d.reason} ·{" "}
                    <button onClick={() => nav(`/leads/${d.email_id}`)} className="cursor-pointer font-bold text-indigo-700 underline">
                      Inspect Email #{d.email_id}
                    </button>
                  </div>
                </div>
                {d.status === "open" && (
                  <div className="flex gap-2">
                    <Button variant="primary" onClick={() => resolve(d.id, "merge")}>
                      <GitMerge className="h-4 w-4" /> Confirm &amp; Merge
                    </Button>
                    <Button variant="secondary" onClick={() => resolve(d.id, "dismiss")}>
                      <X className="h-4 w-4" /> Keep Separate
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title={`Duplicate Detection & Merge Audit Log (${logRows.length})`} subtitle="Persisted in the duplicate_log table (exact_email, domain_match, fuzzy_company, manual_merge, dismissed)">
        {logRows.length === 0 ? (
          <p className="text-sm text-slate-500">No duplicate log events recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-indigo-50/80 text-xs font-bold uppercase text-indigo-950">
                <tr>
                  <th className="px-3 py-2.5">ID</th>
                  <th className="px-3 py-2.5">Match Type</th>
                  <th className="px-3 py-2.5">Similarity</th>
                  <th className="px-3 py-2.5">Audit Details</th>
                  <th className="px-3 py-2.5">Actor</th>
                  <th className="px-3 py-2.5">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {logRows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-2 font-bold">#{r.id}</td>
                    <td className="px-3 py-2">
                      <Badge color={r.match_type === "manual_merge" ? "green" : r.match_type === "fuzzy_company" ? "amber" : "blue"}>
                        {r.match_type}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 font-bold tabular-nums">{Math.round(r.similarity)}%</td>
                    <td className="px-3 py-2 text-xs text-slate-700">{r.details}</td>
                    <td className="px-3 py-2 text-xs font-semibold text-slate-600">{r.actor}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
