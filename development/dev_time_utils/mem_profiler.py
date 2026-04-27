import tracemalloc

def tin_patti_game_memory_profiler():
    tracemalloc.start()
    from tin_patti_modified import initiate_game
    import random
    import json
    import tqdm

    correct   = 0
    incorrect = 0
    total     = 500000

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


    total_decided = correct + incorrect
    print("──────────────────────────────────────────────────────────────")

    print(f"Correct   : {correct:>4}  ({correct  / total_decided * 100:.1f} %)")
    print(f"Incorrect : {incorrect:>4}  ({incorrect / total_decided * 100:.1f} %)")

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Current : {(current / 1024) /1024:.2f} MB")
    print(f"Peak    : {(peak / 1024) / 1024:.2f} KB")


if __name__ == "__main__":
    tin_patti_game_memory_profiler()
    