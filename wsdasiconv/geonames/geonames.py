#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from nltk.metrics.distance import edit_distance
db_string = "postgresql+psycopg2://postgre:postgre@10.209.53.95:2345/sicaf"

from model import Municipio

Session = scoped_session(sessionmaker())
engine = create_engine(db_string)
session = Session(bind=engine)

def geonames_reverse(lat, lon, raio=10.0):
    url = "http://api.geonames.org/findNearbyPlaceNameJSON?lat=%f&lng=%f&radius=%f&username=demo" % (lat, lon, raio)
    con = urllib2.urlopen(url)
    dados = json.load(con)
    con.close()
    if dados[u'geonames']:
        return dados[u'geonames']
    else:
        return {}

def get_geonames_code(m):
    lat = session.scalar(m._geo_ponto.y)
    lon = session.scalar(m._geo_ponto.x)
    places = geonames_reverse(lat, lon)
    for place in places:
        nome1 = m.nome.strip().lower()
        nome2 = place[u'name'].strip().lower()
        if edit_distance(nome1, nome2) < 2:
            return int(place[u'geonameId'])
# http://sws.geonames.org/{geonamesId}/

if __name__ == "__main__":
    lat, lon = argv[1], argv[2]
    print geonames_reverse(lat, lon)