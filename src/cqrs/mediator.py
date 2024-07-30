import typing

from cqrs import container as di_container
from cqrs import dispatcher, events, middlewares, requests, response

Req = typing.TypeVar("Req", bound=requests.Request, contravariant=True)
Resp = typing.TypeVar("Resp", bound=response.Response, covariant=True)
E = typing.TypeVar("E", bound=events.Event, contravariant=True)


class RequestMediator:
    """
    The request mediator object.

    Usage::

      message_broker = AMQPMessageBroker(
        dsn=f"amqp://{LOGIN}:{PASSWORD}@{HOSTNAME}/",
        queue_name="user_joined_domain",
        exchange_name="user_joined",
      )
      event_map = EventMap()
      event_map.bind(UserJoinedDomainEvent, UserJoinedDomainEventHandler)
      request_map = RequestMap()
      request_map.bind(JoinUserCommand, JoinUserCommandHandler)
      event_emitter = EventEmitter(event_map, container, message_broker)

      mediator = RequestMediator(
        request_map=request_map,
        container=container
        event_emitter=event_emitter,
      )

      # Handles command and published events by the command handler.
      await mediator.send(join_user_command)

    """

    def __init__(
        self,
        request_map: requests.RequestMap,
        container: di_container.Container,
        event_emitter: events.EventEmitter | None = None,
        middleware_chain: middlewares.MiddlewareChain | None = None,
        *,
        dispatcher_type: typing.Type[dispatcher.RequestDispatcher] = dispatcher.RequestDispatcher,
    ) -> None:
        self._event_emitter = event_emitter
        self._dispatcher = dispatcher_type(
            request_map=request_map,  # type: ignore
            container=container,  # type: ignore
            middleware_chain=middleware_chain,  # type: ignore
        )

    async def send(self, request: Req) -> Resp | None:
        dispatch_result = await self._dispatcher.dispatch(request)

        if dispatch_result.events:
            await self._send_events(dispatch_result.events.copy())

        return dispatch_result.response

    async def _send_events(self, events: typing.List[E]) -> None:
        if not self._event_emitter:
            return

        while events:
            event = events.pop()
            await self._event_emitter.emit(event)


class EventMediator:
    """
    The event mediator object.

    Usage::
      event_map = EventMap()
      event_map.bind(UserJoinedECSTEvent, UserJoinedECSTEventHandler)
      mediator = EventMediator(
        event_map=event_map,
        container=container
      )

      # Handles ecst and notification events.
      await mediator.send(user_joined_event)
    """

    def __init__(
        self,
        event_map: events.EventMap,
        container: di_container.Container,
        *,
        dispatcher_type: typing.Type[dispatcher.EventDispatcher] = dispatcher.EventDispatcher,
    ):
        self._dispatcher = dispatcher_type(event_map, container)

    async def send(self, event: E) -> None:
        await self._dispatcher.dispatch(event)
