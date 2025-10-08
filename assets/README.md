# Assets

**DO NOT MANAGE ALL ASSETS HERE LONG TERM**

Many files under the `assets` directory in the repo are just to get things
going. We do not want to maintain all assets in here in the long run. A lot of
these should be managed in specific repos that are maintained separately and
have their own lifecycle. We eventually want those hooked up to CI/CD that write
the assets to the bucket locations as a build step or have this repo pull them
based on configuration at deploy time.

For now we will need to ensure these assets are up to date with the versions in
their respective repos if those exist (e.g. some ETL functions), and if they are
updated (bug fixes, etc) in the repos, they need to be manually updated here.

## Source Repos

### ETL

- `etl/etl_gphl_cre_alert.py` - from
  [etl-gphl-cre-alert](https://github.com/cape-ph/etl-gphl-cre-alert)
- `etl/etl_tnl_alert.py` - from
  [etl-tnl-alert](https://github.com/cape-ph/etl-tnl-alert)
- `etl/etl_gphl_sequencing.py` - from
  [etl-gphl-sequencing-alert](https://github.com/cape-ph/etl-gphl-sequencing-alert)
