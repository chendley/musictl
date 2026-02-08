"""Audio file abstraction wrapping mutagen and ffprobe."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import mutagen
from mutagen.id3 import ID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis

SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wma", ".wav", ".aiff"}


@dataclass
class AudioInfo:
    """Parsed audio file metadata."""

    path: Path
    format: str = ""
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 0
    duration: float = 0.0
    bitrate: int = 0
    tags: dict[str, str] = field(default_factory=dict)
    has_id3v1: bool = False
    has_id3v2: bool = False
    error: str | None = None

    @property
    def is_hires(self) -> bool:
        return self.sample_rate > 48000

    @property
    def duration_str(self) -> str:
        minutes, seconds = divmod(int(self.duration), 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def sample_rate_str(self) -> str:
        if self.sample_rate >= 1000:
            return f"{self.sample_rate / 1000:.1f} kHz"
        return f"{self.sample_rate} Hz"


def read_audio(path: Path) -> AudioInfo:
    """Read audio file metadata using mutagen, with ffprobe fallback for stream info."""
    info = AudioInfo(path=path)

    try:
        mfile = mutagen.File(str(path))
    except Exception as e:
        info.error = str(e)
        return info

    if mfile is None:
        info.error = "Unsupported or unreadable audio format"
        return info

    # Determine format and extract tags
    if isinstance(mfile, MP3):
        info.format = "MP3"
        info.bitrate = mfile.info.bitrate
        info.sample_rate = mfile.info.sample_rate
        info.channels = mfile.info.channels
        info.duration = mfile.info.length

        # Check for ID3v1 and ID3v2
        try:
            id3 = ID3(str(path))
            info.has_id3v2 = True
            for key, val in id3.items():
                info.tags[key] = str(val)
        except Exception:
            pass

        # Check ID3v1 by reading raw bytes
        try:
            with open(path, "rb") as f:
                f.seek(-128, 2)
                if f.read(3) == b"TAG":
                    info.has_id3v1 = True
        except Exception:
            pass

    elif isinstance(mfile, FLAC):
        info.format = "FLAC"
        info.sample_rate = mfile.info.sample_rate
        info.bit_depth = mfile.info.bits_per_sample
        info.channels = mfile.info.channels
        info.duration = mfile.info.length
        for key, values in (mfile.tags or {}).items():
            info.tags[key] = values if isinstance(values, str) else "; ".join(values)

    elif isinstance(mfile, OggVorbis):
        info.format = "OGG"
        info.sample_rate = mfile.info.sample_rate
        info.channels = mfile.info.channels
        info.duration = mfile.info.length
        for key, values in mfile.tags.items():
            info.tags[key] = values[0] if len(values) == 1 else "; ".join(values)

    else:
        info.format = path.suffix.lstrip(".").upper()
        if hasattr(mfile.info, "sample_rate"):
            info.sample_rate = mfile.info.sample_rate
        if hasattr(mfile.info, "channels"):
            info.channels = mfile.info.channels
        if hasattr(mfile.info, "length"):
            info.duration = mfile.info.length
        if hasattr(mfile.info, "bits_per_sample"):
            info.bit_depth = mfile.info.bits_per_sample
        for key, val in (mfile.tags or {}).items():
            info.tags[str(key)] = str(val)

    # Use ffprobe for bit depth if not available from mutagen (e.g., MP3)
    if info.bit_depth == 0 and info.sample_rate == 0:
        _fill_from_ffprobe(info)

    return info


def _fill_from_ffprobe(info: AudioInfo) -> None:
    """Fill missing audio info from ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a:0",
                str(info.path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            return

        stream = streams[0]
        if not info.sample_rate:
            info.sample_rate = int(stream.get("sample_rate", 0))
        if not info.bit_depth:
            info.bit_depth = int(stream.get("bits_per_raw_sample", 0))
        if not info.channels:
            info.channels = int(stream.get("channels", 0))
        if not info.duration:
            info.duration = float(stream.get("duration", 0))
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
