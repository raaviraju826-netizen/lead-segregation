import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import { Factory, GraduationCap, Code2, Truck, ArrowRight, FlaskConical, Mail, ShieldAlert, AlertCircle, Sparkles, Building2, CopyCheck, UploadCloud, ShieldCheck, Send, RefreshCw } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, ErrorBox, Loading, EmptyState, INDUSTRY_META } from "../components/ui";
import { fmtDate } from "../components/badges";

const IND_CARDS = [
  { name: "Manufacturing", displayName: "Manufacturing", slug: "manufacturing", icon: Factory, desc: "Automotive, textile, electronics, industrial machinery & chemical plants" },
  { name: "Education", displayName: "Education & EdTech", slug: "education", icon: GraduationCap, desc: "Schools, colleges & universities, coaching, EdTech & training institutes" },
  { name: "IT & Software", displayName: "IT & Software", slug: "it-software", icon: Code2, desc: "Custom software, SaaS, cloud/DevOps, AI & data, cybersecurity & IT services" },
  { name: "Logistics & Transportation", displayName: "Logistics & Transportation", slug: "logistics", icon: Truck, desc: "Freight carriers, courier networks, warehousing, fleet & supply chain" },
];

const PRIO_COLORS = { High: "#f43f5e", Medium: "#f59e0b", Low: "#3b82f6" };
const TRUST_COLORS = { Verified: "#10b981", "Partially Verified": "#3b82f6", Unverified: "#8b5cf6", "Conflicting Evidence": "#f43f5e" };

function StatTile({ label, value, sub, icon: Icon, gradient, iconBg, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-4 shadow-md transition hover:-translate-y-0.5 hover:shadow-lg ${gradient} ${onClick ? "cursor-pointer" : ""}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-700">{label}</span>
        {Icon && (
          <span className={`grid h-9 w-9 place-items-center rounded-xl text-white shadow-sm ${iconBg}`}>
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <div className="mt-2 text-3xl font-extrabold tabular-nums text-slate-900">{value ?? 0}</div>
      {sub && <div className="mt-1 text-xs font-medium text-slate-600">{sub}</div>}
    </div>
  );
}

export default function Overview() {
  const nav = useNavigate();
  const { source, setSource } = useSource();
  const { data: stats, loading, error, reload } = useApi(() => api.stats(source), [source]);
  const latestReq = useApi(() => api.leads({ source, page: 1, page_size: 1, sort: "date", order: "desc" }), [source]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  // Quick live mail sender to rajurajuu970@gmail.com right on the dashboard
  const [quickMail, setQuickMail] = useState({
    sender_name: "Kiran Kumar",
    sender_email: "kiran@creativestudio.in",
    subject: "Website design and web development enquiry",
    body: "Hello Raju,\n\nWe need a modern website design and web application development for our company. Please share your website design quotation and proposal.\n\nRegards,\nKiran Kumar\nDirector\nCreative Studio Software Solutions\n+91 98480 55667",
  });

  // Auto-poll every 8 seconds so newly arrived Gmail messages appear automatically
  useEffect(() => {
    const t = setInterval(() => {
      reload();
      latestReq.reload();
    }, 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  const sendQuickMail = async (preset) => {
    const payload = preset || quickMail;
    setBusy(true); setMsg(null);
    try {
      await api.ingestEmail({
        source: "gmail",
        emails: [
          {
            sender_name: payload.sender_name,
            sender_email: payload.sender_email,
            subject: payload.subject,
            body: payload.body,
            headers: { To: "rajurajuu970@gmail.com", "Delivered-To": "rajurajuu970@gmail.com" },
          },
        ],
      });
      setSource("gmail");
      reload();
      latestReq.reload();
    } catch (e) {
      setMsg(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const [syncToast, setSyncToast] = useState(null);

  const refreshInbox = async () => {
    setBusy(true); setMsg(null); setSyncToast(null);
    try {
      const res = await api.simulateGmailInbox();
      setSource("gmail");
      reload();
      latestReq.reload();
      setSyncToast(`Refreshed & synced rajurajuu970@gmail.com (${res.fetched} checked, ${res.processed} newly classified).`);
    } catch (e) {
      reload();
      latestReq.reload();
    } finally {
      setBusy(false);
    }
  };

  const loadDemoData = async () => {
    setBusy(true); setMsg(null);
    try {
      await api.demoLoad();
      setSource("demo");
      reload();
      latestReq.reload();
    } catch (e) {
      setMsg(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !stats) return <Loading label="Loading dashboard metrics…" />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const byInd = stats?.by_industry || {};
  const indVerdicts = stats?.industry_verdict_stats || {};
  const indData = IND_CARDS.map((c) => ({
    name: c.displayName,
    real: indVerdicts[c.name]?.real ?? byInd[c.name] ?? 0,
    fake: indVerdicts[c.name]?.fake ?? 0,
  }));
  const prioData = Object.entries(stats?.priority_distribution || {}).map(([name, value]) => ({ name, value, fill: PRIO_COLORS[name] || "#64748b" }));
  const trustData = Object.entries(stats?.company_trust_distribution || {}).map(([name, value]) => ({ name, value, fill: TRUST_COLORS[name] || "#8b5cf6" }));
  const latestMail = latestReq.data?.items?.[0];

  return (
    <div className="space-y-6">
      {/* Bright colorful hero banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 p-6 text-white shadow-lg shadow-indigo-500/20">
        <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-yellow-300/20 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-16 left-1/3 h-48 w-48 rounded-full bg-cyan-300/20 blur-2xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold text-yellow-200 backdrop-blur-xs">
              <Sparkles className="h-3.5 w-3.5" /> Auto-Detect REAL vs FAKE by Keywords &amp; Score · Inbox: rajurajuu970@gmail.com
            </div>
            <h1 className="mt-2 text-2xl font-extrabold tracking-tight">LeadSense AI — Automatic Real/Fake &amp; 4-Industry Segregation</h1>
            <p className="mt-1 max-w-2xl text-sm text-indigo-100">
              When an email arrives at <b>rajurajuu970@gmail.com</b>, it automatically tells whether it is <b>REAL</b> or <b>FAKE</b> based on keywords &amp; score, and classifies it into the 4 industries below.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={refreshInbox}
              disabled={busy}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-white/20 px-3.5 py-2.5 text-xs font-bold text-white backdrop-blur-xs hover:bg-white/30"
            >
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> {busy ? "Syncing…" : "Refresh & Sync Inbox"}
            </button>
            <button
              onClick={() => nav("/gmail")}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-amber-400 to-orange-500 px-4 py-2.5 text-xs font-extrabold text-slate-950 shadow-md hover:from-amber-300 hover:to-orange-400"
            >
              <Mail className="h-4 w-4" /> Gmail Sync &amp; Status
            </button>
          </div>
        </div>
      </div>

      {msg && <ErrorBox message={msg} />}
      {syncToast && (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2.5 text-xs font-bold text-emerald-900">
          ✓ {syncToast}
        </div>
      )}

      {/* Latest Incoming Mail to rajurajuu970@gmail.com — Automatic REAL vs FAKE Result + Quick Tester */}
      <div className="grid gap-4 lg:grid-cols-12">
        {latestMail && (
          <div
            onClick={() => nav(`/leads/${latestMail.id}`)}
            className={`cursor-pointer rounded-2xl border p-5 shadow-md transition hover:shadow-lg lg:col-span-7 ${
              latestMail.verdict === "FAKE"
                ? "border-rose-300 bg-gradient-to-r from-rose-50 via-pink-50 to-orange-50 text-rose-950"
                : "border-emerald-300 bg-gradient-to-r from-emerald-50 via-teal-50 to-cyan-50 text-emerald-950"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-extrabold uppercase tracking-wider text-slate-600">
                Latest Mail Received at rajurajuu970@gmail.com · {fmtDate(latestMail.email_date)}
              </span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1 text-xs font-extrabold text-white shadow-sm ${
                  latestMail.verdict === "FAKE" ? "bg-gradient-to-r from-rose-600 to-red-600" : "bg-gradient-to-r from-emerald-600 to-teal-600"
                }`}
              >
                {latestMail.verdict === "FAKE" ? <ShieldAlert className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                AUTOMATIC VERDICT: {latestMail.verdict} MAIL (Score: {latestMail.real_fake_score}%)
              </span>
            </div>

            <div className="mt-2 text-base font-extrabold text-slate-900">
              Subject: “{latestMail.subject}”
            </div>
            <div className="text-xs font-medium text-slate-600">
              From: <b>{latestMail.contact_name || latestMail.company_name || "Sender"}</b> &lt;{latestMail.email}&gt; → To: <b>rajurajuu970@gmail.com</b>
            </div>

            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <span className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-extrabold text-white">
                Industry: {latestMail.industry} ({latestMail.sub_industry || "General"})
              </span>
              <span className="rounded-lg bg-white px-2.5 py-1 text-xs font-extrabold text-indigo-800 ring-1 ring-indigo-200">
                Accuracy Score: {latestMail.accuracy_score}%
              </span>
              <span className="rounded-lg bg-white px-2.5 py-1 text-xs font-extrabold text-slate-800 ring-1 ring-slate-200">
                Authenticity Score: {latestMail.real_fake_score}%
              </span>
            </div>

            <p className="mt-2 text-xs font-medium">{latestMail.verdict_reason}</p>

            <div className="mt-2 flex flex-wrap gap-1.5">
              {latestMail.verdict === "FAKE"
                ? (latestMail.fake_keywords || []).map((kw, i) => (
                    <span key={i} className="rounded-full bg-rose-200 px-2.5 py-0.5 text-[11px] font-extrabold text-rose-950">
                      Fake Keyword: “{kw}”
                    </span>
                  ))
                : (latestMail.real_keywords || []).map((kw, i) => (
                    <span key={i} className="rounded-full bg-emerald-200 px-2.5 py-0.5 text-[11px] font-extrabold text-emerald-950">
                      Real Keyword: “{kw}”
                    </span>
                  ))}
            </div>
          </div>
        )}

        {/* Instant Send Mail to rajurajuu970@gmail.com box right on Overview */}
        <div className="rounded-2xl border border-indigo-200 bg-white p-4 shadow-md lg:col-span-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-extrabold uppercase tracking-wider text-indigo-950">
              Send / Simulate Instant Mail to rajurajuu970@gmail.com
            </span>
            <div className="flex gap-1.5">
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  sendQuickMail({
                    sender_name: "Kiran Kumar",
                    sender_email: "kiran@creativestudio.in",
                    subject: "Website design and web development enquiry",
                    body: "Hello Raju,\n\nWe need a modern website design and web application development for our business. Please share your website design quotation and proposal.\n\nRegards,\nKiran Kumar\nCreative Studio Software Solutions\n+91 98480 55667",
                  })
                }
                className="cursor-pointer rounded-lg bg-emerald-100 px-2.5 py-1 text-[11px] font-extrabold text-emerald-800 hover:bg-emerald-200"
              >
                + Test REAL Website Design Mail
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  sendQuickMail({
                    sender_name: "Fake Web Agency",
                    sender_email: "billing@urgent-webdesign-pay.com",
                    subject: "Urgent payment: Website design account suspended",
                    body: "Hello,\n\nYour website design and cloud software account will be suspended within 24 hours. Kindly wire transfer the urgent payment or verify your account password and share your bank details immediately.",
                  })
                }
                className="cursor-pointer rounded-lg bg-rose-100 px-2.5 py-1 text-[11px] font-extrabold text-rose-800 hover:bg-rose-200"
              >
                + Test FAKE Website Design Mail
              </button>
            </div>
          </div>

          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            <input
              value={quickMail.sender_email}
              onChange={(e) => setQuickMail({ ...quickMail, sender_email: e.target.value })}
              placeholder="Sender email"
              className="rounded-xl border border-indigo-200 px-2.5 py-1.5 text-xs"
            />
            <input
              value={quickMail.subject}
              onChange={(e) => setQuickMail({ ...quickMail, subject: e.target.value })}
              placeholder="Subject (e.g. Website design)"
              className="rounded-xl border border-indigo-200 px-2.5 py-1.5 text-xs"
            />
          </div>
          <textarea
            rows={2}
            value={quickMail.body}
            onChange={(e) => setQuickMail({ ...quickMail, body: e.target.value })}
            placeholder="Write mail body here..."
            className="mt-2 w-full rounded-xl border border-indigo-200 p-2 text-xs"
          />
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[11px] text-slate-500">
              Sent from phone Gmail? <button onClick={() => nav("/gmail")} className="cursor-pointer font-bold text-indigo-700 underline">Link App Password on /gmail</button>
            </span>
            <Button variant="primary" disabled={busy} onClick={() => sendQuickMail()}>
              <Send className="h-3.5 w-3.5" /> {busy ? "Checking…" : "Send to Dashboard & Check Real/Fake"}
            </Button>
          </div>
        </div>
      </div>

      {/* 4 Colorful Industry Cards showing Total, REAL Mails count, FAKE Mails count, and Accuracy % */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-extrabold uppercase tracking-wider text-indigo-950">
            Click Any of the 4 Industries Below to View Real Mails vs Fake Mails &amp; Accuracy Score
          </h2>
          <div className="flex items-center gap-2 text-xs font-bold">
            <button
              type="button"
              onClick={() => nav("/leads?verdict=REAL")}
              className="cursor-pointer rounded-full bg-emerald-100 px-3 py-1 font-extrabold text-emerald-800 hover:bg-emerald-200"
            >
              Total Real Mails: {stats?.total_real_mails ?? stats?.total_leads ?? 0}
            </button>
            <button
              type="button"
              onClick={() => nav("/leads?verdict=FAKE")}
              className="cursor-pointer rounded-full bg-rose-100 px-3 py-1 font-extrabold text-rose-800 hover:bg-rose-200"
            >
              Total Fake Mails: {stats?.total_fake_mails ?? stats?.suspicious ?? 0}
            </button>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {IND_CARDS.map(({ name, displayName, slug, icon: Icon, desc }) => {
            const meta = INDUSTRY_META[name];
            const v = indVerdicts[name] || { total: byInd[name] || 0, real: byInd[name] || 0, fake: 0, avg_accuracy: 0 };
            return (
              <div
                key={slug}
                onClick={() => nav(`/industry/${slug}`)}
                className={`group relative flex cursor-pointer flex-col justify-between overflow-hidden rounded-2xl border bg-gradient-to-br ${meta.softBg} ${meta.border} p-5 text-left shadow-md transition-all duration-200 hover:-translate-y-1 hover:shadow-xl`}
              >
                <div className={`absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r ${meta.gradient}`} />
                <div>
                  <div className="flex items-center justify-between">
                    <span className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${meta.iconBg}`}>
                      <Icon className="h-6 w-6" />
                    </span>
                    <div className="text-right">
                      <span className="rounded-xl bg-white/95 px-3 py-1 text-2xl font-extrabold tabular-nums text-slate-900 shadow-xs">
                        {v.total}
                      </span>
                      <div className="mt-1 text-[11px] font-bold text-indigo-700">
                        Accuracy: {v.avg_accuracy}%
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 text-base font-extrabold text-slate-900">{displayName}</div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-600">{desc}</p>

                  {/* Explicit REAL vs FAKE counts right on each industry card */}
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); nav(`/industry/${slug}?verdict=REAL`); }}
                      className="flex cursor-pointer items-center justify-between rounded-xl border border-emerald-300 bg-emerald-50/90 px-2.5 py-1.5 text-xs font-extrabold text-emerald-800 shadow-2xs hover:bg-emerald-100"
                    >
                      <span className="inline-flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> REAL</span>
                      <span className="text-sm tabular-nums">{v.real}</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); nav(`/industry/${slug}?verdict=FAKE`); }}
                      className="flex cursor-pointer items-center justify-between rounded-xl border border-rose-300 bg-rose-50/90 px-2.5 py-1.5 text-xs font-extrabold text-rose-800 shadow-2xs hover:bg-rose-100"
                    >
                      <span className="inline-flex items-center gap-1"><ShieldAlert className="h-3.5 w-3.5 text-rose-600" /> FAKE</span>
                      <span className="text-sm tabular-nums">{v.fake}</span>
                    </button>
                  </div>
                </div>
                <div className={`mt-4 inline-flex items-center gap-1.5 text-xs font-bold ${meta.text}`}>
                  Click to view {v.real} Real &amp; {v.fake} Fake mails <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Colorful KPI Summary Row */}
      <div className="grid gap-3.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
        <StatTile
          label="Emails Processed"
          value={stats?.total_emails}
          sub={`${stats?.high_priority || 0} high-priority leads`}
          icon={Mail}
          onClick={() => nav("/leads")}
          gradient="from-sky-50 via-blue-50 to-indigo-50 border-sky-200"
          iconBg="bg-gradient-to-br from-sky-500 to-blue-600"
        />
        <StatTile
          label="Real Client Mails"
          value={stats?.total_real_mails ?? stats?.total_leads}
          sub="Verified by keywords & score"
          icon={ShieldCheck}
          onClick={() => nav("/leads?verdict=REAL")}
          gradient="from-emerald-50 via-teal-50 to-cyan-50 border-emerald-200"
          iconBg="bg-gradient-to-br from-emerald-500 to-teal-600"
        />
        <StatTile
          label="Fake / Scam Mails"
          value={stats?.total_fake_mails ?? stats?.suspicious}
          sub="Phishing / scam keywords / spoof"
          icon={ShieldAlert}
          onClick={() => nav("/leads?verdict=FAKE")}
          gradient="from-rose-50 via-pink-50 to-red-50 border-rose-200"
          iconBg="bg-gradient-to-br from-rose-500 to-pink-600"
        />
        <StatTile
          label="Unique Companies"
          value={stats?.unique_companies}
          sub="Normalized & deduplicated"
          icon={Building2}
          onClick={() => nav("/leads")}
          gradient="from-indigo-50 via-violet-50 to-purple-50 border-indigo-200"
          iconBg="bg-gradient-to-br from-indigo-500 to-violet-600"
        />
        <StatTile
          label="Needs Review"
          value={stats?.needs_review}
          sub="Confidence 0.50–0.74"
          icon={AlertCircle}
          onClick={() => nav("/review")}
          gradient="from-amber-50 via-yellow-50 to-orange-50 border-amber-200"
          iconBg="bg-gradient-to-br from-amber-500 to-orange-500"
        />
        <StatTile
          label="Duplicate Records"
          value={stats?.duplicate_records}
          sub={`${stats?.not_a_lead || 0} non-lead newsletters`}
          icon={CopyCheck}
          onClick={() => nav("/duplicates")}
          gradient="from-fuchsia-50 via-purple-50 to-pink-50 border-fuchsia-200"
          iconBg="bg-gradient-to-br from-fuchsia-500 to-purple-600"
        />
      </div>

      {stats?.total_emails === 0 ? (
        <Card>
          <EmptyState
            title="No emails loaded yet"
            hint="Click below to sync incoming client emails for rajurajuu970@gmail.com or load the 48-email benchmark dataset."
          >
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <Button variant="primary" onClick={() => sendQuickMail()}>
                <UploadCloud className="h-4 w-4" /> Test Website Design Mail Now
              </Button>
              <Button variant="secondary" onClick={loadDemoData} disabled={busy}>
                <FlaskConical className="h-4 w-4" /> Load Benchmark Dataset
              </Button>
            </div>
          </EmptyState>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Real Mails vs Fake Mails by Industry" subtitle="Green = Real business mails · Red = Fake/Scam mails per industry">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={indData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#334155", fontWeight: 600 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#334155" }} />
                  <Tooltip />
                  <Bar dataKey="real" name="REAL Mails" fill="#10b981" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="fake" name="FAKE Mails" fill="#f43f5e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card title="Lead Priority & Company Trust" subtitle="Separate Lead Relevance priority vs preliminary Company Trust labels">
            <div className="grid h-64 grid-cols-2 gap-2">
              <div>
                <div className="text-center text-xs font-bold text-slate-600">Lead Priority</div>
                <ResponsiveContainer width="100%" height="90%">
                  <PieChart>
                    <Pie data={prioData} dataKey="value" nameKey="name" innerRadius={42} outerRadius={70} paddingAngle={4}>
                      {prioData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div>
                <div className="text-center text-xs font-bold text-slate-600">Company Trust</div>
                <ResponsiveContainer width="100%" height="90%">
                  <PieChart>
                    <Pie data={trustData} dataKey="value" nameKey="name" innerRadius={42} outerRadius={70} paddingAngle={4}>
                      {trustData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
