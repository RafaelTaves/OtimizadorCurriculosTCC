import { cn } from "@/lib/utils";
export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "h-11 w-full min-w-0 rounded-[10px] border border-control bg-surface px-3 text-base placeholder:text-muted-foreground aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}
