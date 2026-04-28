import random
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Final, List, Tuple, Literal, Optional


# ─────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────

class AndarBaharError(Exception):
    """Base exception for all Andar Bahar errors."""


class InvalidBidError(AndarBaharError):
    """Raised when a bidding amount is non-positive."""


class InvalidDelayError(AndarBaharError):
    """Raised when delay is outside the accepted float range."""


class DeckExhaustedError(AndarBaharError):
    """Raised when the deck runs out before a matching card is found."""


class InvalidBiasError(AndarBaharError):
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

Winner = Literal['A', 'B']
BiasType = Literal[0, 1]
CardTuple = Tuple[str, str]
GameOutput = Dict[str, object]


# ─────────────────────────────────────────────
# Card / Deck
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Unknown rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"Unknown suit: {self.suit!r}")

    def as_tuple(self) -> CardTuple:
        return (self.rank, self.suit)

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Deck:
    """A standard 52-card deck. One joker/reference card is opened first."""

    __slots__ = ('_cards',)

    def __init__(self) -> None:
        self._cards: List[Card] = [Card(r, s) for r in RANKS for s in SUITS]

    def shuffle(self) -> None:
        random.shuffle(self._cards)

    def deal_one(self) -> Card:
        if not self._cards:
            raise DeckExhaustedError('Deck has no cards left.')
        return self._cards.pop()

    def __len__(self) -> int:
        return len(self._cards)


# ─────────────────────────────────────────────
# Bias Calculator
# ─────────────────────────────────────────────

class BiasCalculator:
    """Lower bidder is favoured, same idea as your Teen Patti file."""

    @staticmethod
    def calculate(group_a_bidding_amt: float, group_b_bidding_amt: float) -> BiasType:
        if group_a_bidding_amt <= 0 or group_b_bidding_amt <= 0:
            raise InvalidBidError(
                'Bidding amounts must be positive. '
                f'Got A={group_a_bidding_amt}, B={group_b_bidding_amt}.'
            )

        if group_a_bidding_amt < group_b_bidding_amt:
            return 0          # A bids less → bias favours A
        if group_a_bidding_amt > group_b_bidding_amt:
            return 1          # B bids less → bias favours B
        return random.randint(0, 1)  # type: ignore[return-value]


class DelayGuard:
    """Clamps / validates the delay value according to game rules."""

    @staticmethod
    def clamp(delay: float) -> float:
        if not isinstance(delay, (int, float)):
            raise InvalidDelayError(f'Delay must be numeric, got {type(delay).__name__}.')
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
    joker: Card
    andar: Tuple[Card, ...]
    bahar: Tuple[Card, ...]
    winner: Winner
    winning_card: Card
    total_draws: int
    deal_order: Tuple[Winner, ...]


# ─────────────────────────────────────────────
# Andar Bahar Game Engine
# ─────────────────────────────────────────────

class AndarBaharGame:
    """
    Core Andar Bahar engine.

    Flow:
    1. Open one joker/reference card.
    2. Deal one card at a time to A(Andar), then B(Bahar), alternating.
    3. The side that receives the first card with the same rank as joker wins.
    4. Bias is implemented by re-dealing full rounds until the favoured side wins.
    """

    __slots__ = ('bias', 'evaluation_threshold')

    def __init__(self, bias: BiasType, evaluation_threshold: int = 20) -> None:
        if bias not in (0, 1):
            raise InvalidBiasError(f'Bias must be 0 or 1, got {bias!r}.')
        self.bias: BiasType = bias
        self.evaluation_threshold: int = evaluation_threshold

    @staticmethod
    def _deal_round(start_side: Winner = 'A') -> RoundResult:
        deck = Deck()
        deck.shuffle()

        joker = deck.deal_one()
        andar: List[Card] = []
        bahar: List[Card] = []
        current_side: Winner = start_side
        total_draws = 0
        deal_order: List[Winner] = []

        while len(deck) > 0:
            card = deck.deal_one()
            total_draws += 1
            deal_order.append(current_side)

            if current_side == 'A':
                andar.append(card)
            else:
                bahar.append(card)

            if card.rank == joker.rank:
                return RoundResult(
                    joker=joker,
                    andar=tuple(andar),
                    bahar=tuple(bahar),
                    winner=current_side,
                    winning_card=card,
                    total_draws=total_draws,
                    deal_order=tuple(deal_order),
                )

            current_side = 'B' if current_side == 'A' else 'A'

        raise DeckExhaustedError('No matching card found. This should be impossible with a valid deck.')

    @staticmethod
    def _format_cards(cards: Tuple[Card, ...]) -> Tuple[CardTuple, ...]:
        return tuple(card.as_tuple() for card in cards)

    def play_until_winner(self) -> RoundResult:
        target: Winner = 'A' if self.bias == 0 else 'B'

        while True:
            # Randomize starting side so the game does not always begin with Andar.
            start_side: Winner = random.choice(('A', 'B'))
            result = self._deal_round(start_side=start_side)
            if result.winner == target:
                return result

    def generate_output(self, result: RoundResult, delay: float) -> GameOutput:
        return {
            'JOKER': result.joker.as_tuple(),
            'A': self._format_cards(result.andar),
            'B': self._format_cards(result.bahar),
            'WINNER': result.winner,
            'WINNING_CARD': result.winning_card.as_tuple(),
            'TOTAL_DRAWS': result.total_draws,
            'DEAL_ORDER': tuple(result.deal_order),
            'DELAY': delay,
            'TIME': datetime.now().strftime('%H:%M:%S'),
        }


# ─────────────────────────────────────────────
# Game Session
# ─────────────────────────────────────────────

class GameSession:
    _FALLBACK: GameOutput = {
        'JOKER': None,
        'A': None,
        'B': None,
        'WINNER': None,
        'WINNING_CARD': None,
        'TOTAL_DRAWS': None,
        'DELAY': None,
    }

    def __init__(self, group_a_bidding_amt: float, group_b_bidding_amt: float, delay: float) -> None:
        self._a_bid = group_a_bidding_amt
        self._b_bid = group_b_bidding_amt
        self._delay = delay

    def run(self) -> GameOutput:
        try:
            clamped_delay = DelayGuard.clamp(self._delay)
            bias = BiasCalculator.calculate(self._a_bid, self._b_bid)
            threshold = random.randint(MIN_BIAS_THRESHOLD, MAX_BIAS_THRESHOLD)

            game = AndarBaharGame(bias, threshold)
            result = game.play_until_winner()
            return game.generate_output(result, clamped_delay)

        except AndarBaharError as exc:
            print(f'[AndarBahar] Game error: {exc}')
            return {**self._FALLBACK, 'DELAY': self._delay}

        except Exception as exc:
            print(f'[AndarBahar] Unexpected error: {exc}')
            return {**self._FALLBACK, 'DELAY': self._delay}


# ─────────────────────────────────────────────
# Public convenience wrapper
# ─────────────────────────────────────────────

def initiate_game(group_a_bidding_amt: float, group_b_bidding_amt: float, delay: float) -> GameOutput:
    """Same public function name, so backend call-site remains simple."""
    return GameSession(group_a_bidding_amt, group_b_bidding_amt, delay).run()


if __name__ == '__main__':
    for _ in range(10):
        a = random.randint(10, 290)
        b = random.randint(10, 290)
        winner = initiate_game(a, b, 0.3)
        print((a, b, winner["WINNER"]))
