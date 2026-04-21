import numpy as np
import pytest
from unittest.mock import MagicMock
from dicom_to_ros.dicom_utils import prepare_pixel_data, generate_camera_info


def make_pixel_bytes(frames, rows, cols, dtype, fill=1000):
    arr = np.full((frames, rows, cols), fill, dtype=np.dtype(dtype))
    return list(arr.tobytes())


class TestPreparePixelData:
    def test_single_frame_shape_and_flag(self):
        data = make_pixel_bytes(1, 4, 6, "uint16")
        volume, is_multiframe = prepare_pixel_data(data, 4, 6, "uint16")
        assert volume.shape == (1, 4, 6)
        assert is_multiframe is False

    def test_multi_frame_shape_and_flag(self):
        data = make_pixel_bytes(3, 4, 6, "uint16")
        volume, is_multiframe = prepare_pixel_data(data, 4, 6, "uint16")
        assert volume.shape == (3, 4, 6)
        assert is_multiframe is True

    def test_uint8_dtype_preserved(self):
        data = make_pixel_bytes(1, 4, 4, "uint8", fill=200)
        volume, _ = prepare_pixel_data(data, 4, 4, "uint8")
        assert volume.dtype == np.uint8
        assert np.all(volume == 200)

    def test_int16_dtype_and_values_preserved(self):
        arr = np.full((1, 4, 4), -500, dtype=np.int16)
        data = list(arr.tobytes())
        volume, _ = prepare_pixel_data(data, 4, 4, "int16")
        assert volume.dtype == np.int16
        assert np.all(volume == -500)

    def test_inconsistent_byte_count_raises(self):
        with pytest.raises(Exception):
            prepare_pixel_data(list(b"\x00\x01\x02"), 4, 4, "uint16")


class TestGenerateCameraInfo:
    def test_dimensions_match_inputs(self):
        msg = generate_camera_info(MagicMock(), 128, 256, [0.5, 0.5])
        assert msg.height == 128
        assert msg.width == 256

    def test_k_matrix_derived_from_spacing(self):
        msg = generate_camera_info(MagicMock(), 64, 64, [2.0, 4.0])
        assert msg.k[0] == pytest.approx(1.0 / 4.0)  # fx = 1/col_spacing
        assert msg.k[4] == pytest.approx(1.0 / 2.0)  # fy = 1/row_spacing

    def test_zero_spacing_does_not_raise(self):
        msg = generate_camera_info(MagicMock(), 64, 64, [0.0, 0.0])
        assert msg.k[0] == pytest.approx(1.0)
        assert msg.k[4] == pytest.approx(1.0)
