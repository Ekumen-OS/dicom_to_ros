import io
import requests
import pydicom
from pathlib import Path


def download_direct_dicom_samples():
    """
    Downloads Native 2D and 3D Multi-Frame DICOMs directly.
    Skips download if the file already exists on disk.
    Strictly decompresses compressed DICOMs before saving.
    """
    base_dir = Path("dicom_samples")

    sources = [
        # --- 2D SAMPLES ---
        {
            "url": (
                "https://raw.githubusercontent.com/pydicom/pydicom/main/src/pydicom/data/test_files/CT_small.dcm"
            ),
            "type": "2D",
            "modality": "CT",
            "filename": "native_2d_ct_slice.dcm",
            "description": "Native 2D CT Slice (Uncompressed)",
        },
        {
            "url": (
                "https://raw.githubusercontent.com/pydicom/pydicom/main/src/pydicom/data/test_files/MR_small.dcm"
            ),
            "type": "2D",
            "modality": "MRI",
            "filename": "native_2d_mri_slice.dcm",
            "description": "Native 2D MRI Slice (Uncompressed)",
        },
        {
            "url": (
                "https://raw.githubusercontent.com/pydicom/pydicom/main/src/pydicom/data/test_files/JPEG2000.dcm"
            ),
            "type": "2D",
            "modality": "MRI",
            "filename": "native_2d_mri_compressed.dcm",
            "description": "Native 2D MRI Slice [JPEG2000 Compressed]",
        },
        # --- 3D SAMPLES ---
        {
            "url": (
                "https://raw.githubusercontent.com/ivmartel/dwv/develop/tests/data/multiframe-test1.dcm"
            ),
            "type": "3D",
            "modality": "MRI",
            "filename": "native_3d_mri_cardiac.dcm",
            "description": "Native 3D Cardiac MRI Multi-Frame",
        },
        {
            "url": (
                "https://raw.githubusercontent.com/pydicom/pylibjpeg-data/main/ljdata/ds/JPEGBaseline/color3d_jpeg_baseline.dcm"
            ),
            "type": "3D",
            "modality": "US",
            "filename": "native_3d_ultrasound_color.dcm",
            "description": "Native 3D Ultrasound Multi-Frame (Color)",
        },
    ]

    print("Checking for existing Direct 2D and 3D DICOM files...")

    for source in sources:
        target_dir = base_dir / source["type"] / source["modality"]
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / source["filename"]

        # If the file already exists on the volume, skip the download
        if output_path.exists():
            print(
                f"\n- Skipping {source['description']} -> Already exists:"
                f" {output_path.name}"
            )
            continue

        try:
            print(f"\n- Downloading {source['description']}...")
            response = requests.get(source["url"], timeout=60)
            response.raise_for_status()

            # Load file
            ds = pydicom.dcmread(io.BytesIO(response.content))

            # Decompress pixel data
            if ds.file_meta.TransferSyntaxUID.is_compressed:
                ds.decompress()

            # Save as new file
            ds.save_as(output_path)
            print(f"  -> Decompression successful: {output_path.name}")

        except Exception as e:
            print(f"  -> ERROR: Failed to process. Reason: {e}")

    print("\nFile check and download process completed!")


if __name__ == "__main__":
    download_direct_dicom_samples()
