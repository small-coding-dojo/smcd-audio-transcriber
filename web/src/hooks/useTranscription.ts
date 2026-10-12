import { useCallback, useEffect, useRef, useState } from "react";
import { client } from "../api/client";
import { ClientError, type ApiError, type Transcript } from "../api/types";

export type Phase =
  | { name: "idle" }
  | { name: "submitting" }
  | { name: "processing"; queued: boolean; progress?: number }
  | { name: "done"; transcript: Transcript }
  | { name: "error"; error: ApiError };

const POLL_MS = 1000;
const MAX_NETWORK_FAILURES = 5;

const toApiError = (e: unknown): ApiError =>
  e instanceof ClientError ? e.error : { code: "network", message: "Could not reach the service." };

/** idle -> submitting -> processing (polling) -> done | error. Everything lives in memory only. */
export function useTranscription() {
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const abort = useRef<AbortController | null>(null);
  const jobId = useRef<string | null>(null);

  const reset = useCallback(() => {
    abort.current?.abort();
    if (jobId.current) void client.cancel(jobId.current);
    jobId.current = null;
    setPhase({ name: "idle" });
  }, []);

  const start = useCallback(async (file: File) => {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setPhase({ name: "submitting" });
    try {
      const id = await client.submit(file, ctl.signal);
      jobId.current = id;
      let failures = 0;
      for (;;) {
        try {
          const job = await client.get(id, ctl.signal);
          failures = 0;
          if (job.status === "done") return setPhase({ name: "done", transcript: job.result });
          if (job.status === "failed") return setPhase({ name: "error", error: job.error });
          setPhase({
            name: "processing",
            queued: job.status === "queued",
            progress: job.status === "processing" ? job.progress : undefined,
          });
        } catch (e) {
          if (ctl.signal.aborted || e instanceof ClientError || ++failures >= MAX_NETWORK_FAILURES) throw e;
        }
        await new Promise((r) => setTimeout(r, POLL_MS));
        if (ctl.signal.aborted) return;
      }
    } catch (e) {
      if (ctl.signal.aborted) return;
      setPhase({ name: "error", error: toApiError(e) });
    }
  }, []);

  useEffect(() => () => abort.current?.abort(), []);

  return { phase, start, reset };
}
