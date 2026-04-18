"""Pydantic models for cowrie's JSON log schema.

`CowrieEvent` is a discriminated union keyed on `eventid`; unknown events
fail validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _EventBase(BaseModel):
    """Common envelope for every cowrie event; unknown fields preserved via `extra="allow"`."""

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
    eventid: Literal["cowrie.session.connect"] = "cowrie.session.connect"
    dst_ip: str
    dst_port: int
    session_id: str = Field(validation_alias="session")


class SessionParams(_EventBase):
    eventid: Literal["cowrie.session.params"] = "cowrie.session.params"
    arch: str | None = None
    session_id: str = Field(validation_alias="session")


class SessionClosed(_EventBase):
    eventid: Literal["cowrie.session.closed"] = "cowrie.session.closed"
    duration: float | None = None
    session_id: str = Field(validation_alias="session")


# -- SSH client introspection -----------------------------------------------


class ClientVersion(_EventBase):
    eventid: Literal["cowrie.client.version"] = "cowrie.client.version"
    version: str
    session_id: str = Field(validation_alias="session")


class ClientKex(_EventBase):
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
    eventid: Literal["cowrie.client.size"] = "cowrie.client.size"
    width: int
    height: int
    session_id: str = Field(validation_alias="session")


class ClientVar(_EventBase):
    eventid: Literal["cowrie.client.var"] = "cowrie.client.var"
    name: str
    value: str
    session_id: str = Field(validation_alias="session")


class ClientFingerprint(_EventBase):
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
