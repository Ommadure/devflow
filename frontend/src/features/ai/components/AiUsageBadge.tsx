import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useGetAiUsageQuery } from "../api/aiApi";

/** "12/50 AI requests left today" — refreshed after every AI request. */
export function AiUsageBadge() {
  const { data } = useGetAiUsageQuery();
  if (!data) return null;
  const low = data.remaining <= Math.max(1, Math.floor(data.limit / 10));
  return (
    <p className={cn("flex items-center gap-1.5 text-xs", low ? "text-warning" : "text-text/60")}
      title={`Resets at ${new Date(data.resets_at).toLocaleTimeString()}`}>
      <Sparkles aria-hidden className="size-3.5" />
      {data.remaining}/{data.limit} AI requests left today
    </p>
  );
}
