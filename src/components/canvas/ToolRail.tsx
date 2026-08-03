import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Tool } from "@/lib/canvas/geometry";
import {
  MousePointer2,
  Hand,
  Pen,
  Highlighter,
  Eraser,
  Type,
  StickyNote,
  Spline,
  Grid3x3,
} from "lucide-react";

const TOOLS: { id: Tool; label: string; icon: typeof Pen; key: string }[] = [
  { id: "select", label: "Select", icon: MousePointer2, key: "V" },
  { id: "pan", label: "Pan", icon: Hand, key: "H" },
  { id: "connector", label: "Connector", icon: Spline, key: "L" },
  { id: "pen", label: "Pen", icon: Pen, key: "P" },
  { id: "highlighter", label: "Highlighter", icon: Highlighter, key: "" },
  { id: "eraser", label: "Eraser", icon: Eraser, key: "" },
  { id: "text", label: "Text", icon: Type, key: "" },
  { id: "note", label: "Sticky note", icon: StickyNote, key: "N" },
];

export function ToolRail({
  tool,
  setTool,
  disabled,
  snapEnabled,
  setSnapEnabled,
}: {
  tool: Tool;
  setTool: (t: Tool) => void;
  disabled: boolean;
  snapEnabled: boolean;
  setSnapEnabled: (v: boolean) => void;
}) {
  return (
    <div className="flex w-14 flex-col items-center gap-1 border-r border-border bg-sidebar py-3">
      {TOOLS.map((t) => (
        <Tooltip key={t.id}>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t.label}
              aria-pressed={tool === t.id}
              disabled={disabled && t.id !== "select" && t.id !== "pan"}
              onClick={() => setTool(t.id)}
              className={cn(
                "h-9 w-9 rounded-md text-muted-foreground hover:text-foreground",
                tool === t.id && "bg-primary/15 text-primary ring-1 ring-primary/40",
              )}
            >
              <t.icon size={17} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {t.label}
            {t.key && <span className="ml-2 font-mono text-xs opacity-60">{t.key}</span>}
          </TooltipContent>
        </Tooltip>
      ))}
      <div className="my-2 h-px w-7 bg-border" />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Snap to grid"
            aria-pressed={snapEnabled}
            onClick={() => setSnapEnabled(!snapEnabled)}
            className={cn(
              "h-9 w-9 rounded-md text-muted-foreground hover:text-foreground",
              snapEnabled && "bg-accent/15 text-accent ring-1 ring-accent/40",
            )}
          >
            <Grid3x3 size={17} />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">Snap to grid</TooltipContent>
      </Tooltip>
    </div>
  );
}
