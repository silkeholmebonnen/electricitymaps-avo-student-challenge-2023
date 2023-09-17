from datetime import datetime
from logging import Logger, getLogger
from typing import Any
import re
import json
import arrow

from pytz import timezone

# The request library is used to fetch content through HTTP
from requests import Response, Session

from electricitymap.contrib.lib.models.event_lists import (
    ProductionBreakdownList,
)
from electricitymap.contrib.lib.models.events import ProductionMix, StorageMix
from electricitymap.contrib.lib.types import ZoneKey
from parsers.lib.exceptions import ParserException

'''
    I used pattern matching because the json file that the website receives from a backend, held the data in some 
    JavaScript object, so the json that was holding the data also contained method calls, e.g. showconventionalSeries, 
    so when trying to decode the json with json.loads() it gave errors. I would have looked into doing this another 
    way if I had more time.

    The data also had data about conventional power but I didn't know where to add it, so I didn't use it.
    I don't know if it is correct but I added coal and lignite data to coal.
'''

TYPE_MAPPING = {
    r'{"id":"solar".*?]}': "solar", 
    r'{"id":"biomass".*?]}': "biomass",
    r'{"id":"coal".*?]}': "coal",
    r'{"id":"gas".*?]}': "gas",
    r'{"id":"run-of-the-river".*?]}': "hydro",
    r'{"id":"uranium".*?]}': "nuclear",
    r'{"id":"wind-onshore".*?]}': "wind",
    r'{"id":"wind-offshore".*?]}': "wind",
    r'{"id":"lignite".*?]}': "coal", 
}

def fetch_production(
    zone_key: ZoneKey,
    session: Session = Session(),
    target_datetime: datetime | None = None,
    logger: Logger = getLogger(__name__),
) -> list[dict] | dict:

    #Requests the last known production mix (in MW) of a given country.
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
    #logger.debug(f"Raw generation breakdown: {obj}")

    series_pattern = r'"series":\[.*\]'
    match = re.search(series_pattern, obj["js"])
    json_string = match.group()
    pat = r'\[.+\]'

    for pattern, mode in TYPE_MAPPING.items():
        match = re.search(pattern, json_string)
        group = match.group()
        data_match = re.search(pat, group)
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

    print("fetch_production(XX) ->")
    print(fetch_production(ZoneKey("XX")))
