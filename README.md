# Python CQRS pattern implementaion with Transaction Outbox supporting

## Overview

This is a package for implementing the CQRS (Command Query Responsibility Segregation) pattern in Python applications.
It provides a set of abstractions and utilities to help separate read and write use cases, ensuring better scalability, performance, and maintainability of the application.

This package is a fork of the [diator](https://github.com/akhundMurad/diator) project ([documentation](https://akhundmurad.github.io/diator/)) with several enhancements:

1. Support for Pydantic [v2.*](https://docs.pydantic.dev/2.8/);
2. `Kafka` support using [aiokafka](https://github.com/aio-libs/aiokafka);
3. Added `EventMediator` for handling `Notification` and `ECST` events coming from the bus;
4. Redesigned the event and request mapping mechanism to handlers;
5. Added `bootstrap` for easy setup;
6. Added support for [Transaction Outbox](https://microservices.io/patterns/data/transactional-outbox.html), ensuring that `Notification` and `ECST` events are sent to the broker.


## Request Handlers

Request handlers can be divided into two main types:

### Command Handler

Command Handler executes the received command. The logic of the handler may include, for example, modifying the state of the domain model.
As a result of executing the command, an event may be produced to the broker.
> [!TIP]
> By default, the command handler does not return any result, but it is not mandatory.

```python
from cqrs.requests.request_handler import RequestHandler, SyncRequestHandler
from cqrs.events.event import Event

class JoinMeetingCommandHandler(RequestHandler[JoinMeetingCommand, None]):

      def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
          self._meetings_api = meetings_api
          self.events: list[Event] = []

      @property
      def events(self) -> typing.List[events.Event]:
          return self._events

      async def handle(self, request: JoinMeetingCommand) -> None:
          await self._meetings_api.join_user(request.user_id, request.meeting_id)


class SyncJoinMeetingCommandHandler(SyncRequestHandler[JoinMeetingCommand, None]):

      def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
          self._meetings_api = meetings_api
          self.events: list[Event] = []

      @property
      def events(self) -> typing.List[events.Event]:
          return self._events

      def handle(self, request: JoinMeetingCommand) -> None:
          # do some sync logic
          ...
```

### Query handler

Query Handler returns a representation of the requested data, for example, from the [read model](https://radekmaziarka.pl/2018/01/08/cqrs-third-step-simple-read-model/#simple-read-model---to-the-rescue).
> [!TIP]
> The read model can be constructed based on domain events produced by the `Command Handler`.

```python
from cqrs.requests.request_handler import RequestHandler
from cqrs.events.event import Event

class ReadMeetingQueryHandler(RequestHandler[ReadMeetingQuery, ReadMeetingQueryResult]):

      def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
          self._meetings_api = meetings_api
          self.events: list[Event] = []

      @property
      def events(self) -> typing.List[events.Event]:
          return self._events

      async def handle(self, request: ReadMeetingQuery) -> ReadMeetingQueryResult:
          link = await self._meetings_api.get_link(request.meeting_id)
          return ReadMeetingQueryResult(link=link, meeting_id=request.meeting_id)

```


## Event Handlers

Event handlers are designed to process `Notification` and `ECST` events that are consumed from the broker.
To configure event handling, you need to implement a broker consumer on the side of your application.
Below is an example of `Kafka event consuming` that can be used in the Presentation Layer.

```python
from cqrs.events import EventHandler, SyncEventHandler

class UserJoinedEventHandler(EventHandler[UserJoinedEventHandler]):

    def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
      self._meetings_api = meetings_api

    async def handle(self, event: UserJoinedEventHandler) -> None:
      await self._meetings_api.notify_room(event.meeting_id, "New user joined!")

class SyncUserJoinedEventHandler(SyncEventHandler[UserJoinedEventHandler]):

    def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
      self._meetings_api = meetings_api

    def handle(self, event: UserJoinedEventHandler) -> None:
      # do some sync logic
      ...
```

## Producing Notification/ECST Events

During the handling of a command event, messages of type `cqrs.NotificationEvent` or `cqrs.ECSTEvent` may be generated and then sent to the broker.

```python
class CloseMeetingRoomCommandHandler(requests.RequestHandler[CloseMeetingRoomCommand, None]):

    def __init__(self) -> None:
        self._events: typing.List[events.Event] = []

    @property
    def events(self) -> typing.List[events.Event]:
        return self._events

    async def handle(self, request: CloseMeetingRoomCommand) -> None:
        # some process
        event = events.NotificationEvent(
            event_topic="meeting_room_notifications",
            event_name="meeteng_room_closed",
            payload=dict(
                meeting_room_id=request.meeting_room_id,
            ),
        )
        self._events.append(event)
```

After processing the command/request, if there are any Notification/ECST events,
the EventEmitter is invoked to produce the events via the message broker.

> [!WARNING]
> It is important to note that producing events using the events property parameter does not guarantee message delivery to the broker.
> In the event of broker unavailability or an exception occurring during message formation or sending, the message may be lost.
> This issue can potentially be addressed by configuring retry attempts for sending messages to the broker, but we recommend using the [Transaction Outbox](https://microservices.io/patterns/data/transactional-outbox.html) pattern,
> which is implemented in the current version of the python-cqrs package for this purpose.

## Kafka broker

```python
from cqrs.adapters import kafka as kafka_adapter
from cqrs.message_brokers import kafka as kafka_broker


producer = kafka_adapter.kafka_producer_factory(
    dsn="localhost:9094",
    topics=["test.topic1", "test.topic2"],
)
broker = kafka_broker.KafkaMessageBroker(producer)
await broker.send_message(...)
```

## Transactional Outbox

The package implements the [Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html) pattern, which ensures that messages are produced to the broker according to the at-least-once semantics.


```python
from sqlalchemy.ext.asyncio import session as sql_session
from cqrs import events

def do_some_logic(meeting_room_id: int, session: sql_session.AsyncSession):
    """
    Make changes to the database
    """
    session.add(...)


class CloseMeetingRoomCommandHandler(requests.RequestHandler[CloseMeetingRoomCommand, None]):

    def __init__(self, repository: cqrs.SqlAlchemyOutboxedEventRepository):
        self._repository = repository
        self._events: typing.List[events.Event] = []

    @property
    def events(self):
        return self._events

    async def handle(self, request: CloseMeetingRoomCommand) -> None:
        async with self._repository as session:
           do_some_logic(request.meeting_room_id, session)
           self.repository.add(
               session,
               events.ECSTEvent(
                  event_name="MeetingRoomClosed",
                  payload=dict(message="foo"),
              ),
           )
           await self.repository.commit(session)
```


## Producing Events from Outbox to Kafka

As an implementation of the Transactional Outbox pattern, the SqlAlchemyOutboxedEventRepository is available for use as an access repository to the Outbox storage.
It can be utilized in conjunction with the KafkaMessageBroker.

```python
import asyncio
import cqrs
from cqrs.message_brokers import kafka as kafka_broker

session_factory = async_sessionmaker(
    create_async_engine(
        f"mysql+asyncmy://{USER}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}",
        isolation_level="REPEATABLE READ",
    )
)

broker = kafka_broker.KafkaMessageBroker(
    kafka_adapter.kafka_producer_factory(
        dsn="localhost:9094",
        topics=["test.topic1", "test.topic2"],
    ),
    "DEBUG"
)

producer = cqrs.EventProducer(cqrs.SqlAlchemyOutboxedEventRepository(session_factory, zlib.ZlibCompressor()), broker)
loop = asyncio.get_event_loop()
loop.run_until_complete(app.periodically_task())
```


## Transaction log tailing

If the Outbox polling strategy does not suit your needs, I recommend exploring the [Transaction Log Tailing](https://microservices.io/patterns/data/transaction-log-tailing.html) pattern.
The current version of the python-cqrs package does not support the implementation of this pattern.

> [!TIP]
> However, it can be implemented using [Debezium + Kafka Connect](https://debezium.io/documentation/reference/stable/architecture.html),
> which allows you to produce all newly created events within the Outbox storage directly to the corresponding topic in Kafka (or any other broker).


## DI container

Use the following example to set up dependency injection in your command, query and event handlers. This will make dependency management simpler.

```python
import di
...

def setup_di() -> di.Container:
    """
    Binds implementations to dependencies
    """
    container = di.Container()
    container.bind(
        di.bind_by_type(
            dependent.Dependent(cqrs.SqlAlchemyOutboxedEventRepository, scope="request"),
            cqrs.OutboxedEventRepository
        )
    )
    container.bind(
        di.bind_by_type(
            dependent.Dependent(MeetingAPIImplementaion, scope="request"),
            MeetingAPIProtocol
        )
    )
    return container
```


## Mapping

To bind commands, queries and events with specific handlers, you can use the registries `EventMap` and `RequestMap`.

```python
from cqrs import requests, events

from app import commands, command_handlers
from app import queries, query_handlers
from app import events as event_models, event_handlers


def init_commands(mapper: requests.RequestMap) -> None:
    mapper.bind(commands.JoinMeetingCommand, command_handlers.JoinMeetingCommandHandler)

def init_queries(mapper: requests.RequestMap) -> None:
    mapper.bind(queries.ReadMeetingQuery, query_handlers.ReadMeetingQueryHandler)

def init_events(mapper: events.EventMap) -> None:
    mapper.bind(events.NotificationEvent[events_models.NotificationMeetingRoomClosed], event_handlers.MeetingRoomClosedNotificationHandler)
    mapper.bind(events.ECSTEvent[event_models.ECSTMeetingRoomClosed], event_handlers.UpdateMeetingRoomReadModelHandler)
```


## Bootstrap

The `python-cqrs` package implements a set of bootstrap utilities designed to simplify the initial configuration of an application.
```python
import functools

from cqrs.events import bootstrap as event_bootstrap
from cqrs.requests import bootstrap as request_bootstrap

from app import dependencies, mapping, orm

@functools.lru_cache
def mediator_factory():
    return request_bootstrap.bootstrap(
        di_container=dependencies.setup_di(),
        commands_mapper=mapping.init_commands,
        queries_mapper=mapping.init_queries,
        domain_events_mapper=mapping.init_events,
        on_startup=[orm.init_store_event_mapper],
    )


@functools.lru_cache
def event_mediator_factory():
    return event_bootstrap.bootstrap(
        di_container=dependencies.setup_di(),
        events_mapper=mapping.init_events,
        on_startup=[orm.init_store_event_mapper],
    )
```

## Integaration with presentation layers

>[!TIP]
> I recommend reading the useful paper [Onion Architecture Used in Software Development](https://www.researchgate.net/publication/371006360_Onion_Architecture_Used_in_Software_Development).
> Separating user interaction and use-cases into Application and Presentation layers is a good practice.
> This can improve the `Testability`, `Maintainability`, `Scalability` of the application. It also provides benefits such as `Separation of Concerns`.

### FastAPI requests handling

If your application uses FastAPI (or any other asynchronous framework for creating APIs).
In this case you can use python-cqrs to route requests to the appropriate handlers implementing specific use-cases.

```python
import fastapi
import pydantic

from app import dependecies, commands

router = fastapi.APIRouter(prefix="/meetings")


@router.put("/{meeting_id}/{user_id}", status_code=status.HTTP_200_OK)
async def join_metting(
    meeting_id: pydantic.PositiveInt,
    user_id: typing.Text,
    mediator: cqrs.RequestMediator = fastapi.Depends(dependencies.mediator_factory),
):
    await mediator.send(commands.JoinMeetingCommand(meeting_id=meeting_id, user_id=user_id))
    return {"result": "ok"}

```

### Kafka events consuming

If you build interaction by events over brocker like `Kafka`, you can to implement an event consumer on your application's side,
which will call the appropriate handler for each event.
An example of handling events from `Kafka` is provided below.

```python
import aiokafka
import cqrs
import orjson

from app import events

class OnEvent:

    def __init__(
        self,
        event_mediator: cqrs.EventMediator
    ):
        self._event_mediator = event_mediator

    async def __call__(self, kafka_message: aiokafka.ConsumerRecord) -> None:
        event = cqrs.ECSTEvent[events.ECSTMeetingRoomClosed].model_validate(
            orjson.loads(kafka_message.value),
            context={"assume_validated": True},
        )
        await self._event_mediator.send(event)
```
