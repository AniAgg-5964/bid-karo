#!/usr/bin/env python
"""Build the narration track and caption files for the BidKaro demo video.

The caption track is written by ``demo/record-demo.cjs``. This script turns
those captions into narration with the local Windows speech engine (SAPI) and
mixes every sentence into a single track placed at the caption timestamp, then
writes matching SRT and WebVTT caption files.

If no local speech engine is available the script fails with a clear message
instead of pretending that narration exists; the captioned silent video is
still valid output in that case.

Usage (from the repository root):

    python demo\\build-narration.py --recording demo\\.recording
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 22050
TTS_SCRIPT = r"""
param([string]$InputPath, [string]$OutDir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$data = Get-Content -Raw -Encoding UTF8 $InputPath | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = -1
$voice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like '*Zira*' } | Select-Object -First 1
if ($voice) { $synth.SelectVoice($voice.VoiceInfo.Name) }
foreach ($item in $data) {
  $path = Join-Path $OutDir $item.wav
  $synth.SetOutputToWaveFile($path)
  $synth.Speak([string]$item.text)
  $synth.SetOutputToNull()
}
$synth.Dispose()
Write-Output "synthesized $($data.Count) clips"
"""


def srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def vtt_timestamp(seconds: float) -> str:
    return srt_timestamp(seconds).replace(",", ".")


def write_caption_files(captions: list[dict], out_dir: Path) -> tuple[Path, Path]:
    srt_lines: list[str] = []
    vtt_lines: list[str] = ["WEBVTT", ""]
    for index, item in enumerate(captions, start=1):
        start = item["startMs"] / 1000
        end = max(item.get("endMs", item["startMs"] + 4000) / 1000, start + 1)
        srt_lines.append(str(index))
        srt_lines.append(f"{srt_timestamp(start)} --> {srt_timestamp(end)}")
        srt_lines.append(item["text"])
        srt_lines.append("")
        vtt_lines.append(f"{vtt_timestamp(start)} --> {vtt_timestamp(end)}")
        vtt_lines.append(item["text"])
        vtt_lines.append("")
    srt_path = out_dir / "captions.srt"
    vtt_path = out_dir / "captions.vtt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
    return srt_path, vtt_path


def synthesize(captions: list[dict], work_dir: Path) -> list[Path]:
    if sys.platform != "win32":
        raise SystemExit(
            "Local text-to-speech is only wired for Windows SAPI. "
            "Ship the captioned silent video instead."
        )
    payload = [
        {"text": item["text"], "wav": f"cap-{index:03d}.wav"}
        for index, item in enumerate(captions, start=1)
    ]
    input_path = work_dir / "tts-input.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    script_path = work_dir / "tts.ps1"
    script_path.write_text(TTS_SCRIPT, encoding="utf-8")

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-InputPath",
            str(input_path),
            "-OutDir",
            str(work_dir),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"Text-to-speech failed:\n{result.stdout}\n{result.stderr}")
    print(result.stdout.strip())
    return [work_dir / item["wav"] for item in payload]


def mix(captions: list[dict], clips: list[Path], out_path: Path) -> float:
    frames: list[bytes] = []
    total_frames = 0
    with wave.open(str(clips[0]), "rb") as probe:
        rate = probe.getframerate()
        width = probe.getsampwidth()
        channels = probe.getnchannels()
    if rate != SAMPLE_RATE or width != 2 or channels != 1:
        raise SystemExit(
            f"Unexpected speech format (rate={rate}, width={width}, channels={channels})."
        )

    for item, clip in zip(captions, clips):
        with wave.open(str(clip), "rb") as handle:
            payload = handle.readframes(handle.getnframes())
        offset = int(item["startMs"] * SAMPLE_RATE / 1000)
        if offset > len(frames):
            frames.extend([b"\x00\x00"] * (offset - len(frames)))
        frames.append(payload)
        total_frames = max(total_frames, offset + len(payload) // 2)

    tail = int(SAMPLE_RATE * 0.6)
    frames.extend([b"\x00\x00"] * tail)
    total_frames += tail

    with wave.open(str(out_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        for frame in frames:
            out.writeframesraw(frame)
    return total_frames / SAMPLE_RATE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recording",
        default="demo/.recording",
        help="Directory written by demo/record-demo.cjs.",
    )
    args = parser.parse_args()

    recording_dir = Path(args.recording)
    manifest_path = recording_dir / "captions.json"
    if not manifest_path.exists():
        print(f"Missing {manifest_path}. Run demo/record-demo.cjs first.", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captions = manifest.get("captions") or []
    if not captions:
        print("The caption track is empty.", file=sys.stderr)
        return 2

    srt_path, vtt_path = write_caption_files(captions, recording_dir)
    print(f"wrote {srt_path}")
    print(f"wrote {vtt_path}")

    work_dir = recording_dir / "tts"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        clips = synthesize(captions, work_dir)
    except SystemExit as exc:
        print(f"Narration unavailable: {exc}", file=sys.stderr)
        return 3

    narration_path = recording_dir / "narration.wav"
    duration = mix(captions, clips, narration_path)
    print(f"wrote {narration_path} ({duration:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
