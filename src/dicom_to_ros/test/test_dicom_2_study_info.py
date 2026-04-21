import pytest
from unittest.mock import MagicMock
from dicom_to_ros.dicom_2_study_info import Dicom2StudyInfoNode


def make_msg(**kwargs):
    defaults = dict(
        patient_id="P001",
        patient_name="Doe^John",
        sex="M",
        age="045Y",
        modality="CT",
        study_date="20240101",
        series_description="Chest CT",
        sop_instance_uid="1.2.3.4.5",
    )
    defaults.update(kwargs)
    msg = MagicMock()
    msg.header = MagicMock()
    for k, v in defaults.items():
        setattr(msg, k, v)
    return msg


@pytest.fixture
def node():
    n = Dicom2StudyInfoNode()
    yield n
    n.destroy_node()


class TestDicom2StudyInfoCallback:
    def test_all_fields_mapped_correctly(self, node):
        published = []
        node.pub.publish = lambda m: published.append(m)

        node.callback(make_msg())

        assert len(published) == 1
        info = published[0]
        assert info.patient_id == "P001"
        assert info.patient_name == "Doe^John"
        assert info.sex == "M"
        assert info.age == "045Y"
        assert info.modality == "CT"
        assert info.study_date == "20240101"
        assert info.series_description == "Chest CT"
        assert info.sop_instance_uid == "1.2.3.4.5"

    def test_publishes_exactly_once_per_message(self, node):
        node.pub.publish = MagicMock()

        node.callback(make_msg())

        node.pub.publish.assert_called_once()
