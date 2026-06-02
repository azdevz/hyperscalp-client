// dashboard/components/MilestoneBar.tsx

const MILESTONES = [
  { phase: "Seed",      min: 100,   max: 250 },
  { phase: "Growth I",  min: 250,   max: 500 },
  { phase: "Growth II", min: 500,   max: 1000 },
  { phase: "Scale I",   min: 1000,  max: 2500 },
  { phase: "Scale II",  min: 2500,  max: 5000 },
  { phase: "Scale III", min: 5000,  max: 10000 },
];

export default function MilestoneBar({ balance = 100 }: { balance?: number }) {
  const current = MILESTONES.find((m) => balance >= m.min && balance < m.max)
    || MILESTONES[MILESTONES.length - 1];

  const totalProgress = Math.min((balance - 100) / (10000 - 100), 1);
  const phaseProgress = Math.min(
    (balance - current.min) / (current.max - current.min),
    1
  );

  return (
    <div className="card fade-in">
      <div className="card-title">🏆 Compounding Progress</div>

      {/* Total bar */}
      <div style={{ marginBottom: "14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            ${balance.toLocaleString()} / $10,000
          </span>
          <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent-green)" }}>
            {(totalProgress * 100).toFixed(1)}%
          </span>
        </div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{
              width: `${totalProgress * 100}%`,
              background: "var(--gradient-hl)",
            }}
          />
        </div>
      </div>

      {/* Phase indicators */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "12px" }}>
        {MILESTONES.map((m) => {
          const done    = balance >= m.max;
          const active  = balance >= m.min && balance < m.max;
          return (
            <div
              key={m.phase}
              style={{
                flex: 1,
                height: "4px",
                borderRadius: "2px",
                background: done
                  ? "var(--accent-green)"
                  : active
                  ? "var(--accent-blue)"
                  : "var(--bg-elevated)",
                transition: "background 0.4s",
              }}
            />
          );
        })}
      </div>

      {/* Current phase */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "2px" }}>
            Current Phase
          </div>
          <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--accent-blue)" }}>
            {current.phase}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "2px" }}>
            Phase Progress
          </div>
          <div style={{ fontSize: "15px", fontWeight: 700 }}>
            {(phaseProgress * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Phase progress bar */}
      <div className="progress-track" style={{ marginTop: "8px", height: "6px" }}>
        <div
          className="progress-fill"
          style={{
            width: `${phaseProgress * 100}%`,
            background: "var(--gradient-gold)",
          }}
        />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>${current.min.toLocaleString()}</span>
        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>${current.max.toLocaleString()}</span>
      </div>
    </div>
  );
}
