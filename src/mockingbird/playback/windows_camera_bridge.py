"""Optional Windows DirectShow webcam playback bridge helpers."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
import json
import os
from pathlib import PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys

from mockingbird.playback.frame_capture import read_one_jpeg_frame
from mockingbird.playback.rtsp_bridge import MJPEG_BOUNDARY, iter_multipart_mjpeg

WINDOWS_DSHOW_STREAM_TYPE = "windows_dshow"
DEFAULT_WINDOWS_FFMPEG_BINARY = "ffmpeg"
WINDOWS_POWERSHELL_BINARY = "powershell.exe"
WINDOWS_CAMERA_CONTROLS_LAUNCH_TIMEOUT_SECONDS = 10.0

_DANGEROUS_NAME_PATTERN = re.compile(r"[\x00\r\n]")
_DANGEROUS_EXECUTABLE_PATH_PATTERN = re.compile(r'[\x00\r\n"]')
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_WSL_MOUNT_PATH_PATTERN = re.compile(r"^/mnt/([A-Za-z])/(.+)$")
_WINDOWS_POWERSHELL_SUFFIX = (
    "windows/system32/windowspowershell/v1.0/powershell.exe"
)
_VIDEO_DEVICE_PATTERN = re.compile(r'"([^"]+)"\s+\(video\)', re.IGNORECASE)


def normalize_windows_ffmpeg_binary(ffmpeg_binary_path: str | None) -> str:
    return (
        (ffmpeg_binary_path or DEFAULT_WINDOWS_FFMPEG_BINARY).strip()
        or DEFAULT_WINDOWS_FFMPEG_BINARY
    )


def normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def validate_windows_camera_name(name: str | None) -> bool:
    normalized = (name or "").strip()
    return bool(normalized) and not _DANGEROUS_NAME_PATTERN.search(normalized)


def is_windows_ffmpeg_binary(ffmpeg_binary_path: str | None) -> bool:
    normalized = normalize_windows_ffmpeg_binary(ffmpeg_binary_path).lower().replace("\\", "/")
    return normalized.endswith(".exe") or normalized.startswith("/mnt/c/")


def is_windows_ffmpeg_available(ffmpeg_binary_path: str | None = None) -> bool:
    normalized = normalize_windows_ffmpeg_binary(ffmpeg_binary_path)
    if is_windows_ffmpeg_binary(normalized):
        return True
    return shutil.which(normalized) is not None


def windows_camera_status(
    *,
    camera_name: str | None,
    ffmpeg_binary_path: str | None = None,
    platform_name: str = sys.platform,
    ffmpeg_available: bool | None = None,
) -> str:
    if not validate_windows_camera_name(camera_name):
        return "camera_name_missing"
    if platform_name.startswith("linux") and not is_windows_ffmpeg_binary(ffmpeg_binary_path):
        return "unsupported_host"
    if is_windows_ffmpeg_binary(ffmpeg_binary_path):
        return "available"
    if ffmpeg_available is None:
        ffmpeg_available = is_windows_ffmpeg_available(ffmpeg_binary_path)
    if not ffmpeg_available:
        return "ffmpeg_missing"
    return "available"


WhichFactory = Callable[[str], str | None]
PathIsFile = Callable[[str], bool]
HostEnvironment = Mapping[str, str]


def _require_interactive_windows_host(
    platform_name: str,
    environment: HostEnvironment,
) -> None:
    if platform_name.startswith("win"):
        return
    if platform_name.startswith("linux") and any(
        (environment.get(name) or "").strip()
        for name in ("WSL_INTEROP", "WSL_DISTRO_NAME")
    ):
        return
    raise ValueError("unsupported_platform")


def _is_explicit_executable_path(value: str) -> bool:
    return (
        bool(_WINDOWS_DRIVE_PATH_PATTERN.match(value))
        or "/" in value
        or "\\" in value
    )


def _resolve_host_executable(
    binary: str,
    *,
    which: WhichFactory,
    path_is_file: PathIsFile,
) -> str:
    if _DANGEROUS_EXECUTABLE_PATH_PATTERN.search(binary):
        raise ValueError("invalid_windows_executable_path")
    resolved = binary if _is_explicit_executable_path(binary) else which(binary)
    if not resolved or not path_is_file(resolved):
        raise FileNotFoundError("windows_executable_missing")
    return resolved


def _wsl_mount_path_to_windows(path: str) -> str:
    match = _WSL_MOUNT_PATH_PATTERN.fullmatch(path.replace("\\", "/"))
    if match is None:
        raise ValueError("unsupported_platform")
    drive, remainder = match.groups()
    windows_remainder = remainder.replace("/", "\\")
    return f"{drive.upper()}:\\{windows_remainder}"


def _windows_drive_path_to_wsl_mount(path: str) -> str:
    if not _WINDOWS_DRIVE_PATH_PATTERN.match(path):
        raise ValueError("invalid_windows_executable_path")
    drive = path[0].lower()
    remainder = path[3:].replace("\\", "/")
    return f"/mnt/{drive}/{remainder}"


def windows_ffmpeg_invocation_binary(
    ffmpeg_binary_path: str | None,
    *,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
) -> str:
    """Return the executable spelling required by the current process host."""

    configured = normalize_windows_ffmpeg_binary(ffmpeg_binary_path)
    host_platform = platform_name or sys.platform
    host_environment = os.environ if environment is None else environment
    if (
        host_platform.startswith("linux")
        and _WINDOWS_DRIVE_PATH_PATTERN.match(configured)
        and any(
            (host_environment.get(name) or "").strip()
            for name in ("WSL_INTEROP", "WSL_DISTRO_NAME")
        )
    ):
        return _windows_drive_path_to_wsl_mount(configured)
    return configured


def resolve_windows_ffmpeg_for_controls(
    ffmpeg_binary_path: str | None,
    *,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
    which: WhichFactory = shutil.which,
    path_is_file: PathIsFile = os.path.isfile,
) -> str:
    """Resolve one validated ffmpeg.exe path for the Windows desktop launcher."""

    host_platform = platform_name or sys.platform
    host_environment = os.environ if environment is None else environment
    _require_interactive_windows_host(host_platform, host_environment)

    configured = normalize_windows_ffmpeg_binary(ffmpeg_binary_path)
    host_binary = windows_ffmpeg_invocation_binary(
        configured,
        platform_name=host_platform,
        environment=host_environment,
    )
    resolved = _resolve_host_executable(
        host_binary,
        which=which,
        path_is_file=path_is_file,
    )
    if host_platform.startswith("win"):
        windows_path = PureWindowsPath(resolved)
        if (
            not _WINDOWS_DRIVE_PATH_PATTERN.match(resolved)
            or not windows_path.is_absolute()
            or windows_path.name.lower() != "ffmpeg.exe"
        ):
            raise ValueError("invalid_windows_executable_path")
        return resolved

    if PurePosixPath(resolved).name.lower() != "ffmpeg.exe":
        raise ValueError("unsupported_platform")
    return _wsl_mount_path_to_windows(resolved)


def resolve_windows_powershell_for_controls(
    *,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
    which: WhichFactory = shutil.which,
    path_is_file: PathIsFile = os.path.isfile,
) -> str:
    """Resolve Windows PowerShell as a host-invocable interactive launcher."""

    host_platform = platform_name or sys.platform
    host_environment = os.environ if environment is None else environment
    _require_interactive_windows_host(host_platform, host_environment)
    resolved = _resolve_host_executable(
        WINDOWS_POWERSHELL_BINARY,
        which=which,
        path_is_file=path_is_file,
    )
    if host_platform.startswith("linux"):
        _wsl_mount_path_to_windows(resolved)
        normalized_path = PurePosixPath(resolved).as_posix().lower()
        if not normalized_path.endswith(f"/{_WINDOWS_POWERSHELL_SUFFIX}"):
            raise ValueError("controls_unavailable")
    else:
        windows_path = PureWindowsPath(resolved)
        system_root = PureWindowsPath(
            host_environment.get("SystemRoot") or "C:\\Windows"
        )
        trusted_path = (
            system_root
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / WINDOWS_POWERSHELL_BINARY
        )
        if (
            not _WINDOWS_DRIVE_PATH_PATTERN.match(resolved)
            or str(windows_path).lower() != str(trusted_path).lower()
        ):
            raise ValueError("controls_unavailable")
    return resolved


def windows_camera_controls_status(
    *,
    camera_name: str | None,
    ffmpeg_binary_path: str | None = None,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
    which: WhichFactory = shutil.which,
    path_is_file: PathIsFile = os.path.isfile,
) -> str:
    """Report whether an interactive DirectShow property page can be launched."""

    if not validate_windows_camera_name(camera_name):
        return "camera_name_missing"
    try:
        resolve_windows_ffmpeg_for_controls(
            ffmpeg_binary_path,
            platform_name=platform_name,
            environment=environment,
            which=which,
            path_is_file=path_is_file,
        )
    except FileNotFoundError:
        return "ffmpeg_missing"
    except ValueError as error:
        return (
            "unsupported_platform"
            if str(error) == "unsupported_platform"
            else "controls_unavailable"
        )
    try:
        resolve_windows_powershell_for_controls(
            platform_name=platform_name,
            environment=environment,
            which=which,
            path_is_file=path_is_file,
        )
    except (FileNotFoundError, ValueError):
        return "controls_unavailable"
    return "available"


def build_windows_dshow_list_devices_command(
    *,
    ffmpeg_binary_path: str | None = None,
) -> list[str]:
    return [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]


def parse_windows_dshow_video_devices(output: str) -> list[str]:
    devices: list[str] = []
    for match in _VIDEO_DEVICE_PATTERN.finditer(output):
        name = match.group(1)
        if name not in devices:
            devices.append(name)
    return devices


RunFactory = Callable[..., subprocess.CompletedProcess[str]]


def list_windows_dshow_video_devices(
    *,
    ffmpeg_binary_path: str | None = None,
    timeout_seconds: float = 10.0,
    run_factory: RunFactory = subprocess.run,
) -> list[str]:
    """Return DirectShow video device names without opening a camera stream."""

    completed = run_factory(
        build_windows_dshow_list_devices_command(
            ffmpeg_binary_path=ffmpeg_binary_path,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    output = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    )
    return parse_windows_dshow_video_devices(output)


def build_windows_dshow_camera_controls_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
) -> list[str]:
    """Build the explicit DirectShow property-page command without a shell."""

    if not validate_windows_camera_name(camera_name):
        raise ValueError("invalid_windows_camera_name")
    return [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "dshow",
        "-show_video_device_dialog",
        "true",
        "-i",
        f"video={camera_name.strip()}",
        "-t",
        "0.2",
        "-f",
        "null",
        "NUL",
    ]


def build_windows_dshow_camera_controls_launcher_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
    which: WhichFactory = shutil.which,
    path_is_file: PathIsFile = os.path.isfile,
) -> list[str]:
    """Build a fixed PowerShell launcher with user values encoded only as data."""

    powershell_binary = resolve_windows_powershell_for_controls(
        platform_name=platform_name,
        environment=environment,
        which=which,
        path_is_file=path_is_file,
    )
    windows_ffmpeg_binary = resolve_windows_ffmpeg_for_controls(
        ffmpeg_binary_path,
        platform_name=platform_name,
        environment=environment,
        which=which,
        path_is_file=path_is_file,
    )
    ffmpeg_command = build_windows_dshow_camera_controls_command(
        camera_name,
        ffmpeg_binary_path=windows_ffmpeg_binary,
    )
    payload = base64.b64encode(
        json.dumps(
            {
                "file_path": ffmpeg_command[0],
                "argument_line": subprocess.list2cmdline(ffmpeg_command[1:]),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$payloadBytes = [Convert]::FromBase64String('{payload}')",
            "$payloadJson = [Text.Encoding]::UTF8.GetString($payloadBytes)",
            "$payload = $payloadJson | ConvertFrom-Json",
            (
                "$process = Start-Process -FilePath $payload.file_path "
                "-ArgumentList $payload.argument_line -WindowStyle Normal "
                "-PassThru -ErrorAction Stop"
            ),
            (
                "if ($null -eq $process -or $process.Id -le 0) "
                "{ throw 'camera_controls_process_not_started' }"
            ),
            "[Console]::Out.Write($process.Id)",
        ]
    )
    encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return [
        powershell_binary,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
        encoded_script,
    ]


def launch_windows_dshow_camera_controls(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    platform_name: str | None = None,
    environment: HostEnvironment | None = None,
    which: WhichFactory = shutil.which,
    path_is_file: PathIsFile = os.path.isfile,
    timeout_seconds: float = WINDOWS_CAMERA_CONTROLS_LAUNCH_TIMEOUT_SECONDS,
    run_factory: RunFactory = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Launch the driver controls without owning the dialog's lifetime."""

    return run_factory(
        build_windows_dshow_camera_controls_launcher_command(
            camera_name,
            ffmpeg_binary_path=ffmpeg_binary_path,
            platform_name=platform_name,
            environment=environment,
            which=which,
            path_is_file=path_is_file,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )


def build_windows_dshow_mjpeg_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    output_frame_rate: int = 5,
) -> list[str]:
    if not validate_windows_camera_name(camera_name):
        raise ValueError("invalid_windows_camera_name")
    command = [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-f",
        "dshow",
    ]
    normalized_video_size = normalize_optional_text(video_size)
    normalized_input_format = normalize_optional_text(input_format)
    normalized_framerate = normalize_optional_text(
        str(framerate) if framerate is not None else None
    )
    if normalized_input_format:
        command.extend(["-input_format", normalized_input_format])
    if normalized_video_size:
        command.extend(["-video_size", normalized_video_size])
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            f"video={camera_name.strip()}",
            "-an",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-r",
            str(output_frame_rate),
            "pipe:1",
        ]
    )
    return command


PopenFactory = Callable[..., subprocess.Popen[bytes]]


def start_windows_dshow_mjpeg_process(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_windows_dshow_mjpeg_command(
        camera_name,
        ffmpeg_binary_path=windows_ffmpeg_invocation_binary(ffmpeg_binary_path),
        input_format=input_format,
        video_size=video_size,
        framerate=framerate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def build_windows_dshow_frame_capture_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
) -> list[str]:
    if not validate_windows_camera_name(camera_name):
        raise ValueError("invalid_windows_camera_name")
    command = [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-f",
        "dshow",
    ]
    normalized_video_size = normalize_optional_text(video_size)
    normalized_input_format = normalize_optional_text(input_format)
    normalized_framerate = normalize_optional_text(
        str(framerate) if framerate is not None else None
    )
    if normalized_input_format:
        command.extend(["-input_format", normalized_input_format])
    if normalized_video_size:
        command.extend(["-video_size", normalized_video_size])
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            f"video={camera_name.strip()}",
            "-an",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
    )
    return command


def start_windows_dshow_frame_capture_process(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_windows_dshow_frame_capture_command(
        camera_name,
        ffmpeg_binary_path=windows_ffmpeg_invocation_binary(ffmpeg_binary_path),
        input_format=input_format,
        video_size=video_size,
        framerate=framerate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def capture_windows_dshow_frame(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> bytes:
    process = start_windows_dshow_frame_capture_process(
        camera_name,
        ffmpeg_binary_path=ffmpeg_binary_path,
        input_format=input_format,
        video_size=video_size,
        framerate=framerate,
        popen_factory=popen_factory,
    )
    return read_one_jpeg_frame(process)


__all__ = [
    "DEFAULT_WINDOWS_FFMPEG_BINARY",
    "MJPEG_BOUNDARY",
    "WINDOWS_CAMERA_CONTROLS_LAUNCH_TIMEOUT_SECONDS",
    "WINDOWS_DSHOW_STREAM_TYPE",
    "WINDOWS_POWERSHELL_BINARY",
    "build_windows_dshow_frame_capture_command",
    "build_windows_dshow_camera_controls_command",
    "build_windows_dshow_camera_controls_launcher_command",
    "build_windows_dshow_list_devices_command",
    "build_windows_dshow_mjpeg_command",
    "capture_windows_dshow_frame",
    "is_windows_ffmpeg_available",
    "is_windows_ffmpeg_binary",
    "iter_multipart_mjpeg",
    "launch_windows_dshow_camera_controls",
    "list_windows_dshow_video_devices",
    "normalize_windows_ffmpeg_binary",
    "parse_windows_dshow_video_devices",
    "resolve_windows_ffmpeg_for_controls",
    "resolve_windows_powershell_for_controls",
    "start_windows_dshow_frame_capture_process",
    "start_windows_dshow_mjpeg_process",
    "validate_windows_camera_name",
    "windows_camera_controls_status",
    "windows_camera_status",
]
