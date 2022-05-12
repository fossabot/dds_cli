from requests_mock.mocker import Mocker
from pytest import raises

from dds_cli import DDSEndpoint
from dds_cli.exceptions import ApiResponseError, DDSCLIException
from dds_cli.utils import perform_request


def test_perform_request_post_request() -> None:
    url: str = "http://localhost"
    with Mocker() as mock:
        mock.post(url, status_code=200, json={})
        response: Response = perform_request(endpoint=url, headers={}, method="post")
        assert response == {}


def test_perform_request_project_creation_error() -> None:
    response_json: Dict = {
        "message": "message",
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.CREATE_PROJ, status_code=400, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.CREATE_PROJ, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert exc_info.value.args[0] == "API Request failed.: message"


def test_perform_request_project_creation_error_list() -> None:
    response_json: Dict = {
        "message": ["message"],
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.CREATE_PROJ, status_code=400, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.CREATE_PROJ, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert exc_info.value.args[0] == "API Request failed.: message"


def test_perform_request_project_creation_error_insufficient_credentials() -> None:
    response_json: Dict = {
        "message": "You do not have the required permissions to create a project.",
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.CREATE_PROJ, status_code=403, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.CREATE_PROJ, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert (
            exc_info.value.args[0]
            == "API Request failed.: You do not have the required permissions to create a project."
        )


def test_perform_request_add_motd_error_insufficient_credentials() -> None:
    response_json: Dict = {
        "message": "Only Super Admin can add a MOTD.",
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.ADD_NEW_MOTD, status_code=403, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.ADD_NEW_MOTD, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert exc_info.value.args[0] == "API Request failed.: Only Super Admin can add a MOTD."


def test_perform_request_activate_TOTP_error() -> None:
    response_json: Dict = {
        "message": ["message"],
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.USER_ACTIVATE_TOTP, status_code=400, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.USER_ACTIVATE_TOTP, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert exc_info.value.args[0] == "API Request failed."


def test_perform_request_activate_HOTP_error() -> None:
    response_json: Dict = {
        "message": ["message"],
        "title": "",
        "description": "",
        "pi": "",
        "email": "",
    }
    with Mocker() as mock:
        mock.post(DDSEndpoint.USER_ACTIVATE_HOTP, status_code=400, json=response_json)
        with raises(DDSCLIException) as exc_info:
            perform_request(endpoint=DDSEndpoint.USER_ACTIVATE_HOTP, headers={}, method="post")

        assert len(exc_info.value.args) == 1
        assert exc_info.value.args[0] == "API Request failed."
