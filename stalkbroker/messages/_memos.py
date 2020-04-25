import random


_MEMOS = [
    "401K through the vegetable way.",
    "Turn-up your profits.",
    "Lets unearth a fortune, together.",
    "Not just another piece of shovelware",
]


def random_memo() -> str:
    """
    Pick a random memo to add to a report / bulletin.

    :returns: random memo.
    """
    return random.choice(_MEMOS)
