from uuid import UUID, uuid4

import pydantic

from cqrs.dispatcher import RequestDispatcher
from cqrs.events import Event
from cqrs.middlewares import MiddlewareChain
from cqrs.requests import Request, RequestHandler, RequestMap
from cqrs.response import Response


class ReadMeetingDetailsQuery(Request):
    meeting_room_id: UUID = pydantic.Field()
    status: str | None = pydantic.Field(default=None)


class ReadMeetingDetailsQueryResult(Response):
    meeting_room_id: UUID = pydantic.Field()
    status: str | None = pydantic.Field(default=None)


class ReadMeetingDetailsQueryHandler(
    RequestHandler[ReadMeetingDetailsQuery, ReadMeetingDetailsQueryResult],  # type: ignore
):
    def __init__(self) -> None:
        self.called = False
        self._events: list[Event] = []

    @property
    def events(self) -> list:
        return self._events

    async def handle(
        self,
        request: ReadMeetingDetailsQuery,
    ) -> ReadMeetingDetailsQueryResult:
        self.called = True
        return ReadMeetingDetailsQueryResult(meeting_room_id=request.meeting_room_id)


class TestQueryContainer:
    _handler = ReadMeetingDetailsQueryHandler()

    async def resolve(self, type_):
        return self._handler


async def test_default_dispatcher_logic() -> None:
    middleware = FirstMiddleware()
    request_map = RequestMap()
    request_map.bind(ReadMeetingDetailsQuery, ReadMeetingDetailsQueryHandler)
    middleware_chain = MiddlewareChain()
    middleware_chain.add(middleware)
    dispatcher = RequestDispatcher(
        request_map=request_map,
        container=TestQueryContainer(),  # type: ignore
        middleware_chain=middleware_chain,
    )

    request = ReadMeetingDetailsQuery(meeting_room_id=uuid4())

    result = await dispatcher.dispatch(request)

    assert request.status == "REQ"
    assert result.response.status == "RES"


async def test_default_dispatcher_chain_logic() -> None:
    request_map = RequestMap()
    request_map.bind(ReadMeetingDetailsQuery, ReadMeetingDetailsQueryHandler)
    middleware_chain = MiddlewareChain()
    middleware_chain.set([FirstMiddleware(), SecondMiddleware(), ThirdMiddleware()])
    dispatcher = RequestDispatcher(
        request_map=request_map,
        container=TestQueryContainer(),  # type: ignore
        middleware_chain=middleware_chain,
    )

    request = ReadMeetingDetailsQuery(meeting_room_id=uuid4())

    result = await dispatcher.dispatch(request)

    assert request.status == "REQ"
    assert result.response.status == "RES"

    assert request.status == "REQ"
    assert result.response.status == "RES"

    assert request.status == "REQ"
    assert result.response.status == "RES"


class FirstMiddleware:
    async def __call__(self, request: Request, handle):
        request.status = "REQ"  # type: ignore
        response = await handle(request)
        response.status = "RES"
        return response


class SecondMiddleware:
    async def __call__(self, request: Request, handle):
        request.status = "REQ"  # type: ignore
        response = await handle(request)
        response.status = "RES"
        return response


class ThirdMiddleware:
    async def __call__(self, request: Request, handle):
        request.status = "REQ"  # type: ignore
        response = await handle(request)
        response.status = "RES"
        return response
