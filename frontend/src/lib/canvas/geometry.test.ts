import { describe, expect, it } from "vitest";
import {
  anchorPoint,
  bounds,
  clamp,
  connectorPath,
  makeNode,
  newConnector,
  newStroke,
  nodeCenter,
  offsetCopy,
  strokePath,
  MAX_ZOOM,
  MIN_ZOOM,
} from "./geometry";
import { PALETTE_INDEX } from "@/lib/api/palette";
import type { NodeElement, StrokeElement } from "@/lib/api/types";

const node = (overrides: Partial<NodeElement> = {}): NodeElement => ({
  id: "el_1",
  kind: "node",
  componentType: "service",
  x: 0,
  y: 0,
  width: 100,
  height: 50,
  label: "Service",
  created_by: "usr_1",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("makeNode", () => {
  it("centers the node on the drop point using the palette size", () => {
    const spec = PALETTE_INDEX["cache"]!;
    const created = makeNode("cache", 300, 200, "usr_1");

    expect(created.width).toBe(spec.width);
    expect(created.height).toBe(spec.height);
    expect(nodeCenter(created)).toEqual({ x: 300, y: 200 });
    expect(created.label).toBe(spec.label);
    expect(created.created_by).toBe("usr_1");
  });

  it("falls back to a default box for an unknown component type", () => {
    const created = makeNode("not-in-the-palette", 0, 0, "usr_1");

    expect(created.width).toBe(168);
    expect(created.height).toBe(76);
    expect(created.label).toBe("Component");
  });

  it("keeps text and notes in their own element kinds", () => {
    expect(makeNode("text", 0, 0, "usr_1").kind).toBe("text");
    expect(makeNode("note", 0, 0, "usr_1").kind).toBe("note");
    expect(makeNode("cache", 0, 0, "usr_1").kind).toBe("node");
  });
});

describe("anchorPoint", () => {
  it("lands on the border, not the center, for a node to its right", () => {
    const box = node({ x: 0, y: 0, width: 100, height: 50 });
    const point = anchorPoint(box, { x: 500, y: 25 });

    expect(point.x).toBeCloseTo(100);
    expect(point.y).toBeCloseTo(25);
  });

  it("leaves through the top edge when the target is above", () => {
    const box = node({ x: 0, y: 0, width: 100, height: 50 });
    const point = anchorPoint(box, { x: 50, y: -500 });

    expect(point.x).toBeCloseTo(50);
    expect(point.y).toBeCloseTo(0);
  });

  it("degenerates to the center when the target is the center", () => {
    const box = node({ x: 0, y: 0, width: 100, height: 50 });

    expect(anchorPoint(box, nodeCenter(box))).toEqual({ x: 50, y: 25 });
  });
});

describe("connectorPath", () => {
  const a = { x: 0, y: 0 };
  const b = { x: 100, y: 40 };

  it("draws a single line segment when straight", () => {
    expect(connectorPath(a, b, "straight")).toBe("M 0 0 L 100 40");
  });

  it("turns at the horizontal midpoint when elbowed", () => {
    expect(connectorPath(a, b, "elbow")).toBe("M 0 0 L 50 0 L 50 40 L 100 40");
  });

  it("emits a cubic curve otherwise", () => {
    expect(connectorPath(a, b, "curved")).toMatch(/^M 0 0 C /);
  });
});

describe("strokePath", () => {
  it("draws a dot for a single point so a tap is still visible", () => {
    expect(strokePath([10, 20])).toBe("M 10 20 L 10.1 20");
  });

  it("smooths a multi-point stroke through quadratic segments", () => {
    const path = strokePath([0, 0, 10, 10, 20, 0]);

    expect(path.startsWith("M 0 0")).toBe(true);
    expect(path).toContain("Q");
  });
});

describe("bounds", () => {
  it("returns the box of a node", () => {
    expect(bounds(node({ x: 5, y: 7, width: 20, height: 30 }))).toEqual({
      x: 5,
      y: 7,
      width: 20,
      height: 30,
    });
  });

  it("derives the box of a stroke from its points", () => {
    const stroke: StrokeElement = {
      id: "st_1",
      kind: "stroke",
      points: [10, 20, 40, 5, 30, 60],
      color: "#000000",
      width: 2,
      opacity: 1,
      created_by: "usr_1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    expect(bounds(stroke)).toEqual({ x: 10, y: 5, width: 30, height: 55 });
  });

  it("has no box for a connector, which follows its endpoints", () => {
    expect(bounds(newConnector("a", "b", "usr_1"))).toBeNull();
  });
});

describe("offsetCopy", () => {
  it("gives the copy a new id and offsets it", () => {
    const original = node({ x: 10, y: 20 });
    const copy = offsetCopy(original, 16) as NodeElement;

    expect(copy.id).not.toBe(original.id);
    expect([copy.x, copy.y]).toEqual([26, 36]);
  });

  it("offsets every point of a stroke", () => {
    const stroke = newStroke(0, 0, "pen", "#000000", 2, "usr_1");
    const copy = offsetCopy({ ...stroke, points: [0, 0, 10, 10] }, 5) as StrokeElement;

    expect(copy.points).toEqual([5, 5, 15, 15]);
  });

  it("refuses to copy a connector on its own", () => {
    expect(offsetCopy(newConnector("a", "b", "usr_1"), 16)).toBeNull();
  });
});

describe("newStroke", () => {
  it("makes the highlighter wide and translucent", () => {
    const pen = newStroke(0, 0, "pen", "#000000", 3, "usr_1");
    const highlighter = newStroke(0, 0, "highlighter", "#000000", 3, "usr_1");

    expect(pen.width).toBe(3);
    expect(pen.opacity).toBe(1);
    expect(highlighter.width).toBe(12);
    expect(highlighter.opacity).toBeLessThan(1);
  });
});

describe("clamp", () => {
  it("holds zoom inside the supported range", () => {
    expect(clamp(0.01, MIN_ZOOM, MAX_ZOOM)).toBe(MIN_ZOOM);
    expect(clamp(99, MIN_ZOOM, MAX_ZOOM)).toBe(MAX_ZOOM);
    expect(clamp(1.5, MIN_ZOOM, MAX_ZOOM)).toBe(1.5);
  });
});
