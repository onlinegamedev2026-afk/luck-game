import json

# Card value mapping
RANK_ORDER = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7,
              '8':8, '9':9, 'T':10, 'J':11, 'Q':12, 'K':13, 'A':14}

def is_sequence(values):
    values = sorted(values)
    
    # Normal sequence
    if values[2] - values[1] == 1 and values[1] - values[0] == 1:
        return True
    
    # A-2-3 special case
    if values == [2, 3, 14]:
        return True
    
    return False

def hand_rank(hand):
    values = sorted([RANK_ORDER[r] for r, s in hand])
    suits = [s for r, s in hand]
    
    is_flush = len(set(suits)) == 1
    seq = is_sequence(values)
    
    # Count occurrences
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    count_values = sorted(counts.values(), reverse=True)

    # Trail (3 same)
    if count_values == [3]:
        return (6, values[::-1])
    
    # Pure sequence
    if seq and is_flush:
        if values == [2, 3, 14]:
            return (5, [3])  # lowest
        return (5, [values[2]])  # highest card
    
    # Sequence
    if seq:
        if values == [2, 3, 14]:
            return (4, [3])  # lowest
        return (4, [values[2]])
    
    # Color
    if is_flush:
        return (3, values[::-1])
    
    # Pair
    if count_values == [2,1]:
        pair = max(counts, key=lambda x: (counts[x], x))
        kicker = min(counts, key=lambda x: (counts[x], x))
        return (2, [pair, kicker])
    
    # High card
    return (1, values[::-1])

def compare_hands(A, B):
    rankA = hand_rank(A)
    rankB = hand_rank(B)
    
    if rankA > rankB:
        return 'A'
    elif rankB > rankA:
        return 'B'
    else:
        return 'Tie'

# Load your JSON file
with open("results_unbiased.json", "r") as f:
    data = json.load(f)

errors = []

for i, game in enumerate(data):
    A = game['A']
    B = game['B']
    expected = game['W']
    
    result = compare_hands(A, B)
    
    if result != expected:
        errors.append({
            "index": i,
            "A": A,
            "B": B,
            "expected": expected,
            "got": result
        })

# Output results
print(f"Total games: {len(data)}")
print(f"Mismatches: {len(errors)}")

if errors:
    print("\nSome mismatches:")
    for e in errors[:10]:
        print(e)
else:
    print("All results are correct ✅")