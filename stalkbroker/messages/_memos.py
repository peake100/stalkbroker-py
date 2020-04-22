import random


_MEMOS = [
    "401K through the vegetable way.",
    "Turning-up your profits.",
    "Lets unearth a fortune, together.",
    "Not just another piece of shovelware",
]


def random_memo() -> str:
    return random.choice(_MEMOS)
