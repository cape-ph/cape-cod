"""Lambda for handling GETs for listing public user attributes."""

import base64
import datetime
import io
import json
import logging

import boto3
import weasyprint
from botocore.exceptions import ClientError
from capepy.aws.dynamodb import CannedReportTable
from capepy.aws.utils import decode_error
from jinja2 import BaseLoader, Environment, TemplateNotFound

logger = logging.getLogger()
logger.setLevel("INFO")


# TODO: move into capepy utils. waiting for the capepy layer refactor in this
#       repo (moving to config/requirements.txt based layer definitions whereas
#       capepy is a class into itself right now) before doing too many more
#       capepy releases.
class S3Exception(Exception):
    pass


class S3TemplateLoader(BaseLoader):
    """Jinja2 template loader for templates on Amazon S3."""

    def __init__(self, bucket, prefix):
        self.bucket = bucket
        self.prefix = prefix

    def get_source(self, environment, template):
        """Override of get_source for loading an S3 template.

        Args:
            environment: Jinja2 environment. Ignored here.
            template: The name of the template to load.

        Returns:
            A tuple containing the template source as a string, the filename of
            the template and the reload helper for the template.
        """
        try:
            template_bytes = get_s3_object(
                self.bucket, f"{self.prefix}/{template}"
            )

            template_io = io.BytesIO(template_bytes)
            return (
                # source of template as a str
                template_io.read().decode("utf-8"),
                # name of the template
                f"{template}.html",
                # reload helper
                lambda: True,
            )
        except S3Exception as e:
            logger.error(e)

        raise TemplateNotFound(template)


# TODO: move into capepy utils. waiting for the capepy layer refactor in this
#       repo (moving to config/requirements.txt based layer definitions whereas
#       capepy is a class into itself right now) before doing too many more
#       capepy releases.
def get_s3_object(bucket, key):
    """Load an object as a file from S3.

    Args:
        bucket: The name of the bucket the object is housed in.
        key: The full key for the object in the named bucket.

    Returns: The contents of the object as bytes.
    """
    # Create an S3 client object
    s3_client = boto3.client("s3")

    response = s3_client.get_object(
        Bucket=bucket,
        Key=key,
    )

    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    if status != 200:
        err = f"ERROR - Could not get object {key} from bucket {bucket}."

        logger.error(err)

        # NOTE: need to properly handle exception stuff here, and we probably want
        #       this going somewhere very visible (e.g. SNS topic or a perpetual log
        #       as someone will need to be made aware)
        raise S3Exception(err)

    return response.get("Body").read()


# TODO: this could go into capepy as well. we will need an abstraction to run an
#       arbitrary athena query for many of these data functions, but wcould also
#       hit other data sources, so it's not strictly athena.
def get_report_data(fnarn: str, payload: dict | None = None):
    """Invoke a lambda data function by ARN and return the result.

    Args:
        fnarn: The ARN of the function to invoke.
        payload: A dict of data to pass to the lambda. If provided, this will be
                 marshalled to json and then encoded as utf-8 bytes.

    Returns:
        The result of the lambda invoke on success.

    Raises:
        Exception on non-successful status.
    """
    lambda_client = boto3.client("lambda")
    response = lambda_client.invoke(
        FunctionName=fnarn,
        # TODO: this is synchronous. eventually we probably want to move to
        #       asynchronous reports (i.e. generate -> store -> notify) in which
        #       case this would change (or be replaced with something like a
        #       report generation queue). In any event, this will cause us to
        #       pay for 2 lambdas at a time while this one does nothing but
        #       waits for the other to finish.
        InvocationType="RequestResponse",
        # this will give the data function execution log back to this caller. if
        # we have an error in getting report data, we'll log the issue here.
        LogType="Tail",
        # If we do not get a payload to pass to the lambda, we'll give it an
        # empty payload (None is not a valid value for this arg)
        Payload=(json.dumps(payload or {}).encode("utf-8")),
    )

    # RequestResponse types return 200 on success. Other invocation types have
    # different statii for success
    if response["StatusCode"] != 200 or response.get("FunctionError", None):
        # general error message for the exception
        msg = (
            f"Attempt to invoke report data function {fnarn} yielded "
            f"non-success status {response['StatusCode']}."
        )

        # more details for the log.
        errmsg = f"{msg}. Invoke log: {response['LogResult']}"
        if response.get("FunctionError", None):
            # if FunctionError exists, Payload will have more info
            errorinfo = response.get("Payload").read().decode("utf-8")
            errmsg = f"{errmsg} Error info: {errorinfo}"

        logger.error(f"{errmsg}")

        # NOTE: need to properly handle exception stuff here, and we probably want
        #       this going somewhere very visible (e.g. SNS topic or a perpetual log
        #       as someone will need to be made aware)
        raise Exception(msg)

    # The data in this particular response comes back in "Payload" (as opposed
    # to something like "Body" which some other reposnses use.
    # TODO: this assumes all report data comes back as json...
    return json.loads(response.get("Payload").read().decode("utf-8"))


def convert_report_format(report_html, format="html"):
    """Convert the format incoming HTML (if needed) and return a bytestream.

    Args:
        report_html: The rendered HTML string for a given report.
        format: The format the output file should be in (e.g. "html", "pdf")
                assuming the format conversion is supported.

    Return:
        On success, a tuple containing the reported formatted for the response,
        additional headers for the response, and additional values for the
        reposnse.

    Raises:
        Exception on invalid format specified.
    """

    def encode_binary_report_format(report_bytes):
        """Base64 encode a binary report to make API Gateway happy.

        API Gateway handles text formats fine, but needs binary formats base64
        encoded so they can be treated as strings. This needs to be undone on
        the client side.

        Args:
            report_bytes: The contents of the report as bytes.

        Returns:
            The report_bytes base64 encoded and an additional values dict with
            the value specifying this encoding.
        """
        return base64.b64encode(report_bytes).decode("utf-8"), {
            "isBase64Encoded": True
        }

    additional_headers = {}
    additional_values = {}
    report_bytes = None

    match format:
        case "html":
            # in this case we already have html and will just return the
            # bytestream
            report_bytes = io.BytesIO(report_html.encode("utf-8")).getvalue()
            additional_headers.update({"Content-Type": "text/html"})
        case "pdf":
            # in this case we want to feed the html to the pdf engine then
            # return a base64 encoded bytestream on that
            wep_html = weasyprint.HTML(string=report_html, encoding="utf-8")
            pdf_io = io.BytesIO()
            wep_html.write_pdf(target=pdf_io)
            pdf_io.seek(0)
            report_bytes, addl_vals = encode_binary_report_format(
                pdf_io.getvalue()
            )
            additional_headers.update(
                {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": (
                        f"attachment;filename="
                        f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S-')}"
                        f"bactopia-report.pdf"
                    ),
                }
            )
            additional_values.update(addl_vals)
        case _:
            msg = (
                f"Cannot format report in requested format {format}. Format "
                f"not supported"
            )
            raise Exception(msg)

    return report_bytes, additional_headers, additional_values


def index_handler(event, context):
    """Handler for the GET for listing public user attributes.

    If there is no `Authorization` header present, this will return a 401.

    :param event: The event object that contains the HTTP request.
    :param context: Context object.
    """

    try:

        headers = event.get("headers", {})

        resp_data = {}

        # assume the best will happen and set our output up for success
        resp_status = 200
        resp_headers = {
            "Content-Type": "application/octet-stream",
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

        qsp = event.get("queryStringParameters")
        additional_values = {}
        additional_headers = {}

        # TODO: clean up, get a pattern for handling error and content type
        #       switching
        if qsp is None:
            resp_data = json.dumps(
                {
                    "message": "Missing required query string parameters: reportId"
                }
            )
            additional_headers["Content-Type"] = "application/json"
            resp_status = 400
        else:
            report_id = qsp.get("reportId")
            format = qsp.get("format", "html")

            if report_id is None:
                resp_data = json.dumps(
                    {
                        "message": "Missing required query string parameters: reportId"
                    }
                )
                additional_headers["Content-Type"] = "application/json"
                resp_status = 400
            else:
                ddb_table = CannedReportTable()

                report_item = ddb_table.get_report(report_id)

                if report_item is None:
                    logger.warning(
                        "Attempt to get report metadata for non-existent "
                        f"report id: {report_id}"
                    )
                    resp_status = 404
                    msg = (
                        "Report not found or caller doesn't have sufficient "
                        "permission to read canned reports."
                    )
                    additional_headers["Content-Type"] = "application/json"
                    resp_data = json.dumps({"message": msg})
                else:
                    bucket = report_item.get("template_bucket")

                    # _ here is the separator
                    prefix, _, template = report_item.get(
                        "template_key"
                    ).rpartition("/")

                    s3template_loader = S3TemplateLoader(
                        bucket=bucket, prefix=prefix
                    )
                    jinja_env = Environment(loader=s3template_loader)

                    template = jinja_env.get_template(template)

                    report_data = get_report_data(
                        # right now we are passing an empty args dict to the
                        # data function. this will change eventually
                        report_item.get("data_function"),
                        {},
                    )

                    report_html = template.render(report_data)

                    report_bytes, additional_headers, additional_values = (
                        convert_report_format(report_html, format)
                    )

                    resp_data = report_bytes

        # update the headers with any additional ones we got, construct the
        # return dict, update it with any additional values we got, and return
        # it
        resp_headers.update(additional_headers)

        resp = {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": resp_data,
        }

        resp.update(additional_values)

        return resp
    except ClientError as err:
        code, message = decode_error(err)

        msg = f"Error during fetch of user attributes. {code} " f"{message}"

        return {
            "statusCode": 500,
            "body": msg,
        }
    except Exception as e:
        # TODO: this exception should be specific, but is
        #       dependent on getting a specific one raised from
        #       get_s3_object and get_report_data, which is
        #       dependent on moving those into capepy

        msg = f"{e}"
        return {
            "statusCode": 500,
            "body": msg,
        }
