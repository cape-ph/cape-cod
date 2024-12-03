"""Module of utility functions for interacting with Jinja2"""

import pathlib

from jinja2 import Environment, FileSystemLoader


def get_j2_template_from_path(tmplt_pth: str):
    """Get a Jinja2 template object from a path string.

    Args:
        tmplt_pth: The path to the template file

    Returns:
        The template object for the path.
    """
    pth = pathlib.Path(tmplt_pth)

    env = Environment(loader=FileSystemLoader(pth.parent))
    return env.get_template(pth.name)
