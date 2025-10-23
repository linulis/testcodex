from dicom_editor.dataset import PixelArray


def test_ensure_single_sample_handles_quadrupled_payload():
    rows, cols = 4, 4
    expected = list(range(rows * cols))
    quadrupled = expected * 4
    array = PixelArray(rows=rows, columns=cols, values=quadrupled, samples_per_pixel=1)
    array.ensure_single_sample()
    assert array.values == expected
    assert array.samples_per_pixel == 1


def test_rescale_to_8bit_normalises_range():
    array = PixelArray(rows=1, columns=4, values=[10, 20, 30, 40], bits_allocated=16)
    array.rescale_to_8bit()
    assert array.values == [0, 85, 170, 255]
    assert array.bits_allocated == 8
