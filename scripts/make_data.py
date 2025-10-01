from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
import importlib.util
import sys

# path to the root of the project
dir_prj = Path(__file__).parent.parent

# if the project package is not installed in the environment
if importlib.util.find_spec('arcgis_oriented_imagery') is None:
    
    # get the relative path to where the source directory is located
    src_dir = dir_prj / 'src'

    # throw an error if the source directory cannot be located
    if not src_dir.exists():
        raise EnvironmentError('Unable to import arcgis_oriented_imagery.')

    # add the source directory to the paths searched when importing
    sys.path.insert(0, str(src_dir))

# import arcgis_oriented_imagery
import arcgis_oriented_imagery

# read and configure 
config = ConfigParser()
config.read('config.ini')

# get paths and settings from the config file
log_dir = config.get('DEFAULT', 'LOG_DIRECTORY')
log_level = config.get('DEFAULT', 'LOG_LEVEL')
s3_bucket = dir_prj / config.get('DEFAULT', 'S3_BUCKET')
working_directory = Path(config.get('DEFAULT', 'WORKING_DIRECTORY'))

# get a yyyyymmddThhmmss string for timestamping outputs
timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')

# ensure logging directory exists
if not log_dir.exists():
    log_dir.mkdir(parents=True)

# use the log level from the config to set up basic logging
logger = arcgis_oriented_imagery.utils.get_logger(level=log_level, logfile_path=log_dir / f'make_data_{timestamp}.log')

# log the configuration settings being used
logger.info(f'Log directory: {log_dir}')
logger.info(f'Working directory: {working_directory}')
logger.info(f'S3 bucket: {s3_bucket}')
logger.info(f'Log level: {log_level}')

# if the working directory does not exist, create it
if not working_directory.exists(): 
    working_directory.mkdir(parents=True)

# get new or updated CSV files from the S3 bucket
new_csv_files = arcgis_oriented_imagery.data.get_new_camera_info_tables(
    s3_bucket_path=s3_bucket,
    local_working_directory=working_directory
)

# log the new or updated CSV files found
if new_csv_files:
    logger.info(f'New or updated CSV files found: {[str(f) for f in new_csv_files]}')
else:
    logger.info('No new or updated CSV files found.')

# process each new or updated CSV file
new_datasets = []
for csv_file in new_csv_files:
    dataset = arcgis_oriented_imagery.data.process_camera_info_table(
        camera_info_table=csv_file,
        working_directory=working_directory,
        # camera_info_field_map=camera_info_field_map
    )
    logger.info(f'Created oriented imagery dataset: {dataset}')
    new_datasets.append(dataset)

if new_datasets:
    logger.info(f'{len(new_datasets):,} new oriented imagery datasets created: {[str(d) for d in new_datasets]}')