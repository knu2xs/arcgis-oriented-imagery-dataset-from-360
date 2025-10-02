---
title: Home
---
# ArcGIS Oriented Imagery Dataset from 360 Imagery 0.1.0.dev3 Documentation

This is the documentation for ArcGIS Oriented Imagery Dataset from 360 Imagery. All the Markdown (`md`) files in
`./docsrc/mkdocs` become the documentation pages.

Streamline the process of ingesting Oriented Imagery from a 360 degree camera.

## Requirements

- [ArcGIS Pro](https://pro.arcgis.com/en/pro-app/latest/get-started/install-and-sign-in-to-arcgis-pro.htm)
- [S3 API](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) (installed _and configured_)
- [Git](https://git-scm.com/downloads) (Optional) - Useful for getting this repo.

## Getting Started

#### Clone this Repo

````
git clone https://github.com/knu2xs/arcgis-oriented-imagery-dataset-from-360
````

Optionally, if you do not have Git installed, you can download and unpack the ZIP file. This works just as well.

### Create Python Environment

Create a Python environment with all needed requirements, notably the 
[AWS SDK for Python, Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html).

This project includes a quick command streamlining much of this.

```
make env
```

However, if this does not work, the following commands will accomplish much of the same thing.

```
conda create -p ./env --clone "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3"
conda activate -p ./env
conda install -c conda-forge boto3
```

#### Set Configuration

Set the values in the configuration file located at `./scripts/config.ini`.

#### Run Make Data

Run the command to scan for new `.csv` files in S3, and create an Oriented Imagery Dataset in
the working directory for each new file discovered in S3.

!!! note

    This command activates the Python environment created above, and runs the `./src/make_data.py` script.
    If you need to customize the workflow, you can edit the script directly.

## Python API

This project also includes a [Python API](./api.md) for programmatic access to its functionality.

The primary function is `process_camera_info_table`, but the [API documentation](./api.md) 
details all available functions.

::: arcgis_oriented_imagery.data.process_camera_info_table
    options:
      members:
        - method_a
        - method_b
      show_root_heading: true
      show_source: false
