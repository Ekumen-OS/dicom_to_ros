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

from setuptools import setup
import os
from glob import glob

package_name = "dicom_to_ros"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        # Install marker file in the package index
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        # Include our package.xml file
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Susana Chavez",
    maintainer_email="susana.chavez@ekumenlabs.com",
    description="DICOM Listener to ROS 2 Bridge",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dicom_server = dicom_to_ros.dicom_server:main",
            "dicom2img = dicom_to_ros.dicom_2_img:main",
            "dicom2studyinfo = dicom_to_ros.dicom_2_study_info:main",
            "dicom2video = dicom_to_ros.dicom_2_video:main",
            "dicom2pcl = dicom_to_ros.dicom_2_pcl:main",
            "dicom2tf = dicom_to_ros.dicom_2_tf:main",
        ],
    },
)
