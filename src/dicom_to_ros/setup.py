from setuptools import setup

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
            "dicom_listener = dicom_to_ros.dicom_node:main",
        ],
    },
)
