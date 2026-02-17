# DICOM to ROS2

DICOM is a standard format for medical images. It provides a format for image transmission and a protocol for image transmission. 

This repo provides the full context for passing DICOM 2D images through a ROS Node.

# Project structure

## Docker

This folder provides the Dockerfile with all the setup needed for running the main node. 

## Src

This is the workspace of ROS. It contains all the packages needed and the main server node.

1. `dicom_to_ros:` this package contains the main node for executing the listener side and contains the publish of the following topics: `dicom_image_topic` and `dicom_info_topic`

2. `dicom_interfcaes:` this package contains the custom `DicomInfo.msg` which is customized for this case of study.

## Dicom_samples

This folder contains example DICOM images for testing purposes.
This data was downloaded from the following sources:
- https://www.magnetomworld.siemens-healthineers.com/clinical-corner/protocols/dicom-images
- https://dicom.offis.de/download/images/ddsm/
- https://www.dicomlibrary.com/ 

# Workspace Setup

```
docker compose up --build -d
```

After this the ROS2 node that starts the `pynetdicom` server will be ready to accept requests.

# Workflow

This package is split into three main steps as shown in the image:

<img src= diagram.png width=700 />

## DICOM Client

In your host machine install `dcmtk` with `sudo apt update && sudo apt install dcmtk -y`.
This inclueds a **C-STORE SCU** client that can make requests to the ROS2 node.

### Usage

Run the command, passing the path tot the diresed DICOM file to upload.

`storescu 127.0.0.1 11112 -aec ROS_DICOM_AE +sd <path_to_dicom_file>`

## DICOM Listener Node (`dicom_listener`)

This is the core node of the `dicom_to_ros` package. It functions as a hybrid bridge: acting as a **DICOM Storage SCP (Server)** to accept medical images from PACS or modalities, and immediately republishing them as **ROS 2 topics**.

### Overview

The node initializes a `pynetdicom` server on a background thread. When it receives a `C-STORE` request (a DICOM file transfer):

1.  It decodes the pixel data and metadata.
2.  It converts the image to an OpenCV-compatible format.
3.  It extracts specific patient and scan tags.
4.  It publishes **two synchronized messages**: one for the image and one for the metadata.

###  Published Topics

| Topic Name | Message Type | Description |
| :--- | :--- | :--- |
| `/dicom_image_topic` | `sensor_msgs/Image` | The visual scan data (converted to 8-bit grayscale). |
| `/dicom_info_topic` | `dicom_interfaces/DicomInfo` | The associated metadata (Patient ID, Modality, Spacing, etc.). |

> **Synchronization Note:** Both messages published for a single DICOM file share the exact same `header.stamp`. This allows downstream nodes to use `message_filters::TimeSynchronizer` to recombine the image and metadata perfectly.

### Data Processing Logic

#### Image Normalization

DICOM images often come in 12-bit or 16-bit integers with varying ranges. To make them compatible with standard Computer Vision tools (OpenCV/ROS), we perform Min-Max normalization to cast them to `mono8` (uint8):

$$Pixel_{new} = \frac{(Pixel_{raw} - Pixel_{min})}{Pixel_{max}} \times 255$$

  * **Multi-frame Support:** If the input is a 3D volume (a multi-frame DICOM), the node iterates through every frame in the sequence. Each frame is published as a distinct `sensor_msgs/Image` and `dicom_interfaces/DicomInfo` message pair. The `DicomInfo` message includes `current_frame_index` and `total_frames` to identify each slice's position within the volume.

#### Metadata Extraction

The node populates the custom `DicomInfo` message defined in the `dicom_interfaces` package. The fields include:

  * **Identifiers:** `patient_id`, `patient_name`, `sop_instance_uid`
  * **Demographics:** `sex`, `age`
  * **Scan Details:** `modality`, `study_date`, `series_description`
  * **Technical:** `pixel_spacing` (row/col mm), `slice_thickness`
  * **Frame Indexing:** `current_frame_index` and `total_frames` to support multi-frame volumes.

### Configuration Parameters

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `ae_title` | `ROS_DICOM_AE` | The Application Entity Title for the DICOM Server. |
| `port` | `11112` | The TCP port to listen for incoming DICOM connections. |

### Usage

#### Prerequisites

Ensure you have built the workspace so that the `dicom_interfaces` are generated:

```bash
colcon build
source install/setup.bash
```

#### Running the Node

```bash
ros2 run dicom_to_ros dicom_listener
```

# Verifying Output

To see the metadata flowing in real-time:

```bash
ros2 topic echo /dicom_info_topic
```

To see the image data:

Outside the container, in the local machine, run:

```bash
xhost +local:root
```

```bash
ros2 run rqt_image_view rqt_image_view
```
