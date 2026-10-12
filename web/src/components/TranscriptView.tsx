import { useEffect, useMemo, useRef, useState } from "react";
import type { Transcript } from "../api/types";
import { download, exportTranscript, type ExportFormat, type Names } from "../lib/export";
import { formatTime } from "../lib/format";

interface Props {
  transcript: Transcript;
  audioUrl: string;
}

const FORMATS: ExportFormat[] = ["txt", "srt", "vtt", "json"];

export function TranscriptView({ transcript, audioUrl }: Props) {
  const audio = useRef<HTMLAudioElement>(null);
  const [now, setNow] = useState(0);
  const [query, setQuery] = useState("");
  const [names, setNames] = useState<Names>({});
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);
  const activeRef = useRef<HTMLLIElement>(null);

  const active = transcript.segments.findIndex((s) => now >= s.start && now < s.end);
  const speakerIndex = (sp: string) => transcript.speakers.indexOf(sp) % 6;
  const nameOf = (sp: string) => names[sp] ?? sp;

  const q = query.trim().toLowerCase();
  const matches = useMemo(
    () => new Set(q ? transcript.segments.flatMap((s, i) => (s.text.toLowerCase().includes(q) ? [i] : [])) : []),
    [q, transcript],
  );

  useEffect(() => {
    if (follow) activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active, follow]);

  const seek = (t: number) => {
    if (!audio.current) return;
    audio.current.currentTime = t;
    void audio.current.play();
  };

  const copy = async () => {
    await navigator.clipboard.writeText(exportTranscript(transcript, "txt", names));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="card">
      <audio
        ref={audio}
        src={audioUrl}
        controls
        onTimeUpdate={(e) => setNow(e.currentTarget.currentTime)}
        aria-label="Recording"
      />

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search transcript"
          aria-label="Search transcript"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="check">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow playback
        </label>
        <button className="secondary" onClick={copy}>{copied ? "Copied ✓" : "Copy"}</button>
        {FORMATS.map((f) => (
          <button key={f} className="secondary" onClick={() => download(exportTranscript(transcript, f, names), f)}>
            .{f}
          </button>
        ))}
      </div>

      {transcript.speakers.length > 0 && (
        <div className="speakers" aria-label="Rename speakers">
          {transcript.speakers.map((sp) => (
            <label key={sp} className={`chip s${speakerIndex(sp)}`}>
              <input
                value={names[sp] ?? sp}
                aria-label={`Name for ${sp}`}
                onChange={(e) => setNames({ ...names, [sp]: e.target.value })}
                size={Math.max(6, nameOf(sp).length)}
              />
            </label>
          ))}
        </div>
      )}
      {q && <p className="hint">{matches.size} matching segment{matches.size === 1 ? "" : "s"}</p>}

      <ol className="segments">
        {transcript.segments.map((s, i) => (
          <li
            key={i}
            ref={i === active ? activeRef : undefined}
            className={`${i === active ? "active" : ""}${matches.has(i) ? " match" : ""}`}
          >
            <button className="time" onClick={() => seek(s.start)} aria-label={`Play from ${formatTime(s.start)}`}>
              {formatTime(s.start)}
            </button>
            <div>
              {s.speaker && <span className={`who s${speakerIndex(s.speaker)}`}>{nameOf(s.speaker)}</span>}
              <p>{s.text}</p>
            </div>
          </li>
        ))}
      </ol>
      {transcript.speakers.length === 0 && (
        <p className="hint">Speaker identification wasn’t available for this recording.</p>
      )}
    </div>
  );
}
