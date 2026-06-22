"""Scheduler package — periodic summaries, heatmap, daily report."""

from src.scheduler.jobs import SummaryScheduler


def start_scheduler(exchange, send_fn):
    """Convenience factory: create and return a SummaryScheduler."""
    return SummaryScheduler(exchange, send_fn)


__all__ = ["SummaryScheduler", "start_scheduler"]
