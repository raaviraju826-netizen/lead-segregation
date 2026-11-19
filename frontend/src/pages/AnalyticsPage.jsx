import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid, Legend } from "recharts";
import { LineChart as ChartIcon, Sparkles, ShieldCheck, ShieldAlert, Mail, Award } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api } from "../services/api";
import { Card, ErrorBox, Loading } from "../components/ui";

const PALETTE = ["#2563eb", "#8b5cf6", "#06b6d4", "#f97316", "#10b981", "#ec4899", "#f59e0b", "#6366f1"];
const RISK_COLORS = { Low: "#10b981", Medium: "#f59e0b", High: "#f43f5e", Unknown: "#64748b" };
const CONF_COLORS = { "0.75–1.00": "#10b981", "0.50–0.74": "#f59e0b", "0.00–0.49": "#f43f5e" };

const IND_META = [
  { name: "Manufacturing", displayName: "Manufacturing", slug: "manufacturing" },
  { name: "Education", displayName: "Education & EdTech", slug: "education" },
  { name: "IT & Software", displayName: "IT & Software", slug: "it-software" },
  { name: "Logistics & Transportation", displayName: "Logistics & Transportation", slug: "logistics" },
];

export default function AnalyticsPage() {
  const nav = useNavigate();
  const { source } = useSource();
  const { data: stats, loading, error, reload } = useApi(() => api.stats(source), [source]);

  if (loading && !stats) return <Loading label="Computing analytics…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const indVerdicts = stats?.industry_verdict_stats || {};
  const indRows = IND_META.map((m) => {
    const v = indVerdicts[m.name] || { total: 0, real: 0, fake: 0, avg_accuracy: 0, avg_real_score: 0, avg_fake_score: 0 };
    return {
      ...m,
      total: v.total,
      real: v.real,
      fake: v.fake,
      avg_accuracy: v.avg_accuracy,
      avg_real_score: v.avg_real_score,
      avg_fake_score: v.avg_fake_score,
    };
  });

  const totalReal = stats?.total_real_mails ?? indRows.reduce((s, r) => s + r.real, 0);
  const totalFake = stats?.total_fake_mails ?? indRows.reduce((s, r) => s + r.fake, 0);
  const totalIndMails = totalReal + totalFake;
  const overallAcc = stats?.overall_accuracy ?? 0;

  const subData = Object.entries(stats?.by_sub_industry || {})
    .map(([name, value], i) => ({ name, value, fill: PALETTE[i % PALETTE.length] }))
    .sort((a, b) => b.value - a.value);

  const confData = Object.entries(stats?.confidence_distribution || {}).map(([name, value]) => ({
    name,
    value,
    fill: CONF_COLORS[name] || "#6366f1",
  }));

  const riskData = Object.entries(stats?.email_risk_distribution || {}).map(([name, value]) => ({
    name: `${name} Risk`,
    value,
    fill: RISK_COLORS[name] || "#64748b",
  }));

  const statusData = Object.entries(stats?.status_distribution || {}).map(([name, value], i) => ({
    name,
    value,
    fill: PALETTE[i % PALETTE.length],
  }));

  const sourceData = Object.entries(stats?.by_source || {}).map(([name, value], i) => ({
    name: name.toUpperCase(),
    value,
    fill: PALETTE[i % PALETTE.length],
  }));

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 p-5 text-white shadow-lg shadow-blue-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <ChartIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
                <Sparkles className="h-3 w-3" /> Real-Time Database &amp; RAG Telemetry
              </div>
              <h1 className="text-xl font-extrabold">Deep Lead, Real vs. Fake &amp; Classification Analytics</h1>
              <p className="text-xs text-white/90">
                4-Industry Real vs. Fake breakdown, classification accuracy scores, sub-industry distribution, and RAG confidence calibration.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-extrabold">
            <button
              onClick={() => nav("/leads?verdict=REAL")}
              className="cursor-pointer rounded-xl bg-emerald-500 px-3.5 py-2 text-white shadow-sm hover:bg-emerald-400"
            >
              ✓ Total Real Mails: {totalReal}
            </button>
            <button
              onClick={() => nav("/leads?verdict=FAKE")}
              className="cursor-pointer rounded-xl bg-rose-500 px-3.5 py-2 text-white shadow-sm hover:bg-rose-400"
            >
              ✗ Total Fake Mails: {totalFake}
            </button>
          </div>
        </div>
      </div>

      {/* Top KPI Summary Cards matching Overview & 4 Industries */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div
          onClick={() => nav("/leads?verdict=ALL")}
          className="cursor-pointer rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-blue-50 to-sky-50 p-4 shadow-md transition hover:-translate-y-0.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold uppercase tracking-wider text-indigo-800">4-Industry Mails</span>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white"><Mail className="h-4 w-4" /></span>
          </div>
          <div className="mt-2 text-3xl font-extrabold text-indigo-950">{totalIndMails}</div>
          <div className="mt-1 text-xs font-semibold text-indigo-700">
            {totalReal} Real + {totalFake} Fake ({stats?.total_emails || 0} total inbox msgs)
          </div>
        </div>

        <div
          onClick={() => nav("/leads?verdict=REAL")}
          className="cursor-pointer rounded-2xl border border-emerald-300 bg-gradient-to-br from-emerald-50 via-teal-50 to-cyan-50 p-4 shadow-md transition hover:-translate-y-0.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-800">Total Real Mails</span>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-600 text-white"><ShieldCheck className="h-4 w-4" /></span>
          </div>
          <div className="mt-2 text-3xl font-extrabold text-emerald-950">{totalReal}</div>
          <div className="mt-1 text-xs font-semibold text-emerald-700">Verified genuine client enquiries</div>
        </div>

        <div
          onClick={() => nav("/leads?verdict=FAKE")}
          className="cursor-pointer rounded-2xl border border-rose-300 bg-gradient-to-br from-rose-50 via-pink-50 to-orange-50 p-4 shadow-md transition hover:-translate-y-0.5"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold uppercase tracking-wider text-rose-800">Total Fake Mails</span>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-rose-600 text-white"><ShieldAlert className="h-4 w-4" /></span>
          </div>
          <div className="mt-2 text-3xl font-extrabold text-rose-950">{totalFake}</div>
          <div className="mt-1 text-xs font-semibold text-rose-700">Scam / phishing keywords detected</div>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 via-yellow-50 to-orange-50 p-4 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold uppercase tracking-wider text-amber-900">Classification Accuracy</span>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-500 text-white"><Award className="h-4 w-4" /></span>
          </div>
          <div className="mt-2 text-3xl font-extrabold text-amber-950">{overallAcc}%</div>
          <div className="mt-1 text-xs font-semibold text-amber-800">0.6 × Model + 0.4 × ChromaDB RAG</div>
        </div>
      </div>

      {/* 4-Industry Real vs Fake & Accuracy Table + Grouped Bar Chart */}
      <div className="grid gap-6 lg:grid-cols-12">
        <Card
          title="4-Industry Real vs. Fake Mails & Accuracy Breakdown"
          subtitle="Click any industry or Real/Fake pill to drill down into the exact emails"
          className="lg:col-span-7"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-indigo-100 bg-indigo-50/70 text-[11px] font-extrabold uppercase text-indigo-950">
                  <th className="px-3 py-2.5">Industry</th>
                  <th className="px-3 py-2.5 text-center">Total</th>
                  <th className="px-3 py-2.5 text-center">✓ Real Mails</th>
                  <th className="px-3 py-2.5 text-center">✗ Fake Mails</th>
                  <th className="px-3 py-2.5 text-center">Real Score</th>
                  <th className="px-3 py-2.5 text-center">Accuracy %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-100">
                {indRows.map((r) => (
                  <tr key={r.slug} className="hover:bg-indigo-50/40">
                    <td
                      onClick={() => nav(`/industry/${r.slug}`)}
                      className="cursor-pointer px-3 py-2.5 font-extrabold text-indigo-950 hover:text-indigo-600"
                    >
                      {r.displayName}
                    </td>
                    <td className="px-3 py-2.5 text-center font-bold text-slate-800">{r.total}</td>
                    <td className="px-3 py-2.5 text-center">
                      <button
                        onClick={() => nav(`/industry/${r.slug}?verdict=REAL`)}
                        className="cursor-pointer rounded-full bg-emerald-100 px-2.5 py-0.5 font-extrabold text-emerald-800 hover:bg-emerald-200"
                      >
                        {r.real} Real
                      </button>
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <button
                        onClick={() => nav(`/industry/${r.slug}?verdict=FAKE`)}
                        className="cursor-pointer rounded-full bg-rose-100 px-2.5 py-0.5 font-extrabold text-rose-800 hover:bg-rose-200"
                      >
                        {r.fake} Fake
                      </button>
                    </td>
                    <td className="px-3 py-2.5 text-center font-bold text-emerald-700">{r.avg_real_score}%</td>
                    <td className="px-3 py-2.5 text-center">
                      <span className="rounded-lg bg-indigo-100 px-2 py-0.5 font-extrabold text-indigo-800">
                        {r.avg_accuracy}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-indigo-200 bg-indigo-50/90 font-extrabold text-indigo-950">
                  <td className="px-3 py-2.5">Total Across 4 Industries</td>
                  <td className="px-3 py-2.5 text-center">{totalIndMails}</td>
                  <td className="px-3 py-2.5 text-center text-emerald-700">{totalReal} Real</td>
                  <td className="px-3 py-2.5 text-center text-rose-700">{totalFake} Fake</td>
                  <td className="px-3 py-2.5 text-center text-emerald-700">—</td>
                  <td className="px-3 py-2.5 text-center text-indigo-800">{overallAcc}%</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>

        <Card
          title="Real vs. Fake Mails by Industry"
          subtitle={`Total Real: ${totalReal} · Total Fake: ${totalFake}`}
          className="lg:col-span-5"
        >
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={indRows} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                <XAxis dataKey="displayName" tick={{ fontSize: 10, fill: "#1e293b", fontWeight: 700 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="real" name="REAL Mails" fill="#10b981" radius={[6, 6, 0, 0]} />
                <Bar dataKey="fake" name="FAKE Mails" fill="#f43f5e" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Sub-Industry Real Lead Distribution" subtitle={`Granular sub-industry breakdown across all ${totalReal} verified Real leads`} className="lg:col-span-2">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={subData} layout="vertical" margin={{ top: 5, right: 24, left: 60, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={230} tick={{ fontSize: 11, fill: "#1e293b", fontWeight: 600 }} />
                <Tooltip />
                <Bar dataKey="value" name="Real Leads" radius={[0, 8, 8, 0]}>
                  {subData.map((e, i) => (
                    <Cell key={i} fill={e.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="RAG Classification Confidence Calibration" subtitle="0.6 × Model Confidence + 0.4 × Top ChromaDB Similarity across classified industry mails">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={confData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fontWeight: 600 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" name="Industry Mails" radius={[8, 8, 0, 0]}>
                  {confData.map((e, i) => (
                    <Cell key={i} fill={e.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Email Authenticity Risk Distribution" subtitle={`Low Risk = Real Mails (${totalReal}) · Medium/High Risk = Fake Mails (${totalFake})`}>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={riskData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={4} label>
                  {riskData.map((e, i) => (
                    <Cell key={i} fill={e.fill} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Processing Status Breakdown" subtitle="Classified & Needs Review (22 Real) vs Suspicious (5 Fake) vs Not a Lead">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fontWeight: 600 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" name="Emails" radius={[8, 8, 0, 0]}>
                  {statusData.map((e, i) => (
                    <Cell key={i} fill={e.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Records by Ingestion Source" subtitle="Database row counts across Live Gmail, Uploaded CSV/EML/MSG/MBOX, and Demo Dataset">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fontWeight: 700 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" name="Records" radius={[8, 8, 0, 0]}>
                  {sourceData.map((e, i) => (
                    <Cell key={i} fill={e.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}
