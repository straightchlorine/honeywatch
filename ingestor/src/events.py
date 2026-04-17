"""Canonical Pydantic model of cowrie's JSON log schema.

This module is the reference for every event type cowrie emits that we care
about. Fields mirror cowrie's wire names; where our internal code prefers a
different attribute (e.g. `session_id` vs cowrie's `session`, `sha256` vs
cowrie's `shasum`), aliases translate at parse time.

The `CowrieEvent` type below is a discriminated union keyed on `eventid`.
Pass it to a `TypeAdapter` to validate raw lines; pydantic picks the right
subclass from the eventid string. Events that are not in this union will
fail validation -- check the raw line logged by the ingestor at INFO to see
what cowrie sent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _EventBase(BaseModel):
    """Common envelope for every cowrie event.

    Session-scoped subclasses add `session_id: str = Field(validation_alias="session")`.
    `extra="allow"` means any cowrie field we haven't explicitly modelled is
    still captured -- access it via `.model_extra` or `.model_dump()`. The
    known-common fields below are strongly typed for ergonomics.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow", frozen=True)

    timestamp: datetime
    # cowrie.session.params emits `message` as a list; everything else as str.
    message: str | list[Any] | None = None
    sensor: str | None = None
    uuid: str | None = None
    # Most session-scoped events stamp these. Not strictly universal
    # (log.open/closed omit them), so they're optional here.
    src_ip: str | None = None
    src_port: int | None = None
    protocol: str | None = None


# -- Session lifecycle ------------------------------------------------------


class SessionConnect(_EventBase):
    """Incoming TCP connection accepted by cowrie.

    src_ip/src_port/protocol are inherited from _EventBase as Optional; in
    practice cowrie always emits them on this event. dst_ip/dst_port are
    specific to connect.
    """

    eventid: Literal["cowrie.session.connect"] = "cowrie.session.connect"
    dst_ip: str
    dst_port: int
    session_id: str = Field(validation_alias="session")


class SessionParams(_EventBase):
    """Session parameters negotiated after connect (usually arch hint)."""

    eventid: Literal["cowrie.session.params"] = "cowrie.session.params"
    arch: str | None = None
    session_id: str = Field(validation_alias="session")


class SessionClosed(_EventBase):
    """Session teardown, including total duration in seconds."""

    eventid: Literal["cowrie.session.closed"] = "cowrie.session.closed"
    duration: float | None = None
    session_id: str = Field(validation_alias="session")


# -- SSH client introspection -----------------------------------------------


class ClientVersion(_EventBase):
    """Client banner string (e.g. `SSH-2.0-OpenSSH_9.6`)."""

    eventid: Literal["cowrie.client.version"] = "cowrie.client.version"
    version: str
    session_id: str = Field(validation_alias="session")


class ClientKex(_EventBase):
    """Key-exchange algorithms advertised by the client."""

    eventid: Literal["cowrie.client.kex"] = "cowrie.client.kex"
    hassh: str | None = None
    hasshAlgorithms: str | None = None
    kexAlgs: list[str] = Field(default_factory=list)
    keyAlgs: list[str] = Field(default_factory=list)
    encCS: list[str] = Field(default_factory=list)
    macCS: list[str] = Field(default_factory=list)
    compCS: list[str] = Field(default_factory=list)
    langCS: list[str] = Field(default_factory=list)
    session_id: str = Field(validation_alias="session")


class ClientSize(_EventBase):
    """Terminal size requested by the client."""

    eventid: Literal["cowrie.client.size"] = "cowrie.client.size"
    width: int
    height: int
    session_id: str = Field(validation_alias="session")


class ClientVar(_EventBase):
    """Environment variable the client tried to set."""

    eventid: Literal["cowrie.client.var"] = "cowrie.client.var"
    name: str
    value: str
    session_id: str = Field(validation_alias="session")


class ClientFingerprint(_EventBase):
    """Public-key fingerprint offered during pubkey auth."""

    eventid: Literal["cowrie.client.fingerprint"] = "cowrie.client.fingerprint"
    username: str | None = None
    fingerprint: str
    type: str | None = None
    session_id: str = Field(validation_alias="session")


# -- Authentication ---------------------------------------------------------


class LoginSuccess(_EventBase):
    eventid: Literal["cowrie.login.success"] = "cowrie.login.success"
    username: str
    password: str
    session_id: str = Field(validation_alias="session")


class LoginFailed(_EventBase):
    eventid: Literal["cowrie.login.failed"] = "cowrie.login.failed"
    username: str
    password: str
    session_id: str = Field(validation_alias="session")


# -- Shell interaction ------------------------------------------------------


class CommandInput(_EventBase):
    eventid: Literal["cowrie.command.input"] = "cowrie.command.input"
    input: str
    session_id: str = Field(validation_alias="session")


class CommandSuccess(_EventBase):
    eventid: Literal["cowrie.command.success"] = "cowrie.command.success"
    input: str
    session_id: str = Field(validation_alias="session")


class CommandFailed(_EventBase):
    eventid: Literal["cowrie.command.failed"] = "cowrie.command.failed"
    input: str
    session_id: str = Field(validation_alias="session")


# -- File transfer ----------------------------------------------------------


class FileDownload(_EventBase):
    eventid: Literal["cowrie.session.file_download"] = "cowrie.session.file_download"
    url: str | None = None
    outfile: str | None = None
    sha256: str | None = Field(default=None, validation_alias="shasum")
    session_id: str = Field(validation_alias="session")


class FileDownloadFailed(_EventBase):
    eventid: Literal["cowrie.session.file_download.failed"] = (
        "cowrie.session.file_download.failed"
    )
    url: str | None = None
    session_id: str = Field(validation_alias="session")


class FileUpload(_EventBase):
    eventid: Literal["cowrie.session.file_upload"] = "cowrie.session.file_upload"
    filename: str | None = None
    outfile: str | None = None
    sha256: str | None = Field(default=None, validation_alias="shasum")
    session_id: str = Field(validation_alias="session")


# -- Port forwarding attempts -----------------------------------------------


class DirectTcpipRequest(_EventBase):
    eventid: Literal["cowrie.direct-tcpip.request"] = "cowrie.direct-tcpip.request"
    dst_ip: str
    dst_port: int
    src_ip: str | None = None
    src_port: int | None = None
    session_id: str = Field(validation_alias="session")


class DirectTcpipData(_EventBase):
    eventid: Literal["cowrie.direct-tcpip.data"] = "cowrie.direct-tcpip.data"
    dst_ip: str | None = None
    dst_port: int | None = None
    data: str | None = None
    session_id: str = Field(validation_alias="session")


# -- Logger lifecycle (no session) ------------------------------------------


class LogOpen(_EventBase):
    """Cowrie's own log file opened (rare, emitted on cowrie startup)."""

    eventid: Literal["cowrie.log.open"] = "cowrie.log.open"


class LogClosed(_EventBase):
    """Per-session TTY recording closed.

    Despite the `log.closed` eventid this is session-scoped; cowrie emits
    it when the TTY capture file for a session is finalised.
    """

    eventid: Literal["cowrie.log.closed"] = "cowrie.log.closed"
    ttylog: str | None = None
    size: int | None = None
    sha256: str | None = Field(default=None, validation_alias="shasum")
    duplicate: bool | None = None
    duration: float | None = None
    session_id: str | None = Field(default=None, validation_alias="session")


# -- Discriminated union ----------------------------------------------------


CowrieEvent = Annotated[
    Union[
        SessionConnect,
        SessionParams,
        SessionClosed,
        ClientVersion,
        ClientKex,
        ClientSize,
        ClientVar,
        ClientFingerprint,
        LoginSuccess,
        LoginFailed,
        CommandInput,
        CommandSuccess,
        CommandFailed,
        FileDownload,
        FileDownloadFailed,
        FileUpload,
        DirectTcpipRequest,
        DirectTcpipData,
        LogOpen,
        LogClosed,
    ],
    Field(discriminator="eventid"),
]
