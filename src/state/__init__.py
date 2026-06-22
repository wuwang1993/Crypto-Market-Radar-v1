"""State judgment engine — Phase 4 of Crypto Market Radar Bot.

Exports:
    MarketState — enum of 16 market states
    evaluate_state(snap, prev_state) → (MarketState, score)
"""

from src.state.state_types import MarketState
from src.state.engine import evaluate_state

__all__ = ["MarketState", "evaluate_state"]
