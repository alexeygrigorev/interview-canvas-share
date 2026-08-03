import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PanelsTopLeft, ShieldAlert } from "lucide-react";

export const Route = createFileRoute("/join/$token")({
  head: () => ({
    meta: [
      { title: "Join interview — System Design Interview Platform" },
      {
        name: "description",
        content: "Enter your display name to join a live system-design interview canvas.",
      },
      { property: "og:title", content: "Join a system-design interview" },
      { property: "og:description", content: "Enter your name and join the shared canvas." },
    ],
  }),
  component: Lobby,
});

function Lobby() {
  const { token } = Route.useParams();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["token", token],
    queryFn: () => api.inspectToken(token),
    retry: false,
  });

  const join = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const { participant, session } = await api.join(token, name.trim());
      sessionStorage.setItem(`sdip.me.${session.id}`, JSON.stringify(participant));
      navigate({ to: "/room/$sessionId", params: { sessionId: session.id } });
    } catch (err) {
      setBusy(false);
      alert((err as Error).message);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <PanelsTopLeft size={18} className="text-primary" />
          Sketchboard Interviews
        </div>

        {isLoading && <p className="mt-6 text-sm text-muted-foreground">Validating link…</p>}

        {error && (
          <div className="mt-6 flex gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <ShieldAlert size={18} className="shrink-0" />
            <span>{(error as Error).message}</span>
          </div>
        )}

        {data && (
          <>
            <h1 className="mt-6 text-xl font-semibold tracking-tight">{data.session.title}</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              {data.activeCount} participant{data.activeCount === 1 ? "" : "s"} currently in the room
            </p>

            <form onSubmit={join} className="mt-6 space-y-4">
              <div>
                <Label htmlFor="name">Display name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="mt-1.5"
                  autoFocus
                  required
                />
              </div>
              <p className="rounded-md border border-border bg-secondary/50 p-3 text-xs leading-relaxed text-muted-foreground">
                Everything you draw on the canvas is saved and reviewed by the interviewer. Use a
                recent desktop version of Chrome, Edge, Firefox, or Safari — phone editing is not
                supported.
              </p>
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Joining…" : "Join interview"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
