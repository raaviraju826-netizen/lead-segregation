const tone = {
  green: "bg-gradient-to-r from-emerald-500/15 to-teal-500/15 text-emerald-800 ring-emerald-300",
  amber: "bg-gradient-to-r from-amber-500/15 to-orange-500/15 text-amber-900 ring-amber-300",
  red: "bg-gradient-to-r from-rose-500/15 to-pink-500/15 text-rose-800 ring-rose-300",
  slate: "bg-slate-100 text-slate-700 ring-slate-300",
  blue: "bg-gradient-to-r from-blue-500/15 to-cyan-500/15 text-blue-800 ring-blue-300",
  violet: "bg-gradient-to-r from-violet-500/15 to-fuchsia-500/15 text-violet-800 ring-violet-300",
  orange: "bg-gradient-to-r from-orange-500/15 to-amber-500/15 text-orange-800 ring-orange-300",
};

export function Badge({ color = "slate", children, title }) {
  return (
    <span title={title} className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${tone[color] || tone.slate}`}>
      {children}
    </span>
  );
}

const IND_TONE = { Manufacturing: "blue", Education: "violet", "IT & Software": "green", "Logistics & Transportation": "orange" };
export const IndustryBadge = ({ industry }) => <Badge color={IND_TONE[industry] || "slate"}>{industry}</Badge>;

const STATUS_TONE = { Classified: "green", "Needs Review": "amber", "Other / Unknown": "slate", "Not a Lead": "slate", "Suspicious — Review Required": "red" };
export const StatusBadge = ({ status }) => <Badge color={STATUS_TONE[status] || "slate"}>{status}</Badge>;

const RISK_TONE = { Low: "green", Medium: "amber", High: "red", Unknown: "slate" };
export const RiskBadge = ({ risk }) => <Badge color={RISK_TONE[risk] || "slate"}>{risk} risk</Badge>;

const TRUST_TONE = { Verified: "green", "Partially Verified": "blue", Unverified: "slate", "Conflicting Evidence": "red" };
export const TrustBadge = ({ label }) => <Badge color={TRUST_TONE[label] || "slate"}>{label}</Badge>;

const PRIO_TONE = { High: "red", Medium: "amber", Low: "blue" };
export const PriorityBadge = ({ priority }) => <Badge color={PRIO_TONE[priority]}>{priority} priority</Badge>;

export function Score({ value, max = 100, decimals = 0, title }) {
  const pctVal = Math.max(0, Math.min(100, (value / max) * 100));
  const bar =
    pctVal >= 70
      ? "bg-gradient-to-r from-emerald-400 to-teal-500"
      : pctVal >= 40
      ? "bg-gradient-to-r from-amber-400 to-orange-500"
      : "bg-gradient-to-r from-rose-400 to-pink-500";
  return (
    <div className="flex min-w-[92px] items-center gap-2" title={title}>
      <span className="w-9 text-right text-sm font-bold tabular-nums text-slate-800">{Number(value).toFixed(decimals)}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 ring-1 ring-inset ring-slate-200/70">
        <div className={`h-2 rounded-full ${bar}`} style={{ width: `${pctVal}%` }} />
      </div>
    </div>
  );
}

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
export const pct = (x) => `${Math.round(x * 100)}%`;
