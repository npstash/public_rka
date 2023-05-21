from __future__ import annotations

import asyncio
# noinspection PyProtectedMember
import concurrent.futures._base
import os
import shutil
import tempfile
import threading
from typing import Optional

import discord
from gtts import gTTS

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogService
from rka.components.security.credentials import CredentialsManager
from rka.components.ui.tts import ITTS, ITTSSession
from rka.log_configs import LOG_VOICE_AUDIO

logger = LogService(LOG_VOICE_AUDIO)


class DiscordVoiceClient(discord.Client):
    def __init__(self, voice_channel_id: int, text_channel_id: int, token: str, stay_in_voice_time: float, loop):
        discord.Client.__init__(self, loop=loop)
        self.__voice_channel_id = voice_channel_id
        self.__text_channel_id = text_channel_id
        self.__token = token
        self.__start_semaphore = None
        self.__voice_client = None
        self.__voice_join_lock = asyncio.locks.Lock()
        self.__voice_leave_handle = None
        self.__stay_in_voice_time = stay_in_voice_time
        self.__playback_semaphore = asyncio.locks.Semaphore()

    def run(self, semaphore, *args, **kwargs):
        self.__start_semaphore = semaphore
        super().run(self.__token, *args, **kwargs)

    # noinspection PyMethodMayBeStatic
    async def on_connect(self):
        logger.detail(f'on_connect')

    async def on_ready(self):
        logger.detail(f'on_ready')
        self.__start_semaphore.release()

    # noinspection PyMethodMayBeStatic
    async def on_disconnect(self):
        logger.detail(f'on_disconnect')

    # noinspection PyMethodMayBeStatic
    async def on_voice_state_update(self, *args):
        logger.detail(f'on_voice_state_update" {args}')

    # noinspection PyMethodMayBeStatic
    async def on_voice_server_update(self, *args):
        logger.detail(f'on_voice_server_update" {args}')

    async def join_voice(self) -> discord.VoiceClient:
        logger.debug(f'join_voice')
        voice_leave_handle = self.__voice_leave_handle
        if voice_leave_handle and not voice_leave_handle.cancelled():
            voice_leave_handle.cancel()
        channel = self.get_channel(self.__voice_channel_id)
        async with self.__voice_join_lock:
            if not self.__voice_client:
                self.__voice_client = await channel.connect()
            voice_client = self.__voice_client
        self.__voice_leave_handle = self.loop.create_task(self.delayed_leave_voice())
        return voice_client

    async def leave_voice(self):
        logger.debug(f'leave_voice')
        async with self.__voice_join_lock:
            if self.__voice_client:
                await self.__voice_client.disconnect()
            self.__voice_client = None

    async def delayed_leave_voice(self):
        logger.debug(f'delayed_leave_voice')
        await asyncio.sleep(self.__stay_in_voice_time)
        await self.leave_voice()

    async def voice_sample(self, filename: str):
        logger.debug(f'voice_sample')
        await self.wait_until_ready()
        audio_source = discord.FFmpegPCMAudio(filename, options='-filter:a "atempo=1.2,volume=1.2"')
        voice_client = await self.join_voice()
        await self.__playback_semaphore.acquire()
        voice_client.play(audio_source)
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        self.__playback_semaphore.release()

    async def text_tts_message(self, text: str):
        logger.debug(f'text_tts_message')
        await self.wait_until_ready()
        channel = self.get_channel(self.__text_channel_id)
        channel.send(text, tts=True)

    async def close(self):
        logger.debug(f'close')
        await self.leave_voice()
        await super().close()


class DiscordVoiceService(Closeable, ITTSSession):
    def __init__(self, credentials_mgr: CredentialsManager, stay_in_voice_time: float):
        Closeable.__init__(self, explicit_close=False)
        self.__credentials = credentials_mgr.get_credentials('discord-voice')
        self.__started = False
        self.__start_semaphore: Optional[threading.Semaphore] = None
        self.__stay_in_voice_time = stay_in_voice_time
        self.__tts_temp_dir = os.path.join(tempfile.gettempdir(), 'discord_tts')
        self.__discord_client = None

    def __make_voice_tts_file(self, message: str) -> str:
        logger.debug(f'Generating TTS for "{message}"')
        tts = gTTS(text=message)
        if not os.path.exists(self.__tts_temp_dir):
            os.mkdir(self.__tts_temp_dir)
        tf = tempfile.NamedTemporaryFile(mode='w', dir=self.__tts_temp_dir, delete=False)
        tts.save(tf.name)
        tf.close()
        return tf.name

    def __run_discord_loop(self):
        logger.debug(f'Running service thread')
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.__discord_client = DiscordVoiceClient(voice_channel_id=int(self.__credentials['voice-channel']),
                                                       text_channel_id=int(self.__credentials['text-channel']),
                                                       token=self.__credentials['token'],
                                                       stay_in_voice_time=self.__stay_in_voice_time,
                                                       loop=loop)
            self.__discord_client.run(self.__start_semaphore)
        finally:
            logger.debug(f'Returned from discord client loop')

    @staticmethod
    def __check_immediate_future_exception(future, wait_time: float) -> bool:
        # noinspection PyProtectedMember
        try:
            if future.exception(wait_time):
                return False
        except concurrent.futures._base.CancelledError:
            return False
        except concurrent.futures._base.TimeoutError:
            # dont wait longer, assume it will succeed if it didnt fail within timeout
            return True
        return True

    def start(self) -> bool:
        if self.__started:
            return True
        self.__started = True
        logger.info(f'Starting service')
        thread = RKAThread(target=self.__run_discord_loop, name='Discord Voice client thread')
        self.__start_semaphore = threading.Semaphore(0)
        thread.start()
        self.__start_semaphore.acquire(timeout=5.0)
        if not self.__discord_client or not self.__discord_client.is_ready():
            logger.warn(f'Service is NOT started')
            return False
        logger.debug(f'Service is started')
        return True

    def get_ready(self) -> bool:
        if not self.start():
            return False
        future = asyncio.run_coroutine_threadsafe(self.__discord_client.join_voice(), self.__discord_client.loop)
        return DiscordVoiceService.__check_immediate_future_exception(future, 0.1)

    def say(self, text: str, interrupts=False) -> bool:
        return self.voice_sample(text)

    def text_tts_message(self, text: str) -> bool:
        logger.info(f'text_tts_message {text}')
        if not self.start():
            return False
        future = asyncio.run_coroutine_threadsafe(self.__discord_client.text_tts_message(text), self.__discord_client.loop)
        future.result()
        return True

    def voice_sample(self, text: str) -> bool:
        logger.info(f'voice_sample {text}')
        if not self.start():
            return False
        tts_file = self.__make_voice_tts_file(text)
        future = asyncio.run_coroutine_threadsafe(self.__discord_client.voice_sample(tts_file), self.__discord_client.loop)
        return DiscordVoiceService.__check_immediate_future_exception(future, 0.1)

    def is_session_open(self) -> bool:
        return not self.is_closed()

    def close_session(self):
        self.close()

    def close(self):
        Closeable.close(self)
        logger.info(f'close, started = {self.__started}')
        if self.__started:
            future = asyncio.run_coroutine_threadsafe(self.__discord_client.close(), self.__discord_client.loop)
            future.result()
        if os.path.exists(self.__tts_temp_dir):
            shutil.rmtree(self.__tts_temp_dir)


class DiscordTTSService(ITTS):
    def __init__(self, credentials_mgr: CredentialsManager):
        self.__credentials_mgr = credentials_mgr
        self.__lock = threading.Lock()
        self.__current_session = None

    def open_session(self, keep_open_duration: Optional[float] = None) -> ITTSSession:
        keep_open_duration = keep_open_duration if keep_open_duration else 300.0
        with self.__lock:
            if not self.__current_session or self.__current_session.is_closed():
                self.__current_session = DiscordVoiceService(credentials_mgr=self.__credentials_mgr,
                                                             stay_in_voice_time=keep_open_duration)
        return self.__current_session
