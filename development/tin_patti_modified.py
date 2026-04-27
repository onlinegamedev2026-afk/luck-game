"""(মনে রাখার জন্য সিরিয়াল দিলাম)

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
High Card (সবচেয়ে বড় কার্ড)
👉 কিছুই না হলে, বড় কার্ড দেখে জয়"""


import random
from datetime import datetime
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple, Literal


# -----------------------------
# Constants
# -----------------------------
MIN_BIAS_THRESHOLD = 10
MAX_BIAS_THRESHOLD = 20

SUITS = ['H', 'D', 'C', 'S']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']

RANK_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}

# Hand Rankings
TRAIL = 6
PURE_SEQ = 5
SEQ = 4
COLOR = 3
PAIR = 2
HIGH = 1


# -----------------------------
# Card Model
# -----------------------------
@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def value(self):
        return RANK_VALUE[self.rank]


# -----------------------------
# Deck
# -----------------------------
class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, n=3) -> List[Card]:
        return [self.cards.pop() for _ in range(n)]


# -----------------------------
# Hand Evaluator
# -----------------------------
class HandEvaluator:

    @staticmethod
    def is_sequence(values: List[int]) -> bool:
        values = sorted(values)

        # A-2-3 special case
        if values == [2, 3, 14]:
            return True

        return values[2] - values[1] == 1 and values[1] - values[0] == 1

    @staticmethod
    def evaluate(hand: List[Card]) -> Tuple[int, List[int]]:
        values = sorted([c.value() for c in hand])
        suits = [c.suit for c in hand]

        count = Counter(values)
        freq = sorted(count.values(), reverse=True)

        is_flush = len(set(suits)) == 1
        is_seq = HandEvaluator.is_sequence(values)

        # Trail
        if freq == [3]:
            return (TRAIL, [values[2]])  # all three equal; use [2] (max) for semantic clarity

        # Pure Sequence
        if is_seq and is_flush:
            if values == [2, 3, 14]:
                return (PURE_SEQ, [3])  # lowest sequence
            return (PURE_SEQ, [values[2]])  # highest card defines strength

        # Sequence
        if is_seq:
            if values == [2, 3, 14]:
                return (SEQ, [3])  # lowest
            return (SEQ, [values[2]])  # highest card

        # Color
        if is_flush:
            return (COLOR, sorted(values, reverse=True))

        # Pair
        if freq == [2, 1]:
            pair_val = next(k for k, v in count.items() if v == 2)
            kicker = next(k for k, v in count.items() if v == 1)
            return (PAIR, [pair_val, kicker])

        # High Card
        return (HIGH, sorted(values, reverse=True))

    @staticmethod
    def compare(hand1: List[Card], hand2: List[Card]) -> int:
        rank1, val1 = HandEvaluator.evaluate(hand1)
        rank2, val2 = HandEvaluator.evaluate(hand2)

        if rank1 != rank2:
            return 1 if rank1 > rank2 else -1

        for v1, v2 in zip(val1, val2):
            if v1 != v2:
                return 1 if v1 > v2 else -1

        return 0


# -----------------------------
# Game Engine
# -----------------------------
class TinPattiGame:
    def __init__(self, bias: Literal[0, 1] = None, evaluation_threshold: int = 20):
        self.bias = bias  # KEEPING THIS AS REQUESTED
        self.evaluation_threshold = evaluation_threshold

    def play_round(self) -> Tuple[List[Card], List[Card]]:
        deck = Deck()
        deck.shuffle()

        group_A = deck.deal(3)
        group_B = deck.deal(3)

        return group_A, group_B

    def decide_winner(self, group_A, group_B) -> str:
        result = HandEvaluator.compare(group_A, group_B)

        if result == 1:
            return "A"
        elif result == -1:
            return "B"
        return "TIE"

    def play_until_winner(self):
        target = "A" if self.bias == 0 else "B"

        while True:
            group_A, group_B = self.play_round()
            winner = self.decide_winner(group_A, group_B)

            if winner == "TIE":
                continue  # skip ties

            if winner == target:
                return group_A, group_B, winner


    @staticmethod
    def format_hand(hand: List[Card]):
        return tuple((c.rank, c.suit) for c in hand)

    def generate_output(self, group_A, group_B, winner, delay):
        return {
            "A": self.format_hand(group_A),
            "B": self.format_hand(group_B),
            "WINNER": winner,
            "DELAY": delay,
            "TIME": datetime.now().strftime("%H:%M:%S")
        }


# ─────────────────────────────────────────────
# Bias Calculator  (LOGIC UNCHANGED)
# ─────────────────────────────────────────────
def calculate_bias(group_a_bidding_amt: float,
                   group_b_bidding_amt: float) -> Literal[0, 1]:
    if group_a_bidding_amt < group_b_bidding_amt:
        return 0          # A bids less → bias favours A (lower bidder wins)
    if group_a_bidding_amt > group_b_bidding_amt:
        return 1          # B bids less → bias favours B
    return random.randint(0, 1)



# -----------------------------
# Game Entry
# -----------------------------
def initiate_game(group_a_bidding_amt, group_b_bidding_amt, delay):
    try:
        if delay <= 0.2:
            delay = 0.3
        if delay >= 10:
            delay = 9

        bias = calculate_bias(group_a_bidding_amt, group_b_bidding_amt)

        game = TinPattiGame(bias, random.randint(MIN_BIAS_THRESHOLD, MAX_BIAS_THRESHOLD))

        group_A, group_B, winner = game.play_until_winner()

        return game.generate_output(group_A, group_B, winner, delay)

    except Exception as e:
        print("ERROR:", e)
        return {
            "A": None,
            "B": None,
            "WINNER": None,
            "DELAY": delay
        }




# ─────────────────────────────────────────────
# Simulation / Self-test
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