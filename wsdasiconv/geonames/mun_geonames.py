#!/usr/bin/python
# -*- coding:utf-8 -*-
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from geoalchemy import WKTSpatialElement#, DBSpatialElement
from nltk.metrics.distance import edit_distance
from curses.ascii import isascii
from unicodedata import normalize

import sys
sys.path.append("..")
from model import Municipio
from geonames_model import Feature
from geonames_model import Session as GNSession

desacentua = lambda t: filter(isascii, normalize('NFD', t).encode('utf-8'))

def compara_base(inicial=0, skip=False):
    db_string = "postgresql+psycopg2://postgre:postgre@10.209.53.95:2345/sicaf"

    Session = scoped_session(sessionmaker())
    engine = create_engine(db_string)
    session = Session(bind=engine)
    gnsession = GNSession()

    raio = 1.0

    for mun in session.query(Municipio).filter_by(geonameId=None):
        print "== %s, %s ==" % (mun.nome, mun.uf.upper())
        if mun._geo_ponto is None:
            print "* Sem informações de coordenadas geográficas"
            continue
        p = WKTSpatialElement(session.scalar(mun._geo_ponto.wkt))
        gnf = gnsession.query(Feature).filter_by(feature_code="PPL").filter(Feature.position.distance(p) < raio)
        dist = lambda f: edit_distance(desacentua(mun.nome.lower()), desacentua(f.name.lower()))
        candidatos = [t[1] for t in sorted(((dist(f), f) for f in gnf if dist(f)<3))]
        if len(candidatos) == 1:
            c = candidatos[0]
            print "* '%s', %s (IBGE: %d) considerado equivalente a '%s', %s (GeoNameId: %s)" % (mun.nome, mun.uf, mun.cod_ibge, c.name, c.uf, c.geonameid)
            print
            mun.geonameId = int(c.geonameid)
            session.commit()
        elif len(candidatos) > 1:
            if skip:
                print "* Mais de um resultado encontrado - modo não supervisionado ativo."
                continue
            print "Selecione o item mais apropriado a '%s', %s (IBGE: %d) [1]" % (mun.nome, mun.uf, mun.cod_ibge)
            for n, c in enumerate(candidatos, start=1):
                print "%d) '%s', %s - http://sws.geonames.org/%s/" % (n, c.name, c.uf, c.geonameid)
            resp = raw_input("Escolha: ")
            if not resp:
                resp = "1"
            c = candidatos[int(resp) - 1]
            print "* '%s', %s (IBGE: %d) considerado equivalente a '%s', %s (GeoNameId: %s)" % (mun.nome, mun.uf, mun.cod_ibge, c.name, c.uf, c.geonameid)
            print
            mun.geonameId = int(c.geonameid)
            session.commit()
        else:
            print "* Nenhuma feature geografica proxima encontrada no geonames"

if __name__ == "__main__":
    from getopt import getopt
    from sys import argv
    optlist, args = getopt(argv[1:], 'u')
    opcoes = dict(optlist)
    if '-u' in opcoes.keys():
        skip = True
    else:
        skip = False
    if len(args) > 0:
        inicial = int(args[0])
    else:
        inicial = 0
    compara_base(skip=skip)
