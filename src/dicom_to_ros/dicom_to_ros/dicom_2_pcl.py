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
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from dicom_interfaces.msg import Dicom
from dicom_to_ros.dicom_utils import prepare_pixel_data


class Dicom2PCLNode(Node):
    """
    A ROS 2 node that converts DICOM image data into a PointCloud2 message.

    It subscribes to DICOM messages, processes the pixel data to generate a 3D
    point cloud with intensity, and publishes the result.
    """

    def __init__(self):
        """Initializes the node, creating a subscription to the DICOM topic and a
        publisher for the PointCloud2 messages."""
        super().__init__("dicom2pcl")
        self.sub = self.create_subscription(
            Dicom, "/dicom_interfaces/Dicom", self.callback, 10
        )
        self.pcl_pub = self.create_publisher(
            PointCloud2, "dicom_point_cloud", 10
        )

    def callback(self, msg):
        """
        Callback function that processes an incoming DICOM message.

        It reads the pixel volume, thresholds it, and converts the resulting
        voxels into 3D points with intensity values. The resulting point cloud
        is then published.

        Args:
            msg (Dicom): The incoming DICOM message.
        """
        volume, _ = prepare_pixel_data(msg.pixel_data, msg.rows, msg.columns, msg.pixel_dtype)
        volume = volume.astype(np.float32)
        spacing = msg.pixel_spacing
        thickness = msg.slice_thickness

        min_val, max_val = np.min(volume), np.max(volume)
        if max_val > min_val:
            volume = (volume - min_val) / (max_val - min_val) * 255.0
        else:
            volume[:] = 0

        threshold = 20.0
        z_indices, y_indices, x_indices = np.where(volume > threshold)
        intensities = volume[z_indices, y_indices, x_indices]
   
        spacing_x, spacing_y = spacing[1], spacing[0]
        x_coords = (x_indices * spacing_x) / 1000.0
        y_coords = (y_indices * spacing_y) / 1000.0
        z_coords = (z_indices * thickness) / 1000.0

        points = np.stack([x_coords, y_coords, z_coords, intensities], axis=-1)

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



        pcl_msg = point_cloud2.create_cloud(msg.header, fields, points)
        self.pcl_pub.publish(pcl_msg)
        self.get_logger().info(f"Published PointCloud ({len(points)} points).")


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    node = Dicom2PCLNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()