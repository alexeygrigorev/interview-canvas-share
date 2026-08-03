import type { CanvasElement, ConnectorElement, NodeElement, InterviewSession } from "@/lib/api/types";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Trash2, Copy, ArrowLeftRight } from "lucide-react";

const INK = ["#5eead4", "#fbbf24", "#f472b6", "#a78bfa", "#60a5fa", "#f87171", "#e2e8f0"];

interface Props {
  session: InterviewSession;
  selected: CanvasElement[];
  commit: (fn: (prev: CanvasElement[]) => CanvasElement[]) => void;
  canEdit: boolean;
  inkColor: string;
  setInkColor: (c: string) => void;
  inkWidth: number;
  setInkWidth: (w: number) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}

export function PropertiesPanel({
  session,
  selected,
  commit,
  canEdit,
  inkColor,
  setInkColor,
  inkWidth,
  setInkWidth,
  onDelete,
  onDuplicate,
}: Props) {
  const single = selected.length === 1 ? selected[0] : null;
  const patch = (id: string, p: Partial<CanvasElement>) =>
    commit((prev) => prev.map((el) => (el.id === id ? ({ ...el, ...p } as CanvasElement) : el)));

  return (
    <ScrollArea className="h-full w-72 border-l border-border bg-sidebar">
      <div className="space-y-5 p-4">
        {!selected.length && (
          <section>
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Interview prompt
            </h2>
            <p className="whitespace-pre-wrap rounded-md border border-border bg-card p-3 text-[13px] leading-relaxed text-foreground/85">
              {session.prompt || "No prompt provided."}
            </p>
          </section>
        )}

        {single && single.kind !== "connector" && single.kind !== "stroke" && (
          <NodeProps node={single} patch={patch} canEdit={canEdit} />
        )}

        {single && single.kind === "connector" && (
          <ConnectorProps conn={single} patch={patch} canEdit={canEdit} />
        )}

        {selected.length > 1 && (
          <p className="text-[13px] text-muted-foreground">{selected.length} elements selected</p>
        )}

        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Ink
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {INK.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`Ink color ${c}`}
                onClick={() => setInkColor(c)}
                style={{ backgroundColor: c }}
                className={`h-6 w-6 rounded-full ring-offset-2 ring-offset-sidebar ${
                  inkColor === c ? "ring-2 ring-primary" : ""
                }`}
              />
            ))}
          </div>
          <div className="mt-3">
            <Label className="text-xs text-muted-foreground">Stroke width</Label>
            <ToggleGroup
              type="single"
              value={String(inkWidth)}
              onValueChange={(v) => v && setInkWidth(Number(v))}
              className="mt-1.5 justify-start"
            >
              {[2, 4, 8].map((w) => (
                <ToggleGroupItem key={w} value={String(w)} className="h-8 px-3 text-xs">
                  {w}px
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        </section>

        {selected.length > 0 && canEdit && (
          <div className="flex gap-2 border-t border-border pt-4">
            <Button variant="secondary" size="sm" onClick={onDuplicate} className="flex-1">
              <Copy size={14} /> Duplicate
            </Button>
            <Button variant="destructive" size="sm" onClick={onDelete} className="flex-1">
              <Trash2 size={14} /> Delete
            </Button>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

function NodeProps({
  node,
  patch,
  canEdit,
}: {
  node: NodeElement;
  patch: (id: string, p: Partial<CanvasElement>) => void;
  canEdit: boolean;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        {node.componentType}
      </h2>
      <div>
        <Label htmlFor="el-label" className="text-xs text-muted-foreground">
          Label
        </Label>
        <Input
          id="el-label"
          value={node.label}
          disabled={!canEdit}
          onChange={(e) => patch(node.id, { label: e.target.value } as Partial<CanvasElement>)}
          className="mt-1.5"
        />
      </div>
      <div>
        <Label htmlFor="el-desc" className="text-xs text-muted-foreground">
          Description
        </Label>
        <Textarea
          id="el-desc"
          value={node.description ?? ""}
          disabled={!canEdit}
          rows={3}
          onChange={(e) =>
            patch(node.id, { description: e.target.value } as Partial<CanvasElement>)
          }
          className="mt-1.5"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {(["width", "height"] as const).map((k) => (
          <div key={k}>
            <Label className="text-xs capitalize text-muted-foreground">{k}</Label>
            <Input
              type="number"
              value={Math.round(node[k])}
              disabled={!canEdit}
              onChange={(e) =>
                patch(node.id, { [k]: Number(e.target.value) } as Partial<CanvasElement>)
              }
              className="mt-1.5"
            />
          </div>
        ))}
      </div>
    </section>
  );
}

function ConnectorProps({
  conn,
  patch,
  canEdit,
}: {
  conn: ConnectorElement;
  patch: (id: string, p: Partial<CanvasElement>) => void;
  canEdit: boolean;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Connector
      </h2>
      <div>
        <Label htmlFor="conn-label" className="text-xs text-muted-foreground">
          Label
        </Label>
        <Input
          id="conn-label"
          value={conn.label}
          placeholder="HTTPS, events, read/write"
          disabled={!canEdit}
          onChange={(e) => patch(conn.id, { label: e.target.value } as Partial<CanvasElement>)}
          className="mt-1.5"
        />
      </div>
      <div>
        <Label className="text-xs text-muted-foreground">Routing</Label>
        <ToggleGroup
          type="single"
          value={conn.style}
          onValueChange={(v) => v && patch(conn.id, { style: v } as Partial<CanvasElement>)}
          className="mt-1.5 justify-start"
        >
          {(["straight", "elbow", "curved"] as const).map((s) => (
            <ToggleGroupItem key={s} value={s} className="h-8 px-2.5 text-xs capitalize">
              {s}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="space-y-2.5">
        {(
          [
            ["arrowStart", "Arrow at start"],
            ["arrowEnd", "Arrow at end"],
            ["dashed", "Dashed line"],
          ] as const
        ).map(([key, label]) => (
          <div key={key} className="flex items-center justify-between">
            <Label className="text-[13px] font-normal">{label}</Label>
            <Switch
              checked={conn[key]}
              disabled={!canEdit}
              onCheckedChange={(v) => patch(conn.id, { [key]: v } as Partial<CanvasElement>)}
            />
          </div>
        ))}
      </div>
      <div>
        <Label className="text-xs text-muted-foreground">Line width</Label>
        <ToggleGroup
          type="single"
          value={String(conn.width)}
          onValueChange={(v) => v && patch(conn.id, { width: Number(v) } as Partial<CanvasElement>)}
          className="mt-1.5 justify-start"
        >
          {[1, 2, 4].map((w) => (
            <ToggleGroupItem key={w} value={String(w)} className="h-8 px-3 text-xs">
              {w}px
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <Button
        variant="secondary"
        size="sm"
        disabled={!canEdit}
        onClick={() =>
          patch(conn.id, { from: conn.to, to: conn.from } as unknown as Partial<CanvasElement>)
        }
      >
        <ArrowLeftRight size={14} /> Reverse direction
      </Button>
    </section>
  );
}
