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
        self.summary = summarize([])

    def get_history(self):
        """Return a snapshot of this customer's events in processing order.

        The snapshot belongs to the caller, who may modify the list or the
        events in it without affecting the state.
        """
        return copy.deepcopy(self._events)

    def has_event(self, event_id: str) -> bool:
        return any(e.event_id == event_id for e in self.get_history())

    def add(self, event) -> None:
        bisect.insort(self._events, event, key=_order_key)
        self.summary = summarize(self.get_history())
