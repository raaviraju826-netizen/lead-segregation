import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Download, Factory, GraduationCap, Code2, Truck, ShieldCheck, ShieldAlert, Layers, Award } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api } from "../services/api";
import LeadsTable from "../components/LeadsTable";
import { Card, INDUSTRY_META } from "../components/ui";

const META = {
  manufacturing: { name: "Manufacturing", displayName: "Manufacturing", icon: Factory, desc: "Senders whose business is manufacturing (automotive, textile, electronics, industrial machinery, chemical, or other factories)." },
  education: { name: "Education", displayName: "Education & EdTech", icon: GraduationCap, desc: "Senders that are educational institutions or platforms (schools, colleges & universities, coaching, EdTech, training)." },
  "it-software": { name: "IT & Software", displayName: "IT & Software", icon: Code2, desc: "Senders whose business is building or providing software, SaaS, cloud/DevOps, AI/data, cybersecurity, or IT services." },
  logistics: { name: "Logistics & Transportation", displayName: "Logistics & Transportation", icon: Truck, desc: "Senders whose business is moving or storing goods (freight, courier, warehousing, fleet, supply chain)." },
};

const ALL_SLUGS = Object.entries(META);

export default function IndustryPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const nav = useNavigate();
  const { source } = useSource();
  const meta = META[slug];
  const stats = useApi(() => api.stats(source), [source, slug]);

  const verdictFilter = searchParams.get("verdict") || "ALL"; // ALL | REAL | FAKE
  const setVerdict = (v) => {
    setSearchParams(v === "ALL" ? {} : { verdict: v });
  };

  if (!meta) {
    return <div className="py-16 text-center text-slate-500">Unknown industry “{slug}”.</div>;
  }
  const Icon = meta.icon;
  const style = INDUSTRY_META[meta.name];
  const vStats = stats.data?.industry_verdict_stats?.[meta.name] || {
    total: 0,
    real: 0,
    fake: 0,
    avg_accuracy: 0,
    avg_real_score: 0,
    avg_fake_score: 0,
  };

  return (
    <div className="space-y-5">
      {/* Quick switcher across the 4 industries */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {ALL_SLUGS.map(([s, m]) => {
            const I = m.icon;
            const st = INDUSTRY_META[m.name];
            const active = s === slug;
            const vs = stats.data?.industry_verdict_stats?.[m.name];
            return (
              <button
                key={s}
                onClick={() => nav(`/industry/${s}`)}
                className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-extrabold transition-all ${
                  active
                    ? `border-transparent bg-gradient-to-r ${st.gradient} text-white shadow-md`
                    : "border-indigo-100 bg-white text-slate-700 hover:bg-indigo-50/60"
                }`}
              >
                <I className="h-4 w-4" /> {m.displayName}
                {vs && (
                  <span className={`ml-1 rounded-full px-2 py-0.5 text-[11px] ${active ? "bg-black/20 text-white" : "bg-slate-100 text-slate-700"}`}>
                    {vs.real} Real · {vs.fake} Fake
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <button onClick={() => api.download("excel", { source, industry: slug })} className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:opacity-95">
            <Download className="h-4 w-4" /> Export {meta.displayName} (.xlsx)
          </button>
          <button onClick={() => api.download("csv", { source, industry: slug })} className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-indigo-200 bg-white px-3.5 py-2 text-xs font-bold text-indigo-700 hover:bg-indigo-50">
            <Download className="h-4 w-4" /> CSV
          </button>
        </div>
      </div>

      {/* Colorful Industry Banner */}
      <div className={`rounded-2xl bg-gradient-to-r ${style.gradient} p-5 text-white shadow-lg`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <Icon className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold">{meta.displayName} — Real vs Fake Mails &amp; Accuracy Breakdown</h1>
              <p className="text-xs text-white/90">{meta.desc}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl bg-white/15 px-4 py-2.5 backdrop-blur-xs">
            <Award className="h-6 w-6 text-yellow-300" />
            <div>
              <div className="text-[11px] font-bold uppercase text-yellow-200">Industry Classification Accuracy</div>
              <div className="text-2xl font-extrabold">{vStats.avg_accuracy}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* 3 Big Clickable Cards: All Mails vs REAL Mails vs FAKE Mails */}
      <div className="grid gap-4 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => setVerdict("ALL")}
          className={`flex cursor-pointer items-center justify-between rounded-2xl border p-5 text-left transition-all ${
            verdictFilter === "ALL"
              ? "border-indigo-500 bg-gradient-to-br from-indigo-50 via-violet-50 to-blue-50 ring-2 ring-indigo-500/30 shadow-md"
              : "border-slate-200 bg-white hover:bg-slate-50"
          }`}
        >
          <div>
            <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-700">All {meta.displayName} Mails</div>
            <div className="mt-1 text-3xl font-extrabold text-slate-900">{vStats.total}</div>
            <div className="mt-1 text-xs font-medium text-slate-600">
              {vStats.real} Real + {vStats.fake} Fake · Avg Accuracy: <b>{vStats.avg_accuracy}%</b>
            </div>
          </div>
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md">
            <Layers className="h-6 w-6" />
          </span>
        </button>

        <button
          type="button"
          onClick={() => setVerdict("REAL")}
          className={`flex cursor-pointer items-center justify-between rounded-2xl border p-5 text-left transition-all ${
            verdictFilter === "REAL"
              ? "border-emerald-500 bg-gradient-to-br from-emerald-50 via-teal-50 to-cyan-50 ring-2 ring-emerald-500/30 shadow-md"
              : "border-emerald-200 bg-emerald-50/40 hover:bg-emerald-50"
          }`}
        >
          <div>
            <div className="text-xs font-extrabold uppercase tracking-wider text-emerald-800">✓ REAL Mails in {meta.displayName}</div>
            <div className="mt-1 text-3xl font-extrabold text-emerald-700">{vStats.real}</div>
            <div className="mt-1 text-xs font-semibold text-emerald-800">
              Avg Authenticity Score: <b>{vStats.avg_real_score}%</b> · Click to show only REAL
            </div>
          </div>
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-md">
            <ShieldCheck className="h-6 w-6" />
          </span>
        </button>

        <button
          type="button"
          onClick={() => setVerdict("FAKE")}
          className={`flex cursor-pointer items-center justify-between rounded-2xl border p-5 text-left transition-all ${
            verdictFilter === "FAKE"
              ? "border-rose-500 bg-gradient-to-br from-rose-50 via-pink-50 to-orange-50 ring-2 ring-rose-500/30 shadow-md"
              : "border-rose-200 bg-rose-50/40 hover:bg-rose-50"
          }`}
        >
          <div>
            <div className="text-xs font-extrabold uppercase tracking-wider text-rose-800">✗ FAKE Mails in {meta.displayName}</div>
            <div className="mt-1 text-3xl font-extrabold text-rose-600">{vStats.fake}</div>
            <div className="mt-1 text-xs font-semibold text-rose-800">
              Avg Authenticity Score: <b>{vStats.avg_fake_score}%</b> · Click to show only FAKE
            </div>
          </div>
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-rose-500 to-pink-600 text-white shadow-md">
            <ShieldAlert className="h-6 w-6" />
          </span>
        </button>
      </div>

      <Card
        title={`${meta.displayName} — Showing ${verdictFilter === "REAL" ? "Only REAL Client Mails" : verdictFilter === "FAKE" ? "Only FAKE / Scam Mails" : "All Mails (Real & Fake)"}`}
        subtitle="Classified by matched keywords, authenticity score, and ChromaDB RAG industry accuracy"
      >
        <LeadsTable
          key={`${slug}-${source}-${verdictFilter}`}
          fetcher={(params) => api.industryLeads(slug, { ...params, source, verdict: verdictFilter })}
          deps={[slug, source, verdictFilter]}
          filters={["status", "priority", "company_trust", "email_risk"]}
          exportContext={{ source, industry: slug }}
          emptyHint={`No ${verdictFilter.toLowerCase()} ${meta.displayName} mails found in this source.`}
        />
      </Card>
    </div>
  );
}
