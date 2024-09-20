"""File-related utiliy functions."""


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
