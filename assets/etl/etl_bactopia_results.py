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
AMRFINDERPLUS_LEGACY_OBJ = "amrfinderplus-proteins.tsv"
AMRFINDERPLUS_OBJ = "amrfinderplus.tsv"
# file which contains the command used to execute bactopia
SOFTWARE_VERSION_OBJ = "software_versions.yml"

# TODO: These are the keys we care about matching and processing right now.
#       this is not exhaustive in the long term and really only supports
#       our current single run use case of bactopia.

# these names are looked for explicitly if the object is in the bactopia output
# hierarchy
BACTRUN_FILES = [
    # Keep the legacy AMRFinderPlus filename separate from the current
    # output-contract filename.
    {"prefix": "merged-results/", "key": AMRFINDERPLUS_LEGACY_OBJ},
    {"prefix": "merged-results/", "key": AMRFINDERPLUS_OBJ},
    {"prefix": "merged-results/", "key": MLST_OBJ},
    {"prefix": "software-versions/", "key": SOFTWARE_VERSION_OBJ},
]


class BactopiaOutputContractV1Adapter:
    """Parse the stable Bactopia output contract v1 merged-results."""

    MLST_INPUT_HEADER = (
        "FILE",
        "SCHEME",
        "ST",
        "STATUS",
        "SCORE",
        "ALLELES",
    )
    MLST_OUTPUT_HEADER = (
        "file",
        "scheme",
        "st",
        "status",
        "score",
        "alleles",
    )
    AMRFINDER_REPORT_COLUMNS = frozenset(
        {
            "element_symbol",
            "element_name",
            "scope",
            "subtype",
            "class",
            "subclass",
            "type",
            "method",
            "%_coverage_of_reference",
            "%_identity_to_reference",
        }
    )

    def parse_mlst(self, source_bytes):
        """Return normalized MLST rows for the output contract."""

        rows = list(
            csv.reader(
                io.StringIO(source_bytes.decode("utf-8")), delimiter="\t"
            )
        )
        if not rows:
            raise ValueError("Output contract v1 MLST output is empty")

        header = tuple(cell.strip().upper() for cell in rows[0])
        if header != self.MLST_INPUT_HEADER:
            raise ValueError(
                "Unexpected output contract v1 MLST header. "
                f"Expected {self.MLST_INPUT_HEADER}, received {header}"
            )

        output = [self.MLST_OUTPUT_HEADER]
        for line_number, row in enumerate(rows[1:], start=2):
            if not row:
                continue
            if len(row) != len(self.MLST_INPUT_HEADER):
                raise ValueError(
                    "Unexpected output contract v1 MLST row width at line "
                    f"{line_number}: expected {len(self.MLST_INPUT_HEADER)}, "
                    f"received {len(row)}"
                )
            output.append(row)
        return output

    def parse_amrfinderplus(self, source_bytes):
        """Normalize and validate AMRFinderPlus report-query columns."""

        rows = list(
            csv.reader(
                io.StringIO(source_bytes.decode("utf-8")), delimiter="\t"
            )
        )
        if not rows:
            raise ValueError("Output contract v1 AMRFinderPlus output is empty")

        header = [re.sub(r"[\s-]", "_", cell).lower() for cell in rows[0]]
        missing = sorted(self.AMRFINDER_REPORT_COLUMNS - set(header))
        if missing:
            raise ValueError(
                "Output contract v1 AMRFinderPlus output is missing required "
                f"columns: {', '.join(missing)}"
            )

        output = [header]
        for line_number, row in enumerate(rows[1:], start=2):
            if row and len(row) != len(header):
                raise ValueError(
                    "Unexpected output contract v1 AMRFinderPlus row width "
                    f"at line {line_number}: expected {len(header)}, "
                    f"received {len(row)}"
                )
            output.append(row)
        return output


OUTPUT_ADAPTER = BactopiaOutputContractV1Adapter()


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
        print(f"Processing MLST file (raw key: {alert_obj_key})")
        writer.writerows(OUTPUT_ADAPTER.parse_mlst(etl_job.get_src_file()))

    elif objfull == AMRFINDERPLUS_OBJ:
        print(f"Processing AMRFinderPlus file (raw key: {alert_obj_key})")
        writer.writerows(
            OUTPUT_ADAPTER.parse_amrfinderplus(etl_job.get_src_file())
        )

    elif objfull == AMRFINDERPLUS_LEGACY_OBJ:
        print(
            f"Processing legacy AMRFinderPlus file (raw key: {alert_obj_key})"
        )
        reader = csv.reader(
            io.StringIO(etl_job.get_src_file().decode("utf-8")), delimiter="\t"
        )
        for idx, row in enumerate(reader):
            if idx == 0:
                row = [re.sub(r"[\s-]", "_", c).lower() for c in row]
            writer.writerow(row)

    elif objfull == SOFTWARE_VERSION_OBJ:
        print(f"Processing software versions file (raw key: {alert_obj_key})")
        writer.writerow(
            [
                "id",
                "bactopia_version",
                "run_date",
                "input_file",
                "parameter_name",
            ]
        )
        software_version = yaml.safe_load(etl_job.get_src_file())
        bactopia_version = software_version.get("Workflow", {}).get(
            "bactopia", None
        )
        command = software_version.get("Workflow", {}).get("command", None)
        run_date = software_version.get("Workflow", {}).get("date", None)
        if command:
            parts = shlex.split(command)
            id = 1
            for i, part in enumerate(parts):
                parameter_name = parts[i - 1] if i > 0 else None
                if part.startswith("s3://") and parameter_name != "-work-dir":
                    writer.writerow(
                        [id, bactopia_version, run_date, part, parameter_name]
                    )
                    id += 1

    etl_job.write_sink_file(sio_buff.getvalue(), clean_obj_key)
