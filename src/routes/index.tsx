import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api/mock-api";
import { StateBadge } from "@/components/Presence";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  Link2,
  Copy,
  Archive,
  MoreHorizontal,
  PanelsTopLeft,
  Radio,
  RotateCcw,
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Interview dashboard — System Design Interview Platform" },
      {
        name: "description",
        content:
          "Create, share, and review live system-design interviews on a collaborative infinite canvas.",
      },
      { property: "og:title", content: "System Design Interview Platform" },
      {
        property: "og:description",
        content: "Run live system-design interviews on a shared realtime canvas.",
      },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: api.getCurrentUser });
  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["sessions"] });

  const copyLink = async (id: string) => {
    const link = await api.createGuestLink(id);
    const url = `${window.location.origin}/join/${link.token}`;
    await navigator.clipboard.writeText(url).catch(() => {});
    toast.success("Candidate link copied", { description: url });
    refresh();
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-sidebar">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-4">
          <PanelsTopLeft className="text-primary" size={20} />
          <span className="text-sm font-semibold tracking-tight">Sketchboard Interviews</span>
          <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            MVP v1.0 · mocked API
          </span>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-muted-foreground">{user?.email}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
              {user?.display_name.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Interviews</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Every session owns a canvas, a revocable candidate link, and a saved final snapshot.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                api.resetMockData();
                refresh();
                toast.success("Mock data reset");
              }}
            >
              <RotateCcw size={14} /> Reset mock data
            </Button>
            <Button onClick={() => navigate({ to: "/interviews/new" })}>
              <Plus size={16} /> New interview
            </Button>
          </div>
        </div>

        <div className="mt-8 overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-card text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">Participants</th>
                <th className="px-4 py-3 font-medium">Last modified</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    Loading sessions…
                  </td>
                </tr>
              )}
              {sessions?.map((s) => (
                <tr key={s.id} className="border-t border-border hover:bg-card/60">
                  <td className="px-4 py-3">
                    <Link
                      to={s.state === "ended" || s.state === "archived" ? "/review/$sessionId" : "/room/$sessionId"}
                      params={{ sessionId: s.id }}
                      className="font-medium hover:text-primary"
                    >
                      {s.title}
                    </Link>
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{s.prompt}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StateBadge state={s.state} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.participants.length
                      ? s.participants.map((p) => p.display_name).join(", ")
                      : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {new Date(s.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => navigate({ to: "/room/$sessionId", params: { sessionId: s.id } })}
                      >
                        <Radio size={13} /> Open
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label={`Actions for ${s.title}`}>
                            <MoreHorizontal size={16} />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => copyLink(s.id)}>
                            <Link2 size={14} /> Copy candidate link
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() =>
                              api.duplicateSession(s.id).then(() => {
                                toast.success("Duplicated as a new draft");
                                refresh();
                              })
                            }
                          >
                            <Copy size={14} /> Duplicate
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() =>
                              api.archiveSession(s.id).then(() => {
                                toast.success("Archived");
                                refresh();
                              })
                            }
                          >
                            <Archive size={14} /> Archive
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-6 text-xs text-muted-foreground">
          Backend is mocked in the browser. Open a candidate link in a second tab to see realtime
          presence and canvas sync.
        </p>
      </main>
    </div>
  );
}
