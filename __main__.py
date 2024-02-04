"""
Module pour l'extraction de MTGTOP8 en vue de stocker
et d'analyser les données dans l'objectif de définir
une vue plus précise des archétypes joués avec
`mtgdc-parser` et d'autres outils à venir comme
`mtgdc-aggregator` ou `mtgdc-database`.
"""

from mtgdc_scrapper import extraction

if __name__ == "__main__":
    extraction()
