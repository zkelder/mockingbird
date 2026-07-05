"""Request-scoped JPEG frame capture helpers for local camera bridges."""

from __future__ import annotations

from typing import BinaryIO
import subprocess


def read_one_jpeg_frame(
    process: subprocess.Popen[bytes],
    *,
    chunk_size: int = 64 * 1024,
    max_bytes: int = 10_000_000,
) -> bytes:
    stdout = process.stdout
    if stdout is None:
        _stop_process(process)
        raise ValueError("no_frame_captured")

    buffer = bytearray()
    try:
        while len(buffer) <= max_bytes:
            chunk = _read_stdout(stdout, chunk_size)
            if not chunk:
                break
            buffer.extend(chunk)
            frame = _extract_first_jpeg_frame(buffer)
            if frame is not None:
                return frame
    finally:
        _stop_process(process)

    raise ValueError("no_frame_captured")


def _read_stdout(stdout: BinaryIO, chunk_size: int) -> bytes:
    return stdout.read(chunk_size)


def _extract_first_jpeg_frame(buffer: bytearray) -> bytes | None:
    start = buffer.find(b"\xff\xd8")
    if start < 0:
        if len(buffer) > 1:
            del buffer[:-1]
        return None

    end = buffer.find(b"\xff\xd9", start + 2)
    if end < 0:
        if start > 0:
            del buffer[:start]
        return None

    return bytes(buffer[start : end + 2])


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


__all__ = ["read_one_jpeg_frame"]
