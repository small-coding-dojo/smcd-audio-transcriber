import type { Segment, Transcript } from "../api/types";
import { formatTime } from "./format";

export type ExportFormat = "txt" | "srt" | "vtt" | "json";
export type Names = Record<string, string>;

const label = (s: Segment, names: Names) => (s.speaker ? (names[s.speaker] ?? s.speaker) : null);

function stamp(sec: number, sep: "," | "."): string {
  const ms = Math.round(sec * 1000);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)}${sep}${p(ms % 1000, 3)}`;
}

export function exportTranscript(t: Transcript, fmt: ExportFormat, names: Names = {}): string {
  const line = (s: Segment) => {
    const who = label(s, names);
    return who ? `${who}: ${s.text}` : s.text;
  };
  switch (fmt) {
    case "txt":
      return t.segments.map((s) => `[${formatTime(s.start)}] ${line(s)}`).join("\n") + "\n";
    case "srt":
      return t.segments.map((s, i) => `${i + 1}\n${stamp(s.start, ",")} --> ${stamp(s.end, ",")}\n${line(s)}\n`).join("\n");
    case "vtt":
      return "WEBVTT\n\n" + t.segments.map((s) => `${stamp(s.start, ".")} --> ${stamp(s.end, ".")}\n${line(s)}\n`).join("\n");
    case "json":
      return JSON.stringify({ ...t, segments: t.segments.map((s) => ({ ...s, speaker: label(s, names) })) }, null, 2);
  }
}

export function download(content: string, fmt: ExportFormat) {
  const type = fmt === "json" ? "application/json" : "text/plain";
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `transcript.${fmt}`;
  a.click();
  URL.revokeObjectURL(url);
}
