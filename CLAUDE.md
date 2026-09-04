# FastKit

Base multi-tenant para produtos que têm conta, assinatura, pagamento e conteúdo: tenants, usuários,
planos, direitos, benefícios, comércio, galeria, integrações com gateways e um site público indexável.

Um processo serve três superfícies, cada uma no seu caminho:

| Caminho | O que é | Onde vive |
| --- | --- | --- |
| `/` | o site público, renderizado no servidor | `templates/global/site/` |
| `/admin` | o painel administrativo, uma SPA Vue | `webapps/admin/` |
| `/api` | a API que os aplicativos consomem | as camadas do backend |

**Idioma:** código sempre em inglês, documentação interna sempre em pt-BR. Isso vale para
identificadores, comentários, docstrings e mensagens de commit de um lado, e para este arquivo do
outro. O `README.md` e a pasta `docs/` são a documentação **pública** e ficam em inglês.

---

## Como uma tarefa é feita aqui

**Este arquivo é o contrato.** O que está escrito aqui vale sem precisar ser repetido a cada pedido —
nem o padrão de código, nem o de formatação, nem o que nunca se cria, nem o que exige perguntar antes.
Um pedido novo diz **o que** fazer, e este arquivo diz **como**.

### O que se faz por padrão

| Regra | O que significa |
| --- | --- |
| **Editar o arquivo direto** | a mudança vai no arquivo que já existe, no lugar dela, e não num arquivo novo ao lado |
| **Entregar a versão final** | o que mudou, mudou: o formato antigo sai, e nada fica atrás dele por precaução |
| **Refatorar o que a mudança tocou** | se o desenho ficou errado, o certo é acertar o desenho, e não pendurar mais um caso especial nele |
| **Fazer quando fizer sentido** | uma mudança existe porque ela é necessária, nunca para mostrar trabalho — não sobra abstração, não sobra opção de configuração que ninguém pediu, não sobra teste de coisa óbvia |

### O que nunca se cria sem pedido

| O que | Por quê |
| --- | --- |
| arquivo `.md` novo | a documentação interna é este arquivo, e a pública é o `README.md` com a pasta `docs/` |
| migration | não existe Alembic aqui, e o schema sai do `Base.metadata` — ver [Sem migrations](#sem-migrations) |
| script solto, ferramenta de apoio, roteiro de verificação | nasce fora do repositório, roda, e some — ver [Um verificador é código, e ele erra](#um-verificador-é-código-e-ele-erra) |
| teste novo | a suíte cobre o comportamento, não a linha: um teste entra quando há **comportamento novo** a provar ou quando a cobertura do backend cairia de 100% |
| commit ou push | só quando pedido, e aí vai direto na `main` — ver [Commits](#commits) |

### O que exige perguntar antes, sempre

Produção, em qualquer forma: banco, bucket, credencial, chamada à API de produção, deploy, restart.
**Uma autorização vale para aquela ação e não abre a seguinte.** A regra inteira está em
[Nada em produção sem perguntar antes](#nada-em-produção-sem-perguntar-antes-é-regra-não-preferência).

Fora de produção, o mesmo vale para **falar com um terceiro**: um roteiro que exercite webhook,
checkout ou refresh contra o servidor local stuba o gateway ou não roda.

### A barra

**O código tem que parecer escrito por um engenheiro de produto experiente, e não por um gerador.**
Isso não é estilo, é o critério de aceitação: sem gambiarra, sem fallback genérico, sem `else` para um
caso que ninguém sabe o que é, sem comportamento implícito inesperado, sem código morto e sem uma
segunda forma de fazer a mesma coisa.

---

## Comandos

Sempre pelo `make`, e o `make` sempre pelo `uv`.

**Nenhuma receita chama uma ferramenta Python pelo nome.** O script de console que o instalador escreve
carrega um shebang com o caminho absoluto do interpretador de **quando o ambiente nasceu** — e uma
máquina que trocou de Python fica com duas árvores em `.venv/lib/`, cada comando lendo uma delas. O
sintoma engana: aparece como `ModuleNotFoundError` de uma dependência recém-declarada, exatamente como
se a declaração estivesse errada. `uv run` resolve o ambiente antes de chamar qualquer coisa, e
`tests/test_makefile.py` falha se uma receita chamar `python`, `pytest`, `ruff` ou `uvicorn` direto.

**E nenhuma receita roda npm da raiz.** Os dois projetos Node moram em `webapps/`, e um `npm install`
sem `--prefix` escreveria `node_modules` na raiz do repositório. A mesma trava cobra isso.

**E a CI chama a receita, em vez de escrever o comando de novo.** O único comando que quem desenvolve
roda é o do `Makefile`, então um pipeline que reescreve os mesmos passos mantém uma cópia que ninguém
exercita, e ela diverge sem nada acusar. A CI só diz o que uma receita não pode dizer por si — instalar
o próprio runtime, com `uv sync --frozen` e `npm ci` —, e a mesma trava falha se ela escrever um comando
que uma receita já declara.

**E ela não roda num commit que só toca a prosa.** O `paths-ignore` do pipeline nomeia `AGENTS.md`,
`CLAUDE.md`, `README.md`, `docs/` e `extras/`, porque corrigir uma frase não muda o que a aplicação faz.
**O que isso custa está escrito aqui:** a suíte lê justamente esses arquivos — número, símbolo, endereço
e frase são conferidos contra o código —, então uma trava de documentação quebrada é publicada com o
pipeline verde. Quem edita a prosa roda `make test` na máquina, que é o mesmo comando de sempre.

| Comando | O que faz |
| --- | --- |
| `make deps` | `uv sync` |
| `make deps-update` | atualiza o lock e sincroniza |
| `make format` | `ruff check --fix`, `ruff format` e o prettier dos dois front-ends |
| `make lint` | confere sem escrever |
| `make start` | sobe a API em `0.0.0.0:8000` com reload |
| `make test` | roda o pytest |
| `make test-cov` | pytest com cobertura, relatório em `htmlcov/` |
| `make migrate` | cria as tabelas que faltam |
| `make recreate-schema` | derruba tudo e recria, **perdendo os dados** |
| `make schema-diff` | compara o banco que a configuração aponta com o esquema do código, e escreve o DDL que falta |
| `make administrator` | cria `admin@admin.com` / `admin` fora de todo tenant, ou o que `USERNAME=… EMAIL=… PASSWORD=…` disser |
| `make seed` | recria o banco e popula tudo para os testes locais |
| `make delivery` | roda uma passada dos jobs de entrega |
| `make sweep-files` | lista os arquivos órfãos do storage, sem apagar |
| `make sweep-files-apply` | apaga os órfãos listados |
| `make admin-*` | `deps`, `start`, `build`, `test`, `test-cov`, `format` do painel |
| `make site-*` | `deps`, `start`, `build`, `test`, `test-cov`, `format` dos assets do site |
| `make docker-*` | `build`, `start`, `stop`, `restart`, `logs`, `migrate`, `administrator` |

**Uma receita declara o que ela lê.** Três testes medem o que um build escreve — o contraste dos dois
temas lê o CSS construído do site, e os dois `brand.css` saem do `config/base.py` —, então `test`,
`test-cov` e `site-test` nomeiam os builds de que dependem. Num clone novo, onde nada sobrou de um build
anterior, é isso que faz a suíte achar o que ela mede.

**Um comando que fez o que foi pedido devolve zero.** O `make sweep-files` lista órfãos e listar é o que
ele foi mandado fazer, então ele termina com sucesso mesmo achando nenhum. O `recreate-schema` devolve 1
por outro motivo, que é ter **recusado** destruir sem confirmação.

**Antes de dizer que terminou:** `make format`, `make test`, `make admin-test` e `make site-test` têm
que passar, e a cobertura do backend tem que estar em 100%.

**O piso de 100% é do `pyproject.toml`**, e não um número escrito no arquivo da CI, senão o comando
local que existe para prová-lo passa com qualquer cobertura.

---

## Stack

**Backend** — Python 3.13 e 3.14, FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2, PyJWT, argon2, Pillow,
aioboto3, Jinja2, [Queuefy](https://github.com/paulocoutinhox/queuefy),
[Cachefy](https://github.com/paulocoutinhox/cachefy). SQLite (`aiosqlite`) em
desenvolvimento, MySQL (`aiomysql`) em produção.

**A versão do Python é afirmada em cinco lugares e provada num.** O `requires-python` diz o piso, o badge
do README diz quais, a matriz da CI **roda a suíte em cada uma delas**, e o `Dockerfile` constrói no piso
com o mesmo Node em que o pipeline roda os dois builds — `tests/test_app.py` falha se os cinco
discordarem. O `.python-version` fica no piso, porque quem desenvolve desenvolve no mínimo que o projeto
sustenta.

**O mesmo vale para o teto de corpo do proxy.** O `client_max_body_size` do `nginx.conf` é o
`upload_max_bytes` da configuração escrito uma segunda vez, fora do Python: um proxy mais apertado recusa
com um 413 que esta aplicação nunca vê, e um mais largo entrega um corpo que ela vai recusar depois de
lê-lo. `tests/test_app.py` cobra que os dois sejam o mesmo número.

**As três árvores de dependência são auditadas contra aviso conhecido**, e as ferramentas nascem fora do
repositório: `uvx pip-audit` sobre o que o `uv export` fixa, e `npm audit` em cada um dos dois front-ends.
Isso não está na CI de propósito — um aviso novo aparece sem ninguém ter mexido em nada, e travar o
pipeline por isso é parar trabalho que não tem relação com ele.

**Ferramental** — `uv` para ambiente e dependências, `ruff` para lint **e** formatação. Não há black:
`ruff format` é o formatador, e ter dois seria duas respostas para a mesma pergunta. Tudo mora no
`pyproject.toml` — dependências, grupo de dev, ruff, pytest e cobertura. Não existe `requirements.txt`,
`pytest.ini` nem `.coveragerc`.

**Admin** — Vue 3 `<script setup>`, Vite, Tailwind CSS 4, Pinia, vue-router, vue-i18n, TinyMCE 8
auto-hospedado. Testes em Vitest com jsdom e `@vue/test-utils`.

**Site** — Jinja2 renderizado pelo próprio processo. `webapps/site/` não é uma aplicação: é o pipeline
que constrói **dois** arquivos, `styles.css` e `scripts.js`, mais o JavaScript de melhoria progressiva
que os acompanha. Testes em Vitest.

**Sem TypeScript.** O admin e o site são JavaScript puro, por decisão. Não introduza `.ts`,
`tsconfig.json`, tipos em JSDoc nem `defineProps<T>()`. A validação de props é a runtime do Vue.

---

## Estrutura do projeto

```
fastkit/
├── CLAUDE.md            este arquivo
├── README.md            a documentação pública
├── docs/                a documentação pública, em inglês
├── Makefile             todo comando do projeto
├── Dockerfile           uma imagem, três estágios
├── docker-compose.yml   um arquivo para todo ambiente, escolhido por APP_ENV
├── entrypoint.sh        aplica o schema e então serve
├── nginx.conf           o proxy reverso, para quando existe um na frente
├── main.py              monta o app: log, cors, locale, erros, site, rotas, estáticos
├── manage.py            comandos de linha de comando
├── pyproject.toml       dependências, ruff, pytest e cobertura
├── uv.lock              o que uma instalação reproduz
├── config/              um arquivo por ambiente, herdando em cadeia
├── data/                o que a instância escreve: o sqlite e o media local
├── enums/               enums de domínio, um arquivo por módulo
├── extras/              o que não é código: as imagens do README, o seed e o DDL do schema-diff
├── helpers/             infraestrutura compartilhada por todos os módulos
├── jobs/                tarefas agendadas, declaradas no `Queuefy` da aplicação
├── locale/              en.json, pt.json e es.json, as mensagens da API e do site
├── models/              tabelas SQLAlchemy
├── routes/              endpoints HTTP, com `routes/site/` desenhando páginas
├── schemas/             entrada e saída Pydantic
├── services/            regra de negócio
├── templates/           os templates Jinja do site e de todo e-mail
├── tests/               espelha a estrutura acima
└── webapps/
    ├── admin/           a SPA Vue do painel, servida em /admin
    └── site/            o build de css e js do site
```

**Tudo que a instância escreve mora em `data/`.** O SQLite do desenvolvimento é `data/app.db` e o
storage local é `data/media/`. Um volume cobre tudo, e nada da máquina de quem desenvolve cai na raiz
do repositório.

### As camadas do backend

O fluxo é sempre o mesmo e não se pula etapa:

```
routes/  ->  schemas/  ->  services/  ->  models/
```

- O **`routes/`** não tem regra de negócio. Recebe, delega ao service, devolve o schema de leitura.
- O **`services/`** não conhece HTTP. Não recebe `Request`, não levanta `HTTPException`, não lê header.
- O **`models/`** não tem comportamento. São colunas, índices e relacionamentos.
- O **`schemas/`** não acessa banco.

### `helpers/` — o que é de todo mundo

| Arquivo | Responsabilidade |
| --- | --- |
| `audit.py` | o que um operador fez no painel, escrito onde o resto do sistema já é lido |
| `auth.py` | dependências de autenticação: `CurrentUser`, `get_administrator`, `get_current_brand` |
| `brand.py` | quem uma requisição responde por: um tenant onde a instância serve muitas marcas, e a configuração onde ela serve uma |
| `cache.py` | o `Cachefy` da aplicação e os sete espaços onde o conteúdo final montado é guardado |
| `captcha.py` | o contrato de desafio e os três provedores |
| `consent.py` | o que o visitante permite guardar: `given` lê a resposta, `remember` a grava, `wanted` traduz o formulário |
| `cookies.py` | como este site escreve um cookie, que é uma resposta só para quem o lê e por onde ele viaja |
| `cors.py` | origens permitidas |
| `crud.py` | fábrica de rotas CRUD: `build_router`, `build_readonly_router`, filtros da query |
| `csrf.py` | o valor que viaja no cookie e no formulário |
| `dates.py` | `now()`, `as_utc`, `naive_utc`, `add_months`, `add_interval` |
| `db.py` | engine, sessão, `Base`, `create_schema`, `recreate_schema`, `commit`, `insert_or_read`, `run_scoped` |
| `errors.py` | hierarquia de erros e o formato da resposta |
| `forms.py` | o payload de um formulário, validado pelas mesmas regras da API |
| `head.py` | o método que uma rota não declara e todo leitor automático usa |
| `headers.py` | o que toda resposta carrega, e quais delas são de um leitor só e ninguém na frente pode guardar |
| `i18n.py` | resolve o idioma do `Accept-Language` |
| `idempotency.py` | a escrita que um cliente nomeou, para que mandá-la duas vezes cobre uma vez |
| `lifespan.py` | cria o schema na subida e roda o worker da fila |
| `locale.py` | middleware que fixa o idioma da requisição |
| `log.py` | configuração do logging |
| `money.py` | a unidade mínima de cada moeda, que é o que um gateway cobra em, e como uma pessoa lê um valor dela |
| `pagination.py` | `PageParams`, `Page[T]`, `CurrentPage` |
| `payload.py` | o teto do corpo que este processo lê inteiro na memória |
| `postal_code.py` | o contrato de busca de código postal e a implementação de cada país que tem uma |
| `rate_limiter.py` | limite por IP e limite global, num contador que não cresce sem fim |
| `remote.py` | o corpo que outra máquina respondeu, lido como um mapa ou como nada |
| `router.py` | ordem de registro dos routers da API e do site |
| `scheduler.py` | o `Queuefy` da aplicação, o worker desta instância e os ouvintes que viram auditoria |
| `schema.py` | constrói o schema, e fica acima do engine e dos models para que nenhum dos dois adie um import |
| `scope.py` | `reaches_tenant`, `belongs_to_tenant` |
| `search.py` | o termo, o casamento e o ranking de uma busca, e o índice que cada banco precisa |
| `security.py` | senha, token, criptografia de segredos |
| `sentry.py` | arma o rastreador de falhas, e não arma onde não há dsn |
| `settings.py` | carrega `config.<APP_ENV>` |
| `signing.py` | um valor que o servidor entrega e lê de volta sem guardar em lugar nenhum, assinado para um propósito só |
| `site.py` | o tenant, o idioma, a sessão, o flash, a paginação e a renderização de uma página |
| `static.py` | serve `/media`, `/static` e a SPA do admin |
| `storage.py` | abstração de armazenamento, `build_key`, `storage` |
| `templates.py` | o Jinja, com o tenant sobrescrevendo o global |
| `text.py` | `slugify`, `alphabetical`, `only_digits`, `is_valid_cpf`, `display_name` |
| `tracing.py` | o nome que uma requisição responde por, e que amarra log, auditoria e falha |
| `visitor.py` | o nome assinado pelo qual um banner conta um leitor que permitiu analytics |

**Todo helper abre dizendo o que é**, numa frase. É a pasta que todo módulo alcança e a que mais se lê
fria, e `tests/test_layout.py` falha quando um deles abre calado.

**Regra das utilitárias:** função utilitária de um módulo vai no helper daquele módulo, não num
`utils.py` genérico. Se é utilitária de um só service e ninguém mais usa, é um método do próprio
service — não sobe pra `helpers/`.

---

## Padrão de código

### Formatação — é da ferramenta, não sua

Não formate na mão e não ordene import na mão. Escreva o código e rode `make format`.

O `ruff` está configurado em `pyproject.toml` com `line-length = 320` e
`format.skip-magic-trailing-comma = true`. O lint roda com `select = ["E4", "E7", "E9", "F", "I"]` —
erros reais, código morto e ordem de import.

O prettier dos front-ends usa `@trivago/prettier-plugin-sort-imports`, `printWidth: 320`, `tabWidth: 4`.

> Nunca rode `npx prettier` sem config. O default dele é 80 colunas e quebra toda chamada em várias
> linhas, contra o padrão da casa.

### Chamadas em uma linha

Função, método, construtor e chamada ficam **sempre numa linha só**. Parâmetro não quebra em várias
linhas. É pra isso que a largura é 320.

```python
# The width is 320 so a signature like this one never breaks.
async def lookup(self, db: AsyncSession, search: str | None, limit: int, filters: dict | None = None, operator=None) -> list[dict]:
```

A exceção é uma literal que o formatador decide manter expandida.

### Comentários

**Todo comentário é uma frase completa, começando com letra maiúscula e terminando com ponto final.**
Vale para `#`, `//` e `"""..."""`, e o texto é sempre em inglês.

Comentário é raro. Só existe quando explica **por que**, nunca **o que**. Se o comentário descreve o
que a linha faz, apague o comentário.

| Regra | O que impede |
| --- | --- |
| maiúscula no começo e ponto no fim | o fragmento solto que não se lê como frase |
| uma frase inteira por linha, e nunca uma frase continuando na linha seguinte | um comentário lido pela metade |
| a frase atual termina com ponto antes de a próxima começar na linha seguinte | duas ideias grudadas |
| nada de verboso, fragmentado ou narrativo | o comentário que conta uma história em vez de dar o motivo |

**Nenhuma frase começa em minúsculo, e isso vale para toda prosa deste projeto** — comentário,
docstring, este arquivo, o `README.md` e a pasta `docs/`. Quando a frase começaria por um identificador
escrito em minúsculo, a grafia dele **nunca** muda: quem muda é a frase, que ganha na frente a palavra
que diz o que aquele nome é.

| Em vez de | Escreva |
| --- | --- |
| `` `tests/test_layout.py` cobra as três coisas`` | `tests/test_layout.py` cobra as três coisas |
| `` `migrate` creates a table`` | The `migrate` command creates a table |
| `` `role` é um enum de três valores`` | A coluna `role` é um enum de três valores |

O mesmo vale para um nome próprio que começa em minúsculo, como `reCAPTCHA`. Três travas cobram isso:
duas leem todo comentário e toda docstring do código que roda, e a terceira lê toda frase deste arquivo,
do `README.md` e dos guias.

**Nome próprio se escreve como o dono dele escreve**, em qualquer lugar da frase: MySQL, SQLite,
PostgreSQL, InnoDB, RevenueCat, Stripe, Google, reCAPTCHA, Queuefy, TinyMCE, e as siglas em caixa alta.

**O comentário acima de uma função, método, classe ou módulo diz o que ela faz para quem vai
chamá-la**, e nunca como ela está implementada por dentro. As 92 descrições de rota são publicadas em
`/docs`, então elas não são comentário interno: são a documentação que quem integra lê.

**O que nunca é comentário:** um rótulo separando seções artificiais do arquivo. Nada de `# helpers`,
`# validators` ou `# ---`. Se o arquivo precisa de placa para ser lido, o problema é o arquivo.

**O que a regra não alcança:** diretiva lida por ferramenta (`# fmt: off`, `# noqa`, `// eslint-disable`
e as parentes), shebang, cabeçalho de licença e endereço dentro de um comentário ficam exatamente como
a ferramenta espera.

### Outras regras de escrita

- Sem ponto e vírgula separando sentenças numa mesma linha.
- Sem código de compatibilidade retroativa e sem checagem de legado.
- Sem código morto, sem fallback genérico, sem comportamento implícito inesperado.
- Sem `TYPE_CHECKING` import.
- Retorno cedo, sem `else` depois de um `return`.
- Sem aninhamento que um retorno antecipado desfaz.
- `__init__.py` sempre vazio, exceto `models/registry.py`, que existe pra preencher o metadata.
- **A regra de um campo mora no tipo dele, e não no schema.** `Cpf`, `MobilePhone` e `Timezone` são tipos
  anotados que carregam o tamanho e a validação, porque a mesma checagem escrita em dois schemas é a
  mesma checagem que um dia diverge.

### A ordem de um arquivo

**Um arquivo é lido de cima para baixo, então ele é escrito assim.** A ordem é sempre a mesma:

```
imports  ->  constantes  ->  variáveis  ->  classes e funções
```

| Regra | O que ela impede |
| --- | --- |
| **todo import fica no topo, e nenhum dentro de uma função** | um ciclo contornado em vez de quebrado, e um módulo que esconde do que ele depende |
| **nenhum import depois de o arquivo começar a fazer coisa** | uma dependência que chega tarde demais para quem já precisou dela |
| **constante antes de variável** | um `logger` ou um `router` no meio do caminho entre o nome e o que ele significa |

**O que vem depois da primeira definição é o que deriva dela** — a instância no fim do arquivo, o
`router` que a fábrica monta, o `PROVIDERS` que instancia as classes acima. Isso não é desordem: é a
única ordem possível.

O `tests/test_layout.py` cobra as três coisas em todo arquivo do código que roda, e ele prova a própria
varredura: uma pasta de código que ele não lê falha a suíte. A `tests/` fica de fora de propósito,
porque um teste alcança a fábrica que ele usa dentro do caso que a usa.

> **Um import dentro de uma função é sempre um ciclo, e um ciclo se quebra e não se adia.** O contrato
> de gateway é `services/gateway.py`, que não conhece service nenhum. Construir schema é
> `helpers/schema.py`, que fica acima do engine e dos models. E a página de 404 do site é **entregue**
> ao tratador de erro pelo `main.py`, em vez de buscada por ele.

### A forma de um método

**Um método tem começo, meio e fim, e isso se enxerga sem ler.** Bloco de responsabilidade diferente
separado por **uma** linha em branco, nunca vários `if` e retornos colados visualmente, nunca linha em
branco entre linhas do mesmo bloco.

**E não se extrai método para encurtar a tela.** O certo é extrair quando o trecho tem **um nome**, e
deixar onde está quando ele não tem.

**E ele não recebe o que não lê.** Um argumento que o corpo nunca toca é um argumento que **todo chamador
continua passando**, e ele sobrevive ao que um dia precisou dele. `tests/test_layout.py` percorre as
funções do código que roda e recusa isso — com uma exceção nomeada para as cinco assinaturas que
**outro** declara: o listener do SQLAlchemy, o do Queuefy, os dois lados do `TypeDecorator` e o `save`
do storage, onde um provedor lê o content type e o outro não. Uma segunda trava falha quando uma dessas
exceções sobrevive à função que a pediu.

### Integração com terceiro se escreve lendo a documentação atual dele

**Nunca de memória, e isso é regra.** Antes de escrever ou mexer em qualquer integração — gateway,
loja, provedor de e-mail, storage, captcha — abra a documentação **da versão atual** do fornecedor e
confira campo por campo.

O que isso custa é uma leitura. O que evita é o tipo de erro que passa em todo teste e só aparece com
dinheiro de verdade: um campo que mudou de lugar, um valor que é dólar e não a moeda do comprador, um
período que deixou de ficar na assinatura e passou a ficar no item dela.

Ao escrever a integração, **anote aqui o que veio de lá** — o nome do campo, o que ele significa, e o
que a documentação do fornecedor diz. É isso que faz a próxima revisão ser uma conferência.

---

## Nomenclatura e organização de arquivos

**Um arquivo por domínio, não um arquivo por classe.** `models/commerce.py` guarda `Product`, `Purchase`
e `UserProduct`, e `services/commerce.py` os services correspondentes. O mesmo nome de arquivo se repete
nas camadas, e é assim que se acha as coisas.

**Como decidir onde uma classe nova vai:**

- O domínio já existe? Vai no arquivo dele, no fim, junto das irmãs.
- É um domínio novo? Arquivos novos com o mesmo nome, um por camada — e só os que fizerem sentido.
- Um arquivo grande não é motivo pra quebrar. `services/subscription.py` tem oito services e está certo.
- O que **nunca** acontece: um arquivo com classes de dois domínios diferentes.

Fora dos domínios existem os arquivos compartilhados de cada camada: `models/base.py`,
`models/registry.py`, `schemas/common.py`, `services/crud.py` e `services/gateway.py` — este último é o
contrato que todo gateway implementa, e ele não conhece service nenhum.

**Underline é só de pacote Python.** Todo segmento que aparece numa URL vai com traço, na API e no
site: `/api/gallery-photos`, `/account/password-recovery`, `images/gallery`, `files/product`. Nunca
`/api/minha_api/x`, sempre `/api/minha-api/x`.

**O que fica de fora da regra é o nome do parâmetro**, que vai entre chaves e nunca é digitado:
`/account/purchases/{purchase_id}` é o endereço que o Python lê, e `/account/purchases/42` é o que a
pessoa abre. `tests/test_docs.py` percorre os 176 caminhos da API **e as páginas do site**, e a
`test_the_folder_of_a_stored_file_is_a_public_address_too` cobra o mesmo da pasta de cada finalidade de
upload — uma chave de storage também vira endereço.

### Os domínios

| Domínio | Camadas | O que guarda |
| --- | --- | --- |
| `tenant` | todas | o tenant e o que é escopado a ele |
| `user` | todas | conta, token, papel, status, avatar, endereço |
| `subscription` | todas | plano, direito, benefício, assinatura, concessão |
| `commerce` | todas | produto, compra e o que a conta possui |
| `gallery` | todas | galeria e foto de galeria |
| `content` | todas | conteúdo e categoria de conteúdo |
| `banner` | todas | espaço promovido |
| `integration` | todas | gateway externo, produto externo, evento de webhook |
| `language` | todas | idiomas oferecidos |
| `country` | todas | países, e qual serviço responde o código postal de cada um |
| `newsletter` | todas | quem pediu para receber, e se o endereço já confirmou |
| `event` | todas | evento reportado pelo cliente |
| `system_log` | todas | registro de auditoria |
| `email` | model, schema, service, rota | a fila de mensagens e os endereços que pararam de receber |
| `idempotency` | model, helper | a escrita que um cliente nomeou, para que mandá-la duas vezes cobre uma vez |
| `account` | model, schema, service, rota | moeda, saldo, extrato e o que a própria conta faz de si |
| `auth` | schema, service, rota | entrar, cadastrar, recuperar senha |
| `checkout` | service | o que abre uma sessão de pagamento num gateway |
| `contact` | service, rota | o que alguém escreve ao operador |
| `upload` | model, service, rota | as regras de arquivo por finalidade, e o arquivo que subiu e ninguém reclamou |
| `delivery` | service | o motor de entrega |
| `webhook` | service, rota | o que um gateway reporta, e o que isso move |
| `reconciliation` | service | o que o provedor diz que a conta tem, e o que fazer quando diverge |
| `retention` | service | o que uma tabela operacional para de guardar |
| `rotation` | service | a reescrita dos segredos guardados, quando a chave que escreve muda |
| `sweep` | service | a varredura de arquivos órfãos |
| `site` | rotas | as páginas públicas, em `routes/site/` |

Dois arquivos de rota não seguem o nome do domínio, de propósito: `routes/credit.py` expõe o CRUD
administrativo do extrato do domínio `account`, e `routes/meta.py` publica o que o admin precisa pra
montar as telas sem ter model nenhum atrás.

### Nomes

| Coisa | Padrão | Exemplo |
| --- | --- | --- |
| Tabela | singular, `snake_case` | `commerce_product` |
| Model | `PascalCase` singular | `Product` |
| Coluna | `snake_case` | `product_id`, `created_at` |
| Campo na rede | o mesmo nome em `camelCase`, pelo alias | `productId`, `createdAt` |
| Chave estrangeira | `<tabela>_id` | `gallery_id` |
| Índice | `<tabela>_<intenção>` | `commerce_product_listing` |
| Restrição e chave | o mesmo, e o nome começa pela tabela | `subscription_benefit_grant_key` |
| Restrição única | nomeada sempre, nunca `unique=True` solto | `UniqueConstraint("token", name="user_token")` |
| Enum | `PascalCase`, valores `snake_case` | `PurchaseStatus.CHARGED_BACK = "charged_back"` |
| Enum cujo valor vira segmento de URL | `PascalCase`, valores em kebab | `UploadPurpose.GALLERY_PHOTO = "gallery-photo"` |
| Schema de leitura | `<Model>Schema` | `ProductSchema` |
| Schema de escrita | `<Model>Create` / `<Model>Update` | `ProductCreate` |
| Schema reduzido | `<Model>Reference` | `ProductReference` |
| Identidade com regra | um tipo anotado em `schemas/common.py` | `Cpf`, `MobilePhone`, `Timezone` |
| Service | `<Model>Service` + instância no fim do arquivo | `product_service = ProductService()` |
| Rota de admin | `/api/<recurso-no-plural-em-kebab>` | `/api/gallery-photos` |
| Rota de cliente | `/api/<familia>/<superficie>` | `/api/commerce/products` |
| Chave de mensagem | `error.` / `validation.` / `site.` em kebab | `error.product-out-of-tenant` |
| Teste | `test_<frase_que_descreve_o_comportamento>` | `test_a_refund_marks_the_payment_and_never_reaches_for_what_it_bought` |

O nome do teste é uma frase em inglês que descreve o comportamento, não o método chamado.

**E o nome começa pela tabela, e não pelo model.** **No PostgreSQL o nome de um índice é do banco
inteiro e não da tabela**, então dois domínios que abreviassem para o mesmo nome colidiriam ao criar o
schema, e no `information_schema` nada diria a que tabela um deles pertence — que é a leitura que este
arquivo manda fazer antes de mexer numa chave estrangeira. `tests/test_sql_portability.py` cobra as três
coisas: que o nome comece pela tabela, que nenhum se repita, e que nenhum passe dos 64 caracteres que o
MySQL aceita.

> **Uma renomeação de índice é de graça aqui e não num produto publicado.** Este repositório é um
> template, cujo banco nasce do zero — lá ela é DDL a acumular. E ela pede cuidado com o namespace ao
> lado: o nome de um índice e o de um **enum** publicado no `/api/meta` são coisas diferentes, e uma
> troca cega nos catálogos quebra os rótulos do painel.

**E onde as duas regras se cruzam, a do endereço vence.** O valor de `UploadPurpose` é o segmento de
`POST /api/uploads/{purpose}`, então ele vai com traço e não com underline — é a mesma regra que faz o
recurso ser `/api/gallery-photos`. `tests/test_docs.py` cobra a forma de todo valor de enum e nomeia esse
como exceção **com o motivo escrito**, junto de uma segunda trava que falha se ele um dia passar a
seguir a regra comum e a exceção ficar para trás.

### Nome de coluna reservado

O atributo Python da coluna `metadata` é **`meta`** em todos os models, porque o `declarative_base` do
SQLAlchemy reserva `metadata`:

```python
meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
```

---

## Como adicionar um recurso novo

Sete passos, nesta ordem:

1. Um enum novo vai em **`enums/<modulo>.py`**.
2. A tabela vai em **`models/<modulo>.py`**, herdando `Base, IdentifiedMixin, TimestampMixin`.
3. No **`models/registry.py`**, importe e adicione ao `__all__`, senão a tabela não é criada.
4. Os schemas vão em **`schemas/<modulo>.py`**: `<Nome>Schema`, `<Nome>Create` e `<Nome>Update = as_optional(...)`.
5. O service vai em **`services/<modulo>.py`**, com a subclasse de `CrudService` e a instância no fim do arquivo.
6. As rotas vão em **`routes/<modulo>.py`**, com `build_router(...)`, e são registradas em `helpers/router.py`.
7. A definição do painel vai em **`webapps/admin/src/resources/<secao>.js`**, e é registrada no `index.js`.

Depois, sempre nos **três** catálogos de cada lado:

- Em `locale/en.json`, `pt.json` e `es.json`: mensagens de erro, de validação e do site, mais um
  `enum.<enum>.<valor>` por valor de enum novo.
- Em `webapps/admin/src/i18n/en.js`, `pt.js` e `es.js`: `resource.<nome>.menu`, `.title` e `.singular`,
  um `field.<nome>` por campo novo, um `group.<chave>` por fieldset novo e um `enum.<enum>.<valor>` por
  valor novo.

E os testes: um em `tests/routes/` pelo contrato e um em `tests/services/` pela regra, mais o do admin
se a tela ganhou comportamento.

As travas rodam sozinhas e não deixam uma declaração mentir:

| Teste | O que impede |
| --- | --- |
| `tests/test_registry.py` | model mapeado que o registry não nomeia, e nome no `__all__` que ele não importou |
| `tests/test_docs.py` | número escrito em prosa que deixou de bater com a superfície |
| `tests/test_docs.py` | símbolo do projeto que a prosa nomeia e o código não tem mais |
| `tests/test_docs.py` | job documentado que o agendador não registra, e o contrário |
| `tests/test_docs.py` | comentário ou docstring que não é uma frase com maiúscula e ponto |
| `tests/test_docs.py` | frase da documentação aberta em minúsculo, onde quem se reescreve é a frase e nunca o nome |
| `tests/test_docs.py` | conjunto que a prosa conta e o esquema declara de outro tamanho, e papel que ela nomeia e o enum não tem |
| `tests/test_docs.py` | superfície que o roteiro de início promete e nunca constrói |
| `tests/test_docs.py` | símbolo e comando que a documentação **pública** nomeia e o projeto não tem |
| `tests/test_docs.py` | endereço que a documentação **pública** nomeia e a aplicação não responde, no caminho e no método |
| `tests/test_docs.py` | assinatura ou classe que a prosa mostra e o código não tem |
| `tests/test_docs.py` | número de índices, uniques e `FULLTEXT` que a prosa afirma e o esquema não declara |
| `tests/test_docs.py` | valor de enum escrito fora da forma que este projeto dá a um |
| `tests/test_app.py` | arquivo que um front-end lê fora da própria pasta e o estágio que o constrói não copia |
| `tests/test_app.py` | schema construído a partir de uma metadata nomeada em vez da lista que a aplicação cria |
| `tests/test_app.py` | processo que sobe com o segredo que a configuração publicada traz por preencher |
| `tests/test_app.py` | endereço que o seed escreve e o schema que grava a linha recusa |
| `tests/test_app.py` | rota que responde GET e recusa HEAD, e schema que publica um HEAD |
| `tests/test_app.py` | rota literal declarada depois de um parâmetro do mesmo método, que nunca responde |
| `tests/test_app.py` | valor de enum sem implementação em qualquer tabela que o código despacha por, achadas no fonte e não nomeadas à mão |
| `tests/test_app.py` | padrão com que um build lê a configuração e que deixou de achar o valor que o servidor tem |
| `tests/test_app.py` | a suíte armando menos do que o `main.py` arma, sem o motivo escrito |
| `tests/test_manage.py` | comando que o parser declara e o despacho não nomeia |
| `tests/test_manage_loops.py` | módulo que dirige a sessão compartilhada e abre um laço por fora do `run_scoped` |
| `tests/test_makefile.py` | receita chamando ferramenta Python direto, ou npm sem `--prefix` |
| `tests/test_makefile.py` | a CI escrevendo um comando que uma receita já declara |
| `tests/test_makefile.py` | receita que roda um comando na imagem e o entrega ao entrypoint, que o engole |
| `tests/test_requirements.py` | módulo que o código importa e o `pyproject.toml` não declara |
| `tests/test_layout.py` | import dentro de função, import depois do código, e constante escrita depois de uma variável |
| `tests/test_layout.py` | função que recebe um argumento que o corpo nunca lê |
| `tests/test_messages.py` | chave de mensagem que falta em qualquer catálogo, a que o código nomeia e nenhum guarda, e a que sobrou |
| `tests/test_messages.py` | valor de enum que a API publica e um catálogo não nomeia |
| `tests/test_messages.py` | tradução que nomeia um placeholder que as outras não nomeiam |
| `tests/test_roles.py` | quem alcança o painel escrito como uma derivação em vez de uma lista |
| `tests/test_role_matrix.py` | rota do `/api` que ninguém classificou, e recurso que não nomeia papel nenhum |
| `tests/test_route_guards.py` | rota sem guarda que não esteja declarada como aberta, e rota que recebe um identificador e não entrega o dono à consulta |
| `tests/test_ownership.py` | leitor que alcança a linha de outro, pela API ou pelo site |
| `tests/test_access.py` | o que alguém tenta alcançar e não é dele: papel, catálogo, linha de outro, chave de outro e conta que não existe |
| `tests/test_access.py` | login que ninguém tem respondido sem pagar o hash que um que existe paga |
| `tests/test_security.py` | injeção, markup, token forjado, redirecionamento para fora, chave que sobe de pasta e payload que nomeia o dono |
| `tests/test_security.py` | valor assinado para um propósito que outro leitor deste site aceita |
| `tests/test_security.py` | resposta de um leitor só que um cache na frente poderia guardar e entregar a outro |
| `tests/test_security.py` | módulo que escreve um cookie por fora do `helpers/cookies.py` |
| `tests/test_intrusion.py` | destino que o navegador executaria, uuid carregando injeção, nome de leitor forjado, marca lendo o que outra montou e confinado alargando por filtro |
| `tests/test_api_restrictions.py` | rota que abre escrita numa tabela que o motor escreve, payload de cliente que nomeia dono ou saldo, e texto que a coluna não guarda |
| `tests/test_api_restrictions.py` | schema de leitura que exige uma coluna que a tabela deixa vazia |
| `tests/test_api_restrictions.py` | coluna obrigatória cujo schema aceita um texto em branco |
| `tests/test_sql_portability.py` | sintaxe que só um dos três dialetos aceita |
| `tests/test_sql_portability.py` | o saldo lido sem a trava que o movimento sobre ele depende |
| `tests/test_sql_portability.py` | ordenação por coluna anulável que não diz o que fazer com o nulo |
| `tests/test_contrast.py` | par de cores que uma página põe um sobre o outro abaixo do contraste legível |
| `tests/test_contrast.py` | cor que um tema do site declara duas vezes, onde a de fábrica ganharia por especificidade |
| `tests/test_providers.py` | mapa de provedor que não responde por todo valor do enum, e contrato que aceita uma subclasse vazia |
| `tests/test_admin_audit.py` | escrita administrativa que não deixa rastro e não está nomeada como isenta |
| `tests/test_admin_contract.py` | campo do admin que a API não aceita, e recurso sem rota |
| `tests/test_admin_contract.py` | coluna do admin que o schema de leitura não responde |
| `tests/test_admin_contract.py` | filtro ou ordenação que o grid desenha e o service não aplica |
| `tests/test_admin_contract.py` | caixa de busca que o grid desenha e o service não procura |
| `tests/test_admin_contract.py` | campo de arquivo do admin que o service não declara, ou declara com outra finalidade |
| `tests/test_admin_contract.py` | rótulo que sobrou num catálogo do admin depois que a tela que o desenhava saiu |
| `tests/test_admin_contract.py` | valor que um template desenha como markup e o painel não autora no editor |
| `tests/test_admin_contract.py` | enum que o painel desenha e a API não publica, e o que ela publica e ninguém desenha |
| `tests/routes/test_crud_contract.py` | filtro que atravessa outra tabela e responde linhas para um valor que nomeia nada |
| `tests/routes/test_crud_contract.py` | relação que o schema de leitura responde e o service não carrega |
| `tests/services/test_crud.py` | recurso localizado sem índice único sobre a chave que o endereça |
| `tests/services/test_crud.py` | coluna de arquivo que um `Dependent` esqueceu, e chave que aponta para fora da finalidade |
| `tests/services/test_crud.py` | coluna que o painel autora no editor e o service não lê um arquivo de |
| `tests/services/test_sweep.py` | passada de órfãos que leia uma tabela que não é a dela, ou que a leia sem lote |
| `tests/services/test_email.py` | mensagem enfileirada com um template que não existe, ou sem um nome que ele lê |
| `tests/services/test_image_processing.py` | tela de imagem maior do que esta instância desenha, recusada antes de ser alocada |
| `tests/helpers/test_forms.py` | chave recusada que não é um campo do formulário que a página desenhou |
| `tests/helpers/test_money.py` | coluna de dinheiro mais estreita do que a moeda mais fina divide |
| `tests/helpers/test_money_reading.py` | idioma oferecido que não diz como escreve um número |
| `tests/helpers/test_payload.py` | rota isenta do teto de corpo que não alcança regra de tamanho nenhuma |
| `tests/helpers/test_search.py` | `text_search_fields` sem o `search_index` que o MySQL exige |
| `tests/helpers/test_cache.py` | superfície guardada cujo valor a store recusa |
| `tests/routes/test_tenant.py` | ordem de cascata que faz uma referência restrita disparar ao excluir um tenant |
| `tests/routes/test_password_reset.py` | endereço que recebe mais de uma recuperação por janela, ou token queimado por quem só pediu |
| `tests/routes/test_app_parity.py` | o que o site faz e a API não |
| `tests/routes/site/test_account.py` | página da conta que responde a quem não tem sessão |
| `tests/routes/site/test_public.py` | link que uma página desenha e não responde, e entrada do sitemap que não responde |
| `tests/routes/site/test_public.py` | endereço que o sitemap nomeia numa instalação onde ninguém escreveu nada ainda |
| `tests/routes/site/test_public.py` | página que deixa de ser desenhada inteira em algum dos idiomas oferecidos |
| `tests/routes/site/test_public.py` | endereço absoluto que segue o host da requisição em vez do que o site declara |
| `tests/routes/site/test_public.py` | link morto dentro da área que só um leitor com sessão enxerga |
| `tests/routes/site/test_public.py` | controle recusado que não diz que foi, ou que aponta uma mensagem que a página não desenhou |
| `tests/routes/site/test_public.py` | controle visível sem rótulo, e título que pula um nível |
| `webapps/admin/tests/components/fields.test.js` | campo do painel que fica vermelho e não diz que foi recusado |
| `webapps/admin/tests/i18n/index.test.js` | chave que uma tela do painel pede e nenhum catálogo guarda |
| `webapps/site/tests/shape.test.js` | utilitário de `display` escrito ao lado de um componente que já o decide |
| `webapps/site/tests/shape.test.js` | atributo `data-` que nada procura, e classe que a folha construída não define |

### O `CrudService`

Quase tudo que um recurso precisa vem de declarar atributos:

```python
class GalleryService(TaggedService):
    model = Gallery
    search_fields = ("tag",)
    text_search_fields = ("title",)
    filter_fields = ("tenant_id", "language_id", "active")
    ordering_fields = ("id", "title", "tag", "position", "published_at", "created_at")
    default_ordering = "position"
    relations = ("tenant", "language")
    label_fields = ("title",)
    position_field = "position"
    listing_fields = ("position", "id")
    dependents = (Dependent(GalleryPhoto, "gallery_id", ("image",)),)
```

Os ganchos que uma subclasse sobrescreve quando tem regra própria: `prepare`, `validate`,
`after_save`, `before_delete`, `build_label`, `label_ordering`. Os quatro primeiros são assíncronos.

O `position_field` nomeia a coluna de ordem e é o que faz a fábrica montar a rota de reordenação.

**O valor pelo qual um registro é endereçado é um slug, tenha ele sido digitado ou derivado.**
`apply_slug` passa por `slugify` nos dois casos, e o motivo é que esse valor não fica no banco: ele
vira **endereço**, chave de storage e pasta de template.

| Onde ele reaparece | Quem |
| --- | --- |
| `/content/{tag}`, `/gallery/{tag}` | a `tag` de `Content`, `ContentCategory` e `Gallery` |
| `/products/{slug}` | o `slug` de `Product` |
| `/checkout/plan/{code}` e `/api/subscriptions/plans/{code}/checkout` | o `code` de `Plan` |
| `templates/tenants/<code>/` e o remetente daquele tenant | o `code` de `Tenant` |

> **Derivar em silêncio e recusar o digitado seriam duas regras para a mesma coluna.** Quem deixa o
> campo em branco recebe um slug do título, então quem digita "Minha Página" recebe `minha-pagina`
> pelo mesmo caminho, e não um 422 explicando a diferença.

**Um filtro que nomeia algo de outra tabela é uma declaração, e não um método.** `filters_elsewhere`
mapeia o nome do filtro para um `Elsewhere`, que diz as duas coisas que a fábrica precisa: por qual
coluna o valor da query é lido, e a que linhas ele estreita a listagem.

```python
    filters_elsewhere = {"user_id": Elsewhere(Subscription.user_id, lambda value: UserEntitlement.subscription_id.in_(select(Subscription.id).where(Subscription.user_id == value)))}
```

**E um valor que nomeia uma linha que ninguém tem estreita para nada.** Um `IN` de subconsulta vazia
faz isso por construção. Uma subconsulta escalar não faz: ela devolve **nulo**, que em `reaches_tenant`
significa *as linhas compartilhadas*, e aí o formulário ofereceria o catálogo compartilhado inteiro em
vez de nada. É a mesma regra que este arquivo já escreve sobre filtro: o que nomeia nada responde nada.

O `relations` aceita caminho pontuado — `"subscription.user"` carrega os dois níveis numa consulta só,
evitando `MissingGreenlet`.

O `declared(prepared, instance, name)` lê um valor do payload, senão do registro, senão do default da
coluna. Use sempre isso numa validação: o payload de criação passa por `exclude_unset=True`.

### `Dependent` e exclusão

Excluir um registro apaga os dependentes e os arquivos deles, do galho mais fundo pra fora:

```python
dependents = (Dependent(GalleryPhoto, "gallery_id", ("image",)),)
```

**Uma recusa da chave é um conflito venha ela de onde vier, e o arquivo sai depois da linha.** A exclusão
de um filho é um `DELETE` que **recusa onde ele roda**, e não no commit, então a tradução é do bloco
inteiro, por um `refusing` que o `commit` também usa. E o que o storage perde é o que a linha que sumiu
nomeava — nessa ordem, senão uma exclusão recusada deixa o registro vivo apontando para um arquivo que
já não existe.

**O que o `Dependent` apaga é o que o service daquele filho declara que as linhas dele mencionam**, e
não uma lista de colunas escrita nele: duas escritas para o mesmo fato são a segunda que alguém esquece.

> **E a varredura de services percorre a árvore inteira, não um nível dela.** Um recurso que herda de
> `TaggedService` some de um `__subclasses__()` de um nível só, e a trava segue passando sem conferir
> nada daquele recurso.

> **E o `Dependent` nomeia a chave por string, então uma renomeação passa por ele calada.** Uma trava
> cobra que a coluna nomeada exista.

> **Um filho que não menciona arquivo nenhum é apagado onde ele está**, sem ser carregado: ler o que
> cada linha menciona traria as maiores tabelas inteiras para a memória para não achar nada.

**E o que o `Dependent` apaga tem que ser o que o banco já apagaria.** Um service que derruba um filho
que a chave estrangeira declara `RESTRICT` está contornando a própria declaração dele, e aí uma das
duas está errada — nunca as duas certas:

| O que a coluna aponta | O que ela declara |
| --- | --- |
| uma aresta, dos dois lados dela | `CASCADE`, porque uma aresta não é um registro e some com qualquer uma das pontas |
| um registro de catálogo | `RESTRICT`, porque apagá-lo apagaria o significado de quem aponta |

O que protege um direito vivo é `subscription_user_entitlement.entitlement_id`, que é `RESTRICT`: o
direito que uma assinatura concedeu não é excluído, e o que um plano só lista some com ele.

---

## Banco de dados

### A sessão lê no nível `READ COMMITTED`, e isso é decisão

**O `helpers/db.py` abre todo engine de servidor em `READ COMMITTED`**, e o padrão do InnoDB, que é
`REPEATABLE READ`, é justamente o que este código não pode ter. O motivo é o desenho que se repete em
todo lugar aqui: **ler, decidir, e ler de novo dentro da mesma transação.**

| O que o padrão do InnoDB faz | O que isso custa |
| --- | --- |
| todo `SELECT` responde o instantâneo que a transação abriu com | "perguntar de novo" devolve a mesma resposta velha |
| a inserção que bate numa chave única deixa um lock compartilhado na linha duplicada | o `insert_or_read` de N perdedores vira **deadlock** |

Em `READ COMMITTED` cada sentença enxerga o que já foi commitado, os gap locks somem, e o SQLite do
desenvolvimento passa a responder como o MySQL da produção — que é o que faz o dev valer como ensaio.
O PostgreSQL já é `READ COMMITTED` por padrão.

> **O que isso pede da configuração do MySQL:** o binlog em formato de linha, que é o padrão desde o
> 5.7 — `READ COMMITTED` não é compatível com o binlog em formato de sentença.

### Duas escritas que disputam a mesma linha

**Existe uma forma de resolver isso e ela é `helpers.db.insert_or_read`.** Sempre que dois caminhos
podem passar pelo mesmo `SELECT` antes de qualquer um dos dois escrever, quem perde recebe a linha que
o vencedor gravou, em vez de um erro.

Ela insere dentro de um **savepoint**, e isso não é detalhe: um `rollback` no meio de uma transação
expira **todos** os objetos da sessão, e quem chamou encontraria `MissingGreenlet` no lugar da linha.

**E a releitura de quem perdeu é um `SELECT` simples, sem `FOR UPDATE`.** Ela pode ser simples porque a
sessão roda em `READ COMMITTED`. Travar a linha ali seria pior do que inútil: a inserção recusada já
deixou um lock compartilhado nela.

**Ela procura a linha antes de escrever**, e é isso que faz a segunda chamada em diante não emitir
`INSERT` nenhum — sem essa leitura, toda releitura de um evento reentregue disputa um lock que não
precisava existir.

> **O que sobra, e nada em processo nenhum resolve:** N transações criando a **mesma linha do zero no
> mesmo instante**. O InnoDB dá um lock compartilhado na chave duplicada para cada uma, elas se cruzam,
> e ele mata uma — a transação inteira, com os savepoints dentro dela. O sintoma é
> `SAVEPOINT sa_savepoint_1 does not exist`, que é o SQLAlchemy tentando desfazer um savepoint que o
> servidor já levou.
>
> **Não dá para se recuperar disso no lugar.** O único jeito de seguir na mesma sessão é `rollback()`, e
> ele expira todo objeto que o chamador já tinha. Quem perdeu a transação repete a operação, e **todo
> caminho que chega aqui já é repetido**: o gateway reentrega o webhook, o `retry_failed_grants` recolhe
> a concessão, o cliente reenvia o lote de eventos, a passada seguinte refaz a reconciliação, e o
> `refresh` do aplicativo é segurado pela janela de 10s antes de chegar perto disso.

Os lugares onde acontece de verdade:

| Onde | Quem disputa com quem |
| --- | --- |
| concessão de um ciclo | duas instâncias servindo a mesma fila de cron |
| evento de webhook | o gateway reentregando o que ele não teve certeza de ter entregue |
| direito e benefício da assinatura | o webhook e o `refresh` do aplicativo, no mesmo segundo |
| produto que a conta passa a possuir | o motor de entrega e o pagamento que acabou de ser confirmado |
| lançamento do extrato | dois nós recolhendo a mesma concessão abandonada |
| evento reportado pelo cliente | o aparelho reenviando o lote que juntou offline |

**No extrato ela tem uma parte a mais:** a carteira só se move para quem **escreveu** a linha. Quem
perde devolve o lançamento do vencedor e não soma nada — somar seria um saldo que o extrato não tem
lançamento para explicar, que é exatamente o que `balance_after` existe para impedir.

**E o saldo sobre o qual um lançamento é escrito é lido sob trava.** É a única trava de linha do projeto,
e ela é o que serializa dois lançamentos de chaves diferentes sobre a mesma carteira: sem ela, os dois
leem o mesmo saldo e um dos dois some. **O SQLite não tem trava de linha** e compila `FOR UPDATE` para
nada, então a suíte inteira passa sem ela e quem paga é a produção — por isso
`tests/test_sql_portability.py` compila a leitura no dialeto do MySQL e cobra a trava no texto.

O `helpers.db.commit` continua existindo e é outra coisa: ele traduz a violação em `ConflictError` para
quando a colisão **é** o erro.

**E quem chama é que diz qual colisão foi**, porque o banco recusa por dois motivos e a mensagem é
lida por uma pessoa:

| O que o banco recusou | O que a resposta diz |
| --- | --- |
| uma chave única, numa escrita | `error.duplicated-record` |
| uma chave estrangeira, numa exclusão | `error.record-still-referenced` |

As 22 chaves com `RESTRICT` respondem a segunda, e `tests/test_access.py` percorre todas elas cobrando
a frase certa — e cobra junto que uma **escrita** que colide continue dizendo duplicata.

### Sem migrations

O schema vem do `Base.metadata`. **Não existe Alembic e não se deve adicionar.**

- O `make migrate` cria o que falta e não toca no que existe. É o que o container roda antes de servir.
- O `make recreate-schema` derruba tudo e recria. Perde os dados.

**Este repositório é um template, e um template não tem banco publicado.** Uma mudança de model aqui é
uma linha a mais no `Base.metadata` e nada além disso: quem começa um produto a partir dele roda
`make migrate` numa base vazia e recebe o schema inteiro.

| Onde | O que acontece |
| --- | --- |
| aqui, no template | o banco é **recriado** — `make recreate-schema` ou `make seed` — e nenhum DDL é escrito para ninguém |
| num produto já publicado a partir dele | quem o mantém acumula o DDL da própria instalação, com o `make schema-diff` |

**Nada neste repositório acompanha o schema de uma instalação de terceiro**, então não se escreve
migration, não se acumula script de alteração e não se guarda DDL versionado.

**A lista de schemas é uma, e quem constrói lê aquela.** `SCHEMAS`, em `helpers/schema.py`, nomeia o
`Base.metadata` mais os metadata da fila e do cache, e tanto a aplicação quanto o `schema-diff` iteram
sobre ela. Uma trava recusa `create_all` chamado sobre uma metadata nomeada em vez da variável do laço,
que é a forma de escrever uma segunda lista.

### `make schema-diff`

Sobe um MySQL descartável, constrói o esquema **do zero** a partir do `SCHEMAS`, lê o esquema do banco
que a configuração aponta, e compara os dois pelo `information_schema`. Escreve três arquivos em
`extras/schema/`, que não são versionados.

| Situação | O que sai |
| --- | --- |
| tabela, coluna anulável, índice, chave estrangeira que faltam | a sentença pronta |
| coluna obrigatória **com** default | o `ADD ... DEFAULT <valor>` e o `DROP DEFAULT` logo abaixo |
| coluna obrigatória **sem** default | comentada, porque alguém decide com que valor as linhas de hoje ficam |
| índice que mudou de forma mantendo o nome | o `DROP` antes do `CREATE` |
| coluna, índice ou chave que **sobra** no banco | listado como decisão humana, nunca gerado |

**Remoção nunca é proposta**, e o motivo é que ela perde dado: uma renomeação chega aqui como uma
remoção mais uma adição.

> **O `DEFAULT` é a parte que mais custa errar.** Um `ADD COLUMN ... NOT NULL` sem default não falha: o
> MySQL preenche as linhas existentes com `''` ou `0`, e `''` não é um valor que nenhum enum tem.

**Depois de aplicar, roda de novo.** O diff zerando é a prova de que o banco migrado ficou idêntico a
um criado do zero.

### Adição vai antes do deploy, remoção vai depois

| A mudança | Quando o DDL roda | Por quê |
| --- | --- | --- |
| coluna, tabela ou índice **novo** | **antes** do deploy | a imagem antiga não nomeia o que não conhece, e a nova precisa achar pronto |
| coluna que **sai** | **depois** do deploy | a imagem antiga ainda a declara |

**O SQLAlchemy nomeia toda coluna mapeada em todo `SELECT`.** Não existe `SELECT *` no ORM — então uma
coluna removida do banco enquanto a imagem antiga roda derruba **toda leitura daquela tabela**, com
`Unknown column`, até o deploy sair.

> **O `schema-diff` não pega isso:** ele compara o banco com o **código desta máquina**, e não com o que
> está publicado.

### Trocar o MySQL pelo PostgreSQL

Nada no código é escrito para um banco específico. Trocar é configuração:

1. Troque `aiomysql` por `asyncpg` no `pyproject.toml` e rode `make deps`.
2. `DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/banco`.
3. Nada mais. O `DROP_DIALECTS` de `helpers/db.py` já sabe que o PostgreSQL derruba com `CASCADE`.

Continue gravando naive UTC — a coluna `UtcDateTime` é a mesma nos três e a aplicação nunca depende do
offset do banco.

### Timezone

Timestamp é gravado em **UTC**, sempre. A coluna é `UtcDateTime`, que grava naive UTC e devolve aware
UTC. O admin e o site exibem no fuso da conta, e quem lê sem conta lê em UTC.

Use `helpers.dates.now()`, nunca `datetime.now()` nem `datetime.utcnow()`.

**E ela pede microssegundo ao MySQL, com `DATETIME(6)`.** O `DATETIME` cru guarda segundo inteiro e
**trunca** o resto, enquanto o SQLite e o PostgreSQL guardam a fração — então o instante que volta do
banco deixa de ser igual ao que ainda está na memória, e a reconciliação passa a reescrever o que
ninguém mudou a cada passada. `tests/test_sql_portability.py` compila toda tabela no dialeto do MySQL e
falha se uma coluna de data nascer sem a fração.

### O índice existe para o que a tela pergunta

O esquema declara 107 índices e uniques e 14 `FULLTEXT`, e o critério para cada um é uma pergunta só:
a tabela cresce sem limite **e** a coluna é seletiva?

| Tabela | O que a cobre | Por que precisou |
| --- | --- | --- |
| `system_log` | `(tenant_id, created_at)`, `(user_id, created_at)` | cada passada de cron escreve duas linhas, para sempre |
| `app_event` | `(tenant_id, occurred_at)`, `(user_id, occurred_at)` | o cliente reporta em lote |
| `integration_webhook_event` | `(tenant_id, created_at)`, `(subscription_id, occurred_at)` | o extrato de uma assinatura é caminho quente |
| `subscription` | `(tenant_id, status)` | cresce com a base |
| `commerce_purchase` | `(user_id, created_at)`, `(tenant_id, status)` | idem |

> **O que não ganha índice, e é decisão:** `active`, `featured`, `type`, `status` de tabela pequena e
> as chaves estrangeiras de catálogo. Um índice sobre duas ou três chaves distintas custa escrita e o
> planejador o ignora.

**Uma fila faz outra pergunta, e ela é o que o índice de `status` responde.** Uma tela pergunta *o que
esta marca escreveu*, e uma passada pergunta *o que ainda não foi trabalhado* — e essa segunda procura
justamente o valor **raro**: umas poucas linhas pendentes no meio de milhões já liquidadas. É aí que uma
coluna de poucos valores distintos paga um índice, e por isso seis existem:

| Índice | O que ele serve |
| --- | --- |
| `app_event_status_queue` | a passada que reivindica o que o cliente reportou |
| `outbound_email_queue` | a passada que envia o que está na fila |
| `integration_webhook_event_status` | o recolhimento do que falhou ou ficou tomado |
| `subscription_benefit_due` | o ciclo que venceu e ainda não foi entregue |
| `subscription_benefit_grant_status` | a concessão que falhou ou ficou abandonada |
| `stored_file_waiting` | a varredura do arquivo que ninguém reclamou |

**O índice cobre a consulta que a tela faz, não a coluna isolada.** Um recurso `managedByParent` é
sempre lido **com o filtro do pai**, e aí o índice certo é `(pai, ordenação)`.

### Ordenar é ordenar até o fim

**Toda listagem desempata pelo `id`, e isso não é enfeite.** Um banco é livre para devolver as linhas
empatadas na ordem que quiser, e com `limit`/`offset` isso significa **a mesma linha em duas páginas e
outra em nenhuma**. `apply_ordering` fecha a ordem com a chave, na mesma direção, e `label_ordering`
faz o mesmo no lookup.

Vale para toda coluna que repete: `position`, `name`, `status`, `price`, e até `created_at`.

**E ordenar por coluna anulável diz o que fazer com o nulo.** O MySQL e o SQLite leem o nulo como o
menor valor e o PostgreSQL como o maior, então quando a ordem **decide qual linha responde** o nulo se
diz por predicado — nunca com `nullslast()`, que compila nos três e sai como sintaxe que só um aceita:

```python
.order_by(WebhookEvent.occurred_at.is_(None), WebhookEvent.occurred_at.desc())
```

### Uma marca, ou muitas, e o ambiente é que diz

**O `settings.multi_tenant` decide, e nunca uma consulta ao banco** — cadastrar o primeiro tenant não pode
mudar as regras da instalação em silêncio. O padrão é **falso**, porque um produto começa com uma marca.

| | marca única | muitas marcas |
| --- | --- | --- |
| o site | não procura host nenhum, e responde no escopo nulo | o host **tem** que casar com `Tenant.domain` |
| a API | não exige `X-Tenant-Code`, e **recusa** um que venha | exige, sempre |
| o que é gravado | `tenant_id` nulo em tudo | o tenant resolvido |

> **Recusar o cabeçalho onde ele não significa nada** é o que impede duas formas de dizer qual site é
> este. Aceitá-lo e ignorá-lo seria a segunda.

**O `dev` herda a marca única do `config/base.py`**, porque um produto começa com uma marca e é nela que
quem desenvolve desenvolve. **`stage` declara muitas**, porque alguma coisa tem que exercitar o modo que
tem mais o que dar errado, e **`prod` declara uma** — declara em vez de herdar, porque produção afirma
tudo o que ela é. Alinhar os dois é a primeira coisa que quem parte do template faz.

**E a suíte declara o modo dela**, ao lado do banco, do storage e do captcha: ela roda em muitas marcas,
e `tests/test_single_brand.py` desliga isso para provar a outra.

**O `make seed` enche a marca que o ambiente serve, e é por isso que ele costura `Brand` e não
`Tenant`.** Em marca única ele não escreve tenant nenhum e tudo nasce no escopo nulo; em muitas marcas
ele monta as duas do `TENANTS` como sempre. Sem isso, um `make seed` num dev de marca única grava
banner, plano, assinatura e membro dentro de um tenant que o site daquele modo não alcança — o catálogo
aparece e **não há plano, banner nem conta com que entrar**.

> **O seed é omitido da cobertura**, então nenhuma suíte prova esses dois caminhos: quem os prova é
> rodá-lo. O de marca única é o `make seed`, e o de muitas é um roteiro que aponta a configuração para
> um banco descartável — nasce fora do repositório, roda, e some.

### `Tenant` não é só escopo, e por isso existe o `Brand`

A linha de tenant carrega a identidade da marca — o nome que vai em todo `<title>` e no JSON-LD, a pasta
que sobrescreve o template, o domínio dos links que saem por e-mail, o endereço do contato. Sem tenant
nenhum não haveria de onde ler isso.

**O `helpers/brand.py` é a peça que os dois modos produzem**, e nada além dela lê `Tenant` direto:

| O que | Muitas marcas | Marca única |
| --- | --- | --- |
| `id` | o id do tenant | **nulo** |
| `code` | `tenant.code` | vazio, e o site desenha só o `global/` |
| `name` | `tenant.name` | `settings.name` |
| `domain` | `tenant.domain` | `settings.site.domain` |
| `email_contact` | `tenant.email_contact` | `settings.email.from_address` |

> **O `id` é nulo de propósito, e não um zero.** `reaches_tenant(coluna, None)` já significa *as linhas
> sem tenant*, então o modo de marca única funciona **sem um `if` em cada consulta** — as mesmas
> predicadas respondem certo nos dois.

**E todo endereço absoluto sai de `Brand.address(path)`**, nunca do host da requisição: o canonical, o
`og:url`, o JSON-LD, a linha `Sitemap:` do `robots.txt`, todo `<loc>` do `sitemap.xml`, a url de retorno
do checkout e os links que saem por e-mail. Seguir o cabeçalho `Host` é deixar quem perguntar com o host
que quiser receber um sitemap inteiro apontando para lá.

### O painel confina quem pertence a uma marca

**Um operador com `tenant_id` preenchido é respondido a marca dele e nenhuma outra**, e o que ele
cadastra nasce nela.

| A conta que opera | O que a listagem e o lookup respondem |
| --- | --- |
| `tenant_id` nulo | tudo |
| com tenant, `reaches_shared` falso | só as linhas da marca dela |
| com tenant, `reaches_shared` verdadeiro | as dela **mais** as compartilhadas |

**`User.reaches_shared` é propriedade da conta**, com padrão falso, e um administrador é quem concede.
Ela governa **ler**: escrever numa linha compartilhada deixaria uma marca reescrever o que a outra lê.

**Criar carimba, e não pergunta.** Um payload que nomeie outro tenant não é recusado, é ignorado — o
service escreve o do operador. Ler, editar e excluir a linha de outra marca respondem **404**, porque a
linha de outro não existe, que é a mesma regra do lado do cliente.

**Um filho é confinado pelo pai, e nunca por uma coluna que alguém acrescentou nele.** `reaches_through`
é a declaração — a chave com que ele aponta, o model que ele aponta, e como **aquele** chega a um tenant
quando ele também não tem: `subscription_benefit_grant` chega em dois saltos, e a declaração encadeia.

**Três recursos não têm como ser confinados, e é por natureza:** um país, um idioma e a própria lista de
marcas não pertencem a marca nenhuma. Eles declaram `system_wide`, e um operador que pertence a uma
marca recebe **403** neles.

**Uma chave estrangeira que o payload nomeia tem que apontar para uma linha que o operador alcança**, e
a recusa é `error.related-not-found`. Confinar a leitura sem confinar a referência deixaria um operador
plantar uma foto na galeria de outra marca, e ela apareceria no site público dela. A checagem usa a
mesma predicada do confinamento, resolvida pelo service do model que a chave aponta, e a varredura que
acha esse service percorre a árvore inteira em vez de um nível dela.

**E o painel não desenha o que ele não alcança.** `/api/meta/permissions` deixa esses três de fora para
quem é confinado — um item de menu que responde 403 é pior do que item nenhum — e responde `confined`,
que é o que faz o formulário **parar de desenhar o campo de tenant** em vez de oferecer uma opção só
para algo que o servidor decide sozinho.

### Escopo por tenant

Coluna `tenant_id` anulável nos models compartilháveis, onde **nulo significa que todo tenant
alcança**. Filtre sempre com `helpers.scope.reaches_tenant`:

```python
statement.where(reaches_tenant(Product.tenant_id, user.tenant_id))
```

Nunca `tenant_id.in_([id, None])` — em SQL, `IN (id, NULL)` não casa com linha nula.

E quando o que importa é **em qual escopo a linha está**, e não o que ela alcança, use
`belongs_to_tenant`: é o que faz uma identidade ser única dentro de um tenant. As unicidades que
envolvem tenant coalescem o nulo em zero, porque num índice único comum nenhum nulo é igual a outro e
dois registros globais iguais passariam.

---

## Autenticação e permissão

### Quem alcança o quê, e onde isso está escrito

**Um papel decide, e ele se declara num lugar só.** `helpers.auth.requires(*roles)` é a única guarda de
papel do projeto, e `get_administrator` é `requires(UserRole.ADMINISTRATOR)` — não existe uma segunda
forma de dizer quem entra.

**Quem trabalha no painel é nomeado um a um, e nunca derivado.** `PANEL_ROLES` lista `editor` e
`administrator`, e **um papel novo não alcança nada até alguém escrever que ele alcança**. Uma regra
escrita como *todo papel menos um* entrega o painel ao papel que for acrescentado ao enum, no dia em que
ele nasce, sem ninguém ter decidido isso — o que uma permissão nunca pode fazer é se conceder sozinha.

> **A mesma regra vale para toda permissão daqui:** `CrudService.roles` nasce nomeando o administrador e
> `lookup_roles` espelha uma lista escrita à mão. Nenhuma delas é *todos menos um*, e uma trava lê a
> declaração e recusa se ela voltar a ser.

**Um recurso diz quem o gerencia, e um catálogo diz quem o resolve.** São duas coisas diferentes:

| Declaração | O que ela decide | Padrão |
| --- | --- | --- |
| `CrudService.roles` | quem lista, lê e escreve o recurso | o administrador |
| `CrudService.lookup_roles` | quem resolve ele como **opção do formulário de outro** | o mesmo que `roles` |

> **Dar um recurso a um papel é dar o que aquele recurso pode fazer.** O corpo de um conteúdo é
> renderizado como markup de propósito — é o que um editor escreve no TinyMCE —, então **quem alcança
> `contents` põe HTML, e portanto script, em toda página pública do site.** Isso não é um furo: é o custo
> de entregar as páginas a alguém, e quem entrega precisa saber. `tests/test_access.py` prova que é isso
> mesmo que acontece.

> **E o painel desenha esse markup onde ele não alcança nada.** O JWT do painel vive no `localStorage`,
> então um `onerror` gravado por um editor rodaria dentro da origem autenticada de um administrador que
> abrisse aquele registro — escalada de papel de verdade, e não a exposição que o parágrafo acima aceita.
> A pré-visualização é um `iframe` com `sandbox`, e **não há sanitizador**: um sanitizador é uma lista
> que se contorna, e aquele markup existe para ser renderizado. O que muda é **onde**.

> **Sem a segunda declaração, um formulário fica impossível de preencher.** O editor gerencia conteúdo, e
> o conteúdo aponta para idioma e tenant — que ele não gerencia. Sem poder resolver aqueles dois lookups,
> o formulário dele desenha dois campos vazios que nunca respondem. `tests/test_admin_contract.py` falha
> quando um formulário oferece uma opção que quem o lê não consegue resolver.

**O registro do que a aplicação serve é derivado, e não acumulado.** `build_readonly_router` pendura no
router que ele devolve o par nome-service, e `helpers/router.py` monta o `RESOURCES` a partir dos
routers que ele **registra**. Um router construído e nunca registrado não entra em lugar nenhum, e uma
fábrica que escrevesse num dicionário global faria o `/api/meta/permissions` responder um recurso que a
aplicação não serve.

**O painel não declara papel nenhum.** Ele pergunta em `GET /api/meta/permissions` **o que esta conta
alcança** — nunca o mapa inteiro, que numa rota aberta contaria a forma do sistema para quem não entrou
— e desenha o menu com a resposta. Uma trava falha se uma definição de recurso ganhar um `roles`.

| Superfície | Onde o papel é declarado |
| --- | --- |
| um recurso de CRUD | `CrudService.roles`, e a fábrica aplica o que o service declarou |
| uma rota escrita à mão | a anotação dela: `AdministratorUser`, `CurrentUser`, ou `Depends(requires(...))` |

Trocar quem alcança um recurso inteiro é **uma linha no service**. Acrescentar um papel é um valor no
`UserRole` mais a declaração de quem passa a alcançar o quê.

**E o mapa inteiro está escrito num arquivo.** `tests/test_role_matrix.py` nomeia toda rota aberta e
toda rota de conta, e prova contra a aplicação rodando que:

| O que ele prova | Como |
| --- | --- |
| toda rota do `/api` está classificada | o que não é aberta nem de conta é administrativa, e a soma tem que fechar |
| o que é de conta recusa quem não tem sessão | 401 sem token, e nunca 401 com um |
| o que é aberto responde sem token | nenhuma delas devolve 401 |
| o que é administrativo recusa um leitor | **403 em todas**, uma a uma |
| todo recurso nomeia um papel | e o papel é um valor do enum |
| a fábrica é o único lugar que guarda um recurso | a dependência aparece uma vez no arquivo |

> **Uma rota nova falha essa trava até alguém decidir de quem ela é.** Essa derivação por subtração é
> segura porque o que sobra é **testado a recusar um leitor** — uma que **concedesse** por subtração não
> seria.

**De quem é a linha** é a outra metade, e ela é provada em `tests/test_ownership.py`: um leitor contra as
linhas de outro, pela API e pelo site, mais o cabeçalho de tenant, que diz **qual marca está sendo lida**
e nunca move a conta que está lendo.

### O que a API é, e o que ela não é

**A API se autentica por `Authorization: Bearer <jwt>` e por mais nada.** Um aplicativo não guarda
cookie, então não existe sessão de cookie no `/api`:

| | O site | A API |
| --- | --- | --- |
| quem é a pessoa | um cookie `httponly` com o mesmo JWT | o cabeçalho `Authorization` |
| o que prova que o pedido veio de quem diz | o token de CSRF, porque um cookie viaja sozinho | nada, porque **nada viaja sozinho** |
| um desafio de captcha | desenhado na página | buscado em `GET /api/meta/captcha` |

**O cookie do site não é credencial da API**, e é justamente isso que faz a API não precisar de CSRF —
um site de terceiro pode disparar uma requisição, mas não pode escrever o cabeçalho `Authorization`.
O `tests/test_security.py` prova as três coisas: o cabeçalho entra, o cookie do site não, e **nenhuma
resposta do `/api` grava cookie nenhum**.

### Toda tentativa de alcançar o que não é seu está escrita como um teste

O `tests/test_access.py` é a outra metade de `test_security.py`: aquele é sobre **entrar**, este é sobre
**alcançar**. Ele roda contra a aplicação e cobra, uma a uma:

| O que se tenta | O que responde |
| --- | --- |
| um papel alcançando recurso que o service não deu | 403 em **todos** eles, um por um |
| um catálogo que um papel resolve, lido como recurso | resolver e ler são permissões diferentes: 200 no lookup, 403 na listagem |
| perguntar outra coisa a um lookup, por filtro | 422, porque um filtro que a listagem não declarou é recusado e não ignorado |
| um username que forjaria uma linha do registro | 422, no cadastro e no painel |
| um login que não existe | o mesmo código, o mesmo corpo e o mesmo hash de um que existe |
| a linha de outra conta, por id e por listagem | 404 e lista vazia |
| nomear papel, tenant, dono, saldo ou contador da trava num payload | 422 |
| a chave de idempotência de outra conta | duas contas nunca dividem espaço de nomes |
| o mapa de quem alcança o quê, sem conta | 401 |
| um token de conta bloqueada | 401 |
| adivinhar a senha de uma conta para trancar outra | a contagem é da conta adivinhada, e só dela |
| um `X-Request-Id` com quebra de linha | substituído, porque ele chega inteiro num log |
| uma chave de webhook que ninguém sorteou | 404 |
| entrar num tenant com a identidade de outro | `error.invalid-credentials` |

### Um destino que um operador escreve é conferido

**O `url` de um banner vai direto para o `href` da home pública**, e quem alcança `banners` é o
**editor** — um `javascript:alert(1)` gravado ali executaria script no navegador de todo visitante.

**A regra mora no tipo**, e são dois porque as duas perguntas são diferentes:

| Tipo | O que ele aceita | Onde |
| --- | --- | --- |
| `LinkUrl` | outro site, ou um caminho **deste** — nunca um esquema que o navegador executa | o destino de um banner |
| `ReturnUrl` | só absoluto, porque é o gateway que vai alcançá-lo | o retorno de um checkout |

> **O regex do Pydantic v2 é o do Rust, e não tem look-ahead.** Um que use um falha ao **construir o
> schema** — no import, e não numa requisição.

O `tests/test_intrusion.py` percorre nove formas de escrever um destino que um navegador executaria, e as
recusa uma a uma.

### Toda tentativa de entrar está escrita como um teste

O `tests/test_security.py` é a lista das coisas que alguém tenta, e ela roda contra a aplicação:

| O que se tenta | O que responde |
| --- | --- |
| **SQL na busca, no filtro, na ordenação, no login, na tag e no cabeçalho de tenant** | o termo é higienizado antes de qualquer dialeto, o filtro que a coluna não lê é 422, e a ordenação que ninguém declarou é 422 |
| **um id que não cabe na coluna** | 422 antes da consulta, porque um número maior do que um `BigId` guarda estoura dentro do driver |
| **markup no nome, no tenant, num aviso** | o autoescape do Jinja, e o único HTML confiado é o que um operador escreveu no corpo de uma página |
| **um token forjado, sem algoritmo, com o papel trocado, de senha antiga, de conta apagada ou bloqueada** | 401, e o papel dentro do token não decide nada |
| **um `next` apontando para fora** | `inside`, e o teste percorre dezessete formas de escrever outro host |
| **uma chave de arquivo que sobe de pasta** | recusada onde é escrita **e** no storage, que recusa a chave que sai da raiz |
| **nomear `role`, `tenantId`, `id` ou `token` num payload de cliente** | o schema é fechado, e o papel não muda |
| **um campo maior que a coluna, um `limit` sem teto, um corpo que não é JSON** | 422 |
| **um cabeçalho carregando outro cabeçalho** | nada disso chega na resposta |
| **um formulário do site vindo de outro lugar** | o cookie de CSRF, que um terceiro não lê nem escreve |
| **markup vestido de imagem, e extensão que a finalidade não aceita** | os bytes são decodificados, e a extensão é conferida antes |

> **O que a lista assume, e é decisão:** o desafio de imagem **não guarda estado**, então ele prova que
> alguém resolveu um desafio há pouco e não que cada chamada teve o seu. Um token vale até expirar, e o
> que segura repetição é o rate limit. Torná-lo de uso único pede estado compartilhado, que é
> exatamente o que o desenho evita.

### Um valor assinado é assinado para uma coisa

Quatro valores saem daqui assinados com a mesma chave e entregues a qualquer visitante — o desafio, o
nome do visitante, o flash e a resposta sobre cookies. **O propósito entra no HMAC**, então `sign` e
`unsign` recebem o para quê, e um valor assinado para um fim **não verifica** como outro. Sem isso, um
token de desafio colado no cookie de flash responde 500 em toda página do site.

### O que toda resposta carrega

**Uma defesa que o navegador cobra vale mais do que uma que ele confia.** Três cabeçalhos saem em toda
resposta, do site, do painel e da API:

| Cabeçalho | O que ele impede |
| --- | --- |
| `X-Frame-Options: SAMEORIGIN` | o login do painel e as páginas da conta desenhados dentro da página de um terceiro, que é onde alguém coleta o que a pessoa digitou |
| `X-Content-Type-Options: nosniff` | o navegador adivinhar o tipo de um arquivo servido em `/media` e executar o que ele adivinhou |
| `Referrer-Policy: strict-origin-when-cross-origin` | o endereço inteiro de uma página de conta vazar no referer de um link que sai daqui |

**Não há CSP, e isso é decisão.** O corpo de um conteúdo é markup que um operador escreveu no TinyMCE, e
uma política que valesse a pena escrever quebraria o editor e o estilo embutido que ele gera. Uma CSP
que libera tudo o que este site já faz não impede nada, e escrevê-la seria dizer que existe uma defesa
onde não existe.

### Uma resposta que é de um leitor só diz isso

**A requisição disse quem está perguntando, ou a resposta diz** — sessão, `Authorization` ou um cookie
escrito —, e aí ela sai `private, no-store`. Toda página deste site cunha um token de CSRF por
visitante, e a home responde páginas diferentes para quem tem sessão e para quem não tem: um cache
compartilhado que guardasse isso entregaria o token e o cookie de um visitante a todo mundo.

**O que é servido do disco fica de fora**, porque um arquivo nunca depende de quem pediu e mandar o
navegador não guardá-lo é buscar toda imagem de toda página de novo.

**E um site que se declara `https` manda HSTS**, para o navegador não voltar a falar http com aquele
host — a primeira requisição em texto claro é justamente a que alguém intercepta. Quem decide é o
`scheme` que a instalação declara, e `hsts_max_age` zerado é ela dizendo para não mandar.

### Um corpo que este processo lê inteiro tem teto

**Ler um corpo inteiro na memória é o jeito de derrubar um processo com uma requisição só**, e não com
muitas — o rate limit conta chamadas, e uma basta. Quem responde por isso é `helpers/payload.py`, um
middleware montado por último para ficar por fora de todos os outros.

| O que chega | O que acontece |
| --- | --- |
| `content-length` acima do teto | recusado com **413**, sem ler byte nenhum |
| `content-length` dentro do teto | passa direto, porque o servidor não entrega mais do que ele disse |
| sem comprimento, com `transfer-encoding` | contado enquanto chega, e recusado no byte que passa do teto |
| `multipart/form-data` **num endereço que recebe arquivo** | não é medido aqui: o upload transmite para o disco e cobra o teto da finalidade dele |

O `request_max_bytes` é 1 MB, que é ordens de grandeza mais do que qualquer JSON desta API pede. O
`upload_max_bytes` continua sendo outra coisa, e continua sendo 512 MB.

> **O cabeçalho é escolha de quem chama, então ele nunca decide se um corpo é medido.** A isenção vale
> para o **endereço** que recebe arquivo, e não para o content-type que a requisição diz carregar — quais
> são esses endereços sai da aplicação, procurando `UploadFile` na assinatura de cada rota, então um
> upload escrito depois é transmitido sem ninguém lembrar de nada.

> **E a isenção é derivada, então ela é cobrada.** Uma rota escrita depois com um `UploadFile` na
> assinatura **toma a isenção sem pedir**, e o que ela não pode tomar é ficar sem limite nenhum: uma trava
> percorre as rotas isentas e cobra que cada uma alcance a regra da finalidade dela.

> **A rota mais exposta é a do webhook**: ela é aberta, um estranho a alcança, e ela lê o corpo cru
> porque a assinatura é conferida sobre ele. Sem teto, um `POST` de dois gigabytes derruba o processo
> inteiro — o site, o painel e a API junto.

> **Um `nginx` na frente não resolve.** Ele é opcional aqui, e o `client_max_body_size` dele é 512 MB
> justamente porque o upload precisa disso.

### O que outra máquina respondeu se lê de um jeito só

**O `helpers.remote.body_of` é a única forma de ler o corpo de uma chamada a terceiro**, e ela responde um
mapa ou um dicionário vazio. Um `.json()` cru levanta quando o corpo não é JSON, e um 200 com uma página
de manutenção dentro vira **500 nosso** em vez de recusa.

| Quem chama | O que um corpo ilegível significa |
| --- | --- |
| o reCAPTCHA | recusa, que é o que a regra sempre disse: só uma aprovação limpa passa |
| o código postal | não achado |
| o RevenueCat | uma conta sem nada, que a reconciliação trata como qualquer outra |
| o checkout | `error.checkout-refused`, porque uma sessão sem endereço é uma sessão que não abriu |

> **E um endereço sem cidade e sem estado não é um endereço.** O ViaCEP responde 200 com o corpo vazio
> em alguns casos, e devolver isso enche o formulário de campos em branco como se a busca tivesse
> funcionado.

### O que custa cpu não roda no laço que responde todo o resto

**Um processo assíncrono tem um laço só, e o que segura esse laço segura a requisição de todo mundo.**
Não é o total de trabalho que importa e sim quanto tempo o laço fica parado: enquanto ele calcula, a
sonda de saúde, a página do site e a leitura da API esperam.

| O que | Onde ele roda |
| --- | --- |
| o argon2 de um login | `asyncio.to_thread`, porque um hash custa dezenas de milissegundos de cpu |
| o banco de fusos | uma constante `TIMEZONES`, lida uma vez, porque ele não muda enquanto o processo vive |
| desenhar o desafio de imagem | onde está, porque um milissegundo e pouco não paga uma thread |

**A lista de fusos que o painel desenha é exatamente o conjunto contra o qual a API valida**, porque é o
mesmo valor.

> **Uma trava cobra que a senha seja processada fora da thread principal**, senão o dia em que alguém
> "simplificar" o `to_thread` volta a congelar a frota sem nada acusar.

### As duas sondas dizem coisas diferentes

| Sonda | O que ela responde | Quem lê, e o que faz com isso |
| --- | --- | --- |
| `GET /api/meta/health` | que **este processo responde**, sem tocar em nada | o orquestrador, que reinicia quando ela cala |
| `GET /api/meta/ready` | que **esta cópia consegue servir**, perguntando ao banco | o balanceador, que para de mandar tráfego quando ela recusa |

**Reiniciar não conserta um banco morto**, e é por isso que a de liveness não pergunta a ele: um banco
fora do ar reiniciaria a frota inteira em laço. A de readiness pergunta com prazo — `readiness_timeout`
— e responde **503** quando não é atendida, que é o que faz **uma** cópia drenar em vez de todas
recusarem requisição.

> **A sonda de saúde é `/api/meta/health`, e apontá-la para `/health` é pior do que não ter sonda.** A
> raiz é do site, então `/health` responde **200 com uma página** — uma sonda ali diz que está tudo bem
> com a API fora do ar.

### Uma senha errada é contada na conta

**O rate limit conta endereço, e a conta é o que está sendo adivinhado.** Ele também conta na memória de
um processo, então com quatro workers em dez nós um endereço só ganha quarenta vezes o orçamento. E
`POST /api/signin` **não pede captcha** — só o site e o login do admin pedem.

| O que acontece | O que a conta responde |
| --- | --- |
| senha errada | conta mais uma, e responde `error.invalid-credentials` |
| a conta de `sign_in_attempts` fecha | ganha uma espera que **dobra** a cada erro seguinte, até `sign_in_cooldown_max` |
| senha certa dentro da espera | `error.too-many-attempts`, porque só quem já sabe a senha é mandado esperar |
| senha errada dentro da espera | `error.invalid-credentials`, o mesmo de sempre |
| senha certa depois da espera | entra, e zera o contador |

> **Quem está adivinhando nunca vê a espera**, e é isso que impede a trava de virar um jeito de
> descobrir quais contas existem. Um login que não nomeia ninguém responde igual e não conta nada.

**E um login que não existe paga o mesmo hash de um que existe.** A senha é conferida contra
`no_such_account`, um hash de um valor sorteado no import — um `and` que curto-circuitasse antes do
argon2 conta pelo tempo da resposta quais contas existem.

**A contagem é feita pelo banco, num `UPDATE`, e não por este lado.** Ler o valor e escrever de volta
perde uma contagem toda vez que duas tentativas chegam juntas, e o que se perde ali são tentativas que
quem adivinha ganha de graça.

**Ninguém exclui a linha em que está logado.** A auditoria da exclusão apontaria para alguém que já não
existe.

### O painel deixa rastro

**A fábrica escreve no `system_log` quem criou, editou, excluiu e reordenou o quê**, na categoria
`admin`. É um lugar só para os 31 recursos, porque a fábrica é um lugar só.

**Nada do corpo entra no registro.** Um payload carrega senha e chave de gateway, e um registro de
auditoria é lido por mais gente do que o formulário foi.

**E o painel não é só CRUD.** `audit.written` é uma função que qualquer rota chama com o autor, e é o
que cobre o que a fábrica não construiu: conceder crédito à mão, forçar uma entrega. Quem cobra isso é
`tests/test_admin_audit.py`, que percorre **toda escrita administrativa da aplicação rodando** — o que
não vem da fábrica e não chama `audit.written` tem que estar nomeado no `UNTRACKED`, com o motivo
escrito.

> **O que um administrador fez sobrevive ao que ele apagou.** Apagar um tenant leva as linhas daquele
> tenant, e a linha que diz quem o apagou é do administrador, que é global.

### Uma requisição tem nome

O `helpers/tracing.py` lê o `X-Request-Id` que vier ou cunha um, guarda num `ContextVar` e devolve no
cabeçalho. O log carrega o nome em toda linha, e a auditoria o grava junto do que foi feito. Um nome que
não caiba no formato aceito é **substituído**, porque ele chega inteiro numa linha de log.

### A chave de criptografia pode girar

**O `security.encryption_keys` é uma lista: a primeira escreve e todas leem.** Sem isso, trocar a chave
torna todo segredo de integração ilegível — em silêncio, até um webhook falhar a autenticação.

```
1. põe a chave nova na frente da lista
2. faz o deploy
3. roda `manage.py rotate-secrets`
4. tira a antiga da lista, e faz o deploy de novo
```

**A reescrita recusa em vez de escrever por cima do que não conseguiu abrir**, com
`error.secret-unreadable`: gravar de novo um segredo ilegível o substituiria por nada, e ninguém saberia
até um gateway ligar.

**E ela lê o schema em vez de uma lista que alguém mantém.** `RotationService.stored` percorre todo
model do registry atrás de coluna terminada em `_encrypted`, então um model que ganhar um segredo depois
é reescrito sem ninguém precisar lembrar.

### Uma escrita que o cliente nomeia acontece uma vez

**Um aplicativo que repete o `POST` do checkout abriria duas sessões no gateway e duas compras.** As
duas rotas de checkout honram `Idempotency-Key`, e a chave é **tomada antes de o trabalho começar** —
duas chamadas que só olhassem primeiro fariam as duas o trabalho.

| O que a chave encontra | O que a rota responde |
| --- | --- |
| ninguém a tomou | esta chamada faz o trabalho e guarda a resposta nela |
| já tem resposta | a mesma resposta, sem abrir nada |
| tomada e ainda sem resposta | 409, porque a primeira chamada ainda está respondendo |
| tomada há mais de 5 minutos e sem resposta | esta chamada assume, porque a primeira morreu |
| tomada por outra rota | 409, porque uma chave nomeia uma escrita e não duas |

**Assumir a chave de uma chamada que morreu é um `UPDATE`, e não um `if`.** `take_over` marca
`claimed_at` numa escrita condicionada a ela ainda estar sem resposta e ainda estar vencida — ler a
janela e depois decidir deixa as duas chamadas que a leram juntas fazerem as duas o trabalho.

**E é `claimed_at` que a janela mede, nunca `created_at`.** Assumir move o momento em que o trabalho
foi tomado, e a linha continua nascida quando nasceu — medindo pelo nascimento, toda chamada seguinte
encontraria a chave vencida para sempre.

**A chave é da conta que a usou**, então dois clientes nunca disputam o mesmo espaço de nomes. Ela vive
numa linha de `ClientRequest`, que guarda a conta, a chave, o endereço que a nomeou, quando o trabalho
foi tomado e a resposta que aquele endereço deu. **E ela tem janela de retenção**, porque uma chave por
checkout nomeado é mais uma tabela operacional que cresceria para sempre.

### Um endereço que o servidor recusou para de receber

**Só a recusa do destinatário suprime o endereço**, e nunca um 5xx que é da nossa configuração: uma
credencial errada também responde 5xx, e suprimir um leitor de verdade por causa dela seria silencioso.

| O que o servidor diz | O que acontece |
| --- | --- |
| 5xx recusando o **destinatário** | a mensagem fica `refused`, e o endereço entra na supressão |
| 4xx | tenta de novo, como sempre |
| 5xx de autenticação ou de remetente | tenta de novo: é a configuração que está errada, não o leitor |

**A fila não disca para quem está suprimido** — ela grava a linha como `refused`, para que fique o
rastro de que houve tentativa. E a supressão **não é podada** pela retenção: ela é o que impede escrever
para o mesmo endereço morto para sempre.

### As nove perguntas que toda API nova responde

| # | A pergunta | A trava |
| --- | --- | --- |
| 1 | **Quem pode chamar?** Ou tem guarda, ou está nomeada na lista de abertas com o motivo escrito | `tests/test_route_guards.py`, `tests/test_role_matrix.py` |
| 2 | **De quem é a linha?** Se recebe identificador, o dono da sessão vai para a consulta, e o que não é dele **não existe** | `tests/test_route_guards.py`, `tests/test_ownership.py` |
| 3 | **O cliente pode nomear o dono?** Nunca. `user_id`, `tenant_id`, `role` e saldo só existem num payload que **só o administrador** alcança | `tests/test_api_restrictions.py` |
| 4 | **Isso escreve o que o motor escreve?** Assinatura, direito, benefício, concessão, extrato, compra, posse, evento e registro são **somente leitura** na API | `tests/test_api_restrictions.py` |
| 5 | **O que ela responde é dela?** Ordenação e filtro que a API não aplica são recusados, não ignorados | `tests/test_admin_contract.py` |
| 6 | **Cabe na coluna?** Todo texto que um cliente manda tem `max_length`, nunca maior que o `String(n)` | `tests/test_api_restrictions.py` |
| 7 | **O cliente pode nomear uma chave de arquivo?** Um leitor nunca — ele manda o arquivo, e a rota escreve a coluna | `CrudService.ensure_files_are_of_their_purpose` |
| 8 | **Ela responde uma lista que cresce sem fim?** Toda listagem de cliente pagina, porque uma linha por evento de gateway não tem teto | `tests/routes/test_subscription.py` |
| 9 | **Todo número que ela lê tem teto?** Identificador, filtro, `offset` e número de página são recusados acima do que uma coluna guarda | `tests/test_security.py` |

**A sexta existe porque o que o banco recusa vira 500 e o que o schema recusa vira 422.** Todo texto
livre declara `FREE_TEXT_MAX`, que são 16.000 caracteres — o que cabe num `Text` do MySQL mesmo se cada
caractere custar quatro bytes.

**E um texto que a linha tem que ter não é um branco.** `Text(n)` é o tipo — apara o espaço, exige um
caractere e carrega a largura da coluna —, e uma trava percorre todo schema de escrita cobrando que a
coluna que a tabela declara obrigatória não aceite branco.

> **E quem deixou o campo em branco é avisado disso, e não de um comprimento.** Pedir ao menos um
> caractere é pedir alguma coisa em vez de nada, e as duas são frases diferentes: um nome em branco lê
> que não pode ficar em branco, e um username de duas letras continua lendo o comprimento que falta.

**A oitava existe porque o que cresce por fora não pergunta.** Uma conta antiga acumula um lançamento
por ciclo e um aviso por evento de gateway, e uma listagem sem teto responde a tabela inteira num
corpo só. Extrato, compras e os avisos de uma assinatura paginam, na API e no site.

**A sétima existe porque uma coluna de arquivo não guarda um texto, guarda um alvo de exclusão.** Uma
linha que para de mencionar um arquivo é o que apaga aquele arquivo do storage. Como as chaves viajam
para os clientes, apontar o `avatar` para a imagem de um produto e depois trocá-lo apagaria essa imagem
do bucket.

**Por isso `file_fields` é um mapa de coluna para finalidade, e não uma lista de nomes.** Uma declaração
diz as duas coisas: onde a chave pode apontar, e o que apagar quando a linha muda ou some. A fábrica
recusa a chave que não estiver na pasta daquela finalidade, e `tests/test_admin_contract.py` falha se um
campo de arquivo do admin não tiver a mesma finalidade do lado do service.

| Quem | Como ele preenche uma coluna de arquivo |
| --- | --- |
| um leitor | **nunca a nomeia** — ele manda o arquivo em `POST /api/account/avatar` e a rota escreve a coluna |
| um administrador | nomeia a chave que o upload dele respondeu, e a fábrica recusa qualquer pasta que não seja a da finalidade daquela coluna |

**A nona existe porque um número grande demais não é recusado pelo banco: ele estoura dentro do
driver.** `BIG_INTEGER_MAX` e `INTEGER_MAX` são declarados uma vez, ao lado do `BigId` de que o
primeiro é o teto, e todo lugar por onde um número entra lê um dos dois:

| Onde ele entra | O que carrega o teto |
| --- | --- |
| o identificador no caminho | `RecordId` |
| o filtro na query | o `coerce` de `helpers/crud.py`, que recusa antes de a consulta existir |
| o `offset` de qualquer listagem | `ListingOffset`, que é o mesmo em `CurrentPage` e nas três listagens de cliente |
| o `page` de uma listagem do site | `page_number`, que responde a primeira página para o que uma página não pode ser |
| **o corpo de uma escrita** | `Reference`, `Position`, `Quantity`, `IntervalValue` e `Amount`, em `schemas/common.py` |

> **A regra é o teto da coluna e não um número escolhido.** O SQLite guarda o que lhe derem, então um
> `position` além de 32 bits passa em toda a suíte e responde *out of range* no MySQL:
> `tests/test_sql_portability.py` compila cada tabela no dialeto do MySQL, lê a largura de cada coluna e
> cobra que todo inteiro que um cliente escreve caiba nela.

> **Uma listagem que escreve os próprios limites à mão é a que fica de fora.** As três listagens de
> cliente leem `ListingLimit` e `ListingOffset`, que são os mesmos que a fábrica usa — repetir
> `Query(50, ge=1, le=200)` em cada uma é como as três nasceram sem teto de `offset`.

> **E o número é lido antes de ser convertido.** Acima de alguns milhares de dígitos é o próprio
> `int(texto)` que levanta, então `page_number` compara o comprimento com o da última página antes de
> converter — do lado do filtro esse levantar já vira 422, porque `coerce` roda dentro de um `try`.

**O que o motor escreve, e por quê**, está declarado em `ENGINE_OWNED`:

| Tabela | De onde a linha vem |
| --- | --- |
| `Subscription` | do que o gateway responde, nunca de uma requisição |
| `UserEntitlement` | do motor de entrega |
| `SubscriptionBenefit` | do retrato tirado na ativação |
| `BenefitGrant` | de um ciclo entregue uma vez, com a chave que diz isso |
| `CreditTransaction` | é append-only, e um saldo se corrige com outra movimentação |
| `Purchase` | é aberta por este lado antes de o gateway ver, e liquidada pelo que ele responde |
| `UserProduct` | de um pagamento ou do motor, nunca de um POST |
| `AppEvent` | o cliente reporta em lote, o cron fecha |
| `WebhookEvent` | o que o gateway disse é o que ele disse |
| `SystemLog` | **um registro de auditoria em que alguém escreve deixa de ser um** |
| `OutboundEmail` | uma mensagem entra na fila pelo service que a redigiu, e nunca por um POST |

> **A exceção do administrador é explícita e é uma só:** `CreditTransactionCreate` nomeia a conta,
> porque conceder crédito a alguém é o que um operador faz.

### Um identificador que o cliente escolheu não é uma permissão

O `tests/test_route_guards.py` percorre cada rota de `routes/` e cobra: ou ela tem guarda, ou está
**nomeada** numa lista de abertas, e se recebe identificador no caminho, **entrega o dono à consulta**.

A segunda é a que importa: uma rota pode declarar `CurrentUser` e nunca passar o `user` adiante, e ao
ler o código isso parece protegido. A trava só aceita `user.id`, `user.token` ou o `user` passado ao
service.

As abertas carregam o motivo no próprio teste: entrar, cadastrar, o `admin/signin`, a recuperação de
senha, os idiomas oferecidos, o `/api/meta`, o `/api/meta/health`, e o webhook, cuja credencial é a
chave sorteada no caminho.

**As rotas de CRUD não aparecem uma a uma** porque nascem da fábrica, e é lá que o
`Depends(get_administrator)` está declarado — um teste separado cobra aquela linha.

### A conta

- **Toda conta nasce com um `token`**, um UUID único no banco inteiro. É por ele que a conta é nomeada
  fora daqui, e o id numérico nunca atravessa a rede da aplicação.
- **A conta é criada com pelo menos uma de quatro identidades:** username, e-mail, CPF ou celular.
  Quem valida é `UserService.ensure_identity`, no cadastro e na edição.
- Login por **qualquer uma das quatro, no mesmo campo**. `user_service.find_by_login` resolve.
- **A identidade é única dentro do tenant, não no sistema.** Quem garante é um índice **funcional**
  sobre `COALESCE(tenant_id, 0)` — num índice único comum `NULL != NULL`, e dois globais com o mesmo
  e-mail passariam.
- A coluna `role` é um enum de três valores: `normal`, `editor` e `administrator`, e o painel nomeia os dois últimos um a um.
- Só administrador entra no admin. `/api/admin/signin` recusa conta normal mesmo com a senha certa.
- O **JWT não expira**, de propósito. O que corta o acesso é o `status` da conta, não o relógio.
- **O `sub` do JWT é o token da conta, não o id.**
- **O papel viaja no token e a autorização nunca o lê.** `get_administrator` consulta o papel no banco,
  então tirar o administrador de alguém vale na hora.
- Senha com argon2. Segredo de integração com Fernet.

### A conta é confirmada pela identidade que ela tem

Apagar a conta pelo site pede que a pessoa digite a identidade dela de volta, e essa identidade é a
primeira que ela tiver entre e-mail, username, CPF e celular — **nessa ordem**, que é a que uma pessoa
reconhece, e não a ordem em que as quatro são validadas. Pedir o e-mail seria pedir o que metade das
contas não tem.

### O escopo em que um login é resolvido

| Caminho | Resolve em | Como sabe |
| --- | --- | --- |
| `/api/signin`, `/api/signup`, `/api/account/password-reset` | o tenant que chamou | `X-Tenant-Code`, **obrigatório** |
| o site | o tenant do host | `Tenant.domain` |
| `/api/admin/signin` | o escopo global | não tem tenant, e não precisa |

**O administrador é global**, e é isso que desempata o admin. Por isso `create-administrator` não tem
`--tenant`.

Entrar num tenant onde a identidade não existe responde `error.invalid-credentials` — o mesmo que uma
senha errada, então a resposta nunca conta em que tenant alguém tem conta.

### O nome pelo qual uma conta é chamada

Uma cascata, não um campo: `nickname`, depois `first_name` + `last_name`, depois `email`, `username`,
`mobile_phone`, `cpf`, e por último `#<id>`.

**Ela existe uma vez, em `helpers.text.display_name`**, e é de lá que saem os três lugares que nomeiam
uma conta: o `build_label` do lookup, o campo `displayName` da API, e o que o site mostra.

### A senha, e o que trocá-la significa

**Uma senha nova encerra toda sessão que a antiga abriu**, e quem a trocou **continua dentro**.

Quem faz isso é `User.session_epoch`, um contador. Todo JWT carrega o `epoch` com que foi emitido, e
`AuthService.settle_password` avança o da conta. A rota de troca responde o token novo.

**E ela queima o token de recuperação que estivesse pendente.**

**O `User.token` não é tocado, e isso é o ponto.** Ele é o identificador que o gateway conhece —
sorteá-lo de novo deixaria a assinatura paga apontando para ninguém.

| Campo | Para que serve | Quando muda |
| --- | --- | --- |
| `token` | nomear a conta fora daqui | nunca, exceto no apagamento |
| `session_epoch` | dizer quais sessões ainda valem | a cada troca de senha |
| `failed_sign_ins` | contar o que está sendo adivinhado | a cada senha errada, e zera ao entrar |
| `sign_in_blocked_until` | até quando a conta para de responder | quando a contagem fecha, dobrando a cada erro seguinte |

> **No dia em que o token passar a expirar, o `session_epoch` sai junto** — ele existe como
> consequência de o JWT não expirar.

### O token de recuperação é uma credencial

`POST /api/account/password-reset` é uma rota **aberta**, e por isso responde **204 e corpo vazio**,
sempre — login que existe, login que não existe e conta sem e-mail respondem idêntico. Senão a rota
vira uma forma de perguntar quem tem conta aqui. `tests/routes/test_password_reset.py` falha se o token
aparecer numa resposta.

**E um endereço recebe uma recuperação por janela.** A rota é aberta e não pede desafio nenhum, então
cada chamada geraria um token novo e enfileiraria mais um e-mail: a caixa de quem nunca pediu nada
enche, e **o token que a vítima está segurando é queimado a cada pedido**, de modo que o link legítimo
dela nunca funciona. A janela é tomada com um `UPDATE` condicionado ao `recovery_token_created_at`,
como toda janela deste projeto, e `password_reset_interval` é de 60 segundos. A resposta é a mesma
dentro e fora da janela.

Um envio que falha **não vira erro para quem chamou**: vira linha `error` no registro do sistema.

### O direito ao esquecimento

`DELETE /api/account/me` **anonimiza**, e é `UserService.erase` quem faz — apagar a linha levaria junto
assinatura e extrato, que são registro de dinheiro e não dado pessoal.

O que é sobrescrito, todos com valor **sorteado**: `username`, `email`, `cpf`, `mobile_phone`,
`password_hash` e `token` — este último é o que **desloga em todo aparelho**. `first_name`,
`last_name`, `nickname`, `avatar`, `notes` e `meta` ficam vazios, e `status` vira `erased`.

O e-mail sorteado usa o TLD reservado `.invalid` (RFC 2606).

**O que vai embora junto** é comportamento: os eventos reportados e os endereços.
**O que fica** é transação: assinatura, extrato, compras e o que a conta possui. **Isso é uma decisão,
não um esquecimento.**

**A conta apagada não volta a responder.** A guarda de sessão recusa `erased` antes de qualquer rota.

---

## Contratos da API

Todo endpoint fica sob `/api/<modulo>`. Hoje são 176 caminhos em 40 grupos, sobre 35 tabelas.

### A API fala camelCase

**Todo nome de campo que atravessa a rede é `camelCase`**, e o Python continua `snake_case`. Quem faz a
ponte é o `alias_generator` do `BaseSchema`. **E toda peça que atravessa a rede é construída nele**,
sem exceção — `Page`, `PageParams`, `LookupItem`, `LookupResponse` e `ReorderRequest` inclusive. Uma
trava percorre os schemas que a aplicação carrega e recusa o que não está sobre a base, porque o dia em
que uma delas ganhar um campo de duas palavras a listagem inteira responde um nome em snake_case ao
lado de todos os outros.

Isso vale para o corpo, para o filtro na query, para o `ordering` e para o mapa `errors`.

O que **não** vira camelCase, porque não é nome de campo: valor de enum, nome de enum no `/api/meta`,
chave de tradução, header e as chaves de dentro de um `dict` opaco.

**Listagem** — `GET /api/<recurso>?limit=&offset=&search=&ordering=&<filtros>`

```json
{ "count": 0, "limit": 50, "offset": 0, "items": [] }
```

O `limit` é 50 por padrão e no máximo 200. `ordering` aceita `campo` ou `-campo`, e só os declarados —
**um que não esteja declarado é recusado com 422**, e não trocado pelo padrão em silêncio.

**E a mesma regra vale para o filtro: um parâmetro que a listagem não conhece é recusado com 422**,
nomeando qual foi. Quem digitou `tenant_id` em vez de `tenantId` receberia **a lista inteira** e a
leria como filtrada.

**Lookup** — `GET /api/<recurso>/lookup?search=&limit=&<filtros>`, máximo 50, padrão 20. E
`GET /api/<recurso>/lookup/{record_id}` responde uma opção só, para o formulário resolver o valor que
já carrega sem procurar na primeira página.

**Erro** — sempre o mesmo formato, em qualquer status:

```json
{ "code": "error.product-out-of-tenant", "detail": "…", "errors": { "productId": "…" } }
```

**E isso vale para a recusa do rate limit também.** A biblioteca devolveria um 429 sem corpo e sem
content type — página em branco para quem lê no navegador, e nada para quem integra —, então ela recebe
uma fábrica de resposta que monta o mesmo `code`/`detail`, com o `Retry-After` que ela calculou.

**E o que responde GET responde HEAD.** Uma rota declarada pela fábrica do FastAPI honra exatamente os
métodos escritos, e quem pergunta com HEAD primeiro é justamente quem este site existe para atender: um
buscador, um verificador de link, o desdobrador de link de um mensageiro, e um monitor de uptime. Quem
responde é `helpers/head.py`, que reescreve o método antes do roteamento — acrescentar o método na rota
daria a cada uma um gêmeo HEAD no `/docs`, dobrando a documentação que quem integra lê.

### A busca: prosa é uma coisa, identificador é outra

| Lista | Para | Como responde | Exemplo |
| --- | --- | --- | --- |
| `text_search_fields` | prosa | prefixo de palavra, com índice | `name`, `title`, `first_name` |
| `search_fields` | identificador | qualquer pedaço, com `LIKE` | `slug`, `cpf`, `reference`, `email` |

Ninguém lembra metade de um nome, e todo mundo lembra o meio de um número.

**Só entra em `text_search_fields` coluna `String`.** Um `Text` fica de fora: indexá-lo custa mais do
que a busca nele vale.

**O termo é higienizado antes de chegar a qualquer dialeto.** `helpers/search.py` tira todo caractere
que algum banco leria como sintaxe. O InnoDB **levanta erro de sintaxe** com `apple+` ou `@`.

**A semântica é a mesma nos três bancos.** Cada um só a expressa com o que tem de mais rápido: MySQL
com `MATCH … AGAINST` em modo booleano, PostgreSQL com `to_tsquery`, SQLite concatenando as colunas.

**Uma palavra que o índice não guarda é descartada, nunca exigida.** O InnoDB não indexa nada abaixo de
`innodb_ft_min_token_size`, que é **3** — a truncação não salva a palavra curta ali, ao contrário do
MyISAM.

> **Armadilha:** o MySQL só responde `MATCH … AGAINST` se existir índice `FULLTEXT` cobrindo
> **exatamente** aquelas colunas. Por isso `text_search_fields` e `search_index(...)` andam juntos, e
> `tests/helpers/test_search.py` falha se um existir sem o outro.

> **Em produção:** `make migrate` cria tabela que falta, e **não** adiciona índice em tabela que já
> existe. Um `text_search_fields` novo num banco publicado exige o `ALTER TABLE … ADD FULLTEXT` à mão.

### Um recurso escrito uma vez por idioma

`LocalizedService` guarda a regra uma vez: **o idioma pedido vence, o inglês responde pelo que ele não
tem, o tenant vence o compartilhado, e a listagem responde uma linha por chave.** Quem herda dela diz
qual é a chave, no `localized_key`.

| Base | A chave | Quem usa |
| --- | --- | --- |
| `TaggedService` | `tag` | `content` e `gallery`, lidos por um endereço que carrega a tag |
| `PlanService` | `code` | o plano, que é o mesmo produto vendido uma vez por mercado |

> **A listagem e a tag têm que concordar.** Um card que mostra um título e abre outro é pior que card
> nenhum, e um `sitemap.xml` com o mesmo endereço duas vezes é o mesmo erro visto de fora.

**E a chave é única dentro do tenant e do idioma, nas três.** `language_scoped_unique` é o índice
funcional que diz isso, pelo mesmo motivo de sempre: num índice único comum nenhum nulo é igual a outro,
e uma linha que não nomeia tenant nem idioma ficaria de fora. `tests/services/test_crud.py` percorre todo
`LocalizedService` e cobra o índice, porque essa chave é um **endereço** — sem ela, dois títulos que
reduzem ao mesmo slug salvam os dois, o endereço abre um deles, e o outro é uma página que o operador
criou, que ninguém alcança e sobre a qual nada foi dito.

**Um plano tem idioma, e é ele que decide em que moeda o preço está escrito.** O mesmo `code` existe uma
vez por idioma — `monthly` em USD para quem lê em inglês e em BRL para quem lê em português — e a
listagem, a página de planos e o checkout respondem sempre a linha do idioma de quem está lendo. Sem
isso o comprador veria um preço e pagaria outro.

**O idioma é opcional**, e um plano que não nomeia nenhum é o plano de todo mundo. A unicidade é
`(tenant_id, code, COALESCE(language_id, 0))`, num índice funcional pelo mesmo motivo da identidade.

> **O que isso não é:** tradução de tela. O nome e a descrição de um plano são conteúdo daquele mercado,
> e não a mesma frase em outra língua — quem vende no Brasil pode vender outro pacote por outro preço.

### O aplicativo faz o que o site faz

**O site e o aplicativo são o mesmo produto**, então tudo que uma pessoa faz numa página tem endereço na
API. Quem prova isso é `tests/routes/test_app_parity.py`.

| O que a pessoa faz | No site | Na API |
| --- | --- | --- |
| entrar, cadastrar, recuperar senha | `/account/login`, `/account/signup`, `/account/password-recovery` | `POST /api/signin`, `/signup`, `/account/password-reset` |
| ler e editar a conta | `/account`, `/account/profile` | `GET` e `PUT /api/account/me` |
| trocar de idioma | `POST /account/language` | `PUT /api/account/me` com `languageId`, e a lista em `/api/languages/active` |
| endereço | `/account/address` | `GET /api/account/addresses`, `PUT` e `DELETE` por finalidade |
| **países e código postal** | o formulário do endereço | `GET /api/countries/offered` e `GET /api/countries/{code}/postal-code/{cep}` |
| **os planos à venda** | `/plans` | `GET /api/subscriptions/plans` |
| produtos à venda | `/products` | `GET /api/commerce/products` |
| **pagar** | `POST /checkout/product/{slug}` | `POST /api/commerce/products/{slug}/checkout` e `/api/subscriptions/plans/{code}/checkout` |
| assinaturas e seus pagamentos | `/account/subscriptions` | `GET /api/subscriptions/me` e `/{subscription_id}/transactions` |
| compras | `/account/purchases` | `GET /api/account/purchases` e `/{purchase_id}` |
| produtos que possui | `/account/products` | `GET /api/account/products` |
| saldo e extrato | `/account/credits` | `GET /api/account/balances` e `/api/account/credits` |
| **falar com o operador** | `/contact` | `POST /api/contact` |
| **newsletter** | `/newsletter` | `POST /api/newsletter`, `/confirm/{token}`, `/unsubscribe/{token}` |
| apagar a conta | `/account/delete` | `DELETE /api/account/me` |

**Onde a API pede o que o site não pede:**

| Rota | O que ela pede a mais | Por quê |
| --- | --- | --- |
| o checkout | `successUrl` e `cancelUrl` | o site conhece o próprio endereço e um aplicativo só conhece o dele, e os dois têm que ser `http` ou `https` |
| o código postal | uma sessão | ela chama um terceiro, e uma rota aberta seria a cota dele aberta também |
| contato e newsletter | o mesmo desafio de captcha do site | um formulário que qualquer um manda é um formulário que qualquer um inunda, e o desafio vem de `GET /api/meta/captcha` |

> **O checkout do site não carrega chave de idempotência, e isso é decisão.** A chave existe na API
> porque **um aplicativo repete o `POST` sozinho** quando a rede falha, e um navegador não — o clique
> duplo abre no máximo uma segunda compra `pending`, que o próprio gateway fecha com o evento de
> expiração, sem cobrança dupla. E o token de CSRF não serviria de chave: ele nomeia a **página**, não a
> compra, então dois produtos abertos na mesma janela dividiriam a chave e o segundo receberia a
> resposta do primeiro.

> **O link de confirmação da newsletter aponta para o site mesmo quando quem assinou foi o aplicativo.**
> Ele é clicado num cliente de e-mail e não dentro do aplicativo, e sai de `Brand.address` como todo
> endereço absoluto.

> **Comprar dentro de um aplicativo de loja não passa por aqui.** iOS e Android exigem a compra da
> própria loja para conteúdo digital, e é o RevenueCat que responde por ela — este checkout é o caminho
> de quem vende pela web.

### As duas superfícies do mesmo dado

| Quem | Schema | O que carrega |
| --- | --- | --- |
| admin | `ProductSchema` | as colunas cruas, `image` e `file` como chave de storage |
| cliente | `CatalogProductSchema` | `imageUrl` resolvido, mais `owned` |
| admin | `BannerSchema` | `image` como chave |
| cliente | `ActiveBannerSchema` | `imageUrl` resolvido |

**A regra:** o que um cliente lê nunca recebe chave de storage, recebe endereço. Quem resolve é o
`storage.url` dentro do service, nunca o cliente montando caminho.

**E o que as duas superfícies respondem igual é montado uma vez.** O produto, o banner e a galeria são
respondidos por schemas diferentes de cada lado, de propósito — o plano não é, e o mesmo
`CatalogPlanSchema` é montado ao lado do schema que os dois leem, que é o único lugar onde acrescentar
um campo não pede que alguém lembre do outro lado.

**E o arquivo é a habilitação:** o `fileUrl` de um produto só é construído em
`GET /api/account/products`, que é a única superfície que já sabe que quem pergunta o possui.

> **E o que guarda esse arquivo é o endereço, não uma checagem.** O `url` é o endereço nu do bucket, e é
> isso que faz uma imagem ser servida sem passar por este processo — o bucket é lido por qualquer um
> porque a política dele diz isso, e nunca porque um upload pediu. O que impede alguém de baixar o
> arquivo de um produto que não comprou é o uuid da chave, que não se adivinha, e **não** uma permissão
> conferida na hora. Isso tem duas consequências que quem publica precisa saber: um endereço que vazou
> vale para sempre, e um reembolso não devolve o produto. Trocar isso é trocar o endereço nu por um
> assinado com prazo, e aí o `url` deixa de ser um endereço e passa a ser uma chamada.

**Todo recurso que um cliente endereça carrega um UUID sorteado.** O `id` autoincremental continua sendo
a chave interna dos relacionamentos, e os schemas de admin, referência e cliente de banner, moeda,
produto, conteúdo, categoria, galeria, foto e plano também respondem `uuid`. Uma trava percorre esse
conjunto e cobra coluna, unique nomeado e campo em todo schema que o expõe.

### O espaço promovido, e o que ele conta

**Um banner é um espaço, e o `placement` diz qual.** Hoje são quatro — a home do site e três espaços que
o aplicativo desenha —, e um espaço pede só o que é dele. Ele carrega ainda a janela `starts_at`/`ends_at`,
a `position`, o `active` e a imagem.

**Ele tem idioma, pela mesma regra de todo catálogo daqui:** um banner que não nomeia idioma é o banner
de **todo** leitor, exatamente como uma linha sem tenant é de todo tenant. O site passa o idioma da
página e a API o do `Accept-Language`.

**E ele é endereçado pelo `uuid`.** O `ActiveBannerSchema` não responde `id`: o autoincremental diz
quantos existem, e é o `uuid` que um cliente conta uma view e um click por.

| O que | Onde |
| --- | --- |
| listar o que está vivo agora | `GET /api/banners/active?placement=` |
| contar que foi visto | `POST /api/banners/{uuid}/view` |
| contar que foi seguido | `POST /api/banners/{uuid}/click` |
| pedir um nome para ser contado por | `GET /api/meta/visitor` |

**Uma view conta uma vez por visitante e por dia**, e quem garante isso é
`UNIQUE(banner_id, kind, visitor, day)` — não é um `if`, é a chave. `Banner.views` e `Banner.clicks` são
o total agregado, e **eles só andam para quem escreveu a linha**: quem perde a corrida recebe a linha do
vencedor e não soma nada, que é a mesma regra do extrato. O incremento é um `UPDATE` do banco, porque ler
e escrever de volta perde toda contagem que chega junto.

**Sem consentimento de `analytics` nada é contado**, e isso não é enfeite: contar um leitor é exatamente
o que aquela categoria nomeia. **E a página nem pede**: o `data-banner` só é escrito onde a contagem
vale, então o script não acha o que ligar e ninguém que respondeu não — ou não respondeu ainda — gasta
duas chamadas por página num pedido que o servidor ia recusar, nem o orçamento de rate limit daquele
endereço. O nome é sorteado com `secrets`, assinado, e vive num cookie `httponly` que a página não lê —
retirar a permissão o apaga.

**O site conta pela própria API, como o aplicativo faz**, e não por uma segunda rota: a página carrega o
código do tenant e o script manda o cabeçalho. Um `IntersectionObserver` conta a view quando o banner
chega na tela, e o `fetch` vai com `keepalive` para não segurar o clique. **Sem JavaScript o link
funciona e nada é contado.**

> **O corpo aceita um nome porque um aplicativo não tem cookie**, e por isso `GET /api/meta/visitor`
> existe: sem ele o campo era uma porta sem chave, já que só este lado assina um nome e nada entregava um.

**A tabela de impressões é operacional e tem janela**, e os totais agregados **não** — eles sobrevivem à
poda, senão a retenção apagaria a contagem histórica junto com a deduplicação.

### O cache guarda a resposta montada

**[Cachefy](https://github.com/paulocoutinhox/cachefy) com a entrada no mesmo banco da aplicação**, do
mesmo jeito que o Queuefy guarda a fila — `SqlAlchemyStore(async_engine)`, e a tabela `cachefy_entry`
mora num `MetaData` da biblioteca. Por isso ela é criada pelo `helpers/schema.py`, ao lado do
`Base.metadata` e do metadata da fila: são três, e uma lista só.

**O cache não guarda query. Guarda o conteúdo final montado** — o mapa ou a lista depois que idioma,
tenant, relacionamentos e endereços de storage já viraram a resposta que o site ou a API consome. Quem
faz isso é `catalogue.fetch`, que lê a chave e só no vazio roda o produtor e grava.

A chave nomeia a superfície e **tudo** que muda a resposta: tenant, idioma, tag, slug, placement e termo
de busca. Uma parte de fora é um tenant lendo a página de outro. **E ela é limitada por construção**,
porque uma `tag` não é: as partes viram um digest, e a superfície continua legível na linha — uma chave
maior do que a coluna que a guarda é recusada pelo MySQL ou **truncada na chave de outra página**.

**Cada coisa tem o espaço dela, e cada espaço tem o tempo de vida dele.** São sete, e o motivo é que
uma busca e uma política de privacidade não envelhecem no mesmo relógio:

| Espaço | Vive | Por quê |
| --- | --- | --- |
| `search` | 30 s | o conjunto de chaves é aberto, então ele é o que menos deve acumular |
| `home` e `banners` | 60 s | é a página que mais muda de mão |
| `products` | 120 s | um catálogo muda quando alguém edita, e não sozinho |
| `plans`, `content`, `gallery` | 300 s | é conteúdo que fica parado por semanas |

**A superfície entra na chave, e não no nome do espaço.** A API e o site montam o mesmo produto em
formatos diferentes, então `surface=api` e `surface=site` são chaves diferentes dentro do mesmo espaço —
e limpar `products` limpa as duas, porque é a mesma coisa vista de dois lados.

**O `cache.enabled` é do ambiente.** O `dev` não liga, e é isso que faz uma edição no painel aparecer no
pedido seguinte. **Editar no painel não invalida nada:** a entrada vale até o tempo de vida do espaço
dela, e a retenção derruba o que já morreu pelo `purge` da própria biblioteca.

> **Não existe store muda, e isso é decisão da biblioteca:** ela recusa tempo de vida zero com
> `CacheError`, dizendo que é *"a value already dead where it is written"*. Então "desligado" não é um
> provedor dela e sim o ambiente dizendo que não liga o cache, exatamente como o `cron_enabled` faz com
> o worker.

**O que a biblioteca promete, e muda o desenho:** uma store inalcançável é **miss e nunca exceção**, um
montador só roda enquanto os outros esperam, e ausência é distinguida de `None`.

**E um valor que nenhuma store grava é recusado na escrita, com um aviso no log.** Isso é o pior tipo
de falha: o cache simplesmente **nunca funciona, e nada quebra**. Uma entrada é JSON onde quer que ela
viva, e o JSON tem **um** tipo numérico só, o float do IEEE 754 — então um `Decimal` não tem
representação lá, e `19.90` viraria `19.899999999999998578915`.

**O cache é transporte, e quem devolve o tipo é o schema.** A montagem sai por
`model_dump(mode="json")` e **volta pelo mesmo schema**, que reconstrói o `Decimal` exato a partir do
texto. Escrever `str(preço)` na montagem seria mudar o dado para agradar o transporte, e aí a página
passaria a desenhar um tipo diferente conforme o cache estivesse ligado ou não.

O `tests/helpers/test_cache.py` dirige **toda** superfície que o código guarda e falha se qualquer uma
delas for recusada, cobrando junto que o conjunto que ela dirige seja o conjunto que o código guarda.

`CatalogProductSchema.owned` nunca entra no valor compartilhado. O catálogo é `CatalogEntrySchema`, que
não tem posse nenhuma, e cada requisição preenche `owned` depois — guardar o mapa já personalizado
entregaria o produto de uma conta para outra.

### E-mail

Nada é discado na requisição. `email_service.queue` escreve a linha em `outbound_email` e commita, e o
cron `send_pending_emails` envia a cada dois minutos.

**A linha é reivindicada antes de ser discada, e não depois.** `claim` marca `sending` num `UPDATE`
condicionado a ela ainda estar `pending` — sem isso, duas instâncias com a tag `email` leem a mesma
fila e a pessoa recebe a mesma mensagem duas vezes. E `reclaim_abandoned` devolve para `pending` o que
passou de `ABANDONED_AFTER`.

**Uma mensagem para uma conta é escrita no idioma daquela conta**, e não no da requisição que a
disparou. `email_service.to_user(db, tenant_id, user, subject_key, template, **context)` é o único
jeito de mandar uma: ele resolve o idioma pela `language_id` da conta, traduz o **assunto** nele, e
grava esse idioma na linha — que é o que `deliver_record` fixa antes de renderizar o corpo.

O `queue` continua existindo para a mensagem que **não** vai para uma conta, como o contato que chega ao
operador, e ela grava o idioma da requisição.

O corpo é um template Jinja2, sempre HTML:

```
templates/global/email/base.html            o que vale para todo mundo
templates/tenants/<code>/email/base.html    o que aquele tenant sobrescreve
```

**O tenant vence, o global responde pelo que ele não tem, e o que não existe em nenhum dos dois
levanta.** Um template que falta é configuração a corrigir, e nunca um servidor a derrubar.

**E um nome que o template lê e o contexto não tem levanta também.** O Jinja responde vazio por padrão,
então `{{ brnad.name }}` escreveria um buraco na página e seguiria adiante. O ambiente é
`StrictUndefined`, e como a suíte desenha **toda** página do site e renderiza toda mensagem da fila, um
nome errado falha onde ele é escrito e não onde ele é lido.

**O nome que a fila guarda é o nome nu do template**, porque quem envia monta o caminho com ele:
`f"email/{template}.html"`. Um nome carregando a própria pasta vira `email/email/contact.html.html`, que
não existe. `tests/services/test_email.py` varre toda chamada de `queue` e de `to_user` e cobra que o
template exista **e que a chamada entregue todo nome que aquele template lê** — o `link` que falta num
convite não derruba nada, ele só chega em branco na caixa de alguém. Os nomes que o remetente sempre
põe — `t`, `language`, `brand` e `subject` — são o `FRAME`, e ninguém precisa passá-los.

**Uma mensagem que pede resposta carrega `reply_to`.** O remetente é o endereço do sistema, então sem
isso a resposta do operador vai para o sistema e nunca para quem escreveu.

**E a recuperação de senha carrega o endereço, não só o código.** A página de reset lê o token do
caminho e de lugar nenhum, então um código sem link é um código que ninguém consegue usar — o link é
para quem está no site, e o código continua ali para quem está no aplicativo.

**Um endereço suprimido é uma linha de `SuppressedAddress`, e ela não é podada.** A retenção apaga o que
nenhuma regra vai ler de novo, e essa vai ser lida em toda mensagem escrita dali em diante.

**A fila é lida no admin, e o `context` dela não.** `outbound-emails` mostra para quem, qual template,
o estado, as tentativas e o erro — e nunca o contexto de onde a mensagem foi escrita, porque o de uma
recuperação de senha **carrega o token dentro**.

### Idioma

**Três idiomas: inglês, português e espanhol.** Quem os declara é `settings.languages`, um mapa de
código para o nome pelo qual quem fala aquele idioma o chama — e é dele que saem a lista de idiomas
oferecidos, o catálogo carregado, as bandeiras do rodapé e o `/api/meta`. Um só lugar.

| Superfície | Como o idioma é resolvido |
| --- | --- |
| a API | o header `Accept-Language` |
| o site | a conta, senão o cookie, senão o `Accept-Language` — nesta ordem |
| um e-mail | **o idioma da conta que recebe**, gravado na linha da fila |

Toda mensagem está traduzida nos **três** catálogos: `locale/en.json`, `pt.json` e `es.json`. Ao
adicionar uma chave, adicione nos três — e o mesmo vale para os três catálogos do admin.

**Ninguém precisa lembrar disso.** `tests/test_messages.py` percorre `settings.languages` e cobra as
quatro direções: a chave que um catálogo tem e outro não, a que o código nomeia e nenhum guarda, a que
sobrou depois de a regra sair, e o valor de enum que a API publica sem rótulo em algum deles. Do lado
do admin, `tests/i18n/index.test.js` cobra o mesmo, mais a chave que uma tela pede por literal e nenhum
catálogo guarda — comparar catálogos **entre si** nunca acha a que falta nos três.

**E uma quinta direção: o que a mensagem nomeia por dentro.** Quem chama passa um conjunto de valores —
`translate("email.password-reset-validity", hours=…)` —, então uma tradução que nomeia outro é
`KeyError` **só para quem lê naquele idioma**, num caminho que a suíte escrita em inglês nunca exercita.
As duas travas comparam os placeholders de cada chave nos três catálogos, dos dois lados.

**E `default_language` tem que estar entre os oferecidos.** Fora deles, **toda** mensagem levanta
`KeyError` — o processo sobe e depois responde 500 em toda página e toda rota. É um validador do
modelo, então ele falha no import e passa pelo `derive`.

---

## O site

O site é renderizado pelo mesmo processo que responde a API, com Jinja2. Um buscador e um visitante
leem o mesmo HTML, porque não há aplicação nenhuma no cliente decidindo o que é a página.

### Por que servidor e não SPA

Uma página que só existe depois que o JavaScript roda é uma página que o buscador recebe vazia. O site
existe para ser achado, então ele é HTML pronto — e as telas de conta, que precisam de sessão e
formulário, ficam mais simples assim do que com uma segunda aplicação e uma segunda camada de estado.

### Os caminhos

**Nenhum caminho carrega idioma.** Uma página é um endereço só, e ela é lida no idioma de quem a abre:

```
/                          a home
/about  /contact  /plans  /products  /products/{slug}  /newsletter
/gallery  /gallery/{tag}  /content/{tag}
/account/…                 tudo que precisa de sessão
/checkout/…                para onde o gateway devolve o comprador
/language                  POST: a escolha de idioma, e volta para a página de onde veio
/theme                     POST: a escolha de paleta, e volta para a página de onde veio
/cookies                   o que o visitante permite guardar, e o POST que grava a resposta
/newsletter/confirm/{token}  /newsletter/unsubscribe/{token}
/sitemap.xml  /robots.txt
```

Uma tag que nada responde é uma página que não existe. `/about` é um endereço com nome para a tag
`about` — o texto dele é um conteúdo que o operador edita como qualquer outro, e não um template, então
ele **não** é entrada estática do `sitemap.xml`: a varredura de conteúdo já o lista quando ele existe.

**E o que a navegação nomeia por tag ela só desenha se aquela tag responder.** `NAVIGATION` declara as
quatro — `about`, `terms`, `privacy` e `cookies` — com o endereço que cada uma abre, e `get_page`
resolve numa consulta só, pelo mesmo caminho que a página abriria, guardada no espaço de conteúdo. Sem
isso, apagar um conteúdo no painel deixa um link morto no rodapé de **toda** página do site.

### Em que idioma esta página está

Uma cascata, e ela para no primeiro que responde:

| Ordem | De onde vem | Por quê |
| --- | --- | --- |
| 1 | `user.language` | quem escolheu uma vez lê o mesmo idioma no próximo aparelho |
| 2 | o cookie `fastkit_language` | é o único lugar que sobra para quem não tem conta |
| 3 | `Accept-Language` | o que o navegador pediu, para quem nunca escolheu |

**Escolher é um POST**, porque escolher grava: `POST /language` escreve o cookie, escreve o
`language_id` de quem está logado, e devolve a pessoa para a página de onde ela veio. O campo `next`
é lido por `helpers.site.inside`, que só aceita um caminho **deste** site.

### Onde a pessoa estava indo

**Uma página que pede sessão guarda para onde a pessoa ia**, e entrar a coloca lá:

```
GET /account/address        ->  303 /account/login?next=%2Faccount%2Faddress
entrar                      ->  303 /account/address
```

O destino atravessa o caminho inteiro: o link para o cadastro leva o `next` junto, e cadastrar-se
termina no mesmo lugar. Quem já está logado e abre o login vai direto para onde ia.

**E voltar é sempre um GET, então um formulário nomeia a página em que ele foi desenhado.** O que uma
pessoa aperta para assinar é um `POST /checkout/plan/{code}`, e guardar **esse** endereço a mandaria de
volta para um caminho que não responde a GET. É a mesma forma que o `PageExpired` usa — o cabeçalho de
origem lido por `inside`, e a home quando não há um.

**E o campo é a única coisa da página que decide para onde o navegador vai, então ele é a única que
pode virar uma porta para fora.** `inside` desarma isso em três passos:

| Passo | O que ele impede |
| --- | --- |
| tira controle, espaço e barra invertida **antes** de olhar | um navegador também os tira, e `/\evil.test` é outro host para ele |
| exige uma barra só no começo | `//evil.test`, `///evil.test` e todo endereço absoluto |
| recusa o que é da API ou do painel | o site nunca entrega alguém em `/api` ou em `/admin` |

E `landing` recusa o próprio login como destino, porque voltar para a página de onde a pessoa acabou de
sair não é chegar a lugar nenhum. `tests/test_security.py` percorre dezessete formas de escrever outro
host contra os três lugares que aceitam um destino.

O rodapé desenha uma bandeira por idioma oferecido, e a conta tem a mesma escolha em
`/account/language`.

**Uma conta nasce lendo o que a pessoa já estava lendo:** `auth_service.register` grava a
`language_id` do idioma da requisição, então a primeira mensagem que ela recebe sai naquele idioma.

### A conta é uma lista de opções

**O perfil não é uma tela: é uma lista.** `/account` mostra o avatar, o nome e o saldo de cada moeda,
e abaixo uma opção por página. Cada uma abre uma página, e cada página volta para a lista.

**E a lista é agrupada pelo que cada coisa é**, porque oito opções seguidas não dizem qual delas
responde o quê: **o perfil** — dados pessoais, endereço, idioma e senha — e **o que a pessoa comprou** —
assinaturas, compras, produtos e créditos. O que ela alcança fecha a página, como sempre.

**Não existe barra de botões repetida em toda página**, e o motivo é concreto: uma barra com um `Sair`
desenhado como link acima do formulário da página é o primeiro `form` do documento, e quem aperta Enter
num campo sai do sistema em vez de salvar.

A exclusão da conta é uma seção de risco de verdade: um cabeçalho vermelho, o que ela apaga, o que ela
mantém, o campo que pede a identidade escrita à mão, e um caminho de volta.

### Um campo de arquivo mostra o que tem

O `<input type="file"` cru não desenha nada legível e não diz o que foi escolhido. O componente
`upload` do site desenha a caixa, o botão e o nome do arquivo, com o input invisível por cima — e
`webapps/site/src/upload.js` escreve o nome do que foi escolhido onde estava o rótulo vazio.

### O endereço começa pelo país

A ordem do formulário é **país, código postal, e o resto depois**, porque é o país que decide se o
código postal pode ser procurado. **Um endereço tem um complemento e não dois.**

| Peça | O que faz |
| --- | --- |
| `Country` | o cadastro: nome, código ISO 3166-1, e **qual provedor responde o código postal dele** |
| `helpers/postal_code.py` | o contrato e a implementação de cada provedor |
| `GET /account/address/postal-code` | o que o provedor achou, e só para uma sessão deste site |
| `webapps/site/src/postal-code.js` | ao sair do campo, mostra o aviso, busca, e **preenche só o que ainda está vazio** |

> **E só a última busca preenche.** O campo é preenchido enquanto está vazio, então a resposta **antiga
> chegando primeiro** o preencheria e a nova encontraria tudo cheio sem corrigir nada. Quem carrega toma
> um número e descarta o que chega depois de outro ter sido tomado.

**Um país sem provedor não pergunta a ninguém.** A página recebe a lista de países que têm um, e o
campo se comporta como qualquer outro para os demais.

> **O que veio da documentação do ViaCEP:** o endereço é `https://viacep.com.br/ws/<oito dígitos>/json/`,
> os campos são `logradouro`, `bairro`, `localidade` e `uf`, um CEP com qualquer outro formato responde
> **400**, e um CEP que não existe responde **200 com `erro`** no corpo. Por isso o comprimento é
> conferido antes de perguntar, e o corpo é o que diz que não foi achado.

**O `country_code` continua sendo o código e não uma FK**, porque ele é uma chave natural que viaja
para o gateway e para a etiqueta de entrega. Quem garante que ele existe é `UserAddressService`, que
recusa com `error.country-not-offered` o país que o cadastro não oferece.

### Um número é escrito do jeito que o país dele escreve

**`Country.phone_mask` é a forma, e ela é cadastro pela mesma razão que o provedor de código postal é:**
um operador a edita, cada país tem a sua, e **um país sem forma nenhuma desenha um campo comum**. O
zero da máscara é um dígito que alguém digita e o resto é literal — o Brasil nasce com `(00) 00000-0000`
no `make seed`.

| Peça | O que faz |
| --- | --- |
| `Country.phone_mask` | a forma, editável no painel e respondida em `GET /api/countries/offered` |
| `webapps/site/src/mask.js` | escreve a forma enquanto a pessoa digita, e nada mais |
| a macro `field(..., mask)` | carrega o `data-mask`, e sem máscara não carrega atributo nenhum |

**De que país é o número é o país em que a conta escreve o endereço dela**, que é o único sinal que a
página tem. Quem não tem endereço digita num campo comum.

**A forma e o número são duas grandezas, e por isso são limitadas separado.** O que é guardado é o
número — `dialled` derruba a pontuação —, então o schema aceita os 32 caracteres que a forma escrita
pode ter e **recusa o número que não couber nos 16 da coluna**. Medir a forma deixaria uma máscara mais
longa estourar um número que cabe, e medir só na coluna deixaria 32 dígitos chegarem num `String(16)`.

**E o site sem JavaScript continua funcionando**: a máscara é melhoria progressiva, e o servidor lê os
dígitos de qualquer forma que a pessoa tenha escrito.

> **Reescrever o valor de um campo joga o cursor para o fim**, então o lugar para onde ele volta é
> contado em **dígitos** e nunca em caracteres, porque a pontuação que a máscara escreve entra e sai
> enquanto alguém digita.

### A newsletter

**Ninguém entra sem o próprio endereço dizer que sim.** A inscrição nasce `pending`, o endereço recebe
um link, e só o clique a liga. O mesmo token é por onde ela sai.

Ela tem página própria — `/newsletter` — e não um campo no rodapé, e o motivo é o captcha: um desafio
desenhado no rodapé seria um desafio cunhado em **toda** página do site, para uma caixa que quase
ninguém usa.

**Um endereço que pede duas vezes é a mesma linha pedindo duas vezes**, resolvido por `insert_or_read`,
e um que já confirmou não recebe outro pedido de confirmação.

**E um que ainda não respondeu só é escrito uma vez por janela.** O duplo opt-in impede que alguém
inscreva outra pessoa, e não impede nada quanto a **escrever** para ela: dentro do rate limit um
formulário aberto mandaria trezentos e-mails por minuto para quem nunca pediu nada. `claim_invitation`
toma a janela com um `UPDATE` condicionado ao `invited_at`, e `INVITATION_INTERVAL` é uma hora — curto
o bastante para quem não viu a primeira mensagem pedir de novo, e longo o bastante para o formulário
não ser um megafone.

### Os cookies, e o que o visitante permite guardar

**Nada além do que o site precisa para responder é guardado antes de alguém dizer que sim.** As
categorias são um enum — `necessary`, `preferences`, `analytics`, `marketing` — e `settings.site.consent`
diz quais este ambiente pergunta. **`necessary` nunca está entre elas**, porque ninguém é perguntado
sobre o que faz a página existir, e um ambiente que a oferecesse é recusado no import.

| Peça | O que faz |
| --- | --- |
| `enums/consent.py` | as categorias |
| `helpers/consent.py` | `given` lê a resposta, `remember` a grava, `wanted` traduz o que o formulário disse |
| `/cookies` | a página onde a escolha é feita e refeita, e o `POST` que a grava |
| `partials/consent.html` | o aviso, desenhado **só enquanto ninguém respondeu** |
| a tag `cookies` do conteúdo | o texto da política, editado no painel como qualquer outro |

**Recusar tudo é um clique, exatamente como permitir tudo.** Os dois botões do aviso têm o mesmo peso
visual — um "aceitar" em destaque ao lado de um "recusar" apagado é o desenho que os reguladores
chamam de consentimento que não foi dado.

**A resposta é gravada com a versão da pergunta.** Mudar `consent.version` é perguntar de novo a todo
mundo, e um cookie escrito antes disso não responde pela pergunta de hoje. Uma categoria que o
ambiente parou de oferecer também para de estar permitida, mesmo que o cookie ainda a nomeie.

**E o consentimento tem consequência**, senão ele é enfeite: o idioma e a paleta são os cookies de
preferência que este site escreve, e eles **só sobrevivem à visita onde alguém permitiu** — sem
permissão a escolha vale para a visita e nada é guardado depois dela. Responder de novo reescreve **os
dois**, então retirar encurta o cookie que já existia em vez de deixá-lo mais um ano.

O nome assinado que deduplica view e click de banner também só existe com `analytics`. Ele fica num
cookie `httponly`, é preservado quando a mesma resposta é dada outra vez e é apagado quando a permissão
é retirada.

> **Retirar tem que ser tão fácil quanto dar**, e é por isso que existe uma página no rodapé além do
> aviso: um aviso que some depois de respondido seria a única chance de mudar de ideia.

**E o aviso ocupa o espaço que ele ocupa.** Ele é `sticky`, e não `fixed`: fixo ele não entra no layout
e **cobre o fim de toda página enquanto estiver de pé** — que é exatamente a primeira visita —, e o que
fica embaixo dele é o fim do rodapé, onde mora o seletor de idioma.

### De quem é a requisição

**O host diz.** `Tenant.domain` é único. Uma máquina sem domínio próprio nomeia um em
`site.default_tenant`. Sem default e sem casamento **não há site**, e a resposta diz isso — neutra para
quem pergunta, porque dizer ao mundo qual host não tem marca é contar como a instalação está
configurada, e com o host e o default que falharam **no log**, que é onde um operador procura.

### Um cookie é escrito de um jeito só

**Quatro atributos decidem quem lê um cookie e por onde ele viaja** — `httponly`, `secure`, `samesite` e
`path` —, e `helpers/cookies.py` é o único lugar que escreve um, com `remember` e `forget`. Escritos em
cada módulo eles concordam até o dia em que o sétimo cookie esquece um deles, e o que se perde ali é um
script passando a ler a sessão. `tests/test_security.py` falha se qualquer módulo escrever o seu.

### A sessão do site

Entrar cunha o mesmo JWT que a API responde e o guarda num cookie `httponly`. A página nunca o lê e
nenhum script alcança. Sair apaga, e trocar a senha cunha outro para este aparelho continuar dentro.

### As peças de uma página

Uma página do site é montada com as mesmas peças, e é por isso que todas se parecem:

| Peça | Onde |
| --- | --- |
| `page_header`, `card`, `empty`, `rows`, `row`, `submit`, `option`, `chevron`, `nav_link` | `partials/ui.html` |
| `field`, `area`, `choice`, `upload` | `partials/field.html` |
| a paginação | `partials/pagination.html` |
| as bandeiras e o seletor de idioma | `partials/flags.html`, `partials/language-selector.html` |

**Uma peça que existe e ninguém chama é pior do que peça nenhuma**, porque o markup dela acaba copiado
em cada página e mudar o card vira mudar onze arquivos. Elas são chamadas pela forma `{% call %}`, e
uma trava lê a forma da própria peça e recusa aquela escrita à mão — uma cópia dentro do verificador é
uma cópia que sobrevive ao que ela copiou.

> **Uma variante não é a peça.** Um card que é `<article>` por semântica, um que carrega margem própria
> e um que é grade continuam escritos onde estão — parametrizar o elemento leria pior do que repetir a
> superfície.

**O menu diz onde a pessoa está.** `nav_link` marca o item quando a página lida é a que aquele endereço
abre **ou uma abaixo dela** — `/gallery/office` marca Galeria e `/account/purchases` marca a conta —, e
quem responde isso é `Page.at`. A marca é peso, sublinhado e `aria-current="page"`, e nunca só a cor. A
home é o único endereço que marca só a si mesmo: toda página do site fica abaixo dela.

**Uma macro importada não enxerga o contexto de quem a importou**, então toda importação que usa `t`
carrega `with context`. Sem isso, a página quebra com `t is undefined` na primeira renderização.

**Nenhuma listagem é uma `<table>`.** Uma tabela rola de lado numa tela estreita, e o que se lê num
celular é uma lista de linhas que empilham. Toda grade vai de uma coluna para duas e só então para
três — `sm:grid-cols-2 lg:grid-cols-3` — porque saltar de uma para três aperta a tela de 700px.

### Formulário

| Guarda | Como |
| --- | --- |
| CSRF | o mesmo valor sorteado no cookie e num campo escondido, e só uma página deste site lê um para preencher o outro |
| Captcha | o que o ambiente declarar, conferido antes de qualquer escrita |
| Validação | os mesmos schemas Pydantic da API, lidos de volta como um mapa que a página marca o campo com |

**E esse mapa é indexado pelo nome com que a página desenhou o input, e nunca pelo nome da rede.** A API
fala camelCase e o `name` de um input não fala, então uma recusa de `mobile_phone` chega como
`mobilePhone` e a macro procuraria a outra: **o campo nunca seria apontado, e a página se redesenharia
sem dizer o que estava errado.** `tests/helpers/test_forms.py` percorre todo schema de formulário do
site e cobra que toda chave recusada seja um campo dele.

**Uma escrita responde um redirecionamento**, então recarregar nunca manda o formulário duas vezes. **E
um duplo clique também não manda:** o primeiro envio marca o formulário, o segundo é recusado antes de
sair, e o botão que enviou fica em estado de carregando. Ele **nunca é desabilitado**, porque um botão
desabilitado para de carregar o `name` e o `value` que o servidor lê — e vários botões deste site
carregam os dois. A marca também interrompe a propagação, senão o ouvinte do captcha, que está no mesmo
formulário, cunharia um token e o enviaria de novo por conta própria. O que a próxima página deve dizer
viaja num cookie de flash assinado, lido uma vez.

**Um formulário do site nunca sai pelo tratador de erro da API:**

| O que foi recusado | O que a pessoa vê |
| --- | --- |
| o desafio | a página desenhada de novo, com a mensagem no campo do captcha e **um desafio novo** |
| o token de CSRF | um redirecionamento de volta para a página de onde o formulário veio, com um aviso |

O CSRF é um redirecionamento e não uma página desenhada porque **o token velho não serve mais**: o que
a pessoa precisa é da página com um token que este site acabou de emitir. Quem faz isso é `PageExpired`,
que lê o cabeçalho de origem por `inside` e cai na home quando não há um.

> **O token de CSRF é double submit e não um valor assinado solto.** Um token assinado que qualquer um
> pode buscar num GET não prova nada — o que prova é o cookie, porque um site de terceiro não o lê nem
> o escreve.

### Uma página que quebra continua sendo uma página

O 404 e o 500 do site são **desenhados**, e não JSON: a forma de uma resposta é de quem a lê, então a
API continua respondendo JSON e o site responde a página. O que quebrou pode ser justamente o que a
página precisa para ser desenhada, então o tratador registra a segunda falha e responde o JSON — um
tratador que levanta responde corpo nenhum.

### SEO

Toda página carrega `<title>`, descrição, canonical e Open Graph. A home carrega a organização em
JSON-LD. O `sitemap.xml` lista **uma entrada por página**, mais uma por conteúdo, galeria e produto.

**E "uma por página" é toda página que responde a mesma coisa para todo mundo**, que é o critério que o
próprio `PUBLIC_PATHS` declara sobre si — uma página pública que fica de fora é uma página que existe e
que nenhum buscador tem como achar.

**Não há `hreflang` e não há endereço por idioma**, porque não há endereço por idioma para apontar.

**E o canonical é o endereço da página, nunca o endereço com que alguém chegou nela.** Saindo de
`request.url`, `/products?utm_source=twitter` se declararia canônico de si mesmo — que é exatamente o
conteúdo duplicado que a tag existe para evitar.

**E o site é rastreado como um buscador o rastreia.** Uma trava parte da home, segue todo `href` e todo
`src`, e cobra que cada endereço responda — depois confere que **toda entrada do `sitemap.xml` responde
200**. Uma segunda caminhada parte de `/account` **com sessão**, porque um link morto é mais
constrangedor onde quem o encontra já é cliente.

### Claro e escuro

**O site desenha com [DaisyUI](https://daisyui.com), e o painel com uma paleta declarada aqui.** São dois
vocabulários porque são dois builds e duas decisões: o site é markup Jinja, onde um plugin de CSS puro dá
componente e tema prontos, e o painel é Vue com componentes próprios.

| | O site | O painel |
| --- | --- | --- |
| a paleta | os temas `light` e `black` do DaisyUI | tokens no `@theme`, cada um com os dois lados num `light-dark()` |
| os nomes | `bg-base-100`, `text-base-content`, `text-error`, `btn`, `card`, `alert` | `bg-raised`, `text-ink`, `text-danger` |
| quem escolhe | `data-theme` no `<html>`, escrito pelo servidor | o `color-scheme`, escrito pelo store |

**Nenhuma cor crua é escrita numa tela, dos dois lados.** `tests/test_docs.py` percorre os templates e os
dois front-ends e recusa um `slate` ou um `rose` — o que sobra é a cortina do lightbox e o branco sobre
ela, nomeados com o motivo: aquela superfície é escura nas duas paletas, então ali a cor **é** o papel.

**Os dois temas do plugin são ajustados pela API dele, e não por CSS escrito por cima.** Dois ajustes,
os dois medidos e não julgados a olho:

| O que o plugin entrega | Por que ele não serve aqui |
| --- | --- |
| o `black` é monocromático: `--color-primary` é um cinza e `--color-base-100` é o mesmo preto da página | um botão primário lê como desabilitado, e um card não tem borda contra o fundo |
| o `light` afina `error`, `success` e `warning` para serem **preenchimento** com texto branco em cima | este site também os escreve como **texto** num card branco, onde eles ficam abaixo de 3:1 |

**E um tema é declarado uma vez.** O `@plugin "daisyui"` recebe `themes: false`, porque nomear um tema na
lista **e** no bloco que o ajusta escreve a paleta de fábrica num seletor de especificidade maior — e o
valor ajustado perde no navegador.

**Contraste é medido, e é um teste.** `tests/test_contrast.py` lê os dois temas do CSS **construído** —
que é o que um navegador recebe — converte cada `oklch` e cobra o que a página põe sobre o quê. Ele lê
**todo** bloco que nomeia o tema, inclusive o `:is(…)` de fábrica, cobra que cada cor de um tema seja
declarada uma vez, e cobra que `base-100` e `base-200` sejam diferentes, senão um card não se separa da
página em que ele está.

**A escolha é uma preferência, e é guardada como o idioma.** O cookie `fastkit_theme`, escrito por
`POST /theme`, e por isso o `<html>` já sai com o tema do servidor — **uma página nunca desenha claro e
depois vira** na frente de quem está lendo. Sem escolha não há atributo, e aí o `--prefersdark` do plugin
deixa o aparelho decidir. **E ele obedece ao consentimento**, exatamente como o `fastkit_language`.

**Uma pessoa escolhe claro ou escuro, e o `DRAWN_AS` diz com que tema cada um é desenhado** — o escuro é
o `black`. São duas coisas: o que alguém escolhe é do domínio, e o nome do tema é do plugin.

**Um botão carrega a escolha inteira**, e `NEXT_THEME` diz onde o próximo toque cai: do aparelho para
claro, de claro para escuro, e de escuro de volta para o aparelho. No site ele é um formulário, então
**funciona sem JavaScript** como todo o resto.

**E os dois lados dizem isso duas vezes, porque não há código entre eles** — o enum `Theme` com o
`NEXT_THEME` de um lado, o `THEMES` com o `NEXT` do outro. `tests/test_app.py` lê o arquivo do painel e
cobra que o conjunto e o ciclo sejam os mesmos, senão o botão gira para um lado no site e para outro no
painel e ninguém consegue explicar por quê.

### Um valor é escrito do jeito que quem lê escreve um

**O `helpers/money.py` responde as duas perguntas que um valor tem**, e elas são diferentes: `minor_units`
diz em quanto um gateway é mandado cobrar, e `money` diz como uma pessoa lê aquilo. As páginas chamam
`money(valor, moeda)` e `number(valor)`, que o Jinja recebe já amarrados ao idioma da requisição.

| Idioma | Como um valor sai |
| --- | --- |
| `en` | `$1,234.50` e `USD 1.00` |
| `pt` | `$ 1.234,50` e `USD 1,00` |
| `es` | `1.234,50 $` e `1,00 USD` |

**E a coluna guarda o que a moeda mais fina divide.** `Money` é `NUMERIC(12, 3)`, declarado uma vez em
`models/base.py` e usado nas cinco colunas de dinheiro, porque o dinar divide em milésimos e duas casas
arredondariam isso sem uma palavra — inclusive em `WebhookEvent.amount`, que é **o que o gateway
reportou**. `tests/helpers/test_money.py` percorre toda coluna numérica do esquema e cobra a casa que o
`THREE_DECIMAL` do helper declara.

**Os dois mapas são indexados e nunca alcançados por queda.** O idioma que chega aqui é sempre um dos que
a instância oferece, então a queda não protege nada — ela só esconde o idioma acrescentado sem formato,
que passaria a mostrar um número no formato do inglês para quem não tem como perceber.

**Um símbolo encosta no número e um código não**, porque um código é uma palavra: `$1.00` está certo e
`USD1.00` não. E **as casas decimais são as da moeda**, lidas do mesmo `factor` que o gateway usa — um
iene não tem nenhuma e um dinar tem três.

### Uma data é lida pelo relógio de quem a lê

Todo instante é gravado em UTC, e o site desenha os oito que ele mostra no **fuso da conta** — o `day` e
o `moment` chegam ao template amarrados a ele, do mesmo jeito que o `money` e o `number` chegam
amarrados ao idioma. Uma compra feita às nove da noite em São Paulo apareceria com a data do dia
seguinte se a página desenhasse o valor guardado. Quem lê sem conta lê em UTC.

### Um título desce um nível de cada vez

**Quem não enxerga a página caminha por ela pelos títulos**, então um nível pulado é um degrau que não
existe. Toda página do site tem **um** `h1` e nenhum salto, e o painel tem o mesmo: uma seção com título
logo abaixo do título da tela é um `h2`, no `AppCard`, no `FieldGroup` e no `SubitemManager`.

O `tests/routes/site/test_public.py` conta os títulos das doze páginas públicas, e o teste do formulário do
painel monta a tela e cobra que a sequência não pule.

### Um teclado alcança o conteúdo em um toque

**A primeira coisa focável é o salto para o conteúdo, nas duas superfícies.** Sem ele, quem navega por
teclado percorre os seis links do cabeçalho do site **em cada página**, e no painel percorre os trinta e
um da barra lateral **em cada tela**. Ele é `sr-only` até receber foco, e aí desenha como qualquer outro
botão daquela superfície.

**E as palavras de um controle vêm sempre do catálogo, inclusive as que o JavaScript desenha.** A página
passa as palavras num `data-`, e o módulo as lê pelo nome.

> **Lê-las por chave calculada não serve**, ainda que funcione: a trava dos ganchos não enxerga
> `words[qualquer]`, e o que ela não enxerga ela não protege. Os três botões do lightbox são lidos como
> `dataset.close`, `dataset.previous` e `dataset.next`, escritos por extenso.

### Um controle é nomeado por um rótulo, e não por uma legenda

**Uma legenda nomeia o grupo e um rótulo nomeia o controle**, e quem não enxerga a página ouve o segundo.
O `fieldset` do DaisyUI é desenhado pela classe `fieldset-legend`, que funciona em qualquer elemento —
então cada campo do site carrega um `id` e um `<label for>` com aquela classe, e o visual é o mesmo.

O `tests/routes/site/test_public.py` desenha os seis formulários públicos e cobra que **todo controle
visível** tenha um rótulo apontando para ele, e que nenhum apareça sem `id` e sem `aria-label`.

**E um controle que a página recusou diz que foi recusado.** A borda vermelha e a frase embaixo são a
metade que só quem enxerga a página recebe: o controle carrega `aria-invalid` e aponta a mensagem pelo
`aria-describedby`, e a mensagem carrega o `id` que ele nomeia.

**No painel valem as duas mesmas travas:** todo controle carrega `id` ou `aria-label`, e **um botão que
desenha só um ícone diz o que faz** — o `AppIcon` é `aria-hidden`, então um botão com um ícone dentro e
mais nada é anunciado como um botão vazio. **E o botão que abre o menu diz se ele está aberto**, com
`aria-expanded`.

### O que a marcação carrega é o que alguém procura

**Um atributo `data-` existe para alguma coisa achá-lo**, então um que nada procura é marcação que não faz
nada. `webapps/site/tests/shape.test.js` percorre os que os templates carregam e cobra que cada um seja
procurado — no JavaScript ou na folha de estilo, escrito como `data-nome` ou lido como `dataset.nome`, que
é a mesma coisa em duas grafias.

> **O `data-theme` fica de fora, nomeado com o motivo:** ele é o contrato do plugin com o navegador, e não
> um gancho deste site.

### Um link e a página em que ele está

**Nenhum link do site é sublinhado, nem em repouso nem sob o ponteiro.** O `link` do DaisyUI sublinha por
padrão e o `link-hover` sublinha no hover — não há variante que nunca sublinhe, então **este site não usa
`link`**: um link diz o que é pela cor, e o hover troca a cor. Uma trava recusa a palavra `underline` e
recusa a classe `link` em qualquer template.

**A página atual é marcada pela cor**, com `text-primary`. Quem responde por quem usa leitor de tela é o
`aria-current="page"`, que não depende de cor nenhuma.

> **O `menu` não serve como marcador.** Ele dá fundo e preenchimento a cada item, então o botão de tema e
> o link de entrar ganham caixas cinzas que não combinam com nada. Um navbar é uma fila de links, e um
> `menu` é uma lista de opções.

**O cabeçalho tem uma hierarquia e ela é deliberada:** os quatro links de seção são texto, entrar é um
`btn btn-primary` porque é a ação que a página quer, e o tema é um `btn btn-ghost btn-square` porque é um
controle e não um destino.

**A logo vem antes do nome da marca, e ela é desenhada com `currentColor`.** Por isso ela é escura na
página clara e clara na escura, sem uma segunda imagem e sem regra de tema: ela é a cor do texto ao lado
dela. O `favicon.svg` continua sendo outra coisa — ele é o ícone da aba, onde não há tema para herdar.

### Um componente decide o que ele decide

**Um utilitário escrito ao lado de um componente é o que briga com ele.** O `alert` do DaisyUI é um
**grid**, então um `flex-1` no texto dele não faz nada. O `card` já traz superfície, borda
(`card-border`) e respiro (`card-body`), então uma página que escreve `border`, `bg-base-100` e `p-8` ao
lado dele está dizendo a mesma coisa duas vezes e uma delas vai discordar.

O `webapps/site/tests/shape.test.js` percorre os templates e recusa, ao lado de um componente, o que aquele
componente já decide: tamanho de fonte, peso, raio, borda, preenchimento e sombra. **Layout continua
sendo do Tailwind** — largura, grade, espaçamento e `justify-between` são o que se escreve ao lado de um
componente, e não contra ele.

> **E a mesma trava lê o que a folha construída define.** Uma classe que o build nunca escreveu é markup
> que não faz nada, e uma migração é exatamente o que deixa uma para trás.

### A cor da marca é declarada num lugar

**O `config/base.py` diz a matiz e o croma, e os dois builds derivam a rampa inteira dela.**
`webapps/declared.js` é o único que lê o `config/base.py`, e os dois `vite.config.js` o chamam — ele
responde pelo `admin_path`, pelo `api_path` e pela marca. Cada build escreve um `src/brand.css` antes de
compilar, que não é versionado, e a folha de estilo aponta para ele em vez de escrever uma cor.

**A marca não vira com a paleta, e o texto dela vira.** São dois papéis, como o `danger` e o
`danger-fill`: um passo cheio carrega texto branco e por isso fica escuro nas duas paletas, e o
`brand-ink` clareia no escuro para ser lido sobre um card escuro. Espelhar a rampa inteira põe texto
branco sobre um azul claro em 1.88:1.

> **Uma trava lê cada padrão que atravessa essa ponte**, roda-o contra o `config/base.py`, e cobra que o
> valor achado seja o que o servidor tem — quatro formas de quebrar a ponte foram medidas, e as quatro
> falham. Uma asserção salva por um `or` não confere nada: o lado direito acha o texto da própria
> mensagem de erro.

### Uma imagem preenche a caixa em que ela é desenhada

**Toda imagem que uma listagem desenha é 16:9 e preenche a caixa** — `aspect-video w-full object-cover` —
e a regra de upload guarda **naquela mesma forma**. As duas coisas andam juntas de propósito: uma caixa
16:9 sobre um arquivo quadrado desenha a foto centrada numa poça de espaço vazio.

| Finalidade | Guardada em |
| --- | --- |
| banner, foto de galeria, imagem de produto, imagem de plano | 16:9, cortado |
| avatar | 1:1, porque um avatar é um círculo |

### Os assets

O `webapps/site` constrói exatamente dois arquivos, com nome fixo: `styles.css` e `scripts.js`, servidos
em `/static`. **Nome fixo e não hash com manifesto**: um manifesto é um arquivo a ler em tempo de request
e um caminho a errar quando o build não rodou.

**O que invalida o cache é a data em que o build escreveu o arquivo**, e não a versão da aplicação, que
não muda enquanto se desenvolve — toda mudança de css ou de script ficaria invisível atrás do cache do
navegador. A mesma regra serve num ambiente publicado, onde o arquivo dentro da imagem tem a data do
build: uma regra só, sem ramo por ambiente, e o endereço é lido a cada página porque um build pode rodar
com o servidor no ar.

As classes vêm dos templates Jinja, e é por isso que o build do Tailwind lê `templates/` por um
`@source`.

**O JavaScript é melhoria progressiva e nada mais**: o menu que abre numa tela estreita, o aviso que
fecha, o nome do arquivo escolhido num campo de upload, o CEP que preenche o que ainda está vazio, a
foto da galeria que abre por cima da página, e o token do reCAPTCHA cunhado antes do envio. **Toda
página funciona sem ele** — o endereço é um formulário preenchido à mão, e a foto é um link que abre o
arquivo.

**Todo módulo do site tem a mesma forma**, e ela tem duas metades: `bindX(root, send)` liga o que a
página tem e **responde se achou alguma coisa para ligar**, com um booleano em todos, e a chamada ao
servidor é uma função exportada ao lado, que o `main.js` injeta. É essa separação que deixa um teste
dirigir a ligação com um dublê em vez da rede.

> **A foto abre num `<dialog>`, e o jsdom não implementa um.** O `showModal` e o `close` são calçados em
> `webapps/site/tests/setup.js`, que é o único lugar onde isso existe.

> **O `ownerDocument` de um `document` é nulo.** A ligação recebe `document` na página e um elemento no
> teste, e um teste que passasse um elemento provaria o contrário do que a página faz.

### Sobrescrever um template por tenant

```
templates/tenants/acme/site/pages/home.html   o que este tenant desenha
templates/global/site/pages/home.html         o que todo mundo desenha
```

Nada precisa ser duplicado para mudar uma página de uma marca.

> **O site não linka o painel.** Nenhum link, nenhuma menção, nem no texto nem no HTML entregue — o
> painel é onde um operador trabalha, e um link para ele numa página que todo visitante lê é um convite
> que ninguém quis mandar. Um teste varre os templates e falha se o `admin_path` aparecer neles.

---

## Um provedor se escreve de uma forma só

**Quatro coisas neste projeto são um contrato com uma implementação por fornecedor**: o captcha, o
provedor de código postal, o gateway de pagamento e o storage. O eixo que importa é **quando um erro é
pego**:

| A forma | Um provedor que não implementa nada |
| --- | --- |
| `__init_subclass__` | falha **na definição da classe** |
| `ABC` com `@abstractmethod` | falha **na construção**, que acontece no import porque o `PROVIDERS` instancia ali |
| base plana com `raise NotImplementedError` | **passa**, e quebra dentro de uma requisição |

Só existem as duas primeiras, e as duas falham antes de o processo servir alguém. O gateway fica com o
`__init_subclass__` porque as regras dele são **condicionais** — quem se declara `queryable` tem que
implementar `state_from_query` —, e `ABC` não sabe dizer isso.

**E todo provedor é alcançado por um índice, nunca por queda.** `PROVIDERS[enum]` nos quatro, e o
provedor é escolhido por enum e não por um `Literal` — um `if` cujo último ramo entrega tudo que ninguém
classificou é um provedor novo virando outro em silêncio. Cada provedor de storage recebe o
`StorageSettings` e lê dele o que precisa, que é o que faz o mapa ser indexável sem um `if` para montar
cada um.

**Todo corpo que outra máquina respondeu é lido por `helpers.remote.body_of`**, nos quatro, e nenhum
`.json()` cru sobrou.

O `tests/test_providers.py` **acha** os mapas no fonte em vez de nomeá-los, e cobra de cada um que a
chave seja um enum respondido por inteiro e que o contrato recuse uma subclasse vazia.

## Captcha

**Um formulário público carrega o desafio que o ambiente declarar.** `disabled` é uma escolha do
ambiente, nunca o que uma falha assume — e nunca o que um ambiente que não diz nada assume: o padrão é
`image`, que o próprio servidor desenha e não pede chave a ninguém.

| Provedor | O que a página desenha | Como é respondido |
| --- | --- | --- |
| `image` | um PNG que o servidor desenhou, e o campo para digitá-lo | a palavra volta assinada, então nada é guardado entre as duas requisições |
| `recaptcha_v3` | a site key, e um token cunhado antes do envio | conferido no Google, recusado abaixo do `score_threshold` |
| `disabled` | nada | tudo passa |

**O desafio de imagem não guarda estado.** A palavra viaja dentro de um valor assinado com HMAC e prazo
— por isso ele funciona com N instâncias sem sessão compartilhada e sem Redis.

**A palavra é sorteada com `secrets`, e o ruído do desenho com `random`.** São duas coisas diferentes:
a palavra é o segredo do desafio, e o ruído só precisa parecer bagunçado. Sorteada pelo Mersenne
Twister, a palavra deixa de ser um segredo — quem observa algumas centenas delas reconstrói o estado do
gerador e prevê todas as seguintes.

**Qualquer coisa que não seja uma aprovação limpa é recusa**, e isso inclui um Google que não
respondeu: um problema de rede não é um visitante que passou.

**E do lado da página vale o mesmo, com uma diferença: o formulário sai de qualquer jeito.** O
`recaptcha_v3` segura o envio, cunha o token e reenvia — se o token não vem, quem decide continua sendo
o servidor, que recusa uma resposta vazia e desenha a página com o motivo no campo. Segurar o envio
deixaria o visitante apertando um botão que não faz nada, **em silêncio e para sempre**.

> **E para isso valer, cunhar o token precisa poder falhar.** Um `new Promise` que só recebe `resolve`
> transforma uma recusa do Google numa promessa **pendente para sempre**, e quem espera por ela espera
> para sempre junto — não há `catch` que pegue nem `finally` que rode. Os dois lugares que cunham
> passam `.then(resolve, reject)`.

Onde é pedido: entrar, cadastrar, recuperar senha, contato e newsletter no site, e **o login do admin**.
O site desenha o desafio no próprio HTML, e o admin o busca em `GET /api/meta/captcha`.

**Um desafio vale para uma tentativa.** O admin pede outro assim que um login é recusado, porque o
token já gasto seria respondido de novo pela mesma palavra.

---

## Assinaturas e entrega

### As peças

| Linha | O que é |
| --- | --- |
| `Plan` | o que uma assinatura é vendida como, uma linha por idioma, precificado só para o site mostrar |
| `Entitlement` | o que um plano concede, nomeado por um `code` que o aplicativo libera funcionalidade por |
| `Benefit` | o que um direito entrega: `access`, `credit` ou `product` |
| `Subscription` | o que um gateway diz que a conta tem |
| `UserEntitlement` | o direito que aquela assinatura acendeu |
| `SubscriptionBenefit` | o retrato do benefício tirado na ativação |
| `BenefitGrant` | uma entrega de um ciclo |

**O `code` existe porque um aplicativo libera funcionalidade por identificador estável**, e nome é
texto de exibição.

**De quanto em quanto tempo um plano cobra são duas colunas — a unidade e o número — e elas são uma
regra só.** O service recusa unidade sem número e número sem unidade, senão a página de planos desenha
a frase condicionada à unidade e interpola o número dentro dela: *"Every None Month"*, publicado para
todo visitante. Um plano sem cobrança recorrente é os dois vazios.

### O retrato

Ativar copia os benefícios do plano para `SubscriptionBenefit`. Editar o catálogo depois nunca
reescreve o que uma assinatura viva prometeu. **Quem trocou de plano carrega o que o plano de agora
promete, e nada do anterior** — `reconcile_entitlements` expira o direito que o plano novo não lista e
`snapshot_benefits` encerra o benefício que ele não lista.

> Sem essa varredura um upgrade deixaria o retrato do plano velho **ativo ao lado** do novo, e a pessoa
> passaria a ter a soma dos dois.

### Cadência e ciclo perdido

| Cadência | Quando entrega |
| --- | --- |
| `on_activation` | uma vez, na ativação |
| `recurring` | na ativação e a cada intervalo |
| `once_per_user` | uma vez **por pessoa**, e não por assinatura |

| Ciclo perdido | Com N ciclos atrasados |
| --- | --- |
| `catch_up` | entrega o mais antigo, um por passada |
| `latest_only` | entrega só o mais recente e pula o resto |
| `skip` | não entrega nenhum e retoma no próximo ciclo futuro |

**Um ciclo mensal caminha a partir do ciclo entregue, e não da âncora — então um dia 29, 30 ou 31 desce
e não volta.** Fevereiro é o que aparta: ancorado em 31 de janeiro, o próximo é 29 de fevereiro, e daí
todos os seguintes são no 29 até o próximo fevereiro curto os levar ao 28, onde eles ficam. **A deriva é
de no máximo três dias, ela acontece uma vez e assenta**, e ela não existe do dia 1 ao 28.

> **Isso é escolha e não descuido.** Uma programação ancorada — `âncora + n × intervalo` — não derivaria,
> e o retrato até carrega a âncora e a contagem de ciclos para isso. O que ela custaria é reescrever
> `resolve_due_slot`, que é onde `catch_up`, `latest_only` e `skip` são decididos ciclo a ciclo, e
> mudaria a chave de idempotência de toda concessão futura. Três dias uma vez não paga esse risco.

O `once_per_user` olha as concessões de **todas** as assinaturas daquela pessoa: cancelar e assinar de
novo não paga duas vezes.

### A idempotência

A chave é a `grant_key`, `<benefício>:<ciclo>`. Reprocessar a mesma passada nunca entrega duas vezes, e
cada tipo se protege do seu jeito:

| Tipo | O que impede a segunda entrega |
| --- | --- |
| `credit` | a `grant_key` é a chave de idempotência do extrato |
| `product` | possuir é uma linha só, e a segunda concessão o encontra já possuído |
| `access` | ligar um direito que já está ligado não é uma segunda entrega |

**Um ciclo que rodou faz a programação andar, por menos que ele tenha entregado.** `completed` e
`skipped` são os dois desfechos de um ciclo que aconteceu — só o `failed` segura a data, porque é ele
que o `retry_failed_grants` recolhe.

### `next_grant_at` é uma data que chega, ou não existe

O motor concede por duas portas — a varredura de `recurring` e a ativação de um plano que pediu
`grant_on_activation` — e um benefício que não passa por nenhuma das duas nasce **sem** próxima
concessão. Uma data escrita para nunca chegar aparece no admin como se fosse chegar.

### Teste e carência

| Política | O que a assinatura entrega naquele estado |
| --- | --- |
| `none` | nada |
| `access_only` | só o benefício de tipo `access` |
| `all` | tudo, como uma assinatura paga |

O padrão dos dois é `access_only`, e o motivo é dinheiro: um teste que entrega o que sobrevive a ele é
assinar, pegar e cancelar. O ciclo que a política segurou fecha como `skipped` e **não volta depois**.

### O que a assinatura leva embora, e o que não leva

| O que acaba | O que acontece |
| --- | --- |
| o direito (`UserEntitlement`) | vira `expired`, e o acesso fecha |
| o benefício (`SubscriptionBenefit`) | vira `ended`, e não entrega mais nenhum ciclo |
| o que já foi entregue | **fica**, sempre |

> **O que isso custa, e é uma escolha:** um reembolso devolve o dinheiro e **não** devolve o produto.
> Quem quiser cortar isso corta pelo lado do acesso, que fecha na hora.

### Voltar não é começar de novo

**Voltar é o mesmo ciclo. Começar de novo é que é ciclo novo.** O caso comum não é cancelamento: é
conta atrasada, acesso que cai, conta paga, pessoa de volta. Isso é **suspensão**, e uma suspensão não
deve outro ciclo.

`Plan.resume_delivery_policy` é `same_cycle` ou `new_cycle`, e o padrão é `same_cycle`. O campo é
**obrigatório no admin** mesmo tendo padrão: quem cadastra confirma a escolha em vez de herdá-la sem
ver.

> **Forçar não é parâmetro de cliente.** É `POST /api/subscriptions/{record_id}/new-cycle`, atrás de
> `Depends(get_administrator)`, e escreve no registro do sistema com o id de quem pediu.

### Reiniciar no meio de uma passada

A concessão é gravada como `processing` **antes** da entrega. Um deploy que derrube o processo entre os
dois deixa a linha em `processing`, e por isso o `retry_failed_grants` recolhe **duas** coisas: o que
falhou e o que ficou em `processing` por mais que `ABANDONED_AFTER` (30 min). A janela existe para não
roubar o que outra instância está entregando agora.

---

## O comércio

**Um produto é comprado uma vez e é da conta para sempre.** Ele carrega preço, imagem, um arquivo
opcional que quem possui pode baixar, e os créditos que possuí-lo põe numa carteira.

**Os créditos são propriedade do produto e não da forma como ele foi obtido**, então um pacote comprado
no checkout e o mesmo pacote entregue por um plano movem a carteira do mesmo jeito. Isso é uma regra em
um lugar só: `commerce_service.grant`.

### A compra

**A compra é escrita deste lado antes de o comprador ser mandado para qualquer lugar**, porque o que o
gateway ecoa de volta tem que nomear uma linha que já existe.

```
open_purchase  ->  o comprador vai ao gateway
               ->  o gateway avisa de volta
               ->  settle_purchase(PAID)
               ->  o produto é entregue e os créditos dele se movem
```

Liquidar o mesmo status duas vezes não é uma segunda entrega. Liquidar um reembolso marca o pagamento e
não busca nada de volta.

**E a sessão que não abriu fecha a linha que ela abriria.** O comprador só sai daqui depois que o
gateway responde um endereço, então um gateway que recusa é um comprador que nunca saiu — a compra é
marcada `failed` antes de o erro subir. Sem isso ela ficaria `pending` **para sempre**, esperando um
aviso que ninguém vai mandar, e apareceria em `/account/purchases` como uma cobrança em andamento que
nunca existiu.

**Nem todo meio de pagamento acaba enquanto o comprador olha.** Um boleto devolve a pessoa ao site com
a compra ainda `pending`, e é por isso que a página de retorno lê a linha em vez de dar os parabéns:
o `success_url` carrega a referência que este lado cunhou, e o que ela diz é o que a página desenha.

### A carteira

**A moeda é um cadastro, e não um par fixo.** `Currency` é o que o produto decide chamar de moeda —
código, nome, símbolo — e cada tenant acrescenta as suas. Um saldo é uma linha de `UserBalance`, uma por
conta e por moeda, e o extrato é `CreditTransaction`, também por moeda.

Um saldo se corrige com outra movimentação e nunca editando uma, porque o `balance_after` de cada linha
é o que faz o extrato explicar o saldo.

> **A conta não carrega coluna de saldo.** Duas colunas fixas no `user` seriam duas moedas fixas, e o
> dia em que o produto quisesse uma terceira seria uma migração.

| Tipo | Direção |
| --- | --- |
| `credit` | sempre soma |
| `debit` | sempre subtrai |
| `reversal` | sempre subtrai |
| `adjustment` | **o sinal que veio** |

**O tipo decide a direção**, porque o tipo é o que se audita e se filtra: um lançamento que diz `credit`
nunca pode ser um que tirou da carteira.

**E uma movimentação dirigida recebe uma grandeza, nunca um sinal.** Um valor negativo num `credit`,
`debit` ou `reversal` é recusado com `error.amount-must-be-positive` — o `adjustment` é o único que
carrega o próprio sinal, e é para isso que ele existe. Descartar o sinal com `abs()` faria quem digita
menos cinquenta num crédito ver cinquenta entrar na carteira.

**O saldo tem teto pelo mesmo motivo que tem piso.** Um abaixo de zero é um saldo que ninguém tem, e um
acima do que a coluna guarda estoura dentro do driver — os dois são recusados no mesmo lugar.

### O produto que um plano entrega

`BenefitType.PRODUCT` é o benefício que dá um produto por assinar. **O produto tem que ser alcançado
pelo tenant do direito** — a lista do formulário é estreitada por isso, e o service recusa o que alguém
mandou mesmo assim, com `error.product-out-of-tenant`. A tela filtra e o service recusa: são as duas
metades da mesma regra, e a do service é a que vale.

---

## O que um gateway de pagamento reporta

Quem cria e mexe numa assinatura é o gateway, não uma tela. O caminho é **um por tenant e por
gateway**:

```
GET POST PUT PATCH DELETE  /api/webhooks/{key}
```

A chave é sorteada quando a integração nasce e nunca é editável.

### Quem define o formato é o gateway

**A URL aceita a requisição do jeito que ela vier.** Método, formato do corpo, cabeçalho, assinatura:
cada gateway faz de um jeito. A rota resolve a integração pela chave, embrulha o que chegou num
`InboundCall` e entrega ao provedor.

**Uma chamada que não carrega nada não é evento.** Sem corpo e sem query é sondagem, responde 200 e não
grava linha.

### Autenticar também é de cada um

Não existe um jeito certo de provar quem chamou. Por isso `authenticate` é **método do provedor**.

### O caminho de um evento

| Passo | O que acontece |
| --- | --- |
| 1 | a chave resolve a integração, e com ela o tenant e o gateway |
| 2 | o provedor autentica do jeito dele |
| 3 | o provedor reduz a chamada a um `ProviderEvent` |
| 4 | o evento é gravado e **commitado** — perder o que chegou é pior que não ler |
| 5 | o que ele resolveu move a assinatura ou a compra, e o motor faz o resto |

O evento é durável **antes** de qualquer leitura. Uma falha no passo 5 grava `failed`, escreve no
registro do sistema e **levanta** — o 5xx é o que faz o gateway tentar de novo.

**E o pagamento é liquidado antes de a conta ser resolvida.** Uma cobrança do Stripe não carrega conta
nossa, então exigir uma antes derrubaria o aviso inteiro: a compra é quem diz de quem ela é, e a conta
que o aviso nomeia governa só o lado da assinatura.

**E a compra que um aviso move é do gateway que ligou.** Achar por referência sem conferir isso deixaria
um tenant com dois gateways ter um aviso de um movendo a compra aberta pelo outro.

### A idempotência

`UniqueConstraint("integration_id", "external_event_id")`: o mesmo evento chegando duas vezes é a mesma
linha e uma entrega só. Quando a chamada não traz id de evento, o id é o hash do que chegou.

### A ação nomeia o aviso, e não move a assinatura

O nome que cada gateway dá ao evento vira uma `NormalizedAction`, que **diz do que o aviso tratava**, e
**nenhuma linha de código decide estado por ela**. O nome cru não tem coluna, e isso é deliberado: ele
já está no `payload` guardado.

| Ação | O aviso era sobre |
| --- | --- |
| `activate` / `renew` | uma compra nova ou um ciclo que virou |
| `cancel_at_period_end` | a renovação foi desligada — **o acesso pago continua até o fim do ciclo** |
| `resume` | o cancelamento foi desfeito |
| `enter_grace` | a cobrança falhou e a loja abriu carência |
| `extend` | o período foi prorrogado |
| `suspend` | a assinatura foi pausada |
| `change_plan` | o comprador trocou de produto |
| `expire` | o período acabou |
| `refund` | o dinheiro voltou |

**Quem escreve estado é `ReconciliationService.apply`, e só ela.**

### Uma máquina de estado, duas origens

| Capacidade | O que significa | Quem usa |
| --- | --- | --- |
| `queryable` | o gateway responde *o que essa conta tem agora* | RevenueCat |
| `event_stated` | o aviso resolve o estado, no corpo ou apontando onde buscá-lo | Stripe |

**Um aviso é sobre uma coisa, e uma consulta é sobre todas.** Uma resposta de consulta lista tudo que a
conta tem, então o que falta nela acabou. Um aviso é sobre a compra que ele nomeia, então o silêncio
dele não fecha mais nada — `ReconciliationService.apply` recebe qual dos dois está olhando.

> **Sem esse recorte, um aviso do Stripe sobre uma assinatura fecharia a outra que a mesma conta tem.**

### O que o RevenueCat manda, campo por campo

| Campo | O que é | Onde entra |
| --- | --- | --- |
| `id` | id do evento, **o mesmo numa reentrega** | a chave de idempotência |
| `type` | o nome do evento | vira a `NormalizedAction` |
| `event_timestamp_ms` | quando aconteceu | `occurred_at` |
| `app_user_id` | o token da conta | acha a conta |
| `product_id` e `new_product_id` | o que foi comprado, e o que passou a ser | o `new_product_id` **vence** |
| `price_in_purchased_currency` + `currency` | o que o comprador pagou | o extrato |
| `cancel_reason` / `expiration_reason` | por que acabou | `CUSTOMER_SUPPORT` é o que diz reembolso |

> **A que mais custa errar:** `price` é o valor **em dólar** e `price_in_purchased_currency` é o que a
> pessoa pagou. Gravar o primeiro junto do `currency` diz que alguém pagou 4,20 reais por uma
> assinatura de 19,90.

> **Não existe evento de reembolso.** Ele chega como `CANCELLATION` ou `EXPIRATION` com a razão
> `CUSTOMER_SUPPORT`.

Autenticação: `X-RevenueCat-Webhook-Signature` (`t=…,v1=…`, HMAC-SHA256 sobre `<t>.<corpo cru>`) ou o
`Authorization` direto, e **a assinatura tem cinco minutos de tolerância**, a mesma do Stripe. A
documentação atual deles diz que *"RevenueCat recomputes the signature on each delivery attempt"* e que
a janela *"covers only the individual POST delivery, not the automatic retry delays"* — sem a
tolerância, uma requisição capturada vale para sempre.

> **O cabeçalho tem o mesmo formato dos dois lados, então quem o lê é `signature_parts` e mais
> ninguém.** Um `dict` guarda **a última** `v1`, e um segredo em rotação, que é assinado duas vezes,
> passaria ou seria recusado conforme a ordem em que as duas chegassem.

### O que o Stripe manda, campo por campo

Conferido na documentação atual deles.

**O envelope diz o que ele é, e o objeto dentro dele também.** Um corpo sem `"object": "event"` no topo
não é um aviso e nada é lido dele, e é `data.object.object` — `subscription` ou `checkout.session` — que
diz de qual das duas vidas o aviso trata. Um `checkout.session` só liquida um pagamento em `mode`
`payment`, e o que ele diz é o `payment_status`: `paid` e `no_payment_required` liquidam, `unpaid` deixa
pendente. **A compra é achada pelo `client_reference_id`, que é o `reference` que este lado cunhou** — uma
string, e nunca o id da linha.

| Evento | O que significa aqui |
| --- | --- |
| `customer.subscription.created` | uma assinatura abre |
| `customer.subscription.updated` | o estado é reescrito a partir do objeto |
| `customer.subscription.deleted` | ela acaba |
| `customer.subscription.paused` / `resumed` | pausa e volta |
| `checkout.session.completed` | uma sessão em modo `payment` liquida uma compra nossa |
| `checkout.session.async_payment_succeeded` / `async_payment_failed` | como um pagamento adiado terminou, dias depois |
| `checkout.session.expired` | a sessão morreu sem ninguém pagar |
| `invoice.paid` / `invoice.payment_failed` | registrados, e o estado vem dos eventos de assinatura |
| `charge.refunded` | a compra que aquele pagamento abriu volta, e só onde a cobrança inteira voltou |
| `charge.dispute.*` | a compra é estornada onde a disputa foi **perdida**, e volta a paga onde foi ganha |

> **O período corrente mora no *item* da assinatura** — `items.data[].current_period_start/end` —, que
> é para onde o Stripe o moveu. Ler no nível da assinatura responde nada e a assinatura fica sem
> período.

Todo status que eles nomeiam vira um dos nossos, e são os oito que eles têm:

| O que o Stripe diz | O que isso vira aqui |
| --- | --- |
| `trialing` | em teste |
| `active` | ativa |
| `past_due` | carência |
| `unpaid` | carência |
| `paused` | suspensa |
| `incomplete` | pendente |
| `incomplete_expired` | expirada |
| `canceled` | expirada |

> **Um boleto ou um débito volta `unpaid`, e `unpaid` não é uma cobrança que falhou.** O comprador é
> devolvido ao site antes de o dinheiro sair do banco dele, e o que aconteceu chega dias depois como
> `async_payment_succeeded` ou `async_payment_failed`. Ler `unpaid` como falha marcaria a compra como
> perdida e nunca mais a entregaria, mesmo com o dinheiro pago.

> **E a reentrega desse mesmo aviso chega depois do dinheiro.** O Stripe reentrega o
> `checkout.session.completed` por dias, então uma compra já liquidada nunca volta para `pending` —
> `settle_purchase` só aceita sair de um estado liquidado para outro, que é o que deixa um reembolso
> passar e um aviso atrasado não.

> **E o que este lado guarda de uma sessão é o `payment_intent` dela, e não o id da sessão.** É o
> **mesmo campo** que a cobrança carrega, então um reembolso acha a compra sem que nada precise viajar
> a mais no checkout. Lido na documentação atual deles: `checkout.session.payment_intent` é *"the ID of
> the PaymentIntent for Checkout Sessions in `payment` mode"*, `charge.payment_intent` é *"ID of the
> PaymentIntent associated with this charge"*, e `charge.refunded` é *"whether the charge has been
> **fully** refunded — if the charge is only partially refunded, this attribute will still be false"*.
> Por isso um reembolso parcial não mexe na compra: metade do dinheiro de volta não é uma compra
> desfeita.

> **E o estorno é lido pelo estado da disputa, não pelo nome do evento.** A disputa carrega o mesmo
> `payment_intent`, e o `status` dela é o que separa o que aconteceu: `lost` é *"a dispute resolved in
> the customer's favor"* e vira estorno, `won` é *"resolved in the merchant's favor"* e a compra volta a
> paga. Aberta, em análise, indagação e `prevented` — *"prevented from becoming a formal chargeback"* —
> não movem nada, porque **nenhuma delas tirou dinheiro**. Ler o estado em vez do nome do evento é o que
> faz `closed` e `updated` responderem igual.

> **O `past_due` não inventa uma data de carência.** O Stripe não publica até quando vai tentar de novo, e
> escrever uma data que ninguém disse é dar acesso que ninguém pagou. O acesso vai até o fim do período
> que ele reportou, e se a pessoa pagar ele manda outro `updated` com um período novo.

**Um valor é lido na unidade mínima da própria moeda** — `helpers/money.py` guarda quais moedas não têm
centavos e quais têm três casas. Dividir tudo por cem diz que alguém pagou um centésimo do que pagou.

Autenticação: `Stripe-Signature`, HMAC-SHA256 sobre `<t>.<corpo cru>`, **só o esquema `v1`**, **toda**
assinatura `v1` aceita porque um segredo em rotação é assinado duas vezes, e tolerância de cinco
minutos — o Stripe carimba um timestamp novo a cada reentrega, então um antigo é replay.

Quem é a conta vem de `metadata.account_token`, que o checkout põe na sessão **e** na assinatura.

### Quem nomeia o comprador

| De onde vem o nome | Exemplo | Quem resolve |
| --- | --- | --- |
| a loja devolve o que o app entregou a ela | RevenueCat, com o `app_user_id` | o provedor, lendo o corpo |
| **nós cunhamos a referência antes de mandar pagar** | Stripe, no fluxo web | o service, porque a referência é uma linha nossa |

**Resolver essa referência é trabalho do service e nunca do provedor**, porque ela é uma linha do nosso
banco e um provedor não alcança o banco — essa é justamente a regra que mantém um gateway novo sem
poder sobre a nossa regra de negócio.

### Um gateway novo

**É uma classe, e nada fora dela precisa saber que ela existe.**

| Método | Obrigatório | O que faz |
| --- | --- | --- |
| `authenticate` | sim | prova que quem chamou é o gateway |
| `read` | sim | diz do que a chamada tratava |
| `state_from_query` | só se `queryable` | responde o que a conta tem agora |

**O gateway também nomeia as próprias chaves**, e é por isso que o formulário de Integração pede o que
o painel daquele gateway mostra. A dica diz **onde achar a chave** e nada além disso, e o rótulo **não
passa pelo catálogo de tradução**: *Signing secret* é como o Stripe chama aquilo na tela que o operador
está olhando.

**A gaveta tem o nome do gateway** — `stripe_api_key_encrypted`, `revenuecat_webhook_secret_encrypted`.
Uma coluna chamada `secret` que significa uma coisa num gateway e outra noutro é o que faz ninguém
saber quem é quem.

**Uma capacidade errada falha no import.** `__init_subclass__` recusa a classe que não implementa
`read` ou `authenticate`, a que não diz por qual das duas formas responde, a que se declara `queryable`
sem `state_from_query`, a que não declara credencial, e a que pede um lugar que a integração não tem.

**Todo provedor do enum tem uma implementação.** Não existe gateway sem parser: `PROVIDERS[provider]`
resolve direto, e um valor de enum novo sem classe falha onde ele foi escrito.

O `tests/services/test_gateway_shapes.py` escreve um provedor no molde do Mercado Pago e outro no do
Stripe e prova o caminho inteiro sem tocar em nada fora da classe.

### Quando alguém é consultado

| Caminho | Quando | Custo |
| --- | --- | --- |
| webhook | o gateway avisou | uma consulta, na hora |
| `POST /api/account/subscriptions/refresh` | o app pediu | uma consulta, com janela de 10s marcada **na conta** |
| a passada de assinatura, a cada 5 min | **só** assinatura cujo acesso venceu e ninguém avisou | numa base saudável, **zero** |

**A janela é tomada com um `UPDATE`, não com um `if`.** Ler o campo e depois decidir não segura nada:
cinquenta chamadas no mesmo instante leem o mesmo valor antigo e viram cinquenta consultas.

### O orçamento do gateway

A varredura toma um quarto do orçamento e deixa o resto para o que não pode esperar. **O teto de contas
sai da janela da varredura e não da janela do cron**, porque ela é o primeiro de cinco passos —
dimensionada contra o cron ela gastaria a passada inteira antes de expirar, entregar e recolher.

**E a contagem sozinha não limita nada**, porque quanto tempo o gateway leva para responder é problema
dele: a varredura carrega um **prazo** e para quando ele passa.

**E fechar uma assinatura já fechada responde zero**, sem reescrever `expired_at` — senão a conta volta
para o conjunto a cada passada, para sempre, e o dreno nunca termina.

### Uma conta paga em mais de um lugar ao mesmo tempo

**Quem decide que alguém está assinando não é este lado.** A arquitetura representa as três ao mesmo
tempo, sem que uma apague a outra. O que separa uma linha da outra são dois eixos, e é por isso que a
restrição de unicidade nomeia os dois: `UNIQUE(user_id, integration_id, external_product_id)` — sem ela,
duas linhas da mesma conta com o mesmo produto colapsam numa entrada só do mapa e cada passada alinha
uma diferente.

**Uma reconciliação só fecha sobra dentro da própria integração.** Sem esse recorte, cada gateway
derrubaria o que o outro sustenta a cada passada.

**Cada assinatura entrega tudo o que ela promete, e o que a conta tem é a soma.** É decisão: ele pagou
duas vezes, e uma regra de "o melhor plano vence" faria uma das duas não entregar nada.

---

## Jobs agendados

**Queuefy** com a fila no mesmo banco da aplicação, então todo nó vê a mesma execução e só um a
reivindica. Ligado por `cron_enabled`, declarado importando `jobs/` em `helpers/lifespan.py`, e rodado
por um worker que o lifespan sobe e para junto do processo.

| Job | Quando | Tag | O que faz |
| --- | --- | --- | --- |
| `run_subscription_cycle` | a cada 5 min | `subscription` | uma passada inteira sobre assinatura |
| `process_pending_events` | a cada 10 min | `event` | reivindica e fecha o que os clientes reportaram |
| `send_pending_emails` | a cada 2 min | `email` | envia o que está na fila de e-mail |
| `discard_expired_records` | 04:20 | `retention` | apaga o que nenhuma regra vai ler de novo |
| `discard_orphan_files` | 04:40 | `storage` | apaga o que subiu e ninguém reclamou, lendo as próprias linhas |

**A passada de assinatura faz cinco coisas numa ordem que importa:**

| Ordem | O que roda | Por que aqui |
| --- | --- | --- |
| 1 | `reconciliation_service.reconcile_stale` | o provedor fala antes de o relógio fechar qualquer coisa |
| 2 | `delivery_service.expire_subscriptions` | o que o provedor não salvou, o relógio fecha |
| 3 | `delivery_service.process_due` | o que continua aberto é entregue |
| 4 | `delivery_service.retry_failed_grants` | recolhe a concessão que falhou ou ficou abandonada |
| 5 | `webhook_service.retry_failed` | idem, do lado do gateway |

O `manage.py run-delivery` chama exatamente a mesma função.

Job novo vai em `jobs/<modulo>.py` e é importado em `helpers/lifespan.py`. O job não tem regra de
negócio: abre a sessão, chama o service e **loga quantos registros ele tocou** — isso é do job e não do
service, que não conhece o prefixo daquela linha.

### Uma tabela operacional para de crescer

**Uma instalação que roda por anos é uma que ainda responde**, e o que a derruba não é carga: é uma
tabela que ninguém nunca podou. O `system_log` ganha duas linhas a cada passada de cron, o `app_event`
recebe o que o aplicativo reportou em lote, o `integration_webhook_event` guarda o corpo inteiro do que
o gateway mandou, e a fila do Queuefy escreve uma linha por ocorrência de cada job.

`RetentionSettings` diz quanto tempo cada uma guarda, e **zero guarda para sempre**:

| Tabela | Padrão | O que é apagado |
| --- | --- | --- |
| `system_log` | 180 dias | qualquer linha, porque ela é registro e não estado |
| `app_event` | 90 dias | o que fechou, mais o que falhou e já gastou as tentativas |
| `integration_webhook_event` | 90 dias | idem, e a janela é muito maior que a reentrega de qualquer gateway |
| `outbound_email` | 90 dias | o que foi enviado, mais o que falhou e já gastou as tentativas |
| `client_request` | 30 dias | a chave que já tem resposta, porque passada a janela ninguém está mais repetindo aquela chamada |
| `banner_impression` | 90 dias | a linha que deduplica uma view, porque o total agregado sobrevive a ela |
| `queuefy_run` | 30 dias | a execução liquidada, pelo `purge` da própria biblioteca |

**Nada em curso é apagado.** Uma linha só sai quando nenhuma regra vai olhar para ela de novo — por isso
o que ainda pode ser recolhido pelo `retry_failed` fica, por mais velho que seja.

> **A exclusão anda de mil em mil, e isso não é enfeite.** A primeira passada sobre uma tabela que
> ninguém nunca podou apaga milhões de linhas, e um `DELETE` único seguraria a tabela por minutos e
> encheria o undo log do InnoDB. Em lotes, cada um commita e solta.

> **A janela do webhook é o que sustenta a idempotência.** Apagar o evento apaga a memória de que ele
> já chegou — 90 dias é ordens de grandeza mais que a hora que um gateway reentrega.

### Uma passada acontece uma vez

**A fila decide quem se dá ao trabalho de tentar. Quem decide que roda é a reivindicação da execução.**
Todo worker calcula o próximo minuto que a expressão casa e o grava sob uma chave única, e o banco guarda
uma, e os outros são informados de que a chave já é de alguém. A reivindicação é um `UPDATE`
condicional que só um ganha.

**Nada elege um líder**, porque nada precisa.

**O que a reivindicação não cobre:** `manage.py run-delivery` chama as mesmas funções **sem passar pelo
agendador**. Quem responde por essa corrida é a `grant_key`, o `insert_or_read` e o `claim` da fila de
e-mail. São duas camadas guardando coisas diferentes.

Com isso `cron_queues` é o que ele é de verdade: **distribuir carga, e não garantir correção.**

### Toda fila reivindica a linha antes de trabalhá-la

O e-mail, o evento reportado pelo cliente e o aviso do gateway fazem a mesma coisa: um `UPDATE`
condicionado ao estado ainda ser o de espera, um commit por item, e um recolhimento do que ficou tomado
por mais que `ABANDONED_AFTER`. Sem isso, duas passadas que se sobreponham leem as mesmas linhas e
processam as duas — e a sobreposição não é hipótese, porque um job de 10 minutos tem `timeout=590`.

### Uma varredura não é trabalho da passada

**Uma escrita sobre a tabela inteira pertence a quem roda sozinho.** Devolver à fila o que um nó morto
deixou reservado é uma escrita dessas, e dentro do caminho que **todo nó percorre** ela vira deadlock —
repetir a escrita seria tratar o sintoma. Ela mora no job, que é o único lugar onde a execução única já
está garantida: a ocorrência do cron é reivindicada por um nó, e é esse nó que varre antes de mandar.

### Cada execução deixa rastro

O worker anuncia cada execução, e `helpers/scheduler.py` transforma isso em linha de `system_log` na
categoria `cron`: um `info` ao começar, um `success` com a duração ao terminar, um `error` com a
mensagem quando falha.

**A descrição diz o que rodou, e não só o nome dele** — `Scheduled service "send_pending_emails"
finished`. Quem lê o registro depois não estava lá para saber que aquele nome era um serviço agendado.

**Um ouvinte que quebra quebra sozinho:** a biblioteca captura o que ele levantar, então uma tabela de
auditoria cheia nunca transforma um job que funcionou num job que falhou.

### O que o cliente reporta

`POST /api/events` só **aceita e guarda** — o `uuid` do cliente é o que faz um lote reenviado entrar
uma vez só. Quem lê depois é o `process_pending_events`, e o que ele faz com cada nome é virar linha do
registro do sistema, na categoria daquele nome.

Um nome que o backend nunca aprendeu fecha como `ignored` — nunca como falha, senão a fila cresceria
para sempre atrás dele. O que fechou como `failed` é lido de novo até `MAX_ATTEMPTS`.

Por isso `AppEventName` **não é publicado no `/api/meta`**: o conjunto é aberto do lado de quem reporta.

---

## Storage

### Ninguém alcança o bucket

**A credencial do storage é do servidor, e de mais ninguém.** O único jeito de um byte entrar no bucket
é atravessar a aplicação, e ele atravessa por uma de duas portas:

| Rota | Quem chama | O que ela faz |
| --- | --- | --- |
| `POST /api/account/avatar` | a conta | grava a imagem **e já atualiza a conta**, respondendo o `AccountSchema` inteiro |
| `POST /api/uploads/{purpose}` | **só o administrador** | grava e responde a chave, que o formulário guarda no campo |

**A rota da conta é uma chamada só, e isso é o ponto.** O cliente nunca vê uma chave de storage, nunca
guarda uma, e nunca manda uma — **uma chave que um cliente segura é uma chave que ele pode apontar para
qualquer lugar**.

**As duas portas gravam pela mesma regra.** `UserService.settle_avatar` chama o mesmo
`upload_service.store` com `UploadPurpose.AVATAR`.

**Trocar a foto apaga a anterior, e nessa ordem:** a linha passa a apontar para a nova, commita, e só
então o arquivo velho sai.

### Quem pode ler um objeto é o bucket que diz

**Um upload nunca nomeia uma ACL.** A documentação atual da AWS diz que um bucket criado hoje nasce em
*Bucket owner enforced*, com **as ACLs desabilitadas**: *"PUT requests that contain other ACLs fail and
return a 400 error with the error code AccessControlListNotSupported"*, e *"new objects can be uploaded
to your bucket only if they use bucket owner full control ACLs or don't specify an ACL"*. Um upload que
nomeasse uma não subiria arquivo nenhum — nem avatar, nem imagem de produto, nem banner.

O objeto é lido por qualquer um quando a **política do bucket** permite, que é onde um bucket é
configurado. O `docs/deploy.md` traz a política pronta.

### A regra de cada finalidade é configuração

**Toda finalidade mora em `settings.uploads`, em `config/base.py`**, e um ambiente sobrescreve a que
quiser pelo `derive`. Não há regra de upload escrita dentro de um service, e é isso que faz trocar a
largura de um banner ou a pasta de um produto ser uma linha de configuração.

| Campo de `UploadSettings` | O que decide |
| --- | --- |
| `folder` | onde a chave começa, e é ele que `ensure_files_are_of_their_purpose` cobra |
| `extensions` | o que aquela finalidade aceita |
| `max_bytes` | o teto dela, sempre limitado pelo `upload_max_bytes` do ambiente |
| `naming` | **como o arquivo se chama** — `uuid` ou `original` |
| `image` | **o que os bytes viram** — ou `None`, que é o que diz que a finalidade é arquivo e não imagem |

| Finalidade | Pasta | Extensões | Limite | Nome | Imagem |
| --- | --- | --- | --- | --- | --- |
| `image` | `images/content` | imagem | 10 MB | uuid | 1600 de largura, webp 82 |
| `avatar` | `images/user/avatar` | imagem | 5 MB | uuid | 256×256 com crop, webp 85 |
| `banner` | `images/banner` | imagem | 10 MB | uuid | 1920×1080 com crop, webp 82 |
| `gallery-photo` | `images/gallery` | imagem | 10 MB | uuid | 1600×900 com crop, webp 82 |
| `product-image` | `images/product` | imagem | 10 MB | uuid | 1280×720 com crop, webp 85 |
| `plan-image` | `images/plan` | imagem | 10 MB | uuid | 1280×720 com crop, webp 85 |
| `product-file` | `files/product` | documento | 512 MB | **original** | nenhuma |

**Imagem** é `.jpg .jpeg .png .webp .gif` e **documento** é `.pdf .epub .zip .mp3 .mp4`. Onde a regra
diz imagem, o conteúdo é decodificado com o Pillow — a extensão é o que o nome afirma, não o que os
bytes são.

SVG fica de fora de propósito: carrega markup, e um editor renderiza o que vier dentro.

**Uma trava lê essa tabela contra a configuração** — pasta, teto, nome, forma, formato e qualidade —, e
lê junto toda forma que o `README.md` escreve, porque a documentação pública dizendo outro número é meia
correção.

### O que o `make seed` põe nas imagens

**Cada imagem mostra a coisa que ela ilustra**, e mora em `extras/seed/`. A linha nomeia o arquivo dela
— o `picture` do banner, do produto, do plano e da conta, e a lista `pictures` de uma galeria, que a
versão em português e a em inglês compartilham porque é o mesmo escritório.

**E o que o seed escreve é o que o painel consegue gravar de volta.** Os endereços de contato de um
tenant são derivados do domínio dele, e o schema que escreve um tenant recusa um nome de uso especial —
com um domínio desses, abrir a marca no painel e **salvar sem mudar nada** responde 422 em dois campos
que ninguém tocou. O domínio semeado é `.example`, reservado para exemplo pela RFC 2606, e uma trava
percorre todo endereço que o seed escreve cobrando que o schema o aceite.

**Elas ficam no repositório de propósito**, e é o que faz `make seed` rodar **sem rede** e desenhar a
mesma coisa toda vez.

**E os bytes atravessam o mesmo pipeline que um upload do painel atravessa.** `IncomingFile` é um
Protocol justamente para isso, então o seed embrulha o que leu do disco num `Picture` e chama
`upload_service.store(purpose, ...)` — o arquivo semeado é um arquivo de verdade, com a pasta, o nome
sorteado, o webp e o corte que a finalidade manda, na resolução que `settings.uploads` declara.

> **Um arquivo que falta derruba o seed**, com o caminho na mensagem. Desenhar um retângulo no lugar
> seria esconder a falha atrás de exatamente o que essas imagens vieram substituir.

**E o seed esvazia o storage junto com o banco.** Um banco recriado do zero deixa órfão todo arquivo que
o anterior apontava, então `discard_media` roda logo depois do `recreate_schema`.

### Como um arquivo se chama

Toda chave sai de `build_key`, e **as duas formas carregam o uuid**:

| `naming` | A chave | Para quê |
| --- | --- | --- |
| `uuid` | `<pasta>/AAAA/MM/DD/<uuid>.<ext>` | nada que a pessoa digitou chega ao storage |
| `original` | `<pasta>/AAAA/MM/DD/<uuid>/<nome-limpo>.<ext>` | o navegador salva o arquivo com o nome que a pessoa conhece |

**No modo `original` o uuid é a pasta e não o nome**, e essa é a parte que importa: é por ele que um
arquivo é resolvido, então o nome legível não atrapalha — e dois arquivos com o mesmo nome no mesmo dia
nunca se sobrescrevem.

**O nome legível não é o que a pessoa digitou.** `readable_name` normaliza o acento, derruba tudo que
não é letra ou número, corta em 80 caracteres e nunca deixa passar separador nem ponto — a extensão vem
da regra, e não do nome. `Manual do Usuário.PDF` vira `manual-do-usuario.pdf`.

**O arquivo nunca fica inteiro na memória do processo.** O corpo é lido em pedaços para um
`SpooledTemporaryFile` que rola para o disco passados 4 MB. A exceção é imagem, e ela é segura: só ali
os bytes são lidos inteiros, porque o Pillow precisa deles.

### Tratamento de imagem

Toda finalidade de imagem declara o que a imagem **vira** antes de ser gravada, num `ImageSettings`:

| Campo | O que faz |
| --- | --- |
| `width` / `height` | a caixa, e um lado deixado de fora acompanha o outro |
| `crop` | preenche a caixa exata cortando pelo centro, e **amplia** o que for menor |
| `image_format` | `jpeg`, `png` ou `webp`, e é dele que sai a extensão da chave |
| `quality` | o que o encoder recebe, para `jpeg` e `webp` |
| `store` | **`processed` ou `original`** |

- **Sem crop**, a imagem cabe na caixa mantendo a proporção, e uma menor **fica como está**.
- **Transparência é achatada** quando o formato de saída não guarda alfa.
- A extensão da chave vem do formato de saída, e não do arquivo enviado.

**E uma imagem tem teto no que ela pesa depois de decodificada, e não só no que ela pesa na rede.**
`image_max_pixels` são 40 milhões, conferidos logo depois de abrir o arquivo — abrir lê **só o
cabeçalho**, então a tela que ele anuncia é recusada antes de um pixel dela ser alocado. Um PNG de 252
KB que anuncia 9000×9000 leva o processo de 345 MB para 396 MB de RSS, e a rota do avatar é alcançável
por qualquer leitor.

> **O decodificador não protege sozinho, e é por isso que o teto é deste lado.** Ele **avisa** até o
> dobro de um limite próprio e só levanta acima disso, então uma tela de 81 milhões de pixels passa sem
> uma palavra — e o erro que ele levanta acima do dobro é um dos capturados, senão um PNG de 186 KB
> responde 500 em vez de uma recusa.

**O `store` é a escolha entre guardar o que chegou e guardar o que a regra descreve.** Com `original`, os
bytes vão para o storage exatamente como vieram, com a extensão e o content type deles.

> **Os bytes são decodificados nos dois casos**, e isso não é desperdício: é a única coisa que impede um
> `.png` que na verdade é markup de entrar no bucket. `store: original` guarda o original, e nunca
> guarda o que não é uma imagem.

**Uma finalidade sem `image` é arquivo e não imagem**, e é essa ausência que o upload lê — não há uma
segunda forma de dizer a mesma coisa.

### Um arquivo sai quando a linha para de mencioná-lo

**Isso é a regra inteira, e ela vale para as três formas de um registro nomear um arquivo.**
`mentions()` declara onde procurar — a coluna de arquivo, a coluna que o painel autora no editor, e o
mapa livre de `meta` —, e criar, editar e excluir passam todos por **reivindicar** o que a linha
menciona e **soltar** o que ela deixou de mencionar.

| Passo | O que acontece |
| --- | --- |
| `upload_service.store` | escreve a linha de `StoredFile` — uuid, chave, finalidade, tamanho — e **então** grava o arquivo |
| um registro é salvo | `claim` marca `claimed_at` em todo uuid que aquele registro menciona |
| um registro deixa de mencionar | `release` apaga o arquivo e a linha dele |
| o cron diário | apaga o que passou da carência sem nunca ter sido reivindicado |

**A reclamação lê os valores do próprio registro, e não as colunas de arquivo.** É o que faz a imagem
que o editor embute no HTML de um conteúdo ser reclamada como qualquer outra: ela não está numa coluna
de arquivo, está dentro do corpo. E `claim` e `release` leem o valor que quem chama tem na mão — uma
chave, um corpo de markup ou o uuid nu —, porque quem escreve fora da fábrica, como o `make seed`, tem
a chave e não o uuid.

**A varredura não lê tabela nenhuma inteira e não lista o bucket.** Ela lê as próprias linhas, em lotes
de mil, e o que ela segura na memória é o lote. Um teste dirige a passada com um ouvinte no engine e
falha se ela emitir um `SELECT` sobre qualquer tabela que não seja a dela.

> **O contrário não escala.** Ler toda coluna de texto e JSON de toda tabela, guardar todos os uuids
> referenciados num set e percorrer o bucket comparando custa 105 MB de memória com um milhão de
> arquivos e 1,4 GB com dez milhões, mais uma chamada de listagem por mil objetos no S3.

**É o mesmo desenho do `ActiveStorage` do Rails**, que anota cada arquivo numa tabela dele e apaga com
um job de carência o que ficou sem anexo. **Por isso o cron diário vem ligado:** ele só apaga arquivo
que esta aplicação escreveu e que nada nunca mencionou — o que mais estiver no bucket não é dele para
decidir.

> **E o arquivo é anotado antes de ser gravado.** Na outra ordem, uma escrita que falha depois de o
> arquivo já estar no bucket deixa um arquivo que **nenhuma linha anotou**, e a varredura lê linhas — ele
> nunca mais é visto por ninguém. Anotado primeiro, uma gravação que falha deixa uma linha que não
> nomeia nada, e a varredura a recolhe apagando uma chave que não existe, que não é nada.

**E o arquivo escrito para uma linha que não foi escrita vai junto com ela.** O upload acontece antes da
linha que o reclama, então uma gravação que não passa na mesma requisição desfaz o arquivo que ela
escreveu. O que sobra é o arquivo de quem subiu a imagem e fechou a aba — duas requisições, e a segunda
nunca chegou —, e esse é o que a varredura recolhe depois da carência.

### O storage é do ambiente e não do tenant

| Quando | Quem é o tenant |
| --- | --- |
| ao enviar um e-mail | o da linha da fila, que já está gravado |
| ao gravar um arquivo | **ninguém sabe ainda** — o upload acontece antes de o registro existir |
| ao ler ou apagar esse arquivo | o do registro, que pode nem ser o de quem enviou |

Um bucket por tenant só passa a ser possível quando o upload souber para qual tenant está gravando
**e** houver resposta para o que acontece com o arquivo quando o registro troca de tenant.

---

## Configuração

Um arquivo por ambiente, cada um derivando do `dev` por `derive`, que reconstrói o objeto em vez de
copiar — então toda sobrescrita passa pela mesma validação:

```
                 ->  config/stage.py
config/dev.py
                 ->  config/prod.py
```

**O `stage` e o `prod` são irmãos, e não uma corrente.** Os dois partem do `dev`, que é o que descreve a
forma da aplicação, e nenhum dos dois herda do outro — senão toda folga que o `stage` se dá para rodar
sem segredo nenhum chegaria à produção por omissão, e bastaria esquecer uma sobrescrita.

### A regra: valor de configuração mora no `.py`, nunca em variável de ambiente

**Nenhum arquivo de `config/` lê `os.environ`.** A única coisa que vem do ambiente é `APP_ENV`, e ela
não é configuração — é **qual** configuração carregar. Um teste falha se um `os.environ` reaparecer em
`config/`.

O motivo é operacional: uma variável de ambiente vive na máquina, e no dia em que o servidor se perde
ela se perde junto. O arquivo diz **o que** o ambiente é — qual banco, qual bucket, qual provedor de
captcha, quanto custa um hash — e isso é o que precisa sobreviver à máquina.

### E este repositório é público, então o valor não mora nele

**O `config/stage.py` e o `config/prod.py` declaram a forma e nunca o segredo.** Toda chave publicada aqui é
um marcador — `change-me`, `insecure`, `not-for-deployment` —, e quem sobe o produto preenche os dele na
instalação dele, que é privada. O que é público é a **estrutura** do ambiente, e ela é útil justamente
por isso: um arquivo mostra o que precisa existir, sem entregar nada.

**E nenhum ambiente serve com um segredo que este repositório publica.** A chave que assina todo valor
que o servidor entrega e lê de volta, e a que criptografa a credencial de cada gateway, são recusadas
**na subida do processo** enquanto trouxerem o marcador — nenhum framework entrega um placeholder que
funciona: o Django recusa subir sem a chave secreta dele, o Laravel lança quando nenhuma chave foi
gerada, e o Rails gera a dele na instalação. A recusa é na subida e não na construção da configuração,
porque a suíte importa o `config/prod.py` para provar outras coisas sobre ele. E uma segunda trava lê o
`config/prod.py` e falha se ele deixar de trazer o marcador, porque uma recusa que procura um texto vale
nada no dia em que aquele texto sai.

**O default do `config/base.py` é o valor de um ambiente implantado, e o `dev` é quem afrouxa.** Um
ambiente publicado escrito depois herda o lado seguro por omissão em vez de por memória: o `scheme` é
`https` e o `cookie_secure` é verdadeiro, e é o `dev` que declara os dois juntos porque a máquina de
quem desenvolve não tem TLS. Pela mesma regra, as origens de CORS nascem sem deixar ninguém entrar, o
e-mail nasce `smtp` — `console` é **imprimir a mensagem no log em vez de mandá-la**, e um ambiente
publicado que o herdasse escreveria todo token de recuperação no próprio log — e o captcha nasce
`image`.

**E um valor público também precisa ser declarado por instalação.** Num ambiente que serve **uma
marca**, nada procura host nenhum e `site.domain` **é** todo endereço absoluto que a aplicação escreve:
o `sitemap.xml`, o `robots.txt`, o JSON-LD, a url de retorno do checkout e o link de confirmação da
newsletter, que sai por e-mail. Ele é um marcador como o resto, e uma trava cobra isso de todo ambiente
publicado que serve uma marca — o `stage` fica de fora porque ele serve muitas, e ali quem diz o domínio
é o `Tenant`.

Duas travas guardam os segredos, e as duas moram em `tests/test_app.py`:

| Trava | O que impede |
| --- | --- |
| toda chave de um ambiente publicado é um marcador | um segredo de verdade colado onde o padrão pede um valor |
| nada publicado carrega o **formato** de uma credencial | um `AKIA`, um `sk_live_`, um `whsec_`, um DSN do Sentry ou uma chave privada em qualquer arquivo publicado |

A segunda existe porque a primeira só olha `config/`, e uma chave colada por engano cai em qualquer
lugar — num compose, num nginx, num exemplo do README.

**Não existe lista de tenants no código.** Os códigos vivem no banco, e um arquivo de configuração só
nomeia os tenants que sobrescrevem alguma coisa.

### O nome do produto sai de um lugar só

`NAME` em `config/base.py` é como o produto se chama, e é dali que saem o título da API, a descrição do
`manage.py`, o remetente padrão do e-mail e o nome que o admin desenha no canto — este último pelo
`/api/meta`, que é como o painel também descobre a versão. **O admin não guarda o nome em catálogo de
tradução**, porque um nome próprio não se traduz.

### Limites

| Limite | Valor | Onde |
| --- | --- | --- |
| Itens por página | 50 por padrão, 200 no máximo | `helpers/pagination.py` |
| Número que um cliente digita | o que a coluna em que ele cai guarda | `BIG_INTEGER_MAX` e `INTEGER_MAX`, em `models/base.py` |
| Itens num lookup | 20 por padrão, 50 no máximo | `helpers/crud.py` |
| Registros no grid do admin | 25 por página | `ResourceListView.vue` |
| Linhas numa listagem do site | 20 por página | `site.page_size` |
| Lembrança do idioma escolhido | 1 ano | `site.language_max_age` |
| Lembrança da paleta escolhida | 1 ano | `site.theme_max_age` |
| Recusa de http depois da primeira visita | 1 ano | `site.hsts_max_age` |
| Validade de uma resposta sobre cookies | 180 dias | `site.consent.max_age` |
| Validade de uma busca em cache | 30 s | `cache.search_ttl` |
| Validade da home e dos banners em cache | 60 s | `cache.home_ttl`, `cache.banners_ttl` |
| Validade do catálogo em cache | 120 s | `cache.products_ttl` |
| Validade de plano, conteúdo e galeria em cache | 300 s | `cache.plans_ttl`, `cache.content_ttl`, `cache.gallery_ttl` |
| Corpo que o processo lê inteiro | 1 MB | `request_max_bytes` |
| Espera do banco na sonda de prontidão | 2 s | `readiness_timeout` |
| Senhas erradas antes de a conta parar de responder | 5 | `security.sign_in_attempts` |
| Espera que a conta ganha, e o teto dela | 60 s dobrando, até 900 s | `security.sign_in_cooldown`, `sign_in_cooldown_max` |
| Uma chave de idempotência segurada por uma chamada que morreu | 5 min | `helpers/idempotency.py` |
| Upload | 512 MB no teto geral, e o de cada finalidade | `upload_max_bytes`, `uploads` |
| Tela de uma imagem depois de decodificada | 40 milhões de pixels | `image_max_pixels` |
| Upload que rola para o disco | 4 MB | `SPOOL` |
| Rate limit por IP | 300/min em prod, 600/min em stage, desligado em dev | `rate_limit.ip_limit` |
| Rate limit total | 3000/min em prod, 6000/min em stage | `rate_limit.total_limit` |
| Endereços que o contador do rate limit guarda | 50000, os últimos vistos | `rate_limit.tracked_clients` |
| Execuções de cron ao mesmo tempo | 4 | `cron_concurrency` |
| Validade de uma reivindicação sem batida | 5 min | `cron_lease_seconds` |
| Busca na query | 128 caracteres | `helpers/pagination.py` |
| Token de recuperação de senha | 1 hora | `password_reset_token_ttl` |
| Espera de um endereço entre duas recuperações | 60 s | `password_reset_interval` |
| Validade de um desafio de captcha | 10 min | `captcha.ttl` |
| Espera de um endereço entre dois convites da newsletter | 1 hora | `INVITATION_INTERVAL` |
| Quem pode falar por um cliente | só o loopback, e as faixas privadas de `stage` em diante | `trusted_proxies` |
| Validade de um token de CSRF | 1 hora | `site.csrf_ttl` |
| Carência do arquivo órfão | 24 horas | `storage.orphan_grace_hours` |
| Retenção de registro, evento, aviso e mensagem | 180, 90, 90 e 90 dias | `retention.system_log_days` |
| Retenção da chave de idempotência respondida | 30 dias | `retention.client_request_days` |
| Retenção da deduplicação de banner | 90 dias | `retention.banner_impression_days` |
| Retenção da execução de cron | 30 dias | `retention.cron_run_days` |
| Linhas por lote de exclusão | 1000 | `retention.batch` |

> **O rate limit é por processo, não do sistema.** Com quatro workers, um teto de 3000/min vale
> 12000/min no conjunto. Enquanto o limite existe para segurar abuso, e não para dimensionar
> capacidade, isso é aceitável e barato.

> **E o contador guarda os endereços vistos por último e mais nenhum.** A biblioteca troca a janela
> vencida quando o mesmo endereço bate de novo, e nunca tira o que parou de bater — num dicionário
> comum, todo IP que já chamou fica lá enquanto o processo viver, e uma varredura de muitas origens
> derruba o processo por memória.

---

## O admin

O admin é servido em **`/admin`**, e trocar isso é **uma linha**: `admin_path` em `config/base.py`.
O servidor roteia por ele, o `vite.config.js` **lê esse mesmo arquivo** para saber com que prefixo
escrever os caminhos dos assets, e o roteador do Vue lê o que o build escreveu. **O mesmo vale para
onde a API responde**: o painel é servido num caminho e **chama** outro, e o build entrega o `api_path`
ao cliente por `define`. Uma trava cobra que o painel não escreva nenhum dos dois por conta própria,
**lendo o painel inteiro** — o arquivo de tela é `.vue` e o endereço de webhook que o operador cola no
console do gateway é montado numa delas.

> **Quem serve a raiz compara o caminho inteiro, e não o começo dele.** `/administrators` começa como
> `/admin` e não é o painel: com um `startswith` solto, essa página responde JSON em vez do 404
> desenhado.

### É dirigido por definição

**Não se escreve tela.** Existem três telas genéricas — lista, detalhe e formulário — e cada recurso é
um objeto declarativo em `webapps/admin/src/resources/`. Adicionar um recurso é adicionar uma
definição, nunca um `.vue`.

Flags do recurso: `readOnly`, `canView`, `canCreate`, `canEdit`, `canDelete`, `activatable` e
`managedByParent`.

Hoje são 31 recursos, agrupados nas seções `["access", "commerce", "subscriptions", "content",
"integrations", "operations"]`.

### Subitens

Um recurso que só faz sentido dentro do pai declara `subitems`, e a tela de edição do pai ganha um
painel que lista, cria, edita, exclui e reordena os filhos, semeando a chave estrangeira. Ele **só
aparece na edição**, nunca na criação: um filho precisa de um pai já salvo.

**Um filho com ordem se reordena pela seta**, e quem reescreve a ordem é o servidor, numa transação só.

> **A posição não é única, e isso é decisão.** Duas linhas na mesma posição não decidem nada: a ordem
> desempata pelo `id`, e a reordenação reescreve as duas de qualquer jeito. Um índice único ali só
> recusaria um cadastro que não tem nada de errado.

> **A reordenação vai num `PUT` só, e não em N do navegador.** Mandar um por linha colide no meio do
> caminho e deixa a lista pela metade se um falhar.

> **E o painel não oferece uma ordem que ele não pode escrever inteira.** Ele desenha uma página de
> filhos, então ele diz quantas desenhou de quantas existem, e a seta some enquanto ele não tem o
> conjunto todo — reordenar o que está na tela renumera as desenhadas e deixa as invisíveis onde
> estavam, o que com o padrão zero as joga **para a frente** do conjunto que o operador acabou de
> arrumar.

**A rota literal é declarada antes da rota do identificador**, senão `PUT /order` cai em
`PUT /{record_id}`. `tests/test_app.py` percorre as rotas na ordem em que a aplicação as registrou e
falha quando um caminho literal vem depois de um parâmetro do mesmo método e da mesma forma — porque ele
nunca responde. A mesma varredura recusa a rota declarada duas vezes.

### Um componente por tipo de dado

Nunca escreva um `<input>` solto numa tela. Cada tipo tem seu componente: `text`, `textarea`, `number`,
`switch`, `select`, `lookup`, `datetime`, `date`, `json`, `html`, `image`, `file`, `password`,
`timezone`.

**O tom é um vocabulário só.** O mesmo vermelho se chama `error` no alerta, no badge e no toast, e
`danger` fica onde ele é a palavra certa: o `variant` de um botão, que nomeia uma **ação destrutiva** e
não uma falha.

**E nenhum conjunto fechado do painel é alcançado por queda.** O tom, o ícone e o tipo de campo são
indexados direto: um nome que ninguém declarou **não desenha nada**, e é visto — um `|| TONES.info`
esconde o erro atrás de um tom que parece certo, e um `|| PATHS.info` desenha o glifo de informação no
lugar do nome escrito errado. Uma trava **acha** todo componente de `ui/` que declara uma tabela fechada,
e outra fecha as duas direções do catálogo de ícones: o que falta e o que sobrou.

> **Mas um alerta nunca engole a mensagem.** Ler `tone.classes` de um tom inexistente estoura e mata a
> renderização, que é pior que a queda: o alerta desenha sem estilo e sem ícone, e o texto continua
> sendo lido.

> **E o validador de prop não cabe aqui:** o compilador do Vue iça o `defineProps()` para fora do
> `setup`, então ele não pode referenciar a tabela declarada ao lado. A garantia é uma trava.

**Todo componente de campo recebe os mesmos quatro**: o `field`, o `modelValue`, o `error` e o
`inputId`. O `FieldShell` desenha a mensagem do erro, e cada campo usa o `error` para **marcar o próprio
controle** como inválido — sem ele, a mensagem aparece e o controle não é apontado, que numa tela de
muitos campos é a diferença entre achar e procurar. **Um prop que ninguém lê é um prop que alguém
colou**, e uma trava lê cada componente e cobra que ele leia tudo o que declara.

**O conjunto é fechado, então `FIELD_COMPONENTS` é indexado**, e cada tipo tem um construtor em `resources/fields.js`,
que é o vocabulário com que um recurso é declarado. Uma trava percorre todo tipo que qualquer recurso
declara e cobra as duas metades: que exista um componente para ele e que exista um construtor.

**O catálogo do admin não guarda rótulo que nenhuma tela desenha**, e o do enum só guarda o que o
`/api/meta` publica — nas duas direções, porque um `enumName` escrito errado desenha um select vazio,
que se lê como um campo sem opção.

**Um segredo guardado diz que está guardado, e nunca aparece.** Todo campo `password` declara
`storedBy`, o nome do booleano que o registro responde.

**Chave estrangeira sempre usa `lookup`, nunca um `<select>` com a tabela inteira dentro.**

**A lista do lookup é desenhada fora do campo**, presa ao `body`. É o que a mantém inteira dentro de um
modal.

**Data e hora não usam o campo nativo do navegador.** `DateField` e `DateTimeField` são duas fachadas do
mesmo `DatePicker.vue`, e não existe uma terceira só de hora porque nenhuma coluna do schema guarda uma.

**A semana começa no dia em que ela começa para quem está lendo.** `FIRST_WEEKDAY` diz isso por idioma —
domingo em inglês e em português, **segunda em espanhol** —, e o cabeçalho e a grade leem o mesmo valor,
senão cada coluna nomeia um dia diferente do que está embaixo dela.

### Campos que dependem uns dos outros

```js
lookup("planId", "field.plan", "plans", { dependsOn: "integrationId" })
```

| Opção | Efeito |
| --- | --- |
| `dependsOn` | um nome ou uma lista; a consulta vai filtrada por ele e o campo fica fechado até o pai responder |
| `filterAs` | o nome com que o filtro chega ao recurso dependente |

Mudar um nível **esvazia todos os níveis abaixo**, em qualquer profundidade.

**Os dois usos de hoje são regras de verdade, e não enfeite:** o plano que uma integração pode apontar
é o do tenant dela, e o produto que um benefício pode entregar é o que o direito alcança. A tela filtra
e o service recusa.

### Ordenação

**O rótulo de um valor de enum é Title Case**, com as palavras pequenas em minúsculo: *Cancel at Period
End*, *Somente Acesso*. E **um nome próprio se escreve como o dono dele escreve**, tanto no rótulo do
enum quanto no que um lookup responde: um registro é nomeado por *Acme - RevenueCat*, e nunca pelo
código do tenant com o valor cru do enum.

Enum, select e lookup aparecem **sempre em ordem alfabética**. Enum ordena pelo rótulo traduzido, então
a ordem muda junto com o idioma. A comparação ignora acento e caixa e lê sequência de dígitos como
número.

### Regras das telas

**O painel desenha o que a conta alcança, e nunca desenha para depois tirar.** A navegação só completa
depois de `/api/meta` e `/api/meta/permissions` responderem, e enquanto isso o `AppBoot` ocupa a tela —
com o nome do produto e um indicador — em vez de um branco. Isso acontece **uma vez**, na primeira
navegação, para não piscar a cada clique.

**E um boot que falhou diz o que o impediu.** Mandar quem tem sessão para o login não resolve — o login
devolve ao painel e o boot recomeça, em laço —, então a tela de boot fica, carrega o motivo e oferece
começar de novo, que ali é a página inteira porque nada foi carregado.

| Peça | O que ela faz |
| --- | --- |
| `stores/permissions.js` | pergunta o que a conta alcança, guarda, e **esquece** quando outra conta entra |
| `AppSidebar` | desenha só o que ela alcança, e uma seção sem nada não vira um título sobre uma lista vazia |
| a guarda do roteador | recusa o endereço de um recurso que a conta não alcança, e não só o botão |
| `DashboardView` | os cartões saem de `RESOURCES` filtrado pelo que a conta alcança, com um ícone que o próprio recurso já declara |

**Uma resposta que chega atrasada não volta para a tela.** Digitar, ordenar, paginar e ir de um registro
ao seguinte sobrepõem requisições, e a mais antiga respondendo por último desenha o que ninguém pediu.
Quem responde por isso é `support/latest.js`, num lugar só: quem carrega toma um número e descarta o que
chegar depois de outro ter sido tomado. **No formulário isso não é só desenhar errado:** `save` faz
`PUT` no id do endereço, então uma resposta atrasada aceita ali **grava os valores do registro anterior
por cima do que a URL nomeia**. Uma trava recusa uma tela que volte a contar as próprias requisições.

**Grid** — busca, filtros e paginação no topo, 25 por página. **O filtro de tenant vem primeiro**,
logo depois da caixa de busca, porque é o corte mais largo que a tela faz e todos os outros estreitam
dentro dele. A primeira coluna é sempre o `id`, e o grid abre por `-id`. Clicar na linha leva ao lugar
mais longe que a pessoa pode ir.

**Visualização** — os mesmos grupos do formulário, em leitura, mais o `viewExtra` no fim.

**Formulário** — campos em fieldsets. O grupo `audit` só aparece na edição. Voltar e salvar levam
**sempre ao grid**.

**Exclusão** — sempre com confirmação em modal, nomeando o registro.

**Botão só existe se a permissão existir**, e **a URL é uma porta como outra qualquer**: a guarda do
roteador recusa `/new` e `/edit` de um recurso que não permite.

**E um endereço que nenhum recurso responde cai na tela de 404 do painel.** A rota `/:resource` casa com
qualquer segmento e é declarada antes do catch-all, então sem isso o `NotFoundView` existe e o endereço
que ele foi escrito para atender nunca chega nele.

**Alertas e avisos** — alerta na tela é `AppAlert`, aviso passageiro é o toast da store `ui`. Nunca
`alert()` do browser. **Uma listagem que falhou desenha o alerta, e não um toast**: o toast some, e o
que fica é o `EmptyState` dizendo que não há registros — uma recusa do servidor lida como uma tabela
vazia. **E um aviso é levantado pelo nome do tom dele**: a store expõe `success`, `error` e `info`, e
não um `notify(tom, mensagem)` que deixa existir um tom que a tabela não nomeia.

### Tema e layout

Tailwind 4, com o tema declarado em `@theme`. A paleta da marca é `brand-50` a `brand-900` em `oklch`,
com a matiz que o `config/base.py` declara. Duas classes de componente valem por todo campo:
`.field-control` e `.field-control-invalid`.

> **Armadilha conhecida:** o `<main>` precisa de `relative` e `min-h-0`. Sem `relative`, os elementos
> `sr-only` se ancoram no `html` e a página inteira ganha uma faixa em branco rolando embaixo.

Tudo é responsivo. Teste em 1440 e em largura de celular antes de dar como pronto.

### A barra superior do painel

Ela mostra a foto da conta, o botão do tema e o nome. **Onde não há foto ficam as iniciais** do nome pelo
qual a conta é chamada — que é o `displayName`, e não o username cru.

### Editor HTML

TinyMCE 8 auto-hospedado, sob GPL, com `license-key="gpl"` passado como **prop** do componente Vue —
passar dentro de `init` não funciona. O idioma vem do pacote `tinymce-i18n`, e apontar `language` pro
caminho `/langs/` não funciona porque o catch-all da SPA responde HTML.

**O editor responde por todo idioma que o painel oferece**, num mapa indexado direto: o catálogo do
TinyMCE nomeia os idiomas de outro jeito — `pt` é `pt_BR` lá — e o inglês é o único que ele já carrega.
Um ternário sobre três valores responde por dois, e quem escreve em espanhol escreveria num editor em
inglês dentro de um painel em espanhol.

> **E a suíte do painel monta os mesmos catálogos que o painel monta.** Um harness que carrega dois dos
> três é o que deixa o editor perder um idioma sem nada acusar.

Os imports de efeito colateral do TinyMCE têm **ordem semântica**, por isso
`importOrderSideEffects: false` no `.prettierrc`.

**A moldura é do `.editor-shell`, não do TinyMCE.**

---

## Publicar

Não há passo de migration à parte: o `entrypoint.sh` roda `manage.py migrate` e só então serve.

```bash
make docker-build
make docker-start APP_ENV=prod
make docker-administrator USERNAME=admin EMAIL=voce@dominio.com PASSWORD=…
```

**Uma imagem, um processo, três superfícies.** Não há serviço separado para o site, para o admin ou
para o cron. Escalar é subir mais cópias da mesma imagem.

**O que muda de comportamento vem do `config/prod.py`, não do comando.**

**Um comando entregue ao entrypoint não é executado, é engolido.** O `entrypoint.sh` aplica o schema e
termina em `exec uvicorn`, ignorando o que lhe passam — então uma receita que rode um comando na imagem
passa `--entrypoint python`, senão ela sobe **um segundo servidor web** que fica de pé para sempre. Uma
trava recusa uma receita que rode um comando na imagem sem sobrescrever o entrypoint.

**A pilha espera o banco em vez de morrer até ele existir.** O banco declara um healthcheck e a
aplicação depende dele com `required: false`, que é o que faz **uma produção cujo banco é externo não
arrastar o banco local**.

**E cada estágio do build copia o que aquele front-end alcança fora da própria pasta.** Os dois leem o
`webapps/declared.js`, que lê o `config/base.py`, e o do site lê `templates/` pelo `@source` do
Tailwind — os dois estágios espelham a árvore do repositório em vez de achatá-la, para o caminho
relativo ser o mesmo dentro e fora do container. Uma trava lê **cada estágio**, porque estar no outro é
não estar, e o pipeline chama `make docker-build`, que é a única coisa que prova um build.

> **Coluna nova num banco já publicado é manual, e isso é problema de quem publicou.** `migrate` cria
> tabela que falta e não altera tabela que existe — no template, onde o banco nasce do zero, isso nunca
> aparece.

### Quem pode falar por um cliente

**Um cabeçalho encaminhado vale exatamente o que vale a conexão que o trouxe.** O `--proxy-headers`
sozinho não basta: o uvicorn confia no `127.0.0.1` e em mais ninguém, e um nginx num contêiner ao lado
não é o loopback. O resultado é silencioso e duplo:

| O que quebra | Como aparece |
| --- | --- |
| todo endereço absoluto que este lado monta | sai `http` num site que é `https` |
| o limite por IP | toda requisição parece vir do proxy, então o teto por endereço vira um balde só e um abusador gasta o de todo mundo |

O `trusted_proxies` mora onde configuração mora, e o `entrypoint.sh` o lê **da mesma configuração que o
processo carrega**. O padrão é o loopback, que quer dizer *não há nada na frente*, e o `stage` em diante
nomeia as faixas privadas em que um proxy reverso vive.

> **Confiar em `*` só é correto onde a porta da aplicação não está publicada.** Com ela publicada,
> qualquer um forja o `X-Forwarded-For` e o limite por IP deixa de existir — que é pior do que o
> problema que ele resolveria.

### Rodar mais de uma cópia

| Peça | Como se comporta |
| --- | --- |
| a API e o site | sem estado: qualquer cópia responde qualquer requisição |
| o cron | toda cópia calcula a mesma ocorrência e **uma** a reivindica |
| `cron_queues` | divide **carga**, e nunca garante correção |
| o rate limit | conta em memória do processo |
| o storage | é do ambiente e o mesmo para todas |
| a sessão do banco | abre em `READ COMMITTED` |

---

## Nada em produção sem perguntar antes. É regra, não preferência.

**Toque nenhum em produção sem consulta explícita, e uma autorização não se estende para a próxima.**

| O que | Quem faz |
| --- | --- |
| `ALTER TABLE`, `DROP`, `CREATE INDEX`, correção de dado | eu escrevo, o Paulo executa |
| Criar registro pela API de produção | só com pedido explícito, daquela vez |
| Ler ou gravar no bucket de produção | só com pedido explícito, daquela vez |
| Usar a credencial da nuvem para qualquer chamada | só com pedido explícito, daquela vez |
| Deploy, restart, subir imagem | o Paulo |

**Não se testa em produção.** Nem sonda, nem objeto de teste, nem "só para conferir". Quando faltar
informação de produção, o certo é **pedir o log ou o resultado do comando**, e esperar.

**Antes de qualquer coisa em produção, ele precisa saber exatamente o quê, com todos os detalhes.**
Descrever depois de fazer não conta.

E a query é **gerada no dialeto de produção**, não escrita de cabeça:

```python
print(str(CreateIndex(index).compile(dialect=mysql.dialect())))
```

> **O ensaio começa achando a base, e essa é a parte que erra.** `git diff models/` só diz a verdade
> contra o commit que **está publicado**.

> **O `UUID()` do MySQL não é o `uuid4()` do Python.** Ele é de versão 1: carrega o relógio e o endereço
> da máquina. Para um `token` de conta — que existe para **não ser adivinhável** — isso não serve.

> **Nunca escreva um script que nomeie uma chave estrangeira gerada pelo MySQL.** O `_ibfk_N` numera
> **pela posição da coluna na tabela**. Resolva o nome pelo `information_schema`.

**O que a remoção esconde:** criar um banco do zero nunca acusa uma coluna que devia ter saído e não
saiu. Só o ensaio — montar o formato de hoje, aplicar o script, criar um segundo do zero e comparar
`information_schema` inteiro — mostra a diferença.

---

## Testes

**Meta: 100% de cobertura no backend.** Não é aspiração, é o estado atual e tem que continuar.

Backend em `tests/`, espelhando a estrutura do projeto. O pytest está configurado no `pyproject.toml`
com `asyncio_mode = "auto"` — teste assíncrono é só `async def`, sem decorator.

O `tests/test_app_flows.py` cobre o outro eixo: **um teste por jornada que uma pessoa faz**, encadeando
as chamadas na ordem em que um cliente as faz. São 21 fluxos.

A pasta `tests/routes/site/` cobre o site inteiro: cada página respondendo HTML e status de verdade, o
redirecionamento de quem não tem sessão, o CSRF recusado, o captcha recusado, a escolha de idioma, a
newsletter, o CEP, o checkout, o sitemap e o 404 desenhado.

**A suíte declara quatro coisas para si**, em `tests/conftest.py`, e cada uma carrega o motivo escrito:
o banco, o storage, o captcha e **quantas marcas ela serve**. O `dev` declara `image` no captcha, porque
quem desenvolve tem que ver na máquina o que o visitante vê — e um teste que tivesse de ler a palavra de
um PNG não provaria nada sobre a página que ele está testando. E ela roda em muitas marcas porque é o
modo que tem mais o que dar errado, enquanto `tests/test_single_brand.py` desliga isso para provar o
outro.

**E ela arma o que o `main.py` arma.** O que ela deixa de fora carrega o motivo escrito, e uma trava
falha quando ela arma menos sem dizer por quê — um harness menor que o produto prova menos do que diz.

O `tests/routes/test_crud_contract.py` cobre o contrato de **todos** os recursos CRUD de uma vez. Ao
adicionar um recurso, entre com o prefixo na lista.

- O `tests/conftest.py` cria um banco SQLite temporário e aponta o storage pra um diretório temporário.
- O `tests/factories.py` tem as fábricas, e **toda fábrica constrói uma linha sem marca**, porque marca
  única é o modo que o template traz e uma fábrica que exige tenant não escreve o caso normal.
- Fixtures prontas: `db`, `app`, `client`, `site`, `signed_in`, `tenant`, `administrator`, `member`,
  `currency`, `country`, `admin_headers`, `member_headers`, `tenant_headers`.
- Helpers de formulário: `token_in` e `opened`, que leem o token de CSRF que a página desenhou.

**A suíte constrói o schema uma vez e esvazia entre os testes.** Derrubar e recriar custa mais do que
esvaziar, e sobre uma suíte deste tamanho isso é a diferença entre minutos e segundos. O custo do
argon2 é configuração: `dev` hasha barato, produção e stage com os 64 MiB que o argon2 recomenda, e um
teste falha se um ambiente publicado baixar isso.

A cobertura precisa de `concurrency = ["greenlet", "thread"]` — a ponte assíncrona do SQLAlchemy roda
em greenlet, e sem isso linhas cobertas aparecem como não cobertas.

**O piso é de linha, e medir ramo também vale a pena de vez em quando.** Com `--cov-branch` a suíte dá
**99,83%**, e os quinze ramos parciais estão contados — nenhum deles esconde caminho:

| Quantos | O que é | Por que o outro lado não acontece |
| --- | --- | --- |
| dez | uma guarda no fim de uma função | o lado falso dela é o `return` que vem logo abaixo |
| dois | o topo de um laço que sempre acha o que procura | ele nunca chega ao fim sem ter saído antes |
| dois | as duas linhas de `helpers/db.py` que só o SQLite executa | quem as toma pelo outro lado é o ensaio contra o MySQL |
| um | o idioma de quem lê, em `banner.list_active` | ele é opcional pela convenção que toda listagem compartilha, e os dois chamadores sempre o passam |

Não é o piso porque um `...` de `Protocol` nunca vai ter os dois lados.

Admin e site com Vitest e jsdom.

**Validação visual:** mudança de tela se confirma no navegador contra um servidor de verdade, não só no
teste unitário.

Use e-mail `@acme.com` nos testes — o validador recusa `.test`, que é TLD de uso especial.

### O que a suíte não vê, porque ela roda em outro banco

**A suíte roda em SQLite e a produção em MySQL**, então sintaxe que só um dos dois aceita passa em todo
teste e falha exatamente onde importa. `tests/test_sql_portability.py` é a resposta escrita para isso, e
**a regra é maior que os casos dela:** toda vez que uma consulta usar algo que não seja SQL comum aos
três dialetos, ela se confere compilando no dialeto do MySQL.

**O jeito de achar o resto é subir um MySQL descartável e apontar a suíte para ele.** É como aparecem
os que nenhum teste em SQLite pode ver: uma ordenação de nulo que só um dialeto aceita, um nome de
tabela entre aspas duplas num `DROP`, uma palavra curta exigida na busca, uma coluna de data sem fração.

**Três coisas o ensaio pede da máquina, e nenhuma delas é do código:** a limpeza entre testes usa
`SET FOREIGN_KEY_CHECKS` no lugar do `PRAGMA`, o laço de evento tem que valer para a sessão inteira
— `-o asyncio_default_fixture_loop_scope=session -o asyncio_default_test_loop_scope=session` —, porque
o pool de um banco de servidor guarda conexão entre os testes e o SQLite abre em `NullPool`, e a fixture
que derruba `socket.connect` tem que abrir para a porta daquele banco.

**E ao rodá-lo, o que falha não é bug.** Quatro testes falham por serem do ensaio: o que confere o
`PRAGMA` do SQLite, o que afirma que o dev roda em arquivo, o que prova que a suíte não alcança a rede,
e um `recreate-schema` do `manage.py`, onde a sessão do teste segura a tabela enquanto outra conexão a
derruba.

> **O pool é o que decide se este ensaio anda.** Uma conexão ociosa do pool segura o lock que a
> reconstrução precisa, e o `DROP TABLE` para em *waiting for table metadata lock*. Abrindo o engine em
> `NullPool` — que é o que o SQLite ganha de graça — isso some. **Em produção nada disso existe**,
> porque o `manage.py` é um processo só, começa com o pool vazio e dá `dispose()` ao fim de cada `run`.

**E o que o ensaio prova de positivo é o que mais importa:** as tabelas que o código declara, mais as
duas que a fila e o cache trazem, com os índices, uniques e `FULLTEXT` que ele nomeia, nascem no
servidor exatamente como estão escritos, e a busca responde como está escrito aqui.

### O ensaio que só a concorrência de verdade acusa

**Um segundo ensaio existe e ele é o de vários nós.** Ele abre dezesseis **processos** contra o mesmo
MySQL, solta-os juntos numa barreira, e confere o que sobrou no banco. Como é ferramenta e não
comportamento, ele não mora no repositório.

**Toda escrita que se resolve por corrida passa por ele antes de ser dada como pronta**, e o que ele
mede é o que sobrou no banco e não o que o código diz:

| O que se mediu | O que aconteceu |
| --- | --- |
| 600 mensagens na fila de e-mail | **600 enviadas, uma tentativa cada**, nenhuma discada duas vezes |
| a mesma ocorrência de cron por dez workers | **uma linha por ocorrência**, e um `started` por ocorrência no registro |
| seis processos contando cinco senhas erradas cada | **30 de 30 contadas**, que é o que o `UPDATE` do banco garante |
| seis processos tomando as mesmas cinco chaves de idempotência | **cinco chaves e cinco respostas**, e os perdedores recusados |
| seis processos drenando a mesma fila de 120 eventos | **120 processados, uma tentativa cada**, nada preso em `processing` |
| a mesma fila com a reivindicação desligada | **719 linhas de registro para 120 eventos**, que é o defeito que ela existe para impedir |
| dezesseis registros mencionando a mesma imagem | **uma linha de arquivo, reivindicada uma vez** |
| dezesseis recuperações de senha do mesmo endereço | **um e-mail enfileirado** |
| dezesseis liquidações da mesma compra | **um produto possuído**, sem entrega dobrada |
| oito dizendo pago e oito dizendo reembolsado, sobre a mesma linha | nenhuma exceção, e a posse continua sendo uma |
| dezesseis reembolsos simultâneos | estornada, **e o produto continua da conta** |
| quatro registros soltando a foto enquanto doze varreduras rodam | **os quatro que uma página ainda menciona sobrevivem**, e o resto sai |

> **O ensaio prova que enxergaria.** Tirando a leitura do `rowcount` da janela da recuperação, os mesmos
> dezesseis processos enfileiram **seis e-mails** em vez de um. Um verificador que não acha nada não
> provou nada, e este acha.

> **O que ele pede da máquina:** o `settings.database.url` tem que ser trocado **antes** de `helpers.db`
> ser importado, porque o engine nasce no import, e cada `asyncio.run` precisa de um `dispose()` no fim
> — uma conexão do pool não atravessa dois laços.

> **E um verificador que não roda o código como uma requisição roda não está medindo o código.** Um
> ensaio que não commita acusa um total parado em zero, e um que roda em SQLite acusa o extrato perdendo
> lançamentos, porque ali o `FOR UPDATE` compila para nada. Nenhum dos dois é bug do projeto.

### Nada da suíte alcança uma máquina que não é esta

Uma fixture `autouse` derruba `socket.connect`, então **um teste que tente abrir conexão falha em vez
de sair**. O banco é arquivo e o cliente da API é in-process, então nada legítimo passa por ali.

O motivo é concreto: **o banco local carrega a chave de verdade do gateway sempre que alguém está
testando uma compra**. Com ela no banco, tudo que toca o caminho de refresh, checkout ou webhook fala
com o projeto de verdade — e uma passada ponta a ponta contra o servidor local já criou dois assinantes
vazios no painel do fornecedor.

**A regra que vale fora da suíte também:** um roteiro que exercite webhook, checkout ou refresh contra
o servidor local **stuba o gateway ou não roda**.

### Um verificador é código, e ele erra

Auditar o projeto com um script escrito na hora é o jeito certo de varrer — e **o script é código não
testado como qualquer outro**.

| Regra | Por quê |
| --- | --- |
| **abra o código que o verificador acusou** e confirme com os olhos | um relato falso custa mais caro que a varredura inteira |
| **um verificador que não acha nada não provou nada** | quebre alguma coisa de propósito e veja se ele acusa |
| **não case linguagem com nesting por regex** — conte colchete | uma definição cabe numa linha ou em vinte |
| **desconfie primeiro do verificador** quando o resultado for grande demais | vinte e sete recursos errados é um bug no verificador |
| **toda varredura tem piso**: ela afirma quantos itens encontrou antes de afirmar que nenhum estava errado | uma expressão que parou de casar deixa a trava passando para sempre sem conferir nada |
| **uma asserção salva por um `or` não confere nada** | o lado que sempre passa esconde o lado que nunca casou |
| **uma trava lê a superfície que ela protege, e não uma cópia dela** | uma cópia dentro do verificador sobrevive ao que ela copiou |
| **uma trava que nomeia o que ela confere cobre o que alguém lembrou de nomear** | achar no fonte cobre o próximo sem ninguém precisar lembrar |

---

## Commits

Mensagem em inglês, no imperativo, uma linha, minúscula depois do prefixo e sem ponto final. O prefixo
é o domínio tocado:

```
commerce: hand the credits of a product over the same way however it was obtained
site: draw every public page from the server so a crawler reads what a visitor does
storage: discard the orphan files no row of any table mentions
```

Commit ou push só quando pedido. **Vai direto na `main`** — não se cria branch e não se abre PR.

**Um pedido de commit é um commit.** O conjunto de trabalho vai numa mensagem só, e não fatiado por
domínio.

**Script de teste ou ferramenta de apoio não entra no repositório**, a não ser que o Paulo diga que
entra. E um commit **não carrega carona**: se a mensagem fala de uma coisa, o commit contém aquela
coisa, e mais nada.

---

## Armadilhas conhecidas

| Sintoma | Causa e saída |
| --- | --- |
| Caminho errado da API responde 200 com HTML | o site pega tudo que sobrou: quem serve a raiz recusa o que é da API antes de desenhar |
| O site responde JSON num endereço que ninguém digitaria | um segmento que não pode nomear um registro é a página desenhada de 404 |
| Um bug numa página mostra JSON cru ao visitante | o 500 do site é desenhado como o 404, e só a API responde JSON |
| Toda leitura de uma tabela responde `Unknown column` em produção | uma coluna saiu do banco antes de o deploy sair — adição antes, remoção depois |
| Banco migrado com `DEFAULT` que o criado do zero não tem | o default preencheu as linhas velhas e ficou |
| Ensaio de produção acusando mudança que não existe | ele foi montado sobre um commit que não é o publicado |
| `ModuleNotFoundError` de dependência recém-declarada | uma receita chamou a ferramenta pelo console script, no Python de quando o venv nasceu |
| `node_modules` na raiz do repositório | um `npm` sem `--prefix webapps/...` |
| A suíte passa na máquina de quem desenvolve e quebra na CI | ela lê o que um build escreve, e o `dist` sobra de um build anterior |
| Lançamento de crédito repetido virando 500 | ler pela chave de idempotência e depois inserir é um `SELECT` que dois nós atravessam juntos |
| 500 ao gravar duas vezes o mesmo vínculo | `db.commit()` direto; use `helpers.db.commit` |
| Excluir uma linha apontada responde que ela já existe | a exclusão passa o código dela, e não o da duplicata |
| Excluir um registro que alguém aponta responde 500 | a recusa vem do `execute` de um filho, e a tradução é do bloco inteiro |
| Uma exclusão recusada apaga o arquivo do registro que sobreviveu | o arquivo sai depois da linha, e nunca antes |
| `MissingGreenlet` ao serializar | relação não carregada; declare em `relations` |
| `MissingGreenlet` depois de um conflito de unicidade | `rollback()` expira **todos** os objetos da sessão; use `begin_nested()` |
| `SAVEPOINT ... does not exist` sob concorrência de verdade | o InnoDB matou a transação da vítima do deadlock: quem perdeu repete a operação |
| `Deadlock found` em algo que o `insert_or_read` protege | em `READ COMMITTED` a releitura é um `SELECT` simples |
| Uma passada de cron morre inteira com dez nós | uma varredura sobre a tabela toda estava dentro dela: varredura é do job, que um nó só roda |
| Reler dentro da mesma transação responde o que já mudou lá fora | a sessão abre em `READ COMMITTED` por causa disso |
| Banco de produção conecta no host errado | senha com `@` ou `#` crua na URL — escape com `quote(senha, safe="")` |
| Linha compartilhada some do filtro | `IN (id, NULL)` não casa com nulo; use `reaches_tenant` |
| Dois usuários globais com o mesmo e-mail | `UNIQUE(tenant_id, email)` não vê nulo; a unicidade é sobre `COALESCE(tenant_id, 0)` |
| Excluir um tenant responde 500 | um `Dependent` nomeia uma coluna que foi renomeada |
| Filtro com valor inválido responde a lista inteira | um valor que a coluna não lê é 422 |
| Um filtro que aponta para um direito inexistente responde o catálogo compartilhado | um escopo nulo lê como as linhas compartilhadas: o filtro cobra que a linha exista |
| Busca com palavra de duas letras responde vazio | o InnoDB não indexa abaixo de três |
| `Can't find FULLTEXT index matching the column list` | `text_search_fields` sem o `search_index` do model |
| Login do cliente responde 422 pedindo `X-Tenant-Code` | a identidade é única por tenant |
| Cobertura mostra `return` não coberto | falta `concurrency = ["greenlet", "thread"]` |
| Tela que passa em todo teste e responde 500 em produção | a suíte roda em SQLite e produção em MySQL |
| Um `position` passa em toda a suíte e responde 500 em produção | o SQLite guarda o que lhe derem e a coluna é de 32 bits no MySQL |
| Tirar a trava do saldo passa em toda a suíte | o SQLite compila `FOR UPDATE` para nada, e a trava lê o texto no dialeto do MySQL |
| Uma listagem devolve outra primeira linha no PostgreSQL | ordenar por coluna anulável sem dizer o que fazer com o nulo, que cada banco lê de um lado |
| Criar o schema no PostgreSQL falha por nome repetido | um índice é do banco inteiro lá: todo nome começa pela tabela dele |
| Duas coisas iguais comparam diferente depois de um round-trip | o `DATETIME` do MySQL trunca o microssegundo: a coluna pede `DATETIME(6)` |
| Validação recebe `None` num campo com default | `exclude_unset=True` descarta o que não veio; use `declared()` |
| Um id enorme na URL, no filtro, no `offset` ou no corpo responde 500 | ele estoura dentro do driver: todo número lê o teto da coluna em que ele cai |
| Arquivo órfão após excluir o pai | o que o `Dependent` apaga é o que o service do filho declara que as linhas dele mencionam |
| Uma imagem tirada do corpo de uma página fica no bucket para sempre | um arquivo sai quando a linha para de mencioná-lo, e o corpo é uma das formas de mencionar |
| A varredura apaga as imagens que o `make seed` acabou de escrever | quem escreve fora da fábrica reivindica o que nomeia, e reivindicar lê chave, markup ou uuid |
| A varredura de órfãos estoura a memória num storage grande | ela lê as próprias linhas em lote, e nunca as tabelas nem o bucket |
| Servidor cai quando alguém envia um arquivo grande | o corpo tem que ir para um `SpooledTemporaryFile` |
| Um upload de poucos KB derruba o processo | uma imagem tem teto no que ela pesa depois de decodificada, conferido antes de alocar |
| Um PNG pequeno responde 500 em vez de uma recusa | o erro do decodificador precisa estar entre os capturados |
| Um `POST` de dois gigabytes derruba o processo | um corpo que se lê inteiro tem teto, cobrado na porta por `helpers/payload.py` |
| Um cabeçalho anula o teto de corpo | a isenção é do endereço que recebe arquivo, e não do content-type |
| Nenhum upload funciona num bucket S3 criado hoje | um bucket novo nasce com ACL desabilitada, e um upload que nomeia uma é recusado com 400 |
| Um leitor apaga a imagem de um produto do bucket | só a pasta da finalidade daquela coluna é aceita |
| Uma chave com `../` passa pela conferência de finalidade | começar com a pasta certa não basta, e o storage recusa a chave que sai da raiz |
| Cliente recebe o caminho do arquivo em vez do endereço | a rota respondeu o schema do admin |
| Página com faixa branca rolando | falta `relative` no `<main>` |
| Slug recusado ao salvar | `slugify` tem que receber `column_length(campo)` como limite |
| Um `tag` quebra o `sitemap.xml` inteiro, ou um card abre um 404 | um endereço é um slug tenha ele sido digitado ou derivado |
| Dois conteúdos salvam e um deles nunca abre | a tag é um endereço, e ela é única dentro do tenant e do idioma |
| Assinatura volta a valer e nunca mais entrega | um benefício encerrado é revivido no `activate` |
| Quem subiu de plano passa a ter o dobro | `activate` encerra o que o plano de agora não promete |
| Duas assinaturas ativas para uma compra só | quem impede é `UNIQUE(user_id, integration_id, external_product_id)` |
| Evento parado em `processing` para sempre | `webhook_service.retry_failed` recolhe o que passou de `ABANDONED_AFTER` |
| Um evento reportado vira duas linhas do registro | a passada reivindica a linha antes de trabalhá-la |
| Renovação perdida some depois do relógio expirar | a reconciliação olha também o que fechou nos últimos dois dias |
| Chave do gateway recusada e nada acontece | um 401 ou 403 é configuração, não rede: vira `error` no registro do sistema |
| A varredura pergunta sobre a mesma conta para sempre | fechar o que já está fechado responde zero, sem reescrever `expired_at` |
| Uma rajada de refresh vira uma rajada de chamadas ao gateway | a janela tem que ser tomada com um `UPDATE` condicionado |
| Um aviso do Stripe fecha a outra assinatura da conta | um aviso é sobre uma coisa: `apply` recebe se a lista é completa |
| Assinatura do Stripe sem período | o período mora no item, e não na assinatura |
| Uma compra reembolsada continua dizendo paga para sempre | o pagamento é liquidado antes de a conta ser resolvida |
| Uma disputa perdida não aparece em lugar nenhum | a compra é estornada pelo estado da disputa, e uma ganha volta a paga |
| Uma chamada de gateway capturada pode ser reenviada para sempre | os dois assinam cada entrega de novo, então o carimbo tem cinco minutos |
| Um segredo de webhook em rotação é aceito ou recusado conforme a ordem | um `dict` guarda a última `v1`: quem lê o cabeçalho é `signature_parts` |
| Alguém pagou um centésimo do que pagou | o valor é lido na unidade mínima da moeda, e nem toda moeda tem centavos |
| O comprador pagou menos do que a página dizia | `minor_units` arredonda, porque truncar corta o que a moeda não guarda |
| Um pagamento em dinar é gravado com menos do que foi pago | a coluna de dinheiro guarda três casas |
| Chamada de webhook responde 500 em vez de 401 | `hmac.compare_digest` recusa strings não-ascii: compare bytes |
| Um upgrade abre uma segunda assinatura | `adopt` mantém o `external_id` igual ao que o provedor reporta agora |
| Uma compra fica `pending` para sempre e nunca existiu | a sessão que o gateway recusou fecha a linha que ela abriria |
| Quem paga pelo site cai numa página de não encontrado | o retorno sai de `Brand.address`, e uma asserção com `endswith` não vê barra dupla |
| Quem digita menos cinquenta num crédito vê cinquenta entrar | uma movimentação dirigida recebe grandeza, e só o ajuste carrega sinal |
| Uma conta vê o produto como se possuísse, e ela não possui | posse é de uma conta e o valor guardado é de todo mundo: o catálogo é guardado sem ela |
| Imagem some depois de o tenant ganhar bucket próprio | o upload acontece antes de o registro existir: o storage é do ambiente |
| Lookup mostra primeiro quem não tem nome | `label_ordering` ordena o nulo por predicado |
| A mesma linha aparece em duas páginas do grid | ordenação por coluna que repete sem desempate: toda ordem fecha pelo `id` |
| Uma listagem por tag mostra um card em outro idioma | a listagem responde uma linha por tag, pela mesma regra que a tag abre |
| A mensagem fica `failed` para sempre e ninguém recebe | o template guardado carregava a própria pasta, e quem envia monta o caminho |
| Um e-mail chega com um link em branco | a trava cobra que a chamada entregue todo nome que o template lê |
| Uma página sai com um pedaço faltando e nada acusa | o Jinja responde vazio para o indefinido: o ambiente é `StrictUndefined` |
| Um aviso do gateway some sem deixar linha | um carimbo que não se lê levantava antes de o evento ser gravado |
| Escrever para um endereço morto queima o domínio | a recusa do destinatário suprime o endereço, e a de autenticação não |
| O site não acha tenant nenhum e não desenha nada | o host não casa com `Tenant.domain` e o ambiente não nomeia um default — o log diz qual |
| O `sitemap.xml` aponta para um IP ou para o host de outra pessoa | todo endereço absoluto sai de `Brand.address` |
| Um buscador acha um 404 logo no primeiro endereço do sitemap | uma página de conteúdo não é entrada estática: a varredura já a lista quando ela existe |
| Uma página pública não é achada por buscador nenhum | ela responde igual para todo mundo e tem que estar no `sitemap.xml` |
| Apagar um conteúdo deixa um link morto no rodapé de todo o site | a navegação desenha só a tag que responde, resolvida numa consulta |
| Um link compartilhado com `?utm_source=` vira uma página nova no buscador | o canonical é o endereço da página, e não o endereço com que se chegou |
| Um monitor de uptime diz que o serviço está fora do ar | ele pergunta com HEAD, e uma rota do FastAPI só honra o método que ela declara |
| Uma cópia sem banco continua recebendo tráfego | a sonda de prontidão é a que pergunta ao banco |
| Formulário do site responde 422 sem dizer o campo | o token de CSRF não veio, ou o cookie que responde por ele não estava lá |
| Um formulário do site responde JSON numa tela preta | o captcha desenha a página de novo e o CSRF redireciona |
| Um campo do site é recusado e a página não aponta nada | a página marca o campo pelo nome com que ela o desenhou, e não pelo nome da rede |
| Um leitor de tela não é avisado de que o campo foi recusado | o controle carrega `aria-invalid` e nomeia a mensagem |
| Um leitor de tela anuncia um campo sem nome | uma legenda nomeia o grupo, e o controle precisa de um `<label for>` |
| Um botão de fechar é anunciado como um botão vazio | o ícone é `aria-hidden`, então o botão precisa dizer o que faz |
| Um teclado percorre o menu inteiro em toda página | o primeiro focável é o salto para o conteúdo |
| Um controle desenhado por JavaScript fala inglês | a página passa as palavras, e o módulo as lê pelo nome |
| Uma tela pula de `h1` para `h3` | uma seção com título fica um nível abaixo do título da tela, nas duas superfícies |
| A página do site sai com `{{` no meio | um bloco declarado num `include`, que não cruza a fronteira: o bloco mora no layout |
| Uma macro do site responde `t is undefined` | `{% from … import … with context %}` |
| Apertar Enter num campo do site faz sair da conta | um formulário de logout desenhado antes do formulário da página é o primeiro `form` do documento |
| Desabilitar o botão no envio perde o valor que o servidor lê | ele é marcado e nunca desabilitado, porque vários botões carregam `name` e `value` |
| Apertar Enviar numa página com reCAPTCHA não faz nada | o formulário sai de qualquer jeito, e o servidor recusa dizendo o motivo |
| O botão de entrar do painel gira sem fim e sem mensagem | um `new Promise` sem `reject` nunca se resolve |
| Salvar um endereço responde 422 sem dizer nada errado | o país não está no cadastro: `error.country-not-offered` |
| O CEP não é procurado em lugar nenhum | o país daquele endereço não declara provedor |
| O CEP preenche o endereço de um código que já foi trocado | só a última busca preenche |
| Corrigir um dígito no meio do telefone joga o cursor para o fim | o cursor volta contado em dígitos, e não em caracteres |
| O captcha não aparece em nada rodando local | `dev` declara `image`, e é a **suíte** que o desliga para si |
| Uma compra da noite aparece com a data do dia seguinte | o site desenha o instante no fuso da conta |
| Uma página em português mostra `BRL 99.90` | um valor é escrito pelo `money`, que agrupa e separa como quem lê escreve |
| Um idioma novo mostra o número no formato do inglês | o formato é indexado, então um idioma sem formato falha onde ele foi escrito |
| Uma tela quebra só para quem lê em espanhol | a tradução nomeava outro placeholder, e as travas comparam os três catálogos |
| Um rótulo falta em espanhol e nenhuma trava reclama | os catálogos saem da pasta e são contados contra os idiomas oferecidos |
| Um botão do painel mostra `action.format` como rótulo | comparar catálogos entre si não acha a chave que falta nos três |
| Quem escreve em espanhol escreve num editor em inglês | o editor lê um mapa indexado, e não um ternário |
| O calendário do painel abre no domingo para quem lê em espanhol | a semana começa onde ela começa para cada idioma |
| Um campo do painel aparece como caixa de texto sem ninguém pedir | o mapa de tipos é indexado, e uma trava cobra componente e construtor |
| Um campo do painel desenha um select sem nenhuma opção | o `enumName` não é publicado pela API |
| Um tom ou um ícone escrito errado desenha o neutro | nenhum conjunto fechado do painel é alcançado por queda |
| Um erro de validação aparece e o campo não é apontado | todo componente recebe o `error` e marca o próprio controle |
| Salvar um registro grava os valores do anterior por cima | a tela recarrega ao trocar de endereço, e a resposta atrasada era aceita |
| Uma listagem que o servidor recusou diz que não há registros | as três telas de recurso desenham o mesmo alerta |
| Um endereço errado no painel responde uma página em branco | o que nenhum recurso responde vai para a tela de 404 |
| O painel abre em branco quando a API não responde | a tela de boot fica e diz o que impediu, com um caminho de volta |
| O painel para de achar a API depois de uma mudança de configuração | o build entrega o que o servidor declarou |
| O webhook colado no console do gateway aponta para lugar nenhum | o mesmo, e a trava lê o painel inteiro |
| Uma tela inteira do painel responde 500 numa instalação de marca única | o schema de leitura exigia `tenant_id`, e nenhuma tabela exige tenant |
| O lookup de integração responde `AttributeError` | quem nomeia a marca onde não há tenant é o `Brand` |
| Reordenar as fotos joga as que não apareciam para a frente | a tela não oferece uma ordem que ela não pode escrever inteira |
| Abrir um conteúdo pelo painel cai na página de 404 do site | o link carregava tenant e idioma, e uma página é um endereço só |
| Um editor rouba o token de um administrador pelo corpo de uma página | o painel desenha aquele markup num `iframe` com `sandbox` |
| Um editor põe `javascript:` num banner e ele roda na home | um destino é um tipo, e ele recusa o esquema que um navegador executa |
| Uma descrição formatada aparece com `<p>` literal na página | o que o painel autora como markup é o que o site desenha assim |
| Um operador planta uma foto na galeria de outra marca | toda chave estrangeira do payload aponta para uma linha que ele alcança |
| Um editor de uma marca lista o conteúdo de outra | toda leitura e toda escrita são confinadas pela conta que opera |
| Um papel novo no enum alcança o painel sem ninguém decidir | quem trabalha no painel é nomeado um a um |
| Um recurso do admin abre para todo mundo | a fábrica lê `CrudService.roles`, e o padrão é administrador |
| Uma rota nova responde 200 para quem não devia | a matriz de papéis falha até alguém dizer de quem ela é |
| Uma listagem responde vazio no lugar de 404 | uma linha que não é do chamador não existe |
| O tempo da resposta diz quais contas existem | um login de ninguém é conferido contra um hash de ninguém |
| Adivinhar a senha de uma conta não tem freio | o limite conta endereço, e a espera é contada na conta |
| Tentativas simultâneas contam menos do que aconteceram | o incremento é do banco, num `UPDATE` |
| Pedir recuperação em série enche a caixa de alguém e queima o token dela | a janela é tomada com um `UPDATE` |
| Um formulário aberto vira um megafone para o endereço de outra pessoa | a janela do convite é tomada do mesmo jeito |
| Um cookie faz toda página do site responder 500 | um valor assinado para um propósito não verifica como outro |
| Um cache na frente entrega o token de CSRF de um visitante a todos | a resposta que é de um leitor só diz `private, no-store` |
| Um cookie novo nasce sem `httponly` e um script passa a lê-lo | só o `helpers/cookies.py` escreve cookie |
| O login do painel é desenhado dentro da página de outro site | toda resposta carrega os três cabeçalhos que o navegador cobra |
| Uma instalação assina tudo com uma chave que está no GitHub | o processo recusa subir com o marcador que a configuração publicada traz |
| Todo link de produção aponta para `localhost:8000` | com uma marca, `site.domain` é todo endereço absoluto |
| Um ambiente publicado novo serve cookie de sessão sem *Secure* | o default é o valor implantado, e o `dev` é quem afrouxa |
| Todo link que sai por e-mail aponta para `http` num site `https` | o servidor não sabe quem pode falar por um cliente |
| O limite por IP não limita ninguém | idem: toda requisição parece vir do proxy |
| Quem bate no limite recebe uma página em branco sem explicação | a recusa do limitador monta o mesmo corpo de erro que o resto |
| A memória do processo cresce até ele morrer | o contador do rate limit guardava todo endereço que já chamou |
| Uma requisição qualquer trava por dezenas de milissegundos | o argon2 e o banco de fusos não rodam no laço |
| Uma página do site fica mais lenta a cada registro cadastrado | uma leitura por linha dentro do laço: a capa de N galerias sai numa consulta só |
| Uma listagem da API fica mais lenta a cada registro cadastrado | a mesma coisa do outro lado |
| A passada de uma fila fica mais lenta a cada mês de operação | o índice dela é `(status, tempo)`, e é o valor raro que o faz pagar |
| A tabela mais escrita do sistema paga um índice que nada usa | `level` e `category` têm cinco valores cada |
| Uma edição no painel não aparece no site | o que vale é o `ttl`, e o `dev` não liga o cache |
| O cache é ligado em produção e mesmo assim tudo vai ao banco | um `Decimal` não cabe em JSON: a store recusa com um aviso no log |
| Uma página desenha um tipo com o cache ligado e outro com ele desligado | a montagem sai por `model_dump(mode="json")` e volta pelo mesmo schema |
| Uma página com `tag` longa nunca é cacheada, ou responde o conteúdo de outra | as partes viram digest e a chave tem largura fixa |
| Um 200 de um terceiro com HTML dentro vira 500 nosso | todo corpo de terceiro passa por `helpers.remote.body_of` |
| O CEP preenche o formulário com campos vazios | um corpo sem cidade e sem estado não nomeia lugar nenhum |
| Um aplicativo não consegue contar uma view | só este lado assina um nome: `GET /api/meta/visitor` entrega um |
| Quem recusou analytics segue mandando duas chamadas por página | o banner só é marcado como contável onde a contagem vale |
| Retirar o consentimento deixa a paleta guardada por um ano | a resposta reescreve os dois cookies de preferência |
| O rodapé não pode ser clicado na primeira visita | o aviso de cookies é `sticky` e reserva o espaço dele |
| A página pisca em claro antes de ficar escura | o servidor escreve a classe |
| O botão primário do tema claro é roxo e não a cor da marca | um tema é declarado uma vez, senão a paleta de fábrica ganha por especificidade |
| O botão primário do tema escuro parece desabilitado | o `black` do plugin é monocromático, e o ajuste passa pela API dele |
| Um erro de campo some sobre o card branco | as cores semânticas do tema claro são de preenchimento |
| O botão de tema gira para um lado no site e para outro no painel | uma trava lê o arquivo do outro lado |
| O mesmo botão é roxo num tema e azul no outro | a marca é declarada num lugar, e os dois builds derivam a rampa dela |
| A logo some no tema escuro | ela é desenhada com `currentColor` |
| O X de um alerta fica colado na frase | o `alert` é um grid, e o `flex-1` ao lado dele não faz nada |
| Um link do menu ganha uma caixa cinza atrás dele | um navbar é uma fila de links, e um `menu` é uma lista de opções |
| Uma classe da migração antiga não desenha nada | a trava compara o que os templates usam com o que a folha construída define |
| Um `data-` sobra na marcação depois de uma reescrita | a trava cobra que algo o procure, nas duas grafias |
| Uma cor crua volta a aparecer numa tela | a trava percorre templates e os dois front-ends |
| Uma mudança de css ou de script não aparece sem recarregar à força | a versão do asset é a data do build |
| Mudar o visual de um card pede editar onze arquivos | a peça é chamada, e uma trava recusa a forma dela escrita à mão |
| Um módulo novo do site nunca roda | o `main.js` não o chama, e a trava cobra que todo `bindX` seja iniciado |
| Um clone novo responde a página de 404 em `/admin` | o `dist` do painel não é versionado: o roteiro de início constrói toda superfície |
| `make docker-build` falha e a suíte inteira passa | uma trava lê cada estágio, e o pipeline constrói a imagem |
| Um estágio do build acha um arquivo por caminho relativo e o outro não | os dois espelham a árvore do repositório |
| `make docker-administrator` pendura e não cria conta nenhuma | o comando ia como argumento do entrypoint, que serve e ignora o que recebe |
| A aplicação morre e volta algumas vezes no primeiro boot | o banco tem healthcheck e a dependência é condicional |
| `make seed` morre com um future preso ao laço anterior | quem dirige a sessão compartilhada não abre laço por fora do `run_scoped` |
| `make seed` deixa o site sem plano, sem banner e sem conta | o seed costura `Brand`, e não `Tenant` |
| A pasta `data/media` cresce a cada `make seed` | um banco recriado deixa todo arquivo órfão, então o storage é esvaziado junto |
| Abrir um tenant e salvar sem mudar nada responde 422 | o endereço derivado de um domínio de uso especial é recusado |
| `make sweep-files` acha zero órfãos e reporta erro | listar é o que ele foi mandado fazer, e ele fez |
| O `schema-diff` manda derrubar a tabela do cache | os dois lados iteram sobre a mesma lista de schemas |
| O ensaio contra o MySQL falha oito testes do `manage.py` | um engine com pool não atravessa dois `asyncio.run` |
| A página de planos mostra *Every None Month* | a unidade e o número são uma regra só |
| Uma página de conteúdo mostra `None` no lugar do texto | uma coluna opcional é desenhada como opcional |
| Um produto aparece no catálogo sem nome nenhum | um texto que a linha tem que ter é `Text(n)` |
| Uma conta sem e-mail não consegue se apagar | a confirmação pede a identidade que a conta tem |
| Excluir a própria conta no painel responde "registro duplicado" | ninguém exclui a linha em que está logado |
| Uma linha do registro de auditoria aparece do nada | uma identidade não carrega quebra de linha |
| Assinar sem sessão termina em página não encontrada | voltar do login é um GET, então o destino é a página em que o formulário foi desenhado |
| Uma trava passa a não conferir nada | `__subclasses__()` enxerga um nível, e um service com base própria sai da varredura |
| Uma trava passa para sempre por causa de um `or` na asserção | o lado esquerdo é um regex que nunca casou |
| Um número da prosa envelhece sem nada acusar | escrito em negrito ele escapa da trava, que tira a ênfase antes de ler |
| Um guia mostra um endereço que a API não responde | a trava lê o caminho e o método contra as rotas registradas |
| Uma finalidade de upload nova responde `KeyError` na rota dela | a tabela é o `return` de uma função, e a varredura lê todo literal |
| Uma rota nova responde 404 ou cai na rota errada | um literal declarado depois de um parâmetro do mesmo método nunca responde |
| Um comando novo do `manage.py` roda a passada de entrega | todo comando é nomeado num mapa, sem queda por fora |
| O processo sobe e responde 500 em toda rota | o idioma padrão não está entre os oferecidos, e a configuração recusa isso no import |
| Um parâmetro que ninguém lê atravessa dez chamadas | a trava recusa, e o que outro declara é nomeado com o motivo |
| Um campo novo responde snake_case ao lado dos outros em camelCase | o schema não estava sobre o `BaseSchema` |
| Um tipo novo de benefício marca toda concessão como falha em silêncio | a trava dos conjuntos fechados acha as tabelas no fonte |
| Uma tela some depois que alguém trocou o `PROVIDERS` | o mapa é indexado e responde por todo valor do enum |
| Um provedor incompleto quebra dentro de uma requisição | a base recusa a subclasse vazia, e o `PROVIDERS` a constrói no import |
| Um provedor de storage novo vira S3 sem ninguém pedir | ele é indexado por enum, e não alcançado pelo último `if` |
| A suíte prova algo que a aplicação de verdade não faz | o `conftest` arma o que o `main.py` arma, e o que fica de fora carrega o motivo |
| Um upload dentro do teto é recusado com 413 antes de chegar | o `client_max_body_size` do nginx é o `upload_max_bytes` escrito de novo |
| A imagem constrói num Python que ninguém confere | o `Dockerfile` é o quinto lugar que nomeia a versão |
| Uma trava de documentação quebrada é publicada com a CI verde | o pipeline não roda num commit que só toca a prosa, então quem a edita roda `make test` na máquina |
| A cobertura local passa em 98% e o pipeline recusa | o piso é do `pyproject.toml` |
| A CI passa e o comando local falha, ou o contrário | ela chama a receita, que é a única que alguém roda |
| A prosa conta um conjunto que mudou de tamanho | ele é contado do esquema, e não escrito à mão |
| Uma folga do `stage` aparece na produção | os dois derivam do `dev` e nenhum herda do outro |

---

## Antes de dar como pronto

- [ ] `make format` rodado
- [ ] `make test` passando, cobertura do backend em 100%
- [ ] `make admin-test` passando e `make admin-build` sem erro
- [ ] `make site-test` passando e `make site-build` sem erro
- [ ] chave de tradução adicionada nos três catálogos, dos dois lados
- [ ] mudança de tela conferida no navegador
- [ ] nada de comentário de várias linhas, nada de chamada quebrada em várias linhas
- [ ] se mexeu em model: `models/registry.py` atualizado e banco local **recriado** — este repositório é
      um template, então não há migration a escrever nem DDL a acumular
