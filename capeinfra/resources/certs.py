"""Module of cert/key related classes and functions."""

import os

import pulumi_aws as aws
from pulumi import ResourceOptions, warn

from capeinfra.resources.pulumi import CapeComponentResource

from ..util.file import file_as_string

# TODO: ISSUE #99
# TODO: ISSUE #125


class BYOCert(CapeComponentResource):
    """ACM Cert wrapper for bring-your-own cert use case."""

    @staticmethod
    def from_config(name: str, tls_cfg: dict, desc_name: str | None = None):
        """Create an ACM Certificate resource for the given tls config.

        In the event that the config is not valid or has any bad values
        (including names of files that cannot be read), a ValueError will be
        raised.

        The format of the config dict is:
        {
            "dir": <directory path containing all required pem files>,
            "ca-cert": <name of the cert chain pem file>,
            "server-key": <name of the server key pem file>,
            "server-cert": <name of the server cert pem file>,

        }

        Args:
            name: The name to give the AWS ACM Cert resource.
            tls_cfg: The configuration dict for the BYOCert cert being created.
        Returns:
            The created ACM cert.
        Raises:
            ValueError: On missing/invalid configuration options
        """

        tls_dir = tls_cfg.get("dir")
        files = [
            tls_cfg.get("ca-cert"),
            tls_cfg.get("server-key"),
            tls_cfg.get("server-cert"),
        ]

        if tls_dir is None or None in files:
            raise ValueError(
                f"TLS configuration for ACM cert resource {name} is invalid. "
                "One or more expected configuration values are not provided."
            )

        try:

            ca_crt_pth, server_key_pth, server_crt_pth = [
                # join with `f or ""` is to make LSP happy...
                os.path.join(tls_dir, f or "")
                for f in files
            ]

            return BYOCert(
                name,
                ca_crt_pth,
                server_crt_pth,
                server_key_pth,
                desc_name=desc_name,
            )
        except (FileNotFoundError, IsADirectoryError) as err:
            raise ValueError(
                f"One or more configured TLS asset files could not be found "
                f"during ACM Cert ({name}) creation: {err}"
            )

    def __init__(self, name, ca_path, cert_path, key_path, *args, **kwargs):
        """Create a BYOCert object.

        Args:
            name: The unique name for this resource.
            ca_path: The full path (deployment host side) of the cert chain pem
                     file.
            cert_path: The full path (deployment host side) of the server cert
                       pem file.
            key_path: The full path (deployment host side) for the server key
                      pem file.

        Raises:
            FileNotFoundError: When any of the given file paths cannot be
                               found.
        """
        super().__init__(
            "capeinfra:resources:certs:BYOCert", name, *args, **kwargs
        )

        ca_crt_pem, server_crt_pem, server_key_pem = [
            # this raises FileNotFoundError
            file_as_string(pth)
            for pth in [ca_path, cert_path, key_path]
        ]

        self.acmcert = aws.acm.Certificate(
            f"{name}-acmcert",
            certificate_chain=ca_crt_pem,
            private_key=server_key_pem,
            certificate_body=server_crt_pem,
            opts=ResourceOptions(parent=self),
        )
