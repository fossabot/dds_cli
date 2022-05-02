"""DDS CLI utils module."""

import numbers
from pathlib import Path

import requests
import rich.console
import simplejson
from jwcrypto.common import InvalidJWEOperation
from jwcrypto.jwe import InvalidJWEData
from jwcrypto.jws import InvalidJWSObject
from jwcrypto import jwt
import http
from rich.table import Table
from typing import List, Union

import dds_cli.exceptions
from dds_cli import DDSEndpoint

console = rich.console.Console()
stderr_console = rich.console.Console(stderr=True)

# Classes


class HumanBytes:
    """Format as human readable.

    Copied from Stack Overflow: https://stackoverflow.com/a/63839503.
    """

    METRIC_LABELS: List[str] = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    BINARY_LABELS: List[str] = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    PRECISION_OFFSETS: List[float] = [0.5, 0.05, 0.005, 0.0005]  # PREDEFINED FOR SPEED.
    PRECISION_FORMATS: List[str] = [
        "{}{:.0f} {}",
        "{}{:.1f} {}",
        "{}{:.2f} {}",
        "{}{:.3f} {}",
    ]  # PREDEFINED FOR SPEED.

    @staticmethod
    def format(num: Union[int, float], metric: bool = False, precision: int = 1) -> str:
        """Human-readable formatting of bytes, using binary (powers of 1024)
        or metric (powers of 1000) representation.
        """
        assert isinstance(num, (int, float)), "num must be an int or float"
        assert isinstance(metric, bool), "metric must be a bool"
        assert (
            isinstance(precision, int) and precision >= 0 and precision <= 3
        ), "precision must be an int (range 0-3)"

        unit_labels = HumanBytes.METRIC_LABELS if metric else HumanBytes.BINARY_LABELS
        last_label = unit_labels[-1]
        unit_step = 1000 if metric else 1024
        unit_step_thresh = unit_step - HumanBytes.PRECISION_OFFSETS[precision]

        is_negative = num < 0
        if is_negative:  # Faster than ternary assignment or always running abs().
            num = abs(num)

        for unit in unit_labels:
            if num < unit_step_thresh:
                # VERY IMPORTANT:
                # Only accepts the CURRENT unit if we're BELOW the threshold where
                # float rounding behavior would place us into the NEXT unit: F.ex.
                # when rounding a float to 1 decimal, any number ">= 1023.95" will
                # be rounded to "1024.0". Obviously we don't want ugly output such
                # as "1024.0 KiB", since the proper term for that is "1.0 MiB".
                break
            if unit != last_label:
                # We only shrink the number if we HAVEN'T reached the last unit.
                # NOTE: These looped divisions accumulate floating point rounding
                # errors, but each new division pushes the rounding errors further
                # and further down in the decimals, so it doesn't matter at all.
                num /= unit_step

        return HumanBytes.PRECISION_FORMATS[precision].format("-" if is_negative else "", num, unit)


# Functions


def sort_items(items: list, sort_by: str) -> list:
    """Sort list of dicts according to specified key."""
    return sorted(items, key=lambda i: i[sort_by])


def create_table(
    title: str,
    columns: list,
    rows: list,
    show_header: bool = True,
    header_style: str = "bold",
    show_footer: bool = False,
    caption: str = "",
    ints_as_string=False,
) -> Table:
    """Create table."""
    # Create table
    table = Table(
        title=title,
        show_header=show_header,
        header_style=header_style,
        show_footer=show_footer,
        caption=caption,
    )

    # Add columns
    for col in columns:
        table.add_column(col, justify="left", overflow="fold")

    # Add rows
    for row in rows:
        table.add_row(
            *[
                rich.markup.escape(
                    dds_cli.utils.format_api_response(
                        str(row[x]) if ints_as_string and isinstance(row[x], int) else row[x], x
                    )
                )
                for x in columns
            ]
        )

    return table


def get_required_in_response(keys: list, response: dict) -> tuple:
    """Verify that required info is present."""
    not_returned = []
    for key in keys:
        item = response.get(key)
        if not item:
            not_returned.append(key)

    if not_returned:
        raise dds_cli.exceptions.ApiResponseError(
            message=f"The following information was not returned: {not_returned}"
        )

    return tuple(response.get(x) for x in keys)


def perform_request(
    endpoint,
    headers,
    method,
    auth=None,
    params=None,
    json=None,
    error_message="API Request failed.",
    timeout=DDSEndpoint.TIMEOUT,
):
    request_method = None
    if method == "get":
        request_method = requests.get
    elif method == "put":
        request_method = requests.put

    """Perform get request."""
    try:
        response = request_method(
            url=endpoint,
            headers=headers,
            auth=auth,
            params=params,
            json=json,
            timeout=timeout,
        )
        response_json = response.json()
    except requests.exceptions.RequestException as err:
        raise dds_cli.exceptions.ApiRequestError(
            message=(
                error_message
                + (
                    ": The database seems to be down."
                    if isinstance(err, requests.exceptions.ConnectionError)
                    else ": Unknown request error."
                )
            )
        )
    except simplejson.JSONDecodeError as err:
        raise dds_cli.exceptions.ApiResponseError(message=str(err))

    # Check if response is ok.
    if not response.ok:
        message = error_message
        if response.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR:
            raise dds_cli.exceptions.ApiResponseError(message=f"{message}: {response.reason}")

        raise dds_cli.exceptions.DDSCLIException(
            message=f"{message}: {response_json.get('message', 'Unexpected error!')}"
        )

    return response_json


def parse_project_errors(errors):
    """Parse all errors related to projects."""
    msg = ""
    if errors:
        for unique_error in set(errors.values()):
            msg += unique_error
            affected_projects = [x for x, y in errors.items() if y == unique_error]
            for proj in affected_projects:
                msg += f"\n   - {proj}"

    return msg


def multiple_help_text(item):
    """Return help text for option with multiple=True."""
    return f" Use the option multiple times to specify more than one {item} [multiple]"


def get_json_response(response):
    """Get json output from requests response."""
    try:
        json_response = response.json()
    except simplejson.JSONDecodeError as err:
        raise SystemExit from err  # TODO: Change?

    return json_response


def format_api_response(response, key: str, binary: bool = False, always_show: bool = False):
    """Take a value e.g. bytes and reformat it to include a unit prefix."""
    formatted_response = response
    if isinstance(response, bool):
        formatted_response = ":white_heavy_check_mark:" if response else ":x:"
    elif isinstance(response, numbers.Number):
        if key in ["Size", "Usage"]:
            formatted_response = HumanBytes.format(num=response, metric=not binary)
            if key == "Usage":
                formatted_response += "H"
        elif key == "Cost":
            formatted_response = HumanBytes.format(num=response, metric=True)[0:-1] + "kr"

    return str(formatted_response)


def get_token_header_contents(token):
    """Function to extract the jose header of the DDS token (JWE).

    :param token: a token that is not None

    returns the jose header of the token on successful deserialization"""
    try:
        token = jwt.JWT(jwt=token)
        return token.token.jose_header
    except (ValueError, InvalidJWEData, InvalidJWEOperation, InvalidJWSObject) as exc:
        raise dds_cli.exceptions.TokenDeserializationError(
            message="Token could not be deserialized."
        ) from exc


def get_token_expiration_time(token):
    """Function to extract the expiration time of the DDS token from its jose header.
    This expiration time is not the actual exp claim encrypted inside the token. This
    is only to help the cli know the time precisely instead of estimating.

    :param token: a token that is not None

    returns the exp claim for the cli from the jose header of the token"""

    jose_header = get_token_header_contents(token=token)
    if jose_header and "exp" in jose_header:
        return jose_header["exp"]
    raise dds_cli.exceptions.TokenExpirationMissingError(
        message="Expiration time could not be found in the header of the token."
    )


def readable_timedelta(duration):
    """Function to output a human-readable more sophisticated timedelta
    than str(datatime.timedelta) would.

    :param timedelta duration: difference in time, for example, token_exp_time - utcnow

    returns human-readable time representation from days down to the precision of minutes"""
    timespan = {}
    timespan["days"], rem = divmod(abs(duration.total_seconds()), 86_400)
    timespan["hours"], rem = divmod(rem, 3_600)
    timespan["minutes"], _ = divmod(rem, 60)
    time_parts = ((name, round(value)) for name, value in timespan.items())
    time_parts = [
        f"{value} {name if value > 1 else name[:-1]}" for name, value in time_parts if value > 0
    ]
    if time_parts:
        return " ".join(time_parts)
    else:
        return "less than a minute"


def get_deletion_confirmation(action: str, project: str) -> bool:
    """Confirm that the user wants to perform deletion."""
    question = f"Are you sure you want to {action} {project}? All its contents "
    if action in ["delete", "abort"]:
        question = question + "and metainfo "
    question += "will be deleted!"

    proceed_deletion = rich.prompt.Confirm.ask(question)
    return proceed_deletion


def print_or_page(item):
    """Paginate or print out depending on size of item."""
    if isinstance(item, rich.table.Table):
        if item.columns:
            if item.row_count + 5 > dds_cli.utils.console.height:
                with dds_cli.utils.console.pager():
                    dds_cli.utils.console.print(item)
            else:
                dds_cli.utils.console.print(item)
        else:
            raise dds_cli.exceptions.NoDataError("No users found.")


# Adapted from <https://stackoverflow.com/a/49782093>.
def delete_folder(folder):
    folder = Path(folder)
    for file_or_folder in folder.iterdir():
        if file_or_folder.is_dir():
            delete_folder(file_or_folder)
        else:
            file_or_folder.unlink()
    folder.rmdir()
