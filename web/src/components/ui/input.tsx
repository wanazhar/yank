import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "field relative flex h-11 w-full rounded-lg px-3.5 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground/70",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = "Input";
