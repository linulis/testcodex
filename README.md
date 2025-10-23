# Minimal DICOM Viewer/Editor

This repository contains a lightweight set of helpers for reading, inspecting
and exporting simple CT DICOM images.  The toolkit intentionally supports only
little-endian transfer syntaxes and monochrome pixel data so it can run without
third party dependencies.

## Usage

```
PYTHONPATH=src python -m dicom_editor profiles
PYTHONPATH=src python -m dicom_editor show input.dcm
PYTHONPATH=src python -m dicom_editor save input.dcm output.dcm --profile ct-implicit-8bit
```

Profiles control the transfer syntax and bit depth used when saving.  The
supplied 8-bit profiles normalise the pixel payload to avoid issues where other
viewers display the frame multiple times in a tiled layout.
