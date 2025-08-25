"""Lambda for data retrieval for the bactopia single sample analysis report."""

# TODO:
# need a layer with weasyprint and jinja2
# - need this to be a lambda that returns (for now) this fake data.
# - when we have the actual athena query, we will return data from the lake
#   based on an incoming single sample analysis jobid
import datetime
import json
import logging

from botocore.exceptions import ClientError
from capepy.aws.utils import decode_error

logger = logging.getLogger()
logger.setLevel("INFO")

# TODO: this is to be replaced with a call to an athena query eventually. format
#       is speculative (though tied to the report template using this data, so
#       if this changes that needs to as well.
FAKE_TEMPLATE_DATA = {
    "sample_id": "0123456789",
    "sample_type": "Environmental",
    "sample_matrix": "Soil",
    "sample_collection_date": (
        datetime.datetime.fromisoformat(
            "2025-08-15T14:36:28.024649+00:00"
        ).strftime("%Y-%m-%d %H:%M %Z")
    ),
    "sample_collection_location": "Back yard",
    "pipeline_meta": {
        "name": "Bactopia",
        "version": "3.0.2",
        "run_date": (
            datetime.datetime.fromisoformat(
                "2025-08-15T16:22:33.024649+00:00"
            ).strftime("%Y-%m-%d %H:%M %Z")
        ),
    },
    "organisms_identified": [
        {
            "family": "Simpson",
            "genus": "Bart",
            "species": "Shorts",
            "strain": "Eat My",
        },
        {
            "family": "Griffin",
            "genus": "Meg",
            "species": "Hat",
            "strain": "Fungus",
        },
        {
            "family": "Smith",
            "genus": "Morty",
            "species": "Plumbus",
            "strain": "Schmeckles",
        },
    ],
    "virulence_info": {
        "exact_protein_match": [
            {
                "element_symbol": "Pu",
                "element_name": "Plutonium",
                "scope": "micro",
                "subtype": "sure?",
                "class": "IO",
                "subclass": "BytesIO",
            },
            {
                "element_symbol": "Es",
                "element_name": "Einsteinium",
                "scope": "ortho",
                "subtype": "no, thank you",
                "class": "Exception",
                "subclass": "OSError",
            },
        ],
        "similarity_based_protein_match": [
            {
                "element_symbol": "Sr",
                "element_name": "Strontium",
                "scope": "stetho",
                "subtype": "dr giggles",
                "class": "List",
                "subclass": "DoublyLinked",
                "reference_coverage": "23",
                "reference_identity": "10",
            },
            {
                "element_symbol": "Fl",
                "element_name": "Flerovium",
                "scope": "oscillo",
                "subtype": "yes",
                "class": "object",
                "subclass": "myobject",
                "reference_coverage": "54",
                "reference_identity": "41",
            },
        ],
    },
    "amr_info": {
        "exact_protein_match": [
            {
                "element_symbol": "Sb",
                "element_name": "Antimony",
                "scope": "mouthwash",
                "subtype": "non-alcoholic",
                "class": "collection",
                "subclass": "OrderedDict",
            },
            {
                "element_symbol": "Fr",
                "element_name": "Francium",
                "scope": "endo",
                "subtype": "tube",
                "class": "Reader",
                "subclass": "CsvReader",
            },
        ],
        "similarity_based_protein_match": [
            {
                "element_symbol": "Xe",
                "element_name": "Xenon",
                "scope": "roto",
                "subtype": "tolkien",
                "class": "Head of the",
                "subclass": "Arvid",
                "reference_coverage": "90",
                "reference_identity": "70",
            },
            {
                "element_symbol": "Nh",
                "element_name": "Nihonium",
                "scope": "kaleido",
                "subtype": "fractal",
                "class": "stream",
                "subclass": "iostream",
                "reference_coverage": "87",
                "reference_identity": "34",
            },
        ],
    },
}


def index_handler(event, context):
    """Return data required for the bactopia single sample analysis report.

    If there is no `Authorization` header present, this will return a 401.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    try:

        headers = event.get("headers", {})
        payload = event.get("Payload")

        print(f"Payload from calling lambda: {payload}")

        # TODO: eventually this needs to be replaced with an athena query
        resp_data = FAKE_TEMPLATE_DATA

        # assume the best will happen and set our output up for success
        resp_status = 200
        resp_headers = {
            "Content-Type": "application/json",
            # TODO: ISSUE #141 CORS bypass. We do not want this long term.
            #       When we get all the api and web resources on the same
            #       domain, this may not matter too much. But we may
            #       eventually end up with needing to handle requests from
            #       one domain served up by another domain in a lambda
            #       handler. In that case we'd need to be able to handle
            #       CORS, and would want to look into allowing
            #       configuration of the lambda (via pulumi config that
            #       turns into env vars for the lambda) that set the
            #       origins allowed for CORS.
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
        }

        # And return our response however it ended up
        return {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": json.dumps(resp_data),
        }
    except ClientError as err:
        code, message = decode_error(err)

        msg = (
            f"Error during fetch of bactopia single sample analysis report "
            f"data. {code} "
            f"{message}"
        )

        return {
            "statusCode": 500,
            "body": msg,
        }
