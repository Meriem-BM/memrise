from datetime import datetime

from memrise.core.time import utc_now


class SystemClock:
    def now(self) -> datetime:
        return utc_now()
