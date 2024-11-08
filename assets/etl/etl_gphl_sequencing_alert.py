"""ETL script for raw Epi/HAI sequencing report pdf."""

import io
from datetime import datetime

from capepy.aws.glue import EtlJob
from pypdf import PdfReader
from tabula.io import read_pdf

etl_job = EtlJob()

# NOTE: for now we'll take the alert object key and change out the file
#       extension for the clean data (leaving all namespacing and such). this
#       will probably need to change
clean_obj_key = etl_job.parameters["OBJECT_KEY"].replace(".pdf", ".csv")

# the response should contain a StreamingBody object that needs to be converted
# to a file like object to make the pdf libraries happy
f = io.BytesIO(etl_job.get_raw_file())

try:
    # get the report date from the 4th line of the pdf
    reader = PdfReader(f)
    page = reader.pages[0]
    date_reported = page.extract_text().split("\n")[3].strip()
    datetime.strptime(date_reported, "%m/%d/%Y")
except ValueError as err:
    err_message = (
        f"ERROR - Could not properly read sequencing report date. "
        f"ETL will continue."
        f"{err}"
    )

    etl_job.logger.error(err_message)

    date_reported = ""

try:
    # get two tables from the pdf
    tables = read_pdf(f, multiple_tables=True, pages=2)
    assert isinstance(tables, list)
    mlst_st = tables[0]
    genes = tables[1]
except (IndexError, KeyError) as err:
    err_message = (
        f"ERROR - Could not properly read sequencing PDF tables. "
        f"ETL Cannot continue."
        f"{err}"
    )

    etl_job.logger.error(err_message)

    # NOTE: need to properly handle exception stuff here, and we probably
    #       want this going somewhere very visible (e.g. SNS topic or a
    #       perpetual log as someone will need to be made aware)
    raise Exception(err_message)

# filter the columns we need and join the tables together
interim = mlst_st[["Accession_ID", "WGS_ID", "MLST_ST"]]
genes_inter = genes.set_index("Unnamed: 0").T
genes_interim = genes_inter.filter(regex="(NDM|KPC|IMP|OXA|VIM|CMY)", axis=1)
interim = interim.join(genes_interim, on="WGS_ID")
interim["Date Reported"] = date_reported

# write out the transformed data
with io.StringIO() as csv_buff:
    interim.to_csv(csv_buff, index=False)
    etl_job.write_clean_file(csv_buff.getvalue(), clean_obj_key)
