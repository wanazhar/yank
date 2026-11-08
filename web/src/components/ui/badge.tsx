import { cn } from "@/lib/utils";

export function Badge({
  className,
  children,
  variant = "default",
}: {
  className?: string;
  children: React.ReactNode;
  variant?: "default" | "success" | "warn" | "muted";
}) {
  const styles = {
    default:
      "border border-primary/25 bg-primary/15 text-primary backdrop-blur-md shadow-[inset_0_1px_0_hsl(0_0%_100%/0.12)]",
    success:
      "border border-emerald-400/20 bg-emerald-500/12 text-emerald-300 backdrop-blur-md",
    warn: "border border-amber-400/20 bg-amber-500/12 text-amber-200 backdrop-blur-md",
    muted:
      "border border-white/10 bg-white/[0.06] text-muted-foreground backdrop-blur-md",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
