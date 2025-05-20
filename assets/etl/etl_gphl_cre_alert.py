"""ETL script for raw Epi/HAI CRE alert docx."""

import io

import dateutil.parser as dparser
import pandas as pd
from capepy.aws.glue import EtlJob
from docx import Document

etl_job = EtlJob()

# NOTE: for now we'll take the alert object key and change out the file
#       extension for the clean data (leaving all namespacing and such). this
#       will probably need to change
clean_obj_key = etl_job.parameters["OBJECT_KEY"].replace(".docx", ".csv")

# the response should contain a StreamingBody object that needs to be converted
# to a file like object to make the docx library happy
document = Document(io.BytesIO(etl_job.get_src_file()))

# NOTE: this document is assumed to contain a single table that needs to be
#       processed and nothing else. The file consists of:
#       - a 2 column header row that contains a column (0 index) with the alert
#         report date, which we need (rest of this row can be ignored)
#       - another header row that contains all the column names for the table
#       - rows of data
table = document.tables[0]
data = [[cell.text for cell in row.cells] for row in table.rows]
data = pd.DataFrame(data)

# grab the alert report date
date_received = pd.to_datetime(dparser.parse(data.iloc[0, 0], fuzzy=True))
# get the column list
data.columns = data.loc[1]
# drop the rows we no longer need (date and columns)
data.drop([0, 1], inplace=True)
data.reset_index(drop=True, inplace=True)

# now perform the ETL on the data rows
# NOTE: Questions about the data:
#           - Do we need to split this name to better enable queries later?
#           - will the name only ever be composed of first and last (i.e. no
#             middle name handling)?
#           - do we not want the lab id to carry over into clean data? same
#             with organism id (and anything else that doesn't carry over
#             currently). there's very little penalty (storage cost) for it
#             carrying over, and if it's not part of the AR log, we just don't
#             include it in the AR query, but we still have it if we end up
#             needing it for anything else
interim = pd.DataFrame()
interim["Mechanism (*Submitters Report)"] = data[
    "Anti-Microbial Resistance RT-PCR"
]
interim["Organism"] = data["Organism ID"]
interim["Date Received"] = date_received
interim["Date Reported"] = date_received
interim["Patient Name"] = data["Patient Name"]
interim["DOB"] = pd.to_datetime(data["DOB"], errors="coerce")
interim["Source"] = data["Source"].str.capitalize()
interim["Date of Collection"] = pd.to_datetime(
    data["Date of Collection"], errors="coerce"
)
interim["Testing Lab"] = "GPHL"
interim["State Lab ID"] = data["Lab ID"]
interim["Facility of Origin"] = data["Received from"]

# write out the transformed data
with io.StringIO() as csv_buff:
    interim.to_csv(csv_buff, index=False)
    etl_job.write_sink_file(csv_buff.getvalue(), clean_obj_key)
