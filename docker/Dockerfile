FROM ros:humble-ros-base

# 1. Install System Dependencies
# net-tools and iputils-ping are for debugging network issues
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-cv-bridge \
    ros-humble-sensor-msgs-py \
    ros-humble-rqt-image-view \ 
    ros-humble-rqt-graph \
    net-tools \
    iputils-ping \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies for DICOM
RUN pip install pydicom pynetdicom "numpy<2" opencv-python-headless gdcm pylibjpeg pyjpegls

# 3. Setup Workspace
WORKDIR /ros2_ws

COPY ./src ./src

# 4. Build the workspace

RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build"

RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /ros2_ws/install/setup.bash" >> ~/.bashrc
