import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api/mock-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/interviews/new")({
  head: () => ({
    meta: [
      { title: "New interview — System Design Interview Platform" },
      {
        name: "description",
        content: "Create a system-design interview session with a title, prompt, and duration.",
      },
      { property: "og:title", content: "Create a system-design interview" },
      {
        property: "og:description",
        content: "Set a title, problem statement, and duration, then share a candidate link.",
      },
    ],
  }),
  component: NewInterview,
});

function NewInterview() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(60);
  const [scheduled, setScheduled] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return toast.error("A title is required");
    setBusy(true);
    const session = await api.createSession({
      title: title.trim(),
      prompt: prompt.trim(),
      duration_minutes: duration,
      scheduled_at: scheduled ? new Date(scheduled).toISOString() : null,
    });
    await api.startSession(session.id);
    toast.success("Interview created");
    navigate({ to: "/room/$sessionId", params: { sessionId: session.id } });
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={15} /> Dashboard
        </Link>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">New interview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          A draft session and a blank canvas are created. You can share the candidate link at any
          time.
        </p>

        <form onSubmit={submit} className="mt-8 space-y-5">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Senior Backend — Design a URL shortener"
              className="mt-1.5"
              required
            />
          </div>
          <div>
            <Label htmlFor="prompt">Problem statement</Label>
            <Textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              placeholder="Describe the system to design, constraints, and what you want the candidate to cover."
              className="mt-1.5"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Shown to the candidate immediately after they join (MVP default).
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="duration">Duration (minutes)</Label>
              <Input
                id="duration"
                type="number"
                min={15}
                max={180}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="scheduled">Scheduled for</Label>
              <Input
                id="scheduled"
                type="datetime-local"
                value={scheduled}
                onChange={(e) => setScheduled(e.target.value)}
                className="mt-1.5"
              />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create and open canvas"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => navigate({ to: "/" })}>
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
