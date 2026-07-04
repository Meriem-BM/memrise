import { humanizeReason } from "@/lib/trace";

export function ReasonBadge({ code }: { code: string }) {
  const text = humanizeReason(code);
  return (
    <span className="inline-flex items-center rounded-full border border-white/10 bg-white/6 px-2.5 py-0.5 text-[11px] leading-5 text-warn">
      {text === code ? <span className="font-mono">{code}</span> : text}
    </span>
  );
}
