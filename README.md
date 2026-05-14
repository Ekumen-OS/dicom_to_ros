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

This folder contains example DICOM images for testing. To avoid licensing and repository size issues, the image files are not included in the repository.

When you run `docker compose up`, a one-time service will automatically download and process sample DICOM images from dicomlibrary.com and place them in the `dicom_samples` directory. The script organizes them by dimensionality and modality (e.g., `dicom_samples/2D/CT/`, `dicom_samples/3D/MRI/`).

The script will not re-download files if the `dicom_samples` directory already exists.

> **Note on Data Quality:** Because this is an open-source repository, the automated download script relies on small, freely hosted test files from public repositories (such as the core `pydicom` test suite). While these are perfect for verifying that the pipeline and ROS 2 nodes function correctly, they are toy datasets and **not** high-resolution clinical scans. 

If you want to test high-quality 2D and 3D point cloud rendering in RViz (such as a detailed human head or torso), we highly recommend manually downloading clinical-grade DICOM datasets. You can place these manual downloads directly into the `dicom_samples/` folder. 

**Recommended sources for high-quality DICOMs:**
* **[OsiriX Datasets](https://www.osirix-viewer.com/resources/dicom-image-library/):** Excellent for clean, high-resolution 3D multi-frame scans (e.g., the MANIX head CTA).
* **[The Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net/):** Massive repository of real-world clinical datasets across all modalities.
* **[Siemens Healthineers MAGNETOM World](https://www.magnetomworld.siemens-healthineers.com/clinical-corner/protocols/dicom-images):** Excellent source for high-quality, clinical-grade MRI datasets directly from Siemens scanners.
* **[DICOM Library](https://www.dicomlibrary.com/):** Good for finding specific anonymized pathological examples.

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

The system routes data through 6 specialized nodes, launched via `dicom_pipeline.launch.py`:

1. `dicom_server`: Acts as the DICOM Storage SCP (Server). 
It receives the C-STORE request, serializes the raw file into a byte array, and broadcasts it to the ROS network on `/dicom_interfaces/Dicom.`

2. `dicom2studyinfo`: Subscribes to the raw bytes, extracts patient demographics and scan metadata, and publishes a custom `StudyInfo` message.

3. `dicom2img`: Filters for 2D single-frame scans. Publishes the normalized image and standard camera intrinsics (CameraInfo).

4. `dicom2video`: Filters for 3D multi-frame volumes. Publishes the sequence of slices as a live ROS video feed alongside CameraInfo.

5. `dicom2pcl`: Generates a 3D `sensor_msgs/PointCloud2` from volumetric data using pixel spacing, slice thickness, and intensity thresholding.

6. `dicom2tf`: Extracts the Image Position and Orientation (Patient) tags, converting directional cosines into quaternions to broadcast the `patient_frame` to `dicom_optical_frame` spatial relationship.

###  Published Topics

| Topic Name | Message Type | Node Origin | Description |
| :--- | :--- | :--- | :--- |
| `/dicom_interfaces/Dicom` | `dicom_interfaces/Dicom` | `dicom_server` | The raw serialized DICOM byte array (internal routing). |
| `/dicom_study_info` | `dicom_interfaces/StudyInfo` | `dicom2studyinfo` | Patient ID, Name, Modality, Study Date, etc.. |
| `/dicom_image` | `sensor_msgs/Image` | `dicom2img` | 2D single-frame scans (8-bit grayscale). |
| `/dicom_video_frames` | `sensor_msgs/Image` | `dicom2video` | 3D volume sequence playback. |
| `/dicom_point_cloud` | `sensor_msgs/PointCloud2` | `dicom2pcl` | 3D thresholded spatial data. |
| `/tf` | `tf2_msgs/TFMessage` | `dicom2tf` | Spatial tracking and orientation transforms. |


> **Synchronization Note:**  All processed messages generated from the same DICOM file share the exact same header.stamp, allowing downstream nodes to use `message_filters::TimeSynchronizer` to perfectly recombine spatial, visual, and patient data.



### Image Normalization

DICOM images often come in 12-bit or 16-bit integers with varying ranges. 
To make them compatible with standard Computer Vision tools (OpenCV/ROS), the imaging nodes perform Min-Max normalization to cast them to `mono8` (uint8):

$$Pixel_{new} = \frac{(Pixel_{raw} - Pixel_{min})}{Pixel_{max}} \times 255$$

### Metadata Extraction

The `dicom2studyinfo` node populates the custom `StudyInfo` message defined in the `dicom_interfaces` package. The published fields include:

  * **Identifiers:** `patient_id`, `patient_name`, `sop_instance_uid`
  * **Demographics:** `sex`, `age`
  * **Scan Details:** `modality`, `study_date`, `series_description`

*(Note: Technical geometric data like `pixel_spacing` and `slice_thickness` are extracted directly by the imaging and point cloud nodes to generate physically accurate `CameraInfo` and `PointCloud2` messages).*

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
