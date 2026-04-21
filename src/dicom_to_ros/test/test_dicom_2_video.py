import numpy as np
import pytest
from unittest.mock import MagicMock
import cv_bridge
from dicom_to_ros.dicom_2_video import Dicom2VideoNode


def make_msg(rows=8, cols=8, frames=1, dtype="uint16", fill=1000):
    arr = np.full((frames, rows, cols), fill, dtype=np.dtype(dtype))
    msg = MagicMock()
    msg.pixel_data = list(arr.tobytes())
    msg.rows = rows
    msg.columns = cols
    msg.pixel_dtype = dtype
    msg.pixel_spacing = [1.0, 1.0]
    msg.header = MagicMock()
    return msg


@pytest.fixture
def node():
    n = Dicom2VideoNode()
    yield n
    n.destroy_node()


class TestDicom2VideoCallback:
    def test_single_frame_is_skipped(self, node):
        node.img_pub.publish = MagicMock()
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=1))

        node.img_pub.publish.assert_not_called()
        node.cam_pub.publish.assert_not_called()

    def test_multiframe_publishes_one_image_per_frame(self, node):
        node.img_pub.publish = MagicMock()
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=4))

        assert node.img_pub.publish.call_count == 4
        assert node.cam_pub.publish.call_count == 4

    def test_flat_volume_publishes_all_zeros(self, node):
        published = []
        node.img_pub.publish = lambda m: published.append(m)
        node.cam_pub.publish = MagicMock()

        node.callback(make_msg(frames=2, fill=500))

        assert len(published) == 2
        bridge = cv_bridge.CvBridge()
        for img_msg in published:
            img = bridge.imgmsg_to_cv2(img_msg)
            assert np.all(img == 0)
