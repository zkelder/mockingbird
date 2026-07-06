"""Convert already-saved image media into small grayscale frame planes."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import struct
import subprocess
import zlib

from mockingbird.motion.scoring import FramePlane

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class SavedMediaFrameDecodeError(ValueError):
    """Raised when saved image media cannot become a motion frame plane."""


@dataclass(frozen=True)
class SavedMediaFrame:
    width: int
    height: int
    frame: FramePlane


def load_saved_image_frame_plane(
    path: Path,
    *,
    content_type: str,
    max_dimension: int = 32,
) -> SavedMediaFrame:
    """Load an already-local image as a bounded grayscale frame plane."""

    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise SavedMediaFrameDecodeError("unsupported_image_content_type")
    if max_dimension < 2:
        raise SavedMediaFrameDecodeError("invalid_frame_size")
    if not path.is_file():
        raise SavedMediaFrameDecodeError("missing_media_file")

    if content_type == "image/png":
        return _load_png_frame(path, max_dimension=max_dimension)
    return _load_with_optional_pillow(
        path,
        content_type=content_type,
        max_dimension=max_dimension,
    )


def load_image_frame_plane_bytes(
    data: bytes,
    *,
    content_type: str,
    max_dimension: int = 32,
) -> SavedMediaFrame:
    """Load live image bytes as a bounded grayscale frame plane."""

    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise SavedMediaFrameDecodeError("unsupported_image_content_type")
    if max_dimension < 2:
        raise SavedMediaFrameDecodeError("invalid_frame_size")
    if not data:
        raise SavedMediaFrameDecodeError("missing_media_file")

    if content_type == "image/png":
        return _load_png_frame_data(data, max_dimension=max_dimension)
    return _load_bytes_with_optional_pillow(
        data,
        content_type=content_type,
        max_dimension=max_dimension,
    )


def _load_png_frame(path: Path, *, max_dimension: int) -> SavedMediaFrame:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SavedMediaFrameDecodeError("missing_media_file") from error
    return _load_png_frame_data(data, max_dimension=max_dimension)


def _load_png_frame_data(data: bytes, *, max_dimension: int) -> SavedMediaFrame:
    if not data.startswith(PNG_SIGNATURE):
        raise SavedMediaFrameDecodeError("invalid_png")

    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    interlace_method = 0
    idat_parts: list[bytes] = []
    offset = len(PNG_SIGNATURE)

    while offset + 8 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        chunk_data = data[chunk_data_start:chunk_data_end]
        offset = chunk_data_end + 4

        if chunk_type == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression_method,
                _filter_method,
                interlace_method,
            ) = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None:
        raise SavedMediaFrameDecodeError("invalid_png")
    if width < 1 or height < 1:
        raise SavedMediaFrameDecodeError("invalid_png_dimensions")
    if bit_depth != 8 or color_type not in {0, 2, 6} or interlace_method != 0:
        raise SavedMediaFrameDecodeError("unsupported_png_format")

    channels = {0: 1, 2: 3, 6: 4}[color_type]
    row_stride = width * channels
    try:
        raw_rows = zlib.decompress(b"".join(idat_parts))
    except zlib.error as error:
        raise SavedMediaFrameDecodeError("invalid_png_data") from error
    expected_size = height * (row_stride + 1)
    if len(raw_rows) < expected_size:
        raise SavedMediaFrameDecodeError("invalid_png_data")

    rows: list[list[int]] = []
    previous = [0] * row_stride
    cursor = 0
    for _row_index in range(height):
        filter_type = raw_rows[cursor]
        cursor += 1
        encoded = list(raw_rows[cursor : cursor + row_stride])
        cursor += row_stride
        decoded = _unfilter_png_row(
            encoded,
            previous,
            filter_type=filter_type,
            bytes_per_pixel=channels,
        )
        rows.append(_png_row_to_grayscale(decoded, color_type=color_type, width=width))
        previous = decoded

    frame = _downsample(rows, max_dimension=max_dimension)
    return SavedMediaFrame(width=width, height=height, frame=frame)


def _load_with_optional_pillow(
    path: Path,
    *,
    content_type: str,
    max_dimension: int,
) -> SavedMediaFrame:
    try:
        from PIL import Image
    except ImportError as error:
        return _load_with_ffmpeg(path, max_dimension=max_dimension, cause=error)

    try:
        with Image.open(path) as image:
            if image.format and content_type == "image/webp" and image.format.upper() != "WEBP":
                raise SavedMediaFrameDecodeError("invalid_image")
            gray = image.convert("L")
            width, height = gray.size
            if width < 1 or height < 1:
                raise SavedMediaFrameDecodeError("invalid_image_dimensions")
            out_width, out_height = _scaled_dimensions(
                width,
                height,
                max_dimension=max_dimension,
            )
            resized = gray.resize((out_width, out_height))
            pixels = list(resized.getdata())
    except SavedMediaFrameDecodeError:
        raise
    except OSError as error:
        return _load_with_ffmpeg(path, max_dimension=max_dimension, cause=error)

    frame = [
        pixels[row_index * out_width : (row_index + 1) * out_width]
        for row_index in range(out_height)
    ]
    return SavedMediaFrame(width=width, height=height, frame=frame)


def _load_bytes_with_optional_pillow(
    data: bytes,
    *,
    content_type: str,
    max_dimension: int,
) -> SavedMediaFrame:
    try:
        from PIL import Image
    except ImportError as error:
        return _load_bytes_with_ffmpeg(data, max_dimension=max_dimension, cause=error)

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format and content_type == "image/webp" and image.format.upper() != "WEBP":
                raise SavedMediaFrameDecodeError("invalid_image")
            gray = image.convert("L")
            width, height = gray.size
            if width < 1 or height < 1:
                raise SavedMediaFrameDecodeError("invalid_image_dimensions")
            out_width, out_height = _scaled_dimensions(
                width,
                height,
                max_dimension=max_dimension,
            )
            resized = gray.resize((out_width, out_height))
            pixels = list(resized.getdata())
    except SavedMediaFrameDecodeError:
        raise
    except OSError as error:
        return _load_bytes_with_ffmpeg(data, max_dimension=max_dimension, cause=error)

    frame = [
        pixels[row_index * out_width : (row_index + 1) * out_width]
        for row_index in range(out_height)
    ]
    return SavedMediaFrame(width=width, height=height, frame=frame)


def _load_with_ffmpeg(
    path: Path,
    *,
    max_dimension: int,
    cause: BaseException | None = None,
) -> SavedMediaFrame:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        (
            f"scale='min(iw,{max_dimension})':'min(ih,{max_dimension})':"
            "force_original_aspect_ratio=decrease,format=gray"
        ),
        "-f",
        "image2pipe",
        "-vcodec",
        "pgm",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except FileNotFoundError as error:
        raise SavedMediaFrameDecodeError("image_decoder_unavailable") from (cause or error)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise SavedMediaFrameDecodeError("image_decode_failed") from (cause or error)

    try:
        return _load_pgm_frame(completed.stdout)
    except SavedMediaFrameDecodeError as error:
        raise SavedMediaFrameDecodeError("image_decode_failed") from error


def _load_bytes_with_ffmpeg(
    data: bytes,
    *,
    max_dimension: int,
    cause: BaseException | None = None,
) -> SavedMediaFrame:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-frames:v",
        "1",
        "-vf",
        (
            f"scale='min(iw,{max_dimension})':'min(ih,{max_dimension})':"
            "force_original_aspect_ratio=decrease,format=gray"
        ),
        "-f",
        "image2pipe",
        "-vcodec",
        "pgm",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            input=data,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except FileNotFoundError as error:
        raise SavedMediaFrameDecodeError("image_decoder_unavailable") from (cause or error)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise SavedMediaFrameDecodeError("image_decode_failed") from (cause or error)

    try:
        return _load_pgm_frame(completed.stdout)
    except SavedMediaFrameDecodeError as error:
        raise SavedMediaFrameDecodeError("image_decode_failed") from error


def _load_pgm_frame(data: bytes) -> SavedMediaFrame:
    tokens: list[bytes] = []
    index = 0
    while len(tokens) < 4:
        index = _skip_pgm_whitespace_and_comments(data, index)
        if index >= len(data):
            raise SavedMediaFrameDecodeError("invalid_pgm")
        start = index
        while index < len(data) and data[index] not in b" \t\r\n\f\v":
            index += 1
        tokens.append(data[start:index])

    if tokens[0] != b"P5":
        raise SavedMediaFrameDecodeError("invalid_pgm")
    try:
        width = int(tokens[1])
        height = int(tokens[2])
        max_value = int(tokens[3])
    except ValueError as error:
        raise SavedMediaFrameDecodeError("invalid_pgm") from error
    if width < 1 or height < 1 or max_value != 255:
        raise SavedMediaFrameDecodeError("invalid_pgm")

    if index < len(data) and data[index] in b" \t\r\n\f\v":
        index += 1
    pixel_count = width * height
    pixels = data[index : index + pixel_count]
    if len(pixels) < pixel_count:
        raise SavedMediaFrameDecodeError("invalid_pgm")

    frame = [
        list(pixels[row_index * width : (row_index + 1) * width])
        for row_index in range(height)
    ]
    return SavedMediaFrame(width=width, height=height, frame=frame)


def _skip_pgm_whitespace_and_comments(data: bytes, index: int) -> int:
    while index < len(data):
        if data[index] in b" \t\r\n\f\v":
            index += 1
            continue
        if data[index : index + 1] == b"#":
            index = data.find(b"\n", index)
            if index < 0:
                return len(data)
            index += 1
            continue
        break
    return index


def _unfilter_png_row(
    encoded: list[int],
    previous: list[int],
    *,
    filter_type: int,
    bytes_per_pixel: int,
) -> list[int]:
    decoded: list[int] = []
    for index, value in enumerate(encoded):
        left = decoded[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = _paeth(left, up, up_left)
        else:
            raise SavedMediaFrameDecodeError("unsupported_png_filter")
        decoded.append((value + predictor) & 0xFF)
    return decoded


def _png_row_to_grayscale(
    row: list[int],
    *,
    color_type: int,
    width: int,
) -> list[int]:
    if color_type == 0:
        return row[:width]

    channels = 3 if color_type == 2 else 4
    grayscale: list[int] = []
    for index in range(width):
        offset = index * channels
        red = row[offset]
        green = row[offset + 1]
        blue = row[offset + 2]
        grayscale.append(round(0.299 * red + 0.587 * green + 0.114 * blue))
    return grayscale


def _downsample(rows: list[list[int]], *, max_dimension: int) -> FramePlane:
    height = len(rows)
    width = len(rows[0])
    out_width, out_height = _scaled_dimensions(width, height, max_dimension=max_dimension)
    if out_width == width and out_height == height:
        return rows

    frame: list[list[int]] = []
    for out_y in range(out_height):
        src_y = min(height - 1, int(out_y * height / out_height))
        source_row = rows[src_y]
        frame.append(
            [
                source_row[min(width - 1, int(out_x * width / out_width))]
                for out_x in range(out_width)
            ]
        )
    return frame


def _scaled_dimensions(width: int, height: int, *, max_dimension: int) -> tuple[int, int]:
    largest = max(width, height)
    if largest <= max_dimension:
        return width, height
    scale = largest / max_dimension
    return max(1, round(width / scale)), max(1, round(height / scale))


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left
