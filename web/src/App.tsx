import { useEffect, useState } from "react";
import { Dropzone } from "./components/Dropzone";
import { Progress } from "./components/Progress";
import { TranscriptView } from "./components/TranscriptView";
import { useTranscription } from "./hooks/useTranscription";
import type { ErrorCode } from "./api/types";

const ERROR_TITLES: Record<ErrorCode, string> = {
  unsupported_format: "Unsupported file format",
  too_large: "File too large",
  no_speech: "No speech detected",
  timeout: "This took too long",
  network: "Connection problem",
  internal: "Something went wrong",
};

export default function App() {
  const { phase, start, reset } = useTranscription();
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // The player reads the local file; the object URL never leaves the browser.
  useEffect(() => {
    if (!file) return setAudioUrl(null);
    const url = URL.createObjectURL(file);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const clear = () => {
    reset();
    setFile(null);
  };
  const pick = (f: File) => {
    setFile(f);
    void start(f);
  };

  return (
    <main>
      <header>
        <h1>ClearVoice</h1>
        {phase.name !== "idle" && <button className="secondary" onClick={clear}>{phase.name === "done" ? "Clear & start over" : "Start over"}</button>}
      </header>

      {phase.name === "idle" && <Dropzone onFile={pick} />}

      {(phase.name === "submitting" || phase.name === "processing") && (
        <Progress phase={phase} fileName={file?.name ?? ""} onCancel={clear} />
      )}

      {phase.name === "error" && (
        <div className="card center" role="alert">
          <h2>{ERROR_TITLES[phase.error.code]}</h2>
          <p>{phase.error.message}</p>
          <div className="row">
            {file && phase.error.code !== "no_speech" && phase.error.code !== "unsupported_format" && (
              <button onClick={() => void start(file)}>Try again</button>
            )}
            <button className="secondary" onClick={clear}>Choose another file</button>
          </div>
        </div>
      )}

      {phase.name === "done" && audioUrl && <TranscriptView transcript={phase.transcript} audioUrl={audioUrl} />}
    </main>
  );
}
