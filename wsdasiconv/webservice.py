# -*- encoding: utf-8 -*-
'''
Módulo webservice.py da API de dados abertos do SICONV.
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
'''

import copy

from decimal import Decimal

from webob import Response
from webob.exc import HTTPOk, HTTPBadRequest, HTTPNotFound
from webob.exc import HTTPFound, HTTPSeeOther, HTTPMovedPermanently

# XML (amara)
from amara.writers.struct import structwriter, ROOT, E, E_CURSOR
from StringIO import StringIO as sio

# RDF
from rdflib.graph import ConjunctiveGraph
from rdflib.term import URIRef, Literal
from rdflib.namespace import Namespace, RDF

# sqlalchemy
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import joinedload, joinedload_all, subqueryload, aliased
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy import and_, or_
from sqlalchemy.engine import reflection

# geoalchemy
from geoalchemy import WKTSpatialElement, DBSpatialElement

# configuracao
from __init__ import versao_api
from namespace import URI_BASE
from model import RegistroWS
from model import Base

# serializadores
from serializer import Aggregator, HTMLAggregator, XMLAggregator
from serializer import JSONAggregator, CSVAggregator
from serializer import RDFAggregator

# sessao db
from model import Session

from model import date

# excecoes
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

# mapeia o codigo do formato para o content-type
format_contenttype = {
    'html': 'text/html',
    'xml': 'application/xml',
    'csv': 'text/csv',
    'json': 'application/json',
    'rdf': 'application/rdf+xml',
    'ttl': 'text/turtle',
    'n3': 'text/n3',
    'nt': 'text/plain',
    }

# mapeia o codigo do formato para o metodo de serializacao do objeto
format_ms = {
    'html': ('to_html', [], {}),
    'xml': ('to_xml', [], {}),
    'csv': ('to_csv', [], {}),
    'json': ('to_json', [], {}),
    'rdf': ('to_rdf', [], {'format': 'rdf/xml'}),
    'ttl': ('to_rdf', [], {'format': 'n3'}),
    'n3': ('to_rdf', [], {'format': 'n3'}),
    'nt': ('to_rdf', [], {'format': 'nt'}),
}
# mapeia o codigo do formato para a classe agregadora
format_ag = {
    'html': HTMLAggregator,
    'xml': XMLAggregator,
    'json': JSONAggregator,
    'csv': CSVAggregator,
    'rdf': RDFAggregator,
    'ttl': RDFAggregator,
    'n3': RDFAggregator,
    'nt': RDFAggregator,
}

# funcoes auxiliares

class classproperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()

def append_slash(request):
    '''
    Redireciona a requisicao acrescentando uma barra ao final.
    '''
    url = request.path_url + "/"
    if request.params:
        url+= "?" + "&".join(k + "=" + v for k, v in request.params.items())
    return HTTPMovedPermanently(location=url)

def not_found(mensagem=u"O endereço solicitado não foi encontrado.</p>"):
    texto = u"<h1>404 - Não encontrado</h1>\n<p>%s</p>" % mensagem
    response = HTTPNotFound(body=texto)
    response.content_type = "text/html;charset=utf-8"
    return response

def prepare_response(format):
    '''
    Prepara um objeto resposta no formato especificado.
    
    req: objeto de requisicao http
    format: codigo do formato, chave no dicionario para obter o content-type
    '''
    response=Response()
    response.content_type = format_contenttype[format]
    # Cross-Origin Resource Sharing (CORS)
    response.headers.add('Access-Control-Allow-Origin','*')
    # Indica para os caches que a resposta pode ou não ser compactada
    response.headers.add('Vary','Accept-Encoding')
    # Cache
    response.cache_control.public = True
    # as atualizacoes sao feitas na madrugada, entao o cache deve
    # expirar as 2:00 do dia seguinte
    from datetime import datetime, timedelta, time
    dia_a_mais = int(bool(datetime.now().hour >= 3))
    d = datetime.combine(datetime.today()+timedelta(dia_a_mais), time(3,0))
    response.expires = d
    return response

def finalize_response(req, res):
    '''
    Finaliza o objeto de resposta http antes de envia-la.
    '''
    # Calcula o hash para o cache com e-tag
    res.md5_etag()
    if getattr(req, 'if_none_match', None) and res.etag == req.if_none_match:
        res.body = None
        # retornar 304
        res.status = "304 Not modified"
    elif 'gzip' in req.accept_encoding:
        res.encode_content(lazy=False)
    return res

def serialize(obj, formato):
    '''
    Chama o metodo de serializacao apropriado para o objeto.
    '''
    return getattr(obj, format_ms[formato][0], repr)(**format_ms[formato][2])

# views auxiliares

def redir_doc(request):
    '''
    Redireciona para a documentacao.
    A intencao e' que um acesso na raiz do sitio redirecione o usuario para
    a documentacao.
    '''
    return HTTPSeeOther(location="/doc/")

def classes_modelo():
    from inspect import isclass
    import model
    for nome in dir(model):
        obj = getattr(model, nome)
        if isclass(obj) and issubclass(obj, model.Base) and \
                obj.__name__ != model.Base.__name__:
            yield(obj)

classes_suportadas = dict((cls.__slug_item__, cls) for cls in classes_modelo())

def redir_resource(request):
    '''
    Redireciona a requisicao para um documento que contenha informacoes sobre
    o recurso nao-informacional (ver resolucao http-range-14 do grupo TAG do W3C).
    http://www.w3.org/2001/tag/doc/httpRange-14/HttpRange-14.html
    '''
    
    # prepara os parametros
    cls = request.matchdict['classe']
    id = request.matchdict['id']
    if cls not in classes_suportadas.keys():
        return not_found()
    else:
        return HTTPSeeOther(location=request.application_url + "/dados/%(classe)s/%(id)s" % request.matchdict)

def conneg_dados(request):
    '''
    Realiza negociacao de conteudo HTTP e redireciona para o formato desejado.
    '''
    # prepara os parametros
    cls = request.matchdict['classe']
    id = request.matchdict['id']
    # troca a ordem de prioridade do text/html
    content_types = format_contenttype.values()
    content_types.remove('text/html')
    content_types.insert(0, 'text/html')
    # resolve qual o melhor content-type de acordo com o processo de conneg
    best_content_type = request.accept.best_match(content_types)
    format_dict = dict((v, k) for k, v in format_contenttype.items())
    params = request.matchdict
    params.update({'format': format_dict[best_content_type]})
    url = request.application_url+"/dados/%(classe)s/%(id)s.%(format)s" % params
    
    if cls not in classes_suportadas.keys():
        return not_found()
    else:
        response = HTTPFound(location=url)
        # importante: nao se deve permitir o cache sem considerar os formatos
        # aceitos pelo cliente. Por exemplo, se um Bot acessando a aplicacao
        # foi redirecionado para a versao .xml, isso nao deve ser cacheado
        # para todas as requisicoes, pois um browser deve receber html
        response.headers.add('Vary','Accept')
        return response

# classes do webservice

class Resource(object):
    """Representa um recurso da web.
    """
    
    request = None
    response = None
    atributos_serializar = None
    
    def __init__(self, request):
        self.request = request
    
    # metodos auxiliares
    def append_slash(self):
        '''
        Redireciona a requisicao acrescentando uma barra ao final.
        '''
        request = self.request
        url = request.path_url + "/"
        if request.params:
            url+= "?" + "&".join(k + "=" + v for k, v in request.params.items())
        self.response = HTTPMovedPermanently(location=url)
        return self.response
    
    def not_found(self, mensagem=u"O endereço solicitado não foi encontrado."):
        texto = u"<h1>404 - Não encontrado</h1>\n<p>%s</p>" % mensagem
        response = HTTPNotFound(body=texto)
        response.content_type = "text/html;charset=utf-8"
        self.response = response
        return self.response
    
    def prepare_response(self, format):
        '''
        Prepara um objeto resposta no formato especificado.
        
        req: objeto de requisicao http
        format: codigo do formato, chave no dicionario para obter o content-type
        '''
        response=Response()
        response.content_type = format_contenttype[format]
        # Cross-Origin Resource Sharing (CORS)
        response.headers.add('Access-Control-Allow-Origin','*')
        # Indica para os caches que a resposta pode ou não ser compactada
        response.headers.add('Vary','Accept-Encoding')
        # Cache
        response.cache_control.public = True
        # as atualizacoes sao feitas na madrugada, entao o cache deve
        # expirar as 2:00 do dia seguinte
        from datetime import datetime, timedelta, time
        dia_a_mais = int(bool(datetime.now().hour >= 3))
        d = datetime.combine(datetime.today()+timedelta(dia_a_mais), time(3,0))
        response.expires = d
        self.response = response
        return self.response
    
    def finalize_response(self):
        '''
        Finaliza o objeto de resposta http antes de envia-la.
        '''
        req, res = self.request, self.response
        # Calcula o hash para o cache com e-tag
        res.md5_etag()
        if getattr(req, 'if_none_match', None) and res.etag == req.if_none_match:
            res.body = None
            # retornar 304
            res.status = "304 Not modified"
        elif 'gzip' in req.accept_encoding:
            res.encode_content(lazy=False)
        return self.response
    
    @staticmethod
    def serialize(obj, formato, atributo_serializar):
        '''
        Chama o metodo de serializacao apropriado para o objeto.
        '''
        params = format_ms[formato][2]
        params ["atributo_serializar"] = atributo_serializar
        return getattr(obj, format_ms[formato][0], lambda **p: repr)(**params)
    
    def redir_doc(self):
        '''
        Redireciona para a documentacao.
        A intencao e' que um acesso na raiz do sitio redirecione o usuario para
        a documentacao.
        '''
        self.response = HTTPSeeOther(location="/doc/")
        return self.response
    
    def output(self):
        # retorna o objeto
        if self.response is None:
            self.response = self.prepare_response(self.formato)
            if self.result is None:
                self.response = not_found(u"Recurso não encontrado.")
                return self.response
            output = Resource.serialize(self.result, self.formato, self.atributos_serializar)
            if isinstance(output, str):
                output = output.decode('utf-8')
            self.response.text = output
            response = self.finalize_response()
        return response

class LinkedDataResource(Resource):
    """Representa um recurso linked data.
    
    Os recursos linked data se dividem em
    
    * Recursos informacionais (documentos)
    * Recursos nao informacionais

    Veja: http://www.w3.org/TR/cooluris/
    """
    
    atributos_serializar = "__expostos__"
    
    model_class = None
    
    def __init__(self, model_class, *args, **kw):
        super(LinkedDataResource, self).__init__(*args, **kw)
        if not issubclass(model_class, Base):
            raise ValueError("A classe informada deve ser do SQLAchemy")
        self.model_class = model_class
        self.read_parameters()
        self.query()
    
    def read_parameters(self):
        # prepara os parametros
        request = self.request
        self.id = request.matchdict['id']
        self.formato = request.matchdict['formato']
        if self.formato not in format_contenttype.keys():
            self.response = self.not_found(u"Formato não suportado: %s." % formato)
            return self.response
    
    def query(self):
        # consulta o objeto
        if self.model_class is None:
            raise ValueError("A classe do modelo representada no recurso nao esta definida.")
        session = Session()
        try:
            primary_keys = [key.name for key in self.model_class.__table__.primary_key]
            query = session.query(self.model_class)
            ids = self.id.split(",")
            if len(ids) != len(primary_keys):
                # quantidade de chaves passadas no id difere do esquema
                raise NoResultFound
            for n, pk in enumerate(primary_keys):
                query = query.filter(
                    getattr(self.model_class, pk) == ids[n]
                )
            self.result = query.one()
        except (MultipleResultsFound, NoResultFound):
            session.close()
            self.result = None
        # nao fechar a sessao para permitr lazy loading
        self.session = session
        # session.close()
        return self.result
    
    def output(self):
        
        output = super(LinkedDataResource, self).output()
        # fecha a sessao apos a serializacao para permitir o lazy loading
        self.session.close()
        return output
    
    def redir_resource(self):
        '''
        Redireciona a requisicao para um documento que contenha informacoes sobre
        o recurso nao-informacional (ver resolucao http-range-14 do grupo TAG do W3C).
        http://www.w3.org/2001/tag/doc/httpRange-14/HttpRange-14.html
        '''
        request = self.request
        # prepara os parametros
        cls = request.matchdict['classe']
        id = request.matchdict['id']
        if cls not in classes_suportadas.keys():
            self.response = self.not_found()
            return self.response
        else:
            self.response = HTTPSeeOther(location=request.application_url + "/dados/%(classe)s/%(id)s" % request.matchdict)
            return self.response
    
    def conneg(self):
        '''
        Realiza negociacao de conteudo HTTP e redireciona para o formato desejado.
        '''
        request = self.request
        # prepara os parametros
        cls = request.matchdict['classe']
        id = request.matchdict['id']
        best_content_type = request.accept.best_match(format_contenttype.values())
        format_dict = dict((v, k) for k, v in format_contenttype.items())
        params = request.matchdict
        params.update({'format': format_dict[best_content_type]})
        url = request.application_url+"/dados/%(classe)s/%(id)s.%(format)s" % params
        
        if cls not in classes_suportadas.keys():
            self.response = self.not_found()
            return self.response
        else:
            self.response = HTTPFound(location=url)
            # variar o cache conforme o cabecalho Accept para nao cachear
            # sempre o mesmo formato
            response.headers['Vary'] = 'Accept'
            return self.response

class APIMethod(Resource):
    """Representa um metodo de uma API.
    
    Um metodo possui parametros de consulta, que podem ser ou nao
    filtros para os dados.
    """

    atributos_serializar = "__resumidos__"
    __expostos__ = __resumidos__ = set([
        'id', 'slug', 'name',
        'description',
        'max_results'
    ])
    
    id = "default_method"   # identificador do metodo para meta-descricao
    slug = "resources"      # slug e a parte legivel da URL
    name = u"Método"        # nome legivel do metodo
    description = u"""Um método do webservice.
    """                     # descricao mais longa
    parameters = {
        "param1": {
            "name": "Example Parameter 1 (string)", # nome longo
            "type": unicode,                # tipo (classe) do parametro
            "validator": lambda self, v: True,    # funcao validadora
            "transform": lambda self, v: v,       # funcao de transformacao
            "comparison": "ilike",          # tipo de comparacao
            "optional": True,               # se o valor e opcional
            "query_attribute": "atr1",      # atributo da classe a consultar
        },
        "param2": {
            "name": "Example Parameter 2 (integer)",
            "type": int,
            "range": {
                "min": 0,
                "max": 1,
            },
            "validator": lambda self, v: True,
            "transform": lambda self, v: v,
            "comparison": "=",
            "optional": True,
            # o atributo a consultar pode pertencer a uma classe relacionada
            "query_attribute": "related.atr2",
        },
    }
    
    max_results = 500
    
    # template para a visualizacao em html
    html_template = 'templates/lista.pt'
    
    # importante: esta e' a classe principal a ser consultada
    model_class = Base
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = []
    subquery_atrs = []
    
    def __init__(self, *args, **kw):
        super(APIMethod, self).__init__(*args, **kw)
        self.parameters = copy.deepcopy(self.__class__.parameters)
        self.offset = 0
        self.initialize()
        if self.response is None:
            # se ha resposta (self.response is not None), e' porque foi
            # levantada uma excecao e a resposta contem o codigo HTTP e
            # menagem apropriada.
            # Caso contrario (self.response is None), nada foi colocado
            # na resposta e pode ser realizada a consulta.
            self.query()
        else:
            self.result = None
    
    def initialize(self):
        try:
            self.read_parameters()
        except ValueError, e:
            self.response = HTTPBadRequest(
                body=u"<h1>Solicitação mal formatada</h1><p><strong>Erro:</strong> %s</p>." % \
                    e,
                content_type="text/html")
    
    def read_parameters(self):
        "Processa parametros de consulta"
        # parametros gerais
        self.formato = self.request.matchdict['formato']
        try:
            self.offset = int(self.request.params.get('offset', 0))
        except ValueError:
            self.offset = 0
        # verifica se os parametros especificados existem
        for param in self.request.params.keys():
            if param not in self.parameters.keys() and param != 'offset':
                raise ValueError(u"O parâmetro especificado '%s' é desconhecido." % param)
        # parametros especificos
        for param in self.parameters.keys():
            value = self.request.params.get(param, None)
            # se o valor foi passado na consulta
            if value is not None:
                # faz alguma transformacao previa
                if "pre_transform" in self.parameters[param]:
                    value = self.parameters[param]["pre_transform"](self, value)
                # verifica o tipo do parametro
                if "tipo" in self.parameters[param]:
                    try:
                        # cast que passa a string recebida como parametro 
                        # para o construtor da classe especificada em ["tipo"]
                        value = self.parameters["tipo"](value)
                    except ValueError:
                        raise ValueError(u"O valor passado ao parâmetro '%s' não é do tipo '%s': '%s'" % \
                            (param, self.parameters[param]["tipo"], value))
                # valida o valor do parametro, se houver validador
                if "validator" in self.parameters[param] and not self.parameters[param]["validator"](self, value):
                    raise ValueError (u"Valor inválido passado ao parâmetro '%s': %s" % \
                        (param, value))
                # verifica o contra-dominio (minimo e maximo), se houver
                if "range" in self.parameters[param]:
                    min = self.parameters[param]["range"].get("min", None)
                    max = self.parameters[param]["range"].get("max", None)
                    if min is not None:
                        if value < min:
                            raise ValueError(u"O valor passado como parâmetro '%s' é menor que o mínimo aceitável (%s): %s." % \
                                (param, str(min), str(value)))
                        if value > max:
                            raise ValueError(u"O valor passado como parâmetro '%s' é maior que o máximo aceitável (%s): %s." % \
                                (param, str(max), str(value)))
                # faz a transformacao necessaria
                if "transform" in self.parameters[param]:
                    value = self.parameters[param]["transform"](self, value)
                # todo o processamento do parametro foi feito
            else:
                # nao foi passado o valor para esse parametro na consulta
                if not self.parameters[param].get("optional", True):
                    raise ValueError(u"Faltou especificar o parametro '%s', que é obrigatório." % param)
            # armazena o valor.
            self.parameters[param]["value"] = value
        # registra url da consulta
        params = dict(self.request.params)
        self.url = self.request.route_url('consulta/metodo.formato',
            metodo=self.slug,
            formato=self.formato, _query=params)
    
    def query(self):
        # prepara a sessao
        session = Session()
        
        q = session.query(self.model_class)
        
        # atributos que deverao ser precarregados
        for atr in self.preloaded_atrs:
            q = q.options(joinedload(getattr(self.model_class, atr)))
        # atributos que deverao ser carregados como subqueries
        for atr in self.subquery_atrs:
            q = q.options(subqueryload(getattr(self.model_class, atr)))
        
        # filtra por cada parametro
        for param in (key for key, dic in self.parameters.items() if dic.get("value", None) is not None):
            # verifica qual atributo consultar
            atr = self.parameters[param].get("query_attribute", param)
            steps = atr.split(".") # cadeia de atributos
            next_class = self.model_class
            alias = next_class # duck typing a ser usado nos filtros abaixo
            for step in steps:
                if not isinstance(getattr(next_class,step).property, RelationshipProperty):
                    break
                next_class = getattr(next_class, step).property.mapper.class_
                # gera um alias para a tabela na consulta
                alias = aliased(next_class, name="__".join(
                    (next_class.__tablename__,param)
                ))
                q = q.join(alias)
            value = self.parameters[param]["value"]
            # Se o parametro foi especificado, ele participa da consulta.
            # A variavel alias pode ser o alias da ultima tabela que entrou
            # no join, ou a tabela original caso não tenha sido feito join.
            if self.parameters[param]["comparison"] == "=":
                q = q.filter(getattr(alias,steps[-1])==value)
            elif self.parameters[param]["comparison"] == "ilike":
                q = q.filter(getattr(alias,steps[-1]).ilike("%%%s%%" % value))
            elif self.parameters[param]["comparison"] == "<=":
                q = q.filter(getattr(alias,steps[-1]) <= value)
            elif self.parameters[param]["comparison"] == ">=":
                q = q.filter(getattr(alias,steps[-1]) >= value)
            elif self.parameters[param]["comparison"] == "<":
                q = q.filter(getattr(alias,steps[-1]) < value)
            elif self.parameters[param]["comparison"] == ">":
                q = q.filter(getattr(alias,steps[-1]) > value)
        
        # ordenacao dos resultados
        # ordena pela chave primaria
        primary_key = (key.name for key in self.model_class.__table__.primary_key).next()
        q = q.order_by(getattr(self.model_class,primary_key))
        
        # paginacao dos resultados
        self.total_registros = q.count()
        q = q.limit(self.max_results)
        if self.offset:
            q = q.offset(self.offset)
        
        try:
            things = q.all()
        except NoResultFound:
            things = None
        self.session = session
        
        # links para paginacao
        geral_url = self.url
        atual_url = ""
        prox_url = ""
        params = dict(self.request.params)
        params['offset'] = "%d" % (self.offset)
        atual_url = self.url
        if self.offset + self.max_results < self.total_registros:
            params['offset'] = "%d" % (self.offset + self.max_results)
            prox_url = self.request.route_url('consulta/metodo.formato',
                metodo=self.slug,
                formato=self.formato, _query=params)
        self.dataset_split = {
            'dataset_url': geral_url,
            'current_url': atual_url,
            'current_offset': self.offset,
            'split_size': self.max_results,
            'next_url': prox_url,
        }
        
        self.result = things
    
    def conneg(self):
        '''
        Realiza negociacao de conteudo HTTP e redireciona para o formato desejado.
        '''
        request = self.request
        metodo = request.matchdict['metodo']
        formato = ''
        if '.' in metodo:
            metodo, formato = metodo.split('.')
        if isinstance(metodo, unicode):
            metodo = metodo.encode('utf-8')
        metodos_suportados = [m.path.split('/')[-1] for m in ws.metodos]
        if metodo in metodos_suportados:
            if not formato:
                # conneg
                best_content_type = request.accept.best_match(format_contenttype.values())
                format_dict = dict((v, k) for k, v in format_contenttype.items())
                formato = format_dict[best_content_type]
                url = request.path_url + "." + formato
                if request.params:
                    url+= "?" + "&".join(k + "=" + v for k, v in request.params.items())
                self.response = HTTPFound(location=url)
                # variar a resposta para cache conforme o cabecalho Accept
                response.headers['Vary'] = 'Accept'
                return self.response
            else:
                self.response = self.not_found(u"Rota não encontrada para o método: %s" % metodo)
                return self.response
        else:
            self.response = self.not_found(u"Método não suportado: %s" % metodo)
            return self.response
    
    def output(self):
        # retorna o objeto
        
        if self.response is None:
            if self.result is None:
                self.response = not_found(u"Recurso não encontrado.")
                return self.response
            else:
                # serializa
                ag = format_ag[self.formato](self.slug,
                    atributo_serializar="__resumidos__",
                    total_registros=self.total_registros,
                    dataset_split=self.dataset_split,
                    template=self.html_template,
                    parameters=self.parameters,
                    request=self.request)
                #Chamada para o método na implementação do atributo_serializar
                #ag = format_ag[self.formato](self.slug, atributo_serializar="__resumidos__")
                for thing in self.result:
                    ag.add(thing)
                self.response = self.prepare_response(self.formato)
                output = ag.serialize(format=self.formato)
                if isinstance(output, str):
                    output = output.decode('utf-8')
                self.response.text = output
            # fecha a sessao
            self.session.close()
        self.response = self.finalize_response()
        return self.response
    
    # metodos da classe para serem usados quando da exposicao da lista de
    # metodos da API
    @classmethod
    def item_json(cls, atributo_serializar="__expostos__"):
        "Representacao em JSON do metodo da API"
        return dict((atr, getattr(cls, atr)) for atr in getattr(cls,atributo_serializar))
    # URI do documento que fala sobre a classe
    @classproperty
    @classmethod
    def doc_uri(cls):
        return URI_BASE+"v%s/consulta#%s" % (versao_api, cls.id)
    
    # slug do metodo de consulta, retornado em tempo de execucao
    @classproperty
    @classmethod
    def slug(cls):
        return cls.model_class.__slug_lista__

# views de consultas a API

class ConsultaMunicipios(APIMethod):
    """Metodo de consulta a municipios.
    """
    id = "consulta_municipios"
    name = u"Consulta Municípios"
    description = u"""Este método consulta todos os municípios, opcionalmente filtrados por
    nome ou uf.
    """
    
    def __init__(self, *args, **kw):
        # traz a lista dos estados
        from namespace import dbpedia_estados
        self.estados = [e.lower() for e in dbpedia_estados.keys()]
        super(ConsultaMunicipios, self).__init__(*args, **kw)
    
    parameters = {
        "uf": {
            "name": u"Unidade da Federação", # nome longo
            "type": str,                    # tipo (classe) do parametro
            "validator": lambda self, v: v in self.estados,
            "pre_transform": lambda self, v: v.lower().strip(),
            "transform": lambda self, v: v.upper(), # no banco sao maiusc.
            "comparison": "=",          # tipo de comparacao
            "query_attribute": "_uf",
        },
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Municipio
    model_class = Municipio

class ConsultaOrgaos(APIMethod):
    """Metodo de consulta a orgaos.
    """
    id = "consulta_orgaos"
    name = u"Consulta Orgaos"
    description = u"""Este método consulta todos os orgaos, opcionalmente filtrados por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Orgao
    model_class = Orgao
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = ['orgao_superior']


class ConsultaEsferasAdministrativas(APIMethod):
    """Metodo de consulta a esferas administrativas.
    """
    id = "consulta_esferas_administrativas"
    name = u"Consulta Esferas Administrativas"
    description = u"""Este método consulta todas as esferas administrativas, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import EsferaAdministrativa
    model_class = EsferaAdministrativa

class ConsultaNaturezasJuridicas(APIMethod):
    """Metodo de consulta a naturezas juridicas.
    """
    id = "consulta_naturezas_juridicas"
    name = u"Consulta Naturezas Jurídicas"
    description = u"""Este método consulta todas as naturezas jurídicas, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import NaturezaJuridica
    model_class = NaturezaJuridica
    
class ConsultaSituacoesPropostas(APIMethod):
    """Metodo de consulta a Situacoes Propostas.
    """
    id = "consulta_situacoes_propostas"
    name = u"Consulta Situacoes das Propostas"
    description = u"""Este método consulta todas as situações das propostas, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import SituacaoProposta
    model_class = SituacaoProposta

class ConsultaSituacoesConvenios(APIMethod):
    """Metodo de consulta a Situacoes de Convenios.
    """
    id = "consulta_situacoes_convenios"
    name = u"Consulta Situações dos Convênios"
    description = u"""Este método consulta todas as situações dos convênios, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import SituacaoConvenio
    model_class = SituacaoConvenio

class ConsultaSubsituacoesConvenios(APIMethod):
    """Metodo de consulta a Subsituacoes de Convenios.
    """
    id = "consulta_subsituacoes_convenios"
    name = u"Consulta Subsituações dos Convênios"
    description = u"""Este método consulta todas as subsituações dos convênios, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import SubsituacaoConvenio
    model_class = SubsituacaoConvenio

class ConsultaSituacoesPublicacaoConvenios(APIMethod):
    """Metodo de consulta a Situacoes de Publicacao de Convenios.
    """
    id = "consulta_situacoes_publicacao_convenios"
    name = u"Consulta Situações de Publicação dos Convênios"
    description = u"""Este método consulta todas as situações de publicação dos convênios, opcionalmente filtradas por
    nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import SituacaoPublicacaoConvenio
    model_class = SituacaoPublicacaoConvenio

class ConsultaProponentes(APIMethod):
    """Metodo de consulta a proponentes.
    """
    id = "consulta_proponentes"
    name = u"Consulta Proponentes"
    description = u"""Este método consulta todos os proponentes, opcionalmente filtrados por
    nome, id ou uf do município, ou CPF do responsável.
    """
    
    def __init__(self, *args, **kw):
        # traz a lista dos estados
        from namespace import dbpedia_estados
        self.estados = [e.lower() for e in dbpedia_estados.keys()]
        super(ConsultaProponentes, self).__init__(*args, **kw)
    
    parameters = {
        "uf": {
            "name": u"Unidade da Federação do município", # nome longo
            "type": str,                    # tipo (classe) do parametro
            "validator": lambda self, v: v in self.estados,
            "pre_transform": lambda self, v: v.lower().strip(),
            "transform": lambda self, v: v.upper(), # no banco sao maiusc.
            "comparison": "=",          # tipo de comparacao
            "query_attribute": "municipio._uf"
        },
        "nome": {
            "name": u"Nome ou parte do nome do proponente",
            "type": unicode,
            "comparison": "ilike",
        },
        "nome_responsavel": {
            "name": u"Nome ou parte do nome do responsável pelo proponente",
            "type": unicode,
            "comparison": "ilike",
        },
        "id_municipio": {
            "name": u"Identificador do município",
            "type": int,
            "comparison": "=",
        },
        "id_responsavel": {
            "name": u"Id do Responsável",
            "type": unicode,
            "comparison": "=",
        },
        "id_natureza_juridica":{
            "name": u"Identificador da Natureza Jurídica",
            "type": int,
            "comparison":"=",
        },
        "id_esfera_administrativa":{
            "name": u"Identificador da Esfera Administrativa",
            "type": int,
            "comparison":"=",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Proponente
    model_class = Proponente
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = ['municipio', 'natureza_juridica', 'esfera_administrativa']

class ConsultaPropostas(APIMethod):
    """Metodo de consulta a propostas.
    """
    id = "consulta_propostas"
    name = u"Consulta Propostas"
    description = u"""Este método consulta todas as propostas, opcionalmente filtradas por
    uf ou id do proponente, ou CPF do responsável.
    """
    
    def __init__(self, *args, **kw):
        # traz a lista dos estados
        from namespace import dbpedia_estados
        self.estados = [e.lower() for e in dbpedia_estados.keys()]
        super(ConsultaPropostas, self).__init__(*args, **kw)
    
    parameters = {
        "uf": {
            "name": u"Unidade da Federação do município do proponente", # nome longo
            "type": str,                    # tipo (classe) do parametro
            "validator": lambda self, v: v in self.estados,
            "pre_transform": lambda self, v: v.lower().strip(),
            "transform": lambda self, v: v.upper(), # no banco sao maiusc.
            "comparison": "=",          # tipo de comparacao
            "query_attribute": "proponente.municipio._uf"
        },
        "id_programa": {
            "name": u"Identificador de um programa associado à proposta",
            "type": int,
            "comparison": "=",
            "query_attribute": "_programas.id_programa",
        },
        "id_proponente": {
            "name": u"Identificador do proponente",
            "type": int,
            "comparison": "=",
        },
        "id_responsavel": {
            "name": u"Id do Responsável pela instituição proponente",
            "type": unicode,
            "comparison": "=",
            "query_attribute": "proponente.id_responsavel",
        },
        "id_orgao_concedente": {
            "name": u"Identificador do órgão concedente",
            "type": int,
            "comparison": "=",
        },
        "id_situacao": {
            "name": u"Identificador da situação da proposta",
            "type": int,
            "comparison": "=",
        },
        "id_modalidade": {
            "name": u"Identificador da modalidade de proposta ou convênio",
            "type": int,
            "comparison": "=",
        },
        "id_pessoa_responsavel_pelo_concedente": {
            "name": u"Id do Responsável pela proposta",
            "type": unicode,
            "comparison": "=",
        },
        "id_pessoa_responsavel_pelo_envio": {
            "name": u"Id do Responsável pelo envio da proposta",
            "type": unicode,
            "comparison": "=",
        },
        "id_pessoa_responsavel_pelo_cadastramento": {
            "name": u"Id do Responsável pelo cadastramento da proposta",
            "type": unicode,
            "comparison": "=",
        },
}
    
    # importante: esta e' a classe principal a ser consultada
    from model import Proposta
    model_class = Proposta
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = ['proponente', '_situacao']

class ConsultaConvenios(APIMethod):
    """Metodo de consulta a convenios.
    """
    id = "consulta_convenios"
    name = u"Consulta Convênios"
    description = u"""Este método consulta todos os convênios, opcionalmente filtradas por
    uf ou id do proponente, ou CPF do responsável.
    """
    
    def __init__(self, *args, **kw):
        # traz a lista dos estados
        from namespace import dbpedia_estados
        self.estados = [e.lower() for e in dbpedia_estados.keys()]
        super(ConsultaConvenios, self).__init__(*args, **kw)
    
    parameters = {
        "uf": {
            "name": u"Unidade da Federação do município do proponente", # nome longo
            "type": str,                    # tipo (classe) do parametro
            "validator": lambda self, v: v in self.estados,
            "pre_transform": lambda self, v: v.lower().strip(),
            "transform": lambda self, v: v.upper(), # no banco sao maiusc.
            "comparison": "=",          # tipo de comparacao
            "query_attribute": "proponente.municipio._uf"
        },
        "id_programa": {
            "name": u"Identificador de um programa associado ao convênio",
            "type": int,
            "comparison": "=",
            "query_attribute": "_programas.id_programa",
        },
        "id_proponente": {
            "name": u"Identificador do proponente",
            "type": int,
            "comparison": "=",
        },
        "id_pessoa_responsavel_como_proponente": {
            "name": u"Id do Responsável pela instituição proponente",
            "type": unicode,
            "comparison": "=",
            "query_attribute": "proponente.id_responsavel",
        },
        "cpf_responsavel": {
            "name": u"CPF do Responsável pela instituição proponente",
            "type": unicode,
            "validator": lambda self, v: len(v) == 11,
            # coloca a mascara
            "transform": lambda self, v: u"***%s**" % v[3:9],
            "comparison": "=",
            "query_attribute": "proponente.pessoa_responsavel.cpf",
        },
        "id_orgao_concedente": {
            "name": u"Identificador do órgão concedente",
            "type": int,
            "comparison": "=",
        },
        "id_situacao": {
            "name": u"Identificador da situação da proposta",
            "type": int,
            "comparison": "=",
        },
        "id_modalidade": {
            "name": u"Identificador da modalidade de proposta ou convênio",
            "type": int,
            "comparison": "=",
        },
        "id_pessoa_responsavel_como_concedente": {
            "name": u"Id do Responsável pelo convênio",
            "type": unicode,
            "comparison": "=",
        },
        "cpf_pessoa_responsavel_como_concedente": {
            "name": u"Id do Responsável pelo convênio",
            "type": unicode,
            "validator": lambda self, v: len(v) == 11,
            # coloca a mascara
            "transform": lambda self, v: u"***%s**" % v[3:9],
            "comparison": "=",
            "query_attribute": "pessoa_responsavel_como_concedente.cpf",
        },
    }
    
    # template para a visualizacao em html
    html_template = 'templates/convenios.pt'
    
    # importante: esta e' a classe principal a ser consultada
    from model import Convenio
    model_class = Convenio
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = ['proponente', '_modalidade',
                      '_situacao', 'orgao_concedente']

class ConsultaProgramas(APIMethod):
    """Metodo de consulta a programas do Plano Plurianual (PPA).
    """
    id = "consulta_programas"
    name = u"Consulta Programas"
    description = u"""Este método consulta todos os programas, opcionalmente filtradas por
    uf ou nome.
    """
    
    def __init__(self, *args, **kw):
        # traz a lista dos estados
        from namespace import dbpedia_estados
        self.estados = [e.lower() for e in dbpedia_estados.keys()]
        super(ConsultaProgramas, self).__init__(*args, **kw)
    
    parameters = {
        "estados_habilitados": {
            "name": u"Unidades da Federação habilitadas a receber recursos do programa", # nome longo
            "type": str,                    # tipo (classe) do parametro
            "validator": lambda self, v: v in self.estados,
            "pre_transform": lambda self, v: v.lower().strip(),
            "transform": lambda self, v: v.upper(), # no banco sao maiusc.
            "comparison": "=",          # tipo de comparacao
            "query_attribute": "estados_habilitados.sigla",
        },
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
        "situacao": {
            "name": u"Situação do programa",
            "type": unicode,
            "comparison": "ilike",
        },
        "acao_orcamentaria": {
            "name": u"Código da ação Orçamentária",
            "type": unicode,
            "comparison": "=",
        },
##        "data_publicacao_dou": {
##            "name": u"Data de publicação no Diário Oficial da União",
##            "type": date,
##            "comparison": "=",
##        },
##        "data_publicacao_dou_min": {
##            "name": u"Data mínima de publicação no Diário Oficial da União",
##            "type": date,
##            "comparison": ">=",
##            "query_attribute": "data_publicacao_dou",
##        },
##            "data_publicacao_dou_max": {
##            "name": u"Data máxima de publicação no Diário Oficial da União",
##            "type": date,
##            "comparison": "<=",
##            "query_attribute": "data_publicacao_dou",
##        },
        "id_orgao_superior": {
            "name": u"id do órgão superior associado ao programa",
            "type": int,
            "comparison": "=",
        },
        "id_orgao_vinculado": {
            "name": u"id do órgão vinculado ao programa",
            "type": int,
            "comparison": "=",
        },
        "id_orgao_mandatario": {
            "name": u"id do órgão mandatário associado ao programa",
            "type": int,
            "comparison": "=",
        },
        "id_orgao_executor": {
            "name": u"id do órgão executor associado ao programa",
            "type": int,
            "comparison": "=",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Programa
    model_class = Programa
    
    # atributos que deverao ser pre-carregados
    #  (em geral, relacionamentos com outras classes no sqlalchemy)
    preloaded_atrs = ['atende_a', #'tipo_instrumento',
        'orgao_superior', 'orgao_mandatario', 'orgao_vinculado', 'orgao_executor',
        #'estados_habilitados']
        ]

class ConsultaModalidades(APIMethod):
    """Metodo de consulta a modalidades de propostas e convenios.
    """
    id = "consulta_modalidades"
    name = u"Consulta Modalidades de Propostas e Convênios"
    description = u"""Este método consulta todas as modalidades de propostas e
    convênios, opcionalmente filtradas por nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Modalidade
    model_class = Modalidade

class ConsultaPessoasResponsaveis(APIMethod):
    """Metodo de consulta a pessoas responsaveis por propostas iu convenios.
    """
    id = "consulta_pessoas_responsaveis"
    name = u"Consulta pessoas responsaveis por Propostas ou Convênios"
    description = u"""Este método consulta todas as pessoas responsáveis por
    propostas e convênios, opcionalmente filtradas por nome.
    """
    
    parameters = {
        "nome": {
            "name": u"Nome ou parte do nome",
            "type": unicode,
            "comparison": "ilike",
        },
        "cargo": {
            "name": u"Cargo ou parte do texto do cargo",
            "type": unicode,
            "comparison": "ilike",
        },
        "cpf": {
            "name": u"CPF da pessoa Responsável pelo convênio ou pela proposta",
            "type": unicode,
            "validator": lambda self, v: len(v) == 11,
            # coloca a mascara
            "transform": lambda self, v: u"***%s**" % v[3:9],
            "comparison": "=",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import PessoaResponsavel
    model_class = PessoaResponsavel

class ConsultaEmendas(APIMethod):
    """Metodo de consulta a emendas dos programas.
    """
    id = "consulta_emendas"
    name = u"Consulta emendas dos programas"
    description = u"""Este método consulta todas as emendas
    dos programas, opcionalmente filtradas por programa, por número e/ou por valor.
    """
    
    parameters = {
        "id_programa": {
            "name": u"Id do programa",
            "type": int,
            "comparison": "=",
        },
        "numero": {
            "name": u"número da emenda",
            "type": int,
            "comparison": "=",
        },
##        "valor_min": {
##            "name": u"valor mínimo da emenda",
##            "type": Decimal,
##            "comparison": ">=",
##            "range": {
##                "min": Decimal(0),
##            },
##        },
##        "valor_max": {
##            "name": u"valor mãximo da emenda",
##            "type": Decimal,
##            "comparison": "<=",
##            "range": {
##                "min": Decimal(0),
##            },
##        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Emenda
    model_class = Emenda

class ConsultaOrdensBancarias(APIMethod):
    """Metodo de consulta as ordens bancarias relacionadas aos convenios.
    """
    id = "consulta_ordens_bancarias"
    name = u"Consulta ordens bancarias"
    description = u"""Este método consulta todas as ordens bancárias
    relacionadas aos convênios, opcionalmente filtradas por programa,
    por número da OB, por convênio e/ou por valor.
    """
    
    parameters = {
        "id_convenio": {
            "name": u"Id do convenio",
            "type": int,
            "comparison": "=",
        },
        "numero": {
            "name": u"número da emenda",
            "type": int,
            "comparison": "=",
        },
##        "valor_min": {
##            "name": u"valor mínimo da emenda",
##            "type": Decimal,
##            "comparison": ">=",
##            "range": {
##                "min": Decimal(0),
##            },
##        },
##        "valor_max": {
##            "name": u"valor mãximo da emenda",
##            "type": Decimal,
##            "comparison": "<=",
##            "range": {
##                "min": Decimal(0),
##            },
##        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import OrdemBancaria
    model_class = OrdemBancaria

class ConsultaEspeciesEmpenho(APIMethod):
    """Metodo de consulta a especies de empenho.
    """
    id = "consulta_especies_empenho"
    name = u"Consulta espécies de empenho"
    description = u"""Este método consulta todas as espécies de
    empenho, filtrando por nome ou parte do nome.
    """
    
    parameters = {
        "descricao": {
            "name": u"Texto ou parte do texto",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import EspecieEmpenho
    model_class = EspecieEmpenho

class ConsultaEmpenhos(APIMethod):
    """Metodo de consulta a empenhos.
    """
    id = "consulta_empenhos"
    name = u"Consulta empenhos"
    description = u"""Este método consulta todos os empenhos,
    filtrando por número, convênio ou espécie.
    """
    
    parameters = {
        "numero": {
            "name": u"Número",
            "type": unicode,
            "comparison": "=",
        },
        "id_especie": {
            "name": u"Identificador da espécie de empenho",
            "type": int,
            "comparison": "=",
        },
        "id_convenio": {
            "name": u"Identificador do convênio",
            "type": int,
            "comparison": "=",
        },
        "id_proponente_favorecido": {
            "name": u"Identificador do proponente",
            "type": int,
            "comparison": "=",        
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import Empenho
    model_class = Empenho


class ConsultaAreasAtuacaoProponente(APIMethod):
    """Metodo de consulta a areas de atuacao do proponente.
    """
    id = "consulta_areas_atuacao_proponente"
    name = u"Consulta areas de atuacao"
    description = u"""Este método consulta todas as areas
    de atuacao dos proponentes, opcionalmente filtradas 
    por descrição ou parte da descrição.
    """
    
    parameters = {
        "descricao": {
            "name": u"Descrição",
            "type": unicode,
            "comparison": "ilike",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import AreaAtuacaoProponente
    model_class = AreaAtuacaoProponente

class ConsultaSubareasAtuacaoProponente(APIMethod):
    """Metodo de consulta a subareas de atuacao do proponente.
    """
    id = "consulta_subareas_atuacao_proponente"
    slug = "subareas_atuacao_proponente"
    name = u"Consulta subáreas de atuacao"
    description = u"""Este método consulta todas as subáreas
    de atuacao dos proponentes, opcionalmente filtradas 
    por descrição ou parte da descrição.
    """
    
    parameters = {
        "descricao": {
            "name": u"Descrição",
            "type": unicode,
            "comparison": "ilike",
        },
        "id_area": {
            "name": u"Identificador da área de atuação",
            "type": int,
            "comparison": "=",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import SubAreaAtuacaoProponente
    model_class = SubAreaAtuacaoProponente

class ConsultaHabilitacoesAreaAtuacao(APIMethod):
    """Metodo de consulta a habilitacoes em areas e subareas 
    de atuacao para proponentes.
    """
    id = "consulta_habilitacoes_area_atuacao"
    name = u"Habilitações em áreas de atuação"
    description = u"""Este método consulta todas as habilitações concedidas
    por órgãos a proponentes em áreas e subáreas de atuação, opcionalmente 
    filtradas por órgão, proponente ou área de atuação.
    """
    
    parameters = {
        "id_subarea": {
            "name": u"Identificador da subárea de atuação",
            "type": int,
            "comparison": "=",
        },
        "id_orgao": {
            "name": u"Identificador do órgão",
            "type": int,
            "comparison": "=",
        },
        "id_proponente": {
            "name": u"Identificador do proponente",
            "type": int,
            "comparison": "=",
        },
    }
    
    # importante: esta e' a classe principal a ser consultada
    from model import HabilitacaoAreaAtuacao
    model_class = HabilitacaoAreaAtuacao

consultas = [
    ConsultaMunicipios,
    ConsultaEsferasAdministrativas,
    ConsultaNaturezasJuridicas,
    ConsultaProponentes,
    ConsultaPropostas,
    ConsultaConvenios,
    ConsultaSituacoesPropostas,
    ConsultaSituacoesConvenios,
    ConsultaSubsituacoesConvenios,
    ConsultaSituacoesPublicacaoConvenios,
    ConsultaModalidades,
    ConsultaPessoasResponsaveis,
    ConsultaOrgaos,
    ConsultaProgramas,
    ConsultaEmendas,
    ConsultaOrdensBancarias,
    ConsultaEspeciesEmpenho,
    ConsultaEmpenhos,
    ConsultaAreasAtuacaoProponente,
    ConsultaSubareasAtuacaoProponente,
    ConsultaHabilitacoesAreaAtuacao,
]
metodos_suportados = dict((cls.model_class.__slug_lista__, cls) for cls in consultas)

class Documentacao(Resource):
    @staticmethod
    def lista_metodos(request):
        """
        Retorna a lista de metodos do webservice.
        """
        # verifica se o formato foi fornecido explicitamente
        format = request.matchdict.get('formato', None)
        
        if format is None:
            # realiza a negociacao de conteudo http
            best_content_type = request.accept.best_match(format_contenttype.values())
            format_dict = dict((v, k) for k, v in format_contenttype.items())
            format = format_dict[best_content_type]
            url = URI_BASE+"v%s/consulta.%s" % (versao_api, format)
            return HTTPFound(location=url)
        elif format not in format_contenttype.keys():
            response = not_found(u"Formato não suportado: %s." % formato)
            return response
        
        response = prepare_response(format)
        ag = format_ag[format]('metodos', atributo_serializar='__resumidos__',
            template='templates/doc.pt')
        # nao persistir as classes entre requisicoes
        #c = copy.deepcopy(consultas)
        for consulta in consultas:
            # leva o atributo da classe mae para a classe filha
            consulta.__resumidos__ = set(copy.deepcopy(consulta.__resumidos__))
            consulta.__resumidos__ -= set(('name','description'))
            consulta.__resumidos__ |= set((
                'nome',
                'descricao',
                'parametros',
                'href_uri',
                'href_doc_uri',
                'retorno',
            ))
            consulta.__resumidos__ = sorted(consulta.__resumidos__)
            consulta.nome = consulta.name
            consulta.descricao = consulta.description
            if isinstance(consulta.model_class.__resumidos__, set):
                consulta.retorno = sorted(consulta.model_class.__resumidos__)
            else:
                consulta.retorno = consulta.model_class.__resumidos__
            # ajusta a lista de parametros para ocultar a parte interna
            # ex.: funcoes de validacao
            consulta.parametros = dict([
                (param_id, {
                    'nome':spec['name'],
                    'tipo':spec['type'],
                    }) for param_id, spec in consulta.parameters.items()])
            consulta.href_uri = request.route_url('consulta/metodo',
                metodo=consulta.slug)
            consulta.uri = URI_BASE+"v%s/consulta/%s" % (versao_api,consulta.slug)
            consulta.href_doc_uri = consulta.doc_uri
            ag.add(consulta)
        ag.total_registros = len(ag.aggregator)
        ag.dataset_split = {
            'current_offset': 0,
            'split_size': ag.total_registros,
            'current_url': request.path_url,
        }
        output = ag.serialize(format=format)
        if isinstance(output, str):
            output = output.decode('utf-8')
        response.text = output
        # importante variar o cache conforme o formato aceito pelo cliente
        # (cabecalho 'Accept'), caso o formato nao tenha sido colocado
        # xplicitamente na url e decidido por negociacao de conteudo.
        # Caso contrario, um bot e um browser receberiam o mesmo conteudo
        response.headers['Vary'] = 'Accept,Accept-Encoding'
        return finalize_response(request, response)

def consulta(request):
    slug = request.matchdict['metodo']
    if slug in metodos_suportados.keys():
        return metodos_suportados[slug](request).output()
    else:
        return not_found(u"Método não suportado: %s" % slug)

# views para negociacao de conteudo e redirecionamento

def conneg_api(request):
    '''
    Realiza negociacao de conteudo HTTP e redireciona para o formato desejado.
    '''    
    metodo = request.matchdict['metodo']
    formato = ''
    if '.' in metodo:
        metodo, formato = metodo.split('.')
    if isinstance(metodo, unicode):
        metodo = metodo.encode('utf-8')
    if metodo in metodos_suportados:
        if not formato:
            # conneg
            best_content_type = request.accept.best_match(format_contenttype.values())
            format_dict = dict((v, k) for k, v in format_contenttype.items())
            formato = format_dict[best_content_type]
            url = request.path_url + "." + formato
            if request.params:
                url+= "?" + "&".join(k + "=" + v for k, v in request.params.items())
            response = HTTPFound(location=url)
            response.headers.add('Vary','Accept')
            return response
        else:
            return not_found(u"Rota não encontrada para o método: %s" % metodo)
    else:
        return not_found(u"Método não suportado: %s" % metodo)

# views que retornam dados sobre objetos unicos

def detalhe_recurso(request):
    '''
    Retorna dados sobre um recurso especifico em um formato especifico.
    '''
    classe_slug = request.matchdict['classe']
    if classe_slug in classes_suportadas.keys():
        return LinkedDataResource(classes_suportadas[classe_slug], request).output()
    else:
        return not_found(u"Método não suportado: %s" % classe_slug)

# views de visoes do banco de dados que podem ser usadas como exemplo de
# agregacao
# TODO: criar uma nova classe, diferente de APIMethod e LinkedDataResource,
# herdando de Resource, para representar essas visoes.
def view_relatorio(request):
    """
    Retorna o conteudo da visao do banco de dados de um relatorio.
    """
    from StringIO import StringIO as sio
    from sqlalchemy import Table
    from csv import writer as csv_writer
    view_name = request.matchdict['dbview']
    
    session = Session()
    inspector = reflection.Inspector.from_engine(Base.metadata.bind)
    view = Table(view_name, Base.metadata, autoload=True)
    columns = [column['name'] for column in inspector.get_columns(view, None)]
    results = [columns,]
    results.extend(session.query(view).all())
    s = sio()
    w = csv_writer(s)
    w.writerows(results)
    output = s.getvalue()
    s.close()
    response = prepare_response('csv')
    response.text = output.decode('utf-8')
    response = finalize_response(request,response)
    return response
