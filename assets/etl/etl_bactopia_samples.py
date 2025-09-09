"""ETL script for the initial subset of bactopia results we'll handle."""

import csv
import io
import os
import re
from pathlib import Path

from capepy.aws.glue import EtlJob

etl_job = EtlJob()


def parse_sample_tsv(path):
    print(f"Processing sample tsv file (raw key: {path})")
    return list(
        csv.reader(
            io.StringIO(etl_job.get_src_file().decode("utf-8")), delimiter="\t"
        )
    )


def parse_mash_txt(path):
    print(f"Processing mash txt file (raw key: {path})")
    return list(
        csv.reader(
            io.StringIO(etl_job.get_src_file().decode("utf-8")), delimiter="\t"
        )
    )


def parse_sourmash_txt(path):
    print(f"Processing sourmash txt file (raw key: {path})")
    return list(csv.reader(io.StringIO(etl_job.get_src_file().decode("utf-8"))))


SAMPLE_FILETYPES = [
    {
        "pattern": r".*(.*)/main/assembler/\1.tsv$",
        "parser": parse_sample_tsv,
        "table_name": "assembler",
    },
    {
        "pattern": r".*(.*)/main/sketcher/\1-mash-refseq88-k21.txt$",
        "parser": parse_mash_txt,
        "table_name": "mash-refseq88-k21",
    },
    {
        "pattern": r".*(.*)/main/sketcher/\1-sourmash-gtdb-rs207-k31.txt$",
        "parser": parse_sourmash_txt,
        "table_name": "sourmash-gtdb-rs207-k31",
    },
]


# TODO: ISSUE #144 the output here is for the initial bactopia
#       data handling only (and is specific to a particular invocation of
#       bactopia that is not the only way we care about). It is by no means
#       something that must be carried forward if there is a better way

# before anything else, make sure this object key is one we care about
# and if so grab all the parts of it we need
sample_id = None
obj_path = None
parser = None
table_name = None

alert_obj_key = etl_job.parameters["OBJECT_KEY"]
for filetype in SAMPLE_FILETYPES:
    matches = re.match(filetype["pattern"], alert_obj_key)
    if matches:
        sample_id = matches.group(1)
        obj_path = Path(alert_obj_key)
        parser = filetype["parser"]
        table_name = filetype["table_name"]
        break


# we should have no missing values here
if not all([sample_id, obj_path, parser, table_name]):
    print(f"Bactopia output ETL ignoring {alert_obj_key} per configuration.")
    os._exit(0)

print(
    f"Proceeding with bactopia output processing with prefix [{sample_id}] "
    f"and path {obj_path}"
)

clean_obj_key = os.path.join(
    f"{table_name}",
    f"sample_id={sample_id}",
    f"{obj_path.stem}.csv",
)

# handle the document itself...
print(f"Processing new object: {alert_obj_key}")

with io.StringIO() as sio_buff:
    # Use identified parser to write to sio_buff
    csv.writer(sio_buff).writerows(parser(obj_path))
    # Write sio_buff to the sink file
    etl_job.write_sink_file(sio_buff.getvalue(), clean_obj_key)
