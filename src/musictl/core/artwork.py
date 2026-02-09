"""Album art reading, writing, and extraction across audio formats."""

import base64
from dataclasses import dataclass
from pathlib import Path

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, ID3NoHeaderError, APIC, PictureType
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus


@dataclass
class ArtworkInfo:
    """Album art metadata."""

    mime_type: str
    size_bytes: int
    picture_type: str
    width: int | None = None
    height: int | None = None


_PICTURE_TYPES = {
    0: "Other",
    3: "Front Cover",
    4: "Back Cover",
    5: "Leaflet",
    6: "Media",
    7: "Lead Artist",
    8: "Artist",
}


def _picture_type_name(type_id: int) -> str:
    return _PICTURE_TYPES.get(type_id, f"Type {type_id}")


def detect_image_format(data: bytes) -> tuple[str, tuple[int, int] | None]:
    """Detect MIME type and dimensions from image header bytes."""
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", None

    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        dims = None
        if len(data) >= 24:
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            dims = (width, height)
        return "image/png", dims

    return "application/octet-stream", None


def read_artwork(path: Path) -> list[ArtworkInfo]:
    """Read album art metadata from an audio file."""
    try:
        mfile = mutagen.File(str(path))
    except Exception:
        return []
    if mfile is None:
        return []

    artworks = []

    # MP3 - APIC frames
    if isinstance(mfile, mutagen.mp3.MP3):
        try:
            id3 = ID3(str(path))
        except ID3NoHeaderError:
            return []
        for frame in id3.getall("APIC"):
            _, dims = detect_image_format(frame.data)
            artworks.append(ArtworkInfo(
                mime_type=frame.mime,
                size_bytes=len(frame.data),
                picture_type=_picture_type_name(frame.type),
                width=dims[0] if dims else None,
                height=dims[1] if dims else None,
            ))

    # FLAC - Picture blocks
    elif isinstance(mfile, FLAC):
        for pic in mfile.pictures:
            artworks.append(ArtworkInfo(
                mime_type=pic.mime,
                size_bytes=len(pic.data),
                picture_type=_picture_type_name(pic.type),
                width=pic.width or None,
                height=pic.height or None,
            ))

    # MP4/M4A - covr atom
    elif isinstance(mfile, MP4):
        for cover in mfile.get("covr", []):
            if cover.imageformat == MP4Cover.FORMAT_PNG:
                mime = "image/png"
            elif cover.imageformat == MP4Cover.FORMAT_JPEG:
                mime = "image/jpeg"
            else:
                mime = "application/octet-stream"
            _, dims = detect_image_format(bytes(cover))
            artworks.append(ArtworkInfo(
                mime_type=mime,
                size_bytes=len(cover),
                picture_type="Cover",
                width=dims[0] if dims else None,
                height=dims[1] if dims else None,
            ))

    # OGG/Opus - METADATA_BLOCK_PICTURE
    elif isinstance(mfile, (OggVorbis, OggOpus)):
        for b64_data in mfile.get("metadata_block_picture", []):
            try:
                pic = Picture(base64.b64decode(b64_data))
                artworks.append(ArtworkInfo(
                    mime_type=pic.mime,
                    size_bytes=len(pic.data),
                    picture_type=_picture_type_name(pic.type),
                    width=pic.width or None,
                    height=pic.height or None,
                ))
            except Exception:
                pass

    return artworks


def extract_artwork_data(path: Path) -> tuple[bytes, str] | None:
    """Extract raw image bytes and MIME type from the first artwork in a file."""
    try:
        mfile = mutagen.File(str(path))
    except Exception:
        return None
    if mfile is None:
        return None

    # MP3
    if isinstance(mfile, mutagen.mp3.MP3):
        try:
            id3 = ID3(str(path))
            apics = id3.getall("APIC")
            if apics:
                return apics[0].data, apics[0].mime
        except ID3NoHeaderError:
            pass

    # FLAC
    elif isinstance(mfile, FLAC):
        if mfile.pictures:
            return mfile.pictures[0].data, mfile.pictures[0].mime

    # MP4
    elif isinstance(mfile, MP4):
        covers = mfile.get("covr", [])
        if covers:
            cover = covers[0]
            if cover.imageformat == MP4Cover.FORMAT_PNG:
                mime = "image/png"
            else:
                mime = "image/jpeg"
            return bytes(cover), mime

    # OGG/Opus
    elif isinstance(mfile, (OggVorbis, OggOpus)):
        for b64_data in mfile.get("metadata_block_picture", []):
            try:
                pic = Picture(base64.b64decode(b64_data))
                return pic.data, pic.mime
            except Exception:
                pass

    return None


def embed_artwork(path: Path, image_data: bytes, mime_type: str, overwrite: bool = False) -> bool:
    """Embed artwork into an audio file. Returns True if successful."""
    try:
        mfile = mutagen.File(str(path))
    except Exception:
        return False
    if mfile is None:
        return False

    # Check existing art
    if not overwrite and read_artwork(path):
        return False

    # MP3
    if isinstance(mfile, mutagen.mp3.MP3):
        try:
            id3 = ID3(str(path))
        except ID3NoHeaderError:
            id3 = ID3()

        if overwrite:
            id3.delall("APIC")

        id3.add(APIC(
            encoding=3,
            mime=mime_type,
            type=PictureType.COVER_FRONT,
            desc="Cover",
            data=image_data,
        ))
        id3.save(str(path))
        return True

    # FLAC
    elif isinstance(mfile, FLAC):
        if overwrite:
            mfile.clear_pictures()

        pic = Picture()
        pic.data = image_data
        pic.mime = mime_type
        pic.type = PictureType.COVER_FRONT
        _, dims = detect_image_format(image_data)
        if dims:
            pic.width, pic.height = dims
        mfile.add_picture(pic)
        mfile.save()
        return True

    # MP4
    elif isinstance(mfile, MP4):
        if mime_type == "image/png":
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_PNG)
        else:
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)
        mfile["covr"] = [cover]
        mfile.save()
        return True

    # OGG/Opus
    elif isinstance(mfile, (OggVorbis, OggOpus)):
        pic = Picture()
        pic.data = image_data
        pic.mime = mime_type
        pic.type = PictureType.COVER_FRONT
        _, dims = detect_image_format(image_data)
        if dims:
            pic.width, pic.height = dims

        if overwrite and "metadata_block_picture" in mfile:
            del mfile["metadata_block_picture"]

        mfile["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]
        mfile.save()
        return True

    return False


def remove_artwork(path: Path) -> bool:
    """Remove all artwork from an audio file. Returns True if artwork was removed."""
    try:
        mfile = mutagen.File(str(path))
    except Exception:
        return False
    if mfile is None:
        return False

    # MP3
    if isinstance(mfile, mutagen.mp3.MP3):
        try:
            id3 = ID3(str(path))
            if not id3.getall("APIC"):
                return False
            id3.delall("APIC")
            id3.save(str(path))
            return True
        except ID3NoHeaderError:
            return False

    # FLAC
    elif isinstance(mfile, FLAC):
        if not mfile.pictures:
            return False
        mfile.clear_pictures()
        mfile.save()
        return True

    # MP4
    elif isinstance(mfile, MP4):
        if "covr" not in mfile:
            return False
        del mfile["covr"]
        mfile.save()
        return True

    # OGG/Opus
    elif isinstance(mfile, (OggVorbis, OggOpus)):
        if "metadata_block_picture" not in mfile:
            return False
        del mfile["metadata_block_picture"]
        mfile.save()
        return True

    return False
