# -*- coding: utf-8 -*-

from rdflib.namespace import Namespace

# configuracao
URI_BASE = 'http://api.convenios.gov.br/siconv/'
base = URI_BASE
if base[-1] != '/' and base[-1] != '#':
    base += '/'

# ontologias de governo
LIC = Namespace('http://vocab.e.gov.br/licitacoes#')
SIORG = Namespace('http://vocab.e.gov.br/siorg#')
SIAFI = Namespace('http://vocab.e.gov.br/siafi#')

# namespaces externos
GEO = Namespace('http://www.w3.org/2003/01/geo/wgs84_pos#')
DBPEDIA = Namespace('http://dbpedia.org/resource/')
DBPROP = Namespace('http://dbpedia.org/property/')
DBONT = Namespace('http://dbpedia.org/ontology/')
VOID = Namespace('http://rdfs.org/ns/void#')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')

# mapeamentos da DBPedia
dbpedia_estados = {
    "AP":DBPEDIA["Amap%C3%A1"],
    "CE":DBPEDIA["Cear%C3%A1"],
    "TO":DBPEDIA["Tocantins"],
    "GO":DBPEDIA["Goi%C3%A1s"],
    "MS":DBPEDIA["Mato_Grosso_do_Sul"],
    "MG":DBPEDIA["Minas_Gerais"],
    "PE":DBPEDIA["Pernambuco"],
    "PI":DBPEDIA["Piau%C3%AD"],
    "PA":DBPEDIA["Par%C3%A1"],
    "BA":DBPEDIA["Bahia"],
    "AL":DBPEDIA["Alagoas"],
    "ES":DBPEDIA["Esp%C3%ADrito_Santo"],
    "DF":DBPEDIA["Brazilian_Federal_District"],
    "MT":DBPEDIA["Mato_Grosso"],
    "RN":DBPEDIA["Rio_Grande_do_Norte"],
    "RO":DBPEDIA["Rond%C3%B4nia"],
    "SE":DBPEDIA["Sergipe"],
    "RS":DBPEDIA["Rio_Grande_do_Sul"],
    "RR":DBPEDIA["Roraima"],
    "MA":DBPEDIA["Maranh%C3%A3o"],
    "PB":DBPEDIA["Para%C3%ADba"],
    "AC":DBPEDIA["Acre_(state)"],
    "SC":DBPEDIA["Santa_Catarina_(state)"],
    "AM":DBPEDIA["Amazonas_(Brazilian_state)"],
    "RJ":DBPEDIA["Rio_de_Janeiro_(state)"],
    "PR":DBPEDIA["Paran%C3%A1_(state)"],
    "SP":DBPEDIA["S%C3%A3o_Paulo_(state)"],
}
