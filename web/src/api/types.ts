// API contract (see docs/api-contract.md). Async: submit a job, then poll it.

export interface Segment {
  start: number; // seconds
  end: number;
  speaker: string | null; // null when diarisation is unavailable
  text: string;
}

export interface Transcript {
  duration: number;
  language: string;
  speakers: string[];
  segments: Segment[];
}

export type ErrorCode = "unsupported_format" | "too_large" | "no_speech" | "timeout" | "network" | "internal";

export interface ApiError {
  code: ErrorCode;
  message: string;
}

export type JobState =
  | { status: "queued" }
  | { status: "processing"; progress?: number } // 0..1 when the service can tell
  | { status: "done"; result: Transcript }
  | { status: "failed"; error: ApiError };

export interface TranscriptionClient {
  /** POST /v1/jobs — returns the job id. */
  submit(file: File, signal: AbortSignal): Promise<string>;
  /** GET /v1/jobs/:id */
  get(id: string, signal: AbortSignal): Promise<JobState>;
  /** DELETE /v1/jobs/:id — also discards any server-side result. */
  cancel(id: string): Promise<void>;
}

export class ClientError extends Error {
  constructor(public readonly error: ApiError) {
    super(error.message);
  }
}
