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
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from dicom_interfaces.msg import Dicom
from dicom_to_ros.dicom_utils import (
    prepare_pixel_data,
    generate_camera_info,
)


class Dicom2ImgNode(Node):
    """
    A ROS 2 node that subscribes to a DICOM message, extracts single-frame
    image data, and publishes it as a ROS Image message and a corresponding
    CameraInfo message.
    """

    def __init__(self):
        """
        Initializes the node, sets up the subscriber for DICOM messages, and
        creates publishers for the image and camera info.
        """
        super().__init__("dicom2img")
        self.sub = self.create_subscription(
            Dicom, "/dicom_interfaces/Dicom", self.callback, 10
        )
        self.img_pub = self.create_publisher(Image, "dicom_image", 10)
        self.cam_pub = self.create_publisher(
            CameraInfo, "dicom_camera_info", 10
        )
        self.bridge = CvBridge()

    def callback(self, msg):
        """
        Callback function for the DICOM message subscriber.

        It processes the DICOM data, converts it to a ROS Image message,
        generates CameraInfo, and publishes both. This callback specifically
        handles single-frame DICOM images.

        Args:
            msg (Dicom): The incoming DICOM message.
        """
        volume, is_multiframe = prepare_pixel_data(
            msg.pixel_data, msg.rows, msg.columns, msg.pixel_dtype
        )

        # Only process single images
        if is_multiframe or volume.shape[0] > 1:
            return

        spacing = msg.pixel_spacing
        img_2d = volume[0].astype(np.float32)

        # Normalize
        min_val, max_val = np.min(img_2d), np.max(img_2d)
        if max_val > min_val:
            img_2d = (img_2d - min_val) / (max_val - min_val) * 255.0
        else:
            img_2d[:] = 0

        img_uint8 = img_2d.astype(np.uint8)

        img_msg = self.bridge.cv2_to_imgmsg(img_uint8, encoding="mono8")
        img_msg.header = msg.header

        cam_msg = generate_camera_info(
            msg.header, img_uint8.shape[0], img_uint8.shape[1], spacing
        )

        self.img_pub.publish(img_msg)
        self.cam_pub.publish(cam_msg)
        self.get_logger().info("Published 2D Image & CameraInfo")


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    rclpy.spin(Dicom2ImgNode())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
