from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional, List, Callable, Dict

import discord
from aiohttp import ClientConnectorError

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.concurrency.workthread import RKAFuture
from rka.components.io.log_service import LogService
from rka.components.security.credentials import CredentialsManager
from rka.components.ui.notification import INotificationService
from rka.eq2.configs import configs_root
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.log_configs import LOG_NOTIFICATIONS

logger = LogService(LOG_NOTIFICATIONS)


class DiscordNotificationService(Closeable, INotificationService):
    MAX_MESSAGE_SIZE = 1900
    START_DELAY = 5 * 60.0

    def __init__(self, credentials_mgr: CredentialsManager):
        Closeable.__init__(self, explicit_close=False)
        self.__calback_commands: Dict[str, str] = dict()
        self.__callback: Optional[Callable[[INotificationService, str], None]] = None
        self.__unmatched_callback: Optional[Callable[[INotificationService, str], None]] = None
        credentials = credentials_mgr.get_credentials('discord-notifications')
        self.__token = credentials['token']
        self.__default_channel_id = int(credentials['channel'])
        self.__running = False
        self.__discord_client: Optional[discord.Client] = None
        self.__semaphore = threading.Semaphore(0)
        self.__start_future: Optional[RKAFuture] = None

    def set_commands(self, callback_commands: List[str], callback: Callable[[INotificationService, str], None]):
        self.__calback_commands = {cmd.strip().lower(): cmd for cmd in callback_commands}
        self.__callback = callback

    def set_callback_for_unmatched_commands(self, callback: Callable[[INotificationService, str], None]):
        self.__unmatched_callback = callback

    async def __parse_public_command(self, message: discord.message.Message) -> bool:
        command_lower = str(message.content).strip().lower()
        if command_lower == 'talk here':
            channel_id = message.channel.id
            self.__default_channel_id = message.channel.id
            await message.channel.send(f'OK. This channel ID is {channel_id}')
            return True
        return False

    async def __parse_private_command(self, message: discord.message.Message):
        command_lower = str(message.content).strip().lower()
        if command_lower in self.__calback_commands and self.__callback:
            self.__callback(self, self.__calback_commands[command_lower])
        elif self.__unmatched_callback:
            self.__unmatched_callback(self, command_lower)

    def __start(self):
        if self.__running:
            return
        RKAThread(target=self.__run, name='Discord client thread').start()
        logger.debug(f'Locking sem in run()')
        self.__semaphore.acquire(timeout=10.0)

    def start(self):
        self.__start_future = shared_scheduler.schedule(self.__start, delay=DiscordNotificationService.START_DELAY)

    def start_now(self):
        self.__start()

    def __run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.debug(f'Created new event loop for discord {loop}')
        self.__discord_client = discord.Client(loop=loop)
        logger.debug(f'Created discord client {self.__discord_client}')

        @self.__discord_client.event
        async def on_ready():
            logger.info(f'Discort Bot logged in as {self.__discord_client}')
            self.__semaphore.release()
            logger.debug(f'Releasing sem for run()')

        @self.__discord_client.event
        async def on_message(message):
            if message.author == self.__discord_client.user:
                return
            logger.info(f'Received message {message}')
            if await self.__parse_public_command(message):
                return
            if message.channel.id == self.__default_channel_id:
                await self.__parse_private_command(message)

        try:
            self.__running = True
            self.__discord_client.loop.run_until_complete(self.__discord_client.start(self.__token))
            # self.__discord_client.run(self.__token)
        except ClientConnectorError as e:
            logger.warn(f'discord client fails to connect {e}')
        finally:
            self.__running = False
            self.__discord_client.loop.run_until_complete(self.__discord_client.close())
            self.__discord_client.loop.close()
            logger.info(f'Returned from discord client loop')

    def set_default_channel_id(self, channel_id: int):
        logger.info(f'Set default channel to {channel_id}')
        self.__default_channel_id = channel_id

    async def __message_me(self, message: str, channel_id: int):
        chunks: List[str] = list()
        remaining_message = message
        while len(remaining_message) > 0:
            chunk = remaining_message[:DiscordNotificationService.MAX_MESSAGE_SIZE]
            current_chunk_len = len(chunk)
            lines = chunk.splitlines(keepends=True)
            if len(lines) == 1 or current_chunk_len == len(remaining_message):
                chunks.append(chunk)
                remaining_message = remaining_message[current_chunk_len:]
            else:
                # there is more and multiple lines will be sent
                whole_lines = lines[:-1]
                chunks.append(''.join(whole_lines))
                remaining_message = lines[-1] + remaining_message[current_chunk_len:]
        for chunk in chunks:
            await self.__discord_client.get_channel(channel_id).send(chunk)
        logger.debug(f'Sent "{message}" to {channel_id}')

    def post_notification(self, message: str, channel_id: Optional[int] = None):
        if not self.__running:
            self.start_now()
        if channel_id is None:
            channel_id = self.__default_channel_id
        logger.info(f'Sending "{message}" to {channel_id}')
        if not self.__running:
            logger.warn(f'Cannot send "{message}" to {channel_id}, not running')
        assert channel_id is not None
        asyncio.run_coroutine_threadsafe(self.__message_me(message, channel_id), self.__discord_client.loop)

    def close(self):
        if self.__start_future:
            self.__start_future.cancel_future()
            self.__start_future = None
        if self.__running:
            logger.debug(f'Closing discord client')
            asyncio.run_coroutine_threadsafe(self.__discord_client.close(), self.__discord_client.loop)
        Closeable.close(self)


if __name__ == '__main__':
    _credentials_mgr = CredentialsManager(configs_root, '')
    s = DiscordNotificationService(_credentials_mgr)
    s.start()
    s.post_notification('hi')
    time.sleep(600.0)
    print('sleep done')
    s.close()
