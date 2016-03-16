#!/usr/bin/python
# -*- coding: utf-8 -*-

import psycopg2
from sys import argv


def carga(nome_arq):
    print "Estabelecendo conexao com o host..."
    conn = psycopg2.connect("dbname=SICAF_dump user=postgres password=postgres host=127.0.0.1")
    cur = conn.cursor()
    print "Abrindo arquivo '%s'..." % nome_arq
    with open(nome_arq) as f:
        comando = ""
        for l in f:
            l = l.strip()
            if l and not l.startswith("--") and not l.startswith("CREATE PROCEDURAL LANGUAGE"):
                comando += l
                if ";" in comando:
                    print comando
                    cur.execute(l)
                    comando = ""
        conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    nome_arq = argv[1]
    carga(nome_arq)
