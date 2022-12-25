import requests
import json
import pathlib

from typing import List, Dict, Any
from bs4 import BeautifulSoup


DATA_DIR = pathlib.Path(__file__).absolute().parent.parent / "data"

def _get_table_data(season: int) -> List[Dict[str, Any]]:
    table = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': '*/*'
    }
    r = requests.get(f"https://www.transfermarkt.co.uk/premier-league/tabelle/wettbewerb/GB1/saison_id/{season}", headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')

    for row in soup.select("#yw1 table tbody tr"):
        columns = row.find_all('td')
        table.append({
            "position": columns[0].contents[0].strip(),
            "club": columns[2].contents[1].string.strip(),
            "played": columns[3].string.strip(),
            "won": columns[4].string.strip(),
            "drawn": columns[5].string.strip(),
            "lost": columns[6].string.strip(),
            "goals": columns[7].string.strip(),
            "goals_diff": columns[8].string.strip(),
            "points": columns[9].string.strip(),
        })
    return table


if __name__ == "__main__":
    all = []
    for season in range(1992, 2022):
        all = all + _get_table_data(season)

    with open(f"{DATA_DIR}/club_tables.json", "w") as fp:
        json.dump(all, fp, indent=2)