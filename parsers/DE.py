import json
import re
from datetime import datetime
from logging import Logger, getLogger
from typing import Any

import arrow
from pytz import timezone
from requests import Response, Session

from electricitymap.contrib.lib.models.event_lists import ProductionBreakdownList
from electricitymap.contrib.lib.models.events import ProductionMix, StorageMix
from electricitymap.contrib.lib.types import ZoneKey
from parsers.lib.exceptions import ParserException

# There was also data about conventional power but I didn't know what to add it to, so I didn't use it.
TYPE_MAPPING = {
    r'{"id":"solar".*?]}': "solar",
    r'{"id":"biomass".*?]}': "biomass",
    r'{"id":"gas".*?]}': "gas",
    r'{"id":"run-of-the-river".*?]}': "hydro",
    r'{"id":"uranium".*?]}': "nuclear",
    r'{"id":"wind-onshore".*?]}': "wind",  # wind-onshore and wind-offshore is added to wind
    r'{"id":"wind-offshore".*?]}': "wind",
    r'{"id":"coal".*?]}': "coal",  # coal and lignite data is added to coal
    r'{"id":"lignite".*?]}': "coal",
}


def fetch_production(
    zone_key: ZoneKey,
    session: Session = Session(),
    target_datetime: datetime | None = None,
    logger: Logger = getLogger(__name__),
) -> list[dict] | dict:

    # Requests the last known production mix (in MW) of a given country.

    if target_datetime:
        raise NotImplementedError("This parser is not yet able to parse past dates")

    datetime_today = datetime.today().strftime("%d.%m.%Y")
    url = f"https://www.agora-energiewende.de/en/service/recent-electricity-data/chart/data/power_generation/{datetime_today}/{datetime_today}/today/chart.json"

    res: Response = session.get(url)
    if not res.status_code == 200:
        raise ParserException(
            "DE.py",
            f"Exception when fetching production error code: {res.status_code}: {res.text}",
            zone_key,
        )

    production_mix = ProductionMix()
    production_list = ProductionBreakdownList(logger=logger)

    obj = res.json()
    # logger.debug(f"Raw generation breakdown: {obj}")

    series_pattern = r'"series":\[.*\]'
    series_match = re.search(series_pattern, obj["js"])
    series_string = series_match.group()

    data_pattern = r"\[.+\]"
    for pattern, mode in TYPE_MAPPING.items():
        data_match = re.search(pattern, series_string)
        data_string = data_match.group()
        data_match = re.search(data_pattern, data_string)
        json_data = json.loads(data_match.group())
        last_data_point = json_data[-1][1]
        production_mix.add_value(mode, last_data_point)

    production_list.append(
        zoneKey=zone_key,
        datetime=arrow.utcnow().datetime,
        production=production_mix,
        storage={},
        source="https://www.agora-energiewende.de",
    )
    return production_list.to_list()


if __name__ == "__main__":
    """Main method, never used by the Electricity Maps backend, but handy for testing."""

    print("fetch_production(DE) ->")
    print(fetch_production(ZoneKey("DE")))
