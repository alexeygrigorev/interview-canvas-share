import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CanvasElement,
  ConnectorElement,
  NodeElement,
  StrokeElement,
} from "@/lib/api/types";
import { PALETTE_INDEX } from "@/lib/api/palette";

export type Tool =
  | "select"
  | "pan"
  | "pen"
  | "highlighter"
  | "eraser"
  | "text"
  | "note"
  | "connector";

export interface Viewport {
  x: number;
  y: number;
  z: number;
}

export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 4;
const GRID = 16;

const uid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const snap = (v: number, on: boolean) => (on ? Math.round(v / GRID) * GRID : v);

export function makeNode(
  componentType: string,
  x: number,
  y: number,
  actor: string,
): NodeElement {
  const spec = PALETTE_INDEX[componentType];
  const kind: NodeElement["kind"] =
    componentType === "note" ? "note" : componentType === "text" ? "text" : "node";
  return {
    id: uid("el"),
    kind,
    componentType,
    x: Math.round(x - (spec?.width ?? 168) / 2),
    y: Math.round(y - (spec?.height ?? 76) / 2),
    width: spec?.width ?? 168,
    height: spec?.height ?? 76,
    label: spec?.label ?? "Component",
    created_by: actor,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function nodeCenter(n: NodeElement) {
  return { x: n.x + n.width / 2, y: n.y + n.height / 2 };
}

/** Point on the node border along the direction to `to`. */
export function anchorPoint(n: NodeElement, to: { x: number; y: number }) {
  const c = nodeCenter(n);
  const dx = to.x - c.x;
  const dy = to.y - c.y;
  if (dx === 0 && dy === 0) return c;
  const hw = n.width / 2;
  const hh = n.height / 2;
  const scale = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
  return { x: c.x + dx * scale, y: c.y + dy * scale };
}

export function connectorPath(
  a: { x: number; y: number },
  b: { x: number; y: number },
  style: ConnectorElement["style"],
) {
  if (style === "straight") return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
  if (style === "elbow") {
    const mx = (a.x + b.x) / 2;
    return `M ${a.x} ${a.y} L ${mx} ${a.y} L ${mx} ${b.y} L ${b.x} ${b.y}`;
  }
  const dx = Math.abs(b.x - a.x) * 0.5 + 20;
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
}

export function strokePath(points: number[]) {
  if (points.length < 4) {
    const [x = 0, y = 0] = points;
    return `M ${x} ${y} L ${x + 0.1} ${y}`;
  }
  let d = `M ${points[0]} ${points[1]}`;
  for (let i = 2; i < points.length - 2; i += 2) {
    const mx = (points[i]! + points[i + 2]!) / 2;
    const my = (points[i + 1]! + points[i + 3]!) / 2;
    d += ` Q ${points[i]} ${points[i + 1]} ${mx} ${my}`;
  }
  return d;
}

export function bounds(el: CanvasElement) {
  if (el.kind === "stroke") {
    const xs = el.points.filter((_, i) => i % 2 === 0);
    const ys = el.points.filter((_, i) => i % 2 === 1);
    const x = Math.min(...xs);
    const y = Math.min(...ys);
    return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
  }
  if (el.kind === "connector") return null;
  return { x: el.x, y: el.y, width: el.width, height: el.height };
}

/** Viewport controls: wheel zoom anchored at the cursor, pan, zoom-to-fit. */
export function useViewport(containerRef: React.RefObject<HTMLDivElement | null>) {
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, z: 1 });
  const vpRef = useRef(viewport);
  vpRef.current = viewport;

  const toWorld = useCallback((clientX: number, clientY: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const vp = vpRef.current;
    const px = clientX - (rect?.left ?? 0);
    const py = clientY - (rect?.top ?? 0);
    return { x: (px - vp.x) / vp.z, y: (py - vp.y) / vp.z };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const zoomAt = useCallback((px: number, py: number, nextZoom: number) => {
    setViewport((vp) => {
      const z = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);
      const k = z / vp.z;
      return { z, x: px - (px - vp.x) * k, y: py - (py - vp.y) * k };
    });
  }, []);

  const zoomBy = useCallback(
    (factor: number) => {
      const rect = containerRef.current?.getBoundingClientRect();
      zoomAt((rect?.width ?? 0) / 2, (rect?.height ?? 0) / 2, vpRef.current.z * factor);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [zoomAt],
  );

  const wheelRef = useRef((e: WheelEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const px = e.clientX - (rect?.left ?? 0);
    const py = e.clientY - (rect?.top ?? 0);
    const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
    if (e.ctrlKey || e.metaKey || Math.abs(e.deltaX) < 1) {
      zoomAt(px, py, vpRef.current.z * Math.exp(-dy * 0.0018));
    } else {
      setViewport((vp) => ({ ...vp, x: vp.x - e.deltaX, y: vp.y - dy }));
    }
  });
  wheelRef.current = (e: WheelEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const px = e.clientX - (rect?.left ?? 0);
    const py = e.clientY - (rect?.top ?? 0);
    const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
    if (e.ctrlKey || e.metaKey) {
      zoomAt(px, py, vpRef.current.z * Math.exp(-dy * 0.0018));
    } else if (e.shiftKey) {
      setViewport((vp) => ({ ...vp, x: vp.x - dy }));
    } else {
      setViewport((vp) => ({ ...vp, x: vp.x - e.deltaX, y: vp.y - dy }));
    }
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      wheelRef.current(e);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [containerRef]);

  const fit = useCallback(
    (elements: CanvasElement[]) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const boxes = elements.map(bounds).filter(Boolean) as {
        x: number;
        y: number;
        width: number;
        height: number;
      }[];
      if (!boxes.length) {
        setViewport({ x: rect.width / 2, y: rect.height / 2, z: 1 });
        return;
      }
      const minX = Math.min(...boxes.map((b) => b.x));
      const minY = Math.min(...boxes.map((b) => b.y));
      const maxX = Math.max(...boxes.map((b) => b.x + b.width));
      const maxY = Math.max(...boxes.map((b) => b.y + b.height));
      const pad = 80;
      const z = clamp(
        Math.min(rect.width / (maxX - minX + pad * 2), rect.height / (maxY - minY + pad * 2)),
        MIN_ZOOM,
        1.5,
      );
      setViewport({
        z,
        x: rect.width / 2 - ((minX + maxX) / 2) * z,
        y: rect.height / 2 - ((minY + maxY) / 2) * z,
      });
    },
    [containerRef],
  );

  return { viewport, setViewport, toWorld, zoomBy, zoomAt, fit };
}

export function useSnapping() {
  const [snapEnabled, setSnapEnabled] = useState(true);
  const apply = useCallback((v: number) => snap(v, snapEnabled), [snapEnabled]);
  return { snapEnabled, setSnapEnabled, apply };
}

export function useElementMap(elements: CanvasElement[]) {
  return useMemo(() => {
    const map = new Map<string, CanvasElement>();
    elements.forEach((e) => map.set(e.id, e));
    return map;
  }, [elements]);
}

export function newStroke(
  x: number,
  y: number,
  tool: "pen" | "highlighter",
  color: string,
  width: number,
  actor: string,
): StrokeElement {
  return {
    id: uid("st"),
    kind: "stroke",
    points: [x, y],
    color,
    width: tool === "highlighter" ? width * 4 : width,
    opacity: tool === "highlighter" ? 0.28 : 1,
    created_by: actor,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function newConnector(from: string, to: string, actor: string): ConnectorElement {
  return {
    id: uid("cn"),
    kind: "connector",
    from,
    to,
    style: "curved",
    dashed: false,
    arrowStart: false,
    arrowEnd: true,
    width: 2,
    label: "",
    created_by: actor,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export { uid, clamp, GRID };

/** Duplicate an element offset by `d`; connectors are not copyable standalone. */
export function offsetCopy(el: CanvasElement, d: number): CanvasElement | null {
  const id = uid("el");
  if (el.kind === "connector") return null;
  if (el.kind === "stroke") {
    return { ...el, id, points: el.points.map((p) => p + d) };
  }
  return { ...el, id, x: el.x + d, y: el.y + d };
}
