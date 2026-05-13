import numpy as np
import pytest
from unittest.mock import MagicMock
import cv_bridge
from std_msgs.msg import Header
from dicom_to_ros.dicom_2_img import Dicom2ImgNode


def make_msg(rows=8, cols=8, frames=1, dtype="uint16", fill=1000):
    arr = np.full((frames, rows, cols), fill, dtype=np.dtype(dtype))
    msg = MagicMock()
    msg.pixel_data = list(arr.tobytes())
    msg.rows = rows
    msg.columns = cols
    msg.pixel_dtype = dtype
    msg.pixel_spacing = [1.0, 1.0]
    msg.header = Header()
    return msg


@pytest.fixture
def node():
    n = Dicom2ImgNode()
    yield n
    n.destroy_node()


class TestDicom2ImgCallback:
    def test_single_frame_publishes_image_and_caminfo(self, node):
        node.img_pub.publish = MagicMock()
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=1))

        node.img_pub.publish.assert_called_once()
        node.cam_pub.publish.assert_called_once()

    def test_multiframe_is_skipped(self, node):
        node.img_pub.publish = MagicMock()
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=3))

        node.img_pub.publish.assert_not_called()
        node.cam_pub.publish.assert_not_called()

    def test_flat_image_publishes_all_zeros(self, node):
        published = []
        node.img_pub.publish = lambda m: published.append(m)
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=1, fill=500))

        assert len(published) == 1
        bridge = cv_bridge.CvBridge()
        img = bridge.imgmsg_to_cv2(published[0])
        assert np.all(img == 0)
