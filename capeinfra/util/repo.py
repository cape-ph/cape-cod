"""Module relating to repository actions (e.g. downloading a github release)"""

import urllib.request


def get_github_release_artifact(
    repo_url: str,
    artifact_name: str,
    version: str = "latest",
    dl_loc: str = "/tmp",
) -> str | None:
    """Download the given release artifact and return the local path or None.

    NOTE: Currently the only error checking done on the downloaded file is to
    check for non-0 filesize. In that case None will be returned.

    Args:
        repo_url: The github repository URL (should not include `.git`)
        artifact_name: The name of the release artifact to get.
        version: The version of the release artifact to get. Defaults to
                 `latest`, which may not be valid for the given repo.
        dl_loc: A local download location for the artifact. Defaults to `/tmp`.
    """

    artifact_url = "/".join(
        [repo_url, "releases", "download", version, artifact_name]
    )

    dl_pth = "/".join([dl_loc, artifact_name])
    local_pth, http_msg = urllib.request.urlretrieve(artifact_url, dl_pth)

    # TODO: better verification than checking for non-0 file size.
    return local_pth if int(http_msg.get("Content-Length")) else None
