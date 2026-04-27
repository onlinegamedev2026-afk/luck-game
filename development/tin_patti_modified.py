"""(মনে রাখার জন্য সিরিয়াল দিলাম)

Trail / Set (তিনটা একই)
👉 যেমন: A♠ A♥ A♦
Pure Sequence (Straight Flush)
👉 যেমন: 4♥ 5♥ 6♥
Sequence (Straight)
👉 যেমন: 7♣ 8♦ 9♠
Color (Flush)
👉 একই রঙ, কিন্তু সিরিজ না
👉 যেমন: 2♠ 5♠ 9♠
Pair (দুইটা একই)
👉 যেমন: K♠ K♦ 7♣
High Card (সবচেয়ে বড় কার্ড)
👉 কিছুই না হলে, বড় কার্ড দেখে জয়"""


import random
from datetime import datetime
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Final, List, Optional, Tuple, Literal


# ─────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────

class TinPattiError(Exception):
    """Base exception for all Tin Patti errors."""


class InvalidHandError(TinPattiError):
    """Raised when a hand does not contain exactly 3 valid cards."""


class InvalidBidError(TinPattiError):
    """Raised when a bidding amount is non-positive."""


class InvalidDelayError(TinPattiError):
    """Raised when delay is outside the accepted float range."""


class DeckExhaustedError(TinPattiError):
    """Raised when the deck runs out of cards unexpectedly."""


class InvalidBiasError(TinPattiError):
    """Raised when an unsupported bias value is supplied."""


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

MIN_BIAS_THRESHOLD: Final[int] = 10
MAX_BIAS_THRESHOLD: Final[int] = 20

DELAY_MIN: Final[float] = 0.3
DELAY_MAX: Final[float] = 9.0

SUITS: Final[Tuple[str, ...]] = ('H', 'D', 'C', 'S')
RANKS: Final[Tuple[str, ...]] = (
    '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'
)

RANK_VALUE: Final[Dict[str, int]] = {r: i for i, r in enumerate(RANKS, start=2)}

# Hand rank constants
TRAIL:    Final[int] = 6
PURE_SEQ: Final[int] = 5
SEQ:      Final[int] = 4
COLOR:    Final[int] = 3
PAIR:     Final[int] = 2
HIGH:     Final[int] = 1

Winner   = Literal["A", "B", "TIE"]
BiasType = Literal[0, 1]
HandTuple = Tuple[Tuple[str, str], ...]
GameOutput = Dict[str, object]


# ─────────────────────────────────────────────
# Card
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANK_VALUE:
            raise InvalidHandError(f"Unknown rank: '{self.rank!r}'")
        if self.suit not in SUITS:
            raise InvalidHandError(f"Unknown suit: '{self.suit!r}'")

    def value(self) -> int:
        return RANK_VALUE[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self.rank!r}, {self.suit!r})"


# ─────────────────────────────────────────────
# Deck
# ─────────────────────────────────────────────

class Deck:
    """A standard 52-card deck. Shuffle before dealing."""

    __slots__ = ("_cards",)

    def __init__(self) -> None:
        self._cards: List[Card] = [Card(r, s) for r in RANKS for s in SUITS]

    def shuffle(self) -> None:
        random.shuffle(self._cards)

    def deal(self, n: int = 3) -> List[Card]:
        if len(self._cards) < n:
            raise DeckExhaustedError(
                f"Cannot deal {n} cards — only {len(self._cards)} remain."
            )
        return [self._cards.pop() for _ in range(n)]

    def __len__(self) -> int:
        return len(self._cards)


# ─────────────────────────────────────────────
# Hand Evaluator
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class HandRating:
    """Immutable result of evaluating a 3-card hand."""
    rank: int
    tiebreakers: Tuple[int, ...]

    def __gt__(self, other: "HandRating") -> bool:
        if self.rank != other.rank:
            return self.rank > other.rank
        return self.tiebreakers > other.tiebreakers

    def __lt__(self, other: "HandRating") -> bool:
        return other > self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandRating):
            return NotImplemented
        return self.rank == other.rank and self.tiebreakers == other.tiebreakers


class HandEvaluator:
    """Stateless utility class for evaluating and comparing Tin Patti hands."""

    # A-2-3 special sequence sentinel
    _ACE_LOW_SEQ: Final[List[int]] = [2, 3, 14]

    @staticmethod
    def _validate_hand(hand: List[Card]) -> None:
        if len(hand) != 3:
            raise InvalidHandError(
                f"A hand must have exactly 3 cards, got {len(hand)}."
            )

    @classmethod
    def _is_sequence(cls, values: List[int]) -> bool:
        """Return True if the sorted values form a consecutive run (A-2-3 counts)."""
        sv = sorted(values)
        if sv == cls._ACE_LOW_SEQ:
            return True
        return sv[2] - sv[1] == 1 and sv[1] - sv[0] == 1

    @classmethod
    def evaluate(cls, hand: List[Card]) -> HandRating:
        """Evaluate a 3-card hand and return its HandRating."""
        cls._validate_hand(hand)

        values: List[int] = sorted(c.value() for c in hand)
        suits:  List[str] = [c.suit for c in hand]

        count: Counter = Counter(values)
        freq:  List[int] = sorted(count.values(), reverse=True)

        is_flush: bool = len(set(suits)) == 1
        is_seq:   bool = cls._is_sequence(values)

        # Trail
        if freq == [3]:
            return HandRating(TRAIL, (values[2],))

        # Pure Sequence
        if is_seq and is_flush:
            high = 3 if values == cls._ACE_LOW_SEQ else values[2]
            return HandRating(PURE_SEQ, (high,))

        # Sequence
        if is_seq:
            high = 3 if values == cls._ACE_LOW_SEQ else values[2]
            return HandRating(SEQ, (high,))

        # Color
        if is_flush:
            return HandRating(COLOR, tuple(sorted(values, reverse=True)))

        # Pair
        if freq == [2, 1]:
            pair_val: int = next(k for k, v in count.items() if v == 2)
            kicker:   int = next(k for k, v in count.items() if v == 1)
            return HandRating(PAIR, (pair_val, kicker))

        # High Card
        return HandRating(HIGH, tuple(sorted(values, reverse=True)))

    @classmethod
    def compare(cls, hand1: List[Card], hand2: List[Card]) -> int:
        """
        Compare two hands.
        Returns  1 if hand1 wins, -1 if hand2 wins, 0 for a tie.
        """
        r1 = cls.evaluate(hand1)
        r2 = cls.evaluate(hand2)

        if r1 > r2:
            return 1
        if r1 < r2:
            return -1
        return 0


# ─────────────────────────────────────────────
# Bias Calculator
# ─────────────────────────────────────────────

class BiasCalculator:
    """Encapsulates bias logic: lower bidder is favoured. LOGIC UNCHANGED."""

    @staticmethod
    def calculate(group_a_bidding_amt: float,
                  group_b_bidding_amt: float) -> BiasType:
        if group_a_bidding_amt <= 0 or group_b_bidding_amt <= 0:
            raise InvalidBidError(
                "Bidding amounts must be positive. "
                f"Got A={group_a_bidding_amt}, B={group_b_bidding_amt}."
            )

        if group_a_bidding_amt < group_b_bidding_amt:
            return 0          # A bids less → bias favours A (lower bidder wins)
        if group_a_bidding_amt > group_b_bidding_amt:
            return 1          # B bids less → bias favours B
        return random.randint(0, 1)  # type: ignore[return-value]


# ─────────────────────────────────────────────
# Delay Validator
# ─────────────────────────────────────────────

class DelayGuard:
    """Clamps / validates the delay value according to game rules."""

    @staticmethod
    def clamp(delay: float) -> float:
        if not isinstance(delay, (int, float)):
            raise InvalidDelayError(f"Delay must be numeric, got {type(delay).__name__}.")
        if delay <= 0.2:
            return DELAY_MIN
        if delay >= 10:
            return DELAY_MAX
        return float(delay)


# ─────────────────────────────────────────────
# Round Result
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class RoundResult:
    """Immutable snapshot of a single played round."""
    group_a: Tuple[Card, ...]
    group_b: Tuple[Card, ...]
    winner:  Winner


# ─────────────────────────────────────────────
# Game Engine
# ─────────────────────────────────────────────

class TinPattiGame:
    """
    Core game engine.

    Attributes
    ----------
    bias                 : 0 → favour A, 1 → favour B
    evaluation_threshold : max retries before the biased loop stops
                           (unused in termination logic but preserved for parity)
    """

    __slots__ = ("bias", "evaluation_threshold", "_evaluator")

    def __init__(
        self,
        bias: BiasType,
        evaluation_threshold: int = 20,
    ) -> None:
        if bias not in (0, 1):
            raise InvalidBiasError(f"Bias must be 0 or 1, got {bias!r}.")
        self.bias: BiasType = bias                          # KEEPING THIS AS REQUESTED
        self.evaluation_threshold: int = evaluation_threshold
        self._evaluator: HandEvaluator = HandEvaluator()   # stateless; shared ref is fine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deal_round() -> Tuple[List[Card], List[Card]]:
        deck = Deck()
        deck.shuffle()
        return deck.deal(3), deck.deal(3)

    @staticmethod
    def _decide_winner(group_a: List[Card], group_b: List[Card]) -> Winner:
        result = HandEvaluator.compare(group_a, group_b)
        if result == 1:
            return "A"
        if result == -1:
            return "B"
        return "TIE"

    @staticmethod
    def _format_hand(hand: List[Card]) -> HandTuple:
        return tuple((c.rank, c.suit) for c in hand)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_until_winner(self) -> RoundResult:
        """
        Deal and re-deal until the biased side wins (ties are skipped).
        Returns an immutable RoundResult.
        """
        target: Winner = "A" if self.bias == 0 else "B"

        while True:
            group_a, group_b = self._deal_round()
            winner = self._decide_winner(group_a, group_b)

            if winner == "TIE":
                continue

            if winner == target:
                return RoundResult(
                    group_a=tuple(group_a),
                    group_b=tuple(group_b),
                    winner=winner,
                )

    def generate_output(
        self,
        result: RoundResult,
        delay: float,
    ) -> GameOutput:
        return {
            "A":      self._format_hand(list(result.group_a)),
            "B":      self._format_hand(list(result.group_b)),
            "WINNER": result.winner,
            "DELAY":  delay,
            "TIME":   datetime.now().strftime("%H:%M:%S"),
        }


# ─────────────────────────────────────────────
# Game Session  (replaces bare initiate_game fn)
# ─────────────────────────────────────────────

class GameSession:
    """
    Top-level entry point.  Validates inputs, wires all components together,
    and returns the final output dict (or a safe error dict on failure).
    """

    _FALLBACK: GameOutput = {"A": None, "B": None, "WINNER": None, "DELAY": None}

    def __init__(
        self,
        group_a_bidding_amt: float,
        group_b_bidding_amt: float,
        delay: float,
    ) -> None:
        self._a_bid:  float = group_a_bidding_amt
        self._b_bid:  float = group_b_bidding_amt
        self._delay:  float = delay

    def run(self) -> GameOutput:
        try:
            clamped_delay: float = DelayGuard.clamp(self._delay)
            bias:          BiasType = BiasCalculator.calculate(self._a_bid, self._b_bid)
            threshold:     int = random.randint(MIN_BIAS_THRESHOLD, MAX_BIAS_THRESHOLD)

            game:   TinPattiGame = TinPattiGame(bias, threshold)
            result: RoundResult  = game.play_until_winner()

            return game.generate_output(result, clamped_delay)

        except TinPattiError as exc:
            print(f"[TinPatti] Game error: {exc}")
            return {**self._FALLBACK, "DELAY": self._delay}

        except Exception as exc:
            print(f"[TinPatti] Unexpected error: {exc}")
            return {**self._FALLBACK, "DELAY": self._delay}


# ─────────────────────────────────────────────
# Public convenience wrapper  (keeps existing call-site intact)
# ─────────────────────────────────────────────

def initiate_game(
    group_a_bidding_amt: float,
    group_b_bidding_amt: float,
    delay: float,
) -> GameOutput:
    """Thin wrapper so __main__ and any existing callers need zero changes."""
    return GameSession(group_a_bidding_amt, group_b_bidding_amt, delay).run()


# ─────────────────────────────────────────────
# Simulation / Self-test  ← UNTOUCHED
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import tqdm

    correct   = 0
    incorrect = 0
    total     = 50000
    results   = []

    bar = tqdm.tqdm(
        range(total),
        ncols=100,
        desc="Simulating",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {postfix}",
    )

    for i in bar:
        a  = random.randint(10, 200)
        b  = random.randint(10, 300)
        op = initiate_game(a, b, 0.3)

        results.append({"a": a, "b": b,
                        "A": op["A"], "B": op["B"], "W": op["WINNER"]})

        if a < b and op["WINNER"] == "A":
            correct += 1
        elif a > b and op["WINNER"] == "B":
            correct += 1
        elif a == b:
            correct += 1          # tie-bid → either outcome is fine
        else:
            incorrect += 1

        bar.colour = ("red"    if i < total * 0.33 else
                      "yellow" if i < total * 0.66 else
                      "green")
        bar.set_postfix(correct=correct, incorrect=incorrect)

    with open("results_unbiased.json", "w") as f:
        json.dump(results, f, separators=(",", ":"))

    total_decided = correct + incorrect
    print("──────────────────────────────────────────────────────────────")
    print(f"Results saved to results.json  ({len(results)} entries)")
    print(f"Correct   : {correct:>4}  ({correct  / total_decided * 100:.1f} %)")
    print(f"Incorrect : {incorrect:>4}  ({incorrect / total_decided * 100:.1f} %)")