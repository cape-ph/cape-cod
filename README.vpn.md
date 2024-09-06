# CAPE Private Swimlane VPN

Currently, the CAPE deployment includes a VPN into the private swimlane. In the
future this may be removed for a number of reasons. But at this time it is
envisioned to be a debug route into the private swimlane in addition to being
required to hit http assets in the private swimlane.

## TLS

The connection to the VPN is secured with certificate based authentication.
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

The client seide cert/key are needed for connection to the VPN, but are not part
of the deployment requirements.

## Getting Set Up

The process for getting self-signed certs/keys and connection to the VPN are
included in this section. Other methods are possible (such as using real CA
signed cert/key files), but are not included here at this time.

### Generate Server-Side Certs and Keys

This process is adapted from the
[AWS Client VPN Administrator's Guide](https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/client-auth-mutual-enable.html)
as of the time of writing of thie README. If things don't work, try that guide
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
key/cert can be regenrated (or new ones can be made for new clients) at any time
from the server files and the PEM text only needs to be changed/inserted in the
`ovpn` file if they are regenerated or new ones are created.

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
easyrsa build-client-full client1.domain.tld nopass
```

-   at this point, all files needed for the deployment and the vpn connection
    exist (as long as only one client cert/key pair is desired).

-   **_TODO_**
    -   setup in the pulumi config (and repo setp t ignore default tls path)
    -   how to connect to vpn (getting config, adding clinet cert/key, connect)
    -   routes section (below)

## Routes
