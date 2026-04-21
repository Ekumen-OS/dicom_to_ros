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
import pydicom
import numpy as np
import rclpy
from rclpy.node import Node
from dicom_interfaces.msg import Dicom
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
from scipy.spatial.transform import Rotation as R


class Dicom2TFNode(Node):
    """
    A ROS 2 node that broadcasts the spatial transform (TF) of a DICOM image.

    It subscribes to DICOM messages and uses the `ImagePositionPatient` and
    `ImageOrientationPatient` tags to publish a `TransformStamped` message.
    This defines the position and orientation of the DICOM image frame relative
    to a parent patient frame.
    """

    def __init__(self):
        """Initializes the node, creating a subscription for DICOM messages and a
        `TransformBroadcaster`."""
        super().__init__("dicom2tf")
        self.sub = self.create_subscription(
            Dicom, "/dicom_interfaces/Dicom", self.callback, 10
        )
        self.tf_broadcaster = TransformBroadcaster(self)

    def callback(self, msg):
        """
        Callback function to process an incoming DICOM message.

        It extracts the position and orientation from the DICOM metadata, converts
        them into a ROS `TransformStamped` message, and broadcasts it to the `/tf`
        topic. The transform links the `patient_frame` to the `dicom_optical_frame`.

        Args:
            msg (Dicom): The incoming DICOM message.
        """
        # Translation in mm (convert to meters for ROS)
        x_m, y_m, z_m = (
            msg.image_position[0] / 1000.0,
            msg.image_position[1] / 1000.0,
            msg.image_position[2] / 1000.0,
        )

        # Rotation
        row = np.array(msg.image_orientation[0:3])
        col = np.array(msg.image_orientation[3:6])
        normal = np.cross(row, col)

        # Create rotation matrix [3x3] and get quaternion
        rot_matrix = np.column_stack((row, col, normal))
        quat = R.from_matrix(rot_matrix).as_quat()  # returns [x, y, z, w]

        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "patient_frame"  # Parent frame
        t.child_frame_id = msg.header.frame_id  # dicom_optical_frame

        t.transform.translation.x = x_m
        t.transform.translation.y = y_m
        t.transform.translation.z = z_m

        t.transform.rotation.x = quat[0]
        t.transform.rotation.y = quat[1]
        t.transform.rotation.z = quat[2]
        t.transform.rotation.w = quat[3]

        self.tf_broadcaster.sendTransform(t)
        self.get_logger().info("Published DICOM Transform (TF)")


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    rclpy.spin(Dicom2TFNode())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
