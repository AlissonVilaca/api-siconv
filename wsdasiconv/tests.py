#!/usr/bin/python
# -*- coding: utf-8 -*-

from unittest import TestCase
from model import Session, engine
from model import Fornecedor, FornecedorPF, FornecedorPJ

def popula():
    session = Session()
    session.add_all( # TODO: fazer construtores
        FornecedorPJ(cpf="00000000000134", nome="Banco do Brasil S/A"), 
        FornecedorPF(cpf="00000000000", nome="Fulano de tal"),
    )

class TesteFornecedorPorCNPJ(TestCase):
    def setUp(self):
        popula()

class TesteFornecedorPorCPF(TestCase):
    def setUp(self):
        popula()

class TesteFornecedorPorUF(TestCase):
    def setUp(self):
        popula()
