"""Module of subclasses of pulumi constructs that are useful in constructing the
CAPE infrastructure.

The tooling here is core to building all of `capeinfra` which is why this is a
separate module. Before there were issues of circular dependencies if there
wanted to be anything static or top level in this module it would be impossible
to instantiate because every other modules includes this module and therefore
you cannot modify any state of the module without it importing itself.
"""

from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

from pulumi import ComponentResource, Config


def update_dict(base: Any, delta: Mapping):
    if not isinstance(base, dict):
        return delta
    common_keys = set(base).intersection(delta)
    new_keys = set(delta).difference(common_keys)
    for key in common_keys:
        if delta[key] is not None:
            base[key] = update_dict(base[key], delta[key])
    for key in new_keys:
        if delta[key] is not None:
            base[key] = delta[key]
    return base


DEFAULT_CONFIG_NAME = "cape-cod"


class CapeConfig(dict):
    """Class for CAPE configuration objects

    Attributes:
        config: The configuration object
    """

    def __init__(
        self,
        config: Mapping | str = {},
        config_name: str | None = DEFAULT_CONFIG_NAME,
        default: Mapping | None = None,
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
            config = Config(config_name or DEFAULT_CONFIG_NAME).require_object(
                config
            )
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

    def update(self, delta: Mapping):
        """Update the configuration with values from a new table.

        Args:
            delta: An object to merge into the configuration object. Maintains
                   original structure adding new keys and overwriting keys that
                   have been changed.
        """
        update_dict(self, delta)
        return self


class CapeComponentResource(ComponentResource):
    """Extension of ComponentResource that takes a descriptive name and sets up
    configuration."""

    def __init__(
        self,
        *args,
        desc_name=None,
        config: dict | str = {},
        config_name: str | None = None,
        **kwargs,
    ):
        """Constructor.

        Takes all the same args/kwargs as pulumi's ComponentResource in addition
        to the ones below.

        Args:
            config: A configuration dictionary or a string to pull an object
                    from the Pulumi config
            config_name: the name of the section in the pulumi config (Optional,
                         only used if config is a string)
            desc_name: A descriptive name that can be added to tags for child
                       components because names are so restricted in length.
        """
        super().__init__(*args, **kwargs)
        self._config = CapeConfig(
            config, config_name=config_name, default=self.default_config
        )
        self.desc_name = desc_name

    @property
    @abstractmethod
    def default_config(self) -> dict:
        """Abstract property to get the default configuration of the component."""
        pass

    @property
    def config(self):
        """Return the config object for the component."""
        return self._config
