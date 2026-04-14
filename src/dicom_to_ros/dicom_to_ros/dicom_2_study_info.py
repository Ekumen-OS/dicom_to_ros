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
        ds = pydicom.dcmread(io.BytesIO(bytes(msg.dicom_data)))

        info = StudyInfo()
        info.header = msg.header
        info.patient_id = str(ds.get("PatientID", "Unknown"))
        info.patient_name = str(ds.get("PatientName", "Unknown"))
        info.sex = str(ds.get("PatientSex", "Unknown"))
        info.age = str(ds.get("PatientAge", "Unknown"))
        info.modality = str(ds.get("Modality", "Unknown"))
        info.study_date = str(ds.get("StudyDate", "Unknown"))
        info.series_description = str(ds.get("SeriesDescription", "Unknown"))
        info.sop_instance_uid = str(ds.get("SOPInstanceUID", "Unknown"))

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
