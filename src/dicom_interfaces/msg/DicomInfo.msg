# Standard ROS header for timestamp and frame_id
std_msgs/Header header

# Patient Information
string patient_id
string patient_name
string sex
string age

# Scan Information
string modality
string study_date
string series_description
string sop_instance_uid

# Technical Data
# Pixel spacing is usually [row_spacing, col_spacing] in mm
float64[] pixel_spacing
float64 slice_thickness
