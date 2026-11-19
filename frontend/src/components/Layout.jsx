import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, Download, Factory, GraduationCap, Code2, ListChecks, Mail, Sparkles, Table2, Truck, FlaskConical, UploadCloud, CopyCheck, LineChart, Settings, Layers } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api } from "../services/api";

const nav = [
  { to: "/", label: "Overview Dashboard", icon: BarChart3, end: true, color: "text-indigo-600", activeBg: "from-indigo-600 to-violet-600" },
  { to: "/upload", label: "Upload Emails / CSV", icon: UploadCloud, color: "text-blue-600", activeBg: "from-blue-600 to-indigo-600" },
  { to: "/gmail", label: "Gmail Integration", icon: Mail, color: "text-rose-600", activeBg: "from-rose-500 to-pink-600" },
  { to: "/leads", label: "All Leads", icon: Table2, color: "text-emerald-600", activeBg: "from-emerald-600 to-teal-500" },
  { to: "/industry/manufacturing", label: "Manufacturing", icon: Factory, sub: true, color: "text-blue-600", activeBg: "from-blue-600 to-cyan-500" },
  { to: "/industry/education", label: "Education & EdTech", icon: GraduationCap, sub: true, color: "text-violet-600", activeBg: "from-violet-600 to-fuchsia-500" },
  { to: "/industry/it-software", label: "IT & Software", icon: Code2, sub: true, color: "text-cyan-600", activeBg: "from-cyan-500 to-emerald-500" },
  { to: "/industry/logistics", label: "Logistics & Transport", icon: Truck, sub: true, color: "text-orange-600", activeBg: "from-orange-500 to-rose-500" },
  { to: "/review", label: "Needs Review", icon: ListChecks, color: "text-amber-600", activeBg: "from-amber-500 to-orange-500" },
  { to: "/duplicates", label: "Duplicate Management", icon: CopyCheck, color: "text-fuchsia-600", activeBg: "from-fuchsia-600 to-purple-600" },
  { to: "/analytics", label: "Analytics", icon: LineChart, color: "text-cyan-600", activeBg: "from-cyan-600 to-blue-600" },
  { to: "/settings", label: "Settings / Industries", icon: Settings, color: "text-violet-600", activeBg: "from-violet-600 to-indigo-600" },
  { to: "/export", label: "Export Reports", icon: Download, color: "text-purple-600", activeBg: "from-purple-600 to-indigo-600" },
];

export default function Layout() {
  const { source, setSource } = useSource();
  const health = useApi(() => api.health(), []);
  const mode = health.data?.llm_mode;
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-68 shrink-0 flex-col border-r border-indigo-100 bg-white/90 backdrop-blur-md md:flex">
        <div className="flex items-center gap-3 border-b border-indigo-100/80 bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 px-5 py-4 text-white">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/20 shadow-inner backdrop-blur-xs">
            <Sparkles className="h-5 w-5 text-yellow-200" />
          </div>
          <div>
            <div className="text-base font-extrabold tracking-tight">LeadSense AI</div>
            <div className="text-[11px] font-medium text-indigo-100">Lead Segregation &amp; Trust</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {nav.map(({ to, label, icon: Icon, end, sub, color, activeBg }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3.5 py-2 text-xs font-bold transition-all ${sub ? "ml-3" : ""} ${
                  isActive
                    ? `bg-gradient-to-r ${activeBg} text-white shadow-md shadow-indigo-500/20`
                    : "text-slate-700 hover:bg-indigo-50/70"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-white" : color}`} />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/80 via-sky-50/60 to-fuchsia-50/70 p-3 text-xs text-slate-700">
          <div className="mb-1 flex items-center gap-2 font-semibold">
            <span className={`h-2.5 w-2.5 rounded-full ${health.error ? "bg-rose-500" : "bg-emerald-500 ring-4 ring-emerald-500/20"}`} />
            {health.error ? "Backend offline" : "Engine Active & Ready"}
          </div>
          {mode && <div className="text-slate-600">Pipeline: <b className="text-indigo-700">{mode === "llm_rag" ? "LLM + Chroma RAG" : "Heuristic + Chroma RAG"}</b></div>}
          <div className="mt-0.5 truncate text-[11px] text-slate-500">Inbox: <b>{health.data?.target_gmail_address || "rajurajuu970@gmail.com"}</b></div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-indigo-100 bg-white/85 px-6 py-3 backdrop-blur-md">
          <div className="hidden items-center gap-2 md:flex">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-500" />
            <span className="bg-gradient-to-r from-indigo-700 via-violet-700 to-fuchsia-600 bg-clip-text text-sm font-bold text-transparent">
              AI-Powered Industry-Wise Lead Segregation &amp; Classification System
            </span>
          </div>
          <nav className="flex gap-1 overflow-x-auto md:hidden">
            {nav.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => `whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-semibold ${isActive ? "bg-indigo-600 text-white" : "text-slate-600"}`}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto inline-flex flex-wrap rounded-xl border border-indigo-200 bg-indigo-50/70 p-1 text-xs font-semibold" role="group" aria-label="Data source">
            {[
              ["all", "All Sources", Layers, "from-indigo-600 to-violet-600"],
              ["gmail", "Gmail Inbox", Mail, "from-rose-500 to-pink-600"],
              ["upload", "Uploaded Files", UploadCloud, "from-blue-600 to-cyan-500"],
              ["demo", "Demo (48)", FlaskConical, "from-amber-500 via-orange-500 to-pink-500"],
            ].map(([k, label, Icon, grad]) => (
              <button
                key={k}
                onClick={() => setSource(k)}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
                  source === k ? `bg-gradient-to-r ${grad} text-white shadow-sm` : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Icon className="h-3.5 w-3.5" /> {label}
              </button>
            ))}
          </div>
        </header>
        {source === "demo" && (
          <div className="border-b border-amber-300/80 bg-gradient-to-r from-amber-100/90 via-orange-100/80 to-pink-100/80 px-6 py-2 text-xs font-medium text-amber-950">
            <b className="rounded bg-amber-500 px-1.5 py-0.5 text-white">DEMO MODE</b>{" "}
            <span className="ml-1">Viewing 48 synthetic sample emails processed by the real RAG + scoring pipeline. Switch to “Gmail Inbox”, “Uploaded Files”, or “All Sources” above.</span>
          </div>
        )}
        <main className="mx-auto w-full max-w-[1440px] flex-1 p-6"><Outlet /></main>
      </div>
    </div>
  );
}
