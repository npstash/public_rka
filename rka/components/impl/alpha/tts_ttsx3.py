import random
import threading
from time import sleep
from typing import List, Optional

import pyttsx3.engine

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogService
from rka.components.ui.tts import ITTS, ITTSSession
from rka.log_configs import LOG_VOICE_AUDIO

logger = LogService(LOG_VOICE_AUDIO)


class TTSX3(ITTSSession, Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        ITTSSession.__init__(self)
        self.__tts: Optional[pyttsx3.engine.Engine] = None
        self.__queue: List[Optional[str]] = list()
        self.__queue_lock = threading.Condition()
        self.__running = True
        self.__current_text = None
        RKAThread(name=f'TTS Thread', target=self.__execute_loop).start()

    def __execute_loop(self):
        self.__tts = pyttsx3.init()
        self.__tts.setProperty('volume', 0.6)
        self.__tts.setProperty('rate', 180)
        while self.__running:
            with self.__queue_lock:
                self.__current_text = None
                while len(self.__queue) == 0:
                    self.__queue_lock.wait()
                text = self.__queue.pop(0)
                logger.debug(f'dequed in TTS: {text}')
                if text is None:
                    break
                self.__current_text = text
            self.__tts.say(text)
            self.__tts.runAndWait()
            logger.debug(f'returned from runAndWait after {text}')

    def get_ready(self) -> bool:
        for _ in range(5):
            if self.__tts:
                return True
            sleep(0.2)
        return False

    def say(self, text: str, interrupts=False) -> bool:
        if self.__tts is None:
            sleep(0.2)
        logger.debug(f'say in TTS: {text}, interrupt {interrupts}')
        with self.__queue_lock:
            if self.__current_text == text:
                logger.debug(f'utterance already in progress: {text}')
                return True
            if interrupts:
                logger.debug(f'replacing queue due to interrupting utterance: {text}')
                self.__queue = [text]
                self.__queue_lock.notify()
                return True
            if text in self.__queue:
                logger.debug(f'skip duplicate utterance: {text}')
                return True
            logger.debug(f'appending utterance to the queue: {text}')
            self.__queue.append(text)
            self.__queue_lock.notify()
        return True

    def is_session_open(self) -> bool:
        return self.__running

    def close_session(self):
        self.close()

    def close(self):
        logger.debug(f'stopping TTS engine')
        self.__running = False
        with self.__queue_lock:
            self.__queue.append(None)
            self.__queue_lock.notify()
            if self.__tts is not None:
                self.__tts.stop()
        Closeable.close(self)


class TTSX3Service(ITTS):
    def __init__(self):
        self.__lock = threading.Lock()
        self.__session = None

    def open_session(self, keep_open_duration: Optional[float] = None) -> ITTSSession:
        with self.__lock:
            if not self.__session:
                self.__session = TTSX3()
        return self.__session


if __name__ == '__main__':
    ttss = TTSX3()
    sleep(1)
    ttss.say('The quick brown fox jumped over the lazy dog')
    sleep(2)
    ttss.say('DEATH 1', interrupts=True)
    sleep(1)
    ttss.say('DEATH 2', interrupts=True)
    sleep(1)
    ttss.say('DEATH 3', interrupts=True)
    ttss.say('DEATH 4', interrupts=True)
    ttss.say('DEATH 5', interrupts=True)
    ttss.say('DEATH 6', interrupts=True)
    for i in range(50):
        sleep(random.random() / 10)
        ttss.say('SYNERGY')
    sleep(5)
    ttss.close()
