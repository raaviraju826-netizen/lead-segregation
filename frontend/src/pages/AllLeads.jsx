import { useSearchParams } from "react-router-dom";
import { Table2, Sparkles, ShieldCheck, ShieldAlert } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api } from "../services/api";
import LeadsTable from "../components/LeadsTable";
import { Card } from "../components/ui";

export default function AllLeads() {
  const { source } = useSource();
  const [searchParams, setSearchParams] = useSearchParams();
  const verdict = searchParams.get("verdict") || "";
  const { data: stats } = useApi(() => api.stats(source), [source]);

  const setVerdict = (v) => {
    if (!v) setSearchParams({});
    else setSearchParams({ verdict: v });
  };

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-500 to-cyan-500 p-5 text-white shadow-lg shadow-emerald-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <Table2 className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
                <Sparkles className="h-3 w-3" /> Full Multi-Dimensional Explorer
              </div>
              <h1 className="text-xl font-extrabold">All Processed Emails &amp; Leads</h1>
              <p className="text-xs text-white/90">
                Search, sort, and filter across every processed message by Real vs. Fake verdict, industry, sub-industry, company trust, email risk, and status.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-extrabold">
            <button
              onClick={() => setVerdict("REAL")}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-xl px-3.5 py-2 transition ${
                verdict === "REAL"
                  ? "bg-white text-emerald-800 shadow-md"
                  : "bg-white/20 text-white hover:bg-white/30"
              }`}
            >
              <ShieldCheck className="h-4 w-4" /> Real Client Mails ({stats?.total_real_mails ?? 0})
            </button>
            <button
              onClick={() => setVerdict("FAKE")}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-xl px-3.5 py-2 transition ${
                verdict === "FAKE"
                  ? "bg-white text-rose-800 shadow-md"
                  : "bg-white/20 text-white hover:bg-white/30"
              }`}
            >
              <ShieldAlert className="h-4 w-4" /> Fake / Scam Mails ({stats?.total_fake_mails ?? 0})
            </button>
            <button
              onClick={() => setVerdict("")}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-xl px-3.5 py-2 transition ${
                !verdict
                  ? "bg-white text-teal-900 shadow-md"
                  : "bg-white/20 text-white hover:bg-white/30"
              }`}
            >
              All Inbox Emails ({stats?.total_emails ?? 0})
            </button>
          </div>
        </div>
      </div>
      <Card>
        <LeadsTable
          key={`${source}-${verdict}`}
          fetcher={(params) => api.leads({ ...params, source, ...(verdict ? { verdict } : {}) })}
          deps={[source, verdict]}
          filters={["industry", "status", "priority", "company_trust", "email_risk"]}
          exportContext={{ source, ...(verdict ? { verdict } : {}) }}
          emptyHint="No processed emails found for the current filter."
        />
      </Card>
    </div>
  );
}
