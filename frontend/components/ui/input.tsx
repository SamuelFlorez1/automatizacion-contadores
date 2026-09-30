import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-[8px] border border-line bg-surface-card px-3 py-1.5 text-sm text-ink placeholder:text-ink-subtle",
        "shadow-[inset_0_1px_0_rgb(15_23_42/0.02)]",
        "transition-colors focus-visible:border-brand-600 focus-visible:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-ink",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
