import { cn } from "@/lib/utils";
import type { Participant } from "@/lib/api/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ParticipantStack({
  participants,
  className,
}: {
  participants: Participant[];
  className?: string;
}) {
  return (
    <div className={cn("flex -space-x-2", className)}>
      {participants.slice(0, 6).map((p) => (
        <Tooltip key={p.id}>
          <TooltipTrigger asChild>
            <div
              className="relative flex h-7 w-7 items-center justify-center rounded-full border-2 border-sidebar text-[11px] font-semibold"
              style={{ backgroundColor: p.color, color: "#101418" }}
            >
              {p.display_name.slice(0, 2).toUpperCase()}
              <span
                className={cn(
                  "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-sidebar",
                  p.connection === "connected" && "bg-live",
                  p.connection === "reconnecting" && "bg-warn",
                  p.connection === "offline" && "bg-offline",
                )}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {p.display_name} · {p.role} · {p.connection}
          </TooltipContent>
        </Tooltip>
      ))}
      {participants.length > 6 && (
        <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-sidebar bg-secondary text-[11px]">
          +{participants.length - 6}
        </div>
      )}
    </div>
  );
}

export function StatusDot({ state }: { state: "connected" | "reconnecting" | "offline" }) {
  const map = {
    connected: ["bg-live", "Connected"],
    reconnecting: ["bg-warn animate-pulse", "Reconnecting"],
    offline: ["bg-offline", "Offline"],
  } as const;
  const [color, label] = map[state];
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", color)} />
      {label}
    </span>
  );
}

export function StateBadge({ state }: { state: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        state === "live" && "border-live/40 bg-live/10 text-live",
        state === "draft" && "border-warn/40 bg-warn/10 text-warn",
        state === "ended" && "border-border bg-secondary text-muted-foreground",
        state === "archived" && "border-border bg-transparent text-muted-foreground/70",
      )}
    >
      {state}
    </span>
  );
}
