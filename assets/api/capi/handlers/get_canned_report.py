"""Lambda for handling GETs for listing public user attributes."""

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


class S3TemplateLoader(BaseLoader):
    def __init__(self, bucket, prefix):
        self.bucket = bucket
        self.prefix = prefix

    def get_source(self, environment, template):
        try:
            template_bytes = get_s3_object(
                self.bucket, f"{self.prefix}/{template}"
            )

            template_io = io.BytesIO(template_bytes)
            return (
                template_io.read().decode("utf-8"),
                f"{template}.html",
                lambda: True,
            )
        except Exception as e:
            logger.error(e)

        raise TemplateNotFound(template)


# TODO: move into capepy utils. waiting for the capepy layer refactor in this
#       repo (moving to config/requirements.txt based layer definitions whereas
#       capepy is a class into itself right now) before doing too many more
#       capepy releases.
def get_s3_object(bucket, key):
    """"""
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
        raise Exception(err)

    logger.info(f"Obtained object {key} from bucket {bucket}")

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
        #       report generation queue)
        InvocationType="RequestResponse",
        # this will give the data function execution log back to this caller. if
        # we have an error in getting report data, we'll log the issue here.
        LogType="Tail",
        Payload=(json.dumps(payload).encode("utf-8") if payload else None),
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

    # TODO: this assumes a json payload for all data functions, which may be ok?
    return json.loads(response.get("Body").read().decode("utf-8"))


def convert_report_format(report_html, format="html"):
    """Convert the format incoming HTML (if needed) and return a bytestream.

    Args:
        report_html: The rendered HTML string for a given report.
        format: The format the output file should be in (e.g. "html", "pdf")
                assuming the format conversion is supported.

    Return:
        A BytesIO on the resultant formatted file on success.

    Raises:
        Excception on invalid format specified
    """
    match format:
        case "html":
            # in this case we already have html and will just return the
            # bytestream
            return io.BytesIO(report_html.encode("utf-8"))
        case "pdf":
            # in this case we want to feed the html to the pdf engine then
            # return a bytestream on that
            wep_html = weasyprint.HTML(string=report_html)
            pdf_io = io.BytesIO()
            wep_html.write_pdf(target=pdf_io)
            pdf_io.seek(0)
            return pdf_io
        case _:
            msg = (
                f"Cannot format report in requested format {format}. Format "
                f"not supported"
            )
            raise Exception(msg)


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

        # TODO: clean up, get a pattern for handling error and content type
        #       switching
        if qsp is None:
            resp_data = json.dumps(
                {
                    "message": "Missing required query string parameters: reportId"
                }
            )
            resp_headers["Content-Type"] = "application/json"
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
                resp_headers["Content-Type"] = "application/json"
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
                    resp_headers["Content-Type"] = "application/json"
                    resp_data = json.dumps({"message": msg})
                else:
                    bucket = report_item.get("template_bucket")
                    prefix, template = report_item.get(
                        "template_key"
                    ).rpartition("/")

                    s3template_loader = S3TemplateLoader(
                        bucket=bucket, prefix=prefix
                    )
                    jinja_env = Environment(loader=s3template_loader)

                    template = jinja_env.get_template(template)

                    report_data = get_report_data(
                        report_item.get("data_function")
                    )

                    report_html = template.render(report_data)

                    report_io = convert_report_format(report_html, format)

                    resp_data = report_io.getvalue()

        # And return our response however it ended up
        return {
            "statusCode": resp_status,
            "headers": resp_headers,
            "body": resp_data,
        }
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
