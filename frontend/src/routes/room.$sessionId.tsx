import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api, subscribe } from "@/lib/api/api";
import type { CanvasElement, InterviewSession, Participant } from "@/lib/api/types";
import { useCanvasDoc } from "@/lib/canvas/useCanvasDoc";
import { useRoomPresence } from "@/lib/canvas/useRoomPresence";
import { makeNode, offsetCopy, type Tool, type Viewport } from "@/lib/canvas/geometry";
import { CanvasStage } from "@/components/canvas/CanvasStage";
import { ToolRail } from "@/components/canvas/ToolRail";
import { PalettePanel } from "@/components/canvas/PalettePanel";
import { PropertiesPanel } from "@/components/canvas/PropertiesPanel";
import { ParticipantStack, StateBadge, StatusDot } from "@/components/Presence";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Undo2,
  Redo2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Share2,
  Lock,
  Unlock,
  Settings2,
  MoreVertical,
  ArrowLeft,
  Eye,
  EyeOff,
  Trash,
} from "lucide-react";

export const Route = createFileRoute("/room/$sessionId")({
  head: () => ({
    meta: [
      { title: "Live interview canvas — Whiteboard for system design" },
      {
        name: "description",
        content:
          "Collaborative infinite canvas for live system-design interviews: components, connectors, freehand, and realtime presence.",
      },
      { property: "og:title", content: "Live interview canvas" },
      {
        property: "og:description",
        content: "Realtime collaborative whiteboard for system-design interviews.",
      },
    ],
  }),
  component: Room,
});

function useSessionQuery(sessionId: string) {
  return useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId),
    retry: false,
  });
}

function Room() {
  const { sessionId } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data, isLoading, error } = useSessionQuery(sessionId);
  const [me, setMe] = useState<Participant | null>(null);
  const [session, setSession] = useState<InterviewSession | null>(null);

  useEffect(() => {
    if (data?.session) setSession(data.session);
  }, [data?.session]);

  // Guest identity established in the lobby; otherwise join as the owner.
  useEffect(() => {
    const raw = typeof window !== "undefined" ? sessionStorage.getItem(`sdip.me.${sessionId}`) : null;
    if (raw) {
      setMe(JSON.parse(raw) as Participant);
      return;
    }
    api.joinAsOwner(sessionId).then(setMe);
  }, [sessionId]);

  useEffect(
    () =>
      subscribe(sessionId, (msg) => {
        if (msg.type === "permission_changed") setSession(msg.session);
        if (msg.type === "session_ended") {
          setSession((s) => (s ? { ...s, state: "ended" } : s));
          toast.info("The interviewer ended this session. The canvas is now read-only.");
        }
      }),
    [sessionId],
  );

  if (isLoading || !session || !me) {
    return <Centered>Loading interview…</Centered>;
  }
  if (error) {
    return <Centered>{(error as Error).message}</Centered>;
  }

  return (
    <RoomInner
      session={session}
      setSession={setSession}
      me={me}
      onLeave={() => {
        qc.invalidateQueries({ queryKey: ["sessions"] });
        navigate({ to: "/" });
      }}
    />
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

function RoomInner({
  session,
  setSession,
  me,
  onLeave,
}: {
  session: InterviewSession;
  setSession: (s: InterviewSession) => void;
  me: Participant;
  onLeave: () => void;
}) {
  const isOwner = me.role === "owner";
  const sessionOpen = session.state === "draft" || session.state === "live";
  const canEdit =
    sessionOpen &&
    me.role !== "observer" &&
    (me.role !== "candidate" || session.candidate_editing_enabled);

  const { elements, commit, undo, redo, saveState } = useCanvasDoc(session.id, me.id, canEdit);
  const { peers, sendCursor } = useRoomPresence(session.id, me);
  const [tool, setTool] = useState<Tool>("select");
  const [selection, setSelection] = useState<string[]>([]);
  const [inkColor, setInkColor] = useState("#5eead4");
  const [inkWidth, setInkWidth] = useState(2);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [connection] = useState<"connected" | "reconnecting" | "offline">("connected");
  const vpApi = useRef<{
    zoomBy: (f: number) => void;
    fit: () => void;
    reset: () => void;
    viewport: Viewport;
  } | null>(null);
  const [zoomLabel, setZoomLabel] = useState(100);

  const registerViewportApi = useCallback((apiRef: NonNullable<typeof vpApi.current>) => {
    vpApi.current = apiRef;
    setZoomLabel(Math.round(apiRef.viewport.z * 100));
  }, []);

  const selected = useMemo(
    () => elements.filter((e) => selection.includes(e.id)),
    [elements, selection],
  );

  const placeComponent = (type: string) => {
    const el = makeNode(type, 240 + Math.random() * 220, 200 + Math.random() * 180, me.id);
    commit((prev) => [...prev, el]);
    setSelection([el.id]);
  };

  const deleteSelection = () => {
    commit((prev) =>
      prev.filter(
        (el) =>
          !selection.includes(el.id) &&
          !(el.kind === "connector" && (selection.includes(el.from) || selection.includes(el.to))),
      ),
    );
    setSelection([]);
  };

  const duplicateSelection = () => {
    const copies = selected.map((e) => offsetCopy(e, 24)).filter(Boolean) as CanvasElement[];
    commit((prev) => [...prev, ...copies]);
    setSelection(copies.map((c) => c.id));
  };

  const toggleLock = async () => {
    const next = await api.updateSession(session.id, {
      candidate_editing_enabled: !session.candidate_editing_enabled,
    });
    setSession(next);
    toast.success(next.candidate_editing_enabled ? "Candidate editing unlocked" : "Candidate editing locked");
  };

  const copyLink = async () => {
    const link = await api.createGuestLink(session.id);
    const url = `${window.location.origin}/join/${link.token}`;
    await navigator.clipboard.writeText(url).catch(() => {});
    toast.success("Candidate link copied", { description: url });
  };

  const endSession = async () => {
    const next = await api.endSession(session.id);
    setSession(next);
    toast.success("Interview ended. Final snapshot saved.");
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* top bar */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-sidebar px-3">
        <Button variant="ghost" size="icon" aria-label="Back to dashboard" onClick={onLeave}>
          <ArrowLeft size={17} />
        </Button>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-sm font-semibold">{session.title}</h1>
            <StateBadge state={session.state} />
          </div>
          <div className="flex items-center gap-3">
            <StatusDot state={connection} />
            <span className="text-xs text-muted-foreground">
              {saveState === "saved"
                ? "All changes saved"
                : saveState === "error"
                  ? "Save failed — retrying"
                  : "Saving…"}
            </span>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {!canEdit && (
            <span className="rounded-md border border-warn/40 bg-warn/10 px-2 py-1 text-xs text-warn">
              {session.state === "ended" ? "Session ended — read only" : "Editing locked"}
            </span>
          )}
          <SessionTimer session={session} />
          <ParticipantStack participants={peers} />
          {isOwner && (
            <>
              <Button variant="secondary" size="sm" onClick={copyLink}>
                <Share2 size={14} /> Share
              </Button>
              <Button variant="secondary" size="sm" onClick={toggleLock}>
                {session.candidate_editing_enabled ? <Unlock size={14} /> : <Lock size={14} />}
                {session.candidate_editing_enabled ? "Lock" : "Unlock"}
              </Button>
              <OwnerMenu
                session={session}
                setSession={setSession}
                onClear={() => commit(() => [])}
                peers={peers}
                meId={me.id}
              />
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm" disabled={!sessionOpen}>
                    End interview
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>End this interview?</AlertDialogTitle>
                    <AlertDialogDescription>
                      The canvas becomes read-only for candidates and a final snapshot is saved.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={endSession}>End interview</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <ToolRail
          tool={tool}
          setTool={setTool}
          disabled={!canEdit}
          snapEnabled={snapEnabled}
          setSnapEnabled={setSnapEnabled}
        />
        <PalettePanel onPlace={placeComponent} disabled={!canEdit} />

        <div className="relative min-w-0 flex-1">
          <CanvasStage
            elements={elements}
            commit={commit}
            canEdit={canEdit}
            tool={tool}
            setTool={setTool}
            inkColor={inkColor}
            inkWidth={inkWidth}
            snapEnabled={snapEnabled}
            selection={selection}
            setSelection={setSelection}
            actorId={me.id}
            actorColor={me.color}
            peers={peers}
            cursorsVisible={session.cursors_visible}
            onCursor={sendCursor}
            registerViewportApi={registerViewportApi}
          />

          {/* bottom controls */}
          <div className="pointer-events-auto absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-lg border border-border bg-card/95 p-1 shadow-lg backdrop-blur">
            <Button variant="ghost" size="icon" aria-label="Undo" onClick={undo} disabled={!canEdit}>
              <Undo2 size={16} />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Redo" onClick={redo} disabled={!canEdit}>
              <Redo2 size={16} />
            </Button>
            <span className="mx-1 h-5 w-px bg-border" />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Zoom out"
              onClick={() => {
                vpApi.current?.zoomBy(1 / 1.25);
                setZoomLabel((z) => Math.max(10, Math.round(z / 1.25)));
              }}
            >
              <ZoomOut size={16} />
            </Button>
            <button
              type="button"
              onClick={() => {
                vpApi.current?.reset();
                setZoomLabel(100);
              }}
              className="w-14 font-mono text-xs text-muted-foreground hover:text-foreground"
            >
              {zoomLabel}%
            </button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Zoom in"
              onClick={() => {
                vpApi.current?.zoomBy(1.25);
                setZoomLabel((z) => Math.min(400, Math.round(z * 1.25)));
              }}
            >
              <ZoomIn size={16} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Zoom to fit"
              onClick={() => vpApi.current?.fit()}
            >
              <Maximize2 size={16} />
            </Button>
          </div>

          {session.state === "ended" && (
            <div className="pointer-events-none absolute inset-x-0 top-4 mx-auto w-fit rounded-md border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow">
              This interview has ended.{" "}
              <Link to="/review/$sessionId" params={{ sessionId: session.id }} className="pointer-events-auto text-primary underline">
                Open review
              </Link>
            </div>
          )}
        </div>

        <PropertiesPanel
          session={session}
          selected={selected}
          commit={commit}
          canEdit={canEdit}
          inkColor={inkColor}
          setInkColor={setInkColor}
          inkWidth={inkWidth}
          setInkWidth={setInkWidth}
          onDelete={deleteSelection}
          onDuplicate={duplicateSelection}
        />
      </div>
    </div>
  );
}

function SessionTimer({ session }: { session: InterviewSession }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!session.started_at) return null;
  const elapsed = Math.max(
    0,
    Math.floor(
      ((session.ended_at ? Date.parse(session.ended_at) : now) - Date.parse(session.started_at)) /
        1000,
    ),
  );
  const total = session.duration_minutes * 60;
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return (
    <span
      className={`font-mono text-sm ${elapsed > total ? "text-offline" : "text-muted-foreground"}`}
    >
      {mm}:{ss}
      <span className="ml-1 text-xs opacity-60">/ {session.duration_minutes}m</span>
    </span>
  );
}

function OwnerMenu({
  session,
  setSession,
  onClear,
  peers,
  meId,
}: {
  session: InterviewSession;
  setSession: (s: InterviewSession) => void;
  onClear: () => void;
  peers: Participant[];
  meId: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Session controls">
          <MoreVertical size={17} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Session controls</DropdownMenuLabel>
        {session.state === "draft" && (
          <DropdownMenuItem onSelect={() => api.startSession(session.id).then(setSession)}>
            <Settings2 size={14} /> Start session
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onSelect={() =>
            api
              .updateSession(session.id, { cursors_visible: !session.cursors_visible })
              .then(setSession)
          }
        >
          {session.cursors_visible ? <EyeOff size={14} /> : <Eye size={14} />}
          {session.cursors_visible ? "Hide cursors" : "Show cursors"}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">Participants</DropdownMenuLabel>
        {peers
          .filter((p) => p.id !== meId)
          .map((p) => (
            <DropdownMenuItem
              key={p.id}
              onSelect={() => {
                api.removeParticipant(session.id, p.id);
                toast.success(`${p.display_name} removed`);
              }}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
              Remove {p.display_name}
            </DropdownMenuItem>
          ))}
        {peers.filter((p) => p.id !== meId).length === 0 && (
          <DropdownMenuItem disabled>No other participants</DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onSelect={() => {
            onClear();
            toast.success("Canvas cleared", { description: "Undo restores the previous state." });
          }}
        >
          <Trash size={14} /> Clear canvas
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
