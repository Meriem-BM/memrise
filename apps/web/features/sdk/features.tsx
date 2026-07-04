import { Layers, Share2, ShieldCheck } from "lucide-react";

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
        {/* Big stat + hand-drawn underline */}
        <Card className="col-span-full flex lg:col-span-2">
          <div className="relative m-auto size-fit px-6 py-8">
            <div className="relative flex h-24 w-56 items-center">
              <svg
                className="absolute inset-0 size-full text-white/12"
                viewBox="0 0 254 104"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M112.891 97.7022C140.366 97.0802 171.004 94.6715 201.087 87.5116C210.43 85.2881 219.615 82.6412 228.284 78.2473C232.198 76.3179 235.905 73.9942 239.348 71.3124C241.85 69.2557 243.954 66.7571 245.555 63.9408C249.34 57.3235 248.281 50.5341 242.498 45.6109C239.033 42.7237 235.228 40.2703 231.169 38.3054C219.443 32.7209 207.141 28.4382 194.482 25.534C184.013 23.1927 173.358 21.7755 162.64 21.2989C161.376 21.3512 160.113 21.181 158.908 20.796C158.034 20.399 156.857 19.1682 156.962 18.4535C157.115 17.8927 157.381 17.3689 157.743 16.9139C158.104 16.4588 158.555 16.0821 159.067 15.8066C160.14 15.4683 161.274 15.3733 162.389 15.5286C179.805 15.3566 196.626 18.8373 212.998 24.462C220.978 27.2494 228.798 30.4747 236.423 34.1232C240.476 36.1159 244.202 38.7131 247.474 41.8258C254.342 48.2578 255.745 56.9397 251.841 65.4892C249.793 69.8582 246.736 73.6777 242.921 76.6327C236.224 82.0192 228.522 85.4602 220.502 88.2924C205.017 93.7847 188.964 96.9081 172.738 99.2109C153.442 101.949 133.993 103.478 114.506 103.79C91.1468 104.161 67.9334 102.97 45.1169 97.5831C36.0094 95.5616 27.2626 92.1655 19.1771 87.5116C13.839 84.5746 9.1557 80.5802 5.41318 75.7725C-0.54238 67.7259 -1.13794 59.1763 3.25594 50.2827C5.82447 45.3918 9.29572 41.0315 13.4863 37.4319C24.2989 27.5721 37.0438 20.9681 50.5431 15.7272C68.1451 8.8849 86.4883 5.1395 105.175 2.83669C129.045 0.0992292 153.151 0.134761 177.013 2.94256C197.672 5.23215 218.04 9.01724 237.588 16.3889C240.089 17.3418 242.498 18.5197 244.933 19.6446C246.627 20.4387 247.725 21.6695 246.997 23.615C246.455 25.1105 244.814 25.5605 242.63 24.5811C230.322 18.9961 217.233 16.1904 204.117 13.4376C188.761 10.3438 173.2 8.36665 157.558 7.52174C129.914 5.70776 102.154 8.06792 75.2124 14.5228C60.6177 17.8788 46.5758 23.2977 33.5102 30.6161C26.6595 34.3329 20.4123 39.0673 14.9818 44.658C12.9433 46.8071 11.1336 49.1622 9.58207 51.6855C4.87056 59.5336 5.61172 67.2494 11.9246 73.7608C15.2064 77.0494 18.8775 79.925 22.8564 82.3236C31.6176 87.7101 41.3848 90.5291 51.3902 92.5804C70.6068 96.5773 90.0219 97.7419 112.891 97.7022Z"
                  fill="currentColor"
                />
              </svg>
              <span className="mx-auto block w-fit text-5xl font-semibold text-white">100%</span>
            </div>
            <h3 className="mt-6 text-center text-xl font-semibold text-white">Framework-free</h3>
            <p className="mt-1 text-center text-sm text-muted">Any agent stack, over HTTP.</p>
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
      className={`relative overflow-hidden rounded-2xl border border-border bg-white/1.5 ${className}`}
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
