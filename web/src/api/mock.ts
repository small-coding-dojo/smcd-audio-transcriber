import { ClientError, type JobState, type Segment, type TranscriptionClient } from "./types";

// In-memory fake backend. Nothing is uploaded; the file is only inspected for its name.
// Magic file names: "*fail*" -> internal error, "*silence*" -> no_speech,
// "*mono*" -> no diarisation, "*slow*" -> takes 3x longer.

const SCRIPT: [string, string][] = [
  ["Speaker 1", "Welcome everyone, thanks for joining the call today."],
  ["Speaker 2", "Happy to be here. Shall we start with the roadmap?"],
  ["Speaker 1", "Yes. The first item is the new upload flow for the web application."],
  ["Speaker 2", "Right, and privacy is the main concern: nothing may be stored after the response."],
  ["Speaker 1", "Agreed. Transcripts only live in the browser and disappear when the tab closes."],
  ["Speaker 2", "Good. What about longer recordings?"],
  ["Speaker 1", "Those are processed asynchronously, so the page just polls for the result."],
  ["Speaker 2", "Perfect. Let's make sure we catch every word."],
];

interface Job {
  name: string;
  startedAt: number;
  durationMs: number;
  audioSeconds: number;
}
const jobs = new Map<string, Job>();

function audioDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const a = new Audio();
    const done = (d: number) => {
      URL.revokeObjectURL(url);
      resolve(Number.isFinite(d) && d > 0 ? d : 30);
    };
    a.onloadedmetadata = () => done(a.duration);
    a.onerror = () => done(30);
    a.src = url;
  });
}

function buildSegments(total: number, diarise: boolean): Segment[] {
  const step = total / SCRIPT.length;
  return SCRIPT.map(([speaker, text], i) => ({
    start: +(i * step).toFixed(2),
    end: +((i + 1) * step - 0.3).toFixed(2),
    speaker: diarise ? speaker : null,
    text,
  }));
}

const delay = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

export const mockClient: TranscriptionClient = {
  async submit(file, signal) {
    await delay(400, signal);
    const name = file.name.toLowerCase();
    if (!/^audio\//.test(file.type) && !/\.(mp3|wav|m4a|ogg|flac|webm|aac)$/.test(name)) {
      throw new ClientError({ code: "unsupported_format", message: "This file type is not supported." });
    }
    const audioSeconds = await audioDuration(file);
    const id = crypto.randomUUID();
    const base = Math.min(12000, 3000 + audioSeconds * 100);
    jobs.set(id, { name, startedAt: Date.now(), durationMs: name.includes("slow") ? base * 3 : base, audioSeconds });
    return id;
  },

  async get(id, signal) {
    await delay(150, signal);
    const job = jobs.get(id);
    if (!job) throw new ClientError({ code: "internal", message: "Job not found." });
    const elapsed = Date.now() - job.startedAt;
    if (elapsed < 1200) return { status: "queued" } satisfies JobState;
    if (elapsed < job.durationMs) {
      return { status: "processing", progress: elapsed / job.durationMs } satisfies JobState;
    }
    if (job.name.includes("fail")) {
      return { status: "failed", error: { code: "internal", message: "The transcription engine crashed." } };
    }
    if (job.name.includes("silence")) {
      return { status: "failed", error: { code: "no_speech", message: "No speech was detected." } };
    }
    const diarise = !job.name.includes("mono");
    return {
      status: "done",
      result: {
        duration: job.audioSeconds,
        language: "en",
        speakers: diarise ? ["Speaker 1", "Speaker 2"] : [],
        segments: buildSegments(job.audioSeconds, diarise),
      },
    };
  },

  async cancel(id) {
    jobs.delete(id);
  },
};
