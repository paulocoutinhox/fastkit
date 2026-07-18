class _LenientParams(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def format_message(template: str, params: dict) -> str:
    if not params:
        return template

    try:
        return template.format_map(_LenientParams(params))
    except (ValueError, IndexError, KeyError, AttributeError, TypeError):
        return template
