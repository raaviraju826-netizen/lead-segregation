import { useState } from "react";
import { FileSpreadsheet, FileText, Download, Sparkles, Factory, GraduationCap, Code2, Truck, Layers } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { api, errorMessage } from "../services/api";
import { Button, ErrorBox } from "../components/ui";

const TARGETS = [
  {
    slug: "",
    name: "Complete Multi-Sheet Report (All 8 Sheets)",
    desc: "Includes Summary, All Leads, Manufacturing, Education, IT & Software, Logistics & Transportation, Needs Review, and Suspicious — Review Required.",
    gradient: "from-indigo-50 via-violet-50 to-fuchsia-50 border-indigo-200",
    bar: "from-indigo-600 via-violet-600 to-fuchsia-600",
    icon: Layers,
    iconBg: "from-indigo-600 to-fuchsia-600",
  },
  {
    slug: "manufacturing",
    name: "Manufacturing Leads Only",
    desc: "Export only leads classified under Manufacturing (Automotive, Textile, Electronics, Industrial Machinery, Chemical, Other).",
    gradient: "from-blue-50 via-indigo-50/70 to-cyan-50 border-blue-200",
    bar: "from-blue-600 to-cyan-500",
    icon: Factory,
    iconBg: "from-blue-600 to-cyan-500",
  },
  {
    slug: "education",
    name: "Education Leads Only",
    desc: "Export only leads classified under Education (Schools, Colleges & Universities, Coaching, EdTech, Training Institutes).",
    gradient: "from-violet-50 via-purple-50/70 to-fuchsia-50 border-violet-200",
    bar: "from-violet-600 to-fuchsia-500",
    icon: GraduationCap,
    iconBg: "from-violet-600 to-fuchsia-500",
  },
  {
    slug: "it-software",
    name: "IT & Software Leads Only",
    desc: "Export only leads classified under IT & Software (Custom Software, SaaS, Cloud/DevOps, AI & Data, Cybersecurity, IT Services).",
    gradient: "from-cyan-50 via-teal-50/70 to-emerald-50 border-cyan-200",
    bar: "from-cyan-500 to-emerald-500",
    icon: Code2,
    iconBg: "from-cyan-500 to-emerald-500",
  },
  {
    slug: "logistics",
    name: "Logistics & Transportation Leads Only",
    desc: "Export only leads classified under Logistics & Transportation (Freight, Courier, Warehousing, Fleet, Supply Chain).",
    gradient: "from-orange-50 via-amber-50/70 to-rose-50 border-orange-200",
    bar: "from-orange-500 to-rose-500",
    icon: Truck,
    iconBg: "from-orange-500 to-rose-500",
  },
];

export default function ExportPage() {
  const { source } = useSource();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState(null);

  const run = async (kind, industry) => {
    const key = `${kind}-${industry || "all"}`;
    setBusy(key); setErr(null);
    try {
      await api.download(kind, { source, industry: industry || undefined });
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 p-5 text-white shadow-lg shadow-indigo-500/20">
        <div className="flex items-center gap-3.5">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
            <Download className="h-6 w-6 text-white" />
          </div>
          <div>
            <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
              <Sparkles className="h-3 w-3" /> Formatted Pandas + OpenPyXL Workbooks
            </div>
            <h1 className="text-xl font-extrabold">Export Industry-Wise Excel &amp; CSV Reports</h1>
            <p className="text-xs text-white/90">
              Generating reports from <b>{source === "demo" ? "Demo Mode (48 synthetic emails)" : "Live Gmail Data"}</b> with styled headers, auto-filters, frozen panes, and formula-injection protection.
            </p>
          </div>
        </div>
      </div>

      {err && <ErrorBox message={err} />}

      <div className="grid gap-4 md:grid-cols-2">
        {TARGETS.map((t) => {
          const Icon = t.icon;
          return (
            <div
              key={t.slug || "all"}
              className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-5 shadow-md ${t.gradient} ${!t.slug ? "md:col-span-2" : ""}`}
            >
              <div className={`absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r ${t.bar}`} />
              <div className="flex items-start gap-3.5">
                <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br text-white shadow-md ${t.iconBg}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div className="flex-1">
                  <h2 className="text-base font-extrabold text-slate-900">{t.name}</h2>
                  <p className="mt-1 text-xs text-slate-600">{t.desc}</p>
                  <div className="mt-4 flex flex-wrap gap-2.5">
                    <Button variant="primary" disabled={busy !== ""} onClick={() => run("excel", t.slug)}>
                      <FileSpreadsheet className="h-4 w-4" />
                      {busy === `excel-${t.slug || "all"}` ? "Generating Excel…" : "Download Excel (.xlsx)"}
                    </Button>
                    <Button variant="secondary" disabled={busy !== ""} onClick={() => run("csv", t.slug)}>
                      <FileText className="h-4 w-4" />
                      {busy === `csv-${t.slug || "all"}` ? "Generating CSV…" : "Download CSV (.csv)"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
