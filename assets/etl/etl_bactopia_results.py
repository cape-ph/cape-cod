"""ETL script for the initial subset of bactopia results we'll handle."""

import csv
import io
import os
import re
import shlex

import yaml
from capepy.aws.glue import EtlJob

etl_job = EtlJob()

# partition/column name
BACTRUN_PARTITION = "bactopia_run"
# the files of interest (needed to handle each differently)
MLST_OBJ = "mlst.tsv"
# the versions of the bactopia toolchain seem to have different names of this
# file in the output. this could be a bactopia or amrfinder plus reason, but the
# amrfinderplus file from bactopia version 3.0.1 (and maybe before???) has
# `-proteins` and later versions (at least 3.1.0+) don't.
AMRF_OBJ_301 = "amrfinderplus-proteins.tsv"
AMRF_OBJ_31X = "amrfinderplus.tsv"
# file which contains the command used to execute bactopia
SOFTWARE_VERSION_OBJ = "software_versions.yml"

# TODO: These are the keys we care about matching and processing right now.
#       this is not exhaustive in the long term and really only supports
#       our current single run use case of bactopia.

# these names are looked for explicitly if the object is in the bactopia output
# hierarchy
BACTRUN_FILES = [
    # different versions of the bactopia tool chainss have different names for
    # the amr finder files it seems
    {"prefix": "merged-results/", "key": AMRF_OBJ_301},
    {"prefix": "merged-results/", "key": AMRF_OBJ_31X},
    {"prefix": "merged-results/", "key": MLST_OBJ},
    {"prefix": "software-versions/", "key": SOFTWARE_VERSION_OBJ},
]


# TODO: ISSUE #144 the output here is for the initial bactopia
#       data handling only (and is specific to a particular invocation of
#       bactopia that is not the only way we care about). It is by no means
#       something that must be carried forward if there is a better way

# before anything else, make sure this object key is one we care about
# and if so grab all the parts of it we need
process_object = False
prefix = None
objfull = None
objname = None
suffix = None

alert_obj_key = etl_job.parameters["OBJECT_KEY"]
for file in BACTRUN_FILES:
    if alert_obj_key.endswith(f"{file['prefix']}{file['key']}"):
        # in the case of bactopia output files, we'll want the first 2 parts of
        # the original prefix (e.g. 'bactopia-runs/bactopia-20241008-183748/')
        # and the object name sith suffix. conveniently this means we can just
        # split on "merged-results/"
        prefix, objfull = alert_obj_key.split(file["prefix"])
        _, prefix = prefix.split("bactopia-runs/")
        # if we have an old named amrfinder plus file, rename the output name to be
        # the asme as the newer ones
        objname, suffix = objfull.split(".")
        break


# we should have no missing values here
if not all([prefix, objfull, objname, suffix]):
    print(f"Bactopia output ETL ignoring {alert_obj_key} per configuration.")
    # TODO: this shows the job as failed AWS console. need this to still be able
    #       to be considered a success.
    os._exit(0)

print(
    f"Proceeding with bactopia output processing with prefix [{prefix}], "
    f"objfull [{objfull}], objname [{objname}], and suffix [{suffix}] "
)

clean_obj_key = os.path.join(
    f"{objname}", f"{BACTRUN_PARTITION}={prefix}", f"{objname}.csv"
)

# handle the document itself...
print(f"Processing new object: {alert_obj_key}")

# TODO: the only real special case here is the mlst.tsv file which has no column
#       headers. otherwise we're really just going to copy the file over to a
#       new path with a new suffix
with io.StringIO() as sio_buff:
    writer = csv.writer(sio_buff)

    # NOTE: based on file name matching above, we should never end up where an
    #       if/elif is not hit here
    if objfull == MLST_OBJ:
        # in the mlst.tsv case, we have no header row and need to provide our
        # own
        print(f"Processing MLST file (raw key: {alert_obj_key})")
        reader = csv.reader(
            io.StringIO(etl_job.get_src_file().decode("utf-8")), delimiter="\t"
        )

        # TODO: these headers are made up except for the first 3. this will
        #       need to be fixed sometime if we keep processing this file
        writer.writerow(
            [
                "sample",
                "scheme",
                "sequence_type",
                *[f"gene{i}" for i in range(7)],
            ]
        )
        writer.writerows([row for row in reader])

    elif objfull in [AMRF_OBJ_301, AMRF_OBJ_31X]:
        print(f"Processing AMRFinderPlus file (raw key: {alert_obj_key})")
        reader = csv.reader(
            io.StringIO(etl_job.get_src_file().decode("utf-8")), delimiter="\t"
        )
        # in this case we need to grab the header and modify it to replace
        # spaces and dashes with underscores, and lowercase everything
        for idx, row in enumerate(reader):
            if idx == 0:
                # TODO: ISSUE #TBD ETL helper library needs a normalization
                #       function for column headers to do this...

                # special processing of the columns
                row = [re.sub(r"[\s-]", "_", c).lower() for c in row]

            writer.writerow(row)

    elif objfull == SOFTWARE_VERSION_OBJ:
        print(f"Processing software versions file (raw key: {alert_obj_key})")
        writer.writerow(["id", "input_file", "parameter_name"])
        software_version = yaml.safe_load(etl_job.get_src_file())
        command = software_version.get("Workflow", {}).get("command", None)
        if command:
            parts = shlex.split(command)
            id = 1
            for i, part in enumerate(parts):
                parameter_name = parts[i - 1] if i > 0 else None
                if part.startswith("s3://") and parameter_name != "-work-dir":
                    writer.writerow([id, part, parameter_name])
                    id += 1

    etl_job.write_sink_file(sio_buff.getvalue(), clean_obj_key)
