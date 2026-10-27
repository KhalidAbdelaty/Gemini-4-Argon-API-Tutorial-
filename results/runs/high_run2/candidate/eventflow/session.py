"""Per-customer session state."""

import bisect
import copy

from eventflow.history import summarize


def _order_key(event):
    return (event.ts, event.seq)


class CustomerState:
    """Holds one customer's events in processing order (timestamp, then arrival)."""

    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self._events = []
        self._event_ids = set()
        self._summary = None

    @property
    def summary(self):
        if self._summary is None:
            self._summary = summarize(self._events)
        return self._summary

    @summary.setter
    def summary(self, value):
        self._summary = value

    def get_history(self):
        """Return a snapshot of this customer's events in processing order.

        The snapshot belongs to the caller, who may modify the list or the
        events in it without affecting the state.
        """
        return copy.deepcopy(self._events)

    def has_event(self, event_id: str) -> bool:
        return event_id in self._event_ids

    def add(self, event) -> None:
        self._event_ids.add(event.event_id)
        events = self._events
        if not events:
            events.append(event)
        else:
            last = events[-1]
            if last.ts < event.ts or (last.ts == event.ts and last.seq <= event.seq):
                events.append(event)
            else:
                bisect.insort(events, event, key=_order_key)
        self._summary = None
