# dicom_to_ros Demo

This package provides a ready-to-run demo environment for the `dicom_to_ros` pipeline: it downloads sample DICOM files and launches an RViz2 instance pre-configured to visualize the point cloud and TF data published by the pipeline.

## Prerequisites

The core ROS 2 pipeline must already be running before starting this demo. From the **repository root**:

```bash
export GID=$(id -g)
docker compose -f docker/docker-compose.yml up --build -d
```

This starts the `dicom_listener` container, which builds the ROS 2 workspace and launches all six microservice nodes. The DICOM C-STORE server listens on port `11112`.

## Starting the Demo

From the **repository root**, allow X11 forwarding and bring up the demo services:

```bash
xhost +local:root

export GID=$(id -g)
docker compose -f dicom_to_ros_demo/docker/docker-compose.yml up --build -d
```

This starts two services:

- **`sample_downloader`**: a one-time service that fetches public DICOM samples and organizes them into `dicom_to_ros_demo/dicom_samples/2D/` and `.../3D/`. It does not re-download if the directory already exists.
- **`rviz`**: waits for the downloader to finish, then opens RViz2 with a pre-configured layout (`rviz_config/default.rviz`) showing the 3D point cloud and TF frames.

Both services share the host network and IPC namespace with the core pipeline container, so all ROS 2 topics are visible across them.

## Sending DICOM Files

Install `dcmtk` on your host machine if you haven't already:

```bash
sudo apt update && sudo apt install dcmtk -y
```

Send a DICOM file to the running pipeline using `storescu`:

```bash
storescu -v 127.0.0.1 11112 -aec ROS_DICOM_AE <path_to_dicom_file>
```

The downloaded sample files are available on the host at `dicom_to_ros_demo/dicom_samples/`. For example:

```bash
# Send a 2D scan
storescu -v 127.0.0.1 11112 -aec ROS_DICOM_AE dicom_to_ros_demo/dicom_samples/2D/CT/

# Send a 3D volume
storescu -v 127.0.0.1 11112 -aec ROS_DICOM_AE dicom_to_ros_demo/dicom_samples/3D/MRI/
```

`storescu` can send an entire directory — it will transmit each `.dcm` file in sequence.

## Visualizing Data

### 3D Point Cloud and TF (RViz2)

RViz2 opens automatically when you run `docker compose up`. The default layout is configured with:

- **Fixed frame**: `dicom_optical_frame`
- **PointCloud2** display subscribed to `/dicom_point_cloud`, colored by intensity
- **TF** display showing the `patient_frame` → `dicom_optical_frame` transform

Once you send a 3D volume, the point cloud will appear in the viewport. Use the mouse to orbit, pan, and zoom.

### Study Metadata

Echo the study metadata topic to see patient and scan information:

```bash
docker exec -it dicom_listener /bin/bash -c \
  "source /ros2_ws/install/setup.bash && ros2 topic echo /dicom_study_info"
```

### All Active Topics

```bash
docker exec -it dicom_listener /bin/bash -c \
  "source /ros2_ws/install/setup.bash && ros2 topic list"
```

## High-Quality Test Data

The automated downloader fetches small public DICOM files sufficient for verifying the pipeline. For high-resolution clinical rendering, manually place files into `docker/dicom_samples/` from these sources:

- **[OsiriX DICOM Library](https://www.osirix-viewer.com/resources/dicom-image-library/)** — High-resolution 3D volumes (e.g., MANIX head CTA)
- **[The Cancer Imaging Archive (TCIA)](https://www.cancerimagingarchive.net/)** — Large-scale real-world clinical datasets
- **[Siemens MAGNETOM World](https://www.magnetomworld.siemens-healthineers.com/clinical-corner/protocols/dicom-images)** — Clinical-grade MRI from Siemens scanners
- **[DICOM Library](https://www.dicomlibrary.com/)** — Anonymized pathological examples
