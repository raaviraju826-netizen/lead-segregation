import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export const INDUSTRY_META = {
  Manufacturing: {
    slug: "manufacturing",
    color: "#2563eb",
    gradient: "from-blue-600 via-indigo-500 to-cyan-500",
    softBg: "from-blue-50 via-indigo-50/70 to-cyan-50",
    border: "border-blue-200 hover:border-blue-400",
    iconBg: "bg-gradient-to-br from-blue-500 to-cyan-500 text-white shadow-md shadow-blue-500/25",
    bg: "bg-blue-100/80",
    text: "text-blue-700",
    ring: "ring-blue-300",
  },
  Education: {
    slug: "education",
    color: "#8b5cf6",
    gradient: "from-violet-600 via-purple-500 to-fuchsia-500",
    softBg: "from-violet-50 via-purple-50/70 to-fuchsia-50",
    border: "border-violet-200 hover:border-violet-400",
    iconBg: "bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-500/25",
    bg: "bg-violet-100/80",
    text: "text-violet-700",
    ring: "ring-violet-300",
  },
  "IT & Software": {
    slug: "it-software",
    color: "#06b6d4",
    gradient: "from-cyan-500 via-teal-500 to-emerald-500",
    softBg: "from-cyan-50 via-teal-50/70 to-emerald-50",
    border: "border-cyan-200 hover:border-cyan-400",
    iconBg: "bg-gradient-to-br from-cyan-500 to-emerald-500 text-white shadow-md shadow-cyan-500/25",
    bg: "bg-cyan-100/80",
    text: "text-cyan-700",
    ring: "ring-cyan-300",
  },
  "Logistics & Transportation": {
    slug: "logistics",
    color: "#f97316",
    gradient: "from-orange-500 via-amber-500 to-rose-500",
    softBg: "from-orange-50 via-amber-50/70 to-rose-50",
    border: "border-orange-200 hover:border-orange-400",
    iconBg: "bg-gradient-to-br from-orange-500 to-rose-500 text-white shadow-md shadow-orange-500/25",
    bg: "bg-orange-100/80",
    text: "text-orange-700",
    ring: "ring-orange-300",
  },
};

export function Loading({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-16 font-medium text-indigo-600" role="status">
      <Loader2 className="h-5 w-5 animate-spin text-fuchsia-500" /> {label}
    </div>
  );
}

export function EmptyState({ title = "Nothing to show", hint, children }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center text-slate-600">
      <div className="mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo-100 via-purple-100 to-pink-100 text-indigo-600 shadow-inner">
        <Inbox className="h-7 w-7" />
      </div>
      <p className="text-base font-semibold text-slate-800">{title}</p>
      {hint && <p className="mt-1 max-w-md text-sm text-slate-500">{hint}</p>}
      {children}
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-gradient-to-r from-rose-50 to-orange-50 p-4 text-sm text-rose-900 shadow-sm" role="alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
      <div className="flex-1 font-medium">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="rounded-lg border border-rose-300 bg-white px-2.5 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100">
          Retry
        </button>
      )}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={`rounded-2xl border border-indigo-100/90 bg-white/95 shadow-md shadow-indigo-500/5 backdrop-blur-sm ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-t-2xl border-b border-indigo-100/80 bg-gradient-to-r from-indigo-50/60 via-sky-50/40 to-fuchsia-50/50 px-5 py-3.5">
          <div>
            <h2 className="text-sm font-bold text-slate-900">{title}</h2>
            {subtitle && <p className="text-xs text-slate-600">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Button({ variant = "secondary", className = "", ...props }) {
  const styles = {
    primary: "bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shadow-md shadow-indigo-500/25 hover:from-indigo-500 hover:via-violet-500 hover:to-fuchsia-500 disabled:opacity-50",
    secondary: "border border-indigo-200 bg-white text-indigo-950 shadow-xs hover:border-indigo-300 hover:bg-indigo-50/60 disabled:opacity-50",
    danger: "border border-rose-300 bg-gradient-to-r from-rose-50 to-orange-50 text-rose-700 hover:from-rose-100 hover:to-orange-100 disabled:opacity-50",
    success: "bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-md shadow-emerald-500/25 hover:from-emerald-400 hover:to-teal-400 disabled:opacity-50",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-150 disabled:cursor-not-allowed ${styles} ${className}`}
    />
  );
}
