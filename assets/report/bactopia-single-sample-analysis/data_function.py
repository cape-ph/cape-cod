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


def data_function(event, context):
    """Return data required for the bactopia single sample analysis report.

    :param event: The event object that contains the calling lambda event data.
    :param context: Context object.
    """

    headers = event.get("headers", {})

    # payload will contain any data from the calling lambda that needs to
    # propagate to the data function
    payload = event.get("Payload")

    # TODO: put in athena query to get data of interest. this lambda
    #       function could end up being a more utilitarian "run some athena
    #       query" generalization where the payload from the caller has some
    #       named athena query to run along with values to apply to the
    #       query before running (such as a sample id, etc). unclear at this
    #       time if data functions will be super specialized for one task or
    #       if we can have one function serve many needs

    # unlike the api lambda functions, there isn't really a need to return a
    # dict representing an http response. just send the data back (the caller
    # will get a response object with this data being the value of the
    # "Payload" key
    return FAKE_TEMPLATE_DATA
