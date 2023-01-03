import json
import pathlib
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.transfermarkt.co.uk/premier-league/einnahmenausgaben/wettbewerb/GB1/plus/1"

DATA_DIR = pathlib.Path(__file__).absolute().parent.parent / "data"


def _get_data_for_season(season: int) -> List[Dict[str, Any]]:
    """
    Scrapes the data from transfermarkt for the season specified in the parameter. The
    season should be a 4 digit year and mark the beginning of the season for example, to
    get the data fro 2021/2022, enter 2021.
    """
    rows = []
    params = {
        "ids": "a",
        "sa": "1",
        "saison_id": str(season),
        "saison_id_bis": str(season),
        "nat": "",
        "altersklasse": "",
        "w_s": "",
        "leihe": "",
        "intern": "0",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    r = requests.get(BASE_URL, params=params, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    for row in soup.select("#yw1 table tbody tr"):
        columns = row.find_all("td")
        rows.append(
            {
                "season": season,
                "club": columns[2].string,
                "expenditure": columns[5].string,
                "arrival": columns[6].string,
                "income": columns[7].string,
                "departures": columns[8].string,
                "balance": columns[9].string,
            }
        )
    return rows


def _crawl():
    all = []
    for season in range(1992, 2022):
        all = all + _get_data_for_season(season)
        with open(f"{DATA_DIR}/92-21_income_expense_raw.json", "w") as fp:
            json.dump(all, fp, indent=2)


if __name__ == "__main__":
    _crawl()
