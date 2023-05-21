import time

import winsound

from rka.components.cleanup import Closeable
from rka.components.concurrency.workthread import RKAWorkerThread


class Alerts(Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__last_alert_end = time.time()
        self.__beep_thread = RKAWorkerThread(name='Beeper thread')
        self.__gap = 500

    def close(self):
        self.__beep_thread.close()
        super().close()

    def __overlaps(self) -> bool:
        now = time.time()
        return now <= self.__last_alert_end

    # noinspection PyMethodMayBeStatic
    def __alert_task(self, frequency: int, duration: int):
        winsound.Beep(frequency, duration)
        # time.sleep(self.__gap)

    def __alert(self, frequency: int, duration: int):
        duration_with_gap = max(duration, self.__gap)
        self.__last_alert_end = time.time() + duration_with_gap / 1000.0
        self.__beep_thread.push_task(lambda: self.__alert_task(frequency, duration))

    def major_trigger(self):
        if self.__overlaps():
            return
        self.__alert(420, 90)

    def minor_trigger(self):
        if self.__overlaps():
            return
        self.__alert(270, 90)

    def micro_trigger(self):
        if self.__overlaps():
            return
        self.__alert(180, 50)


if __name__ == '__main__':
    a = Alerts()
    for i in range(10):
        a.micro_trigger()
        time.sleep(0.2)
    a.close()
