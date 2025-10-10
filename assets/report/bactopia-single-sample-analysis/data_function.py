"""Lambda for data retrieval for the bactopia single sample analysis report."""

# TODO:
# need a layer with weasyprint and jinja2
# - need this to be a lambda that returns (for now) this fake data.
# - when we have the actual athena query, we will return data from the lake
#   based on an incoming single sample analysis jobid
import datetime
import json
import logging

import awswrangler as wr
import boto3
from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger()
logger.setLevel("INFO")

METADATA_QRY_TEMPLATE = """
select
    -- collection metadata
    m.sample_id, m.sample_type, m.sample_matrix, m.sample_collection_date,
    m.sample_collection_location,
    -- pipeline information
    rsv.run_date, rsv.bactopia_version, 'bactopia' AS pipeline_name
from
    "{database}"."input_ccd_dlh_t_seqauto_input_clean_vbkt_s3_b1f75c7" as m
join
    "{database}"."result_software_versions" as rsv on
    rsv.input_file=m.sequencing_reads
where
    m.sample_id='{sample_id}' and
    rsv.parameter_name='--ont';
"""

SPECIES_INFO_QRY_TEMPLATE = """
select
    -- organism identitifaction
    rsrmsh.family, rsrmsh.genus, rsrmsh.species, rsrmsh.strain
from
    "{database}"."result_sourmash_gtdb_rs207_k31" as rsrmsh
where
    rsrmsh.id='{sample_id}'
"""

VIRULENCE_INFO_QRY_TEMPLATE = """
select
    -- virulence information
    ramrfp.element_symbol, ramrfp.element_name,
    ramrfp.scope,
    ramrfp.subtype,
    ramrfp.class, ramrfp.subclass,
    ramrfp."%_coverage_of_reference", ramrfp."%_identity_to_reference",
    -- needed for filtering of results
    ramrfp.type, ramrfp.method
from
    "{database}"."input_ccd_dlh_t_seqauto_input_clean_vbkt_s3_b1f75c7" as m
join
    "{database}"."result_software_versions" as rsv on
    rsv.input_file=m.sequencing_reads
join
    "{database}"."result_amrfinderplus" as ramrfp on
    ramrfp.bactopia_run=rsv.bactopia_run
where
    m.sample_id='{sample_id}' and
    rsv.parameter_name='--ont';
"""


def data_function(event, context):
    """Return data required for the bactopia single sample analysis report.

    :param event: The event object that contains the calling lambda event data.
    :param context: Context object.
    """

    # event will contain any data from the calling lambda that needs to
    # propagate to the data function
    sample_id = event.get("sample_id", None)

    if not sample_id:
        msg = f"No sample id given for report. Data function cannot continue"
        logger.error(msg)
        raise ValueError(msg)

    # TODO: this lambda function could end up being a more utilitarian "run
    #       some athena query" generalization where the payload from the caller
    #       has some named athena query to run along with values to apply to
    #       the query before running (such as a sample id, etc). unclear at
    #       this time if data functions will be super specialized for one task
    #       or if we can have one function serve many needs

    # TODO: this is very hard coded for a single demo use case right not. deal
    #       with it...

    athena = boto3.client("athena")

    catalog = next(
        catalog["CatalogName"]
        for catalog in athena.list_data_catalogs()["DataCatalogsSummary"]
    )

    databases = athena.list_databases(CatalogName=catalog)["DatabaseList"]
    database = next(
        (db["Name"] for db in databases if "seqauto-catalog" in db["Name"]),
        None,
    )

    report_data = {}

    if database is not None:

        meta_df = wr.athena.read_sql_query(
            sql=METADATA_QRY_TEMPLATE.format(
                database=database, sample_id=sample_id
            ),
            database=database,
        )

        species_df = wr.athena.read_sql_query(
            sql=SPECIES_INFO_QRY_TEMPLATE.format(
                database=database, sample_id=sample_id
            ),
            database=database,
        )

        virulence_df = wr.athena.read_sql_query(
            sql=VIRULENCE_INFO_QRY_TEMPLATE.format(
                database=database, sample_id=sample_id
            ),
            database=database,
        )

        row = meta_df.iloc[0]

        run_dt = datetime.datetime.strptime(
            row["run_date"], "%Y-%m-%d %H:%M:%S.%f"
        )

        run_dt_aware = run_dt.replace(tzinfo=datetime.timezone.utc)
        report_data = {
            "sample_id": row["sample_id"],
            "sample_type": row["sample_type"],
            "sample_matrix": row["sample_matrix"],
            "sample_collection_date": (
                datetime.datetime.fromisoformat(
                    row["sample_collection_date"]
                ).strftime("%Y-%m-%d %H:%M %Z")
            ),
            "sample_collection_location": row["sample_collection_location"],
            "pipeline_meta": {
                "name": row["pipeline_name"],
                "version": row["bactopia_version"],
                "run_date": (run_dt_aware.strftime("%Y-%m-%d %H:%M %Z")),
            },
        }

        report_data["organisms_identified"] = species_df.to_dict(
            orient="records"
        )

        report_data.setdefault(
            "virulence_info",
            {"exact_protein_match": [], "similarity_based_protein_match": []},
        )

        report_data.setdefault(
            "amr_info",
            {"exact_protein_match": [], "similarity_based_protein_match": []},
        )

        for index, row in virulence_df.iterrows():
            type_key = None
            match_key = None
            if row["type"] == "VIRULENCE":
                # goes in virulence info
                type_key = "virulence_info"
                if row["method"] == "EXACTP":
                    match_key = "exact_protein_match"
                else:
                    match_key = "similarity_based_protein_match"
            elif row["type"] == "AMR":
                # goes in amr_info
                type_key = "amr_info"
                if row["method"] == "EXACTP":
                    match_key = "exact_protein_match"
                else:
                    match_key = "similarity_based_protein_match"
            else:
                # wtf?
                print(f"Unknown type found in virulence info: {row['type']}")
                continue

            d = {
                "element_symbol": row["element_symbol"],
                "element_name": row["element_name"],
                "scope": row["scope"],
                "subtype": row["subtype"],
                "class": row["class"],
                "subclass": row["subclass"],
            }

            if match_key == "similarity_based_protein_match":
                d.update(
                    {
                        "reference_coverage": row["%_coverage_of_reference"],
                        "reference_identity": row["%_identity_to_reference"],
                    }
                )

            report_data[type_key][match_key].append(d)

    else:
        msg = (
            f"Could not find Glue catalog database {database}. Data function "
            "cannot continue"
        )
        logger.error(msg)
        # TODO: what's the right exception for a missing database?
        raise Exception(msg)

    # unlike the api lambda functions, there isn't really a need to return a
    # dict representing an http response. just send the data back (the caller
    # will get a response object with this data being the value of the
    # "Payload" key
    return report_data
