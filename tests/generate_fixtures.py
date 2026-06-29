#!/usr/bin/env python3
"""
Generate test fixtures for the Audio Transcriber Service test suite.

No system packages required — all dependencies are pip-installable:

    pip install -r tests/requirements-test.txt

edge-tts uses Microsoft's neural TTS API (internet access required during generation).
static-ffmpeg downloads a static ffmpeg binary on first run (internet access required once).

Usage:
    python tests/generate_fixtures.py           # skip existing files
    python tests/generate_fixtures.py --force   # regenerate all
"""

import argparse
import asyncio
import json
import os
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

# ── Voice definitions (edge-tts) ──────────────────────────────────────────────
# Two distinct German voices (ConradNeural = male, KatjaNeural = female).
# Additional speakers are differentiated via rate/pitch adjustments.

VOICES: dict[str, dict] = {
    "SPEAKER_00": {"voice": "de-DE-ConradNeural", "rate": "+0%",   "pitch": "+0Hz"},
    "SPEAKER_01": {"voice": "de-DE-KatjaNeural",  "rate": "+0%",   "pitch": "+0Hz"},
    "SPEAKER_02": {"voice": "de-DE-ConradNeural", "rate": "-12%",  "pitch": "-8Hz"},
    "SPEAKER_03": {"voice": "de-DE-KatjaNeural",  "rate": "+12%",  "pitch": "+5Hz"},
    "SPEAKER_04": {"voice": "de-DE-ConradNeural", "rate": "+8%",   "pitch": "+10Hz"},
    "EN_SPEAKER":  {"voice": "en-US-GuyNeural",   "rate": "+0%",   "pitch": "+0Hz"},
}

# ── Scripts ───────────────────────────────────────────────────────────────────

DE_2SPK_SCRIPT = [
    ("SPEAKER_00", "Guten Morgen. Wie geht es Ihnen heute?"),
    ("SPEAKER_01", "Danke, mir geht es sehr gut. Und Ihnen?"),
    ("SPEAKER_00", "Auch gut, danke schön. Was haben Sie heute geplant?"),
    ("SPEAKER_01", "Ich habe ein wichtiges Meeting am Nachmittag. Und Sie?"),
    ("SPEAKER_00", "Ich arbeite heute von zu Hause aus. Das ist sehr angenehm."),
    ("SPEAKER_01", "Das klingt wunderbar. Ich wünsche Ihnen einen schönen Tag."),
]

DE_1SPK_LINES = [
    "Deutschland ist ein Land in Mitteleuropa.",
    "Die Hauptstadt ist Berlin.",
    "Es gibt viele schöne Städte in Deutschland.",
    "München, Hamburg und Köln sind bekannte Städte.",
    "Die deutsche Sprache wird von über neunzig Millionen Menschen gesprochen.",
    "Deutschland ist bekannt für seine Kultur und Geschichte.",
    "Es gibt viele Museen, Theater und Konzerthäuser.",
    "Die deutsche Küche ist sehr vielfältig.",
    "Brot, Wurst und Käse sind typische Lebensmittel.",
    "Deutschland ist auch für seine Autos bekannt.",
    "Volkswagen, BMW und Mercedes sind weltberühmte Marken.",
    "Die Natur in Deutschland ist sehr abwechslungsreich.",
    "Es gibt Berge, Wälder und Seen.",
    "Der Rhein ist ein wichtiger Fluss in Deutschland.",
]

EN_1SPK_LINES = [
    "The quick brown fox jumps over the lazy dog.",
    "Audio transcription is a useful technology for many applications.",
    "This is a test recording for the transcription service.",
]

DE_5SPK_SCRIPT = [
    ("SPEAKER_00", "Guten Tag, ich bin der erste Sprecher."),
    ("SPEAKER_01", "Hallo, ich bin die zweite Sprecherin."),
    ("SPEAKER_02", "Und ich bin der dritte Sprecher."),
    ("SPEAKER_03", "Ich bin die vierte Sprecherin."),
    ("SPEAKER_04", "Und ich bin der fünfte Sprecher."),
    ("SPEAKER_00", "Wir testen heute ein Transkriptionssystem."),
    ("SPEAKER_01", "Es soll mehrere Sprecher erkennen können."),
    ("SPEAKER_02", "Das ist eine wichtige Funktion für viele Anwendungen."),
    ("SPEAKER_03", "Ja, die Sprechererkennung ist sehr nützlich."),
    ("SPEAKER_04", "Ich stimme dem vollkommen zu."),
]

# ── Bootstrap ─────────────────────────────────────────────────────────────────

def bootstrap() -> None:
    """Import optional deps and inject static ffmpeg into PATH."""
    missing = []
    for pkg in ("edge_tts", "static_ffmpeg"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg.replace("_", "-"))

    if missing:
        print(f"ERROR: missing packages: {', '.join(missing)}", file=sys.stderr)
        print("Install:  pip install -r tests/requirements-test.txt", file=sys.stderr)
        sys.exit(1)

    import static_ffmpeg
    static_ffmpeg.add_paths()  # downloads binary on first call, then adds to PATH


# ── Utilities ─────────────────────────────────────────────────────────────────

def ffmpeg(*args: str, quiet: bool = True) -> None:
    cmd = ["ffmpeg", "-y", *args]
    kwargs: dict = {"check": True}
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    subprocess.run(cmd, **kwargs)


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


async def tts_mp3(text: str, voice_key: str, out: Path) -> None:
    import edge_tts
    v = VOICES[voice_key]
    comm = edge_tts.Communicate(text, v["voice"], rate=v["rate"], pitch=v["pitch"])
    await comm.save(str(out))


async def tts_wav(text: str, voice_key: str, out: Path) -> None:
    """Generate TTS as MP3 then convert to WAV for WAV-based fixtures."""
    mp3 = out.with_suffix(".mp3")
    await tts_mp3(text, voice_key, mp3)
    ffmpeg("-i", str(mp3), "-ar", "22050", "-ac", "1", str(out))
    mp3.unlink()


def concat_wavs(parts: list[Path], out: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in parts:
            f.write(f"file '{p.resolve()}'\n")
        list_path = f.name
    try:
        ffmpeg("-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", str(out))
    finally:
        os.unlink(list_path)


def already_done(path: Path, force: bool) -> bool:
    if path.exists() and not force:
        print(f"  skip  {path.name}")
        return True
    return False


# ── Generators ────────────────────────────────────────────────────────────────

async def gen_de_2spk(force: bool) -> None:
    out = FIXTURES / "clear_de_2spk_30s.wav"
    gt  = FIXTURES / "clear_de_2spk_30s.ground_truth.json"
    if already_done(out, force):
        return

    print(f"  gen   {out.name}")
    segments: list[dict] = []
    cursor = 0.0

    with tempfile.TemporaryDirectory() as tmp:
        parts: list[Path] = []
        for i, (speaker, text) in enumerate(DE_2SPK_SCRIPT):
            seg = Path(tmp) / f"seg_{i:02d}.wav"
            await tts_wav(text, speaker, seg)
            dur = ffprobe_duration(seg)
            segments.append({"start": round(cursor, 3), "end": round(cursor + dur, 3),
                              "text": text, "speaker": speaker})
            cursor += dur
            parts.append(seg)
        concat_wavs(parts, out)

    gt.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
    print(f"        ground truth written  ({cursor:.1f}s total)")


async def gen_de_1spk(force: bool) -> None:
    out = FIXTURES / "clear_de_1spk_60s.mp3"
    gt  = FIXTURES / "clear_de_1spk_60s.ground_truth.json"
    if already_done(out, force):
        return

    print(f"  gen   {out.name}")
    segments: list[dict] = []
    cursor = 0.0

    with tempfile.TemporaryDirectory() as tmp:
        parts: list[Path] = []
        for i, text in enumerate(DE_1SPK_LINES):
            seg = Path(tmp) / f"seg_{i:02d}.wav"
            await tts_wav(text, "SPEAKER_00", seg)
            dur = ffprobe_duration(seg)
            segments.append({"start": round(cursor, 3), "end": round(cursor + dur, 3),
                              "text": text, "speaker": "SPEAKER_00"})
            cursor += dur
            parts.append(seg)

        wav_tmp = Path(tmp) / "combined.wav"
        concat_wavs(parts, wav_tmp)
        ffmpeg("-i", str(wav_tmp), "-c:a", "libmp3lame", "-q:a", "2", str(out))

    gt.write_text(json.dumps(segments, ensure_ascii=False, indent=2))
    print(f"        ground truth written  ({cursor:.1f}s total)")


async def gen_en_1spk(force: bool) -> None:
    out = FIXTURES / "clear_en_1spk_10s.wav"
    if already_done(out, force):
        return

    print(f"  gen   {out.name}")
    with tempfile.TemporaryDirectory() as tmp:
        parts: list[Path] = []
        for i, text in enumerate(EN_1SPK_LINES):
            seg = Path(tmp) / f"seg_{i:02d}.wav"
            await tts_wav(text, "EN_SPEAKER", seg)
            parts.append(seg)
        concat_wavs(parts, out)


def gen_silence(force: bool) -> None:
    out = FIXTURES / "silence_10s.wav"
    if already_done(out, force):
        return
    print(f"  gen   {out.name}")
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "10", str(out))


def gen_noisy(force: bool) -> None:
    out    = FIXTURES / "noisy_speech_30s.wav"
    speech = FIXTURES / "clear_de_2spk_30s.wav"
    if already_done(out, force):
        return
    if not speech.exists():
        print(f"  SKIP  {out.name}  (clear_de_2spk_30s.wav not yet present)")
        return
    print(f"  gen   {out.name}")
    ffmpeg(
        "-i", str(speech),
        "-f", "lavfi", "-i", "anoisesrc=color=white:amplitude=0.03",
        "-filter_complex", "amix=inputs=2:duration=first:weights=1 0.4",
        str(out),
    )


def gen_long(force: bool) -> None:
    out    = FIXTURES / "long_90min.mp3"
    source = FIXTURES / "clear_de_1spk_60s.mp3"
    if already_done(out, force):
        return
    if not source.exists():
        print(f"  SKIP  {out.name}  (clear_de_1spk_60s.mp3 not yet present)")
        return
    print(f"  gen   {out.name}  (looping 60s source to 90 min — takes ~30 s)")
    ffmpeg(
        "-stream_loop", "-1", "-i", str(source),
        "-t", "5400",
        "-c:a", "libmp3lame", "-q:a", "7",
        str(out),
    )


def gen_very_short(force: bool) -> None:
    out = FIXTURES / "very_short_200ms.wav"
    if already_done(out, force):
        return
    print(f"  gen   {out.name}")
    ffmpeg("-f", "lavfi",
           "-i", "sine=frequency=440:duration=0.2:sample_rate=22050",
           str(out))


def gen_format_variants(force: bool) -> None:
    source = FIXTURES / "clear_en_1spk_10s.wav"
    if not source.exists():
        print("  SKIP  format variants  (clear_en_1spk_10s.wav not yet present)")
        return

    variants: dict[str, list[str]] = {
        "same_audio.flac": ["-c:a", "flac"],
        "same_audio.m4a":  ["-c:a", "aac", "-b:a", "128k"],
        "same_audio.ogg":  ["-c:a", "libvorbis", "-q:a", "4"],
        "same_audio.webm": ["-c:a", "libopus", "-b:a", "128k"],
        "same_audio.mp4":  ["-c:a", "aac", "-b:a", "128k"],
    }
    for name, codec_args in variants.items():
        out = FIXTURES / name
        if already_done(out, force):
            continue
        print(f"  gen   {name}")
        ffmpeg("-i", str(source), *codec_args, str(out))


def gen_corrupt_wav(force: bool) -> None:
    out = FIXTURES / "corrupt.wav"
    if already_done(out, force):
        return
    print(f"  gen   {out.name}")
    sample_rate  = 22050
    channels     = 1
    bits         = 16
    data_size    = 1024
    byte_rate    = sample_rate * channels * bits // 8
    block_align  = channels * bits // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, channels,
        sample_rate, byte_rate, block_align, bits,
        b"data", data_size,
    )
    rng = random.Random(42)
    garbage = bytes(rng.randint(0, 255) for _ in range(data_size))
    out.write_bytes(header + garbage)


def gen_pdf_fixtures(force: bool) -> None:
    minimal_pdf = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n173\n%%EOF\n"
    )
    for name in ("not_audio.pdf", "fake_wav.wav"):
        out = FIXTURES / name
        if already_done(out, force):
            continue
        print(f"  gen   {name}")
        out.write_bytes(minimal_pdf)


def gen_empty(force: bool) -> None:
    out = FIXTURES / "empty.wav"
    if already_done(out, force):
        return
    print(f"  gen   {out.name}")
    out.write_bytes(b"")


async def gen_5speaker(force: bool) -> None:
    out = FIXTURES / "5speaker_30s.wav"
    if already_done(out, force):
        return

    print(f"  gen   {out.name}")
    with tempfile.TemporaryDirectory() as tmp:
        parts: list[Path] = []
        for i, (speaker, text) in enumerate(DE_5SPK_SCRIPT):
            seg = Path(tmp) / f"seg_{i:02d}.wav"
            await tts_wav(text, speaker, seg)
            parts.append(seg)
        concat_wavs(parts, out)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main_async(force: bool) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    print(f"Writing fixtures to {FIXTURES}\n")

    # TTS fixtures (order matters: later generators depend on earlier outputs)
    await gen_de_2spk(force)
    await gen_de_1spk(force)
    await gen_en_1spk(force)
    await gen_5speaker(force)

    # Pure-ffmpeg / file-manipulation fixtures (synchronous)
    gen_silence(force)
    gen_noisy(force)
    gen_long(force)
    gen_very_short(force)
    gen_format_variants(force)
    gen_corrupt_wav(force)
    gen_pdf_fixtures(force)
    gen_empty(force)

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--force", action="store_true",
                        help="Regenerate files that already exist")
    args = parser.parse_args()

    bootstrap()
    asyncio.run(main_async(args.force))


if __name__ == "__main__":
    main()
