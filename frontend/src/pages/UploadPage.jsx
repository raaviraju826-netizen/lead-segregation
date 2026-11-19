import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileSpreadsheet, Mail, CheckCircle2, Download, Send, Sparkles, Copy, ExternalLink, Factory, GraduationCap, Code2, Truck } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, ErrorBox } from "../components/ui";
import { Badge, fmtDate } from "../components/badges";

const TARGET_INBOX = "rajurajuu970@gmail.com";

const CLIENT_TEMPLATES = [
  {
    key: "manufacturing",
    label: "Manufacturing Client",
    icon: Factory,
    color: "from-blue-600 to-cyan-500",
    sender_name: "Rohit Verma",
    sender_email: "rohit.verma@bharatmachinery.co.in",
    subject: "Enquiry: IoT Production Monitoring & ERP for our CNC Factory",
    body: `Hello Team,

We are an industrial machinery and automotive component manufacturing company operating two CNC production plants in Ahmedabad with 350 employees.

We are looking for an ERP and IoT production monitoring dashboard for our factory assembly lines. Our budget is Rs 12 Lakh and we would like to schedule a demo within 4 weeks.

Please share your proposal and pricing.

Best regards,
Rohit Verma
General Manager - Operations
Bharat Industrial Machinery Pvt Ltd
+91 98250 12345
https://www.bharatmachinery.co.in`,
  },
  {
    key: "education",
    label: "Education & EdTech Client",
    icon: GraduationCap,
    color: "from-violet-600 to-fuchsia-500",
    sender_name: "Dr. Anita Menon",
    sender_email: "admissions@sunriseengineering.edu.in",
    subject: "Requirement: Online Admissions Portal & Website Redesign for our College",
    body: `Dear Team,

I am writing from Sunrise Institute of Engineering & Technology. We are an autonomous engineering college with over 4,200 undergraduate and postgraduate students on our Bengaluru campus.

Our admissions department requires a new college website and online student admissions management portal before the upcoming semester intake.

Kindly share a quotation and implementation timeline.

Warm regards,
Dr. Anita Menon
Dean of Admissions
Sunrise Institute of Engineering & Technology
+91 98450 11223
https://www.sunriseengineering.edu.in`,
  },
  {
    key: "it-software",
    label: "IT & Software Client",
    icon: Code2,
    color: "from-cyan-500 to-emerald-500",
    sender_name: "Sanjay Patel",
    sender_email: "sanjay@cloudnimbus.io",
    subject: "Partnership & Mobile App Development for our SaaS Platform",
    body: `Hi Team,

CloudNimbus Technologies is a B2B SaaS and custom software development company providing cloud DevOps and analytics tools to enterprise clients.

We are looking for a development partner to build a companion iOS and Android mobile app for our SaaS platform within 3 months.

Please let us know if we can schedule a call this week.

Best regards,
Sanjay Patel
Founder & CTO
CloudNimbus Technologies Pvt Ltd
+91 98111 90909
https://www.cloudnimbus.io`,
  },
  {
    key: "logistics",
    label: "✓ REAL Logistics Client",
    icon: Truck,
    color: "from-orange-500 to-rose-500",
    sender_name: "Harpreet Singh",
    sender_email: "harpreet@swifthaulcargo.in",
    subject: "RFQ: Fleet Tracking & Warehouse Inventory Software",
    body: `Hello,

SwiftHaul Cargo Carriers is a freight transportation, 3PL warehousing, and supply chain logistics company operating a fleet of 220 trucks across India.

We need a GPS fleet management and warehouse inventory tracking web application with driver mobile apps. Kindly send your quotation and technical proposal.

Thanks & Regards,
Harpreet Singh
Head of Operations
SwiftHaul Cargo Carriers Pvt Ltd
+91 98150 77889
https://www.swifthaulcargo.in`,
  },
  {
    key: "fake-scam",
    label: "✗ FAKE Scam Mail (Test Fake Detection)",
    icon: Mail,
    color: "from-rose-600 to-red-700",
    sender_name: "Accounts Billing",
    sender_email: "billing@steel-factory-pay.com",
    subject: "Urgent payment: Steel manufacturing plant revised bank account",
    body: `Hello,

We are a steel manufacturing company and industrial machinery factory. Our bank details have changed.

Urgent payment required: kindly wire transfer the invoice amount to our revised bank account within 24 hours and verify your account password or share your bank details immediately.

Global Steel Manufacturing Ltd`,
  },
];

const SAMPLE_CSV = `sender_name,sender_email,subject,body,received_at
"Dr. Kavita Nair","kavita@imperialcollege.edu.in","Campus admission portal & website","Hello, We are an engineering and management college with 3,500 students on campus. We need a new website and online admissions portal before June. Regards, Dr. Kavita Nair, Dean of Admissions, Imperial College of Engineering, +91 98450 33445","2026-11-15T09:30:00Z"
"Rakesh Sharma","rakesh@precisionauto.co.in","ERP for our automotive factory","Hi, Precision Auto Components Pvt Ltd manufactures automotive gears and chassis parts in our two Pune factories. We are looking for an ERP system for inventory management. Regards, Rakesh Sharma, Plant Director, Precision Auto Components Pvt Ltd, +91 98200 11223","2026-11-15T11:00:00Z"
"Megha Kapoor","megha@cloudpulse.io","SaaS partnership enquiry","Hello, CloudPulse Technologies is a SaaS and cloud DevOps software company. We would like to explore a channel partnership for custom software integration. Regards, Megha Kapoor, VP Partnerships, CloudPulse Technologies","2026-11-16T14:15:00Z"
"Arjun Gill","arjun@rapidcargo.in","Fleet tracking mobile app","Dear team, RapidCargo Logistics operates a fleet of 180 freight trucks and 3PL warehouses. We require a fleet tracking mobile app for drivers. Regards, Arjun Gill, Operations Head, RapidCargo Logistics Pvt Ltd, +91 98111 77889","2026-11-17T16:45:00Z"
`;

const MAP_FIELDS = [
  ["sender_name", "Sender Name Column"],
  ["sender_email", "Sender Email Column"],
  ["subject", "Subject Column"],
  ["body", "Email Body Column"],
  ["received_at", "Received Date Column"],
];

export default function UploadPage() {
  const nav = useNavigate();
  const { setSource } = useSource();
  const batches = useApi(() => api.batches(), []);

  const [file, setFile] = useState(null);
  const [csvHeaders, setCsvHeaders] = useState([]);
  const [mapping, setMapping] = useState({ sender_name: "", sender_email: "", subject: "", body: "", received_at: "" });
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);

  const [single, setSingle] = useState({
    sender_name: CLIENT_TEMPLATES[0].sender_name,
    sender_email: CLIENT_TEMPLATES[0].sender_email,
    subject: CLIENT_TEMPLATES[0].subject,
    body: CLIENT_TEMPLATES[0].body,
    target_source: "gmail",
  });

  const applyTemplate = (tpl) => {
    setSingle((s) => ({
      ...s,
      sender_name: tpl.sender_name,
      sender_email: tpl.sender_email,
      subject: tpl.subject,
      body: tpl.body,
    }));
  };

  const copyFormattedEmail = () => {
    const raw = `To: ${TARGET_INBOX}\nFrom: ${single.sender_name} <${single.sender_email}>\nSubject: ${single.subject}\n\n${single.body}`;
    navigator.clipboard.writeText(raw);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const gmailComposeUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(TARGET_INBOX)}&su=${encodeURIComponent(single.subject)}&body=${encodeURIComponent(single.body)}`;

  const onFileSelect = async (f) => {
    setFile(f);
    setResult(null);
    setErr(null);
    setCsvHeaders([]);
    if (f && f.name.toLowerCase().endsWith(".csv")) {
      const slice = await f.slice(0, 4096).text();
      const firstLine = slice.split(/\r?\n/)[0] || "";
      const hdrs = firstLine.split(",").map((h) => h.trim().replace(/^"|"$/g, "")).filter(Boolean);
      setCsvHeaders(hdrs);
      const auto = { sender_name: "", sender_email: "", subject: "", body: "", received_at: "" };
      hdrs.forEach((h) => {
        const low = h.toLowerCase();
        if (!auto.sender_name && (low.includes("name") || low === "author" || low === "contact")) auto.sender_name = h;
        if (!auto.sender_email && (low.includes("email") || low.includes("mail") || low === "from")) auto.sender_email = h;
        if (!auto.subject && (low.includes("subject") || low.includes("title"))) auto.subject = h;
        if (!auto.body && (low.includes("body") || low.includes("message") || low.includes("content") || low.includes("text"))) auto.body = h;
        if (!auto.received_at && (low.includes("date") || low.includes("time") || low.includes("received"))) auto.received_at = h;
      });
      setMapping(auto);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setBusy(true); setErr(null); setResult(null); setProgress(10);
    try {
      const res = await api.uploadFile(file, {
        columnMapping: file.name.toLowerCase().endsWith(".csv") ? mapping : undefined,
        source: "upload",
        onProgress: setProgress,
      });
      setResult(res);
      setSource("upload");
      batches.reload();
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
      setProgress(0);
    }
  };

  const [classifiedLead, setClassifiedLead] = useState(null);

  const handleSingleIngest = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null); setResult(null); setClassifiedLead(null);
    try {
      const res = await api.ingestEmail({
        source: single.target_source || "gmail",
        emails: [
          {
            sender_name: single.sender_name,
            sender_email: single.sender_email,
            subject: single.subject,
            body: single.body,
            headers: { To: TARGET_INBOX, "Delivered-To": TARGET_INBOX },
          },
        ],
      });
      setResult(res);
      if (res.email_ids?.length) {
        const detail = await api.lead(res.email_ids[res.email_ids.length - 1]);
        setClassifiedLead(detail);
      }
      setSource(single.target_source || "gmail");
      batches.reload();
    } catch (er) {
      setErr(errorMessage(er));
    } finally {
      setBusy(false);
    }
  };

  const downloadSampleCsv = () => {
    const blob = new Blob([SAMPLE_CSV], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: "leadsense_sample_leads.csv" });
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-fuchsia-600 p-5 text-white shadow-lg shadow-indigo-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <UploadCloud className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
                <Sparkles className="h-3 w-3" /> Automatic Real vs Fake Keyword Detector + 4-Industry Classifier ({TARGET_INBOX})
              </div>
              <h1 className="text-xl font-extrabold">Client Email Real/Fake Checker &amp; Multi-File Upload</h1>
              <p className="text-xs text-white/90">
                When a client mail arrives for <b>{TARGET_INBOX}</b>, the AI automatically says whether it is <b>REAL</b> or <b>FAKE</b> based on keywords &amp; score, and classifies its industry with accuracy %.
              </p>
            </div>
          </div>
          <button
            onClick={downloadSampleCsv}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-white px-3.5 py-2 text-xs font-bold text-indigo-800 shadow-sm hover:bg-indigo-50"
          >
            <Download className="h-4 w-4" /> Download Sample CSV
          </button>
        </div>
      </div>

      {err && <ErrorBox message={err} />}

      {classifiedLead && (
        <div
          className={`rounded-2xl border p-5 shadow-lg ${
            classifiedLead.verdict === "FAKE"
              ? "border-rose-300 bg-gradient-to-r from-rose-50 via-pink-50 to-orange-50 text-rose-950"
              : "border-emerald-300 bg-gradient-to-r from-emerald-50 via-teal-50 to-cyan-50 text-emerald-950"
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1 text-sm font-extrabold text-white shadow-sm ${
                    classifiedLead.verdict === "FAKE" ? "bg-gradient-to-r from-rose-600 to-red-600" : "bg-gradient-to-r from-emerald-600 to-teal-600"
                  }`}
                >
                  {classifiedLead.verdict === "FAKE" ? "✗ AUTOMATIC RESULT: FAKE / SCAM MAIL" : "✓ AUTOMATIC RESULT: REAL CLIENT MAIL"}
                </span>
                <span className="rounded-xl bg-white px-3 py-1 text-sm font-extrabold shadow-xs">
                  Real/Fake Score: {classifiedLead.real_fake_score}%
                </span>
                <span className="rounded-xl bg-indigo-600 px-3 py-1 text-sm font-extrabold text-white shadow-xs">
                  Industry: {classifiedLead.industry} ({classifiedLead.sub_industry || "General"}) · Accuracy: {classifiedLead.accuracy_score}%
                </span>
              </div>
              <p className="text-xs font-semibold">{classifiedLead.verdict_reason}</p>
              <div className="flex flex-wrap gap-1.5">
                {classifiedLead.verdict === "FAKE"
                  ? (classifiedLead.fake_keywords || []).map((kw, i) => (
                      <span key={i} className="rounded-full bg-rose-200 px-2.5 py-0.5 text-xs font-extrabold text-rose-950">
                        Fake Keyword: “{kw}”
                      </span>
                    ))
                  : (classifiedLead.real_keywords || []).map((kw, i) => (
                      <span key={i} className="rounded-full bg-emerald-200 px-2.5 py-0.5 text-xs font-extrabold text-emerald-950">
                        Real Keyword: “{kw}”
                      </span>
                    ))}
              </div>
            </div>
            <Button variant="primary" onClick={() => nav(`/leads/${classifiedLead.id}`)}>
              Open Full Evidence &amp; Score Report
            </Button>
          </div>

          <div className="mt-4 border-t border-black/10 pt-3">
            <div className="mb-2 text-xs font-extrabold uppercase tracking-wider">
              Click Any of the 4 Industries Below to See How Many REAL Mails &amp; How Many FAKE Mails Are in That Industry:
            </div>
            <div className="grid gap-2.5 sm:grid-cols-4">
              {[
                ["manufacturing", "Manufacturing", "from-blue-600 to-cyan-500"],
                ["education", "Education & EdTech", "from-violet-600 to-fuchsia-500"],
                ["it-software", "IT & Software", "from-cyan-500 to-emerald-500"],
                ["logistics", "Logistics & Transport", "from-orange-500 to-rose-500"],
              ].map(([slug, label, grad]) => (
                <button
                  key={slug}
                  type="button"
                  onClick={() => nav(`/industry/${slug}`)}
                  className={`cursor-pointer rounded-xl bg-gradient-to-r ${grad} px-3.5 py-2.5 text-left text-xs font-extrabold text-white shadow-md hover:opacity-95`}
                >
                  <div>{label}</div>
                  <div className="mt-0.5 text-[11px] font-medium text-white/90">Click to view Real vs Fake count →</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {result && !classifiedLead && (
        <div className="rounded-2xl border border-emerald-300 bg-gradient-to-r from-emerald-50 via-teal-50 to-cyan-50 p-4 text-sm text-emerald-950 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-bold">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              Received &amp; classified into LeadSense AI: {result.processed_records} newly classified, {result.duplicate_records} duplicates skipped, {result.needs_review_records} flagged for review.
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => nav("/leads")}>
                Open Leads Table
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Client Email Format Composer for rajurajuu970@gmail.com */}
      <Card
        title={`Client Request Format Addressed to ${TARGET_INBOX}`}
        subtitle="Click any industry template below to load the exact email format a client sends to rajurajuu970@gmail.com. You can send it via Gmail or ingest it directly."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={copyFormattedEmail}>
              <Copy className="h-4 w-4" /> {copied ? "Copied!" : "Copy Email Format"}
            </Button>
            <a
              href={gmailComposeUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100"
            >
              <Mail className="h-4 w-4" /> Open in Gmail Compose (to {TARGET_INBOX}) <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        }
      >
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase text-slate-500">Load Client Template:</span>
          {CLIENT_TEMPLATES.map((tpl) => {
            const Icon = tpl.icon;
            return (
              <button
                key={tpl.key}
                type="button"
                onClick={() => applyTemplate(tpl)}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-gradient-to-r ${tpl.color} px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:opacity-95`}
              >
                <Icon className="h-3.5 w-3.5" /> {tpl.label}
              </button>
            );
          })}
        </div>

        <form onSubmit={handleSingleIngest} className="space-y-3 text-xs">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 px-3 py-2">
              <div className="text-[11px] font-bold uppercase text-emerald-700">Receiving Inbox (To)</div>
              <div className="mt-1 font-mono text-sm font-extrabold text-emerald-950">{TARGET_INBOX}</div>
            </div>
            <label className="block font-semibold text-slate-700">
              Client Sender Name (From)
              <input
                value={single.sender_name}
                onChange={(e) => setSingle({ ...single, sender_name: e.target.value })}
                className="mt-1 w-full rounded-xl border border-indigo-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="block font-semibold text-slate-700">
              Client Sender Email (From) *
              <input
                required
                type="email"
                value={single.sender_email}
                onChange={(e) => setSingle({ ...single, sender_email: e.target.value })}
                className="mt-1 w-full rounded-xl border border-indigo-200 px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            <label className="block font-semibold text-slate-700 sm:col-span-3">
              Subject Line (What the client is requesting)
              <input
                value={single.subject}
                onChange={(e) => setSingle({ ...single, subject: e.target.value })}
                className="mt-1 w-full rounded-xl border border-indigo-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="block font-semibold text-slate-700">
              Store Under Inbox Bucket
              <select
                value={single.target_source}
                onChange={(e) => setSingle({ ...single, target_source: e.target.value })}
                className="mt-1 w-full rounded-xl border border-indigo-200 bg-white px-3 py-2 text-sm"
              >
                <option value="gmail">Gmail Inbox ({TARGET_INBOX})</option>
                <option value="upload">Uploaded Files</option>
              </select>
            </label>
          </div>

          <label className="block font-semibold text-slate-700">
            Email Body &amp; Signature (Paragraph 1: Client's business description · Paragraph 2: Requested product/service · Bottom: Signature with Name, Title, Company, Phone, Website)
            <textarea
              rows={10}
              value={single.body}
              onChange={(e) => setSingle({ ...single, body: e.target.value })}
              className="mt-1 w-full rounded-xl border border-indigo-200 bg-slate-50/60 p-3 font-mono text-xs leading-relaxed text-slate-800"
            />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <span className="text-xs text-slate-500">
              Tip: Click <b>Open in Gmail Compose</b> above to send this exact email from any browser to <b>{TARGET_INBOX}</b>, or click the button on the right to simulate receiving it immediately.
            </span>
            <Button type="submit" variant="primary" disabled={busy}>
              <Send className="h-4 w-4" /> {busy ? "Processing…" : `Receive into ${TARGET_INBOX} & Classify Now`}
            </Button>
          </div>
        </form>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Bulk Upload CSV, EML, MSG, or MBOX File" subtitle="Flexible CSV column mapping for sender_name, sender_email, subject, body, received_at">
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-indigo-300 bg-gradient-to-br from-indigo-50/70 via-sky-50/50 to-fuchsia-50/60 p-8 text-center transition hover:border-indigo-500">
            <FileSpreadsheet className="mb-2 h-10 w-10 text-indigo-600" />
            <span className="text-sm font-bold text-slate-800">
              {file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : "Click to choose a .csv, .eml, .msg, or .mbox file"}
            </span>
            <span className="mt-1 text-xs text-slate-500">Automatic header detection + custom column mapping for CSV files</span>
            <input
              type="file"
              accept=".csv,.eml,.msg,.mbox"
              className="hidden"
              onChange={(e) => onFileSelect(e.target.files?.[0] || null)}
            />
          </label>

          {csvHeaders.length > 0 && (
            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5">
              <div className="mb-2 text-xs font-bold uppercase text-indigo-900">CSV Column Mapping (Flexible Header Mapper)</div>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {MAP_FIELDS.map(([key, label]) => (
                  <label key={key} className="block text-xs font-medium text-slate-700">
                    {label}
                    <select
                      value={mapping[key] || ""}
                      onChange={(e) => setMapping((m) => ({ ...m, [key]: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-indigo-200 bg-white px-2.5 py-1.5 text-xs"
                    >
                      <option value="">(Auto-detect / None)</option>
                      {csvHeaders.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </div>
          )}

          {busy && progress > 0 && (
            <div className="mt-4">
              <div className="mb-1 flex justify-between text-xs font-semibold text-indigo-700">
                <span>Uploading &amp; running RAG pipeline…</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-indigo-100">
                <div className="h-2 rounded-full bg-gradient-to-r from-indigo-600 to-fuchsia-600 transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          <div className="mt-4 flex justify-end">
            <Button variant="primary" disabled={!file || busy} onClick={handleUpload}>
              <UploadCloud className="h-4 w-4" /> {busy ? "Processing File…" : "Upload & Classify Leads"}
            </Button>
          </div>
        </Card>

        <Card title="Recommended Client Email Structure for Best AI Accuracy" subtitle={`When a client emails ${TARGET_INBOX}, LeadSense AI extracts 7 key signals:`}>
          <div className="space-y-2.5 text-xs text-slate-700">
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
              <div className="font-bold text-indigo-950">1. Recipient &amp; Sender Header</div>
              <div className="mt-0.5 font-mono text-[11px] text-slate-600">
                To: {TARGET_INBOX}<br />
                From: Client Name &lt;name@companydomain.com&gt;<br />
                Subject: Requirement / RFQ / Proposal for [Requested Service]
              </div>
            </div>
            <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-3">
              <div className="font-bold text-violet-950">2. Paragraph 1 — Sender's Business Identity (Determines Industry)</div>
              <div className="mt-0.5 text-slate-600">
                <i>“We are an [automotive component manufacturer / engineering college / SaaS company / freight logistics carrier] operating [plants / campus / platform / fleet]…”</i>
              </div>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3">
              <div className="font-bold text-emerald-950">3. Paragraph 2 — Requested Product/Service (Determines Interest Area &amp; Relevance)</div>
              <div className="mt-0.5 text-slate-600">
                <i>“We are looking for [website development / ERP implementation / mobile app / fleet tracking software] with a timeline of [X weeks] and budget of [Rs/USD]…”</i>
              </div>
            </div>
            <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3">
              <div className="font-bold text-amber-950">4. Email Signature (Determines Contact, Company &amp; Trust Score)</div>
              <div className="mt-0.5 font-mono text-[11px] text-slate-600">
                Best regards,<br />
                [Full Name]<br />
                [Job Title / Designation]<br />
                [Registered Company Name Pvt Ltd / University]<br />
                [+91 Phone Number]<br />
                [https://www.companywebsite.com]
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Upload & Ingestion Batch History" subtitle="Persisted in the upload_batches table">
        {(batches.data || []).length === 0 ? (
          <p className="text-sm text-slate-500">No files uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-indigo-50/70 text-xs font-bold uppercase text-indigo-950">
                <tr>
                  <th className="px-3 py-2.5">Batch</th>
                  <th className="px-3 py-2.5">Filename</th>
                  <th className="px-3 py-2.5">Format</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5">Total</th>
                  <th className="px-3 py-2.5">Processed</th>
                  <th className="px-3 py-2.5">Duplicates</th>
                  <th className="px-3 py-2.5">Needs Review</th>
                  <th className="px-3 py-2.5">Uploaded At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {(batches.data || []).map((b) => (
                  <tr key={b.id}>
                    <td className="px-3 py-2 font-bold">#{b.id}</td>
                    <td className="px-3 py-2 font-medium text-slate-900">{b.filename}</td>
                    <td className="px-3 py-2 uppercase"><Badge color="blue">{b.file_type}</Badge></td>
                    <td className="px-3 py-2"><Badge color={b.status === "completed" ? "green" : "red"}>{b.status}</Badge></td>
                    <td className="px-3 py-2 tabular-nums">{b.total_records}</td>
                    <td className="px-3 py-2 font-bold tabular-nums text-emerald-700">{b.processed_records}</td>
                    <td className="px-3 py-2 tabular-nums text-amber-700">{b.duplicate_records}</td>
                    <td className="px-3 py-2 tabular-nums text-indigo-700">{b.needs_review_records}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{fmtDate(b.created_at)}</td>
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
