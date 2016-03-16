# -*- coding: utf-8 -*-
"""
Módulo serializer.py da API de dados abertos do SICONV.
=======================================================

© 2011, 2012 Ministério do Planejamento, Orçamento e Gestão

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

from types import GeneratorType, LongType
from collections import Iterable
from decimal import Decimal

from pyramid.renderers import get_renderer, render

from namespace import URI_BASE
from namespace import LIC, SIORG, SIAFI
from namespace import GEO
from namespace import DBPEDIA, DBONT, DBPROP
from namespace import VOID, FOAF, VCARD

from datetime import date, time, datetime
from decimal import Decimal
import re
import locale

from geoalchemy.base import SpatialElement

# csv
from csv import writer as csv_writer

# json
try:
    # o modulo json existe na biblioteca padrao do Python 2.6 ou superior
    import json
except ImportError:
    # no Python 2.5, a biblioteca simplejson serve como substituta
    import simplejson as json
# monkey patch de precisao dos floats
json.encoder.FLOAT_REPR = lambda f: ("%.6f" % f)

# RDF
from rdflib.graph import ConjunctiveGraph
from rdflib.term import URIRef, Literal, BNode
from rdflib.namespace import Namespace, RDF, RDFS, OWL

# XML (amara)
from amara.writers.struct import structwriter, ROOT, E, E_CURSOR
from StringIO import StringIO as sio

# HTML
from label_map import labels
from webhelpers.html.builder import HTML
from webhelpers.html.converters import format_paragraphs
from webhelpers.html.tags import link_to_if, link_to, ul

# ajusta o locale para o locale da maquina
locale.setlocale(locale.LC_ALL, '')

# forcar o locale para portugues
# (no servidor nao estava trazendo o locale correto
locale.setlocale(locale.LC_ALL,('pt_BR', 'UTF8'))

class Aggregator(object):
    def __init__(self, format, name, atributo_serializar="__expostos__",
            total_registros=None, dataset_split=None,
            template='templates/lista.pt',
            parameters=None, request=None):
        self.format = format
        self.name = name
        self.aggregator = []
        self._qt_items = 0
        self.total_registros = total_registros
        if dataset_split is None:
            dataset_split = {}
        self.dataset_split = dataset_split
        self.template = template
        self.opened = True
        self.atributo_serializar = atributo_serializar
        if parameters is None:
            parameters = {}
        self.parameters = parameters
        self.filters_used = dict(getattr(request,'params', {}))
        if self.filters_used and self.filters_used.get('offset', False):
            # 'offset' nao e um filtro, entao o retiramos
            del self.filters_used['offset']
    def __len__(self):
        return self._qt_items
    def __repr__(self):
        return "<" + self.__class__.__name__ + "/" + self.formato + \
            " with %d items of type %s>" % (len(self), self.type)
    def _first_obj(self, obj):
        """
        Ajusta o agregador na chegada do primeiro objeto.
        """
        self.obj_class = obj.__class__
        self.type = self.obj_class.__name__
    def add(self, obj):
        """
        Appends an object to the aggregator.
        """
        if not self.opened:
            raise ValueError("Cannot append object to a closed aggregator.")
        if len(self) > 0:
            if not isinstance(obj, self.obj_class):
                raise TypeError("Added instances must have the same type as existing objects.")
        else:
            # primeiro objeto adicionado
            self._first_obj(obj)
        self.aggregator.append(obj)
        self._qt_items += 1
    def formata(self, obj):
        if isinstance(obj, unicode):
            return obj.encode("utf-8")
        elif isinstance(obj, Iterable) \
            and not isinstance(obj, basestring) \
            and not isinstance(obj, dict):
            return ",\n".join(repr(item) for item in obj)
        else:
            return repr(obj)
    def close(self):
        self.opened = False
    def serialize(self, format=None):
        return repr(self.aggregator)

class XMLAggregator(Aggregator):
    def __init__(self, *args, **kw):
        super(XMLAggregator, self).__init__('xml', *args, **kw)
    def formata(self, obj, nome=""):
        if nome:
            obj = getattr(obj, nome)
        if getattr(obj, 'repr_xml', None):
            return obj.repr_xml()
        elif isinstance(obj, URIRef):
            return {'href': obj}
        elif isinstance(obj, unicode):
            return obj.encode("utf-8")
        # tipos com representacao nativa em xml
        elif isinstance(obj, str) or \
            isinstance(obj, date) or \
            isinstance(obj, time):
            return obj
        elif isinstance(obj, int) or \
            isinstance(obj, LongType) or \
            isinstance(obj, float):
            return str(obj)
        elif isinstance(obj, Decimal):
            return "%0.2f" % obj
        elif (isinstance(obj, Iterable) or \
            isinstance(obj, GeneratorType)) and \
            not isinstance(obj, basestring) and \
            not isinstance(obj, dict):
            return (E((item.__element_name__ if getattr(item, '__element_name__', None)
                else item.__class__.__name__), self.formata(item)) for item in obj)
        elif isinstance(obj, dict):
            return (E(k, (v.repr_xml() if getattr(v, 'repr_xml', None) \
                else self.formata(v))) for k, v in obj.items())
        elif isinstance(obj, ExposedObject):
            return (E(obj.__element_name__ if getattr(obj, '__element_name__', None)
                else obj.__class__.__name__, {'href':obj.uri}))
        else:
            format_func = getattr(obj, 'repr_xml', repr)
            return format_func(obj)
    @staticmethod
    def element_name(obj):
        """Retorna o nome do elemento XML do objeto."""
        if getattr(obj, '__element_name__', None):
            name = obj.__element_name__
            if name.startswith('href_'):
                return name[5:]
            else:
                return name
        else:
            return re.sub("([a-z])([A-Z])", "\g<1>_\g<2>", obj.__class__.__name__).lower()
    @staticmethod
    def element_atrs(obj):
        """Retorna atributos XML do objeto a serializar."""
        atrs = {}
        if getattr(obj, 'id', None):
            atrs['id'] = obj.id
        if getattr(obj, 'uri', None):
            atrs['href'] = obj.uri
        return atrs
    def element(self, obj, atr):
        """Retorna um elemento XML para o atributo"""
        nome = atr
        if nome.startswith('href_'):
            nome = nome[5:]
        return E(nome, self.formata(obj, atr))
    def close(self):
        super(XMLAggregator, self).close()
        str_buffer = sio()
        next_url = self.dataset_split.get('next_url', '')
        # estrutura agregadora
        writer = structwriter(stream=str_buffer, indent=True)
        feed = writer.feed(
            ROOT(
                E(self.name,
                    ({'total_registros': self.total_registros}
                        if self.total_registros else {}),
                    ( E( self.element_name(obj),
                        self.element_atrs(obj),
                        ( self.element(obj, atr)
                        for atr in getattr(obj,self.atributo_serializar) if (getattr(obj, atr) or isinstance(getattr(obj,atr),int)) ) )
                    for obj in self.aggregator ),
                    E('proximos', {'href':next_url})
                        if next_url else tuple(),
                )
            )
        )
        r = str_buffer.getvalue()
        str_buffer.close()
        self.serialization = r
    def serialize(self, format='xml'):
        self.close() # Amara XML structwriter precisa fechar
        return self.serialization

class JSONAggregator(Aggregator):
    def __init__(self, *args, **kw):
        super(JSONAggregator, self).__init__('json', *args, **kw)
    @staticmethod
    def serialize_json(obj):
        """
        Funcao auxiliar na serializacao de objetos para JSON.
        """
        if getattr(obj, 'repr_json', None):
            return obj.repr_json()
        elif isinstance(obj, Iterable) and \
                not isinstance(obj, basestring) and \
                not isinstance(obj, dict):
            return list(obj)
        elif isinstance(obj, URIRef):
            return {'href': str(obj)}
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return repr(obj)
    def serialize(self, format='json'):
        metadados = {}
        if self.total_registros:
            metadados['total_registros'] = self.total_registros
        next_url = self.dataset_split.get('next_url', '')
        if next_url:
            metadados['proximos'] = next_url
        return json.dumps(
            {
                'metadados': metadados,
                self.name: [item.item_json(atributo_serializar=self.atributo_serializar) for item in self.aggregator],
            },
            default=self.serialize_json)

class HTMLAggregator(Aggregator):
    def __init__(self, *args, **kw):
        super(HTMLAggregator, self).__init__('html', *args, **kw)
    @classmethod
    def tidy_value(cls, value):
        # objeto exposto
        if isinstance(value, ExposedObject):
            name = getattr(value, 'nome', getattr(value, 'descricao', False))
            ref = cls.tidy_label(value.__class__.__name__) + \
                (" %s" % unicode(value.id)) + \
                (u"" if not name else (u": %s" % name))
            uri = getattr(value, 'uri', False)
            return link_to_if(uri, ref, uri)
        # listas
        elif isinstance(value, Iterable) and \
                not isinstance(value, basestring) and \
                not isinstance(value, dict):
            return ul(cls.tidy_value(item) for item in value)
        # dicionarios
        elif isinstance(value, dict):
            return HTML.dl(HTML(*[
                HTML(*[HTML.dt(cls.tidy_label(k)), HTML.dd(cls.tidy_value(v))])
                    for k, v in value.items()]
            ))
        # datas
        elif isinstance(value, date):
            return value.strftime(u"%d/%m/%Y")
        # decimais (em geral, valores moeda)
        elif isinstance(value, Decimal):
            return u"R$ "+locale.format(u"%.02f",value, grouping=True, monetary=True)
        # booleanos
        elif isinstance(value, bool):
            return u"Verdadeiro" if value else u"Falso"
        # strings longas
        elif isinstance(value, unicode) and len(value) > 140:
            return format_paragraphs(value, preserve_lines=True)
        # caso geral
        else:
            uri = getattr(value, 'uri', False)
            return link_to_if(uri, value, uri)
    
    @staticmethod
    def tidy_label(label):
        if label in labels.keys():
            return labels[label]
        # separa palavras em CamelCase -> Camel Case
        label = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", label)
        return label.replace(u"_", u" ").title()
    def serialize(self, format='html'):
        # prepara metadados
        metadados = {}
        metadados['total_registros'] = getattr(self,'total_registros',0)
        next_url = self.dataset_split.get('next_url', '')
        if next_url:
            metadados['proximos'] = next_url
        # formatos alternativos
        metadados['alternativos'] = {}
        url_formatos = re.compile(r"(\.)html(\??)")
        if url_formatos.search(self.dataset_split['current_url']):
            formatos = ['xml', 'json', 'csv']
            metadados['alternativos'] = dict(zip(formatos, [
                re.sub(url_formatos, r"\1%s\2" % formato, self.dataset_split['current_url'])
                for formato in formatos ]
            ))
        # traz o template do layout geral
        layout = get_renderer('templates/layout.pt').implementation()
        return render(self.template,
            {
                'URI_BASE': URI_BASE,
                'layout': layout,
                'tidy_label': self.tidy_label,
                'tidy_value': self.tidy_value,
                'name': self.name,
                'metadados': metadados,
                'dataset_split': self.dataset_split,
                'filters_used': self.filters_used,
                'filters': self.parameters,
                'd':self.aggregator,
            },
        )

class CSVAggregator(Aggregator):
    def __init__(self, *args, **kw):
        super(CSVAggregator, self).__init__('csv', *args, **kw)
        self.cols = set()
    def add(self, obj):
        super(CSVAggregator, self).add(obj)
        atrs = set()
        for atr in getattr(obj, self.atributo_serializar):
            prop = getattr(obj, atr, None)
            if isinstance(prop, dict):
                for key in prop.keys():
                    atrs.add(atr + '/' + key)
            else:
                atrs.add(atr)
        self.cols.update(atrs)
    def serialize(self, format='csv'):
        """
        Retorna a representação em CSV de toda a agregação.
        """
        utf8_recoder = lambda s: s.encode('utf-8') if isinstance(s, unicode) \
            else s # funcao auxiliar de codificacao em utf-8
        def getter(obj, atr):
            if '/' in atr:
                d, k = atr.split('/')
                if getattr(obj, d, None):
                    return getattr(obj, d, {}).get(k, None)
                else:
                    return None
            else:
                return getattr(obj, atr, None)
        s = sio() # buffer string IO
        w = csv_writer(s)
        # cabecalhos das colunas
        cols = ['id', 'uri']
        cols.extend(sorted(self.cols))
        w.writerow(cols)
        # valores das colunas
        for obj in self.aggregator:
            w.writerow(map(
                utf8_recoder, # csv_writer nao escreve unicode
                (getter(obj, atr) for atr in cols)
                ))
        r = s.getvalue()
        s.close()
        return r
        return self.aggregator

class RDFAggregator(Aggregator):
    def __init__(self, *args, **kw):
        """Inicializa o agregador RDF.
        """
        super(RDFAggregator, self).__init__('csv', *args, **kw)
        self.aggregator = ConjunctiveGraph()
        self.aggregator.bind(u'owl', OWL)
        self.aggregator.bind(u'lic', LIC)
        self.aggregator.bind(u'siorg', SIORG)
        self.aggregator.bind(u'siafi', SIAFI)
        self.aggregator.bind(u'geo', GEO)
        self.aggregator.bind(u'dbpedia', DBPEDIA)
        self.aggregator.bind(u'dbprop', DBPROP)
        self.aggregator.bind(u'dbo', DBONT)
        self.aggregator.bind(u'void', VOID)
        self.aggregator.bind(u'foaf', FOAF)
        self.aggregator.bind(u'vcard', VCARD)
    def add(self, obj):
        """Acrescenta as triplas do objeto ao grafo agregador.
        """
        if getattr(obj, 'repr_rdf', None):
            # objeto tem um metodo para representacao propria em rdf
            triplas = obj.repr_rdf()
            for t in triplas:
                self.aggregator.add(t)
        else:
            # o objeto nao tem o metodo, tenta criar triplas por heuristicas
            subject = obj.uri
            doc = obj.doc_uri
            if doc == subject:
                doc = None
            class_uri = getattr(obj.__class__, '__class_uri__', None)
            expostos = getattr(obj.__class__,self.atributo_serializar, set())
            prop_map = getattr(obj.__class__, '__rdf_prop__', {})
            g = self.aggregator
            #  classe
            if class_uri:
                g.add((URIRef(subject), RDF['type'], URIRef(class_uri)))
            # documento
            if doc:
                g.add((URIRef(doc), RDF['type'], FOAF['Document']))
                g.add((URIRef(subject), FOAF['isPrimaryTopicOf'], URIRef(doc)))
                g.add((URIRef(doc), FOAF['primaryTopic'], URIRef(subject)))
            #  nome
            if getattr(obj, 'nome', None):
                if getattr(obj, '__rdf_prop__', None) is None or \
                        obj.__rdf_prop__.get('nome', None) is None:
                    g.add((URIRef(subject), RDFS['label'], Literal(obj.nome)))
            #  localizacao geo
            if getattr(obj, 'geo_ponto', None):
                ponto = obj.geo_ponto
                if ponto:
                    g.add((URIRef(subject), GEO['lat'], Literal(ponto['lat'])))
                    g.add((URIRef(subject), GEO['long'], Literal(ponto['lon'])))
            #  propriedades
            for atr in expostos:
                if atr in prop_map.keys():
                    if getattr(prop_map[atr], '__call__', None):
                        # as triplas da propriedade sao dadas por uma funcao
                        triplas = prop_map[atr](obj)
                        if triplas:
                            for t in triplas:
                                g.add(t)
                    elif prop_map[atr].get('metodo', None):
                        # as triplas da propriedade sao dadas por um metodo
                        m = getattr(obj, prop_map[atr]['metodo'])
                        triplas = m(atr)
                        if triplas:
                            for t in triplas:
                                g.add(t)
                    elif prop_map[atr].get('pred_uri', None):
                        # a propriedade corresponde a uma unica tripla
                        pred_uri = prop_map[atr]['pred_uri']
                        object = getattr(obj, atr, None)
                        if object:
                            obj_uri = getattr(object, 'uri', lambda: None)()
                            obj_cls_uri = getattr(object, '__class_uri__', None)
                            # o objeto tem uri definida?
                            if obj_uri:
                                g.add((URIRef(subject), URIRef(pred_uri), URIRef(obj_uri)))
                            elif obj_cls_uri:
                                # se o objeto nao tem uri mas tem uri da classe,
                                # tenta criar blank node
                                bn = BNode()
                                g.add((URIRef(subject), URIRef(pred_uri), bn))
                                g.add((bn, RDF['type'], URIRef(obj_cls_uri)))
                                g.add((bn, RDFS['comment'], Literal(unicode(obj))))
                            else:
                                # caso contrario, tratar a propriedade como um literal
                                g.add((URIRef(subject), URIRef(pred_uri), Literal(unicode(object))))
    def serialize(self, format="n3"):
        """Retorna a serializacao do agregador RDF (uniao dos grafos).
        """
        format_map = {
            'xml': 'xml',
            'rdf': 'pretty-xml',
            'rdf/xml': 'pretty-xml',
            'ttl': 'n3',
            'n3': 'n3',
            'nt': 'nt',
        }
        f = format_map.get(format, 'n3')
        current_url = self.dataset_split.get('current_url', '') # url do documento atual
        dataset_url = self.dataset_split.get('dataset_url', '') # url geral do dataset
        next_url = self.dataset_split.get('next_url', '') # url da proxima pagina
        # a uri do dataset: url do documento acrescida de #dataset
        if current_url:
            self.aggregator.add((URIRef(current_url+"#dataset"),RDF['type'],VOID['Dataset']))
            self.aggregator.add((URIRef(current_url),RDF['type'],VOID['DatasetDescription']))
            self.aggregator.add((URIRef(current_url),FOAF['primaryTopic'],URIRef(current_url+"#dataset")))
            if next_url:
                self.aggregator.add((URIRef(current_url+"#dataset"),RDFS['seeAlso'],URIRef(next_url+"#dataset")))
        if next_url:
            self.aggregator.add((URIRef(next_url+"#dataset"),RDF['type'], VOID['Dataset']))
            self.aggregator.add((URIRef(next_url),RDF['type'],VOID['DatasetDescription']))
            self.aggregator.add((URIRef(next_url),FOAF['primaryTopic'],URIRef(next_url+"#dataset")))
        if dataset_url:
            self.aggregator.add((URIRef(dataset_url+"#dataset"),RDF['type'], VOID['Dataset']))
            self.aggregator.add((URIRef(dataset_url),RDF['type'],VOID['DatasetDescription']))
            self.aggregator.add((URIRef(dataset_url),FOAF['primaryTopic'],URIRef(dataset_url+"#dataset")))
            if current_url:
                self.aggregator.add((URIRef(dataset_url+"#dataset"),VOID['subset'],URIRef(current_url+"#dataset")))
            if next_url:
                self.aggregator.add((URIRef(dataset_url+"#dataset"),VOID['subset'],URIRef(next_url+"#dataset")))
        return self.aggregator.serialize(format=f)

class ExposedObject(object):
    """Classe base para um objeto exposto no webservice.
    """
    __slug_item__ = "recurso"
    __slug_lista__ = "recursos"
    def __init__(self):
        # atributos expostos no web service
        self.__expostos__ = set()
        self.__resumidos__ = set()
    @property
    def uri(self):
        """A URI canonica do objeto."""
        slug = getattr(self, '__slug_item__', None)
        if slug is None:
            slug = self.__class__.__name__
            slug = re.sub("([a-z])([A-Z])", "\g<1>_\g<2>", nome_classe)
            slug = nome_classe.lower()
        id = getattr(self, 'id', None)
        if id is None:
            raise AttributeError(u"Não é possível determinar a URI porque o objeto não possui um atributo 'id'.")
        uri = URI_BASE
        if uri[-1] != '/':
            uri += '/'
        uri += 'id/' + slug + '/' + str(self.id)
        return uri
    @property
    def doc_uri(self):
        """A URI do documento que descreve o objeto."""
        return self.uri.replace('/id/', '/dados/', 1)
    def __repr__(self):
        return '<objeto: ' + self.uri + '>'
    def to_csv(self, atributo_serializar="__expostos__", **kw):
        """Expoe o conteudo do objeto em formato CSV.
        """
        ag = CSVAggregator('planilha', atributo_serializar)
        ag.add(self)
        return ag.serialize()
    def to_json(self, atributo_serializar="__expostos__"):
        """Expoe o conteudo do objeto em formato JSON.
        """
        name = getattr(self, '__element_listname__',
            self.__class__.__name__.lower()+'s')
        ag = JSONAggregator(name, atributo_serializar)
        ag.add(self)
        return ag.serialize()
    def to_rdf(self, format="n3", atributo_serializar="__expostos__"):
        """Expoe o conteudo do objeto em formato RDF.
        """
        name = self.uri
        ag = RDFAggregator(name, atributo_serializar)
        ag.add(self)
        return ag.serialize(format=format)
    def to_xml(self, atributo_serializar="__expostos__"):
        """Expoe o conteudo do objeto em formato XML.
        """
        name = getattr(self, '__element_listname__',
            self.__class__.__name__.lower()+'s')
        ag = XMLAggregator(name, atributo_serializar)
        ag.add(self)
        return ag.serialize()
    def to_html(self, atributo_serializar="__expostos__"):
        """Expoe o conteudo do objeto em formato HTML.
        """
        name = getattr(self, '__element_listname__',
            self.__class__.__name__.lower()+'s')
        ag = HTMLAggregator(name, atributo_serializar,
            template='templates/recurso.pt')
        ag.add(self)
        ag.dataset_split['current_url'] = self.doc_uri+".html"
        return ag.serialize()
    def item_json(self, atributo_serializar="__expostos__"):
        """Representacao completa em JSON do objeto.
        """
        formata_nome = lambda nome: \
            nome[5:] if nome.startswith('href_') else nome
        def formata_valor(valor):
            if isinstance(valor, URIRef):
                return {'href': str(valor)}
            elif isinstance(valor, date) or \
                    isinstance(valor, time) or \
                    isinstance(valor, datetime):
                return valor.isoformat()
            elif isinstance(valor, Decimal):
                return "%0.2f" % valor
            else:
                return valor
        chaves = (formata_nome(n) for n in getattr(self,atributo_serializar))
        valores = (formata_valor(getattr(self, atr, None)) for atr in getattr(self,atributo_serializar))
        dados = dict(zip(chaves, valores))
        id = getattr(self, "id", None)
        if id:
            dados["id"] = id
        uri = getattr(self, "uri", None)
        if uri:
            dados["href"] = self.uri
        return dados
    def repr_json(self):
        """Representacao curta em JSON do objeto.
        """
        en = getattr(self, '__element_name__', self.__class__.__name__)
        dados = {en: {}}
        id = getattr(self, "id", None)
        if id:
            dados[en]["id"] = id
        uri = getattr(self, "uri", None)
        if uri:
            dados[en]["href"] = self.uri
        return dados
    def repr_xml(self):
        """Representacao curta em XML do objeto.
        """
        en = getattr(self, '__element_name__', self.__class__.__name__)
        return (E(en, {'href':self.uri}, (self.nome if getattr(self, 'nome', None) else tuple())))
