import cv2
import numpy as np
import pydicom
from cv_bridge import CvBridge
from dicom_interfaces.msg import DicomInfo
from pynetdicom import AE, ALL_TRANSFER_SYNTAXES, evt
from pynetdicom.presentation import AllStoragePresentationContexts
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header


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

    # Helper to look inside a specific sequence item for PixelMeasures
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
    # We grab Frame 0's geometry and assume it applies to the volume for visualization
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
    # Shape could be (H, W, 3) or (Frames, H, W, 3)
    if ds.get("SamplesPerPixel", 1) > 1:
        print("Detected Color Image. Converting to Grayscale for ROS...")

        to_gray = lambda img: cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        if pixels.ndim == 3:
            # Single Frame Color (H, W, 3)
            pixels = to_gray(pixels)  # -> (H, W)
        elif pixels.ndim == 4:
            # Multi Frame Color (Frames, H, W, 3)
            # Convert each frame
            frames = []
            for i in range(pixels.shape[0]):
                frames.append(to_gray(pixels[i]))
            pixels = np.array(frames)  # -> (Frames, H, W)

    # Pixels is either (H, W) or (Frames, H, W)
    if pixels.ndim == 2:
        # Reshape to (1, H, W) for consistent loop logic
        return np.expand_dims(pixels, axis=0), False
    elif pixels.ndim == 3:
        return pixels, True
    else:
        raise ValueError(f"Unsupported pixel dimensions: {pixels.shape}")


def generate_opencv_image(slice_2d: np.ndarray) -> np.ndarray:
    """
    Convert a raw 2D DICOM slice into an 8-bit grayscale image.

    Performs min-max normalization to scale the pixel values to the 0-255
    range required for an 8-bit grayscale image (mono8).

    Args:
        slice_2d (np.ndarray): A 2D NumPy array representing a single raw DICOM slice.

    Returns:
        np.ndarray: The normalized 8-bit grayscale image as a contiguous NumPy array.
    """
    slice_2d = slice_2d.astype(np.float32)
    min_val = np.min(slice_2d)
    max_val = np.max(slice_2d)

    if max_val > min_val:
        slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255
    else:
        slice_2d[:] = 0

    return np.ascontiguousarray(slice_2d.astype(np.uint8))


class DicomImagePublisher(Node):
    """
    A ROS 2 node that functions as a DICOM Storage SCP (server).

    This node initializes a pynetdicom server to listen for incoming DICOM
    C-STORE requests. Upon receiving a DICOM image, it processes the data,
    converts it into ROS 2 messages, and publishes it on two topics:
    - `dicom_image_topic`: sensor_msgs/Image
    - `dicom_info_topic`: dicom_interfaces/DicomInfo
    """

    def __init__(self, ae_title="ROS_DICOM_AE", port=11112):
        """
        Constructs the DicomImagePublisher node.

        Args:
            ae_title (str, optional): The Application Entity Title for the DICOM
                server. Defaults to "ROS_DICOM_AE".
            port (int, optional): The TCP port for the DICOM server to listen on.
                Defaults to 11112.
        """
        super().__init__("dicom_transforms_publisher")

        # 1. ROS 2 Publishers Setup
        self.pcl_pub = self.create_publisher(
            PointCloud2, "dicom_point_cloud", 10
        )
        self.image_pub_ = self.create_publisher(Image, "dicom_image_topic", 10)
        self.info_pub_ = self.create_publisher(
            DicomInfo, "dicom_info_topic", 10
        )
        self.bridge = CvBridge()
        self.get_logger().info("ROS 2 DICOM Listener Node initialized.")

        # 2. pynetdicom AE Setup
        self.ae = AE(ae_title=ae_title)

        for context in AllStoragePresentationContexts:
            self.ae.add_supported_context(
                context.abstract_syntax, ALL_TRANSFER_SYNTAXES
            )

        # 3. Bind the handler for DICOM C-STORE (evt.EVT_C_STORE)
        handlers = [(evt.EVT_C_STORE, self.handle_c_store)]

        # Start the DICOM server in a separate thread
        self.server_thread = self.ae.start_server(
            ("0.0.0.0", port), block=False, evt_handlers=handlers
        )
        self.get_logger().info(f"DICOM Storage SCP listening on port {port}...")

    def __del__(self):
        """Destructor to ensure the pynetdicom server is shut down gracefully."""
        if self.ae and self.server_thread:
            self.ae.shutdown()

    def handle_c_store(self, event):
        """
        Callback handler for pynetdicom's EVT_C_STORE event.

        This method is triggered upon receiving a DICOM image via a C-STORE
        request. It orchestrates the processing and publishing of the received data.

        Args:
            event (pynetdicom.events.Event): The C-STORE event object containing
                the dataset and context information.

        Returns:
            int: A DICOM status code. 0x0000 for success, or an error code
                 (e.g., 0xC001 for processing failure).
        """
        ds = event.dataset
        ds.file_meta = event.file_meta
        if "TransferSyntaxUID" not in ds.file_meta:
            ds.file_meta.TransferSyntaxUID = event.context.transfer_syntax
        self.get_logger().info(
            f"Received {ds.get('Modality')} scan. Processing..."
        )

        try:
            # Get volume and geometry
            volume, is_multiframe = prepare_pixel_data(ds)
            volume = volume.astype(np.float32)
            spacing, thickness = extract_geometry(ds)
            num_frames = volume.shape[0]

            # Normalize entire volume consistently (0-255)
            min_val, max_val = np.min(volume), np.max(volume)
            if max_val > min_val:
                volume = (volume - min_val) / (max_val - min_val) * 255.0
            else:
                volume[:] = 0

            # Keep a uint8 copy for the 2D ROS Image messages
            volume_uint8 = volume.astype(np.uint8)

            # Point Cloud generation
            threshold = 20.0
            z_indices, y_indices, x_indices = np.where(volume > threshold)
            intensities = volume[z_indices, y_indices, x_indices]

            spacing_x, spacing_y = spacing[1], spacing[0]
            x_coords = (x_indices * spacing_x) / 1000.0
            y_coords = (y_indices * spacing_y) / 1000.0
            z_coords = (z_indices * thickness) / 1000.0

            points = np.stack(
                [x_coords, y_coords, z_coords, intensities], axis=-1
            )

            fields = [
                PointField(
                    name="x", offset=0, datatype=PointField.FLOAT32, count=1
                ),
                PointField(
                    name="y", offset=4, datatype=PointField.FLOAT32, count=1
                ),
                PointField(
                    name="z", offset=8, datatype=PointField.FLOAT32, count=1
                ),
                PointField(
                    name="intensity",
                    offset=12,
                    datatype=PointField.FLOAT32,
                    count=1,
                ),
            ]

            common_header = Header()
            common_header.frame_id = "dicom_optical_frame"
            common_header.stamp = self.get_clock().now().to_msg()

            pcl_msg = point_cloud2.create_cloud(common_header, fields, points)
            self.pcl_pub.publish(pcl_msg)
            self.get_logger().info(
                f"Published 3D PointCloud ({len(points)} points)."
            )

            # Publish 2D slices and metadata
            for i in range(num_frames):
                # Image Message
                image_msg = self.bridge.cv2_to_imgmsg(
                    volume_uint8[i], encoding="mono8"
                )
                image_msg.header = common_header

                # Info Message
                info_msg = DicomInfo()
                info_msg.header = common_header
                info_msg.patient_id = str(ds.get("PatientID", "Unknown"))
                info_msg.patient_name = str(ds.get("PatientName", "Unknown"))
                info_msg.sex = str(ds.get("PatientSex", "Unknown"))
                info_msg.age = str(ds.get("PatientAge", "Unknown"))
                info_msg.modality = str(ds.get("Modality", "Unknown"))
                info_msg.study_date = str(ds.get("StudyDate", "Unknown"))
                info_msg.series_description = str(
                    ds.get("SeriesDescription", "Unknown")
                )
                info_msg.sop_instance_uid = str(
                    ds.get("SOPInstanceUID", "Unknown")
                )

                info_msg.current_frame_index = int(i)
                info_msg.total_frames = int(num_frames)
                info_msg.pixel_spacing = spacing
                info_msg.slice_thickness = float(thickness)

                self.image_pub_.publish(image_msg)
                self.info_pub_.publish(info_msg)

            self.get_logger().info(
                f"Published {num_frames} 2D Image & Info messages."
            )
            return 0x0000  # Success

        except Exception as e:
            self.get_logger().error(f"Processing Error: {e}")
            return 0xC001  # Processing failure


def main(args=None):
    """
    Main entry point for the ROS 2 node.

    Initializes rclpy, creates and spins the DicomImagePublisher node to keep it
    alive, and handles clean shutdown on KeyboardInterrupt.

    Args:
        args (list[str], optional): Command-line arguments. Defaults to None.
    """
    rclpy.init(args=args)
    dicom_publisher = DicomImagePublisher()
    try:
        rclpy.spin(dicom_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        dicom_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
