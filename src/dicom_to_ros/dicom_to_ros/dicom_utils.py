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

import cv2
import numpy as np
from sensor_msgs.msg import CameraInfo


def extract_geometry(ds):
    """
    Robustly finds PixelSpacing and SliceThickness.

    This function attempts to extract geometric information from a pydicom dataset,
    checking standard tags as well as enhanced DICOM tags found in functional groups.

    It checks in the following order:
    1. Top-level standard tags (`PixelSpacing`, `SliceThickness`).
    2. Shared Functional Groups Sequence (for enhanced DICOM).
    3. Per-Frame Functional Groups Sequence (for enhanced DICOM, using frame 0).

    Args:
        ds (pydicom.dataset.Dataset): The DICOM dataset to process.

    Returns:
        tuple[list[float], float]: A tuple containing the pixel spacing
        (as a list of two floats [row, col]) and the slice thickness (as a float).
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


def prepare_pixel_data(ds):
    """
    Prepare pixel data from a DICOM dataset for processing.

    Handles color-to-grayscale conversion and normalizes the output shape for
    both single-frame and multi-frame images to a consistent (N, H, W) format.

    Args:
        ds (pydicom.dataset.Dataset): The DICOM dataset containing the pixel data.

    Returns:
        tuple[np.ndarray, bool]: A tuple containing the pixel data as a NumPy
        array with shape (N_Frames, H, W) and a boolean indicating if the
        original data was multi-frame.

    Raises:
        ValueError: If the pixel data has an unsupported number of dimensions.
    """
    pixels = ds.pixel_array

    # Check if Color (SamplesPerPixel > 1 usually implies RGB/YBR)
    if ds.get("SamplesPerPixel", 1) > 1:
        to_gray = lambda img: cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        if pixels.ndim == 3:
            # Single Frame Color (H, W, 3)
            pixels = to_gray(pixels)  # -> (H, W)
        elif pixels.ndim == 4:
            # Multi Frame Color (Frames, H, W, 3)
            frames = []
            for i in range(pixels.shape[0]):
                frames.append(to_gray(pixels[i]))
            pixels = np.array(frames)  # -> (Frames, H, W)

    # Pixels is either (H, W) or (Frames, H, W)
    if pixels.ndim == 2:
        return np.expand_dims(pixels, axis=0), False
    elif pixels.ndim == 3:
        return pixels, True
    else:
        raise ValueError(f"Unsupported pixel dimensions: {pixels.shape}")


def generate_camera_info(header, height, width, spacing):
    """
    Generates a `sensor_msgs/CameraInfo` message based on DICOM metadata.

    This function creates a simplified camera model where the focal length is
    derived from the pixel spacing, assuming an orthographic projection. This is
    useful for providing spatial context to the 2D image in ROS.

    Args:
        header (std_msgs.msg.Header): The ROS header to use for the message,
            containing timestamp and frame ID.
        height (int): The height of the image in pixels.
        width (int): The width of the image in pixels.
        spacing (list[float]): The pixel spacing `[row_spacing, col_spacing]` in mm/pixel.

    Returns:
        sensor_msgs.msg.CameraInfo: The generated CameraInfo message.
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
