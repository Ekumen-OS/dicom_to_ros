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

import io
import rclpy
from rclpy.node import Node
from pynetdicom import AE, evt, ALL_TRANSFER_SYNTAXES
from pynetdicom.presentation import AllStoragePresentationContexts
from dicom_interfaces.msg import Dicom
from dicom_to_ros.dicom_utils import extract_geometry


class DicomServerNode(Node):
    """
    A ROS 2 node that acts as a DICOM C-STORE Service Class Provider (SCP).

    It listens for incoming DICOM files on a network port, and upon receiving a
    file, it serializes it and publishes it onto a ROS topic as a
    `dicom_interfaces/Dicom` message.
    """

    def __init__(self):
        """
        Initialize the node.

        Sets up a pynetdicom Application Entity (AE) to act as a DICOM server.
        Configures supported presentation contexts for storage, starts the
        server in a non-blocking thread, and creates a ROS publisher for the
        DICOM messages.
        """
        super().__init__("dicom_server")
        self.pub = self.create_publisher(Dicom, "/dicom_interfaces/Dicom", 10)

        self.ae = AE(ae_title="ROS_DICOM_AE")
        for context in AllStoragePresentationContexts:
            self.ae.add_supported_context(
                context.abstract_syntax, ALL_TRANSFER_SYNTAXES
            )

        handlers = [(evt.EVT_C_STORE, self.handle_c_store)]
        self.server_thread = self.ae.start_server(
            ("0.0.0.0", 11112), block=False, evt_handlers=handlers
        )
        self.get_logger().info("DICOM Server running on port 11112")

    def handle_c_store(self, event):
        """
        Handle an incoming EVT_C_STORE event.

        Processes the DICOM dataset, extracts metadata and pixel data, wraps
        them in a ROS `Dicom` message, and publishes it.

        Args
        ----
        event : pynetdicom.events.Event
            The event instance containing the dataset and request information.

        Returns
        -------
        int
            A DICOM status code: ``0x0000`` for success, ``0xC000`` on failure.

        """
        try:
            ds = event.dataset
            ds.file_meta = event.file_meta

            pixel_spacing, slice_thickness = extract_geometry(ds)

            # pixel_spacing = ds.get("PixelSpacing", [1.0, 1.0])
            # slice_thickness = float(ds.get("SliceThickness", 1.0))
            image_position = ds.get("ImagePositionPatient", [0.0, 0.0, 0.0])
            image_orientation = ds.get(
                "ImageOrientationPatient", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            )

            msg = Dicom()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "dicom_optical_frame"
            msg.sop_instance_uid = str(ds.get("SOPInstanceUID", "Unknown"))
            msg.modality = str(ds.get("Modality", "Unknown"))
            msg.patient_id = str(ds.get("PatientID", "Unknown"))
            msg.patient_name = str(ds.get("PatientName", "Unknown"))
            msg.sex = str(ds.get("PatientSex", "Unknown"))
            msg.age = str(ds.get("PatientAge", "Unknown"))
            msg.study_date = str(ds.get("StudyDate", "Unknown"))
            msg.series_description = str(ds.get("SeriesDescription", "Unknown"))
            msg.pixel_spacing = [float(x) for x in pixel_spacing]
            msg.slice_thickness = slice_thickness
            msg.image_position = [float(x) for x in image_position]
            msg.image_orientation = [float(x) for x in image_orientation]
            msg.rows = int(ds.Rows)
            msg.columns = int(ds.Columns)
            msg.pixel_dtype = ds.pixel_array.dtype.name
            msg.pixel_data = list(ds.PixelData)

            self.pub.publish(msg)
            self.get_logger().info(
                f"Broadcasted DICOM file: {msg.sop_instance_uid}"
            )

            return 0x0000  # Success status

        except Exception as e:
            self.get_logger().error(f"Serialization crashed: {e}")
            return 0xC000  # "Cannot Understand" error status


def main(args=None):
    """Run the node until shutdown."""
    rclpy.init(args=args)
    node = DicomServerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
