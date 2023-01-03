from pathlib import Path

import fire
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import json
import glob

DATA_DIR = Path(__file__).parent.resolve().parent.resolve() / "data"


_headers = {
    "Accept": "text/html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/108.0.0.0 Safari/537.36"
    ),
}



class EPLCommands:
    def download_match(self, match_id: int, force=False):
        """
        Download the HTML page for the match from premierleague.com
        """
        destination_file = (
            DATA_DIR / f"extract/premierleague.com/matches/{match_id}.html"
        )
        if not force and destination_file.is_file():
            raise SystemExit("Match already downloaded")

        r = requests.get(
            f"https://www.premierleague.com/match/{match_id}", headers=_headers
        )
        if not r.ok:
            raise SystemExit(
                f"! ERROR: failed to download web page. Status code={r.status_code}"
            )

        with open(destination_file, "w") as fp:
            fp.write(r.text)

        print(f"> Downloaded match {match_id} to {destination_file}")


    def process_season_results(self, season: str, return_result=False):
        """
        Extract the data from the season results web page and transform it into cleaned
        JSON data.

        The web pages have to be downloaded manually due to the asynchronous nature the 
        pagination loads as you scroll down the page.
        """
        season_file_name = f"{season.replace('/', '_')}.html"
        raw_file = DATA_DIR / f"extract/premierleague.com/results/{season_file_name}"
        if not raw_file.is_file():
            raise SystemError(f"No file found for the {season} season")

        with open(raw_file) as fp:
            soup = BeautifulSoup(fp.read(), "html.parser")

        results = []

        for div in soup.select(".fixtures div[data-competition-matches-list]"):
            fixture_date = div.get("data-competition-matches-list")
            assert isinstance(fixture_date, str)

            for fixture in div.select(".matchList li"):
                home_team = fixture.get("data-home")
                away_team = fixture.get("data-away")
                venue = fixture.get("data-venue")
                assert isinstance(venue, str)
                score = fixture.select_one(".overview .teams .score")
                assert score
                score = score.text.split("-")

                team_names = fixture.select(".overview .teams .teamName")
                assert team_names

                # matchid
                match_id = fixture.select_one("[data-matchid]")
                assert match_id
                match_id = match_id.get("data-matchid")
                assert isinstance(match_id, str)

                # match kick off time (milliseconds)
                match_ko = fixture.get("data-comp-match-item-ko")
                assert isinstance(match_ko, str)

                home_team_abbr = team_names[0].select_one(".abbr")
                away_team_abbr = team_names[1].select_one(".abbr")
                assert home_team_abbr
                assert away_team_abbr

                results.append(
                    {
                        "match_id": int(match_id),
                        "match_ko": int(match_ko),
                        "date": fixture_date,
                        "home_team": home_team,
                        "home_team_abbr": home_team_abbr.text,
                        "away_team": away_team,
                        "away_team_abbr": away_team_abbr.text,
                        "venue": re.sub(r"<[^<]+?>", "", venue),
                        "home_score": int(score[0]),
                        "away_score": int(score[1]),
                        "match_link": f"https://www.premierleague.com/match/{match_id}",
                    }
                )

        if return_result:
            return results

        OUT_FILE = DATA_DIR / f"transform/premierleague.com/results/{season_file_name.replace('html', 'json')}"
        with open(OUT_FILE, "w+") as fp:
            json.dump(results, fp, indent=2)
        
        print(f"Processed season {season} to {OUT_FILE}")

    def process_all_results(self):
        """
        Process all the results for all seasons
        """
        RAW_DIR = DATA_DIR / "extract/premierleague.com/results/*.html"
        results = []
        for html_file in glob.glob(str(RAW_DIR)):
            m = re.search(r"(\d+_\d+)\.html$", html_file)
            if m:
                season = m.group(1).replace("_", "/")
                if out := self.process_season_results(season, return_result=True):
                    results = results + out

        OUT_FILE = DATA_DIR / "transform/premierleague.com/results/all.json"
        with open(OUT_FILE, "w+") as fp:
            json.dump(results, fp, indent=2)

        print(f"Written {len(results)} to {OUT_FILE}")

if __name__ == "__main__":
    fire.Fire(EPLCommands)
