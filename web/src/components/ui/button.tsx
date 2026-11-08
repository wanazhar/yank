import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "relative z-[1] inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:pointer-events-none disabled:opacity-40 active:scale-[0.97]",
  {
    variants: {
      variant: {
        default:
          "border border-white/20 bg-primary/90 text-primary-foreground shadow-glow backdrop-blur-md hover:bg-primary",
        outline:
          "field border-border text-foreground hover:bg-muted/80",
        ghost: "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 px-3 text-xs rounded-lg",
        lg: "h-12 px-5 text-base rounded-2xl",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  ),
);
Button.displayName = "Button";
