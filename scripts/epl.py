import glob
import json
import re
from pathlib import Path

import fire
import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.resolve().parent.resolve() / "data"


_headers = {
    "Accept": "text/html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/108.0.0.0 Safari/537.36"
    ),
}


class EPLCommands:
    def download_match(self, match_id: int, force=False, skip_on_cached=True):
        """
        Download the HTML page for the match from premierleague.com
        """
        destination_file = (
            DATA_DIR / f"extract/premierleague.com/matches/{match_id}.html"
        )
        if not force and skip_on_cached and destination_file.is_file():
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

                home_score = int(score[0])
                away_score = int(score[1])

                is_draw = home_score == away_score
                is_home_win = home_score > away_score
                is_away_win = home_score < away_score
                winner = -1

                if is_draw:
                    home_points = 1
                    away_points = 1
                elif is_home_win:
                    home_points = 3
                    away_points = 0
                    winner = 0
                elif is_away_win:
                    home_points = 0
                    away_points = 3
                    winner = 1
                else:
                    raise Exception("unable to determine the result")

                results.append(
                    {
                        "season": season,
                        "match_id": int(match_id),
                        "match_ko": int(match_ko),
                        "date": fixture_date,
                        "home_team": home_team,
                        "home_team_abbr": home_team_abbr.text,
                        "home_team_points": home_points,
                        "away_team": away_team,
                        "away_team_abbr": away_team_abbr.text,
                        "away_team_points": away_points,
                        "venue": re.sub(r"<[^<]+?>", "", venue),
                        "home_score": int(score[0]),
                        "away_score": int(score[1]),
                        "match_link": f"https://www.premierleague.com/match/{match_id}",
                        "winner": winner,
                    }
                )

        if return_result:
            return results

        OUT_FILE = (
            DATA_DIR
            / f"transform/premierleague.com/results/{season_file_name.replace('html', 'json')}"
        )
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

        self.validate_processed_match_results()

        print(f"Written {len(results)} to {OUT_FILE}")

    def validate_processed_match_results(self):
        """
        This will run some validation against the produced results in all.json
        """
        df = pd.read_json(DATA_DIR / "transform/premierleague.com/results/all.json")

        # check match link goes to the correct match (verified by match_id)
        for i in df[["match_id", "match_link"]].index:
            match_id = str(df["match_id"][i])
            match_link = str(df["match_link"][i])[-len(match_id) :]
            assert match_id == match_link

    def product_match_links_dataset(self):
        df = pd.read_json(DATA_DIR / "transform/premierleague.com/results/all.json")
        subset = df[["match_id", "match_link"]]

        OUTFILE = DATA_DIR / "transform/premierleague.com/matches/match_links.json"
        subset.to_json(OUTFILE)

        print(f"Written match links to {OUTFILE}")

    def download_all_matches(self):
        """
        Download the raw html page for the match. This expects the match_links.json to be
        present in the data directory.
        """
        df = pd.read_json(
            DATA_DIR / "transform/premierleague.com/matches/match_links.json"
        )

        skipped = 0
        downloaded = 0
        total = len(df.index)

        print(f"starting download. total records {total}")

        for i in df.index:
            match_id = df["match_id"][i]
            self.download_match(match_id, skip_on_cached=False)  # type: ignore
            downloaded += 1

        print(f"FINISHED: downloaded={downloaded}, skipped={skipped}, total={total}")


if __name__ == "__main__":
    fire.Fire(EPLCommands)
