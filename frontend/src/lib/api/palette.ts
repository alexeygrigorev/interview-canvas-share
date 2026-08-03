import {
  Box,
  Square,
  Type,
  StickyNote,
  Group,
  Circle,
  Database,
  Table2,
  Zap,
  HardDrive,
  Warehouse,
  ListOrdered,
  Radio,
  Share2,
  Monitor,
  Smartphone,
  DoorOpen,
  Scale,
  Globe,
  Plug,
  Server,
  Cog,
  FunctionSquare,
  Boxes,
  Brain,
  Sparkles,
  Layers,
  Bot,
  type LucideIcon,
} from "lucide-react";

export interface PaletteItem {
  type: string;
  label: string;
  icon: LucideIcon;
  width: number;
  height: number;
  shape: "rect" | "rounded" | "ellipse" | "note" | "boundary" | "text";
}

export interface PaletteCategory {
  name: string;
  items: PaletteItem[];
}

const n = (
  type: string,
  label: string,
  icon: LucideIcon,
  shape: PaletteItem["shape"] = "rounded",
  width = 168,
  height = 76,
): PaletteItem => ({ type, label, icon, shape, width, height });

export const PALETTE: PaletteCategory[] = [
  {
    name: "General",
    items: [
      n("service", "Service", Box, "rect"),
      n("process", "Process", Square, "rounded"),
      n("text", "Text", Type, "text", 160, 36),
      n("note", "Sticky note", StickyNote, "note", 160, 120),
      n("boundary", "Boundary", Group, "boundary", 360, 240),
      n("generic", "Generic", Circle, "ellipse", 140, 96),
    ],
  },
  {
    name: "Data",
    items: [
      n("sql", "Relational DB", Database),
      n("nosql", "NoSQL DB", Table2),
      n("cache", "Cache", Zap),
      n("blob", "Object storage", HardDrive),
      n("warehouse", "Data warehouse", Warehouse),
    ],
  },
  {
    name: "Messaging",
    items: [
      n("queue", "Queue", ListOrdered),
      n("stream", "Event stream", Radio),
      n("pubsub", "Pub/Sub broker", Share2),
    ],
  },
  {
    name: "Network",
    items: [
      n("client", "Client", Monitor),
      n("mobile", "Mobile client", Smartphone),
      n("gateway", "API gateway", DoorOpen),
      n("lb", "Load balancer", Scale),
      n("cdn", "CDN", Globe),
      n("external", "External API", Plug),
    ],
  },
  {
    name: "Compute",
    items: [
      n("server", "Server", Server),
      n("worker", "Worker", Cog),
      n("function", "Function", FunctionSquare),
      n("cluster", "Container cluster", Boxes),
    ],
  },
  {
    name: "AI",
    items: [
      n("llm", "LLM / model", Brain),
      n("embedding", "Embedding model", Sparkles),
      n("vectordb", "Vector database", Layers),
      n("agent", "Agent / tool", Bot),
    ],
  },
];

export const PALETTE_INDEX: Record<string, PaletteItem> = Object.fromEntries(
  PALETTE.flatMap((c) => c.items).map((i) => [i.type, i]),
);
