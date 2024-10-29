"""Module of subclasses of pulumi objects."""

from abc import abstractmethod
from typing import Any

from pulumi import ComponentResource

from capeinfra.util.config import CapeConfig


class CapeComponentResource(ComponentResource):
    """Extension of ComponentResource that takes a descriptive name and sets up
    configuration."""

    meta: Any = None

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
