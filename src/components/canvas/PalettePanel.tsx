import { PALETTE } from "@/lib/api/palette";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function PalettePanel({
  onPlace,
  disabled,
}: {
  onPlace: (type: string) => void;
  disabled: boolean;
}) {
  return (
    <ScrollArea className="h-full w-56 border-r border-border bg-sidebar">
      <div className="p-3">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Components
        </h2>
        {PALETTE.map((cat) => (
          <div key={cat.name} className="mb-4">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
              {cat.name}
            </p>
            <div className="grid grid-cols-1 gap-1">
              {cat.items.map((item) => (
                <button
                  key={item.type}
                  type="button"
                  disabled={disabled}
                  onClick={() => onPlace(item.type)}
                  className={cn(
                    "flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-left text-[13px] text-foreground/85 transition-colors",
                    "hover:border-border hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    disabled && "cursor-not-allowed opacity-40",
                  )}
                >
                  <item.icon size={15} className="shrink-0 text-primary" />
                  <span className="truncate">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
