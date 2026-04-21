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
import rclpy
from rclpy.node import Node
from dicom_interfaces.msg import Dicom, StudyInfo


class Dicom2StudyInfoNode(Node):
    """
    A ROS 2 node that extracts metadata from a DICOM message and publishes it
    as a `StudyInfo` message. This node subscribes to raw DICOM data and
    publishes key information about the patient and study.
    """

    def __init__(self):
        """Initializes the node, creating a subscription for DICOM messages and a
        publisher for `StudyInfo` messages."""
        super().__init__("dicom2studyinfo")
        self.sub = self.create_subscription(
            Dicom, "/dicom_interfaces/Dicom", self.callback, 10
        )
        self.pub = self.create_publisher(StudyInfo, "dicom_study_info", 10)

    def callback(self, msg):
        """
        Callback function to process an incoming DICOM message.

        It parses the DICOM data to extract patient and study metadata,
        populates a `StudyInfo` message, and publishes it.

        Args:
            msg (Dicom): The incoming DICOM message containing the raw DICOM
                file data.
        """
        info = StudyInfo()
        info.header = msg.header
        info.patient_id = msg.patient_id
        info.patient_name = msg.patient_name
        info.sex = msg.sex
        info.age = msg.age
        info.modality = msg.modality
        info.study_date = msg.study_date
        info.series_description = msg.series_description
        info.sop_instance_uid = msg.sop_instance_uid

        self.pub.publish(info)
        self.get_logger().info("Published StudyInfo")


def main(args=None):
    """
    The main entry point for the ROS 2 node.

    Args:
        args (list, optional): Command-line arguments for rclpy.
        Defaults to None.
    """
    rclpy.init(args=args)
    rclpy.spin(Dicom2StudyInfoNode())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
