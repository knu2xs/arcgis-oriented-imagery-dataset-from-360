import logging
from pathlib import Path
from typing import Union, Optional

from . import _has_arcpy

__all__ = ["get_logger", "format_pandas_for_logging"]


class ArcpyHandler(logging.Handler):
    """Logging handler that routes messages to ArcPy if available.

    This handler uses ArcPy AddMessage/AddWarning/AddError methods so logging
    messages appear in ArcGIS Pro/Server environments.
    """

    terminator = ""

    def __init__(self, level: Union[int, str] = 10):
        if not _has_arcpy:
            raise EnvironmentError(
                "The ArcPy handler requires an environment with ArcPy, a Python environment with ArcGIS Pro or ArcGIS Enterprise."
            )
        super().__init__(level=level)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        # late import to avoid requiring ArcPy at module import time
        import arcpy

        if record.levelno <= 20:
            arcpy.AddMessage(msg)
        elif record.levelno == 30:
            arcpy.AddWarning(msg)
        else:
            arcpy.AddError(msg)


def get_logger(
    level: Optional[Union[str, int]] = "INFO",
    logger_name: Optional[str] = None,
    logfile_path: Union[Path, str] = None,
    propagate: bool = False,
) -> logging.Logger:
    """Return a configured Logger.

    Uses a StreamHandler by default and an ArcpyHandler when ArcPy is available.
    """
    log_str_lst = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN", "FATAL"]
    log_int_lst = [0, 10, 20, 30, 40, 50]

    if not isinstance(level, (str, int)):
        raise ValueError("You must define a specific logging level as a string or integer.")
    if isinstance(level, str) and level not in log_str_lst:
        raise ValueError(f'The log_level must be one of {log_str_lst}. You provided "{level}".')
    if isinstance(level, int) and level not in log_int_lst:
        raise ValueError(f"If providing an integer for log_level, it must be one of {log_int_lst}.")

    logger = logging.getLogger(name=logger_name)
    logger.setLevel(level=level)
    logger.handlers.clear()

    log_frmt = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(log_frmt)
    logger.addHandler(ch)

    logger.propagate = propagate

    if _has_arcpy:
        ah = ArcpyHandler()
        ah.setFormatter(log_frmt)
        logger.addHandler(ah)

    if logfile_path is not None:
        logfile_path = Path(logfile_path)
        if not logfile_path.parent.exists():
            logfile_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(logfile_path))
        fh.setFormatter(log_frmt)
        logger.addHandler(fh)

    return logger


def format_pandas_for_logging(pandas_df, title: str, line_tab_prefix="\t\t") -> str:
    """Format a pandas DataFrame into an indented string suitable for logging.

    Imports pandas locally to avoid a hard dependency at module import time.
    """
    import pandas as pd

    log_str = line_tab_prefix.join(pandas_df.to_string(index=False).splitlines(True))
    log_str = f"{title}:\n{line_tab_prefix}{log_str}"
    return log_str
