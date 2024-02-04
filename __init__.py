"""Fichier pour gérer la logique des decks."""

"""Gestion de la logique des tournois."""
import glob
import json
import os
import re
from threading import Lock, Thread
from typing import List

import requests
from bs4 import BeautifulSoup

from mtgdc_carddata import CardDatabase

DATABASE = CardDatabase()

HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "3600",
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0)"
        + "Gecko/20100101 Firefox/52.0"
    ),
}


class Deck:
    """Classe pour représenter l'objet Deck."""

    def __init__(self, deck_id: str) -> None:
        # C'est un appel "à blanc" du deck car j'ai observé que
        # si la page de deck n'était pas visitée au préalable,
        # l'exportation de la decklist ne fonctionnait pas correctement
        self.soup = Soupe(f"https://mtgtop8.com/event?e=1&d={deck_id}").soup

        self.deck_id = deck_id
        self.link = f"https://mtgtop8.com/mtgo?d={deck_id}"
        self.soup = Soupe(self.link).soup

        self._mainboard = None
        self._sideboard = None

        self._rank = None
        self._player = None

    def to_dict(self) -> dict:
        """Conversion de l'objet en dictionnaire."""
        return {
            "deck_id": self.deck_id,
            "rank": self.rank,
            "player": self.player,
            "commander": self.commander,
            "decklist": self.mainboard,
        }

    @property
    def decklist(self) -> str:
        """Propriété retournant la decklist."""
        return self.soup.prettify()

    @property
    def commander(self) -> List:
        """Propriété qui retourne le sideboard."""
        if self._sideboard is None:
            if "Sideboard" not in self.decklist:
                self._sideboard = ["Unknown Card"]
            else:
                self._sideboard = [
                    line[2:].strip()
                    for line in re.split("Sideboard", self.decklist)[1].split("\n")
                    if len(line[2:].strip()) > 0
                ]

            # Remove leftover html encoding
            for idx, carte in enumerate(self._sideboard):
                if re.search("&amp;", carte):
                    parts = re.split(" &amp; ", carte)
                    self._sideboard[idx] = " & ".join(parts)

        return self._sideboard

    @property
    def mainboard(self) -> List:
        """Propriété qui retourne le mainboard."""
        if self._mainboard is None:
            if "Sideboard" not in self.decklist:
                self._mainboard = [
                    line.strip() for line in self.decklist.split("\n") if line.strip()
                ]
            else:
                self._mainboard = [
                    line.strip()
                    for line in re.split("Sideboard", self.decklist)[0].split("\n")
                    if line.strip()
                ]

            # Clean card names in case of encoding errors
            lines = []
            for line in self._mainboard:
                tmp = line.split(" ", maxsplit=1)
                tmp[1] = DATABASE.card(tmp[1])["name"]
                lines.append(" ".join(tmp))

            self._mainboard = lines

        return self._mainboard

    @property
    def rank(self) -> str:
        """Propriété pour gérer le rang du deck dans le tournoi."""
        return self._rank

    @rank.setter
    def rank(self, value: str) -> None:
        """Setter pour le rang du deck."""
        self._rank = value

    @property
    def player(self) -> str:
        """Propriété pour gérer le joueur du deck."""
        return self._player

    @player.setter
    def player(self, value: str) -> None:
        """Setter pour le joueur du deck."""
        self._player = value


class Soupe:
    """Classe qui contient les informations pour le scrapping."""

    def __init__(self, link: str) -> None:
        self.link = link
        self.soup = self.get_soup()

    @property
    def encoding(self) -> str:
        """Propriété contenant l'encoding de mtgtop8."""
        return "iso-8859-1"

    def get_soup(self) -> BeautifulSoup:
        """Fonction qui récupère la page demandée."""
        req = requests.get(self.link, HEADERS, stream=True, timeout=5000)
        req.encoding = self.encoding
        return BeautifulSoup(req.content, "html.parser", from_encoding=self.encoding)


class Tournoi:
    """Classe pour stocker les informations du tournoi."""

    def __init__(self, soup: Soupe) -> None:
        self.soup = soup.soup
        self.tournoi_id = soup.link.split("=")[1]
        self._is_commander = None
        self._name = ""
        self._place = ""
        self._players = ""
        self._date = ""

    def to_dict(self) -> dict:
        """Fonction qui permet d'exporter l'objet Tournoi en dictionnaire."""
        return {
            "format": "Duel Commander",
            "id": self.tournoi_id,
            "name": self.name,
            "place": self.place,
            "players": self.players,
            "date": self.date,
            "decks": self.get_decks(),
        }

    @property
    def is_commander(self) -> bool:
        """Propriété qui vérifie que la soupe contient un tournoi en Duel Commander."""
        if self._is_commander is None:
            tag = self.soup.find("div", class_="meta_arch")
            self._is_commander = tag is not None and "Duel Commander" in tag.text
        return self._is_commander

    @property
    def name(self) -> str:
        """Propriété qui retourne le nom de l'événement."""
        if self._name == "":
            self._set_name_place()
        return self._name

    @property
    def place(self) -> str:
        """Propriété qui retour le lieu de l'événement."""
        # Le lieu n'est pas toujours indiqué mais le nom l'est toujours
        if self._name == "":
            self._set_name_place()
        return self._place

    @property
    def players(self) -> str:
        """Propriété qui retourne le nombre de joueurs."""
        if self._players == "":
            self._set_players_date()
        return self._players

    @property
    def date(self) -> str:
        """Propriété qui retourne la date de l'événement."""
        if self._date == "":
            self._set_players_date()
        return self._date

    def _set_name_place(self) -> None:
        """Fonction qui récupère le nom et le lieu depuis la soupe."""
        tag = self.soup.find("div", class_="event_title")
        if tag is not None:
            if "@" not in tag.text:
                self._name = tag.text
            else:
                (name, place) = re.split("@", tag.text, maxsplit=1)
                self._name = name.strip()
                self._place = place.strip()

    def _set_players_date(self) -> None:
        """fonction nqui récupère le nombre de joueurs et la date depuis la soupe."""
        div_meta_arch = self.soup.find("div", class_="meta_arch")
        self._players = "0 players"
        self._date = "05/08/93"
        if div_meta_arch:
            tags = div_meta_arch.parent.find_all("div")
            for tag in tags:
                line = "".join(tag.text)
                if re.match(r"[0-9][0-9]/[0-9][0-9]", line) and "-" not in line:
                    self._date = line
                elif "players" in line and "-" not in line:
                    self._players = line
                elif "players" in line and "-" in line:
                    (players, date) = re.split("-", line)
                    self._players = players.strip()
                    self._date = date.strip()

    def get_decks(self) -> List[Deck]:
        """Fonction qui retourne la liste des decks de la page."""
        top8_decks = [
            (tag, "top8") for tag in self.soup.select("div.S14 a[href^='?e=']")
        ]
        out_decks = [(tag, "out") for tag in self.soup.select("optgroup option")]
        deck_to_crawl = top8_decks + out_decks

        # Stockage des decks
        response = []
        deck_ids = []  # Cas de nesting de balise dans certains tournois

        def get_deck_info(deck, option, lock):
            """Procédure appelée lors du threading."""
            if option == "top8":
                rdeck = Deck(re.split("=", deck["href"])[2][:-2])
                block = deck.parent.parent.parent
                rdeck.player = block.find("a", attrs={"class": "player"}).string.strip()
                for div in block.find_all("div"):
                    if div.string is not None:
                        if re.match(r"\d(?:-\d)?", div.string):
                            rdeck.rank = div.string

            if option == "out" and deck["value"] not in deck_ids:
                rdeck = Deck(deck["value"])
                rdeck.player = re.split(" - ", deck.contents[0], maxsplit=1)[1].strip()
                rdeck.rank = re.split("#", deck.parent["label"], maxsplit=1)[1]

            with lock:
                deck_ids.append(rdeck.deck_id)
                response.append(rdeck.to_dict())

        threads = [
            Thread(
                target=get_deck_info,
                args=(item[0], item[1], Lock()),
            )
            for item in deck_to_crawl
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        response = [item for item in response if item is not None]
        response = sorted(response, key=lambda i: int(i["deck_id"]))

        return response


def get_first_id(path: str) -> str:
    """Fonction qui retour le premier id à exporter."""
    files = glob.glob(os.path.join(path, "*.json"))
    id_tournoi = 2694  # Premier tournoi DC sur mtgtop8 : 2695
    if len(files) > 0:
        id_tournoi = max(
            int(os.path.splitext(os.path.basename(file))[0]) for file in files
        )
    return id_tournoi


def extraction() -> None:
    """Fonctionn principale."""

    path = "mtgdc_decklists/decklists"
    first_id = get_first_id(path)

    def extract_tournoi(event_id: str) -> None:
        print("Tournoi", event_id)
        tournoi = Tournoi(Soupe(f"https://mtgtop8.com/event?e={event_id}"))

        if tournoi.is_commander:
            tournoi_data = tournoi.to_dict()
            with open(
                os.path.join(path, f"{event_id}.json"), "+w", encoding="utf-8"
            ) as json_file:
                json.dump(tournoi_data, json_file, ensure_ascii=False, indent=4)

    # A chaque fois, 1000 extractions par groupe de 10
    threads = []
    for i in range(100):
        threads = [
            Thread(
                target=extract_tournoi,
                args=(first_id + 10 * i + j + 1,),
            )
            for j in range(10)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
