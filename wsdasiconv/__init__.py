# -*- coding: utf-8 -*-
"""
Módulo __init__.py da API de dados abertos do SICONV.
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

from pyramid.config import Configurator
from sqlalchemy import engine_from_config

__version__ = "0.2"

versao_api = '1'

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    from wsdasiconv.model import initialize_sql
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)
    config = Configurator(settings=settings)
    config.add_static_view('static', 'wsdasiconv:static')
    
    # consultas a recursos nao-informacionais (ver http-range-14)
    config.add_route('id', '/id/{classe}/{id}', view='wsdasiconv.webservice.redir_resource')
    # consulta a recursos informacionais
    config.add_route('dados/classe/id.formato', '/dados/{classe}/{id}.{formato}', view='wsdasiconv.webservice.detalhe_recurso')
    
    # esta rota de negociacao de conteudo HTTP so deve ser usada se as acima falharem
    config.add_route('dados/classe/id', '/dados/{classe}/{id}', view='wsdasiconv.webservice.conneg_dados')
    
    # consultas a chamadas da API
    config.add_route('consulta/metodo.formato',
        '/v' + versao_api + '/consulta/{metodo}.{formato}',
        view='wsdasiconv.webservice.consulta')
    
    # esta rota de negociacao de conteudo HTTP so deve ser usada se as acima falharem
    config.add_route('consulta/metodo',
        '/v' + versao_api + '/consulta/{metodo}',
        view='wsdasiconv.webservice.conneg_api')
    
    # views de documentacao da API
    config.add_route('consulta/',
        '/v' + versao_api + '/consulta/',
        view='wsdasiconv.webservice.Documentacao.lista_metodos')
    config.add_route('consulta.formato',
        '/v' + versao_api + '/consulta.{formato}',
        view='wsdasiconv.webservice.Documentacao.lista_metodos')
    config.add_route('consulta',
        '/v' + versao_api + '/consulta',
        view='wsdasiconv.webservice.append_slash')
    
    # rotas de consultas para views com informacoes agregadas
    config.add_route('visao/relatorio.csv',
        '/v' + versao_api + '/visao/{dbview}.csv',
        view='wsdasiconv.webservice.view_relatorio')
    
    return config.make_wsgi_app()


