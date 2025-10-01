import csv
from typing import Union, Optional
from pathlib import Path

import pandas as pd

from utils import get_logger
from utils.data import create_feature_dataset

__all__ = ["validate_csv_schema", "rename_columns", "rename_csv_columns"]

# set up logging for this module
logger = get_logger(level="DEBUG", logger_name="arcgis_oriented_imagery.schema")


def validate_csv_schema(
    csv_path: Union[str, Path], required_columns: list[str], fail_if_extra: bool = False
) -> bool:
    """
    Validate that the CSV file contains the required columns.

    Args:
        csv_path: The path to the CSV file.
        required_columns: A list of required column names.
        fail_if_extra: Whether to fail if extra columns are found.

    Returns:
        True if the CSV schema is valid, False otherwise.
    """
    # validate the CSV schema using the csv module
    with open(csv_path, mode="r", newline="") as f:
        reader = csv.reader(f)
        csv_columns = next(reader)
        missing_columns = [col for col in required_columns if col not in csv_columns]

    if missing_columns:
        print(f"Missing columns in CSV: {missing_columns}")
        return False
    
    if fail_if_extra:
        extra_columns = [col for col in csv_columns if col not in required_columns]
        if extra_columns:
            logger.warning(f"Extra columns in CSV: {extra_columns}")

    return True

def rename_dataframe_columns(
    input_data: pd.DataFrame, column_mapping: dict[str, str], warn_if_extra: Optional[bool] = True
) -> Path:
    """
    Rename columns in a Pandas DataFrame based on the provided mapping.

    Args:
        input_data: The input DataFrame.
        column_mapping: Dictionary mapping old column names to new column names.
        warn_if_extra: Whether to log a warning if extra columns are found in the input data.

    Returns:
        Pandas DataFrame with renamed columns.
    """
    # see and notify if there are any extra columns in the input data
    extra_columns = [col for col in input_data.columns if col not in column_mapping.keys()]
    if warn_if_extra and extra_columns:
        logger.warning(f"Extra columns detected: {extra_columns}")

    # get columns being renamed
    renamed_columns = {
        old: new for old, new in column_mapping.items() if old in input_data.columns
    }
    if not renamed_columns:
        logger.info("No columns to rename based on the provided mapping.")
    else:
        logger.info(f"Renaming columns: {renamed_columns}")

    # perform renaming
    renamed_data = input_data.rename(columns=renamed_columns)
    return renamed_data


def rename_csv_columns(
    input_csv_path: Union[str, Path],
    output_csv_path: Union[str, Path],
    column_mapping: dict[str, str],
    warn_if_extra: Optional[bool] = True,
) -> Path:
    """
    Rename columns in a CSV file based on the provided mapping.

    Args:
        input_csv_path: The path to the input CSV file.
        output_csv_path: The path to the output CSV file.
        column_mapping: Dictionary mapping old column names to new column names.
        warn_if_extra: Whether to log a warning if extra columns are found in the input data.
    """
    # ensure input paths are Path objects
    input_csv_path = Path(input_csv_path) if not isinstance(input_csv_path, Path) else input_csv_path
    output_csv_path = Path(output_csv_path) if not isinstance(output_csv_path, Path) else output_csv_path

    # ensure input CSV exists
    if not input_csv_path.exists():
        raise FileNotFoundError(f"Input CSV file not found: {input_csv_path}")

    # Read the input CSV file
    input_data = pd.read_csv(input_csv_path)

    # Rename columns
    renamed_data = rename_dataframe_columns(input_data, column_mapping, warn_if_extra)

    # Write the renamed DataFrame to the output CSV file
    renamed_data.to_csv(output_csv_path, index=False)
    logger.info(f"Renamed CSV saved to: {output_csv_path}")

    return output_csv_path
