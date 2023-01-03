import glob
import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.resolve().parent.resolve() / "data"


def get_fixtures_for_season(file: str):
    with open(file) as fp:
        soup = BeautifulSoup(fp.read(), "html.parser")

    fixtures = []

    for div in soup.select("div[data-competition-matches-list]"):
        fixture_date = div.get("data-competition-matches-list")
        assert isinstance(fixture_date, str)

        for fixture in div.select(".matchList li"):
            home_team = fixture.get("data-home")
            away_team = fixture.get("data-away")
            venue = fixture.get("data-venue")
            score = fixture.select_one(".overview .teams .score").text.split("-")
            team_names = fixture.select(".overview .teams .teamName")
            match_id = fixture.select_one("[data-matchid]").get("data-matchid")
            match_ko = fixture.get("data-comp-match-item-ko")
            fixtures.append(
                {
                    "match_id": int(match_id),
                    "match_ko": int(match_ko),
                    "date": fixture_date,
                    "home_team": home_team,
                    "home_team_abbr": team_names[0].select_one(".abbr").text,
                    "away_team": away_team,
                    "away_team_abbr": team_names[1].select_one(".abbr").text,
                    "venue": re.sub("<[^<]+?>", "", venue),
                    "home_score": int(score[0]),
                    "away_score": int(score[1]),
                    "match_link": f"https://www.premierleague.com/match/{match_id}",
                }
            )

    return fixtures


def process_premier_league_season_results():
    fixtures = []
    for file in glob.glob(str(DATA_DIR / "premier-league-results-raw") + "/*.html"):
        fixtures = fixtures + get_fixtures_for_season(file)

    df = pd.DataFrame(fixtures)
    verify_results_and_match_id(df)
    df.to_json(DATA_DIR / "premier_league_results_92_23.json", indent=2)


def verify_results_and_match_id(df: pd.DataFrame):
    """
    Verify that the match it is part of the URL to get the match data
    """
    for i in df[["match_id", "match_link"]].index:
        match_id = str(df["match_id"][i])
        match_link = str(df["match_link"][i])[-len(match_id) :]
        assert match_id == match_link


def download_match_results(df: pd.DataFrame):
    headers = {
        "Accept": "text.html",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    }

    skipped = 0
    downloaded = 0

    for i in df[["match_id", "match_link"]].index:
        match_id = str(df["match_id"][i])
        output_file = DATA_DIR / f"premier-league-results-raw/matches/{match_id}.html"
        if output_file.is_file():
            skipped += 1
            print(f"skipping {match_id}")
            continue

        r = requests.get(str(df["match_link"][i]), headers=headers)
        downloaded += 1

        with open(str(output_file), "w") as fp:
            fp.write(r.text)
            print(f"Written {match_id}")

    print(f"skipped={skipped}, downloaded={downloaded}")


def parse_match_result_data(match_id: int):
    html_file = DATA_DIR / f"premier-league-results-raw/matches/{match_id}.html"
    if not html_file.is_file():
        print(f"match {match_id} not found. missing file={html_file}")
        sys.exit(1)

    with open(str(html_file)) as fp:
        soup = BeautifulSoup(fp.read(), "html.parser")

    # get the half time score
    node = soup.select_one(".matchStats .halfTime")
    assert node
    text = node.get_text().strip()
    m = re.search(r"(\d+\-\d+)", text)
    assert m
    half_time_score_home = int(m.group(1).split("-")[0])
    half_time_score_away = int(m.group(1).split("-")[1])

    # attendance
    node = soup.select_one(".attendance")
    assert node
    text = node.get_text().strip()
    m = re.search(r"([\d,]+)", text)
    assert m
    attendance = int(m.group(1).replace(",", ""))

    # referee
    node = soup.select_one(".matchInfo .referee")
    assert node
    referee = node.get_text().strip()

    # stadium
    node = soup.select_one(".matchInfo .stadium")
    assert node
    stadium = node.get_text().strip()

    # home events
    events = {"home": [], "away": []}
    for event in soup.select(".matchEvents .home .event"):
        if "goal" in str(event.get_text()).lower():
            text = event.get_text().replace("Goal", "").strip()
            m = re.search(r"^([^\d]+)([0-9]+)", text)
            assert m
            player = m.group(1).strip()
            time = int(m.group(2).replace("'", ""))
            events["home"].append({"type": "goal", "player": player, "time": time})

    # away events
    for event in soup.select(".matchEvents .away .event"):
        if "goal" in str(event.get_text()).lower():
            text = event.get_text().replace("Goal", "").strip()
            m = re.search(r"^([^\d]+)([0-9]+)", text)
            assert m
            player = m.group(1).strip()
            time = int(m.group(2).replace("'", ""))
            events["away"].append({"type": "goal", "player": player, "time": time})

    # home assists
    for assist in soup.select(".assists .home .event"):
        text = assist.get_text().strip()
        m = re.search(r"^([^\d]+)([0-9]+)", text)
        assert m
        player = m.group(1).strip()
        time = int(m.group(2).replace("'", ""))
        events["home"].append({"type": "assist", "player": player, "time": time})

    # away assists
    for assist in soup.select(".assists .away .event"):
        text = assist.get_text().strip()
        m = re.search(r"^([^\d]+)([0-9]+)", text)
        assert m
        player = m.group(1).strip()
        time = int(m.group(2).replace("'", ""))
        events["away"].append({"type": "assist", "player": player, "time": time})

    result = {
        "match_id": match_id,
        "stadium": stadium,
        "half_time_score_home": half_time_score_home,
        "half_time_score_away": half_time_score_away,
        "attendance": attendance,
        "events": events,
        "referee": referee,
    }
    print(json.dumps(result, indent=2))


def main():
    # process_premier_league_season_results()
    df = pd.read_json(DATA_DIR / "premier_league_results_92_23.json")
    parse_match_result_data(428)
    parse_match_result_data(426)
    # df["match_ko"] = pd.to_datetime(df["match_ko"], unit="ms")
    # df.to_json(DATA_DIR / "premier_league_results_92_23.json", indent=2)
    # print(df.head())


if __name__ == "__main__":
    main()
