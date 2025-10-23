"""Bare bones DICOM reader/writer used by the tests."""

from __future__ import annotations

import io
import os
import struct
import uuid
from typing import Dict, Iterable, List, Tuple

from .dataset import DicomDataset, PixelArray, Tag
from .profiles import SaveProfile

EXPLICIT_LONG_VR = {b"OB", b"OW", b"OF", b"SQ", b"UC", b"UR", b"UT", b"UN"}
IMPLICIT_VR_UID = "1.2.840.10008.1.2"
EXPLICIT_VR_LE_UID = "1.2.840.10008.1.2.1"


def _read_tag(stream: io.BufferedReader) -> Tag | None:
    raw = stream.read(4)
    if len(raw) < 4:
        return None
    group, element = struct.unpack("<HH", raw)
    return group, element


def _read_value_explicit(stream: io.BufferedReader) -> Tuple[bytes, bytes]:
    vr = stream.read(2)
    if len(vr) < 2:
        raise EOFError("unexpected end of file when reading VR")
    if vr in EXPLICIT_LONG_VR:
        stream.read(2)  # reserved
        length_bytes = stream.read(4)
        if len(length_bytes) < 4:
            raise EOFError("unexpected end of file when reading VL")
        length = struct.unpack("<I", length_bytes)[0]
    else:
        length_bytes = stream.read(2)
        if len(length_bytes) < 2:
            raise EOFError("unexpected end of file when reading VL")
        length = struct.unpack("<H", length_bytes)[0]
    value = stream.read(length)
    if len(value) < length:
        raise EOFError("unexpected end of file when reading value")
    return vr, value


def _read_file_meta(stream: io.BufferedReader) -> Dict[Tag, bytes]:
    file_meta: Dict[Tag, bytes] = {}
    while True:
        pos = stream.tell()
        tag = _read_tag(stream)
        if tag is None:
            break
        if tag[0] != 0x0002:
            stream.seek(pos)
            break
        _, value = _read_value_explicit(stream)
        file_meta[tag] = value
    return file_meta


def _decode_ascii(value: bytes, default: str = "") -> str:
    if not value:
        return default
    return value.rstrip(b" \0").decode("ascii", errors="ignore") or default


def _decode_unsigned(value: bytes) -> int:
    if len(value) == 2:
        return struct.unpack("<H", value)[0]
    if len(value) == 4:
        return struct.unpack("<I", value)[0]
    raise ValueError("unsupported unsigned value length")


def _decode_pixel_samples(value: bytes, bits_allocated: int) -> List[int]:
    if bits_allocated == 8:
        return list(value)
    if bits_allocated == 16:
        values = []
        for i in range(0, len(value), 2):
            chunk = value[i : i + 2]
            if len(chunk) < 2:
                continue
            values.append(struct.unpack("<H", chunk)[0])
        return values
    raise ValueError("unsupported bit depth")


def read_file(path: str) -> DicomDataset:
    with open(path, "rb") as stream:
        _preamble = stream.read(128)
        magic = stream.read(4)
        if magic != b"DICM":
            raise ValueError("not a DICOM file")

        file_meta = _read_file_meta(stream)
        transfer_syntax_uid = _decode_ascii(file_meta.get((0x0002, 0x0010), b""), EXPLICIT_VR_LE_UID)

        if transfer_syntax_uid != EXPLICIT_VR_LE_UID:
            raise NotImplementedError(
                "Only Explicit VR Little Endian files are supported by this lightweight reader."
            )

        elements: Dict[Tag, bytes] = {}
        rows = columns = 0
        samples_per_pixel = 1
        bits_allocated = 8
        raw_pixel_data = b""

        while True:
            tag = _read_tag(stream)
            if tag is None:
                break
            vr, value = _read_value_explicit(stream)
            elements[tag] = value

            if tag == (0x0028, 0x0010):
                rows = _decode_unsigned(value)
            elif tag == (0x0028, 0x0011):
                columns = _decode_unsigned(value)
            elif tag == (0x0028, 0x0002):
                samples_per_pixel = _decode_unsigned(value)
            elif tag == (0x0028, 0x0100):
                bits_allocated = _decode_unsigned(value)
            elif tag == (0x7FE0, 0x0010):
                raw_pixel_data = value
                break

        pixel_values = _decode_pixel_samples(raw_pixel_data, bits_allocated)
        pixel_array = PixelArray(
            rows=rows,
            columns=columns,
            values=pixel_values,
            samples_per_pixel=samples_per_pixel,
            bits_allocated=bits_allocated,
        )

        dataset = DicomDataset(
            file_meta=file_meta,
            elements=elements,
            pixel_array=pixel_array,
            transfer_syntax_uid=transfer_syntax_uid,
        )
        dataset.sop_class_uid = _decode_ascii(file_meta.get((0x0002, 0x0002), b""), None)
        dataset.sop_instance_uid = _decode_ascii(file_meta.get((0x0002, 0x0003), b""), None)
        return dataset


def _encode_string(value: str) -> bytes:
    encoded = value.encode("ascii")
    if len(encoded) % 2:
        encoded += b" "
    return encoded


def _encode_uint(value: int, width: int) -> bytes:
    if width == 2:
        return struct.pack("<H", value)
    if width == 4:
        return struct.pack("<I", value)
    raise ValueError("unsupported width")


def _write_element_explicit(buffer: io.BufferedIOBase, tag: Tag, vr: bytes, value: bytes) -> None:
    buffer.write(struct.pack("<HH", *tag))
    buffer.write(vr)
    if vr in EXPLICIT_LONG_VR:
        buffer.write(b"\x00\x00")
        buffer.write(struct.pack("<I", len(value)))
    else:
        buffer.write(struct.pack("<H", len(value)))
    buffer.write(value)
    if len(value) % 2:
        buffer.write(b"\x00")


def _write_element_implicit(buffer: io.BufferedIOBase, tag: Tag, value: bytes) -> None:
    buffer.write(struct.pack("<HH", *tag))
    buffer.write(struct.pack("<I", len(value)))
    buffer.write(value)
    if len(value) % 2:
        buffer.write(b"\x00")


def _build_file_meta(dataset: DicomDataset, profile: SaveProfile) -> bytes:
    if not dataset.sop_class_uid:
        dataset.sop_class_uid = "1.2.840.10008.5.1.4.1.1.2"
    if not dataset.sop_instance_uid:
        dataset.sop_instance_uid = f"2.25.{uuid.uuid4().int}"

    buffer = io.BytesIO()
    elements = [
        ((0x0002, 0x0001), b"OB", b"\x00\x01"),
        ((0x0002, 0x0002), b"UI", _encode_string(dataset.sop_class_uid)),
        ((0x0002, 0x0003), b"UI", _encode_string(dataset.sop_instance_uid)),
        ((0x0002, 0x0010), b"UI", _encode_string(profile.transfer_syntax_uid)),
        ((0x0002, 0x0012), b"UI", _encode_string("2.25.999999999999999999999999999999999")),
        ((0x0002, 0x0013), b"SH", _encode_string("PYDICOMLESS")),
    ]

    meta_body = io.BytesIO()
    for tag, vr, value in elements:
        _write_element_explicit(meta_body, tag, vr, value)

    group_length = _encode_uint(meta_body.tell(), 4)
    _write_element_explicit(buffer, (0x0002, 0x0000), b"UL", group_length)
    buffer.write(meta_body.getvalue())
    return buffer.getvalue()


def _encode_pixel_data(dataset: DicomDataset, profile: SaveProfile) -> bytes:
    expected = dataset.rows * dataset.columns
    if len(dataset.pixel_array.values) != expected:
        raise ValueError("pixel data does not match Rows/Columns")

    if profile.bits_allocated == 8:
        payload = bytes(dataset.pixel_array.values)
    elif profile.bits_allocated == 16:
        payload = b"".join(struct.pack("<H", value) for value in dataset.pixel_array.values)
    else:
        raise ValueError("unsupported profile bit depth")

    if len(payload) % 2:
        payload += b"\x00"
    return payload


def _build_dataset_elements(dataset: DicomDataset, profile: SaveProfile) -> Iterable[Tuple[Tag, bytes, bytes]]:
    yield ((0x0008, 0x0008), b"CS", _encode_string("DERIVED\\SECONDARY"))
    yield ((0x0008, 0x0016), b"UI", _encode_string(dataset.sop_class_uid or "1.2.840.10008.5.1.4.1.1.2"))
    yield ((0x0008, 0x0018), b"UI", _encode_string(dataset.sop_instance_uid or f"2.25.{uuid.uuid4().int}"))
    yield ((0x0020, 0x000D), b"UI", _encode_string(dataset.study_instance_uid or f"2.25.{uuid.uuid4().int}"))
    yield ((0x0020, 0x000E), b"UI", _encode_string(dataset.series_instance_uid or f"2.25.{uuid.uuid4().int}"))
    yield ((0x0028, 0x0002), b"US", _encode_uint(1, 2))
    yield ((0x0028, 0x0004), b"CS", _encode_string("MONOCHROME2"))
    yield ((0x0028, 0x0008), b"IS", _encode_string("1"))
    yield ((0x0028, 0x0010), b"US", _encode_uint(dataset.rows, 2))
    yield ((0x0028, 0x0011), b"US", _encode_uint(dataset.columns, 2))
    yield ((0x0028, 0x0100), b"US", _encode_uint(profile.bits_allocated, 2))
    yield ((0x0028, 0x0101), b"US", _encode_uint(profile.bits_stored, 2))
    yield ((0x0028, 0x0102), b"US", _encode_uint(profile.high_bit, 2))
    yield ((0x0028, 0x0103), b"US", _encode_uint(0, 2))

    for tag, value in dataset.iter_tags():
        if tag[0] == 0x0028 and tag[1] in {0x0002, 0x0004, 0x0008, 0x0010, 0x0011, 0x0100, 0x0101, 0x0102, 0x0103}:
            continue
        if tag == (0x7FE0, 0x0010):
            continue
        yield (tag, b"UN", value)

    pixel_data = _encode_pixel_data(dataset, profile)
    vr = b"OB" if profile.bits_allocated == 8 else b"OW"
    yield ((0x7FE0, 0x0010), vr, pixel_data)


def write_file(dataset: DicomDataset, destination: str, profile: SaveProfile) -> None:
    dataset.pixel_array.ensure_single_sample()
    if profile.bits_allocated == 8:
        dataset.pixel_array.rescale_to_8bit()

    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)

    file_meta_bytes = _build_file_meta(dataset, profile)
    dataset.transfer_syntax_uid = profile.transfer_syntax_uid

    with open(destination, "wb") as stream:
        stream.write(b"\x00" * 128)
        stream.write(b"DICM")
        stream.write(file_meta_bytes)

        is_implicit = profile.transfer_syntax_uid == IMPLICIT_VR_UID
        for tag, vr, value in _build_dataset_elements(dataset, profile):
            if is_implicit:
                _write_element_implicit(stream, tag, value)
            else:
                _write_element_explicit(stream, tag, vr, value)
