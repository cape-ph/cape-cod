"""Module of naming utility functions."""

# translation table of vowels for removal from strings
VOWELS_TBL = str.maketrans(dict.fromkeys("aeiouAEIOU"))


def disemvowel(s):
    """Return a copy of the given string with vowels removed.

    This is a naive method of shortening strings to deal with max string
    lengths. May need a better plan in the future.

    Args:
        s: the string to remove vowels from.

    Returns:
        A copy of s with vowels removed.
    """
    return ("-").join(w[0] + w[1:].translate(VOWELS_TBL) for w in s.split("-"))
