# mtgdc_scrapper
Module that scraps MTGTOP8 to retreive MTGDC tournaments. Thoses files are stored in `mtgdc_decklists` folder.

## How does it work?
The process is to request every pages in [MTGTOP8](https://mtgtop8.com/index) using the `event` endpoint:
`https://mtgtop8.com/event?e=<id_tournoi>`.

Using `BeautifulSoup`, the source code is read:
1. Check if there is a `404` message;
1. Check if the event's format is `Duel Commander`;
1. Walk through every deck in the event page and DL the decklists.

## How are data stored?
The script produces a `JSON` file named after the `<id_tournoi>` requested to the endpoint. It stores generic data
and every decklists as well as players' names and finish positions.

## Limitation of the source
MTGTOP8 is a website that stores tournaments on every MTG format. This works through a declarative statements
made by any user to have their tournament displayed. This is maintained outside of any `Barrin's Codex` projects.
The data can't be used to determine actual tier list or any other data calculated
on the mass of tournaments as they are not proofed by any system.
