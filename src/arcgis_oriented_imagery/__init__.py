__title__ = "arcgis-oriented-imagery-dataset-from-360"
__version__ = "0.1.0.dev0"
__author__ = "Joel McCune (https://github.com/knu2xs)"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2025 by Joel McCune (https://github.com/knu2xs)"

from importlib.util import find_spec
import re

# add specific imports below if you want to organize your code into modules, which is mostly what I do
from . import data
from . import schema

__all__ = ["data", "schema"]

# provide variable indicating if arcpy is available
_has_arcpy: bool = find_spec("arcpy") is not None

# provide variable indicating if pandas is available
_has_pandas: bool = find_spec("pandas") is not None
