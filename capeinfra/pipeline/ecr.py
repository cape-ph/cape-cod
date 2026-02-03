"""Abstractions for ECR."""

import pulumi_awsx as awsx
from pulumi import Input

from capepulumi import CapeComponentResource


class ContainerRepository(CapeComponentResource):
    """An ECR Container Repository."""

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:ContainerRepository"

    def __init__(
        self,
        name: Input[str],
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = f"{name}-repo"
        self.repository = awsx.ecr.Repository(self.name, name=self.name)
        self.images = dict[str, ContainerImage]()

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs(
            {
                "repository_url": self.repository.url
                # "compute_environment": self.compute_environment.id,
            }
        )

    def add_image(self, name, config):
        self.images[name] = ContainerImage(
            f"{self.name}-{name}", repository=self, config=config
        )


class ContainerImage(CapeComponentResource):
    """An ECR Container Image."""

    @property
    def type_name(self) -> str:
        """Return the type_name (pulumi namespacing)."""
        return "capeinfra:datalake:ContainerImage"

    def __init__(
        self,
        name: Input[str],
        repository: ContainerRepository,
        *args,
        **kwargs,
    ):
        """Constructor.

        Args:
            name: The name for the resource.
            repository: The repository to store the image into
        Returns:
        """
        # This maintains parental relationships within the pulumi stack
        super().__init__(name, *args, **kwargs)

        self.name = name

        self.image = awsx.ecr.Image(
            f"{repository.name}-{self.name}-img",
            image_name=self.name,
            repository_url=repository.repository.url,
            **self.config,
        )

        # We also need to register all the expected outputs for this component
        # resource that will get returned by default.
        self.register_outputs({"container_image_uri": self.image.image_uri})
