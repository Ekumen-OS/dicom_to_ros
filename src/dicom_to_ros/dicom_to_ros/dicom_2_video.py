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


class Dicom2VideoNode(Node):
    """
    A ROS 2 node that processes multi-frame DICOM files (videos) and publishes
    each frame as a ROS Image message. It subscribes to DICOM messages, and for
    each multi-frame sequence, it publishes a stream of `Image` messages and a
    corresponding `CameraInfo` message for each frame.
    """

    def __init__(self):
        """Initializes the node, creating a subscription for DICOM messages and
        publishers for the video frames (`Image`) and camera info (`CameraInfo`).
        """
        super().__init__("dicom2video")
        self.sub = self.create_subscription(
            Dicom, "/dicom_interfaces/Dicom", self.callback, 10
        )
        self.img_pub = self.create_publisher(Image, "dicom_video_frames", 10)
        self.cam_pub = self.create_publisher(
            CameraInfo, "dicom_video_camera_info", 10
        )
        self.bridge = CvBridge()

    def callback(self, msg):
        """
        Callback function for the DICOM message subscriber.

        It processes multi-frame DICOM data, normalizes the entire volume, and
        then iterates through each frame, publishing it as a ROS `Image` message
        along with `CameraInfo`. It ignores single-frame images.

        Args:
            msg (Dicom): The incoming DICOM message.
        """
        volume, is_multiframe = prepare_pixel_data(
            msg.pixel_data, msg.rows, msg.columns, msg.pixel_dtype
        )

        # Only process multi-frame sequences
        if not is_multiframe and volume.shape[0] <= 1:
            return

        spacing = msg.pixel_spacing
        volume = volume.astype(np.float32)

        # Normalize full volume
        min_val, max_val = np.min(volume), np.max(volume)
        if max_val > min_val:
            volume = (volume - min_val) / (max_val - min_val) * 255.0
        else:
            volume[:] = 0

        volume_uint8 = volume.astype(np.uint8)
        frames = volume_uint8.shape[0]

        cam_msg = generate_camera_info(
            msg.header, volume_uint8.shape[1], volume_uint8.shape[2], spacing
        )

        # Publish frames
        for i in range(frames):
            img_msg = self.bridge.cv2_to_imgmsg(
                volume_uint8[i], encoding="mono8"
            )
            img_msg.header = msg.header
            self.img_pub.publish(img_msg)
            self.cam_pub.publish(cam_msg)

        self.get_logger().info(f"Published {frames} video frames & CameraInfo")


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    rclpy.spin(Dicom2VideoNode())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
