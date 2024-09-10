# CAPE Private Swimlane VPN

Currently, the `CAPE` deployment includes a VPN into the private swimlane. In
the future this may be removed for a number of reasons. But at this time it is
envisioned to be a debug route into the private swimlane in addition to being
required to access http(s) assets in the private swimlane.

## TLS

The connection to the VPN is secured with certificate-based authentication.
**_The CAPE deployment provides no certs/keys_** and it is expected that users
of this repo will bring their own. These may be self-signed, though obviously a
self-signed setup should only be used for development purposes. For more
information on the self-signed setup, see the [Getting Set Up](#getting-set-up)
section below.

The required collection of certs and keys needed for deployment are as follows
(all files should be in PEM format):

1. A CA certificate containing the chain that is used for the server and client
   certs.
1. A server private key
1. A server cert

The client-side cert/key are needed for connection to the VPN, but are not part
of the deployment requirements.

## Getting Set Up

The private swimlane configuration currently only supports certificate-based
authentication. For this to work, two pairs of cert/key `pem` files are needed
in addition to a certificate chain `pem` (a certificate authority cert).

The process for generating self-signed certs/keys and connection to the VPN are
included in this section. Other methods are possible (such as using real CA
signed cert/key files), but are not included here at this time. The following
instructions _should_ work for real certs/keys, but this has not been tested.

### Generate Server and Client-Side Certs and Keys

This process is adapted from the
[AWS Client VPN Administrator's Guide](https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/client-auth-mutual-enable.html)
as of the time of writing of this README. If things don't work, try that guide
to see if there are changes not captured here.

We use [easyrsa](https://github.com/OpenVPN/easy-rsa) (from `OpenVPN`) to
generate the self-signed files. This can be done by other means (e.g. using
`openssl` directly) if desired. We assume that `easyrsa` is already installed
and on the system path. adjust for your setup as needed. We tested against
`easyrsa` version `3.2.0`.

**_NOTE:_** This procedure only has to be done once so long as the certs/keys do
not expire and are not compromised. The cert rotation procedure is not covered
here. Additionally, if the server certificate changes, the VPN endpoint must be
replaced due to how association with the endpoint and cert works in AWS. Client
key/cert can be regenerated (or new ones can be made for new clients) at any
time from the server files and the PEM text only needs to be changed/inserted in
the `ovpn` file if they are regenerated or new ones are created.

-   Create a directory for the pki environment, and initialize the environment:

```bash
mkdir -p ~/some/directory
cd ~/some/directory
easyrsa init-pki
```

-   create a CA that will be used for the signing

```bash
easyrsa build-ca nopass
```

-   create a the server key and cert

```bash
easyrsa --san=DNS:server build-server-full server nopass
```

-   create a the client key and cert

```bash
# the name `client1.domain.tld` isn't really important. Often certs/keys will
# be named for the server they apply to. if generating more than one client
# pair, it's a good idea to include some differentiator of the client in the
# name here
easyrsa build-client-full client1.domain.tld nopass
```

-   at this point, all files needed for the deployment and the vpn connection
    exist (as long as only one client cert/key pair is desired).

### Modify Deployment Configuration

In order to deploy the generated files (and set some other basic VPN
configuration), we need to set some values in the `pulumi` configuration. If
these values are not set or contain an error, a warning will be show during
`pulumi up` stating that the configuration is not valid and configuration of the
VPN will not continue.

**_Because the keys should be protected, it is very important that the
directories set up and referenced in the configuration not end up in the
repository._** The repository is currently setup to ignore files in
`assets/tls`. We recommend using subdirectories here to manage tls assets being
deployed so they do not end up in the repo accidentally. If you use other
directories, be careful.

The following configuration block is supported for VPN (within the `private`
block in the `cape-cod:swimlanes` block):

```yaml
vpn:
    # This CIDR block cannot overlap with the VPC nor with the
    # subnet being assoociated with the VPN endpoint. Additionally
    # it must be at least a /22 and no more than a /12. More here:
    # https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/scaling-considerations.html
    # If not specified, this will default to "10.1.0.0/22"
    cidr-block: "10.1.0.0/22"
    # valid values are "tcp" and "udp". if not specified this will
    # default to "udp"
    transport-proto: "udp"
    tls:
        dir: ./assets/tls/vpn
        # all files must exist in the above `dir`
        ca-cert: ca.crt
        server-key: server.key
        server-cert: server.crt
```

Modify this as required for your setup. At this time VPN can only be configured
if there is a `vpn` subnet in the private swimlane. The default public
configuration contains this (and the `vpn` subnet gets the `10.0.3.0/24` CIDR
block).

## Set Up Connection to VPN

At this time, all testing of connection to the VPN has been performed with
`OpenVPN 2.4.12` (with `OpenSSL 1.1.1k`) via the command line. Other clients may
work, but are not covered here.

This section assumes a deployed `CAPE` instance and permissions to access the
required resource consoles. If you do not have the required permissions to
perform the following steps, you will need to have someone who does follow this
procedure.

Note that this section needs to be repeated any time the client endpoint
changes. This may happen on any `pulumi destroy/up` pair as well as any time the
server cert is replaced (as the endpoint will have to be replaced at that time)
among other events. The main items in the configuration that may change are the
remote name and the contents of `<ca>`, `<cert>`, and `<key>` blocks (depending
on how certs and keys are being managed). If `CAPE` is re-deployed but the VPN
endpoint is not changed in any way, the VPN configuration should remain valid.

### Get the Configuration for the Deployed Endpoint

AWS provides a mechanism to download the `ovpn` config file for a deployed
endpoint. Obtaining this is the first step to connecting to the VPN.

-   Log into the AWS console
-   Navigate to the `VPC` console and select `Client VPN endpoints` under
    `Virtual proivate network (VPN)` in the navigation pane to the left.
-   In the case of an account with only the `CAPE` instance deployed, there
    should be a single VPN endpoint. If there is more than one, you will need to
    examine the description of each to determine which applies to `CAPE`. The
    description should be of the form
    `cape-cod-XXX private swimlane Client VPN Endpoint`, where `XXX` is the
    `stage-name` from the configuration. Select the radio button next to this
    endpoint
-   Click the `Download client configuration` button at the top of the page and
    save the file.

The file will not be complete as AWS only has the server cert/key (and included
in that is the CA cert chain). The config file will require manual insertion of
the client-side `pem` files (both cert and key). Note that when inserting the
contents, you will only want the blocks within (and including)
`-----BEGIN CERTIFICATE-----`/`-----END CERTIFICATE-----` and
`-----BEGIN PRIVATE KEY-----`/`-----END PRIVATE KEY-----`. Any other text in the
`pem` files can be ignored.

In the config file, you will see content for the CA chain in a tag pair
`<ca></ca>`. The content of the client private key and certificate should be
added in a similar manner as follows:

```
<ca>
-----BEGIN CERTIFICATE-----
# contents omitted for brevity
-----END CERTIFICATE-----

</ca>

<cert>
-----BEGIN CERTIFICATE-----
# client cert contents omitted for brevity
-----END CERTIFICATE-----
</cert>

<key>
-----BEGIN PRIVATE KEY-----
# client key contents omitted for brevity
-----END PRIVATE KEY-----
</key>
```

Once updated, save this file to a known location.

### Connect to VPN

Assuming the `ovpn` config file is in the current directory, with the name
`aws-cvpn-endpoint.ovpn` and `openvpn` is on the system path, you can now
connect to the VPN with:

```bash
# NOTE: depending on your setup, `sudo` may be required here
openvpn --config aws-cvpn-endpoint.ovpn
```

## Routes

At this time, the VPN endpoint is associated with the `vpn` subnet described
above. This subnet is authorized to route traffic (egress only) to the internet
as well as within the VPN. The authorizations and routing are fluid and can
change at any time during `CAPE` development. Additionally the VPN itself may be
removed at any time in the future.
