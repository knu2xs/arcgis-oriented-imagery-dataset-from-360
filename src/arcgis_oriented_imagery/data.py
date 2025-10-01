from datetime import timezone
import json
from pathlib import Path
import re
from typing import Union, Optional, Literal
import tempfile

import arcpy
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from ._logging_utils import get_logger

__all__ = ["get_new_camera_info_tables", "process_camera_info_table"]

# set up logging for this module
logger = get_logger(level="DEBUG", logger_name="arcgis_oriented_imagery.data")


def _slugify(value: str, replacement_char: str = "-") -> str:
    """
    Convert a string to a slug suitable for filenames or URLs.

    Args:
        value: The input string.
    Returns:
        A slugified version of the input string.
    """
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", replacement_char, value)
    value = re.sub(rf"{replacement_char}+", replacement_char, value)
    value = value.strip(replacement_char)
    return value


def create_file_geodatabase(file_geodatabase_path: Union[str, Path]) -> Path:
    """
    Create the full path to an ArcGIS File Geodatabase if it does not already exist.

    !!! note
        If the full path does not exist, all necessary parent directories will be created.

    Args:
        file_geodatabase_path: The full path to the File Geodatabase.
    """
    # if ensure the path is a Path object
    file_geodatabase_path = (
        Path(file_geodatabase_path)
        if not isinstance(file_geodatabase_path, Path)
        else file_geodatabase_path
    )

    # if the directories above the file geodatabase do not exist, create them
    parent_dir = file_geodatabase_path.parent
    if not parent_dir.exists():
        parent_dir.mkdir(parents=True)

    # create the file geodatabase if it does not exist
    if not file_geodatabase_path.exists():
        arcpy.management.CreateFileGDB(
            str(file_geodatabase_path.parent), file_geodatabase_path.name
        )

    return file_geodatabase_path


def create_oriented_imagery_dataset(
    dataset_path: Union[str, Path],
    spatial_reference: Union[int, arcpy.SpatialReference] = 4326,
    has_z: Optional[bool] = True,
) -> Path:
    """
    Create an Oriented Imagery Dataset at the specified path if it does not already exist.

    !!! note
        If the full path does not exist, all necessary parent directories will be created.

    Args:
        dataset_path: The full path to the Oriented Imagery Dataset, including the File Geodatabase and
            Feature Dataset.
        spatial_reference: The spatial reference for the Oriented Imagery Dataset. This can be an EPSG code
            (int) or an :class:`arcpy Spatial Reference<arcpy.SpatialReference>` object. Default is 4326 (WGS 84).
        has_z: Whether the Oriented Imagery Dataset has a Z dimension. Default is True.

    Returns:
        The full path to the created Oriented Imagery Dataset.
    """
    # ensure the dataset path is a Path object
    dataset_path = (
        Path(dataset_path) if not isinstance(dataset_path, Path) else dataset_path
    )

    # ensure file dataset path has .gdb suffix
    gdb_pth = dataset_path.parent
    if gdb_pth.suffix.lower() != ".gdb":
        gdb_pth = gdb_pth.with_suffix(".gdb")

    # get the file geodatabase path and create it if it does not exist
    create_file_geodatabase(file_geodatabase_path=gdb_pth)

    # ensure the spatial reference is an arcpy SpatialReference object, and is integer EPSG code if provided as int
    if isinstance(spatial_reference, int):
        spatial_reference = arcpy.SpatialReference(spatial_reference)
    elif not isinstance(spatial_reference, arcpy.SpatialReference):
        raise TypeError(
            "The spatial_reference parameter must be an integer EPSG code or an arcpy SpatialReference object."
        )

    # create the oriented imagery dataset if it does not exist
    if not dataset_path.exists():
        arcpy.management.CreateOrientedImageryDataset(
            out_dataset_path=gdb_pth,
            out_dataset_name=dataset_path.name,
            spatial_reference=spatial_reference,
            has_z=has_z,
        )

    return dataset_path


def add_images_to_oriented_imagery_dataset(
    dataset_path: Union[str, Path],
    camera_info_table: Union[str, Path],
    imagery_category: Optional[
        Literal["Horizontal", "Oblique", "Nadir", "360", "Inspection"]
    ] = "360",
    camera_info_field_map: Optional[dict[str, str]] = None,
    include_all_fields: Optional[bool] = False,
) -> Path:
    """
    Add images to an existing Oriented Imagery Dataset.

    Args:
        dataset_path: The full path to the Oriented Imagery Dataset.
        camera_info_table: The path to the CSV table containing camera information.
        imagery_category: The category of imagery being added. Default is '360'.
        camera_info_field_map: A dictionary mapping the expected field names to the actual field names in the camera info table.
        include_all_fields: Whether all fields from input table, apart from the required schema, will be added to the dataset's
            attribute table. Default is False.
    """
    # ensure paths are Path objects
    dataset_path = (
        Path(dataset_path) if not isinstance(dataset_path, Path) else dataset_path
    )
    images_path = (
        Path(images_path) if not isinstance(images_path, Path) else images_path
    )
    if camera_info_table:
        camera_info_table = (
            Path(camera_info_table)
            if not isinstance(camera_info_table, Path)
            else camera_info_table
        )

    # ensure the oriented imagery dataset exists
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"The specified Oriented Imagery Dataset does not exist: {dataset_path}"
        )

    # ensure the images path exists and is a directory
    if not images_path.exists() or not images_path.is_dir():
        raise FileNotFoundError(
            f"The specified images path does not exist or is not a directory: {images_path}"
        )

    # if the camera info table is provided, ensure it exists
    if camera_info_table and not camera_info_table.exists():
        raise FileNotFoundError(
            f"The specified camera info table does not exist: {camera_info_table}"
        )

    # prepare camera info fields if mapping is provided
    if camera_info_field_map is not None:
        # get a temporary file name with the .csv suffix
        tmp_dir = tempfile.mkdtemp()
        tmp_csv_path = Path(tmp_dir) / "temp_camera_info.csv"

        # rename the columns in the camera info table to match expected names
        from .schema import (
            rename_csv_columns,
        )  # delayed import to avoid circular dependency

        camera_info_table = rename_csv_columns(
            input_csv_path=camera_info_table,
            output_csv_path=tmp_csv_path,
            column_mapping=camera_info_field_map,
            warn_if_extra=True,
        )

    # add images to the oriented imagery dataset
    arcpy.management.AddImagesToOrientedImageryDataset(
        in_oriented_imagery_dataset=str(dataset_path),
        imagery_category=imagery_category,
        input_data=str(camera_info_table),
        include_all_fields=include_all_fields,
    )

    # clean up temporary files if created
    if camera_info_field_map is not None:
        try:
            if tmp_csv_path.exists():
                tmp_csv_path.unlink()
            if Path(tmp_dir).exists():
                Path(tmp_dir).rmdir()
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")

    return dataset_path


def process_camera_info_table(
    camera_info_table: Union[str, Path],
    working_directory: Union[str, Path],
    camera_info_field_map: Optional[dict[str, str]] = None,
    output_dataset: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Process data defined in a camera info table CSV file. This includes renaming columns based on a provided mapping, and creating an output
    oriented imagery dataset.
    """
    # ensure paths are Path objects
    camera_info_table = (
        Path(camera_info_table)
        if not isinstance(camera_info_table, Path)
        else camera_info_table
    )
    working_directory = (
        Path(working_directory)
        if not isinstance(working_directory, Path)
        else working_directory
    )

    # ensure the camera info table exists
    if not camera_info_table.exists():
        raise FileNotFoundError(
            f"The specified camera info table does not exist: {camera_info_table}"
        )

    # ensure the working directory exists
    if not working_directory.exists():
        working_directory.mkdir(parents=True)

    # create a naming convention for output files based on the input camera info table name if output dataset is not provided
    if output_dataset is None:
        base_name = _slugify(camera_info_table.stem)
        output_dataset = (
            working_directory / f"{base_name}.gdb" / f"{base_name}_oriented_imagery"
        )

    # ensure the output dataset path is a Path object
    output_dataset = (
        Path(output_dataset) if not isinstance(output_dataset, Path) else output_dataset
    )

    # build the output oriented imagery dataset
    create_oriented_imagery_dataset(dataset_path=output_dataset)

    # add images to the oriented imagery dataset
    add_images_to_oriented_imagery_dataset(
        dataset_path=output_dataset,
        camera_info_table=camera_info_table,
        camera_info_field_map=camera_info_field_map,
    )

    return output_dataset


def get_new_camera_info_tables(
    s3_bucket_path: str,
    local_working_directory: Union[str, Path],
    manifest_file: Optional[Union[str, Path]] = None,
) -> list[Path]:
    """
    Download new camera info tables from an S3 bucket.

    Args:
        s3_bucket_path: The S3 bucket path where camera info tables are stored.
        local_working_directory: The local directory to download the camera info tables to.
        manifest_file: Optional path to a manifest file listing specific files to download. If not provided,
            one will be created in the local working directory.
    """
    # ensure local working directory is a Path object
    local_working_directory = (
        Path(local_working_directory)
        if not isinstance(local_working_directory, Path)
        else local_working_directory
    )

    # if manifest file is not provided, create one in the local working directory
    if manifest_file is None:
        manifest_file = local_working_directory / "s3_manifest.json"

    # ensure the local working directory exists
    if not local_working_directory.exists():
        local_working_directory.mkdir(parents=True)

    # use boto3 to check and download new camera info tables
    s3 = boto3.client("s3")
    bucket_name = re.match(r"s3://([^/]+)", s3_bucket_path).group(1)
    prefix = re.sub(
        r"s3://[^/]+/", "", s3_bucket_path
    )  # remove 's3://bucket-name/' to get the prefix
    new_tables = []

    try:
        # list objects in the specified S3 bucket and prefix
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if "Contents" not in response:
            logger.info(f"No objects found in S3 bucket {s3_bucket_path}.")
            return new_tables

        # load existing manifest if it exists
        existing_manifest = {}
        if Path(manifest_file).exists():
            with open(manifest_file, "r") as mf:
                existing_manifest = json.load(mf)

        # check each object in the S3 bucket
        for obj in response["Contents"]:
            key = obj["Key"]
            last_modified = obj["LastModified"].replace(tzinfo=timezone.utc).isoformat()
            filename = key.split("/")[-1]
            local_file_path = local_working_directory / filename

            # if a csv file, determine if the file is new or updated
            if filename.endswith(".csv") and (
                (filename not in existing_manifest)
                or (existing_manifest[filename] != last_modified)
            ):
                # download the file
                s3.download_file(bucket_name, key, str(local_file_path))
                new_tables.append(local_file_path)
                existing_manifest[filename] = last_modified
                logger.info(f"Downloaded new/updated camera info table: {filename}")

        # update the manifest file
        with open(manifest_file, "w") as mf:
            json.dump(existing_manifest, mf, indent=4)

    except (NoCredentialsError, PartialCredentialsError):
        logger.error(
            "AWS credentials not found or incomplete. Please configure your AWS credentials."
        )

    except Exception as e:
        logger.error(f"An error occurred while accessing S3: {e}")

    return new_tables
