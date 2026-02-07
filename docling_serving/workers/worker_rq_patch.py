from rq import SimpleWorker
from rq.timeouts import TimerDeathPenalty
from rq.utils import now
from rq.worker import BaseWorker


class PatchedSimpleWorker(SimpleWorker):
    def _install_signal_handlers(self):
        return

    def request_stop(self, signum, frame):
        try:
            self._shutdown_requested_date = now()
            self.handle_warm_shutdown_request()
            self._shutdown()
        except BaseException:
            pass


BaseWorker.death_penalty_class = TimerDeathPenalty
