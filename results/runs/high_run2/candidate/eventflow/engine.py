"""The EventFlow engine: ingest events, then ask for reports."""

from eventflow.models import validate
from eventflow.reports import build_report
from eventflow.session import CustomerState


class EventFlow:
    """Process events into per-customer state and reports.

    Public contract:

    * ``ingest()`` can be called any number of times. ``report()`` always
      reflects every event ingested so far, in timestamp order, even when a
      later batch contains events with earlier timestamps.
    * An event whose ``event_id`` was already seen for that customer is a
      duplicate and is ignored. The first copy wins.
    * Customers never affect each other's reports.
    * ``history()`` and ``report()`` return objects the caller owns.
      Modifying them never changes the engine's state.
    * ``ingest()`` never modifies the raw dicts it is given.
    """

    def __init__(self):
        self._customers = {}
        self._seq = 0

    def ingest(self, raw_events) -> int:
        """Validate and store events. Returns how many were accepted."""
        accepted = 0
        for raw in raw_events:
            event = validate(raw, seq=self._seq)
            self._seq += 1
            state = self._customers.get(event.customer_id)
            if state is None:
                state = CustomerState(event.customer_id)
                self._customers[event.customer_id] = state
            if state.has_event(event.event_id):
                continue
            state.add(event)
            accepted += 1
        return accepted

    def customers(self) -> list:
        return sorted(self._customers)

    def history(self, customer_id: str) -> list:
        return self._customers[customer_id].get_history()

    def report_for(self, customer_id: str):
        return build_report(self._customers[customer_id])

    def report(self) -> dict:
        return {cid: build_report(self._customers[cid]) for cid in sorted(self._customers)}
