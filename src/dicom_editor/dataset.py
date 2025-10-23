"""Data structures describing a simplified DICOM dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

Tag = Tuple[int, int]


@dataclass
class PixelArray:
    """Holds decoded pixel values and image geometry.

    The implementation intentionally stores pixel values as a flat list of
    integers to avoid optional dependencies such as :mod:`numpy`.  A couple of
    helpers exist to rescale the data and to render a small ASCII preview that
    can be shown in the terminal for quick inspection.
    """

    rows: int
    columns: int
    values: List[int]
    samples_per_pixel: int = 1
    bits_allocated: int = 8

    def ensure_single_sample(self) -> None:
        """Coerce multi-sample pixel data into a single-sample representation.

        Some legacy export routines stored RGBA like payloads while still
        claiming to be monochrome images.  Certain viewers interpret such
        payloads as a tiled image which results in a quadruple rendering of the
        content.  The method recognises this scenario and keeps only the first
        channel which corresponds to the actual grayscale signal.
        """

        expected = self.rows * self.columns
        if self.samples_per_pixel == 1 and len(self.values) == expected:
            return

        if len(self.values) == expected * 4 and self.samples_per_pixel == 1:
            self.values = self.values[:expected]
            return

        if self.samples_per_pixel > 1:
            collapsed: List[int] = []
            for i in range(0, len(self.values), self.samples_per_pixel):
                sample = self.values[i : i + self.samples_per_pixel]
                collapsed.append(sum(sample) // len(sample))
            self.values = collapsed

        self.samples_per_pixel = 1

    def rescale_to_8bit(self) -> None:
        """Normalise the pixel data to the 0-255 range."""

        if not self.values:
            return

        minimum = min(self.values)
        maximum = max(self.values)
        if minimum == maximum:
            self.values = [0 for _ in self.values]
            self.bits_allocated = 8
            return

        span = maximum - minimum
        scaled: List[int] = []
        for value in self.values:
            normalised = int(round((value - minimum) * 255.0 / span))
            scaled.append(max(0, min(255, normalised)))
        self.values = scaled
        self.bits_allocated = 8

    def apply_window(self, centre: float, width: float) -> None:
        """Apply a simple window/level transformation."""

        if width <= 0:
            raise ValueError("window width must be positive")

        lower = centre - width / 2
        upper = centre + width / 2
        scaled: List[int] = []
        for value in self.values:
            clamped = max(lower, min(upper, value))
            scaled.append(int(round((clamped - lower) * 255.0 / width)))
        self.values = scaled
        self.bits_allocated = 8

    def ascii_preview(self, max_width: int = 60) -> str:
        """Return a low resolution ASCII art preview of the image."""

        if self.rows == 0 or self.columns == 0:
            return "(empty image)"

        scale = max(1, self.columns // max_width)
        shades = " .:-=+*#%@"
        lines: List[str] = []
        for r in range(0, self.rows, scale):
            builder: List[str] = []
            for c in range(0, self.columns, scale):
                acc = 0
                count = 0
                for rr in range(r, min(r + scale, self.rows)):
                    for cc in range(c, min(c + scale, self.columns)):
                        idx = rr * self.columns + cc
                        if idx < len(self.values):
                            acc += self.values[idx]
                            count += 1
                intensity = acc // max(1, count)
                bucket = intensity * (len(shades) - 1) // 255
                builder.append(shades[bucket])
            lines.append("".join(builder))
        return "\n".join(lines)


@dataclass
class DicomDataset:
    """Simplified representation of a DICOM dataset."""

    file_meta: Dict[Tag, bytes]
    elements: Dict[Tag, bytes]
    pixel_array: PixelArray
    transfer_syntax_uid: str
    sop_class_uid: Optional[str] = None
    sop_instance_uid: Optional[str] = None
    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    additional_elements: Dict[Tag, bytes] = field(default_factory=dict)

    def normalise_pixel_data(self) -> None:
        self.pixel_array.ensure_single_sample()
        self.pixel_array.rescale_to_8bit()

    def update_geometry(self, rows: int, columns: int) -> None:
        self.pixel_array.rows = rows
        self.pixel_array.columns = columns

    @property
    def rows(self) -> int:
        return self.pixel_array.rows

    @property
    def columns(self) -> int:
        return self.pixel_array.columns

    def iter_tags(self) -> Iterable[Tuple[Tag, bytes]]:
        combined: Dict[Tag, bytes] = {}
        combined.update(self.elements)
        combined.update(self.additional_elements)
        for tag in sorted(combined):
            yield tag, combined[tag]
