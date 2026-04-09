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
    Generates the launch description for the DICOM pipeline.

    Returns:
        LaunchDescription: A ROS 2 launch description containing all the nodes
        for the pipeline.
    """
    return LaunchDescription([
        Node(
            package="dicom_to_ros",
            executable="dicom_server",
            name="dicom_server_node",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2img",
            name="dicom2img_node",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2studyinfo",
            name="dicom2studyinfo_node",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2video",
            name="dicom2video_node",
        ),
        Node(
            package="dicom_to_ros",
            executable="dicom2pcl",
            name="dicom2pcl_node",
        ),
        Node(
            package="dicom_to_ros", executable="dicom2tf", name="dicom2tf_node"
        ),
    ])
