# Copyright 2026 Ekumen, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import numpy as np
from sensor_msgs.msg import CameraInfo


def extract_geometry(ds):
    """
    Extract PixelSpacing and SliceThickness from a DICOM dataset.

    Checks standard tags first, then Shared Functional Groups Sequence, then
    Per-Frame Functional Groups Sequence. Falls back to 1.0 mm for any missing
    value.

    Args
    ----
    ds : pydicom.dataset.Dataset
        The DICOM dataset to process.

    Returns
    -------
    tuple[list[float], float]
        Pixel spacing as ``[row_spacing, col_spacing]`` and slice thickness,
        both in mm.

    """
    pixel_spacing = None
    slice_thickness = None

    def check_pixel_measures(sequence_item):
        ps = None
        st = None
        if "PixelMeasuresSequence" in sequence_item:
            measures = sequence_item.PixelMeasuresSequence[0]
            ps = measures.get("PixelSpacing", None)
            st = measures.get("SliceThickness", None)
        return ps, st

    # Standard Tags
    pixel_spacing = ds.get("PixelSpacing", None)
    slice_thickness = ds.get("SliceThickness", None)

    # Shared Functional Groups (Global)
    if pixel_spacing is None and "SharedFunctionalGroupsSequence" in ds:
        try:
            pixel_spacing, st_temp = check_pixel_measures(
                ds.SharedFunctionalGroupsSequence[0]
            )
            if slice_thickness is None:
                slice_thickness = st_temp
        except (AttributeError, IndexError):
            pass

    # Per-Frame Functional Groups
    if pixel_spacing is None and "PerFrameFunctionalGroupsSequence" in ds:
        try:
            pixel_spacing, st_temp = check_pixel_measures(
                ds.PerFrameFunctionalGroupsSequence[0]
            )
            if slice_thickness is None:
                slice_thickness = st_temp
        except (AttributeError, IndexError):
            pass

    # Prevent 0.0 crash
    if pixel_spacing is None:
        pixel_spacing = [1.0, 1.0]  # Default to 1mm

    if slice_thickness is None:
        slice_thickness = 1.0  # Default to 1mm

    # Cast to float for ROS messages
    pixel_spacing = [float(x) for x in pixel_spacing]
    slice_thickness = float(slice_thickness)

    return pixel_spacing, slice_thickness


def prepare_pixel_data(pixel_data: bytes, rows: int, columns: int, pixel_dtype: str):
    """
    Prepare pixel data from a Dicom message for processing.

    Reconstructs a numpy array from raw pixel bytes and dimensions, handling
    both single-frame and multi-frame images into a consistent (N, H, W) format.

    Args
    ----
    pixel_data : bytes
        Raw pixel bytes from the Dicom message.
    rows : int
        Image height in pixels.
    columns : int
        Image width in pixels.
    pixel_dtype : str
        Numpy dtype string (e.g. ``"uint16"``, ``"int16"``, ``"uint8"``).

    Returns
    -------
    tuple[np.ndarray, bool]
        Pixel array with shape ``(N_Frames, H, W)`` and a boolean indicating
        if the data is multi-frame.

    Raises
    ------
    ValueError
        If the pixel data has an unsupported number of dimensions.

    """
    pixels = np.frombuffer(
        bytes(pixel_data), dtype=np.dtype(pixel_dtype)
    ).reshape(-1, rows, columns)

    is_multiframe = pixels.shape[0] > 1

    if pixels.ndim == 3 and pixels.shape[0] == 1:
        return pixels, False
    elif pixels.ndim == 3:
        return pixels, is_multiframe
    else:
        raise ValueError(f"Unsupported pixel dimensions: {pixels.shape}")


def generate_camera_info(header, height, width, spacing):
    """
    Generate a ``sensor_msgs/CameraInfo`` message from DICOM metadata.

    Creates a simplified orthographic camera model whose focal length is
    derived from the pixel spacing, providing spatial context for the image.

    Args
    ----
    header : std_msgs.msg.Header
        ROS header containing timestamp and frame ID.
    height : int
        Image height in pixels.
    width : int
        Image width in pixels.
    spacing : list[float]
        Pixel spacing ``[row_spacing, col_spacing]`` in mm/pixel.

    Returns
    -------
    sensor_msgs.msg.CameraInfo
        The generated CameraInfo message.

    """
    msg = CameraInfo()
    msg.header = header
    msg.height = int(height)
    msg.width = int(width)
    msg.distortion_model = "plumb_bob"
    msg.d = [0.0, 0.0, 0.0, 0.0, 0.0]

    # Intrinsic matrix (K): roughly mapping mm spacing to pixels
    fx = 1.0 / spacing[1] if spacing[1] > 0 else 1.0
    fy = 1.0 / spacing[0] if spacing[0] > 0 else 1.0
    cx = width / 2.0
    cy = height / 2.0

    msg.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
    msg.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    msg.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]

    return msg
