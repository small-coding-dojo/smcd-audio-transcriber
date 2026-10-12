import { ClientError, type ApiError, type JobState, type TranscriptionClient } from "./types";

async function fail(res: Response): Promise<never> {
  let error: ApiError = { code: "internal", message: `Unexpected response (${res.status}).` };
  try {
    const body = await res.json();
    if (body?.error?.code) error = body.error;
  } catch {
    /* keep default */
  }
  throw new ClientError(error);
}

/** Real client for the Audio Transcriber Service. */
export const httpClient: TranscriptionClient = {
  async submit(file, signal) {
    const form = new FormData();
    form.append("audio", file);
    const res = await fetch("/v1/jobs", { method: "POST", body: form, signal });
    if (!res.ok) await fail(res);
    return (await res.json()).id as string;
  },
  async get(id, signal) {
    const res = await fetch(`/v1/jobs/${encodeURIComponent(id)}`, { signal });
    if (!res.ok) await fail(res);
    return (await res.json()) as JobState;
  },
  async cancel(id) {
    await fetch(`/v1/jobs/${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() => {});
  },
};
