import { useCallback, useEffect, useRef, useState } from "react";
import type { CanvasElement, NodeElement, Participant } from "@/lib/api/types";
import { PALETTE_INDEX } from "@/lib/api/palette";
import {
  anchorPoint,
  bounds,
  connectorPath,
  GRID,
  newConnector,
  newStroke,
  nodeCenter,
  strokePath,
  useElementMap,
  useViewport,
  type Tool,
  type Viewport,
} from "@/lib/canvas/geometry";
import { cn } from "@/lib/utils";

interface Props {
  elements: CanvasElement[];
  commit: (fn: (prev: CanvasElement[]) => CanvasElement[], record?: boolean) => void;
  canEdit: boolean;
  tool: Tool;
  setTool: (t: Tool) => void;
  inkColor: string;
  inkWidth: number;
  snapEnabled: boolean;
  selection: string[];
  setSelection: (ids: string[]) => void;
  actorId: string;
  actorColor: string;
  peers: Participant[];
  cursorsVisible: boolean;
  onCursor?: (p: { x: number; y: number } | null) => void;
  registerViewportApi?: (api: {
    zoomBy: (f: number) => void;
    fit: () => void;
    reset: () => void;
    viewport: Viewport;
  }) => void;
}

type Drag =
  | { mode: "none" }
  | { mode: "pan"; sx: number; sy: number; ox: number; oy: number }
  | { mode: "move"; sx: number; sy: number; origin: Record<string, { x: number; y: number }> }
  | { mode: "resize"; id: string; sx: number; sy: number; box: NodeElement }
  | { mode: "marquee"; sx: number; sy: number; x: number; y: number }
  | { mode: "draw"; id: string };

export function CanvasStage(props: Props) {
  const {
    elements,
    commit,
    canEdit,
    tool,
    setTool,
    inkColor,
    inkWidth,
    snapEnabled,
    selection,
    setSelection,
    actorId,
    peers,
    cursorsVisible,
    onCursor,
    registerViewportApi,
  } = props;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const { viewport, setViewport, toWorld, zoomBy, fit } = useViewport(containerRef);
  const map = useElementMap(elements);
  const [drag, setDrag] = useState<Drag>({ mode: "none" });
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [spaceDown, setSpaceDown] = useState(false);
  const clipboard = useRef<CanvasElement[]>([]);

  const snapV = useCallback((v: number) => (snapEnabled ? Math.round(v / GRID) * GRID : v), [
    snapEnabled,
  ]);

  useEffect(() => {
    registerViewportApi?.({
      zoomBy,
      fit: () => fit(elements),
      reset: () => setViewport({ x: 0, y: 0, z: 1 }),
      viewport,
    });
  }, [registerViewportApi, zoomBy, fit, elements, viewport, setViewport]);

  /* ---------------- keyboard ---------------- */
  useEffect(() => {
    const isField = (t: EventTarget | null) =>
      t instanceof HTMLElement && /input|textarea/i.test(t.tagName);
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isField(e.target)) setSpaceDown(true);
      if (isField(e.target) || editing) return;
      const mod = e.metaKey || e.ctrlKey;
      if ((e.key === "Delete" || e.key === "Backspace") && selection.length && canEdit) {
        e.preventDefault();
        commit((prev) =>
          prev.filter(
            (el) =>
              !selection.includes(el.id) &&
              !(el.kind === "connector" && (selection.includes(el.from) || selection.includes(el.to))),
          ),
        );
        setSelection([]);
      }
      if (mod && e.key.toLowerCase() === "c" && selection.length) {
        clipboard.current = elements.filter((el) => selection.includes(el.id));
      }
      if (mod && e.key.toLowerCase() === "v" && clipboard.current.length && canEdit) {
        const copies = clipboard.current.map((el) => offsetCopy(el, 24)).filter(Boolean) as CanvasElement[];
        commit((prev) => [...prev, ...copies]);
        setSelection(copies.map((c) => c.id));
      }
      if (mod && e.key.toLowerCase() === "d" && selection.length && canEdit) {
        e.preventDefault();
        const copies = elements
          .filter((el) => selection.includes(el.id))
          .map((el) => offsetCopy(el, 24))
          .filter(Boolean) as CanvasElement[];
        commit((prev) => [...prev, ...copies]);
        setSelection(copies.map((c) => c.id));
      }
      if (e.key === "Escape") {
        setSelection([]);
        setConnectFrom(null);
      }
      if (!mod && e.key.toLowerCase() === "v") setTool("select");
      if (!mod && e.key.toLowerCase() === "h") setTool("pan");
      if (!mod && e.key.toLowerCase() === "p") setTool("pen");
      if (!mod && e.key.toLowerCase() === "l") setTool("connector");
      if (!mod && e.key.toLowerCase() === "n") setTool("note");
      if (!mod && selection.length && canEdit && ["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key)) {
        e.preventDefault();
        const step = e.shiftKey ? GRID : 2;
        const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
        const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
        commit((prev) =>
          prev.map((el) =>
            selection.includes(el.id) && el.kind !== "connector"
              ? el.kind === "stroke"
                ? { ...el, points: el.points.map((p, i) => p + (i % 2 === 0 ? dx : dy)) }
                : { ...el, x: el.x + dx, y: el.y + dy }
              : el,
          ),
        );
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpaceDown(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [selection, elements, commit, canEdit, setSelection, setTool, editing]);

  /* ---------------- pointer ---------------- */
  const onPointerDownBg = (e: React.PointerEvent) => {
    if (e.button === 1 || tool === "pan" || spaceDown) {
      setDrag({ mode: "pan", sx: e.clientX, sy: e.clientY, ox: viewport.x, oy: viewport.y });
      return;
    }
    const w = toWorld(e.clientX, e.clientY);
    if (!canEdit || tool === "select") {
      setSelection([]);
      setDrag({ mode: "marquee", sx: w.x, sy: w.y, x: w.x, y: w.y });
      return;
    }
    if (tool === "pen" || tool === "highlighter") {
      const stroke = newStroke(w.x, w.y, tool, inkColor, inkWidth, actorId);
      commit((prev) => [...prev, stroke]);
      setDrag({ mode: "draw", id: stroke.id });
      return;
    }
    if (tool === "text" || tool === "note") {
      const spec = PALETTE_INDEX[tool]!;
      const el: NodeElement = {
        id: `el_${Math.random().toString(36).slice(2, 10)}`,
        kind: tool,
        componentType: tool,
        x: snapV(w.x),
        y: snapV(w.y),
        width: spec.width,
        height: spec.height,
        label: tool === "note" ? "New note" : "Text",
        created_by: actorId,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      commit((prev) => [...prev, el]);
      setSelection([el.id]);
      setEditing(el.id);
      setTool("select");
      return;
    }
    if (tool === "connector") setConnectFrom(null);
  };

  const onPointerDownElement = (e: React.PointerEvent, el: CanvasElement) => {
    if (tool === "pan" || spaceDown) return;
    e.stopPropagation();
    if (tool === "eraser" && canEdit) {
      commit((prev) =>
        prev.filter(
          (x) => x.id !== el.id && !(x.kind === "connector" && (x.from === el.id || x.to === el.id)),
        ),
      );
      return;
    }
    if (tool === "connector" && canEdit && el.kind !== "connector" && el.kind !== "stroke") {
      if (!connectFrom) setConnectFrom(el.id);
      else if (connectFrom !== el.id) {
        commit((prev) => [...prev, newConnector(connectFrom, el.id, actorId)]);
        setConnectFrom(null);
      }
      return;
    }
    const multi = e.shiftKey || e.metaKey || e.ctrlKey;
    const nextSel = multi
      ? selection.includes(el.id)
        ? selection.filter((i) => i !== el.id)
        : [...selection, el.id]
      : selection.includes(el.id)
        ? selection
        : [el.id];
    setSelection(nextSel);
    if (!canEdit || tool !== "select") return;
    const origin: Record<string, { x: number; y: number }> = {};
    elements
      .filter((x) => nextSel.includes(x.id))
      .forEach((x) => {
        const b = bounds(x);
        if (b) origin[x.id] = { x: b.x, y: b.y };
      });
    const w = toWorld(e.clientX, e.clientY);
    setDrag({ mode: "move", sx: w.x, sy: w.y, origin });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const w = toWorld(e.clientX, e.clientY);
    onCursor?.(w);
    if (drag.mode === "pan") {
      setViewport((vp) => ({
        ...vp,
        x: drag.ox + (e.clientX - drag.sx),
        y: drag.oy + (e.clientY - drag.sy),
      }));
      return;
    }
    if (drag.mode === "marquee") {
      setDrag({ ...drag, x: w.x, y: w.y });
      return;
    }
    if (drag.mode === "draw") {
      commit(
        (prev) =>
          prev.map((el) =>
            el.id === drag.id && el.kind === "stroke"
              ? { ...el, points: [...el.points, w.x, w.y] }
              : el,
          ),
        false,
      );
      return;
    }
    if (drag.mode === "move") {
      const dx = w.x - drag.sx;
      const dy = w.y - drag.sy;
      commit(
        (prev) =>
          prev.map((el) => {
            const o = drag.origin[el.id];
            if (!o) return el;
            if (el.kind === "stroke") {
              const b = bounds(el)!;
              const ox = snapV(o.x + dx) - b.x;
              const oy = snapV(o.y + dy) - b.y;
              return { ...el, points: el.points.map((p, i) => p + (i % 2 === 0 ? ox : oy)) };
            }
            if (el.kind === "connector") return el;
            return { ...el, x: snapV(o.x + dx), y: snapV(o.y + dy) };
          }),
        false,
      );
      return;
    }
    if (drag.mode === "resize") {
      const b = drag.box;
      commit(
        (prev) =>
          prev.map((el) =>
            el.id === drag.id && el.kind !== "connector" && el.kind !== "stroke"
              ? {
                  ...el,
                  width: Math.max(60, snapV(w.x - b.x)),
                  height: Math.max(36, snapV(w.y - b.y)),
                }
              : el,
          ),
        false,
      );
    }
  };

  const endDrag = () => {
    if (drag.mode === "marquee") {
      const x1 = Math.min(drag.sx, drag.x);
      const x2 = Math.max(drag.sx, drag.x);
      const y1 = Math.min(drag.sy, drag.y);
      const y2 = Math.max(drag.sy, drag.y);
      if (Math.abs(x2 - x1) > 4 || Math.abs(y2 - y1) > 4) {
        const hit = elements.filter((el) => {
          const b = bounds(el);
          return b && b.x >= x1 - b.width && b.x + b.width <= x2 + b.width && b.y >= y1 - b.height && b.y + b.height <= y2 + b.height && b.x + b.width >= x1 && b.x <= x2 && b.y + b.height >= y1 && b.y <= y2;
        });
        setSelection(hit.map((h) => h.id));
      }
    }
    setDrag({ mode: "none" });
  };

  const cursor =
    tool === "pan" || spaceDown
      ? drag.mode === "pan"
        ? "grabbing"
        : "grab"
      : tool === "pen" || tool === "highlighter"
        ? "crosshair"
        : tool === "eraser"
          ? "cell"
          : tool === "connector"
            ? "crosshair"
            : "default";

  const nodes = elements.filter(
    (e): e is NodeElement => e.kind === "node" || e.kind === "text" || e.kind === "note",
  );

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden bg-canvas touch-none select-none"
      style={{ cursor }}
      onPointerDown={onPointerDownBg}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerLeave={() => {
        endDrag();
        onCursor?.(null);
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(circle, var(--canvas-grid) 1px, transparent 1px)",
          backgroundSize: `${GRID * viewport.z}px ${GRID * viewport.z}px`,
          backgroundPosition: `${viewport.x}px ${viewport.y}px`,
        }}
      />
      <svg className="absolute inset-0 h-full w-full">
        <defs>
          <marker
            id="arrow-end"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--canvas-ink)" />
          </marker>
        </defs>
        <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.z})`}>
          {/* connectors */}
          {elements.map((el) => {
            if (el.kind !== "connector") return null;
            const a = map.get(el.from);
            const b = map.get(el.to);
            if (!a || !b || a.kind === "connector" || b.kind === "connector") return null;
            if (a.kind === "stroke" || b.kind === "stroke") return null;
            const pa = anchorPoint(a, nodeCenter(b));
            const pb = anchorPoint(b, nodeCenter(a));
            const mid = { x: (pa.x + pb.x) / 2, y: (pa.y + pb.y) / 2 };
            const selected = selection.includes(el.id);
            return (
              <g key={el.id} onPointerDown={(e) => onPointerDownElement(e, el)}>
                <path
                  d={connectorPath(pa, pb, el.style)}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  className="cursor-pointer"
                />
                <path
                  d={connectorPath(pa, pb, el.style)}
                  fill="none"
                  stroke={selected ? "var(--primary)" : "var(--canvas-ink)"}
                  strokeWidth={el.width}
                  strokeDasharray={el.dashed ? "8 6" : undefined}
                  markerEnd={el.arrowEnd ? "url(#arrow-end)" : undefined}
                  markerStart={el.arrowStart ? "url(#arrow-end)" : undefined}
                  opacity={0.85}
                />
                {el.label && (
                  <g>
                    <rect
                      x={mid.x - el.label.length * 3.6 - 6}
                      y={mid.y - 11}
                      width={el.label.length * 7.2 + 12}
                      height={22}
                      rx={6}
                      fill="var(--canvas)"
                      stroke="var(--canvas-node-border)"
                    />
                    <text
                      x={mid.x}
                      y={mid.y + 4}
                      textAnchor="middle"
                      fontSize={12}
                      fill="var(--canvas-ink)"
                      className="font-mono"
                    >
                      {el.label}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* strokes */}
          {elements.map((el) =>
            el.kind === "stroke" ? (
              <path
                key={el.id}
                d={strokePath(el.points)}
                fill="none"
                stroke={el.color}
                strokeWidth={el.width}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={el.opacity}
                onPointerDown={(e) => onPointerDownElement(e, el)}
                className={cn(selection.includes(el.id) && "drop-shadow-[0_0_6px_var(--primary)]")}
              />
            ) : null,
          )}

          {/* nodes */}
          {nodes.map((el) => {
            const spec = PALETTE_INDEX[el.componentType];
            const selected = selection.includes(el.id);
            const isNote = el.kind === "note";
            const isText = el.kind === "text";
            const isBoundary = el.componentType === "boundary";
            const Icon = spec?.icon;
            return (
              <g
                key={el.id}
                onPointerDown={(e) => onPointerDownElement(e, el)}
                onDoubleClick={() => canEdit && setEditing(el.id)}
                onPointerEnter={() => setHover(el.id)}
                onPointerLeave={() => setHover((h) => (h === el.id ? null : h))}
                className="cursor-pointer"
              >
                {spec?.shape === "ellipse" ? (
                  <ellipse
                    cx={el.x + el.width / 2}
                    cy={el.y + el.height / 2}
                    rx={el.width / 2}
                    ry={el.height / 2}
                    fill="var(--canvas-node)"
                    stroke={selected ? "var(--primary)" : "var(--canvas-node-border)"}
                    strokeWidth={selected ? 2 : 1.25}
                  />
                ) : isText ? null : (
                  <rect
                    x={el.x}
                    y={el.y}
                    width={el.width}
                    height={el.height}
                    rx={isBoundary ? 14 : spec?.shape === "rect" ? 4 : 10}
                    fill={
                      isNote
                        ? el.color ?? "var(--note)"
                        : isBoundary
                          ? "transparent"
                          : "var(--canvas-node)"
                    }
                    stroke={
                      selected
                        ? "var(--primary)"
                        : connectFrom === el.id || hover === el.id
                          ? "var(--accent)"
                          : "var(--canvas-node-border)"
                    }
                    strokeWidth={selected ? 2 : 1.25}
                    strokeDasharray={isBoundary ? "10 6" : undefined}
                  />
                )}
                {Icon && !isNote && !isText && !isBoundary && (
                  <foreignObject x={el.x + 12} y={el.y + el.height / 2 - 10} width={20} height={20}>
                    <Icon size={18} color="var(--primary)" />
                  </foreignObject>
                )}
                <foreignObject
                  x={el.x + (isNote || isText || isBoundary ? 10 : 38)}
                  y={isBoundary ? el.y + 6 : el.y + 8}
                  width={Math.max(20, el.width - (isNote || isText || isBoundary ? 20 : 48))}
                  height={isBoundary ? 24 : el.height - 16}
                >
                  <div
                    className={cn(
                      "flex h-full w-full items-center break-words text-[13px] leading-snug",
                      isNote ? "items-start text-note-foreground" : "text-canvas-ink",
                      isText && "text-[15px] font-medium",
                      isBoundary && "text-xs uppercase tracking-widest text-muted-foreground",
                    )}
                  >
                    {editing === el.id ? (
                      <textarea
                        autoFocus
                        defaultValue={el.label}
                        onBlur={(ev) => {
                          const v = ev.target.value;
                          commit((prev) =>
                            prev.map((x) => (x.id === el.id ? { ...x, label: v } : x)),
                          );
                          setEditing(null);
                        }}
                        onKeyDown={(ev) => {
                          if (ev.key === "Escape") setEditing(null);
                        }}
                        className="h-full w-full resize-none border-0 bg-transparent p-0 text-inherit outline-none"
                      />
                    ) : (
                      <span className="line-clamp-4">{el.label}</span>
                    )}
                  </div>
                </foreignObject>
                {selected && (
                  <>
                    <rect
                      x={el.x - 4}
                      y={el.y - 4}
                      width={el.width + 8}
                      height={el.height + 8}
                      fill="none"
                      stroke="var(--primary)"
                      strokeWidth={1}
                      strokeDasharray="4 4"
                      opacity={0.7}
                    />
                    {canEdit && selection.length === 1 && (
                      <rect
                        x={el.x + el.width - 5}
                        y={el.y + el.height - 5}
                        width={10}
                        height={10}
                        rx={2}
                        fill="var(--primary)"
                        className="cursor-nwse-resize"
                        onPointerDown={(e) => {
                          e.stopPropagation();
                          setDrag({ mode: "resize", id: el.id, sx: 0, sy: 0, box: el });
                        }}
                      />
                    )}
                  </>
                )}
              </g>
            );
          })}

          {/* marquee */}
          {drag.mode === "marquee" && (
            <rect
              x={Math.min(drag.sx, drag.x)}
              y={Math.min(drag.sy, drag.y)}
              width={Math.abs(drag.x - drag.sx)}
              height={Math.abs(drag.y - drag.sy)}
              fill="var(--primary)"
              fillOpacity={0.08}
              stroke="var(--primary)"
              strokeDasharray="4 4"
            />
          )}

          {/* remote cursors */}
          {cursorsVisible &&
            peers
              .filter((p) => p.id !== actorId && p.cursor)
              .map((p) => (
                <g key={p.id} transform={`translate(${p.cursor!.x} ${p.cursor!.y})`}>
                  <path d="M0 0 L0 14 L4 11 L7 17 L10 15 L7 9 L12 9 Z" fill={p.color} />
                  <rect x={12} y={12} width={p.display_name.length * 7 + 12} height={20} rx={6} fill={p.color} />
                  <text x={18} y={26} fontSize={11} fill="#101418" className="font-medium">
                    {p.display_name}
                  </text>
                </g>
              ))}
        </g>
      </svg>
    </div>
  );
}
