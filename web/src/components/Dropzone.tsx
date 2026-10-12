import { useRef, useState } from "react";

const MAX_BYTES = 500 * 1024 * 1024; // client-side sanity limit only; the service decides

interface Props {
  onFile: (file: File) => void;
}

export function Dropzone({ onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const accept = (file?: File) => {
    if (!file) return;
    if (file.size === 0) return setProblem("That file is empty.");
    if (file.size > MAX_BYTES) return setProblem("That file is too large (limit 500 MB).");
    if (!file.type.startsWith("audio/") && !/\.(mp3|wav|m4a|ogg|flac|webm|aac)$/i.test(file.name)) {
      return setProblem("Please choose an audio file (MP3, WAV, M4A, OGG, FLAC, WebM).");
    }
    setProblem(null);
    onFile(file);
  };

  return (
    <div>
      <button
        type="button"
        className={`dropzone${over ? " over" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => (e.preventDefault(), setOver(true))}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => (e.preventDefault(), setOver(false), accept(e.dataTransfer.files[0]))}
      >
        <strong>Drop an audio file here</strong>
        <span>or click to browse · MP3, WAV, M4A, OGG, FLAC</span>
      </button>
      <input ref={input} type="file" accept="audio/*" hidden onChange={(e) => accept(e.target.files?.[0])} />
      {problem && <p role="alert" className="problem">{problem}</p>}
      <p className="privacy">
        🔒 Your audio is sent once for transcription and never stored. The transcript exists only in this tab.
      </p>
    </div>
  );
}
