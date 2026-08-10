import { describe, expect, it } from "vitest";
import { PALETTE, PALETTE_INDEX } from "./palette";

const items = PALETTE.flatMap((category) => category.items);

describe("PALETTE", () => {
  it("has no duplicate component types, which the index would silently drop", () => {
    const types = items.map((item) => item.type);

    expect(new Set(types).size).toBe(types.length);
    expect(Object.keys(PALETTE_INDEX)).toHaveLength(types.length);
  });

  it("indexes every item by its type", () => {
    for (const item of items) {
      expect(PALETTE_INDEX[item.type]).toBe(item);
    }
  });

  it("gives every item a label, an icon, and a positive box", () => {
    for (const item of items) {
      expect(item.label).not.toBe("");
      expect(item.icon).toBeTruthy();
      expect(item.width).toBeGreaterThan(0);
      expect(item.height).toBeGreaterThan(0);
    }
  });

  it("keeps the special-cased text and note types in the palette", () => {
    // makeNode() maps these two types onto their own element kinds.
    expect(PALETTE_INDEX["text"]).toBeDefined();
    expect(PALETTE_INDEX["note"]).toBeDefined();
  });
});
