export function ScoreBar({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 font-mono text-[11px] uppercase tracking-wider text-faint">
        {label}
      </span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-white/70" style={{ width: `${clamped * 100}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-[11px] text-muted">{clamped.toFixed(2)}</span>
    </div>
  );
}
