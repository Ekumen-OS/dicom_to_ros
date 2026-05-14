# DICOM to ROS2

DICOM is a standard format for medical images, providing both a format for image storage and a network protocol for transmission.

This repository provides a fully distributed, microservice-based ROS 2 pipeline for receiving DICOM files (2D slices and 3D multi-frame volumes) over a network and translating them into standard ROS 2 spatial, visual, and informational topics in real-time.

# Project structure

## Docker

This folder provides the `Dockerfile` and `docker-compose.yml` with all the setup needed for running the ROS 2 nodes, dependencies (like `pydicom` and `scipy`), and an RViz2 visualization environment.

## Src

This is the ROS 2 workspace containing the pipeline packages:

1. `dicom_to_ros:` The core package containing the 6 microservice nodes and the launch file to run them all simultaneously.

2. `dicom_interfcaes:` This package contains the custom message types used for internal routing and metadata publishing (`Dicom.msg` and `StudyInfo.msg`).

## Dicom_samples

This folder contains example DICOM images for testing purposes.
This data was downloaded from the following sources:
- https://www.magnetomworld.siemens-healthineers.com/clinical-corner/protocols/dicom-images
- https://dicom.offis.de/download/images/ddsm/
- https://www.dicomlibrary.com/ 

# Workspace Setup

Start the complete pipeline (including the background listener and RViz) by running:

```bash
docker compose up --build -d
```

Because of the Docker configuration, the ROS 2 pipeline is launched automatically upon container startup. 
The `pynetdicom` server will be immediately ready to accept requests on port 11112.

# Workflow

This package is split into a distributed microservice architecture, allowing for robust fault tolerance and separation of concerns.

<img src= workflow_dicom.png width=700 />

## 1. DICOM Client (Sending Data)

In your host machine install `dcmtk` with `sudo apt update && sudo apt install dcmtk -y`.
This inclueds a **C-STORE SCU** client that can make requests to the ROS2 node.

### Usage

Run the following command to send a single DICOM file (note the `-v` flag for verbose output to confirm success):

`storescu -v 127.0.0.1 11112 -aec ROS_DICOM_AE <path_to_dicom_file>`


## 2. ROS 2 Microservices (Processing Data)

The system routes data through 6 specialized nodes, launched via `dicom_nodes.launch.py`:

1. `dicom_server`: Acts as the DICOM Storage SCP (Server). It receives the C-STORE request, parses the DICOM file to extract metadata and pixel data, and broadcasts it as a comprehensive `dicom_interfaces/Dicom` message. This message serves as the central data source for all other processing nodes.

2. `dicom2studyinfo`: Subscribes to the `/dicom_interfaces/Dicom` topic, filters for high-level patient and study metadata, and republishes it as a `dicom_interfaces/StudyInfo` message for easy consumption.

3. `dicom2img`: Subscribes to `/dicom_interfaces/Dicom` and filters for 2D single-frame scans. It publishes the normalized image as a `sensor_msgs/Image` and the corresponding `sensor_msgs/CameraInfo`.

4. `dicom2video`: Subscribes to `/dicom_interfaces/Dicom` and filters for 3D multi-frame volumes. It publishes the sequence of slices as a live ROS video feed (`sensor_msgs/Image` stream) alongside a single `sensor_msgs/CameraInfo`.

5. `dicom2pcl`: Subscribes to `/dicom_interfaces/Dicom` and generates a 3D `sensor_msgs/PointCloud2` from volumetric data using pixel spacing, slice thickness, and intensity thresholding.

6. `dicom2tf`: Subscribes to `/dicom_interfaces/Dicom` and extracts the Image Position and Orientation (Patient) tags. It converts the directional cosines into a quaternion to broadcast the `patient_frame` to `dicom_optical_frame` spatial relationship via `/tf`.

###  Published Topics

| Topic Name | Message Type | Node Origin | Description |
| :--- | :--- | :--- | :--- |
| `/dicom_interfaces/Dicom` | `dicom_interfaces/Dicom` | `dicom_server` | A comprehensive message containing pre-parsed metadata and raw pixel data from the DICOM file. Used for internal routing. |
| `/dicom_study_info` | `dicom_interfaces/StudyInfo` | `dicom2studyinfo` | High-level patient and study metadata (ID, Name, Modality, etc.). |
| `/dicom_image` | `sensor_msgs/Image` | `dicom2img` | A single 2D image from a single-frame scan (normalized to 8-bit grayscale). |
| `/dicom_camera_info` | `sensor_msgs/CameraInfo` | `dicom2img` | Camera intrinsics corresponding to `/dicom_image`. |
| `/dicom_video_frames` | `sensor_msgs/Image` | `dicom2video` | A sequence of 2D image frames from a multi-frame scan. |
| `/dicom_video_camera_info` | `sensor_msgs/CameraInfo` | `dicom2video` | Camera intrinsics corresponding to the `/dicom_video_frames` stream. |
| `/dicom_point_cloud` | `sensor_msgs/PointCloud2` | `dicom2pcl` | A 3D point cloud generated from volumetric data, with intensity values. |
| `/tf` | `tf2_msgs/TFMessage` | `dicom2tf` | Spatial transform from the patient coordinate system to the image frame. |


> **Synchronization Note:**  All processed messages generated from the same DICOM file share the exact same header.stamp, allowing downstream nodes to use `message_filters::TimeSynchronizer` to perfectly recombine spatial, visual, and patient data.



### Image Normalization

DICOM images often come in 12-bit or 16-bit integers with varying ranges. 
To make them compatible with standard Computer Vision tools (OpenCV/ROS), the imaging nodes perform Min-Max normalization to cast them to `mono8` (uint8):

$$Pixel_{new} = \frac{(Pixel_{raw} - Pixel_{min})}{Pixel_{max}} \times 255$$

### Metadata and Data Flow

The `dicom_server` node is responsible for parsing the incoming DICOM file. It extracts all necessary metadata—including patient info, study details, and geometric data—and publishes it in a single, comprehensive `dicom_interfaces/Dicom` message.

Downstream nodes subscribe to this topic and use the pre-parsed data:
* The `dicom2studyinfo` node subscribes to the `Dicom` message and republishes a subset of this information (patient demographics and study details) as a `StudyInfo` message. The fields include:
  * **Identifiers:** `patient_id`, `patient_name`, `sop_instance_uid`
  * **Demographics:** `sex`, `age`
  * **Scan Details:** `modality`, `study_date`, `series_description`
* The imaging (`dicom2img`, `dicom2video`) and point cloud (`dicom2pcl`) nodes use the geometric data like `pixel_spacing` and `slice_thickness` directly from the `Dicom` message to generate physically accurate `CameraInfo` and `PointCloud2` messages.

### Server Configuration Parameters

The `dicom_server` node operates using the following standard DICOM network parameters:

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `ae_title` | `ROS_DICOM_AE` | The Application Entity Title for the DICOM Server. |
| `port` | `11112` | The TCP port to listen for incoming DICOM connections. |

# Verifying Output

To view the data flowing through the pipeline in real-time, execute into the running container:

```bash
docker exec -it dicom_listener /bin/bash
source /ros2_ws/install/setup.bash
```

## View Metadata:

```bash
ros2 topic echo /dicom_study_info
```

## View 2D Images / Video:

From your host machine, ensure X11 forwarding is allowed:
```bash
xhost +local:root
```

Then, launch the ROS image viewer and select `/dicom_image` or `/dicom_video_frames` from the dropdown:

```bash
ros2 run rqt_image_view rqt_image_view
```

## View 3D PointClouds & Transforms:

The `docker-compose.yml` automatically launches an `RViz2` instance. Once you sent the DICOM image, you should see the render on RViz. 
