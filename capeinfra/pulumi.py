"""Module of subclasses of pulumi objects."""

from pulumi import ComponentResource


class DescribedComponentResource(ComponentResource):
    """Extension of ComponentResource that takes a descriptive name."""

    def __init__(self, comp_type, name, *args, desc_name=None, **kwargs):
        """Constructor.

        Takes all the same args/kwargs as pulumi's ComponentResource in addition
        to the ones below.

        Args:
            desc_name: A descriptive name that can be added to tags for child
                       components because names are so restricted in length.
        """
        super().__init__(comp_type, name, *args, **kwargs)
        self.name = name
        self.desc_name = desc_name
