import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/api";
import { StateBadge } from "@/components/Presence";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Download } from "lucide-react";

export const Route = createFileRoute("/review/$sessionId")({
  head: () => ({
    meta: [
      { title: "Interview review — System Design Interview Platform" },
      {
        name: "description",
        content: "Review the final saved canvas, participants, and audit trail of an interview.",
      },
      { property: "og:title", content: "Interview review" },
      { property: "og:description", content: "Final canvas snapshot and session audit trail." },
    ],
  }),
  component: Review,
});

function Review() {
  const { sessionId } = Route.useParams();
  const { data } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId),
    retry: false,
  });
  const { data: doc } = useQuery({
    queryKey: ["canvas", sessionId],
    queryFn: () => api.getCanvas(sessionId),
  });
  const { data: audit } = useQuery({
    queryKey: ["audit", sessionId],
    queryFn: () => api.getAudit(sessionId),
  });

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${sessionId}-canvas.json`;
    a.click();
  };

  if (!data) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={15} /> Dashboard
        </Link>
        <div className="mt-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{data.session.title}</h1>
              <StateBadge state={data.session.state} />
            </div>
            <p className="mt-2 max-w-2xl whitespace-pre-wrap text-sm text-muted-foreground">
              {data.session.prompt}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={exportJson}>
              <Download size={14} /> Export JSON
            </Button>
            <Button size="sm" asChild>
              <Link to="/room/$sessionId" params={{ sessionId }}>
                Open canvas
              </Link>
            </Button>
          </div>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-4">
          {[
            ["Elements", doc?.elements.length ?? 0],
            ["Participants", data.participants.length],
            [
              "Duration",
              data.session.started_at && data.session.ended_at
                ? `${Math.round(
                    (Date.parse(data.session.ended_at) - Date.parse(data.session.started_at)) / 60000,
                  )}m`
                : "—",
            ],
            ["Snapshot", doc ? new Date(doc.updated_at).toLocaleTimeString() : "—"],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
              <p className="mt-1 font-mono text-lg">{value}</p>
            </div>
          ))}
        </div>

        <h2 className="mt-10 text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Audit trail
        </h2>
        <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
          {(audit ?? []).map((a) => (
            <li key={a.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
              <span className="font-mono text-xs text-primary">{a.event}</span>
              <span className="text-xs text-muted-foreground">{new Date(a.at).toLocaleString()}</span>
            </li>
          ))}
          {!audit?.length && (
            <li className="px-4 py-3 text-sm text-muted-foreground">No recorded events.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
