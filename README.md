Código da API de dados abertos do Sistema de Gestão de Convênios e Contratos
de Repasse (Siconv).

# API de Dados Abertos do Siconv

A API foi desenvolvida em 2011 para disponibilizar dados abertos do Siconv.

## Representational State Transfer (REST)

Tecnicamente, ela segue os princípios
[REST](https://en.wikipedia.org/wiki/Representational_state_transfer).
Especificamente, cada recurso apresenta hyperlinks para os recursos com os
quais se relaciona, implementando o princípio
[HATEOAS](https://en.wikipedia.org/wiki/HATEOAS) (Hypermedia as the Engine of
Application State).

Os recursos da API estão disponíveis os seguintes formatos (ou, para usar o
termo técnico usado na [RFC 2616](https://tools.ietf.org/html/rfc2616), a qual
define o protocolo HTTP/1.1, as seguintes *representações*):

* HTML (navegável em um browser)
* XML
* JSON
* CSV
* RDF/XML
* RDF/Turtle

Para cada método da API, há um recurso de formato neutro, que não possui uma
representação (formato) canônica, mas serve como a URI que identifica o objeto
conceitual (por exemplo, um convênio). Este, quando requisitado, redireciona a
outro recurso que tem uma representação (formato) único, indicado também por
uma "extensão" em sua URI. O redirecionamento é o resultado do processo padrão
de Content Negotiation definido no protocolo HTTP/1.1. Isto é, depende dos
valores fornecidos pelo cliente no cabeçalho "Accept" da requisição.

Se o cliente indicar que suporta essa funcionalidade nos cabeçalhos de
requisição (é o caso da maior parte dos browsers, por exemplo), a resposta
também poderá ser compactada, de forma transparente, no formato gzip, assim
economizando banda.

Para as consultas coletivas, os resultados são paginados. Por padrão, cada
página tem até 500 registros, mas esse parâmetro é configurável (vide
definições de métodos e filtros, abaixo). Caso haja mais resultados que os
disponíveis na página, é fornecido link para a consulta da próxima página.

## Banco de dados e definição de esquemas

A API utiliza a bibloteca [SQL Alchemy](http://www.sqlalchemy.org/). Assim, é
compatível com todos os SGBDs suportados por essa plataforma.

A definição do esquema do banco de dados é feita por meio das classes
relacionadas no módulo `model.py`. Todas as classes que representam entidades
do modelo de negócios devem herdar da classe `Base`.

Seguem algumas propriedades especiais de uma tal clase:

* `__table_name__`: nome da tabela no banco de dados
* `__slug_item__`: nome do
  "[slug](https://en.wikipedia.org/wiki/Semantic_URL#Slug)"
  (i.e., parte da URL do método que indica o tipo de objeto consultado),
  para a consulta individual de um objeto específico do tipo
* `__slug_lista__`: nome do "slug" para a consulta coletiva, que retorna
  uma série de objetos do mesmo tipo
* `__expostos__`: lista com os nomes dos atributos que são expostos na
  consulta individual do item
* `__resumidos__`: lista com os nomes dos atributos que aparecem em cada item
  da consulta coletiva (recomenda-se que seja um subconjunto do atributo
  `__expostos__`)
* `__class_uri__`: este atributo, opcional, contém a URI da classe, na web
  semântica, à qual pertencerão os objetos dessa classe. Sugere-se pesquisar
  ontologias existentes no [Schema.org](https://schema.org/) e no
  [Linked Open Vocabularies](http://lov.okfn.org/)
* `__rdf_prop__`: atributo opcional, para uso dos formatos da web semântica,
  contendo um dicionário em que:
  * as chaves são as propriedades existentes na classe. Se estiverem definidas
    e relacionadas nos atributos `__expostos__` ou `__resumidos__`, conforme o
    caso, e o formato solicitado for baseado em RDF, serão geradas as triplas
    associadas a essa propriedade da classe;
  * os valores são funções que recebem como parâmetro o próprio objeto da
    classe e podem retornar uma lista ou tupla de triplas a serem retornadas,
    ou `None`
* `nome`: essa propriedade é utilizada para gerar os textos de hyperlinks,
  quando for formado um hyperlink para a consulta desse objeto
* `href_xxx`: propriedades com o prefixo `href_` criam hyperlinks para a
  consulta de objetos de outra classe, que se relaciona com essa, filtrando
  pela chave deste objeto no relacionamento considerado (ex.: num objeto da
  classe `Municipios`, `href_proponentes` retorna a URL de uma consulta a todos
  os proponentes deste municipio)

## Definições dos métodos e filtros

As definições dos métodos da API e os filtros suportados são feitas no módulo
`webservice.py`. Cada método definido deve herdar da classe `APIMethod`.

Propriedades especiais:

* `model_class`: o valor dessa propriedade é(são) a(s) classe(s) modelo
  utilizada(s) na consulta, importadas do módulo `model.py`
* `parameters`: dicionário em que:
  * as chaves são o nome de um parâmtero da
    [query string](https://en.wikipedia.org/wiki/Query_string) do método.
    Também são normalmente associados ao nome da propriedade da classe
    que será comparada ou consultada.
  * os valores são dicionários, onde:
    * `name`: string que descreve o parâmetro
    * `type`: o tipo Python que será usado para validar o parâmtro
    * `comparison`: indica o tipo de comparação. Estão disponíveis:
      * `=`: o valor informado na query string corresponde exatamente ao valor
        do atributo no banco de dados
      * `like`: texto da propriedade consultada contém o valor informado na
        query string. Como o "LIKE" no SQL
      * `ilike`: como o `like`, mas insensível a maiúsculas. Como o "ILIKE"
        no SQL
      * `<`, `<=`, `>=`, `>`: compara se o valor informado na query string
        se compara sendo menor, menor ou igual, maior ou igual, ou maior que
        o valor do atributo no banco de dados
* `max_results`: quantidade máxima de resultados por página da consulta
  (por padrão, 500)

## Documentação da API

A documentação para usuários da API é gerada automaticamente, baseada nas
[docstrings](https://en.wikipedia.org/wiki/Docstring) e outras informações
das classes. A documentação automática será montada na URL `/versao/consulta`.

## Instalação

 Crie um ambiente virtual para o Python

  `virtualenv --no-site-packages [diretorio-do-ambiente]`

 Ative o ambiente virtual

  `source [diretorio-do-ambiente]/bin/activate`

 Execute a instalação do pacote e de suas dependências
 (obs.: requer conexão com a internet para baixar os pacotes)

  `python setup.py install`
  
  Para ter dados a experimentar, sugere-se carregar o dump do banco de dados
  da API disponibilizado pelo Minisério do Planejamento:
  
  http://repositorio.dados.gov.br/economia-financas/encargos-financeiros/transferencias-financeiras/API_siconv_140515.zip
  
  Obs.: os dados desse dump não estão atualizados.

## Configuração

Edite o arquivo `production.ini` para configurar os parâmetros do banco de
dados, na seção [sqlalchemy]. Estão disponíveis como exemplos nos arquivos
`development.exemplo.ini` e `production.exemplo.ini`.

## Licença

Affero GPL versão 3

