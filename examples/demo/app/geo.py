import asyncio

COUNTRY_DELAY = 3.0
CHILD_DELAY = 1.5
GRID_DELAY = 3.0


async def grid_delay():
    await asyncio.sleep(GRID_DELAY)

COUNTRIES = [("br", "Brazil"), ("us", "United States")]

STATES = {
    "br": [("sp", "São Paulo"), ("rj", "Rio de Janeiro")],
    "us": [("ca", "California"), ("ny", "New York")],
}

CITIES = {
    "sp": [("sao", "São Paulo"), ("cam", "Campinas")],
    "rj": [("rio", "Rio de Janeiro"), ("nit", "Niterói")],
    "ca": [("la", "Los Angeles"), ("sf", "San Francisco")],
    "ny": [("nyc", "New York City"), ("buf", "Buffalo")],
}

DISTRICTS = {
    "sao": [("pin", "Pinheiros"), ("moo", "Mooca")],
    "cam": [("cen", "Centro"), ("bar", "Barão Geraldo")],
    "rio": [("cop", "Copacabana"), ("ipa", "Ipanema")],
    "nit": [("ica", "Icaraí"), ("san", "Santa Rosa")],
    "la": [("dtla", "Downtown"), ("hol", "Hollywood")],
    "sf": [("mis", "Mission"), ("soma", "SoMa")],
    "nyc": [("man", "Manhattan"), ("bro", "Brooklyn")],
    "buf": [("elm", "Elmwood"), ("all", "Allentown")],
}

ALL_STATES = [pair for pairs in STATES.values() for pair in pairs]
ALL_CITIES = [pair for pairs in CITIES.values() for pair in pairs]
ALL_DISTRICTS = [pair for pairs in DISTRICTS.values() for pair in pairs]


def _limit(params):
    return max(1, min(int(params.get("limit", 20)), 50))


def _options(pairs, params):
    if params.get("value"):
        return [{"value": value, "label": label} for value, label in pairs if value == params["value"]]

    query = (params.get("q") or "").lower()
    matches = [{"value": value, "label": label} for value, label in pairs if query in label.lower()]

    return matches[: _limit(params)]


def country_options():
    async def handler(session, params, locale):
        await asyncio.sleep(COUNTRY_DELAY)

        return _options(COUNTRIES, params)

    return handler


def state_options(parent_field):
    async def handler(session, params, locale):
        await asyncio.sleep(CHILD_DELAY)

        if params.get("value"):
            return _options(ALL_STATES, params)

        parent = params.get(parent_field)

        return _options(STATES.get(parent, []), params) if parent else []

    return handler


def city_options(parent_field):
    async def handler(session, params, locale):
        await asyncio.sleep(CHILD_DELAY)

        if params.get("value"):
            return _options(ALL_CITIES, params)

        parent = params.get(parent_field)

        return _options(CITIES.get(parent, []), params) if parent else []

    return handler


def district_options(parent_field):
    async def handler(session, params, locale):
        await asyncio.sleep(CHILD_DELAY)

        if params.get("value"):
            return _options(ALL_DISTRICTS, params)

        parent = params.get(parent_field)

        return _options(DISTRICTS.get(parent, []), params) if parent else []

    return handler
