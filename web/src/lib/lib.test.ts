import { describe, expect, it } from "vitest";
import { exportTranscript } from "./export";
import { formatTime } from "./format";

const t = {
  duration: 10,
  language: "en",
  speakers: ["Speaker 1"],
  segments: [{ start: 0, end: 4.5, speaker: "Speaker 1", text: "Hello." }],
};

describe("formatTime", () => {
  it("formats minutes and hours", () => {
    expect(formatTime(75.3)).toBe("1:15");
    expect(formatTime(3725)).toBe("1:02:05");
  });
});

describe("exportTranscript", () => {
  it("applies renamed speakers", () => {
    expect(exportTranscript(t, "txt", { "Speaker 1": "Anna" })).toBe("[0:00] Anna: Hello.\n");
  });
  it("writes SRT and VTT timestamps", () => {
    expect(exportTranscript(t, "srt")).toContain("00:00:00,000 --> 00:00:04,500");
    expect(exportTranscript(t, "vtt")).toMatch(/^WEBVTT[\s\S]*00:00:00\.000 --> 00:00:04\.500/);
  });
  it("omits labels without diarisation", () => {
    const mono = { ...t, segments: [{ ...t.segments[0], speaker: null }] };
    expect(exportTranscript(mono, "txt")).toBe("[0:00] Hello.\n");
  });
});
