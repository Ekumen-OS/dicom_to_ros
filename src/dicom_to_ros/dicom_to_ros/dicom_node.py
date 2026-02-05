import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from dicom_interfaces.msg import DicomInfo
from cv_bridge import CvBridge, CvBridgeError
from pynetdicom import AE, evt
import pydicom
import numpy as np
import json

from pynetdicom import ALL_TRANSFER_SYNTAXES
from pynetdicom.presentation import AllStoragePresentationContexts


def generate_opencv_image(pixels: np.ndarray) -> np.ndarray:
    """
    Min-max normalization and casting logic (optimized for 2D array).
    """
    # Ensure the input is 2D and then normalize
    if pixels.ndim != 2:
        raise ValueError(f"Normalization function expects a 2D array, but got shape {pixels.shape}")
        
    pixels = pixels - np.min(pixels)
    # Handle division by zero if max is 0
    max_val = np.max(pixels)
    if max_val == 0:
        pixels = pixels * 0  # Result is all zeros
    else:
        pixels = (pixels / max_val) * 255
        
    normalized_image = np.ascontiguousarray(pixels.astype(np.uint8))
    return normalized_image

def dicom_to_opencv(dicom_dataset: pydicom.Dataset, frame_index: int = 0) -> np.ndarray:
    """
    Extracts raw pixels, ensures 2D structure, and calls the custom normalization function.
    """
    try:
        print("Converting DICOM dataset to OpenCV image...")
        raw_pixels = dicom_dataset.pixel_array
        
        # Handle Multi-Frame DICOM
        if raw_pixels.ndim == 3:
            # Select the first frame (or any frame you need)
            # This converts (N_Frames, H, W) to (H, W)
            pixels_2d = raw_pixels[frame_index]
            print(f"Multi-frame DICOM detected. Using frame {frame_index}. New shape: {pixels_2d.shape}")
        elif raw_pixels.ndim == 2:
            # Single frame image
            pixels_2d = raw_pixels
            print(f"Single frame DICOM detected. Shape: {pixels_2d.shape}")
        else:
            raise ValueError(f"Unsupported pixel array dimension: {raw_pixels.ndim}. Expected 2 or 3.")

        opencv_friendly_pixels = generate_opencv_image(pixels_2d)
        print("Conversion to OpenCV image successful.")
        
    except Exception as e:
        print(f"Error during DICOM to OpenCV conversion: {e}")
        raise e
        
    return opencv_friendly_pixels


class DicomImagePublisher(Node):
    """A ROS 2 Node that publishes images received from the DICOM server."""
    
    def __init__(self, ae_title='ROS_DICOM_AE', port=11112):
        super().__init__('dicom_transforms_publisher')
        
        # 1. ROS 2 Publishers Setup
        self.image_pub_ = self.create_publisher(Image, 'dicom_image_topic', 10)
        self.info_pub_ = self.create_publisher(DicomInfo, 'dicom_info_topic', 10)
        self.bridge = CvBridge()
        self.get_logger().info('ROS 2 Transforms Publishers initialized.')
        
        # 2. pynetdicom AE Setup
        self.ae = AE(ae_title=ae_title)

        for context in AllStoragePresentationContexts:
            self.ae.add_supported_context(context.abstract_syntax, ALL_TRANSFER_SYNTAXES)
        
        # 3. Bind the handler for DICOM C-STORE (evt.EVT_C_STORE)
        handlers = [(evt.EVT_C_STORE, self.handle_c_store)]
        
        # Start the DICOM server in a separate thread
        self.server_thread = self.ae.start_server(
            ('0.0.0.0', port), 
            block=False, 
            evt_handlers=handlers
        )
        self.get_logger().info(f"DICOM Storage SCP listening on port {port}...")
        

    def __del__(self):
        """Cleanup on node shutdown."""
        if self.ae and self.server_thread:
            self.ae.shutdown()

    def create_dicom_info_msg(self, ds, timestamp):
        """
        Converts a pydicom dataset into a ROS 2 DicomInfo message.
        """
        msg = DicomInfo()
        
        # 1. Standard Header (Syncs with Image)
        msg.header.stamp = timestamp
        msg.header.frame_id = "dicom_frame"

        # 2. String Fields
        msg.patient_id = str(ds.get("PatientID", "Unknown"))
        msg.patient_name = str(ds.get("PatientName", "Unknown"))
        msg.sex = str(ds.get("PatientSex", "Unknown"))
        msg.age = str(ds.get("PatientAge", "Unknown"))
        
        msg.modality = str(ds.get("Modality", "Unknown"))
        msg.study_date = str(ds.get("StudyDate", "Unknown"))
        msg.series_description = str(ds.get("SeriesDescription", "Unknown"))
        msg.sop_instance_uid = str(ds.get("SOPInstanceUID", "Unknown"))

        # 3. Numeric Fields
        # Pixel Spacing is often a list of strings in DICOM, cast to float list for ROS
        raw_spacing = ds.get("PixelSpacing", [0.0, 0.0])
        msg.pixel_spacing = [float(x) for x in raw_spacing]
        
        msg.slice_thickness = float(ds.get("SliceThickness", 0.0))

        return msg
        
    def handle_c_store(self, event):
        """
        Handler for C-STORE requests from pynetdicom.
        """
        ds = event.dataset
        ds.file_meta = event.file_meta
        if 'TransferSyntaxUID' not in ds.file_meta:
            ds.file_meta.TransferSyntaxUID = event.context.transfer_syntax
        self.get_logger().info(f"Received C-STORE request. SOP Instance UID: {ds.SOPInstanceUID}")

        try:
            # 1. Sync time for topics
            current_time = self.get_clock().now().to_msg()

            # 2 Process DICOM to OpenCV NumPy array
            opencv_image = dicom_to_opencv(ds)
            self.get_logger().info(f"Converted DICOM to OpenCV image with shape: {opencv_image.shape}")
            
            # 3.1 Convert NumPy array to ROS 2 Image message using CV Bridge
            # Use 'mono8' since the function outputs np.uint8 (8-bit grayscale)
            image_msg = self.bridge.cv2_to_imgmsg(opencv_image, encoding='mono8')
            image_msg.header.stamp = current_time
            image_msg.header.frame_id = "dicom_frame"
            
            # 3.2 Info Message
            info_msg = self.create_dicom_info_msg(ds, current_time)
            
            # 4. Publish messages.
            self.image_pub_.publish(image_msg)
            self.info_pub_.publish(info_msg)

            self.get_logger().info(f"Published Image (size: {opencv_image.shape}) & Info for Patient: {info_msg.patient_id}")

            # 5. Return success status (0x0000) for DICOM C-STORE
            return 0x0000 
            
        except CvBridgeError as e:
            self.get_logger().error(f"CV Bridge Error: {e}")
            return 0xC001  # Processing failure
        except Exception as e:
            self.get_logger().error(f"DICOM Processing Error: {e}")
            return 0xC001  # Processing failure

def main(args=None):
    rclpy.init(args=args)
    dicom_publisher = DicomImagePublisher()
    
    try:
        rclpy.spin(dicom_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        dicom_publisher.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()