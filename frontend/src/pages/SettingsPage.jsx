import { useState, useEffect } from "react";
import { Settings, Save, Database, CheckCircle2, Sparkles } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, ErrorBox, Loading, INDUSTRY_META } from "../components/ui";
import { Badge } from "../components/badges";

export default function SettingsPage() {
  const { source } = useSource();
  const inds = useApi(() => api.industries(source), [source]);
  const health = useApi(() => api.health(), []);
  const [selectedSlug, setSelectedSlug] = useState("manufacturing");
  const [desc, setDesc] = useState("");
  const [keywords, setKeywords] = useState("");
  const [subMap, setSubMap] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const current = (inds.data || []).find((i) => i.slug === selectedSlug) || (inds.data || [])[0];

  useEffect(() => {
    if (current) {
      setDesc(current.description || "");
      setKeywords((current.keywords || []).join(", "));
      const formatted = {};
      Object.entries(current.sub_industry_details || {}).forEach(([k, kws]) => {
        formatted[k] = (kws || []).join(", ");
      });
      setSubMap(formatted);
    }
  }, [current?.slug, inds.data]);

  const handleSave = async () => {
    if (!current) return;
    setSaving(true); setMsg(null);
    try {
      const subPayload = {};
      Object.entries(subMap).forEach(([k, v]) => {
        subPayload[k] = v.split(",").map((s) => s.trim()).filter(Boolean);
      });
      const res = await api.updateIndustryConfig(current.slug, {
        description: desc,
        keywords: keywords.split(",").map((s) => s.trim()).filter(Boolean),
        sub_industries: subPayload,
      });
      setMsg({
        type: "ok",
        text: `Saved ${res.updated} taxonomy & rebuilt ChromaDB knowledge base (${res.kb_chunks} active vector chunks).`,
      });
      inds.reload();
      health.reload();
    } catch (e) {
      setMsg({ type: "err", text: errorMessage(e) });
    } finally {
      setSaving(false);
    }
  };

  if (inds.loading && !inds.data) return <Loading label="Loading industry taxonomy settings…" />;
  if (inds.error) return <ErrorBox message={inds.error} onRetry={inds.reload} />;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 p-5 text-white shadow-lg shadow-indigo-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <Settings className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
                <Sparkles className="h-3 w-3" /> Configurable YAML + SQL + ChromaDB Vector Sync
              </div>
              <h1 className="text-xl font-extrabold">Settings &amp; Industry Taxonomy Management</h1>
              <p className="text-xs text-white/90">
                Customize descriptions, keywords, and sub-industries for all four target industries. Saving automatically re-embeds and updates ChromaDB.
              </p>
            </div>
          </div>
          {health.data && (
            <div className="rounded-xl bg-white/15 px-3.5 py-2 text-xs">
              <div>Vector KB Chunks: <b>{health.data.knowledge_base?.chunks}</b></div>
              <div>Reviewed RAG Examples: <b>{health.data.knowledge_base?.reviewed_examples}</b></div>
            </div>
          )}
        </div>
      </div>

      {msg && (
        <div className={`rounded-xl border p-4 text-sm font-medium ${msg.type === "ok" ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-rose-300 bg-rose-50 text-rose-900"}`}>
          {msg.text}
        </div>
      )}

      {/* Industry selector pills */}
      <div className="flex flex-wrap gap-2.5">
        {(inds.data || []).map((ind) => {
          const meta = INDUSTRY_META[ind.name] || INDUSTRY_META.Manufacturing;
          const active = ind.slug === current?.slug;
          return (
            <button
              key={ind.slug}
              onClick={() => setSelectedSlug(ind.slug)}
              className={`cursor-pointer rounded-xl border px-4 py-2.5 text-sm font-extrabold transition-all ${
                active ? `border-transparent bg-gradient-to-r ${meta.gradient} text-white shadow-md` : "border-indigo-100 bg-white text-slate-700 hover:bg-indigo-50"
              }`}
            >
              {ind.display_name} <span className="ml-1.5 rounded-full bg-black/15 px-2 py-0.5 text-xs">{ind.leads}</span>
            </button>
          );
        })}
      </div>

      {current && (
        <Card
          title={`Configure ${current.display_name} Taxonomy & RAG Prompts`}
          subtitle="Persisted in industries.yaml, industry_taxonomy & sub_industries SQL tables, and ChromaDB vector store"
          actions={
            <Button variant="primary" disabled={saving} onClick={handleSave}>
              <Save className="h-4 w-4" /> {saving ? "Re-indexing ChromaDB…" : "Save & Rebuild ChromaDB KB"}
            </Button>
          }
        >
          <div className="space-y-4 text-sm">
            <label className="block font-bold text-slate-800">
              Industry Description
              <textarea
                rows={2}
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                className="mt-1 w-full rounded-xl border border-indigo-200 p-3 text-sm font-normal"
              />
            </label>

            <label className="block font-bold text-slate-800">
              Primary Industry Keywords (comma-separated)
              <input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                className="mt-1 w-full rounded-xl border border-indigo-200 px-3 py-2 text-sm font-normal"
              />
            </label>

            <div>
              <div className="mb-2 text-xs font-extrabold uppercase tracking-wider text-indigo-900">
                Sub-Industries &amp; Sub-Industry Keywords ({Object.keys(subMap).length})
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {Object.entries(subMap).map(([subName, kws]) => (
                  <div key={subName} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="font-bold text-slate-900">{subName}</span>
                      <Badge color="blue">Sub-industry</Badge>
                    </div>
                    <input
                      value={kws}
                      onChange={(e) => setSubMap((m) => ({ ...m, [subName]: e.target.value }))}
                      className="w-full rounded-lg border border-indigo-200 bg-white px-2.5 py-1.5 text-xs"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
