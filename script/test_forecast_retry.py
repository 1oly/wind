"""Check the retry loop in forecastedr_script_DINI.py without calling DMI.

Runs the loop's real source text against a stub client and a fake clock.
"""
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path(__file__).with_name('forecastedr_script_DINI.py').read_text()
LOOP = SRC[SRC.index('forecast = None'):SRC.index('geo = []')]


class FakeTime:
    """Clock that only moves when the loop sleeps, so the test runs instantly."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def run(responses, give_up=timedelta(minutes=10)):
    """Replay `responses` (a list of feature lists or exceptions) through the loop."""
    calls, clock = [], FakeTime()

    class Client:
        def get_forecast(self, **kwargs):
            reply = responses[min(len(calls), len(responses) - 1)]
            calls.append(kwargs['to_time'])
            if isinstance(reply, Exception):
                raise reply
            return reply

    namespace = {
        'client': Client(), 'time': clock, 'timedelta': timedelta,
        'dtnow': datetime(2026, 9, 18, 20), 'HEIGHTS': ['10m'],
        'Collection': type('C', (), {'HarmonieDiniSf': 'sf'}),
        'GIVE_UP_AFTER': give_up, 'print': lambda *a, **k: None,
    }
    try:
        exec(LOOP, namespace)
    except SystemExit as exc:
        return None, calls, clock.slept, str(exc)
    return namespace['forecast'], calls, clock.slept, None


ok = [{'wind': 1}]

forecast, calls, slept, exit_msg = run([ok])
assert forecast == ok and len(calls) == 1 and slept == [] and exit_msg is None, 'clean fetch should not retry'

forecast, calls, slept, exit_msg = run([ValueError('429 busy'), ok])
assert forecast == ok and slept == [60] and exit_msg is None, 'a 429 should be retried after a wait'

# an empty reply means that step is not published yet: walk back an hour at a time first
forecast, calls, slept, exit_msg = run([[], [], [], ok])
assert forecast == ok and len(calls) == 4, 'should walk back through earlier hours'
assert [c.hour for c in calls[:3]] == [20, 19, 18], 'should step back one hour at a time'
assert slept == [60], 'only waits once all three hours came back empty'

forecast, calls, slept, exit_msg = run([ValueError('429 busy')], give_up=timedelta(minutes=3))
assert forecast is None and slept == [60, 60, 60] and 'within 0:03:00' in exit_msg, 'should give up at the deadline'

print('retry loop ok')
