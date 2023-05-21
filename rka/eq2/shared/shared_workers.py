from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.workthread import RKAWorkerThread

shared_scheduler = RKAScheduler('Common scheduler')
shared_worker = RKAWorkerThread('Common worker thread', queue_limit=200)
