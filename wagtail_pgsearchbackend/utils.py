import re

try:
    # Only use the GPLv2 licensed unidecode if it's installed.
    from unidecode import unidecode
except ImportError:
    def unidecode(value):
        return value


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


def get_ancestor_models(model):
    """
    This returns all ancestors of a model, including the model itself.
    """
    models = [model]
    models.extend(model._meta.parents)
    return models
