"""Module of configuration related utilities."""

from collections.abc import Mapping
from typing import Any

from pulumi import Config


def update_dict(base, delta: dict):
    if not isinstance(base, dict):
        return delta
    common_keys = set(base).intersection(delta)
    new_keys = set(delta).difference(common_keys)
    for key in common_keys:
        base[key] = update_dict(base[key], delta[key])
    for key in new_keys:
        base[key] = delta[key]
    return base


class CapeConfig(dict):
    """Class for CAPE configuration objects

    Attributes:
        config: The configuration object
    """

    def __init__(
        self,
        config: dict | str,
        config_name: str | None = "cape-cod",
        default: dict | None = None,
    ):
        """Constructor.

        Args:
            config: The configuration object to instantiate from. If a string is
                    provided it will be retrieved from Pulumi
            config_name: The Pulumi configuration name, if none is provided then
                         the project name is used. (Only applicable when config
                         is a string)
            default: The default configuration object, if any to merge the
                     provided configuration into.

        Raises:
            TypeError: If retrieving the configuration from Pulumi and an object
                       is not returned.
        """
        if isinstance(config, str):
            config = Config(config_name or "cape-cod").require_object(config)
            if not isinstance(config, Mapping):
                raise TypeError(
                    f"Pulumi config value for {config_name}:{config} is not an object"
                )
        if default:
            super().__init__(default)
            self.update(config)
        else:
            super().__init__(config)

    def get(self, *keys, default=None) -> Any:
        """Retrieve an arbitrarily nested value from the configuration object,
           fallback to a default if value is not found while traversing.

        Args:
            *keys: The list keys to search down into the configuration object
            default: The default value to return when element not found,
                     Default: None

        Returns:
            The retrieved value or the default if no value found
        """
        curr = self
        for key in keys:
            if not isinstance(curr, Mapping) or key not in curr:
                curr = default
                break
            curr = curr[key]
        if curr is None:
            curr = default
        return CapeConfig(curr) if isinstance(curr, Mapping) else curr

    def update(self, delta: dict):
        """Update the configuration with values from a new table.

        Args:
            delta: An object to merge into the configuration object. Maintains
                   original structure adding new keys and overwriting keys that
                   have been changed.
        """
        update_dict(self, delta)
