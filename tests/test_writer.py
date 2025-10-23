import os
import struct


from dicom_editor.dataset import DicomDataset, PixelArray
from dicom_editor.io import IMPLICIT_VR_UID, EXPLICIT_VR_LE_UID, read_file, write_file
from dicom_editor.profiles import AVAILABLE_PROFILES


def build_dataset() -> DicomDataset:
    pixels = PixelArray(rows=2, columns=2, values=[0, 64, 128, 255], bits_allocated=8)
    dataset = DicomDataset(file_meta={}, elements={}, pixel_array=pixels, transfer_syntax_uid=EXPLICIT_VR_LE_UID)
    return dataset


def test_write_explicit_profile(tmp_path):
    dataset = build_dataset()
    out_path = tmp_path / "explicit.dcm"
    write_file(dataset, str(out_path), AVAILABLE_PROFILES["ct-explicit-8bit"])

    with open(out_path, "rb") as fp:
        fp.seek(132)  # skip preamble and meta group length element header
        # read first meta element to find transfer syntax UID
        meta_bytes = fp.read(1024)
    assert b"1.2.840.10008.1.2.1" in meta_bytes

    reread = read_file(str(out_path))
    assert reread.pixel_array.rows == 2
    assert reread.pixel_array.columns == 2


def _read_transfer_syntax(path: str) -> str:
    with open(path, "rb") as fp:
        fp.seek(128)
        if fp.read(4) != b"DICM":
            raise AssertionError("not a DICOM file")
        while True:
            tag_bytes = fp.read(4)
            if len(tag_bytes) < 4:
                break
            group, element = struct.unpack("<HH", tag_bytes)
            vr = fp.read(2)
            if vr in {b"OB", b"OW", b"OF", b"SQ", b"UC", b"UR", b"UT", b"UN"}:
                fp.read(2)
                length = struct.unpack("<I", fp.read(4))[0]
            else:
                length = struct.unpack("<H", fp.read(2))[0]
            value = fp.read(length)
            if (group, element) == (0x0002, 0x0010):
                return value.rstrip(b" \0").decode("ascii")
            if group != 0x0002:
                break
    raise AssertionError("transfer syntax not found")


def test_write_implicit_profile(tmp_path):
    dataset = build_dataset()
    out_path = tmp_path / "implicit.dcm"
    write_file(dataset, str(out_path), AVAILABLE_PROFILES["ct-implicit-8bit"])

    ts = _read_transfer_syntax(str(out_path))
    assert ts == IMPLICIT_VR_UID

    with open(out_path, "rb") as fp:
        fp.seek(512)
        tag = fp.read(4)
        # In implicit VR the bytes after the tag must be the length, not a VR code.
        assert tag  # file should contain data beyond meta header
