"""Dialect-aware SQLAlchemy types shared by the library models.

The module generalizes the trick used by the outbox model: a single Python type
is rendered as the most suitable native type of the current dialect. Mapping
between a dialect and its DDL type/value conversion is kept in a per-class
registry, so support for a new DBMS is one `register_dialect` call away.
"""

import dataclasses
import typing
import uuid

try:
    import sqlalchemy

    from sqlalchemy.dialects import mysql, postgresql
except ImportError:
    raise ImportError(
        "You are trying to use SQLAlchemy types, "
        "but 'sqlalchemy' is not installed. "
        "Please install it using: pip install python-cqrs[sqlalchemy]",
    ) from None

__all__ = (
    "Binary16",
    "DialectAwareType",
    "DialectTypeHandler",
    "JSONType",
    "PayloadBinary",
    "UUIDBinary",
)


@dataclasses.dataclass(frozen=True)
class DialectTypeHandler:
    """Describes how a type lives in a particular dialect.

    Attributes:
        type_factory: builds the dialect native type used in DDL and binding.
        bind: converts a Python value into the dialect representation.
        result: converts a value fetched from the database into a Python one.
    """

    type_factory: typing.Callable[[typing.Any], typing.Any]
    bind: typing.Callable[[typing.Any], typing.Any] | None = None
    result: typing.Callable[[typing.Any], typing.Any] | None = None


class DialectAwareType(sqlalchemy.TypeDecorator):
    """Base class for types resolved through a per-dialect registry.

    Subclasses declare a `default_handler` used as a portable fallback and
    register dialect specific handlers via `register_dialect`. Every subclass
    owns its registry, so registrations never leak between types.
    """

    impl = sqlalchemy.LargeBinary
    cache_ok = True

    default_handler: typing.ClassVar[DialectTypeHandler]
    _handlers: typing.ClassVar[typing.Dict[typing.Text, DialectTypeHandler]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Each subclass owns its registry, otherwise a registration made for one
        # type would leak into all the others.
        cls._handlers = dict(cls._handlers)

    @classmethod
    def register_dialect(
        cls,
        dialect_name: typing.Text,
        handler: DialectTypeHandler,
    ) -> None:
        """Registers (or overrides) the handler used for `dialect_name`."""
        cls._handlers[dialect_name] = handler

    @classmethod
    def get_handler(cls, dialect_name: typing.Text) -> DialectTypeHandler:
        """Returns the handler for `dialect_name` or the portable fallback."""
        return cls._handlers.get(dialect_name, cls.default_handler)

    def load_dialect_impl(self, dialect):
        handler = self.get_handler(dialect.name)
        return dialect.type_descriptor(handler.type_factory(dialect))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        handler = self.get_handler(dialect.name)
        if handler.bind is None:
            return value
        return handler.bind(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        handler = self.get_handler(dialect.name)
        if handler.result is None:
            return value
        return handler.result(value)


def _as_uuid(value: typing.Any) -> typing.Any:
    if isinstance(value, str):
        return uuid.UUID(value)
    return value


def _as_bytes(value: typing.Any) -> typing.Any:
    value = _as_uuid(value)
    if isinstance(value, uuid.UUID):
        return value.bytes
    return value


def _as_uuid_from_bytes(value: typing.Any) -> typing.Any:
    if isinstance(value, bytes):
        return uuid.UUID(bytes=value)
    return value


class UUIDBinary(DialectAwareType):
    """`uuid.UUID` stored as a native UUID in PostgreSQL and as BINARY(16) elsewhere."""

    default_handler = DialectTypeHandler(
        type_factory=lambda dialect: sqlalchemy.LargeBinary(16),
        bind=_as_bytes,
        result=_as_uuid_from_bytes,
    )


UUIDBinary.register_dialect(
    "postgresql",
    DialectTypeHandler(
        # asyncpg works with uuid.UUID, no conversion is needed.
        type_factory=lambda dialect: postgresql.UUID(as_uuid=True),
        bind=_as_uuid,
    ),
)
UUIDBinary.register_dialect(
    "mysql",
    DialectTypeHandler(
        type_factory=lambda dialect: mysql.BINARY(16),
        bind=_as_bytes,
        result=_as_uuid_from_bytes,
    ),
)
UUIDBinary.register_dialect("mariadb", UUIDBinary.get_handler("mysql"))


class Binary16(DialectAwareType):
    """Raw 16 bytes: BYTEA in PostgreSQL, BINARY(16) in MySQL, LargeBinary(16) elsewhere."""

    default_handler = DialectTypeHandler(
        type_factory=lambda dialect: sqlalchemy.LargeBinary(16),
        bind=_as_bytes,
    )


Binary16.register_dialect(
    "postgresql",
    DialectTypeHandler(
        type_factory=lambda dialect: postgresql.BYTEA(),
        bind=_as_bytes,
    ),
)
Binary16.register_dialect(
    "mysql",
    DialectTypeHandler(
        type_factory=lambda dialect: mysql.BINARY(16),
        bind=_as_bytes,
    ),
)
Binary16.register_dialect("mariadb", Binary16.get_handler("mysql"))


class JSONType(DialectAwareType):
    """JSON document rendered as plain `JSON` on every dialect.

    The default handler intentionally repeats `sqlalchemy.JSON`, so switching a
    column to this type does not change the generated DDL anywhere. It only adds
    an extension point: a project that wants a native PostgreSQL `JSONB` enables
    it with a single registration, without touching the library models.

    ```python
    from sqlalchemy.dialects import postgresql
    from cqrs.sqlalchemy_types import DialectTypeHandler, JSONType

    JSONType.register_dialect(
        "postgresql",
        DialectTypeHandler(type_factory=lambda dialect: postgresql.JSONB()),
    )
    ```

    No value conversion is performed: serialization stays the responsibility of
    the dialect level JSON type, exactly as with `sqlalchemy.JSON`.
    """

    impl = sqlalchemy.JSON
    cache_ok = True

    default_handler = DialectTypeHandler(
        type_factory=lambda dialect: sqlalchemy.JSON(),
    )


class PayloadBinary(DialectAwareType):
    """Binary blob of an arbitrary length rendered as plain `LargeBinary` everywhere.

    The default handler intentionally repeats `sqlalchemy.LargeBinary` without a
    length, so switching a column to this type keeps the DDL identical on every
    dialect (`BYTEA` in PostgreSQL, `BLOB` in MySQL and SQLite). It only adds an
    extension point for a DBMS the library knows nothing about: Microsoft SQL
    Server, for instance, maps `LargeBinary` to the deprecated `IMAGE`, which a
    project fixes with a single registration.

    ```python
    from sqlalchemy.dialects import mssql
    from cqrs.sqlalchemy_types import DialectTypeHandler, PayloadBinary

    PayloadBinary.register_dialect(
        "mssql",
        DialectTypeHandler(type_factory=lambda dialect: mssql.VARBINARY("max")),
    )
    ```

    No value conversion is performed: the column holds `bytes` and they are
    passed to the driver as is.
    """

    impl = sqlalchemy.LargeBinary
    cache_ok = True

    default_handler = DialectTypeHandler(
        type_factory=lambda dialect: sqlalchemy.LargeBinary(),
    )
