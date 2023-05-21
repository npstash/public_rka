from typing import Optional


class ITTSSession:
    def get_ready(self) -> bool:
        raise NotImplementedError()

    def say(self, text: str, interrupts=False) -> bool:
        raise NotImplementedError()

    def is_session_open(self) -> bool:
        raise NotImplementedError()

    def close_session(self):
        raise NotImplementedError()


class ITTS:
    def open_session(self, keep_open_duration: Optional[float] = None) -> ITTSSession:
        raise NotImplementedError()
