# CQRS

Python-библиотека для реализации шаблона CQRS в приложениях Python. Предоставляет набор абстракций и утилит, которые
помогут разделить задачи чтения и записи, обеспечивая лучшую масштабируемость, производительность и удобство
обслуживания приложения.

Библиотека является форком
библиотеки [diator](https://github.com/akhundMurad/diator) ([документация](https://akhundmurad.github.io/diator/)) с
рядом улучшений:

1. поддержка Pydantic [v2.*](https://docs.pydantic.dev/2.8/);
2. поддержка Kafka в качестве брокера [aiokafka](https://github.com/aio-libs/aiokafka);
3. добавлен `EventMediator` для обработки `Notification` и `ECST` событий, приходящих из шины;
4. переработам механизм `mapping`-а событий и запросов на обработчики;
5. добавлен `bootstrap` для легкого начала работы;
6. Добавлена поддержка [Transaction Outbox](https://microservices.io/patterns/data/transactional-outbox.html),
дающего гарантию отправки `Notification` и `ECST` событий в брокера.

## Примеры использования

### Обработчики событий

```python
from cqrs.events import EventHandler

class UserJoinedEventHandler(EventHandler[UserJoinedEventHandler])
    def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
      self._meetings_api = meetings_api

    async def handle(self, event: UserJoinedEventHandler) -> None:
      await self._meetings_api.notify_room(event.meeting_id, "New user joined!")
```

### Обработчик запросов

#### Обработчик `command`

```python
from cqrs.requests.request_handler import RequestHandler
from cqrs.events.event import Event

class JoinMeetingCommandHandler(RequestHandler[JoinMeetingCommand, None])
      def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
          self._meetings_api = meetings_api
          self.events: list[Event] = []

      async def handle(self, request: JoinMeetingCommand) -> None:
          await self._meetings_api.join_user(request.user_id, request.meeting_id)
```

#### Обработчик `query`

```python
from cqrs.requests.request_handler import RequestHandler
from cqrs.events.event import Event

class ReadMeetingQueryHandler(RequestHandler[ReadMeetingQuery, ReadMeetingQueryResult])
      def __init__(self, meetings_api: MeetingAPIProtocol) -> None:
          self._meetings_api = meetings_api
          self.events: list[Event] = []

      async def handle(self, request: ReadMeetingQuery) -> ReadMeetingQueryResult:
          link = await self._meetings_api.get_link(request.meeting_id)
          return ReadMeetingQueryResult(link=link, meeting_id=request.meeting_id)

```

#### Продюсирование `Notification`/`ECST` событий

Во время обработки запроса/команды можно породить сообщения с типом `cqrs.NotificationEvent` или `cqrs.ECSTEvent`,
которое в дальнейшем продюсируется брокером сообщений

```python
class CloseMeetingRoomCommandHandler(requests.RequestHandler[CloseMeetingRoomCommand, None]):
    def __init__(self) -> None:
        self._events: typing.List[events.Event] = []

    @property
    def events(self) -> typing.List:
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

После обработки команды/запроса, при наличии `Notification`/`ECST` событий, вызывается EventEmitter который
спродюсирует события посредством message_broker'а

### Медиатор

```python
from cqrs.events import EventMap, EventEmitter
from cqrs.requests import RequestMap
from cqrs.mediator import RequestMediator
from cqrs.message_brokers.amqp import AMQPMessageBroker

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
```

### Kafka Брокер

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

### Transactional Outbox

Пакет имплементирует паттерн [Transaction Outbox](https://microservices.io/patterns/data/transactional-outbox.html),
что позволяет гарантировать продюсирование сообщений в брокер согласно семантике `at-least-once`.

```python
from sqlalchemy.ext.asyncio import session as sql_session
from cqrs import events

def do_some_logic(meeting_room_id: int, session: sql_session.AsyncSession):
    """
    Внесение изменений в БД
    """
    session.add(...)


class CloseMeetingRoomCommandHandler(requests.RequestHandler[CloseMeetingRoomCommand, None]):

    def __init__(self, repository: cqrs.SqlAlchemyOutboxedEventRepository):
        self._repository = repository
        self._events: typing.List[events.Event] = []

    async def handle(self, request: CloseMeetingRoomCommand) -> None:
        async with self._repository as session:
           do_some_logic(request.meeting_room_id, session)
           self.repository.add(
               session,
               events.ECSTEvent(
                  event_name="MeetingRoomCloseв",
                  payload=dict(message="foo"),
              ),
           )
           await self.repository.commit(session)
```


### Продюсирование событий из Outbox  в Kafka

В качестве имплементации Transaction Outbox доступен для использования репозиторий доступа к `Outbox` хранилищу SqlAlchemyOutboxedEventRepository.
Его можно использовать в связке с `KafkaMessageBroker`.
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
