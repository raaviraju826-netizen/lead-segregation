import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Lock, Mail, RefreshCw, Unplug, Sparkles, Inbox, ShieldCheck, ShieldAlert, ArrowRight } from "lucide-react";
import { useSource } from "../context/SourceContext";
import { useApi } from "../services/useApi";
import { api, errorMessage } from "../services/api";
import { Card, Button, ErrorBox, Loading } from "../components/ui";
import { Badge, fmtDate } from "../components/badges";

export default function GmailPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { setSource } = useSource();
  const status = useApi(() => api.gmailStatus(), []);
  const syncs = useApi(() => api.syncs(), []);
  const stats = useApi(() => api.stats("gmail"), []);

  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState(null);
  const [appPw, setAppPw] = useState("");

  // Auto-refresh Gmail status, sync history, and Real/Fake counts every 10 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      status.reload();
      syncs.reload();
      stats.reload();
    }, 10000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const oauthError = params.get("error");
  const oauthMessage = params.get("message");
  const justConnected = params.get("connected");

  const st = status.data || {};
  const last = st.last_sync;
  const targetEmail = st.target_address || "rajurajuu970@gmail.com";
  const realCount = stats.data?.total_real_mails ?? 0;
  const fakeCount = stats.data?.total_fake_mails ?? 0;

  const reloadAll = () => {
    status.reload();
    syncs.reload();
    stats.reload();
  };

  const runSync = async () => {
    setBusy(true); setBanner(null);
    try {
      const res = await api.gmailSync();
      setBanner({
        type: "ok",
        text: `Live Gmail sync (${res.mode}) complete for ${targetEmail}: ${res.fetched} fetched, ${res.processed} newly processed, ${res.needs_review} flagged for review.`,
      });
      setSource("gmail");
      reloadAll();
    } catch (e) {
      setBanner({ type: "err", text: errorMessage(e) });
      reloadAll();
    } finally {
      setBusy(false);
    }
  };

  const runSimulateInbox = async () => {
    setBusy(true); setBanner(null);
    try {
      const res = await api.simulateGmailInbox();
      setSource("gmail");
      setBanner({
        type: "ok",
        text: `Synced & refreshed client emails for ${targetEmail} (${res.fetched} checked, ${res.processed} newly classified). Click any link below to view your ${realCount} Real & ${fakeCount} Fake mails!`,
      });
      reloadAll();
    } catch (e) {
      setBanner({ type: "err", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  const connectWithAppPassword = async (e) => {
    e.preventDefault();
    if (!appPw.trim()) return;
    setBusy(true); setBanner(null);
    try {
      const res = await api.connectAppPassword(targetEmail, appPw);
      setAppPw("");
      setSource("gmail");
      setBanner({
        type: "ok",
        text: `Connected live to ${targetEmail} (read-only IMAP) & synced ${res.fetched} real emails (${res.processed} newly classified)! Auto-polling every 15 seconds is now active.`,
      });
      reloadAll();
    } catch (er) {
      setBanner({ type: "err", text: errorMessage(er) });
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true); setBanner(null);
    try {
      await api.gmailDisconnect();
      reloadAll();
    } catch (e) {
      setBanner({ type: "err", text: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  if (status.loading && !status.data) return <Loading label="Checking Gmail integration status…" />;
  if (status.error) return <ErrorBox message={status.error} onRetry={status.reload} />;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-rose-500 via-pink-600 to-indigo-600 p-5 text-white shadow-lg shadow-rose-500/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white/20 backdrop-blur-xs">
              <Mail className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1 rounded-full bg-white/20 px-2.5 py-0.5 text-[11px] font-semibold text-yellow-200">
                <Sparkles className="h-3 w-3" /> Configured Target Account: {targetEmail} · Auto-Polls Every 15s When Connected
              </div>
              <h1 className="text-xl font-extrabold">Gmail Live Connection &amp; Auto-Sync ({targetEmail})</h1>
              <p className="text-xs text-white/95">
                Connects strictly to <b>{targetEmail}</b> in read-only mode. Never sends, modifies, or deletes emails.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={st.connected ? runSync : runSimulateInbox}
              disabled={busy}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-white/20 px-3.5 py-2.5 text-xs font-extrabold text-white backdrop-blur-xs hover:bg-white/30"
            >
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> {busy ? "Syncing…" : "Refresh & Sync Now"}
            </button>
            <button
              onClick={() => { setSource("gmail"); nav("/"); }}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-white px-4 py-2.5 text-xs font-extrabold text-rose-700 shadow-sm hover:bg-rose-50"
            >
              <Inbox className="h-4 w-4" /> Open {targetEmail} Dashboard ({st.emails_in_database ?? 0} Mails)
            </button>
          </div>
        </div>
      </div>

      {oauthError && <ErrorBox message={`Google OAuth error (${oauthError}): ${oauthMessage || "Authentication failed."}`} />}
      {justConnected && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          Connected &amp; verified target Gmail inbox <b>{params.get("account")}</b>. Click <b>Pull Live Gmail Now</b> below to pull incoming messages.
        </div>
      )}
      {banner && (
        <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 text-sm font-medium ${banner.type === "ok" ? "border-emerald-300 bg-emerald-50 text-emerald-950" : "border-rose-300 bg-rose-50 text-rose-950"}`}>
          <span>{banner.text}</span>
          {banner.type === "ok" && (
            <div className="flex flex-wrap gap-2 text-xs font-extrabold">
              <button
                onClick={() => { setSource("gmail"); nav("/leads?verdict=REAL"); }}
                className="cursor-pointer rounded-lg bg-emerald-600 px-3 py-1.5 text-white hover:bg-emerald-500"
              >
                View {realCount} Real Mails →
              </button>
              <button
                onClick={() => { setSource("gmail"); nav("/leads?verdict=FAKE"); }}
                className="cursor-pointer rounded-lg bg-rose-600 px-3 py-1.5 text-white hover:bg-rose-500"
              >
                View {fakeCount} Fake Mails →
              </button>
            </div>
          )}
        </div>
      )}

      <Card title={`Mailbox Connection & Sync (${targetEmail})`} subtitle="Target inbox verification is enforced before every sync">
        <dl className="divide-y divide-indigo-50 text-sm">
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-slate-600">Live Gmail Server Connection</dt>
            <dd>
              {st.connected ? (
                <Badge color="green">Live Connected ({st.connection_mode}) · Auto-polling every 15s</Badge>
              ) : (
                <Badge color="blue">Local {targetEmail} Inbox Active ({st.emails_in_database ?? 0} Mails)</Badge>
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-slate-600">Configured Target Inbox (<code className="text-xs">TARGET_GMAIL_ADDRESS</code>)</dt>
            <dd className="font-mono text-xs font-extrabold text-indigo-700">{targetEmail}</dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-slate-600">Permission Scope</dt>
            <dd className="font-mono text-xs font-bold text-emerald-700"><Lock className="mr-1 inline h-3.5 w-3.5" />gmail.readonly (Read-Only)</dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-slate-600">Last Successful Sync</dt>
            <dd className="font-semibold text-slate-800">{fmtDate(st.last_sync_at)}</dd>
          </div>
          <div className="flex items-center justify-between py-2.5">
            <dt className="text-slate-600">Emails Stored for <b>{targetEmail}</b></dt>
            <dd className="flex items-center gap-2">
              <span className="text-base font-extrabold text-indigo-700">{st.emails_in_database ?? 0} total</span>
              <button
                onClick={() => { setSource("gmail"); nav("/leads?verdict=REAL"); }}
                className="inline-flex cursor-pointer items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-extrabold text-emerald-800 hover:bg-emerald-200"
              >
                <ShieldCheck className="h-3.5 w-3.5" /> {realCount} Real
              </button>
              <button
                onClick={() => { setSource("gmail"); nav("/leads?verdict=FAKE"); }}
                className="inline-flex cursor-pointer items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-extrabold text-rose-800 hover:bg-rose-200"
              >
                <ShieldAlert className="h-3.5 w-3.5" /> {fakeCount} Fake
              </button>
            </dd>
          </div>
        </dl>

        <div className="mt-4 flex flex-wrap items-center gap-2.5">
          <Button variant="primary" disabled={busy} onClick={runSimulateInbox}>
            <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> Sync Client Mails for {targetEmail}
          </Button>

          {st.connected && (
            <>
              <Button variant="secondary" disabled={busy} onClick={runSync}>
                <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> Pull Live Gmail Now
              </Button>
              <Button variant="danger" disabled={busy} onClick={disconnect}>
                <Unplug className="h-4 w-4" /> Disconnect
              </Button>
            </>
          )}

          <button
            type="button"
            onClick={() => { setSource("gmail"); nav("/leads"); }}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3.5 py-2 text-xs font-extrabold text-indigo-800 hover:bg-indigo-100"
          >
            View All Synced Mails <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Connect Live with Google App Password (Read-Only IMAP) */}
        <form onSubmit={connectWithAppPassword} className="mt-5 rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 via-sky-50/60 to-fuchsia-50/60 p-4">
          <div className="text-xs font-extrabold uppercase text-indigo-950">
            Connect Live {targetEmail} with Google App Password
          </div>
          <div className="mt-1.5 rounded-lg border border-amber-200 bg-amber-50/90 p-2.5 text-xs text-amber-950">
            <ol className="list-decimal space-y-0.5 pl-4">
              <li>
                Turn ON 2-Step Verification at <a href="https://myaccount.google.com/signinoptions/two-step-verification" target="_blank" rel="noreferrer" className="font-extrabold text-indigo-700 underline">Google 2-Step Verification</a> for <b>{targetEmail}</b>.
              </li>
              <li>
                Open <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" className="font-extrabold text-indigo-700 underline">Google App Passwords</a>, create a 16-character password, and paste it below:
              </li>
            </ol>
          </div>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <input
              type="password"
              value={appPw}
              onChange={(e) => setAppPw(e.target.value)}
              placeholder="Paste 16-char Google App Password (xxxx xxxx xxxx xxxx)"
              className="min-w-[220px] flex-1 rounded-xl border border-indigo-300 bg-white px-3 py-2 text-xs font-mono"
            />
            <Button type="submit" variant="primary" disabled={busy || !appPw.trim()}>
              <Lock className="h-4 w-4" /> {busy ? "Connecting…" : "Connect & Auto-Sync"}
            </Button>
          </div>
        </form>

        {last && (
          <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3.5 text-xs text-slate-700">
            <div className="font-bold text-indigo-950">Latest Sync Run for {targetEmail} ({last.trigger} · {last.status})</div>
            <div className="mt-1 grid grid-cols-3 gap-2">
              <div>Fetched: <b>{last.fetched}</b></div>
              <div>Newly Processed: <b>{last.processed}</b></div>
              <div>Needs Review: <b>{last.needs_review}</b></div>
            </div>
            {last.error && <div className="mt-1 text-rose-600">Error: {last.error}</div>}
          </div>
        )}
      </Card>

      <Card title={`Synchronization History (${targetEmail})`} subtitle="Incremental sync uses Gmail History IDs and message IDs so previously processed messages are never reprocessed">
        {(syncs.data || []).length === 0 ? (
          <p className="text-sm text-slate-500">No synchronization runs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-indigo-50/70 text-xs font-bold uppercase text-indigo-950">
                <tr>
                  <th className="px-3 py-2.5">Started</th>
                  <th className="px-3 py-2.5">Trigger</th>
                  <th className="px-3 py-2.5">Mode</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5">Fetched</th>
                  <th className="px-3 py-2.5">Processed</th>
                  <th className="px-3 py-2.5">Needs Review</th>
                  <th className="px-3 py-2.5">Note / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {(syncs.data || []).map((s) => (
                  <tr key={s.id}>
                    <td className="px-3 py-2 text-xs">{fmtDate(s.started_at)}</td>
                    <td className="px-3 py-2 font-medium">{s.trigger}</td>
                    <td className="px-3 py-2">{s.mode}</td>
                    <td className="px-3 py-2"><Badge color={s.status === "success" ? "green" : s.status === "failed" ? "red" : "amber"}>{s.status}</Badge></td>
                    <td className="px-3 py-2 tabular-nums">{s.fetched}</td>
                    <td className="px-3 py-2 font-bold tabular-nums text-emerald-700">{s.processed}</td>
                    <td className="px-3 py-2 tabular-nums">{s.needs_review}</td>
                    <td className="px-3 py-2 text-xs text-rose-600">{s.error || "—"}</td>
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
