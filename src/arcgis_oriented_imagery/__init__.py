__title__ = "arcgis-oriented-imagery-dataset-from-360"
__version__ = "0.1.0.dev3"
__author__ = "Joel McCune (https://github.com/knu2xs)"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2025 by Joel McCune (https://github.com/knu2xs)"

from importlib.util import find_spec
import sys

# Determine availability of optional heavy dependencies early and avoid
# importing submodules that may themselves import those packages at
# package import time. This prevents circular imports during test
# collection when tests import submodules directly (e.g. importlib
# importing arcgis_oriented_imagery.data).
#
# Avoid importing .data or .schema here to keep package import lightweight.

# provide variable indicating if arcpy is available
# When tests inject a fake "arcpy" module into sys.modules it may not have
# a proper __spec__ (ValueError from importlib.util.find_spec). Check
# sys.modules first and fall back to find_spec in a safe try/except.
try:
	_has_arcpy = ("arcpy" in sys.modules) or (find_spec("arcpy") is not None)
except Exception:
	_has_arcpy = "arcpy" in sys.modules

try:
	_has_pandas = ("pandas" in sys.modules) or (find_spec("pandas") is not None)
except Exception:
	_has_pandas = "pandas" in sys.modules

__all__ = ["data", "schema"]
