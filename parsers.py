import itertools
import os
import re
import ssl
from random import randint
from time import sleep
from urllib.request import urlopen

import bs4
from bs4 import BeautifulSoup

ssl._create_default_https_context = ssl._create_unverified_context
unverified_context = ssl._create_unverified_context()


os.environ["no_proxy"] = "*"


def get_page(url: str, context: ssl.SSLContext) -> BeautifulSoup:
    sleep(randint(1, 3))
    page = urlopen(url, context=context)
    html = page.read().decode("utf-8")
    return BeautifulSoup(html, "html.parser")


def get_page_data(soup: BeautifulSoup, name: str, attrs: dict) -> list:
    page_data = soup.find_all(name, attrs)
    return page_data


def format_country_sex_age_data(
    country_sex_age: str, split_string: str = ", "
) -> tuple[str, str, int]:
    country, sex_age = country_sex_age.split(split_string)
    return country, sex_age[0], int(sex_age[1:])


def parse_participant_card(participant_card: bs4.element.Tag) -> dict:
    participant_card = list(itertools.chain.from_iterable(participant_card))
    participant_data = dict()
    for item in participant_card:
        if item == "\n":
            continue
        elif isinstance(item, bs4.element.Tag):
            if item["class"][0] == "results-table__values-item-place":
                try:
                    participant_data["place"] = int(item.contents[0])
                except ValueError:
                    participant_data["place"] = item.contents[0].strip()
            elif item["class"][0] == "results-table__values-item-name":
                participant_data["name"] = item.contents[0].replace("\xa0", " ")
            elif item["class"][0] == "results-table__values-item-country":
                (
                    participant_data["country"],
                    participant_data["sex"],
                    participant_data["age"],
                ) = format_country_sex_age_data(item.contents[0].replace("\xa0", " "))
        else:
            if re.match(r"^[\d]{4}$", item):
                participant_data["number"] = int(item)
            elif re.match(r"^[\d]{1}:[\d]{2}$", item) or item == "-":
                participant_data["pace"] = item
            elif re.match(r"^[\d]{1}:[\d]{2}:[\d]{2}$", item) or isinstance(item, str):
                participant_data["total_time"] = item
    return participant_data


def get_participants_from_page(url: str, context: ssl.SSLContext) -> list:
    page_data: BeautifulSoup = get_page(url, context)
    page_data: list = get_page_data(
        page_data, name="a", attrs={"class": "results-table__values"}
    )
    participants_data = []
    for card in page_data:
        participants_data.append(parse_participant_card(card))
    return participants_data


def get_total_participants(url: str, context: ssl.SSLContext) -> int:
    soup: BeautifulSoup = get_page(url, context)
    total_participants = soup.find_all("span", {"class": "results-top__heading-count"})
    try:
        total_participants = int(
            re.findall(r"[\d]+", total_participants[0].contents[0])[0]
        )
    except Exception as ex:
        raise Exception(f"Error: {repr(ex)} on '{url}'")
    return total_participants


def get_race_data(url: str, context: ssl.SSLContext) -> list[dict]:
    total_participants: int = get_total_participants(url, context)
    race_data = []
    page = 1
    while len(race_data) <= total_participants:
        race_data += get_participants_from_page(
            f"{url}page/{page}/page_size/1000/", context
        )
        page += 1
    return race_data


def get_events(url: str, context: ssl.SSLContext) -> list:
    page = get_page(url, context)
    events = page.find_all(name="a", attrs={"class": "results-races__item"}, href=True)
    events_data = dict()
    for event in events:
        name_date = " | ".join(
            [
                event.find_all(
                    name="div", attrs={"class": "results-races__item-info-name"}
                )[0].contents[0],
                event.find_all(
                    name="div", attrs={"class": "results-races__item-info-date"}
                )[0].contents[0],
            ]
        )
        events_data[name_date] = {"link": getattr(event, "attrs")["href"]}
    return events_data


def get_races(url: str, context: ssl.SSLContext):
    page = get_page(url, context)
    races = page.find_all("a", {"class": "results-distances-nav__link"})
    if len(races) == 0:
        races = page.find_all("a", {"class": "results-top-nav__link active"})
    races_data = dict()
    for race in races:
        races_data[race.contents[0]] = {"link": race["href"], "data": dict()}
    return races_data


def get_event_data(races: dict, context: ssl.SSLContext) -> list[dict]:
    for race in races:
        race_link = races[race]["link"]
        if "leaderboard" in race_link:
            race_link = race_link.replace("leaderboard", "finishers")
        elif "overview" in race_link:
            race_link = race_link.replace("overview", "finishers")
        try:
            race_data = get_race_data(race_link, context)
        except Exception as e:
            race_data = str(e)
        races[race]["data"] = race_data
    return races


def get_all_events_data(url: str, context: ssl.SSLContext) -> dict:
    events = get_events(url, context)

    for event in events:
        events[event]["races"] = get_races(events[event]["link"], context)
        events[event]["races"] = get_event_data(events[event]["races"], context)

    return events


# To get data:
# >> get_all_events_data("https://results.runc.run/races/", unverified_context)
