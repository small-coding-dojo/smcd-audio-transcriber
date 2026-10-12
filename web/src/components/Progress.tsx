import type { Phase } from "../hooks/useTranscription";

interface Props {
  phase: Extract<Phase, { name: "submitting" | "processing" }>;
  fileName: string;
  onCancel: () => void;
}

export function Progress({ phase, fileName, onCancel }: Props) {
  const text =
    phase.name === "submitting" ? "Uploading…" : phase.queued ? "Waiting in queue…" : "Transcribing…";
  const pct = phase.name === "processing" ? phase.progress : undefined;
  return (
    <div className="card center">
      <p className="filename">{fileName}</p>
      <div
        className={`bar${pct === undefined ? " indeterminate" : ""}`}
        role="progressbar"
        aria-label={text}
        aria-valuenow={pct === undefined ? undefined : Math.round(pct * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div style={pct === undefined ? undefined : { width: `${pct * 100}%` }} />
      </div>
      <p role="status">{text}</p>
      <button className="secondary" onClick={onCancel}>Cancel</button>
    </div>
  );
}
