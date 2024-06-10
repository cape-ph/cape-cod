# Assets

**DO NOT MANAGE ASSETS HERE LONG TERM**

The files under the `assets` directory in the repo are just to get things
going. We do not want to maintain assets in here in the long run. These are
(for the most part) assets from other repos that are maintained separately.
We eventually want those hooked up to CI/CD that write the assets to the
bucket locations as a build step.

For the purposes of the datalake demo and until we get the CI/CD working, we
will need to ensure these assets are up to date with the versions in their
respective repos, and if they are updated (bug fixes, etc) in the repos, they
need to be manually updated here.

## Source Repos

### ETL

-   `etl/etl_gphl_cre_alert.py` - from [etl-gphl-cre-alert](https://github.com/cape-ph/etl-gphl-cre-alert)
-   `etl/etl_tnl_alert.py` - from [etl-tnl-alert](https://github.com/cape-ph/etl-tnl-alert)
