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


class DicomServerNode(Node):
    """
    A ROS 2 node that acts as a DICOM C-STORE Service Class Provider (SCP).

    It listens for incoming DICOM files on a network port, and upon receiving a
    file, it serializes it and publishes it onto a ROS topic as a
    `dicom_interfaces/Dicom` message.
    """

    def __init__(self):
        """Initializes the node, setting up a pynetdicom Application Entity (AE)
        to act as a DICOM server. It configures supported presentation contexts for
        storage and starts the server in a non-blocking thread. It also creates a
        ROS publisher for the DICOM messages."""
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
        Event handler for the pynetdicom `EVT_C_STORE` event.

        This is triggered when a C-STORE request is received from a peer. The
        function processes the incoming DICOM dataset, serializes it into bytes,
        wraps it in a ROS `Dicom` message, and publishes it.

        Args:
            event (pynetdicom.events.Event): The event instance containing the
                dataset and other request information.

        Returns:
            int: A DICOM status code. `0x0000` for success, or an error code
            (e.g., `0xC000`) on failure.
        """
        try:
            ds = event.dataset
            ds.file_meta = event.file_meta

            # Using save_as is the safest way to serialize network datasets
            with io.BytesIO() as buffer:
                ds.save_as(buffer, write_like_original=False)
                dicom_bytes = buffer.getvalue()

            msg = Dicom()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "dicom_optical_frame"
            msg.sop_instance_uid = str(ds.get("SOPInstanceUID", "Unknown"))
            msg.dicom_data = dicom_bytes

            self.pub.publish(msg)
            self.get_logger().info(
                f"Broadcasted DICOM file: {msg.sop_instance_uid}"
            )

            return 0x0000  # Success status

        except Exception as e:
            self.get_logger().error(f"Serialization crashed: {e}")
            return 0xC000  # "Cannot Understand" error status


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    rclpy.spin(DicomServerNode())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
