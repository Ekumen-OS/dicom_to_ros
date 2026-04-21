import pytest
from unittest.mock import MagicMock
from dicom_to_ros.dicom_2_tf import Dicom2TFNode


def make_msg(position=None, orientation=None):
    msg = MagicMock()
    msg.image_position = position or [0.0, 0.0, 0.0]
    msg.image_orientation = orientation or [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    msg.header.stamp = MagicMock()
    return msg


@pytest.fixture
def node():
    n = Dicom2TFNode()
    yield n
    n.destroy_node()


class TestDicom2TFCallback:
    def test_position_converted_from_mm_to_m(self, node):
        transforms = []
        node.tf_broadcaster.sendTransform = lambda t: transforms.append(t)

        node.callback(make_msg(position=[1000.0, 2000.0, 500.0]))

        t = transforms[0].transform.translation
        assert t.x == pytest.approx(1.0)
        assert t.y == pytest.approx(2.0)
        assert t.z == pytest.approx(0.5)

    def test_quaternion_is_unit_norm(self, node):
        transforms = []
        node.tf_broadcaster.sendTransform = lambda t: transforms.append(t)

        node.callback(make_msg())

        r = transforms[0].transform.rotation
        norm = (r.x**2 + r.y**2 + r.z**2 + r.w**2) ** 0.5
        assert norm == pytest.approx(1.0)

    def test_identity_orientation_produces_valid_transform(self, node):
        transforms = []
        node.tf_broadcaster.sendTransform = lambda t: transforms.append(t)

        node.callback(make_msg(orientation=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0]))

        assert len(transforms) == 1
