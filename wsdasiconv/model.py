# -*- coding: utf-8 -*-
"""
Módulo model.py da API de dados abertos do SICONV.
=======================================================

© 2011-2013 Ministério do Planejamento, Orçamento e Gestão

Este arquivo e parte do webservice de dados abertos do SICONV,
o Sistema de Cadastro de Convênios e Contratos de Repasse.

A documentacao esta disponível em http://api.convenios.gov.br/siconv/doc/

O webservice de dados abertos do SICONV é um software livre; você pode
redistribui-lo e/ou modifica-lo dentro dos termos da Licença Pública Geral
Affero GNU como publicada pela Fundação do Software Livre (FSF); na versão 3
da Licença, ou (na sua opnião) qualquer versão subsequente.

Este programa é distribuido na esperança que possa ser  util, 
mas SEM NENHUMA GARANTIA; sem uma garantia implicita de ADEQUAÇÂO a qualquer
MERCADO ou APLICAÇÃO EM PARTICULAR. Veja a
Licença Pública Geral Affero GNU para maiores detalhes.

http://www.gnu.org/licenses/agpl-3.0.html
"""

from datetime import date as _date, datetime as _datetime

from serializer import ExposedObject

# sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base, synonym_for
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import MetaData, ForeignKey, ForeignKeyConstraint, or_
from sqlalchemy import Table, Column, Integer, BigInteger, SmallInteger
from sqlalchemy import Numeric, Date, Unicode, Boolean
from geoalchemy import GeometryDDL, GeometryColumn, Point
from geoalchemy.postgis import PGComparator
from shapely import wkb

from __init__ import versao_api

from namespace import URI_BASE, DBPEDIA, DBONT, DBPROP, dbpedia_estados, FOAF
from namespace import VCARD
from amara.writers.struct import E

from rdflib import URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL

# sessao
Session = scoped_session(sessionmaker())

# modelo
Base = declarative_base(cls=ExposedObject)

def limita_tamanho(s, tamanho):
    s = unicode(s)
    return s if (len(s) < tamanho) else s[:(tamanho - 5)].rsplit(u" ", 1)[0] + u" ..."

def date(date_str):
    return _date.fromtimestamp(_datetime.strptime(date_str, "%Y-%m-%d"))

class Municipio(Base):
    u"""Representa um município.
    """
    __tablename__ = "municipio"
    __slug_item__ = "municipio"
    __slug_lista__ = "municipios"
    __class_uri__ = "http://dbpedia.org/ontology/Settlement"
    __rdf_prop__ = {
        'uf': lambda self: ((URIRef(self.uri), DBONT['state'], \
            URIRef(dbpedia_estados[self.uf])),
            (dbpedia_estados[str(self.uf)], DBONT['abbreviation'], \
            Literal(self.uf)), \
            (dbpedia_estados[str(self.uf)], DBPROP['isocode'], \
            Literal(u"BR-" + self.uf)),) \
            if (self.uf and dbpedia_estados.get(str(self.uf), None)) \
            else None,
        'uf_nome': lambda self: ((dbpedia_estados[str(self.uf)], \
            RDFS['label'], Literal(self.uf_nome, lang='pt-br')),) \
            if (self.uf and dbpedia_estados.get(str(self.uf), None)) \
            else None,
        'geonameId': lambda self: ((URIRef(self.uri), OWL['sameAs'], \
            URIRef("http://sws.geonames.org/%d/" % self.geonameId)),) \
            if self.geonameId \
            else None,
        'href_fornecedores': lambda self: ((URIRef(self.doc_uri),
            RDFS['seeAlso'], self.href_fornecedores),),
        'href_unidades_cadastradoras': lambda self: ((URIRef(self.doc_uri),
            RDFS['seeAlso'], self.href_unidades_cadastradoras),),
    }
    __expostos__ = set(["nome", "uf", "cod_siconv",
        'href_proponentes'])
    __resumidos__ = __expostos__
    id = Column(Integer, autoincrement=False, primary_key=True)
    nome = Column(Unicode(60))
    _uf = Column("uf", Unicode(2))
    uf_nome = Column(Unicode(60))
    _regiao = Column(Unicode(2))
    _regioes = {
        'N': u"Norte",
        'NE': u"Nordeste",
        'CO': u"Centro-Oeste",
        'SE': u"Sudeste",
        'S': u"Sul"
    }
    
    # relacionamentos:
    #
    # proponentes (Proponente.id)
    
    # atributos derivados
    @property
    def cod_siconv(self):
        return self.id
    @property
    def regiao(self):
        return self._regioes.get(self._regiao, self._regiao)
    @property
    def uf(self):
        uf = {
            'sigla': self._uf,
            'nome': self.uf_nome,
            }
        if self._regiao is not None:
            uf['regiao'] = {
                'sigla': self._regiao,
                'nome': self.regiao,
                }
        return uf
    @property
    def href_proponentes(self):
        """Retorna a URL de consulta a proponentes localizados neste Municipio."""
        return URIRef(URI_BASE + 'v%s/consulta/proponentes?id_municipio=%d' % (versao_api, self.id))

class UnidadeFederativa(Base):
    """Representa uma unidade federativa do Brasil.
    """
    # obs.: essa tabela foi criada para atender ao relacionamento com
    # Programa e aind nao foi integrada as demais classes
    __tablename__ = \
    __slug_item__ = \
    __slug_lista__ = "uf"
    __expostos__ = ['nome', 'sigla']
    __resumidos__ = ['nome', 'sigla']
    sigla = Column(Unicode(2), primary_key=True)
    nome = Column(Unicode(60))
    
    # relacionamentos
    # programas = relationship(Programa, secondary=uf_programa,
    #    backref=backref('estados_habilitado'))

uf_programa = Table('uf_programa', Base.metadata,
    Column('sigla_uf', Unicode(2), ForeignKey('uf.sigla')),
    Column('id_programa', Integer(), ForeignKey('programa.id')),
)

class EsferaAdministrativa(Base):
    """Representa uma esfera administrativa de governo.
    """
    __tablename__ = "esfera_administrativa"
    # __class_uri__ = ''
    __slug_item__ = "esfera_administrativa"
    __slug_lista__ = "esferas_administrativas"
    __expostos__ = ['nome', 'href_proponentes']
    __resumidos__ = __expostos__
    id = Column(Integer, autoincrement=False, primary_key=True)
    nome = Column(Unicode(60))
    
    # atributos derivados
    @property
    def href_proponentes(self):
        return URIRef(URI_BASE + 'v%s/consulta/proponentes?id_esfera_administrativa=%d' % (versao_api,self.id))

class NaturezaJuridica(Base):
    """Representa uma natureza juridica.
    """
    __tablename__ = "natureza_juridica"
    # __class_uri__ = ''
    __slug_item__ = "natureza_juridica"
    __slug_lista__ = "naturezas_juridicas"
    __expostos__ = ['nome', 'href_proponentes']
    __resumidos__ = __expostos__
    
    id = Column(Integer, autoincrement=False, primary_key=True)
    nome = Column(Unicode(60))
    
    # relacionamentos
    # programas = relationship(Programa, secondary=programa_atende_a,
    #    backref=backref('atende_a'))
    
    # atributos derivados
    @property
    def href_proponentes(self):
        return URIRef(URI_BASE + 'v%s/consulta/proponentes?id_natureza_juridica=%d' % (versao_api,self.id))

programa_atende_a = Table('programa_atende_a', Base.metadata,
    Column('id_programa', Integer(), ForeignKey('programa.id')),
    Column('id_natureza_juridica', Integer(), ForeignKey('natureza_juridica.id')),
)

class Proponente(Base):
    u"""Representa um proponente.
    """
    __tablename__ = "proponente"
    # __class_uri__ = ""
    __slug_item__ = "proponente"
    __slug_lista__ = "proponentes"
    __resumidos__ = [
        'cnpj',
        'nome', 'esfera_administrativa', 
        'municipio', 'endereco', 'cep', #'email', 
        'pessoa_responsavel',
        'nome_responsavel', 'cpf_responsavel', 'telefone', 'fax',
        'natureza_juridica',
        'inscricao_estadual', 'inscricao_municipal',
        'href_propostas', 'href_convenios', 'href_habilitacoes', 'href_empenhos',
    ]
    
    __expostos__ = __resumidos__ + [
        'telefone', 'fax',
        'inscricao_estadual', 'inscricao_municipal',
    ]
    
    id = Column(BigInteger, autoincrement=False, primary_key=True)
    nome = Column(Unicode(300))
    id_esfera_administrativa = Column(Integer, ForeignKey('esfera_administrativa.id'))
    id_municipio = Column(Integer, ForeignKey('municipio.id'))
    endereco = Column(Unicode(1024))
    cep = Column(Unicode(8))
    #email = Column(Unicode(1024))
    telefone = Column(Unicode())
    fax = Column(Unicode())
    nome_responsavel = Column(Unicode(70)) #catalogo padrao de dados
    id_responsavel = Column(Unicode(50), ForeignKey('pessoa_responsavel.id'))
    inscricao_estadual = Column(Unicode(200))
    inscricao_municipal = Column(Unicode(200))
    id_natureza_juridica = Column(Integer, ForeignKey('natureza_juridica.id'))
    
    # relacionamentos
    pessoa_responsavel = relationship('PessoaResponsavel', backref=backref('proponentes'))
    municipio = relationship(Municipio, backref=backref('proponentes'))
    natureza_juridica = relationship(NaturezaJuridica, backref=backref('proponentes'))
    esfera_administrativa = relationship(EsferaAdministrativa, backref=backref('proponentes'))
    # backrefs:
    # propostas_como_proponente = relationship(Proposta, backref=backref('proponente')
    # propostas_como_executor = relationship(Proposta, backref=backref('executor')
    
    # atributos derivados
    #@property
    #def natureza_juridica(self):
    #    return self._natureza_juridica.nome
    #@property
    #def esfera_administrativa(self):
    #    return self._esfera_administrativa.nome
    @property
    def cpf_responsavel(self):
        return self.pessoa_responsavel.cpf
    @property
    def propostas(self):
        return {
            'como_proponente': self.propostas_como_proponente,
            'como_executor': self.propostas_como_executor,
            }
    @property
    def href_propostas(self):
        """Retorna a URL de consulta a propostas desse Proponente."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_proponente=%d' % (versao_api,self.id))
    @property
    def href_convenios(self):
        """Retorna a URL de consulta a convenios por esse Proponente."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_proponente=%d' % (versao_api,self.id))
    @property
    def href_habilitacoes(self):
        """Retorna a URL de consulta a habilitaçõs para este Proponente."""
        return URIRef(URI_BASE + 'v%s/consulta/habilitacoes_area_atuacao?id_proponente=%d' % (versao_api,self.id))
    @property
    def href_empenhos(self):
        """Retorna a URL de consulta aos empenhos que favorecem este Proponente."""
        return URIRef(URI_BASE + 'v%s/consulta/empenhos?id_proponente_favorecido=%d' % (versao_api,self.id))
    @property
    def cnpj(self):
        """Retorna um atributo CNPJ do proponente (baseado no id)."""
        cnpj = u"%014d" % self.id
        return u"%s.%s.%s/%s-%s" % \
            (cnpj[:2], cnpj[2:5], cnpj[5:8], cnpj[8:12], cnpj[12:])

class SituacaoProposta(Base):
    """Representa uma possivel situacao de proposta.
    """
    __tablename__ = "situacao_proposta"
    # __class_uri__ = ""
    __slug_item__ = "situacao_proposta"
    __slug_lista__ = "situacoes_propostas"
    __expostos__ = [
        "nome", "href_propostas"
    ]
    __resumidos__ = __expostos__
    id = Column(Integer(), autoincrement=False, primary_key=True)
    nome = Column(Unicode(100))
    
    # relacionamentos
    # propostas = relationship(Proposta, backref=backref('situacao'))
    
    # atributos derivados
    @property
    def href_propostas(self):
        """Retorna a URL de consulta a propostas que estão nesta situação."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_situacao=%d' % (versao_api,self.id))

class SituacaoConvenio(Base):
    """Representa uma situacao de convenio.
    """
    __tablename__ = "situacao_convenio"
    # __class_uri__ = ""
    __slug_item__ = "situacao_convenio"
    __slug_lista__ = "situacoes_convenios"
    __resumidos__ = __expostos__ = [
        "nome", "href_convenios",
    ]
    
    id = Column(Integer(), autoincrement=False, primary_key=True)
    nome = Column(Unicode(100))
    
    # relacionamentos
    # convenios = relationship(Convenio, backref=backref('situacao'))
    # atributos derivados
    @property
    def href_convenios(self):
        """Retorna a URL de consulta a convenios que estão nesta situação."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_situacao=%d' % (versao_api,self.id))

class SubsituacaoConvenio(Base):
    """Representa uma subsituacao de convenio.
    """
    __tablename__ = "subsituacao_convenio"
    # __class_uri__ = ""
    __slug_item__ = "subsituacao_convenio"
    __slug_lista__ = "subsituacoes_convenios"
    __resumidos__ = __expostos__ = [
        "nome",
    ]
    id = Column(Integer(), autoincrement=False, primary_key=True)
    nome = Column(Unicode(100))
    
    # relacionamentos
    # convenios = relationship(Convenio, backref=backref('subsituacao'))

class SituacaoPublicacaoConvenio(Base):
    """Representa uma situacao de publicacao de convenio.
    """
    __tablename__ = "situacao_publicacao_convenio"
    # __class_uri__ = ""
    __slug_item__ = "situacao_publicacao_convenio"
    __slug_lista__ = "situacoes_publicacao_convenio"
    __resumidos__ = __expostos__ = [
        "nome",
    ]
    id = Column(Integer(), autoincrement=False, primary_key=True)
    nome = Column(Unicode(100))
    
    # relacionamentos
    # convenios = relationship(Convenio, backref=backref('situacao_publicacao'))

class Modalidade(Base):
    """Representa uma modalidade de proposta ou de convenio.
    """
    __tablename__ = "modalidade_proposta"
    # __class_uri__ = ""
    __slug_item__ = "modalidade"
    __slug_lista__ = "modalidades"
    __resumidos__ = __expostos__ = [
        "nome", "href_propostas", "href_convenios",
    ]
    
    id = Column(SmallInteger, primary_key=True)
    nome = Column(Unicode(40))
    
    # relacionamentos
    # backrefs:
    # propostas = relationship(Proposta, backref=backref("modalidade"))
    
    # atributos derivados
    @property
    def href_propostas(self):
        """Retorna a URL de consulta a propostas nesta modalidade."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_modalidade=%d' % (versao_api,self.id))
    @property
    def href_convenios(self):
        """Retorna a URL de consulta a convenios nesta modalidade."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_modalidade=%d' % (versao_api,self.id))

class Orgao(Base):
    u"""Representa um órgão.
    """
    __tablename__ = "orgao"
    __class_uri__ = "http://umbel.org/umbel/rc/GovernmentalOrganization"
    __slug_item__ = "orgao"
    __slug_lista__ = "orgaos"
    __resumidos__ = ['id', 'nome', 'orgao_superior', 'cod_siasg']
    __expostos__ = __resumidos__ + [
        'orgaos_subordinados',
        'href_propostas_como_concedente',
        'href_convenios_como_concedente',
        'href_programas_como_superior',
        'href_programas_como_vinculado',
        'href_programas_como_mandatario',
        'href_programas_como_executor',
        'href_habilitacoes',
    ]
    
    id = Column(Integer, autoincrement=False, primary_key=True)
    nome = Column(Unicode(100))
    id_orgao_superior = Column(Integer, ForeignKey('orgao.id'))
    
    # relacionamentos
    orgaos_subordinados = relationship('Orgao',
        backref=backref('orgao_superior', remote_side=[id]))
    # backrefs:
    # orgaos_subordinados
    # propostas_como_executor
    # propostas_como_concedente
    # propostas_como_administrativo
    
    # atributos derivados
    @property
    def cod_siasg(self):
        return self.id
    @property
    def href_propostas_como_concedente(self):
        """Retorna a URL de consulta a propostas que têm este Òrgão como concedente."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_orgao_concedente=%d' % (versao_api,self.id))
    @property
    def href_convenios_como_concedente(self):
        """Retorna a URL de consulta a convenios que têm este Òrgão como concedente."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_orgao_concedente=%d' % (versao_api,self.id))
    @property
    def href_programas_como_superior(self):
        """Retorna a URL de consulta a programas que têm este Òrgão como superior."""
        return URIRef(URI_BASE + 'v%s/consulta/programas?id_orgao_superior=%d' % (versao_api,self.id))
    @property
    def href_programas_como_vinculado(self):
        """Retorna a URL de consulta a programas que têm este Òrgão como vinculado."""
        return URIRef(URI_BASE + 'v%s/consulta/programas?id_orgao_vinculado=%d' % (versao_api,self.id))
    @property
    def href_programas_como_mandatario(self):
        """Retorna a URL de consulta a programas que têm este Òrgão como mandatario."""
        return URIRef(URI_BASE + 'v%s/consulta/programas?id_orgao_mandatario=%d' % (versao_api,self.id))
    @property
    def href_programas_como_executor(self):
        """Retorna a URL de consulta a programas que têm este Òrgão como executor."""
        return URIRef(URI_BASE + 'v%s/consulta/programas?id_orgao_executor=%d' % (versao_api,self.id))
    @property
    def href_habilitacoes(self):
        """Retorna a URL de consulta a habilitações concedidas por este Òrgão."""
        return URIRef(URI_BASE + 'v%s/consulta/habilitacoes_area_atuacao?id_orgao=%d' % (versao_api,self.id))

class PessoaResponsavel(Base):
    """Representa uma pessoa responsavel por uma proposta.
    """
    __tablename__ = "pessoa_responsavel"
    # __class_uri__ = ""
    __slug_item__ = "pessoa_responsavel"
    __slug_lista__ = "pessoas_responsaveis"
    __expostos__ = ['nome','identificacao', 'cpf', 'cargo', #'email',
        'href_propostas_como_responsavel_pelo_concedente',
        'href_convenios_como_responsavel_pelo_concedente',
        'href_propostas_enviadas', 'href_propostas_cadastradas',
        'href_convenios_como_responsavel_pelo_proponente',
    ]
    __resumidos__ = __expostos__
    # existe o participe do proponente e o participe do concedente
    # ^^^ isso mudou ao estudar o esquema do DW
    #     existe apenas uma pessoa responsavel
    
    # id = Column (LargeBinary(20)) # sha1 do atributo cpf
    nome = Column(Unicode(70))
    identificacao = Column(Unicode(20))
    id = Column(Unicode(50), autoincrement=False, primary_key=True)
    cpf = Column(Unicode(11))
    cargo = Column(Unicode(255))
    #email = Column(Unicode(100))
    
    # relacionamentos
    # backrefs:
    # propostas_como_responsavel = relationship(Proposta,
    #    backref=backref('pessoa_responsavel_como_concedente'))
    # convenios_como_responsavel = relationship(Convenio,
    #    backref=backref('pessoa_responsavel_como_concedente'))
    # propostas_enviadas = relationship(Proposta,
    #    backref=backref('pessoa_responsavel_pelo_envio'))
    # propostas_cadastradas = relationship(Proposta,
    #    backref=backref('pessoa_responsavel_pelo_cadastramento'))
    
    # atributos derivados
    @property
    def href_propostas_como_responsavel_pelo_concedente(self):
        """Retorna a URL de consulta a propostas pelas quais esta pessoa e responsavel pelo concedente."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_pessoa_responsavel_pelo_concedente=%s' % (versao_api,self.id))
    @property
    def href_propostas_cadastradas(self):
        """Retorna a URL de consulta a propostas que esta pessoa cadastrou."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_pessoa_responsavel_pelo_cadastramento=%s' % (versao_api,self.id))
    @property
    def href_propostas_enviadas(self):
        """Retorna a URL de consulta a propostas que esta pessoa enviou."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_pessoa_responsavel_pelo_envio=%s' % (versao_api,self.id))
    @property
    def href_convenios_como_responsavel_pelo_concedente(self):
        """Retorna a URL de consulta a convenios pelos quais esta pessoa e responsavel pelo lado do concedente."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_pessoa_responsavel_como_concedente=%s' % (versao_api,self.id))
    @property
    def href_convenios_como_responsavel_pelo_proponente(self):
        """Retorna a URL de consulta a convenios pelos quais esta pessoa e responsavel pelo lado do proponente."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_pessoa_responsavel_como_proponente=%s' % (versao_api,self.id))

class PropostaPrograma(Base):
    """Associacao entre propostas e programas.
    """
    __tablename__ = 'proposta_programa'
    __slug_item__ = "proposta_programa"
    __slug_lista__ = "proposta_programa"
    __expostos__ = [
        'valores',
    ]
    __resumidos__ = __expostos__
    
    id_proposta = Column(BigInteger(), ForeignKey('proposta.id'), primary_key=True)
    id_programa = Column(BigInteger(), ForeignKey('programa.id'), primary_key=True)
    valor_global = Column(Numeric(20,2))
    valor_repasse = Column(Numeric(20,2))
    valor_contrapartida = Column(Numeric(20,2))
    valor_contrapartida_financeira = Column(Numeric(20,2))
    valor_contrapartida_bens = Column(Numeric(20,2))
    
    proposta = relationship("Proposta", backref="_programas")
    programa = relationship("Programa", backref="_propostas")
    
    @property
    def id(self):
        return "%d-%d" % (self.id_proposta, self.id_programa)
    @property
    def valores(self):
        return {
            'global': self.valor_global,
            'repasse': self.valor_repasse,
            'contrapartida': self.valor_contrapartida,
            'contrapartida_financeira': self.valor_contrapartida_financeira,
            'contrapartida_bens_servicos': self.valor_contrapartida_bens,
        }

class ConvenioPrograma(Base):
    """Associacao entre convenios e programas.
    """
    __tablename__ = 'convenio_programa'
    __slug_item__ = "convenio_programa"
    __slug_lista__ = "convenio_programa"
    __expostos__ = [
        'valores',
    ]
    __resumidos__ = __expostos__
    
    id_convenio = Column(BigInteger(), ForeignKey('convenio.id'), primary_key=True)
    id_programa = Column(BigInteger(), ForeignKey('programa.id'), primary_key=True)
    valor_global = Column(Numeric(20,2))
    valor_repasse = Column(Numeric(20,2))
    valor_contrapartida = Column(Numeric(20,2))
    valor_contrapartida_financeira = Column(Numeric(20,2))
    valor_contrapartida_bens = Column(Numeric(20,2))
    
    convenio = relationship("Convenio", backref="_programas")
    programa = relationship("Programa", backref="_convenios")
    
    @property
    def id(self):
        return "%d-%d" % (self.id_convenio, self.id_programa)
    @property
    def valores(self):
        return {
            'global': self.valor_global,
            'repasse': self.valor_repasse,
            'contrapartida': self.valor_contrapartida,
            'contrapartida_financeira': self.valor_contrapartida_financeira,
            'contrapartida_bens': self.valor_contrapartida_bens,
        }

class Proposta(Base):
    """Representa uma proposta.
    """
    __tablename__ = "proposta"
    # __class_uri__ = ""
    __slug_item__ = "proposta"
    __slug_lista__ = "propostas"
    __expostos__ = [
        'numero_proposta',
        'id',
        'convenio',
        'inicio_execucao', 'fim_execucao',
        'justificativa', 'objeto',
        'valor_global', 'valor_repasse',
        'valor_contra_partida',
        'data_envio_proposta', 'data_cadastramento_proposta',
        'situacao',
        'proponente',
        'programas',
        'pessoa_responsavel_pelo_concedente',
        'pessoa_responsavel_pelo_cadastramento',
        'pessoa_responsavel_pelo_envio',
        'composicao_repasse',
    ]
    
    __resumidos__ = [
        'id',
        'inicio_execucao', 'fim_execucao',
        'justificativa_resumida', 'objeto_resumido',
        'valor_global', 'valor_repasse',
        'valor_contra_partida',
        'data_envio_proposta', 'data_cadastramento_proposta',
        'situacao',
        'proponente',
        #'cpf_pessoa_responsavel_pelo_concedente',
        #'cpf_pessoa_responsavel_pelo_cadastramento',
        #'cpf_pessoa_responsavel_pelo_envio',
    ]
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    sequencial = Column(Integer())
    inicio_execucao = Column(Date())
    fim_execucao = Column(Date())
    justificativa = Column(Unicode(5000))
    valor_global = Column(Numeric(20,2), nullable=False) 
    valor_repasse = Column(Numeric(20,2), nullable=False)
    valor_contra_partida = Column(Numeric(20,2))
    valor_contrapartida_financeira = Column(Numeric(20,2))
    valor_contrapartida_bens_servicos = Column(Numeric(20,2))
    
    ano = Column(Integer())
    data_envio_proposta = Column(Date())
    data_cadastramento_proposta = Column(Date())
    id_situacao = Column(Integer(), ForeignKey('situacao_proposta.id'))

    objeto = Column(Unicode(5000))
    
    capacidade_tecnica = Column(Unicode(5000))
    
    agencia_bancaria = Column(Unicode(10))
    conta_bancaria = Column(Unicode(20))
    nome_banco = Column(Unicode(50))
    codigo_banco = Column(SmallInteger())
    
    indicador_parecer_tecnico = Column(Boolean())
    indicador_parecer_juridico = Column(Boolean())
    indicador_parecer_gestor = Column(Boolean())
    
    numero_processo = Column(Unicode(50))
    
    # TODO: emenda parlamentar
    
    # id_convenio = Column(Integer, ForeignKey('convenio.id')) nao preenchido no esquema do banco
    id_proponente = Column(BigInteger, ForeignKey('proponente.id'))
    id_orgao_concedente = Column(Integer, ForeignKey('orgao.id'))
    id_modalidade = Column(SmallInteger, ForeignKey('modalidade_proposta.id'), nullable=False) # esse campo será um tabela no futuro
    id_pessoa_responsavel_pelo_concedente = Column(Unicode(50), ForeignKey('pessoa_responsavel.id'))
    id_pessoa_responsavel_pelo_cadastramento = Column(Unicode(50), ForeignKey('pessoa_responsavel.id'))
    id_pessoa_responsavel_pelo_envio = Column(Unicode(50), ForeignKey('pessoa_responsavel.id'))
    
    # relacionamentos
    _situacao = relationship(SituacaoProposta,
        backref=backref('propostas'))
    _modalidade = relationship(Modalidade,
        backref=backref('propostas'))
    convenio = relationship('Convenio', uselist=False,
        backref=backref('proposta'),
        primaryjoin='Convenio.id_proposta==Proposta.id')
    proponente = relationship(Proponente,
        backref=backref('propostas_como_proponente'))
    orgao_concedente = relationship(Orgao,
        backref=backref('propostas_como_concedente'),
        primaryjoin='Orgao.id==Proposta.id_orgao_concedente')
    pessoa_responsavel_pelo_concedente = relationship(PessoaResponsavel,
        backref=backref('propostas_como_responsavel'),
        primaryjoin='PessoaResponsavel.id==Proposta.id_pessoa_responsavel_pelo_concedente')
    pessoa_responsavel_pelo_cadastramento = relationship(PessoaResponsavel,
        backref=backref('propostas_cadastradas'),
        primaryjoin='PessoaResponsavel.id==Proposta.id_pessoa_responsavel_pelo_cadastramento')
    pessoa_responsavel_pelo_envio = relationship(PessoaResponsavel,
        backref=backref('propostas_enviadas'),
        primaryjoin='PessoaResponsavel.id==Proposta.id_pessoa_responsavel_pelo_envio')
    #programas = relationship('Programa', secondary=proposta_programa,
    #    backref=backref('propostas'))
    # atributos derivados
    @property
    def situacao(self):
        #situacao = {
        #    'id': self.id_situacao,
        #    'nome': self._situacao.nome,
        #}
        situacao = self._situacao
        return situacao
    @property
    def modalidade(self):
        return self._modalidade.nome
    @property
    def numero_proposta(self):
        return u"%d/%d" % (self.sequencial, self.ano)
    @property
    def justificativa_resumida(self):
        return limita_tamanho(self.justificativa, 140)
    @property
    def objeto_resumido(self):
        return limita_tamanho(self.objeto, 140)
    @property
    def programas(self):
        programas = []
        for programa in self._programas:
            programas.append({
                'associacao': [
                    programa.programa,
                    {'valores': programa.valores, },
                ],
            })
        return programas
    @property
    def cpf_pessoa_responsavel_pelo_concedente(self):
        return self.pessoa_responsavel_pelo_concedente.cpf
    @property
    def cpf_pessoa_responsavel_pelo_cadastramento(self):
        return self.pessoa_responsavel_pelo_cadastramento.cpf
    @property
    def cpf_pessoa_responsavel_pelo_envio(self):
        return self.pessoa_responsavel_pelo_envio.cpf

class Convenio(Base):
    """Representa uma Transferencia Voluntaria da Uniao (TVU),
       ou uma proposta para a qual exista empenho.
    """
    __tablename__ = "convenio"
    # __class_uri__ = ""
    __slug_item__ = "convenio"
    __slug_lista__ = "convenios"
    __expostos__ = [
        'id',
        'modalidade',
        'proposta',
        'orgao_concedente',
        'pessoa_responsavel_como_concedente',
        'cpf_pessoa_responsavel_como_concedente',
        'justificativa', 'objeto', 'capacidade_tecnica',
        'data_inicio_vigencia', 'data_fim_vigencia',
        'valor_global', 'valor_repasse',
        'valor_contra_partida',
        'valor_contrapartida_financeira',
        'valor_contrapartida_bens_servicos',
        'agencia_bancaria', 'conta_bancaria', 'codigo_banco', 'nome_banco',
        'indicador_parecer_tecnico', 'indicador_parecer_juridico',
        'indicador_parecer_gestor', 'indicador_publicado',
        'numero_processo', 'numero_interno',
        'permite_ajustes_cronograma_fisico',
        'indicador_termo_aditivo',
        'data_assinatura', 'data_publicacao',
        'situacao', 'subsituacao', 'situacao_publicacao',
        'proponente',
        'programas',
        'composicao_repasse',
        'href_empenhos',
        'href_ordens_bancarias',
    ]
    
    __resumidos__ = [
        'id',
        'modalidade',
        'orgao_concedente',
        'justificativa_resumida', 'objeto_resumido',
        'data_inicio_vigencia', 'data_fim_vigencia',
        'valor_global', 'valor_repasse',
        'valor_contra_partida',
        'data_assinatura', 'data_publicacao',
        'situacao',
        'proponente',
    ]
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True) # numero do convenio
    data_inicio_vigencia = Column(Date()) # = inicio_execucao da classe Proposta
    data_fim_vigencia = Column(Date())    # = fim_execucao da classe Proposta
    justificativa = Column(Unicode(5000))
    valor_global = Column(Numeric(20,2), nullable=False) 
    valor_repasse = Column(Numeric(20,2), nullable=False)
    valor_contra_partida = Column(Numeric(20,2))
    valor_contrapartida_financeira = Column(Numeric(20,2))
    valor_contrapartida_bens_servicos = Column(Numeric(20,2))
    
    data_assinatura = Column(Date())
    data_publicacao = Column(Date())
    id_situacao = Column(Integer(), ForeignKey('situacao_convenio.id'))
    id_subsituacao = Column(Integer(), ForeignKey('subsituacao_convenio.id'))
    id_situacao_publicacao = Column(Integer(), ForeignKey('situacao_publicacao_convenio.id'))

    objeto = Column(Unicode(5000))
    
    capacidade_tecnica = Column(Unicode(5000))
    
    agencia_bancaria = Column(Unicode(10))
    conta_bancaria = Column(Unicode(20))
    nome_banco = Column(Unicode(50))
    codigo_banco = Column(SmallInteger())

    # da proposta
    indicador_parecer_tecnico = Column(Boolean())
    indicador_parecer_juridico = Column(Boolean())
    indicador_parecer_gestor = Column(Boolean())
    
    # do convenio
    indicador_publicado = Column(Boolean())
    numero_processo = Column(Unicode(100))
    numero_interno = Column(Unicode(100))
    permite_ajustes_cronograma_fisico = Column(Boolean())
    indicador_termo_aditivo = Column(Boolean())
    
    id_proposta = Column(BigInteger, ForeignKey('proposta.id'))
    id_proponente = Column(BigInteger, ForeignKey('proponente.id'))
    id_orgao_concedente = Column(Integer, ForeignKey('orgao.id'))
    id_modalidade = Column(SmallInteger, ForeignKey('modalidade_proposta.id'), nullable=False)
    id_pessoa_responsavel_como_concedente = Column(Unicode(50), ForeignKey('pessoa_responsavel.id'))
    
    # relacionamentos
    _situacao = relationship(SituacaoConvenio,
        backref=backref('convenios'))
    _subsituacao = relationship(SubsituacaoConvenio,
        backref=backref('convenios'))
    _situacao_publicacao = relationship(SituacaoPublicacaoConvenio,
        backref=backref('convenios'))
    _modalidade = relationship(Modalidade,
        backref=backref('convenios'))
    proponente = relationship(Proponente,
        backref=backref('convenios_como_proponente'))
    orgao_concedente = relationship(Orgao,
        backref=backref('convenios_como_concedente'),
        primaryjoin='Orgao.id==Convenio.id_orgao_concedente')
    pessoa_responsavel_como_concedente = relationship(PessoaResponsavel,
        backref=backref('convenios_como_responsavel'),
        primaryjoin='PessoaResponsavel.id==Convenio.id_pessoa_responsavel_como_concedente')
    
    # criados por backref
    # proposta = relationship(Proposta, uselist=None,
    #    backref=backref('convenio'),
    #    primaryjoin='Proposta.id==Convenio.id_proposta')
    # composicao_repasse
    
    # atributos derivados
    @property
    def numero_convenio(self):
        return self.id
    @property
    def situacao(self):
        #situacao = {
        #    'id': self.id_situacao,
        #    'nome': self._situacao.nome,
        #}
        situacao = self._situacao
        return situacao
    @property
    def subsituacao(self):
        #subsituacao = {
        #    'id': self.id_subsituacao,
        #    'nome': self._situacao.nome,
        #}
        subsituacao = self._subsituacao
        return subsituacao
    @property
    def situacao_publicacao(self):
        #situacao = {
        #    'id': self.id_situacao_publicacao,
        #    'nome': self._situacao.nome,
        #}
        situacao = self._situacao_publicacao
        return situacao
    @property
    def modalidade(self):
        return self._modalidade.nome
    @property
    def situacao_projeto_basico(self):
        return self._situacao_projeto_basico
    @property
    def justificativa_resumida(self):
        return limita_tamanho(self.justificativa, 140)
    @property
    def objeto_resumido(self):
        return limita_tamanho(self.objeto, 140)
    @property
    def cpf_pessoa_responsavel_como_concedente(self):
        return self.pessoa_responsavel_como_concedente.cpf
    @property
    def programas(self):
        programas = []
        for programa in self._programas:
            programas.append({
                'vinculacao': {
                    'programa': programa.programa,
                    'valores': programa.valores,
                },
            })
        return programas
    
    @property
    def href_empenhos(self):
        """Retorna a URL de consulta aos empenhos deste convênio."""
        return URIRef(URI_BASE + 'v%s/consulta/empenhos?id_convenio=%d' % (versao_api,self.id))
    @property
    def href_ordens_bancarias(self):
        """Retorna a URL de consulta às ordens bancárias deste convênio."""
        return URIRef(URI_BASE + 'v%s/consulta/ordens_bancarias?id_convenio=%d' % (versao_api,self.id))
    
    # renderizacao especial
    def to_html(self, atributo_serializar="__expostos__"):
        """Expoe o conteudo do objeto em formato HTML.
        """
        from serializer import HTMLAggregator
        ag = HTMLAggregator('convenios', atributo_serializar,
            template='templates/convenio.pt')
        ag.add(self)
        ag.dataset_split['current_url'] = self.doc_uri+".html"
        return ag.serialize()

class Programa(Base):
    """Representa um programa do Plano Plurianual (PPA) - conceito do SIOP.
    """
    __tablename__ = "programa"
    # __class_uri__ = ""
    __slug_item__ = "programa"
    __slug_lista__ = "programas"
    __expostos__ = [
        'id',
        'cod_programa_siconv',
        'nome', 'descricao',
        'data_disponibilizacao',
        'data_inicio_recebimento_propostas', 'data_fim_recebimento_propostas',
        'acao_orcamentaria',
        'obriga_plano_trabalho',
        'aceita_emenda_parlamentar',
        'data_inicio_emenda_parlamentar', 'data_fim_emenda_parlamentar',
        'data_inicio_beneficiario_especifico', 'data_fim_beneficiario_especifico',
        'data_publicacao_dou',
        'situacao',
        'orgao_superior', 'orgao_mandatario', 'orgao_vinculado', 'orgao_executor',
        'ufs_habilitadas', 'atende_a',
        'href_emendas',
        'href_propostas',
        'href_convenios',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    cod_programa_siconv = Column(Unicode(18))
    nome = Column(Unicode(255))
    descricao = Column(Unicode(5000))
    data_disponibilizacao = Column(Date())
    data_inicio_recebimento_propostas = Column(Date())
    data_fim_recebimento_propostas = Column(Date())
    acao_orcamentaria = Column(Unicode(8))
    obriga_plano_trabalho = Column(Boolean())
    aceita_emenda_parlamentar = Column(Boolean())
    data_publicacao_dou = Column(Date())
    possui_chamamento_publico = Column(Boolean())
    aceita_despesa_administrativa = Column(Boolean())
    data_inicio_emenda_parlamentar = Column(Date())
    data_fim_emenda_parlamentar = Column(Date())
    data_inicio_beneficiario_especifico = Column(Date())
    data_fim_beneficiario_especifico = Column(Date())
    situacao = Column(Unicode(100))
    
    id_orgao_superior = Column(Integer, ForeignKey('orgao.id'))
    id_orgao_vinculado = Column(Integer, ForeignKey('orgao.id'))
    id_orgao_mandatario = Column(Integer, ForeignKey('orgao.id'))
    id_orgao_executor = Column(Integer, ForeignKey('orgao.id'))
    #id_qualificacao_proposta = Column(Integer, ForeignKey('qualificacao_proposta.id'))
    
    
    # relacionamentos
    orgao_superior = relationship(Orgao,
        backref=backref('programas_como_superior'),
        primaryjoin='Orgao.id==Programa.id_orgao_superior')
    orgao_vinculado = relationship(Orgao,
        backref=backref('programas_como_vinculado'),
        primaryjoin='Orgao.id==Programa.id_orgao_vinculado')
    orgao_mandatario = relationship(Orgao,
        backref=backref('programas_como_mandatario'),
        primaryjoin='Orgao.id==Programa.id_orgao_mandatario')
    orgao_executor = relationship(Orgao,
        backref=backref('programas_como_executor'),
        primaryjoin='Orgao.id==Programa.id_orgao_executor')
    #qualificacao_proposta = relationship(QualificacaoProposta,
    #    backref=backref('programas'))
    atende_a = relationship(NaturezaJuridica, secondary=programa_atende_a,
        backref=backref('programas'))
    estados_habilitados = relationship(UnidadeFederativa, secondary=uf_programa,
        backref=backref('programas'))
    
    _ufs_habilitadas = association_proxy('estados_habilitados', 'sigla')
    
    # atributos derivados
    @property
    def codigo(self):
        return self.id
    
    @property
    def href_emendas(self):
        """Retorna a URL de consulta a emendas associadas a este programa."""
        return URIRef(URI_BASE + 'v%s/consulta/emendas?id_programa=%d' % (versao_api, self.id))
    
    @property
    def href_propostas(self):
        """Retorna a URL de consulta a propostas associadas a este programa."""
        return URIRef(URI_BASE + 'v%s/consulta/propostas?id_programa=%d' % (versao_api, self.id))
    
    @property
    def href_convenios(self):
        """Retorna a URL de consulta a convenios associados a este programa."""
        return URIRef(URI_BASE + 'v%s/consulta/convenios?id_programa=%d' % (versao_api, self.id))
    
    @property
    def ufs_habilitadas(self):
        return sorted(self._ufs_habilitadas)

# GeometryDDL(Municipio.__table__)

class Emenda(Base):
    """Representa uma emenda parlamentar - conceito do SIOP.
    """
    __tablename__ = "emenda"
    # __class_uri__ = ""
    __slug_item__ = "emenda"
    __slug_lista__ = "emendas"
    __expostos__ = [
        'id', 'programa', 'id_programa_qualificacao', 'numero', 'valor',
    ]
    __resumidos__ = __expostos__
    
    id_programa = Column(BigInteger(), ForeignKey('programa.id'),
        primary_key=True)
    numero = Column(BigInteger(), autoincrement=False, primary_key=True)
    id_programa_qualificacao = Column(BigInteger(), autoincrement=False,
        primary_key=True)
    valor = Column(Numeric(20,2))
    
    # relacionamentos
    programa = relationship(Programa, backref=backref('emendas'))
    # propostas e convenios?
    
    # atributos derivados
    @property
    def id(self):
        return "%d,%d,%d" % (self.id_programa, self.numero, self.id_programa_qualificacao)
    
class OrdemBancaria(Base):
    """Representa uma Ordem Bancaria (OB) - conceito do SIAFI.
    """
    __tablename__ = "ordem_bancaria"
    # __class_uri__ = ""
    __slug_item__ = "ordem_bancaria"
    __slug_lista__ = "ordens_bancarias"
    __resumidos__ = [
        'id', 'numero', 'id_unidade_emitente',
        'convenio',
        'data', 'data_ateste',
        'valor',
        'observacao',
        'numero_documento_habil_siafi',
    ]
    __expostos__ = __resumidos__ + [
        'numero_interno_concedente',
        'cod_gestao_emitente',
        'cod_gestao_favorecida',
        'situacao',
        'justificativa_inadimplencia',
    ]
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    numero = Column(Unicode())
    id_unidade_emitente = Column(BigInteger())#, ForeignKey('unidade_emitente.id'))
    id_convenio = Column(BigInteger(), ForeignKey('convenio.id'))
    numero_documento_habil_siafi = Column(Unicode()) # FK com SIAFI
    numero_interno_concedente = Column(Unicode()) # controle do proprio orgao
    cod_gestao_emitente = Column(BigInteger()) # FK com o SIAFI?
    cod_gestao_favorecida = Column(BigInteger()) # FK com o SIAFI?
    observacao = Column(Unicode())
    data_ateste = Column(Date())
    situacao = Column(Unicode()) # texto livre
    justificativa_inadimplencia = Column(Unicode()) # descricao em texto livre
    
    # cancelamento
    cod_cancelamento = Column(Integer()) # FK?
    numero_doc_siafi_cancelamento = Column(BigInteger()) # FK com SIAFI?
    observacao_cancelamento = Column(Unicode())
    data_cancelamento = Column(Date())
    
    no_cpr = Column(Boolean()) # indica se esta ou nao no CPR (SIAFI)
    tipo_documento = Column(Unicode()) # OB ou OBTV, mas e texto livre
    valor = Column(Numeric(20,2))
    data = Column(Date())
    
    # relacionamentos
    convenio = relationship(Convenio,
        backref=backref('ordens_bancarias'))

class EspecieEmpenho(Base):
    """Representa uma Especie de Empenho - conceito do SIAFI.
    """
    __tablename__ = "especie_empenho"
    # __class_uri__ = ""
    __slug_item__ = "especie_empenho"
    __slug_lista__ = "especies_empenho"
    __expostos__ = [
        'id', 'descricao', 'href_empenhos',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    descricao = Column(Unicode())

    @property
    def href_empenhos(self):
        """Retorna a URL de consulta aos empenhos com esta Espécie."""
        return URIRef(URI_BASE + 'v%s/consulta/empenhos?id_especie=%d' % (versao_api,self.id))
    
class Empenho(Base):
    """Representa uma Nota de Empenho - conceito do SIAFI.
    """
    __tablename__ = "empenho"
    # __class_uri__ = ""
    __slug_item__ = "empenho"
    __slug_lista__ = "empenhos"
    __expostos__ = [
        'id', 'numero', 'especie',
        'convenio', 'proponente_favorecido',
        'cod_unidade_gestora_emitente', 'cod_unidade_gestora_referencia',
        'cod_unidade_gestora_responsavel',
        'cod_gestao_emitente', 'cod_gestao_referencia',
        'cod_fonte_recurso', 'tipo_empenho',
        'numero_plano_trabalho_resumido', 'numero_plano_interno',
        'esfera_orcamentaria', 'data_emissao',
        'numero_interno_concedente', 'numero_interno_concedente_referencia',
        'observacao', 'situacao',
        'numero_lista', 'numero_programa_trabalho',
        'cod_unidade_orcamentaria',
        'natureza_despesa_subitem',
        'valor',
        'numero_empenho_referencia',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    numero = Column(Unicode()) # contem caracteres qualificadores alfabeticos
    numero_minuta = Column(Unicode())
    id_convenio = Column(BigInteger(), ForeignKey('convenio.id'))
    id_especie = Column(BigInteger(), ForeignKey('especie_empenho.id'))
    cod_unidade_gestora_emitente = Column(BigInteger()) # FK no SIAFI
    # o atributo a seguir foi retirado pois informacao nao consta no siconv
    # nome_unidade_gestora_emitente = Column(Unicode()) # derivado da UG SIAFI
    cod_unidade_gestora_referencia = Column(BigInteger()) # FK no SIAFI
    cod_unidade_gestora_responsavel = Column(BigInteger()) # FK no SIAFI
    cod_gestao_emitente = Column(BigInteger()) # FK no SIAFI
    cod_gestao_referencia = Column(BigInteger()) # FK no SIAFI
    cod_fonte_recurso = Column(BigInteger()) # FK no SIAFI
    tipo_empenho = Column(Unicode()) # descricao (desnormalizado)
    numero_plano_trabalho_resumido = Column(BigInteger()) # FK no SIOP
    numero_plano_interno = Column(Unicode())
    esfera_orcamentaria = Column(Unicode()) # descricao (desnormalizado)
    data_emissao = Column(Date())
    numero_interno_concedente = Column(Unicode()) # campo livre
    numero_interno_concedente_referencia = Column(Unicode()) # campo livre
    observacao = Column(Unicode())
    situacao = Column(Unicode()) # textual (desnormalizado)
    numero_lista = Column(Unicode()) # dados contem caracteres alfanumericos
    numero_programa_trabalho = Column(BigInteger(), ForeignKey('programa.id'))
    cod_unidade_orcamentaria = Column(BigInteger()) # FK no SIOP?
    numero_natureza_despesa_subitem = Column(Unicode()) # FK no SIOP?
    descricao_natureza_despesa_subitem = Column(Unicode())
    valor = Column(Numeric(20,2))
    # autorrelacionamento consistente apenas no SIAFI
    numero_empenho_referencia = Column(Unicode())
    id_proponente_favorecido = Column(BigInteger(), ForeignKey('proponente.id'))
    
    # relacionamentos
    convenio = relationship(Convenio, backref=backref('empenhos'))
    proponente_favorecido = relationship(Proponente,
        backref=backref('notas_empenho'))
    especie = relationship(EspecieEmpenho,
        backref=backref('especie_empenho'))
        
    # atributos derivados
    # o atributo a seguir foi retirado pois informacao nao consta no siconv
    #@property
    #def unidade_gestora_emitente(self):
    #    ugr = {
    #        'cod': self.cod_unidade_gestora_emitente,
    #        'nome': self.nome_unidade_gestora_emitente,
    #        }
    #    return ugr
    @property
    def natureza_despesa_subitem(self):
        nds = {
            'numero': self.numero_natureza_despesa_subitem,
            'descricao': self.descricao_natureza_despesa_subitem,
            }
        return nds
    

class ComposicaoRepasseProposta(Base):
    """Representa a composicao dos repasses (qualificacao) de uma proposta.
    """
    __tablename__ = "composicao_repasse_proposta"
    __tableargs__ = (
        ForeignKeyConstraint(
            ['emenda_id_programa', 'emenda_numero', 'emenda_id_programa_qualificacao'],
            [
                'emenda.id_programa',
                'emenda.numero',
                'emenda.id_programa_qualificacao',
            ]
        )
    )
    # __class_uri__ = ""
    __slug_item__ = "composicao_repasse_proposta"
    __slug_lista__ = "composicoes_repasse_proposta"
    __expostos__ = [
        'id',
        'tipo',
        'proposta',
        'emenda',
        'valor_repasse',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    id_proposta = Column(BigInteger(), ForeignKey('proposta.id'))
    
    # chave estrangeira composta
    emenda_id_programa = Column(BigInteger())
    emenda_numero = Column(BigInteger())
    emenda_id_programa_qualificacao = Column(BigInteger())
    
    tipo = Column(Unicode()) # tipo da qualificacao:
    # emenda parlamentar, repasse voluntario ou beneficiario especifico
    valor_repasse = Column(Numeric(20,2))
    
    # relacionamentos
    proposta = relationship(Proposta, backref=backref('composicao_repasse'))
    emenda = relationship(Emenda, backref=backref('composicao_repasse_proposta'),
        primaryjoin='and_('
        'ComposicaoRepasseProposta.emenda_id_programa==Emenda.id_programa, '
        'ComposicaoRepasseProposta.emenda_numero==Emenda.numero, '
        'ComposicaoRepasseProposta.emenda_id_programa_qualificacao==Emenda.id_programa_qualificacao)'
        ,
        foreign_keys=[emenda_id_programa, emenda_numero,
            emenda_id_programa_qualificacao]
    )

class ComposicaoRepasseConvenio(Base):
    """Representa a composicao dos repasses (qualificacao) de um convenio.
    """
    __tablename__ = "composicao_repasse_convenio"
    __tableargs__ = (
        ForeignKeyConstraint(
            ['emenda_id_programa', 'emenda_numero', 'emenda_id_programa_qualificacao'],
            [
                'emenda.id_programa',
                'emenda.numero',
                'emenda.id_programa_qualificacao',
            ]
        )
    )
    # __class_uri__ = ""
    __slug_item__ = "composicao_repasse_convenio"
    __slug_lista__ = "composicoes_repasse_convenio"
    __expostos__ = [
        'id',
        'tipo',
        'convenio',
        'emenda',
        'valor_repasse',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    id_convenio = Column(BigInteger(), ForeignKey('convenio.id'))
    
    # chave estrangeira composta
    emenda_id_programa = Column(BigInteger())
    emenda_numero = Column(BigInteger())
    emenda_id_programa_qualificacao = Column(BigInteger())
    
    tipo = Column(Unicode()) # tipo da qualificacao:
    # emenda parlamentar, repasse voluntario ou beneficiario especifico
    valor_repasse = Column(Numeric(20,2))
    
    # relacionamentos
    convenio = relationship(Convenio, backref=backref('composicao_repasse'))
    emenda = relationship(Emenda, backref=backref('composicao_repasse_convenio'),
        primaryjoin='and_('
        'ComposicaoRepasseConvenio.emenda_id_programa==Emenda.id_programa, '
        'ComposicaoRepasseConvenio.emenda_numero==Emenda.numero, '
        'ComposicaoRepasseConvenio.emenda_id_programa_qualificacao==Emenda.id_programa_qualificacao)'
        ,
        foreign_keys=[emenda_id_programa, emenda_numero,
            emenda_id_programa_qualificacao]
    )

class AreaAtuacaoProponente(Base):
    """Representa uma possivel area de atuacao de um proponente.
    """
    __tablename__ = "area_atuacao_proponente"
    # __class_uri__ = ""
    __slug_item__ = "area_atuacao_proponente"
    __slug_lista__ = "areas_atuacao_proponente"
    __expostos__ = [
        'id',
        'descricao',
        'href_subareas',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    descricao = Column(Unicode())

    @property
    def href_subareas(self):
        """Retorna a URL de consulta as subáreas para esta área."""
        return URIRef(URI_BASE + 'v%s/consulta/subareas_atuacao_proponente?id_area=%d' % (versao_api,self.id))
    

class SubAreaAtuacaoProponente(Base):
    """Representa uma possivel subarea de atuacao de um proponente.
    """
    __tablename__ = "subarea_atuacao_proponente"
    # __class_uri__ = ""
    __slug_item__ = "subarea_atuacao_proponente"
    __slug_lista__ = "subareas_atuacao_proponente"
    __expostos__ = [
        'id',
        'area',
        'descricao',
        'href_habilitacoes',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    id_area = Column(BigInteger(), ForeignKey('area_atuacao_proponente.id'))
    descricao = Column(Unicode())
    
    # relacionamentos
    area = relationship(AreaAtuacaoProponente, backref=backref('subareas'))
    
    @property
    def href_habilitacoes(self):
        """Retorna a URL de consulta a habilitaçõs para esta subárea."""
        return URIRef(URI_BASE + 'v%s/consulta/habilitacoes_area_atuacao?id_subarea=%d' % (versao_api,self.id))
    

class HabilitacaoAreaAtuacao(Base):
    """Representa uma habilitacao para um proponente atuar com determinado
    orgao na area especificada.
    """
    __tablename__ = "habilitacao_area_atuacao"
    # __class_uri__ = ""
    __slug_item__ = "habilitacao_area_atuacao"
    __slug_lista__ = "habilitacoes_area_atuacao"
    __expostos__ = [
        'id',
        'subarea',
        'proponente',
        'orgao',
        'pessoa_responsavel',
        'cpf_responsavel',
        'situacao',
        'data_inicio',
        'data_vencimento',
    ]
    __resumidos__ = __expostos__
    
    id = Column(BigInteger(), autoincrement=False, primary_key=True)
    id_subarea = Column(BigInteger(),
        ForeignKey('subarea_atuacao_proponente.id'))
    id_proponente = Column(BigInteger(), ForeignKey('proponente.id'))
    id_orgao = Column(BigInteger(), ForeignKey('orgao.id'))
    id_pessoa_responsavel = Column(Unicode(50),
        ForeignKey('pessoa_responsavel.id'))
    situacao = Column(Unicode())
    data_inicio = Column(Date())
    data_vencimento = Column(Date())
    
    # relacionamentos
    subarea = relationship(SubAreaAtuacaoProponente,
        backref=backref('habilitacoes'))
    proponente = relationship(Proponente, backref=backref('habilitacoes'))
    orgao = relationship(Orgao, backref=backref('habilitacoes'))
    pessoa_responsavel = relationship(PessoaResponsavel,
        backref=backref('habilitacoes'))
    
    @property
    def cpf_responsavel(self):
        return self.pessoa_responsavel.cpf

# incializacao do banco
def initialize_sql(engine):
    Session.configure(bind=engine)
    Base.metadata.bind = engine

class MetodoWS(ExposedObject):
    """
    Um registro de metodo de webservice.
    """
    __expostos__ = set(['path', 'doc_href', 'params'])
    def __init__(self, id, path, params, doc_href=None):
        if not isinstance(id, basestring):
            raise TypeError("parametro 'id' deve ser uma string")
        if not isinstance(path, basestring):
            raise TypeError("parametro 'path' deve ser uma string")
        if not isinstance(params, list):
            raise TypeError("parametro 'params' deve ser uma lista")
        self.id = id
        self.path = path
        self.params = params
        if doc_href:
            self.doc_href = doc_href
    def __repr__(self):
        return "<" + self.__class__.__name__ + " id=%s" % self.id + ">"
    def repr_xml(self):
        attrs = {'href': self.path,}
        if getattr(self, 'doc_href', None):
            attrs['doc_href']=self.doc_href
        return E('metodo', attrs,
            (E('parametros', (E('parametro', par) for par in self.params))))

class RegistroWS(ExposedObject):
    """
    Registro de um webservice.
    """
    __expostos__ = set(['versao', 'metodos'])
    __element_name__ = 'webservice'
    __element_listname__ = 'webservices'
    def __init__(self, id, uri_base, versao="1"):
        self.id = id
        self.uri_base = uri_base
        self.versao = versao
        self.metodos = []
    def __repr__(self):
        return "<" + self.__class__.__name__ + \
            " id=%s, %d metodos" % (self.id, len(self.metodos)) + ">"
    def add_method(self, id, path, params, doc_href=None):
        self.metodos.append(MetodoWS(id, path, params, doc_href=doc_href))
    def repr_xml(self):
        return E('webservice', {'href': self.uri_base}, (item.repr_xml()
            for item in self.metodos()))
