"""File-related utiliy functions."""

import pathlib
import zipfile

from pulumi import error


def file_as_string(pth: str) -> str:
    """Returns the contents of a file in a string.

    Args:
        pth: the path to the file to read
    Raises:
        FileNotFoundError: if the path cannot be found.
    Returns:
        The contents of the file at `pth`.
    """
    s = None
    with open(pth) as f:
        s = f.read()

    return s


def unzip_to(zip_path: str, target_dir: str = "/tmp"):
    """Unzip a zip file to the specified directory.

    Args:
        zip_path: The path to the zip file.
        target_dir: The directory to unzip to. If not specified, the file will
                    be unzipped to `/tmp` to a directory with the same name as
                    the zipf file.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)


def exists_else_error(pth: pathlib.Path, msg: str):
    """Check if a path exists and error out (halt deployment) if not.

    Args:
        pth: The path to check for existence.
        msg: An error message to log if the path does not exist.
    """
    if not pth.exists():
        error(msg)
        raise FileNotFoundError(msg)
