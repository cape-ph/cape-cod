"""ETL script for raw Epi/HAI Tennessee health lab alert xlsx."""

import io
import re

import pandas as pd
from capepy.aws.glue import EtlJob

# Instantiate the ETL Job using capepy
etl_job = EtlJob()

# TODO:
#   - add error handling for the format of the document being incorrect
#   - figure out how we want to name and namespace clean files (e.g. will we
#     take the object key we're given, strip the extension and replace it with
#     one for the new format, or will we do something else)
#   - see what we can extract out of here to be useful for other ETLs. imagine
#     we'd have a few different things that could be made into a reusable
#     package

OUT_COL_NAMES = [
    "Empty",
    "Testing-Results",
    "State",
    "Date_Received",
    "Date_Reported",
    "Last_Name",
    "First_Name",
    "DOB",
    "State_Lab_ID",
    "Specimen",
    "Date_Collection",
    "Submitting_Facility",
    "Sample_Collection_Facility",
    "Known_Positive",
    "Colonization_Detected",
]

# NOTE: The data in this spreadsheet can take a few different forms based on
#       pathogen. This could change in the future. The spreadsheet (regardless
#       of pathogen) does have the same general format and is assumed to
#       contain a single worksheet with a table that needs to be processed,
#       and nothing else. The table consists of:
#       - a 1 column header row that can be ignored
#       - another header row that contains all the column names for the table
#       - rows of data
data = pd.read_excel(etl_job.get_raw_file(), engine="openpyxl", skiprows=1)

# strip out the ingorable header and reset the index
data[1:].reset_index(drop=True, inplace=True)

data.columns = OUT_COL_NAMES

# Output Column Creation
interim = pd.DataFrame()

# TODO: Right now we know of 2 formats the data in these alerts can take on
#       based on organism being alerted about (really, just the data in the
#       column `Description of Testing Completed and Results (including
#       organism name)`). There is one format for Candidia auris and one
#       format for all others we know of right now. The processing needs will
#       be slightly different for this cell and we need a way to know which
#       format to parse. Ideally we'd work with the producers of the alerts
#       and see if we can get all alerts put into a similar format, but for
#       right now we'll check for the substring 'Candida auris' in the first
#       non-header row and react based on that (TODO: SUPER BRITTLE).
if data["Testing-Results"].iloc[1].find("Candida auris") > 0:
    # get a list of pairs of (mechanism, organism) from manipulating the incoming
    # data column
    pairs = [
        (m.strip(), o.strip())
        for m, o in list(map(lambda x: x.split("-"), data["Testing-Results"]))
    ]
    # extract the lists and put them in the right places
    interim["Mechanism (*Submitters Report)"], interim["Organism"] = zip(*pairs)
else:
    # pattern for the organism part
    # NOTE: This is brittle. It banks on the organism always being the format
    #      `X. whatevs ,`, so if the origanism is ever fully spelled out or
    #      anything, this will break. We need to see if we can get a common
    #      format for everything in this first column.
    # NOTE:doing the following for loop as a list comp caused the LSP to
    #      bug out because a non-match in `re.search` returns `None`, and
    #      `group` is not an attribute of `None`. so went with a for loop
    org_pattern = r"([A-Z]\..*?)(?=,)"
    # compiled pattern so we only compile once
    comp_pattern = re.compile(org_pattern)
    pairs = []
    for s in data["Testing-Results"]:
        search = comp_pattern.search(s)
        pairs.append(
            (
                re.sub(org_pattern, "", s),
                search.group(0) if search else "UNKNOWN",
            )
        )

    # extract the lists and put them in the right places
    interim["Mechanism (*Submitters Report)"], interim["Organism"] = zip(*pairs)

interim["Date Received"] = pd.to_datetime(
    data["Date_Received"], errors="coerce"
)
interim["Date Reported"] = pd.to_datetime(
    data["Date_Reported"], errors="coerce"
)
interim["Patient_Name"] = data.apply(
    lambda x: "{Last_Name}, {First_Name}".format(**x), axis=1
)
interim["DOB"] = pd.to_datetime(data["DOB"], errors="coerce")
interim["Source"] = data["Specimen"].apply(lambda x: x.capitalize())
interim["Date of Collection"] = pd.to_datetime(
    data["Date_Collection"], errors="coerce"
)
interim["Testing Lab"] = "TNL"
interim["State_Lab_ID"] = data["State_Lab_ID"]

# write out the transformed data
with io.StringIO() as csv_buff:
    interim.to_csv(csv_buff, index=False)
    etl_job.write_clean_file(
        csv_buff.getvalue(),
        etl_job.parameters["OBJECT_KEY"].replace(".xlsx", ".csv"),
    )
