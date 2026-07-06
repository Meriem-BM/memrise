import { Layers, Plug, Share2, ShieldCheck } from "lucide-react";

/** Bento feature grid: real Memrise capabilities, monochrome, self-contained SVGs. */
export function Features() {
  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto mb-10 max-w-2xl text-center">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-faint">
          Not a vector store
        </p>
        <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          A memory that reasons about what it keeps.
        </h2>
      </div>

      <div className="grid grid-cols-6 gap-3">
        {/* Framework-free */}
        <Card className="col-span-full flex lg:col-span-2">
          <div className="m-auto px-6 py-8">
            <div className="relative mx-auto flex aspect-square size-32 items-center justify-center rounded-full border border-white/10 before:absolute before:-inset-2 before:rounded-full before:border before:border-white/5">
              <div className="flex size-16 items-center justify-center rounded-full border border-white/15 bg-white/3">
                <Plug className="size-7 text-white/80" strokeWidth={1.25} />
              </div>
            </div>
            <div className="mt-6 space-y-1.5 text-center">
              <h3 className="text-lg font-medium text-white">Framework-free</h3>
              <p className="text-sm leading-relaxed text-muted">
                Any agent stack, over plain HTTP.
              </p>
            </div>
          </div>
        </Card>

        {/* Secrets stay out: concentric rings */}
        <Card className="col-span-full sm:col-span-3 lg:col-span-2">
          <div className="px-6 py-8">
            <div className="relative mx-auto flex aspect-square size-32 items-center justify-center rounded-full border border-white/10 before:absolute before:-inset-2 before:rounded-full before:border before:border-white/5">
              <div className="flex size-16 items-center justify-center rounded-full border border-white/15 bg-white/3">
                <ShieldCheck className="size-7 text-white/80" strokeWidth={1.25} />
              </div>
            </div>
            <div className="mt-6 space-y-1.5 text-center">
              <h3 className="text-lg font-medium text-white">Secrets stay out</h3>
              <p className="text-sm leading-relaxed text-muted">
                The extraction gate classifies every episode and drops credentials, tokens, and keys
                before they can ever be stored.
              </p>
            </div>
          </div>
        </Card>

        {/* Forgets on purpose: decay sparkline */}
        <Card className="col-span-full sm:col-span-3 lg:col-span-2">
          <div className="px-6 py-8">
            <div className="lg:px-2">
              <svg
                className="w-full text-white/50"
                viewBox="0 0 300 90"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M0 76 L0 20 L36 24 L60 40 L84 30 L108 52 L132 46 L156 60 L192 56 L228 66 L264 63 L300 68 L300 76 Z"
                  fill="url(#decayFill)"
                />
                <path
                  d="M0 20 L36 24 L60 40 L84 30 L108 52 L132 46 L156 60 L192 56 L228 66 L264 63 L300 68"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <line
                  x1="0"
                  y1="46"
                  x2="300"
                  y2="46"
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray="3 4"
                />
                <defs>
                  <linearGradient
                    id="decayFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="90"
                    gradientUnits="userSpaceOnUse"
                  >
                    <stop stopColor="currentColor" stopOpacity="0.14" />
                    <stop offset="1" stopColor="currentColor" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div className="mt-6 space-y-1.5 text-center">
              <h3 className="text-lg font-medium text-white">Forgets on purpose</h3>
              <p className="text-sm leading-relaxed text-muted">
                Usefulness decays, expired facts retire, and contested pairs resolve, so memory
                sharpens instead of bloating.
              </p>
            </div>
          </div>
        </Card>

        {/* Ranked by real signal: fused equalizer */}
        <Card className="col-span-full lg:col-span-3">
          <div className="grid px-6 py-8 sm:grid-cols-2">
            <div className="relative z-10 flex flex-col justify-between gap-8">
              <div className="relative flex aspect-square size-12 items-center justify-center rounded-full border border-white/10 before:absolute before:-inset-2 before:rounded-full before:border before:border-white/5">
                <Layers className="size-5 text-white/80" strokeWidth={1.25} />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-lg font-medium text-white">Ranked by real signal</h3>
                <p className="text-sm leading-relaxed text-muted">
                  Lexical, semantic, and graph retrieval fuse with reciprocal-rank fusion, then your
                  feedback re-weights what surfaces.
                </p>
              </div>
            </div>
            <div className="relative mt-8 flex items-end justify-center gap-2 sm:mt-0">
              {[
                { label: "lex", h: 44 },
                { label: "sem", h: 68 },
                { label: "grp", h: 32 },
                { label: "str", h: 52 },
                { label: "fused", h: 96, strong: true },
              ].map((bar) => (
                <div key={bar.label} className="flex flex-col items-center gap-2">
                  <div
                    className={
                      bar.strong ? "w-7 rounded-t-md bg-white/80" : "w-7 rounded-t-md bg-white/12"
                    }
                    style={{ height: bar.h }}
                  />
                  <span className="font-mono text-[10px] text-faint">{bar.label}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Living knowledge graph: entity pills */}
        <Card className="col-span-full lg:col-span-3">
          <div className="grid h-full px-6 py-8 sm:grid-cols-2">
            <div className="relative z-10 flex flex-col justify-between gap-8">
              <div className="relative flex aspect-square size-12 items-center justify-center rounded-full border border-white/10 before:absolute before:-inset-2 before:rounded-full before:border before:border-white/5">
                <Share2 className="size-5 text-white/80" strokeWidth={1.25} />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-lg font-medium text-white">A living knowledge graph</h3>
                <p className="text-sm leading-relaxed text-muted">
                  Entities and typed relations project automatically. Traverse the graph, not just
                  the text.
                </p>
              </div>
            </div>
            <div className="mt-8 flex items-center justify-center sm:mt-0">
              <MiniGraph />
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}

function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-border bg-panel ${className}`}
    >
      {children}
    </div>
  );
}

/** Self-contained mini knowledge graph: a central node with three typed, drawn edges. */
function MiniGraph() {
  const mono = "var(--font-jetbrains-mono)";
  const cx = 46;
  const cy = 90;
  const targets = [
    { relation: "USES", node: "pnpm", y: 30 },
    { relation: "DEPLOYS ON", node: "Atlas", y: 90 },
    { relation: "BLOCKED BY", node: "CI", y: 150 },
  ];
  const tx = 240;

  return (
    <svg
      className="w-full max-w-[300px]"
      viewBox="0 0 300 180"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* edges */}
      {targets.map((t) => (
        <line
          key={`edge-${t.node}`}
          x1={cx + 42}
          y1={cy}
          x2={tx - 34}
          y2={t.y}
          stroke="rgba(255,255,255,0.16)"
          strokeWidth={1}
        />
      ))}

      {/* relation labels */}
      {targets.map((t) => {
        const mx = (cx + 42 + tx - 34) / 2;
        const my = (cy + t.y) / 2 - 1;
        const w = t.relation.length * 5.6 + 12;
        return (
          <g key={`rel-${t.node}`}>
            <rect
              x={mx - w / 2}
              y={my - 9}
              width={w}
              height={16}
              rx={4}
              fill="#0b0c0f"
              stroke="rgba(255,255,255,0.1)"
            />
            <text
              x={mx}
              y={my + 2}
              textAnchor="middle"
              fill="rgba(255,255,255,0.45)"
              style={{ fontFamily: mono, fontSize: 8, letterSpacing: 0.6 }}
            >
              {t.relation}
            </text>
          </g>
        );
      })}

      {/* central node */}
      <rect
        x={cx - 42}
        y={cy - 15}
        width={84}
        height={30}
        rx={15}
        fill="rgba(255,255,255,0.06)"
        stroke="rgba(255,255,255,0.2)"
      />
      <text
        x={cx}
        y={cy + 3}
        textAnchor="middle"
        fill="#fff"
        style={{ fontFamily: mono, fontSize: 11 }}
      >
        memrise
      </text>

      {/* target nodes */}
      {targets.map((t) => (
        <g key={`node-${t.node}`}>
          <rect
            x={tx - 34}
            y={t.y - 14}
            width={68}
            height={28}
            rx={14}
            fill="rgba(255,255,255,0.04)"
            stroke="rgba(255,255,255,0.15)"
          />
          <text
            x={tx}
            y={t.y + 3}
            textAnchor="middle"
            fill="rgba(255,255,255,0.8)"
            style={{ fontFamily: mono, fontSize: 11 }}
          >
            {t.node}
          </text>
        </g>
      ))}
    </svg>
  );
}
