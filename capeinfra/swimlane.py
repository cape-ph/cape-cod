"""Module for swimlane related abstractions."""

from abc import abstractmethod

from pulumi import ComponentResource, Config


class ScopedSwimlane(ComponentResource):
    """Base class for all scoped swimlanes.

    A scoped swimlane is the logical grouping of public, protected or private
    resources in the CAPE infra.
    """

    def __init__(self, name, opts=None):
        # This maintains parental relationships within the pulumi stack
        super().__init__(self.type_name, name, None, opts=opts)
        self._cfg_dict = None

    @property
    @abstractmethod
    def type_name(self) -> str:
        """Abstract property to get the type_name (pulumi namespacing)."""
        pass

    @property
    @abstractmethod
    def scope(self) -> str:
        """Abstract property to get the scope (public, protected, private)."""
        pass

    @property
    @abstractmethod
    def default_cfg(self) -> dict:
        """Abstract property to get the type_name (pulumi namespacing)."""
        pass

    def get_config_dict(self):
        """Gets the config dict for the swimlane based on its setup.

        Returns:
            The configuration dict for the swimlane. This comes from the pulumi
            config under the key `cape-cod:swimlanes`
        """
        if self._cfg_dict is None:
            config = Config("cape-cod")
            all_sl_config = config.require_object("swimlanes")
            self._cfg_dict = all_sl_config.get(self.scope, self.default_cfg)
        return self._cfg_dict
