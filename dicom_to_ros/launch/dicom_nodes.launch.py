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

"""
ROS 2 Launch file for the DICOM to ROS pipeline.

This launch file starts all the necessary nodes for the DICOM processing pipeline:
- `dicom_server`: Listens for incoming DICOM files.
- `dicom2img`: Converts single-frame DICOMs to Image messages.
- `dicom2video`: Converts multi-frame DICOMs to a video stream.
- `dicom2pcl`: Converts DICOM volumes to PointCloud2 messages.
- `dicom2studyinfo`: Extracts and publishes study metadata.
- `dicom2tf`: Broadcasts the DICOM's spatial transform.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Generate the launch description for the DICOM pipeline.

    Returns
    -------
    LaunchDescription
        A ROS 2 launch description containing all nodes for the pipeline.

    """
    return LaunchDescription([
        Node(
            package="dicom_to_ros",
            executable="dicom_server",
            name="dicom_server_node",
            output="screen",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2img",
            name="dicom2img_node",
            output="screen",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2studyinfo",
            name="dicom2studyinfo_node",
            output="screen",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2video",
            name="dicom2video_node",
            output="screen",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2pcl",
            name="dicom2pcl_node",
            output="screen",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2tf",
            name="dicom2tf_node",
            output="screen",
        ),
    ])
