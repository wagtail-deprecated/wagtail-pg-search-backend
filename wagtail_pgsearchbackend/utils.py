import re


def keyword_split(keywords):
    """
    Return all the keywords in a keyword string.

    Keeps keywords surrounded by quotes together, removing the surrounding quotes:

    >>> keyword_split('Hello I\\'m looking for "something special"')
    ['Hello', "I'm", 'looking', 'for', 'something special']

    Nested quoted strings are returned as is:

    >>> keyword_split("He said \\"I'm looking for 'something special'\\" so I've given him the 'special item'")
    ['He', 'said', "I'm looking for 'something special'", 'so', "I've", 'given', 'him', 'the', 'special item']

    """
    matches = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', keywords)
    return [match[0] or match[1] or match[2] for match in matches]
