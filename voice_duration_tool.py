#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice Duration Tool
===================

This command-line tool is designed for single-speaker audio files and estimates
the total duration of "effective vocalization" by detecting non-silent regions
with a simple loudness-threshold MVP approach.

Applicable scope:
- Single-person voice source audio
- Threshold-based voiced-duration estimation from digital audio
- Includes non-linguistic vocal sounds such as laughter, gasps, sighs,
  fillers, crying, and similar expressive human vocalizations, as long as
  they are loud enough to pass the configured threshold

Important note about dBFS:
- The silence threshold in this tool uses dBFS, which is a digital-audio
  relative loudness scale.
- dBFS is NOT the same thing as real-world sound pressure level in dB.
- In other words, the default `-40 dBFS` means "40 dB below full scale in the
  digital signal", not "40 decibels in the physical world".

Default behavior:
- The tool uses `pydub.silence.detect_nonsilent`.
- The default silence threshold is `-40 dBFS`.
- This is a practical MVP setting and may need adjustment for different
  recording environments, background noise levels, and microphone gain.

Examples:
- Single file:
    python voice_duration_tool.py input.wav --outdir ./output
- Directory mode:
    python voice_duration_tool.py ./audios --outdir ./output --recursive
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.silence import detect_nonsilent
from pydub.utils import which


SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "统计单人声源音频中的有效发声总时长。"
            "基于 dBFS 阈值检测非静音区间，并导出 CSV/JSON 明细。"
        )
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="输入音频文件或目录路径。支持 wav、mp3、m4a。",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("output"),
        help="输出目录，默认: ./output",
    )
    parser.add_argument(
        "--silence-thresh",
        type=float,
        default=-40.0,
        help="静音阈值，单位 dBFS，默认: -40",
    )
    parser.add_argument(
        "--min-silence-len",
        type=int,
        default=400,
        help="最短静音长度，单位毫秒，默认: 400",
    )
    parser.add_argument(
        "--seek-step",
        type=int,
        default=1,
        help="扫描步长，单位毫秒，默认: 1",
    )
    parser.add_argument(
        "--keep-silence",
        type=int,
        default=0,
        help="对每个片段两侧保留的静音长度，单位毫秒，默认: 0",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="当输入为目录时，递归扫描目录下所有支持的音频文件。",
    )
    return parser.parse_args()


def ensure_ffmpeg_available() -> None:
    if which("ffmpeg") or which("ffprobe"):
        return
    raise RuntimeError(
        "未检测到 ffmpeg/ffprobe。pydub 处理 mp3、m4a 等格式通常依赖 ffmpeg。"
        "请先安装 ffmpeg，并确保其可执行文件已加入系统 PATH。"
    )


def validate_audio_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"输入路径不是文件: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的音频格式: {path.suffix}。仅支持: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )


def load_audio(file_path: Path) -> AudioSegment:
    validate_audio_file(file_path)
    try:
        return AudioSegment.from_file(file_path)
    except CouldntDecodeError as exc:
        raise RuntimeError(
            f"无法解码音频文件: {file_path}。"
            "请确认文件格式正确，且已安装并配置 ffmpeg。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"读取音频失败: {file_path}，错误: {exc}") from exc


def expand_segments_with_keep_silence(
    segments: Sequence[Sequence[int]],
    keep_silence: int,
    audio_duration_ms: int,
) -> List[List[int]]:
    expanded: List[List[int]] = []
    for segment in segments:
        start_ms, end_ms = int(segment[0]), int(segment[1])
        start_ms = max(0, start_ms - keep_silence)
        end_ms = min(audio_duration_ms, end_ms + keep_silence)
        expanded.append([start_ms, end_ms])
    return expanded


def round_seconds(value_ms: int) -> float:
    return round(value_ms / 1000.0, 3)


def build_segment_rows(segments: Sequence[Sequence[int]]) -> List[dict]:
    rows: List[dict] = []
    for index, segment in enumerate(segments, start=1):
        start_ms, end_ms = int(segment[0]), int(segment[1])
        duration_ms = max(0, end_ms - start_ms)
        rows.append(
            {
                "segment_id": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms,
                "start_seconds": round_seconds(start_ms),
                "end_seconds": round_seconds(end_ms),
                "duration_seconds": round_seconds(duration_ms),
            }
        )
    return rows


def write_csv(rows: Sequence[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "segment_id",
        "start_ms",
        "end_ms",
        "duration_ms",
        "start_seconds",
        "end_seconds",
        "duration_seconds",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as jsonfile:
        json.dump(payload, jsonfile, ensure_ascii=False, indent=2)


def write_batch_summary(rows: Sequence[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "file_path",
        "audio_duration_seconds",
        "segment_count",
        "total_voiced_seconds",
        "voiced_ratio",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def collect_audio_files(input_path: Path, recursive: bool) -> List[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在: {input_path}")

    if input_path.is_file():
        validate_audio_file(input_path)
        return [input_path]

    if not input_path.is_dir():
        raise ValueError(f"输入路径既不是文件也不是目录: {input_path}")

    pattern_iter: Iterable[Path]
    if recursive:
        pattern_iter = input_path.rglob("*")
    else:
        pattern_iter = input_path.glob("*")

    files = sorted(
        p for p in pattern_iter if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        raise FileNotFoundError(
            f"目录中未找到支持的音频文件: {input_path}。"
            f"支持格式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return files


def safe_stem(path: Path) -> str:
    return path.stem or "audio"


def build_output_paths(outdir: Path, input_file: Path) -> tuple[Path, Path]:
    base_name = safe_stem(input_file)
    csv_path = outdir / f"{base_name}_segments.csv"
    json_path = outdir / f"{base_name}_segments.json"
    return csv_path, json_path


def analyze_audio(
    file_path: Path,
    outdir: Path,
    silence_thresh: float,
    min_silence_len: int,
    seek_step: int,
    keep_silence: int,
) -> dict:
    audio = load_audio(file_path)
    audio_duration_ms = len(audio)

    raw_segments = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        seek_step=seek_step,
    )
    expanded_segments = expand_segments_with_keep_silence(
        raw_segments,
        keep_silence=keep_silence,
        audio_duration_ms=audio_duration_ms,
    )
    segment_rows = build_segment_rows(expanded_segments)

    total_voiced_ms = sum(row["duration_ms"] for row in segment_rows)
    audio_duration_seconds = round_seconds(audio_duration_ms)
    total_voiced_seconds = round_seconds(total_voiced_ms)
    voiced_ratio = round(
        (total_voiced_ms / audio_duration_ms) if audio_duration_ms > 0 else 0.0,
        4,
    )

    payload = {
        "input_file": str(file_path.resolve()),
        "audio_duration_ms": audio_duration_ms,
        "audio_duration_seconds": audio_duration_seconds,
        "parameters": {
            "silence_thresh_dbfs": silence_thresh,
            "min_silence_len_ms": min_silence_len,
            "seek_step_ms": seek_step,
            "keep_silence_ms": keep_silence,
        },
        "summary": {
            "segment_count": len(segment_rows),
            "total_voiced_ms": total_voiced_ms,
            "total_voiced_seconds": total_voiced_seconds,
            "voiced_ratio": voiced_ratio,
        },
        "segments": segment_rows,
    }

    csv_path, json_path = build_output_paths(outdir, file_path)
    write_csv(segment_rows, csv_path)
    write_json(payload, json_path)

    return {
        "file_name": file_path.name,
        "file_path": str(file_path.resolve()),
        "audio_duration_ms": audio_duration_ms,
        "audio_duration_seconds": audio_duration_seconds,
        "segment_count": len(segment_rows),
        "total_voiced_ms": total_voiced_ms,
        "total_voiced_seconds": total_voiced_seconds,
        "voiced_ratio": voiced_ratio,
        "csv_path": str(csv_path.resolve()),
        "json_path": str(json_path.resolve()),
        "payload": payload,
    }


def print_summary(result: dict) -> None:
    print(f"文件名: {result['file_name']}")
    print(f"音频总时长: {result['audio_duration_seconds']:.3f} 秒")
    print(f"检测到的有效发声片段数: {result['segment_count']}")
    print(f"有效发声总时长: {result['total_voiced_seconds']:.3f} 秒")
    print(f"有效发声占比: {result['voiced_ratio']:.4f}")
    print(f"CSV 明细: {result['csv_path']}")
    print(f"JSON 明细: {result['json_path']}")
    print("-" * 60)


def main() -> int:
    args = parse_args()

    if args.min_silence_len < 0:
        print("错误: --min-silence-len 不能小于 0。", file=sys.stderr)
        return 2
    if args.seek_step <= 0:
        print("错误: --seek-step 必须大于 0。", file=sys.stderr)
        return 2
    if args.keep_silence < 0:
        print("错误: --keep-silence 不能小于 0。", file=sys.stderr)
        return 2

    try:
        ensure_ffmpeg_available()
        audio_files = collect_audio_files(args.input_path, args.recursive)
        args.outdir.mkdir(parents=True, exist_ok=True)

        batch_rows: List[dict] = []
        for audio_file in audio_files:
            result = analyze_audio(
                file_path=audio_file,
                outdir=args.outdir,
                silence_thresh=args.silence_thresh,
                min_silence_len=args.min_silence_len,
                seek_step=args.seek_step,
                keep_silence=args.keep_silence,
            )
            print_summary(result)
            batch_rows.append(
                {
                    "file_name": result["file_name"],
                    "file_path": result["file_path"],
                    "audio_duration_seconds": f"{result['audio_duration_seconds']:.3f}",
                    "segment_count": result["segment_count"],
                    "total_voiced_seconds": f"{result['total_voiced_seconds']:.3f}",
                    "voiced_ratio": f"{result['voiced_ratio']:.4f}",
                }
            )

        if len(batch_rows) > 1 or args.input_path.is_dir():
            batch_summary_path = args.outdir / "batch_summary.csv"
            write_batch_summary(batch_rows, batch_summary_path)
            print(f"批量汇总文件: {batch_summary_path.resolve()}")

        return 0

    except FileNotFoundError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"未预期错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
