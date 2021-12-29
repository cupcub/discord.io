# Apache-2.0
#
# Copyright 2021 VincentRPS
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the LICENSE file for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import asyncio
import logging
import sys
import traceback
import typing

from rpd.boot_text import booting_text
from rpd.exceptions import deprecated
from rpd.helpers import MISSING
from rpd.internal import HTTPClient, DiscordWebSocket
from rpd.user import ClientUser

_log = logging.getLogger(__name__)

__all__ = "Client"

Snowflake = typing.Union[str, int]
SnowflakeList = typing.List[Snowflake]

T = typing.TypeVar("T")
Coro = typing.Coroutine[typing.Any, typing.Any, T]
CoroFunc = typing.Callable[..., Coro[typing.Any]]
CFT = typing.TypeVar("CFT", bound="CoroFunc")


class Client:
    """The base Client for RPD interactions

    .. versionadded:: 2.0

    Attributes
    ----------
    loop
        The Abstract Event Loop Function
    http
        The :class:`HTTPClient`
    ws
        The :class:`DiscordWebSocket`

    Parameters
    ----------

    """

    def __init__(self, token: str, loop: typing.Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop
        self._listeners: typing.Dict[
            str, typing.List[typing.Tuple[asyncio.Future, typing.Callable[..., bool]]]
        ] = {}
        self.token = token
        self.http = HTTPClient()
        self.ws = DiscordWebSocket(self)

    def on_error(self, e_meth: str) -> None:
        """Handles errors for :class:`Client` default.

        .. versionadded:: 0.3.0
        """
        print(f"Handling error in {e_meth}", file=sys.stderr)
        traceback.print_exc()

    async def _run_event(
        self,
        coro: typing.Callable[
            ..., typing.Coroutine[typing.Any, typing.Any, typing.Any]
        ],
        event_name: str,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                await self.on_error(event_name, *args, **kwargs)
            except asyncio.CancelledError:
                pass

    def _schedule_event(
        self,
        coro: typing.Callable[
            ..., typing.Coroutine[typing.Any, typing.Any, typing.Any]
        ],
        event_name: str,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> asyncio.Task:
        wrapped = self._run_event(coro, event_name, *args, **kwargs)
        return asyncio.create_task(wrapped, name=f"rpd: {event_name}")

    def dispatch(self, event: str, *args: typing.Any, **kwargs: typing.Any):
        """Used for dispatching events to `Client.listen`.

        .. versionadded:: 0.3.0
        """
        _log.debug(f"Dispatch of {event} is now starting...")
        event_name = f"on_{event}"

        listeners = self._listeners.get(event)

        if listeners:
            removed = []

            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as E:
                    future.set_exception(E)
                    removed.append(i)
                else:
                    if result:
                        if not args or MISSING:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)
            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, event_name)
        except AttributeError:
            pass
        else:
            self._schedule_event(coro, event_name, *args, **kwargs)

    async def login(self):
        """|coro|
        Logs in the client with the specified credentials.

        .. versionadded:: 0.3.0

        Parameters
        -----------
        token: :class:`str`
            Your bot token.
        Raises
        ------
        :exc:`.LoginFailure`
            The token passed was invalid.
        :exc:`.HTTPException`
            An unknown HTTP related error occurred,
            usually when it isn't 200 or the known incorrect credentials
            passing status code.
        """

        _log.info("Trying to login with the specified credentials")
        
        token = self.token

        data = await self.http._client_login(token.strip())
        self._connection.user = ClientUser(data=data)

    async def logout(self):
        await self.http._client_logout()

    async def connect(self):
        """Starts the WebSocket connection with discord.

        .. versionadded:: 0.3.0
        """

    async def start(self, token: str, auto_reconnect: bool = True) -> None:
        """Combines both :meth:`Client.ws_start` and :meth:`Client.login`"""
        print(booting_text)
        await self.login(token)
        # await self.ws_start(reconnect=auto_reconnect)

    def run(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        """A easy blocking call that starts both the WebSocket and HTTP connections"""

    def listen(self, coro: Coro) -> Coro:
        print(booting_text)
        print(
            "This function has been removed please use Client.event, else events won't work anymore."
        )
        print("Tried to register %s", coro)

    def event(self, coro: Coro) -> Coro:
        """Listen to a certain event

        .. versionadded:: 0.1.0
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError(
                "The event registered must be a coroutine function, else Client will not parse it."
            )

        setattr(self, coro.__name__, coro)
        _log.debug(f"{coro.__name__} has been registered as a event.")
        return coro
