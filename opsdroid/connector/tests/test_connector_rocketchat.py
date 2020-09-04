"""Tests for the RocketChat connector."""
import asyncio
import pytest
import contextlib
import asynctest
import asynctest.mock as amock

from opsdroid.core import OpsDroid
from opsdroid.connector.rocketchat import RocketChat
from opsdroid.events import Message
from opsdroid.cli.start import configure_lang

configure_lang({})


def test_init():
    """Test that the connector is initialised properly."""
    connector = RocketChat(
        {
            "name": "rocket.chat",
            "token": "test",
            "user-id": "userID",
            "update-interval": 0.1,
        },
        opsdroid=OpsDroid(),
    )
    assert connector.default_target == "general"
    assert connector.name == "rocket.chat"


def test_missing_token(caplog):
    """Test that attempt to connect without info raises an error."""

    RocketChat({})
    assert "Unable to login: Access token is missing." in caplog.text


def setUp():
    configure_lang({})
    connector = RocketChat(
        {
            "name": "rocket.chat",
            "token": "test",
            "user-id": "userID",
            "default_target": "test",
        },
        opsdroid=OpsDroid(),
    )

    connector.latest_update = "2018-10-08T12:57:37.126Z"

    with amock.patch("aiohttp.ClientSession") as mocked_session:
        connector.session = mocked_session


@pytest.mark.asyncio
async def test_connect(capsys):
    connector = RocketChat({})
    connect_response = amock.Mock()
    connect_response.status = 200
    connect_response.json = amock.CoroutineMock()
    connect_response.return_value = {
        "_id": "3vABZrQgDzfcz7LZi",
        "name": "Fábio Rosado",
        "emails": [{"address": "fabioglrosado@gmail.com", "verified": True}],
        "status": "online",
        "statusConnection": "online",
        "username": "FabioRosado",
        "utcOffset": 1,
        "active": True,
        "roles": ["user"],
        "settings": {},
        "email": "fabioglrosado@gmail.com",
        "success": True,
    }

    with amock.patch("aiohttp.ClientSession.get") as patched_request:

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(connect_response)

        await connector.connect()

        captured = capsys.readouterr()
        assert "DEBUG" in captured.err
        assert patched_request.status != 200
        assert patched_request.called


@pytest.mark.asyncio
async def test_connect_failure(caplog):
    connector = RocketChat({})
    result = amock.MagicMock()
    result.status = 401

    with amock.patch("aiohttp.ClientSession.get") as patched_request:

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(result)

        await connector.connect()
        assert "Error connecting to RocketChat" in caplog.text


@pytest.mark.asyncio
async def test_get_message(capsys):
    connector = RocketChat({})
    connector.group = "test"
    response = amock.Mock()
    response.status = 200
    response.json = amock.CoroutineMock()
    response.return_value = {
        "messages": [
            {
                "_id": "ZbhuIO764jOIu",
                "rid": "Ipej45JSbfjt9",
                "msg": "hows it going",
                "ts": "2018-05-11T16:05:41.047Z",
                "u": {
                    "_id": "ZbhuIO764jOIu",
                    "username": "FabioRosado",
                    "name": "Fábio Rosado",
                },
                "_updatedAt": "2018-05-11T16:05:41.489Z",
                "editedBy": None,
                "editedAt": None,
                "emoji": None,
                "avatar": None,
                "alias": None,
                "customFields": None,
                "attachments": None,
                "mentions": [],
                "channels": [],
            }
        ]
    }

    with amock.patch.object(
        connector.session, "get"
    ) as patched_request, amock.patch.object(
        connector, "_parse_message"
    ) as mocked_parse_message, amock.patch(
        "asyncio.sleep"
    ) as mocked_sleep:

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(response)

        await connector._get_message()

        assert patched_request.called
        assert mocked_parse_message.called
        assert mocked_sleep.called
        captured = capsys.readouterr()
        assert "DEBUG" in captured.err


@pytest.mark.asyncio
async def test_parse_message(capsys):
    connector = RocketChat({})
    response = {
        "messages": [
            {
                "_id": "ZbhuIO764jOIu",
                "rid": "Ipej45JSbfjt9",
                "msg": "hows it going",
                "ts": "2018-05-11T16:05:41.047Z",
                "u": {
                    "_id": "ZbhuIO764jOIu",
                    "username": "FabioRosado",
                    "name": "Fábio Rosado",
                },
                "_updatedAt": "2018-05-11T16:05:41.489Z",
                "editedBy": None,
                "editedAt": None,
                "emoji": None,
                "avatar": None,
                "alias": None,
                "customFields": None,
                "attachments": None,
                "mentions": [],
                "channels": [],
            }
        ]
    }

    with amock.patch.object(connector, "get_messages_loop"), amock.patch(
        "opsdroid.core.OpsDroid.parse"
    ) as mocked_parse:
        await connector._parse_message(response)
        captured = capsys.readouterr()
        assert "DEBUG" in captured.err
        assert mocked_parse.called
        assert "2018-05-11T16:05:41.047Z", connector.latest_update


@pytest.mark.asyncio
async def test_listen():
    connector = RocketChat({})
    with amock.patch.object(
        connector.loop, "create_task"
    ) as mocked_task, amock.patch.object(
        connector._closing, "wait"
    ) as mocked_event, amock.patch.object(
        connector, "get_messages_loop"
    ):
        mocked_event.return_value = asyncio.Future()
        mocked_event.return_value.set_result(True)
        mocked_task.return_value = asyncio.Future()
        await connector.listen()

        assert mocked_event.called
        assert mocked_task.called


@pytest.mark.asyncio
async def test_get_message_failure(capsys):
    connector = RocketChat({})
    listen_response = amock.Mock()
    listen_response.status = 401

    with amock.patch.object(connector.session, "get") as patched_request:

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(listen_response)
        await connector._get_message()
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert connector.listening == False


@pytest.mark.asyncio
async def test_get_messages_loop():
    connector = RocketChat({})
    connector._get_messages = amock.CoroutineMock()
    connector._get_messages.side_effect = Exception()
    with contextlib.suppress(Exception):
        await connector.get_messages_loop()


@pytest.mark.asyncio
async def test_respond(capsys):
    connector = RocketChat({})
    post_response = amock.Mock()
    post_response.status = 200

    with OpsDroid() as opsdroid, amock.patch.object(
        connector.session, "post"
    ) as patched_request:

        assert opsdroid.__class__.instances
        test_message = Message(
            text="This is a test", user="opsdroid", target="test", connector=connector,
        )

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(post_response)
        await test_message.respond("Response")
        assert patched_request.called
        captured = capsys.readouterr()
        assert "DEBUG" in captured.err


@pytest.mark.asyncio
async def test_respond_failure(capsys):
    connector = RocketChat({})
    post_response = amock.Mock()
    post_response.status = 401

    with OpsDroid() as opsdroid, amock.patch.object(
        connector.session, "post"
    ) as patched_request:

        assert opsdroid.__class__.instances
        test_message = Message(
            text="This is a test", user="opsdroid", target="test", connector=connector,
        )

        patched_request.return_value = asyncio.Future()
        patched_request.return_value.set_result(post_response)
        await test_message.respond("Response")
        captured = capsys.readouterr()
        assert "DEBUG" in captured.err


@pytest.mark.asyncio
async def test_disconnect():
    connector = RocketChat({})
    with amock.patch.object(connector.session, "close") as mocked_close:
        mocked_close.return_value = asyncio.Future()
        mocked_close.return_value.set_result(True)

        await connector.disconnect()
        assert connector.listening == False
        assert connector.session.closed()
        assert connector._closing.set() == None
