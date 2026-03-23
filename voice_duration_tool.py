#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice Duration Tool

默认面向非技术用户：
- 把待统计的音频/视频放进 input/
- 运行脚本后自动扫描 input/
- 输出写到 output/
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


SUPPORTED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".wma",
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".m4v",
}

DEFAULT_INPUT_DIR = Path("input")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_SUMMARY_FILENAME = "all_files_summary.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "统计单人音频/视频文件中的有效发声总时长。"
            "默认直接扫描 input 文件夹，并把结果输出到 output 文件夹。"
        )
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="输入的音频/视频文件或文件夹。默认: ./input",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
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
        help="每个片段两侧额外保留的静音时长，单位毫秒，默认: 0",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="递归扫描输入目录中的子文件夹，默认开启",
    )
    return parser.parse_args()


def ensure_runtime_dirs(outdir: Path) -> None:
    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)


def ensure_ffmpeg_available() -> None:
    if which("ffmpeg") and which("ffprobe"):
        return
    raise RuntimeError(
        "未检测到 ffmpeg/ffprobe。处理 mp3、m4a、mp4、mov 等格式通常依赖 ffmpeg。"
        "请先安装 ffmpeg，并确保 ffmpeg 和 ffprobe 已加入系统 PATH。"
    )


def validate_media_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"输入路径不是文件: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的文件格式: {path.suffix}。支持格式: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )


def load_audio(file_path: Path) -> AudioSegment:
    validate_media_file(file_path)
    try:
        return AudioSegment.from_file(file_path)
    except CouldntDecodeError as exc:
        raise RuntimeError(
            f"无法解码文件: {file_path}。请确认文件未损坏，且 ffmpeg 已正确安装。"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"读取文件失败: {file_path}，错误: {exc}") from exc


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
        "file_type",
        "file_path",
        "audio_duration_seconds",
        "segment_count",
        "total_voiced_seconds",
        "voiced_ratio",
        "csv_path",
        "json_path",
        "status",
        "error_message",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def collect_media_files(input_path: Path, recursive: bool) -> List[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在: {input_path}")

    if input_path.is_file():
        validate_media_file(input_path)
        return [input_path]

    if not input_path.is_dir():
        raise ValueError(f"输入路径既不是文件也不是文件夹: {input_path}")

    pattern_iter: Iterable[Path]
    if recursive:
        pattern_iter = input_path.rglob("*")
    else:
        pattern_iter = input_path.glob("*")

    return sorted(
        p for p in pattern_iter if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def safe_stem(path: Path) -> str:
    return path.stem or "media"


def build_output_paths(outdir: Path, input_file: Path) -> tuple[Path, Path]:
    base_name = safe_stem(input_file)
    csv_path = outdir / f"{base_name}_segments.csv"
    json_path = outdir / f"{base_name}_segments.json"
    return csv_path, json_path


def format_batch_row(result: dict) -> dict:
    return {
        "file_name": result["file_name"],
        "file_type": result["file_type"],
        "file_path": result["file_path"],
        "audio_duration_seconds": f"{result['audio_duration_seconds']:.3f}",
        "segment_count": result["segment_count"],
        "total_voiced_seconds": f"{result['total_voiced_seconds']:.3f}",
        "voiced_ratio": f"{result['voiced_ratio']:.4f}",
        "csv_path": result["csv_path"],
        "json_path": result["json_path"],
        "status": result["status"],
        "error_message": result["error_message"],
    }


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
        "file_name": file_path.name,
        "file_type": file_path.suffix.lower().lstrip("."),
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
        "file_type": file_path.suffix.lower().lstrip("."),
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
        "status": "success",
        "error_message": "",
    }


def build_failure_result(file_path: Path, error_message: str) -> dict:
    return {
        "file_name": file_path.name,
        "file_type": file_path.suffix.lower().lstrip("."),
        "file_path": str(file_path.resolve()),
        "audio_duration_ms": 0,
        "audio_duration_seconds": 0.0,
        "segment_count": 0,
        "total_voiced_ms": 0,
        "total_voiced_seconds": 0.0,
        "voiced_ratio": 0.0,
        "csv_path": "",
        "json_path": "",
        "payload": None,
        "status": "failed",
        "error_message": error_message,
    }


def print_summary(result: dict) -> None:
    print(f"文件名: {result['file_name']}")
    print(f"文件类型: {result['file_type']}")
    print(f"总时长: {result['audio_duration_seconds']:.3f} 秒")
    print(f"有效发声片段数: {result['segment_count']}")
    print(f"有效发声总时长: {result['total_voiced_seconds']:.3f} 秒")
    print(f"有效发声占比: {result['voiced_ratio']:.4f}")
    print(f"CSV 明细: {result['csv_path']}")
    print(f"JSON 明细: {result['json_path']}")
    print("-" * 60)


def print_failure(result: dict) -> None:
    print(f"文件名: {result['file_name']}")
    print("处理状态: 失败")
    print(f"错误信息: {result['error_message']}")
    print("-" * 60)


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_stdio()
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
        ensure_runtime_dirs(args.outdir)
        ensure_ffmpeg_available()
        media_files = collect_media_files(args.input_path, args.recursive)
        batch_summary_path = args.outdir / DEFAULT_SUMMARY_FILENAME

        if not media_files:
            write_batch_summary([], batch_summary_path)
            print(f"未在 {args.input_path.resolve()} 中发现可处理的音频或视频文件。")
            print(f"已生成空白总表: {batch_summary_path.resolve()}")
            return 0

        batch_rows: List[dict] = []
        failure_count = 0

        print(f"开始处理，共发现 {len(media_files)} 个文件。")
        print(f"输入目录: {args.input_path.resolve()}")
        print(f"输出目录: {args.outdir.resolve()}")
        print("=" * 60)

        for media_file in media_files:
            try:
                result = analyze_audio(
                    file_path=media_file,
                    outdir=args.outdir,
                    silence_thresh=args.silence_thresh,
                    min_silence_len=args.min_silence_len,
                    seek_step=args.seek_step,
                    keep_silence=args.keep_silence,
                )
                print_summary(result)
            except Exception as exc:
                result = build_failure_result(media_file, str(exc))
                failure_count += 1
                print_failure(result)

            batch_rows.append(format_batch_row(result))

        write_batch_summary(batch_rows, batch_summary_path)
        print(f"总表已生成: {batch_summary_path.resolve()}")
        print(f"成功: {len(batch_rows) - failure_count} 个，失败: {failure_count} 个。")
        return 1 if failure_count > 0 else 0

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
