"""
O catálogo de entendimentos — as regras que o motor lê.

NÃO É UM FICHÁRIO. Cada entrada declara um `efeito`, e é o efeito que o motor
aplica. Uma lista de temas para leitura humana não seria software; seria um
documento com sintaxe de configuração.

A TRAVA: `homologado = "N"` em tudo que não passou por advogado, e entrada
não homologada **não produz permissão**. O motor prepara; quem assina é
gente. É a mesma disciplina de `titulos.py`, pelo mesmo motivo: uma
afirmação sobre o direito de alguém, feita por software sem revisão, é uma
afirmação que ninguém assinou.

A AUTÓPSIA recusa entrada que diria algo sem ter de onde: homologada sem
fonte, efeito que o motor não conhece, trilha inventada. Fail-closed — uma
entrada defeituosa não entra no catálogo em silêncio.

UM ARQUIVO POR CATEGORIA, e é a divisão que faz o produto atender mais de um
sindicato. Era um arquivo único com `categoria` no topo: funciona para um
contrato, e com dois sindicatos de categorias diferentes passa a avaliar o
filiado de um contra as ações do outro. Agora cada arquivo de
`config/categorias/` é o catálogo DE UMA categoria, o nome do arquivo é o
slug, e a entidade declara quais categorias contratou.

A TABELA DE GRAFIAS DE CARGO MORA AQUI, no `cargos` de cada arquivo, e não em
Python. Enquanto morasse no código, acrescentar categoria era mexer no
código — e é assim que a tabela para de crescer e todo mundo de uma carreira
nova vira INDETERMINADO para sempre.
"""
from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

#: As duas trilhas. "ambas" existe para entendimento que vale nas duas —
#: prescrição, por exemplo, corre tanto para quem executa quanto para quem
#: ajuíza.
EXECUTAR = "executar"
AJUIZAR = "ajuizar"
AMBAS = "ambas"
TRILHAS = (EXECUTAR, AJUIZAR, AMBAS)

#: Efeitos que o motor sabe aplicar. Efeito fora desta lista é erro de
#: catálogo, não comportamento silencioso: alguém escreveu uma regra que
#: ninguém lê, e descobrir isso quando o veredicto sair errado é tarde.
EFEITOS = (
    "dispensa_liquidacao_se_calculo_aritmetico",
    "legitimidade_fora_do_rol_indeterminada",
    "coisa_julgada_alcanca_a_categoria",
    "prazo_prescricional",
    "limite_a_rescisoria_contra_titulo",
)

#: Situações em que um entendimento pode estar.
SITUACOES = ("afetado", "julgado", "transitado", "a_conferir")


#: Onde os catálogos de categoria moram. Mesma postura de
#: `cadastro.CONTRATO`: o caminho é do repositório, não de configuração —
#: catálogo é código revisado, não ajuste de ambiente.
PASTA_PADRAO = Path(__file__).resolve().parent.parent / "config" / "categorias"


class ErroDeCatalogo(ValueError):
    """Defeito no catálogo. Nominal, para virar motivo legível."""


@dataclass(frozen=True)
class Entendimento:
    id: str
    #: De quem este entendimento fala. Preenchido pelo arquivo que o contém,
    #: não entrada por entrada. É o que permite ao motor recusar uma tese de
    #: outra carreira em vez de oferecê-la a quem passar.
    categoria: str = ""
    tribunal: str = ""
    tema: str = ""
    recursos: tuple[str, ...] = ()
    #: Número CNJ do recurso representativo. VAZIO = não monitorável, e o
    #: motor diz isso em vez de fingir que acompanha. O STJ publica
    #: "REsp 2.146.834/AP", que é número de registro; o DataJud só aceita
    #: número CNJ, e o registro do STJ no DataJud não traz o do REsp.
    numero_cnj: str = ""
    relator: str = ""
    orgao: str = ""
    situacao: str = "a_conferir"
    julgado_em: str = ""
    afetado_em: str = ""
    suspensao_nacional: bool = False
    questao: str = ""
    tese: str = ""
    trilha: str = AMBAS
    efeito: str = ""
    criterios: tuple[str, ...] = ()
    fonte: str = ""
    observacoes: str = ""
    homologado: str = "N"

    @property
    def esta_homologado(self) -> bool:
        return self.homologado.strip().upper() == "S"

    @property
    def pendente(self) -> bool:
        """Ainda não há tese. Enquanto pender, a dúvida não é nossa."""
        return self.situacao in ("afetado", "a_conferir") or not self.tese.strip()

    @property
    def monitoravel(self) -> bool:
        return bool(self.numero_cnj.strip())

    @property
    def rotulo(self) -> str:
        """Como a pessoa vê. "STJ, Tema 1.302" e não "STJ-T1302"."""
        numero = self.tema
        if numero and len(numero) == 4 and numero.isdigit():
            numero = f"{numero[0]}.{numero[1:]}"
        return f"{self.tribunal}, Tema {numero}" if numero else self.id


@dataclass(frozen=True)
class AcaoColetiva:
    """Uma ação coletiva, e **quem ela cobre**.

    Não é só um número. Ela alcança UMA CATEGORIA, num PERÍODO — e é disso
    que sai a resposta para "em quais ações esta pessoa participa". Sem
    categoria e período declarados, a pergunta não tem como ser respondida, e
    por isso a autópsia recusa ação homologada sem eles: homologar seria
    afirmar que sabemos quem ela alcança.
    """

    id: str
    descricao: str = ""
    numero_cnj: str = ""
    numeracao_antiga: str = ""
    jurisdicao: str = ""
    autor: str = ""
    situacao: str = ""

    #: A categoria alcançada. Quem não é dela não participa, por mais tempo
    #: de filiação que tenha.
    categoria: str = ""
    #: O período coberto, em AAAA-MM. É contra ele que o período de filiação
    #: da pessoa é cruzado.
    periodo_inicio: str = ""
    periodo_fim: str = ""
    #: Há rol de substituídos? Muda tudo: com rol, quem está fora depende do
    #: STJ Tema 1.302, que está pendente com suspensão nacional. Sem rol, a
    #: coisa julgada alcança a categoria.
    exige_rol: bool = False
    juizo: str = ""

    fonte: str = ""
    observacoes: str = ""
    homologado: str = "N"

    @property
    def esta_homologado(self) -> bool:
        return self.homologado.strip().upper() == "S"

    @property
    def transitada(self) -> bool:
        return self.situacao == "transitado_em_julgado"

    @property
    def rotulo(self) -> str:
        return self.descricao or self.id


@dataclass(frozen=True)
class Catalogo:
    """O catálogo que o motor lê: as categorias de UMA entidade.

    Em disco é um arquivo por categoria. Em memória é este objeto, que pode
    carregar uma categoria (o caso de hoje) ou várias (o sindicato que
    representa mais de uma carreira). `categorias` é SEMPRE tupla, nunca
    string: era string, e a string era a hipótese de que existe um cliente só.

    `cargos` é a tabela de grafias, vinda dos arquivos. É ela que reconhece
    "AFRFB" e "Auditor Fiscal da Receita Federal" como a mesma carreira — e,
    tão importante, que permite RECONHECER uma carreira diferente, porque só
    aí dá para dizer "não participa" com segurança.
    """

    #: As categorias que esta entidade CONTRATOU. Só delas há ação e
    #: entendimento aqui dentro.
    categorias: tuple[str, ...]
    #: categoria canônica -> grafias que aparecem por aí, já normalizadas.
    #:
    #: MAIS LARGO QUE `categorias`, DE PROPÓSITO: traz toda carreira que o
    #: acervo conhece, inclusive as que esta entidade não contratou. Saber que
    #: "Analista Tributário" é outra carreira é conhecimento do mundo, não do
    #: contrato — e é o que permite responder "esta não é a sua carreira" em
    #: vez de "preciso conferir a sua carreira". Reconhecer dependeria de quem
    #: está perguntando, e isso não faz sentido.
    cargos: dict[str, tuple[str, ...]]
    #: categoria canônica -> slug (o nome do arquivo em disco).
    slugs: dict[str, str]
    #: slug -> versão do arquivo. Por arquivo, e não uma só para o conjunto:
    #: é com isso que um veredicto guardado diz de qual catálogo ele saiu.
    versoes: dict[str, int]
    entendimentos: tuple[Entendimento, ...]
    acoes: tuple[AcaoColetiva, ...]

    #: Derivado de `cargos`: grafia normalizada -> categoria. Montado no
    #: __post_init__ para não poder divergir, e porque a busca roda uma vez
    #: por ação por pessoa.
    _por_cargo: dict[str, str] = field(default_factory=dict, repr=False,
                                       compare=False)

    def __post_init__(self) -> None:
        tabela = {
            plano(grafia): categoria
            for categoria, grafias in self.cargos.items()
            for grafia in (*grafias, categoria)
            if plano(grafia)
        }
        object.__setattr__(self, "_por_cargo", tabela)

    # ------------------------------------------------------------- consultas

    def de(self, identificador: str):
        for e in self.entendimentos:
            if e.id == identificador:
                return e
        for a in self.acoes:
            if a.id == identificador:
                return a
        raise KeyError(identificador)

    def por_efeito(self, efeito: str) -> tuple[Entendimento, ...]:
        return tuple(e for e in self.entendimentos if e.efeito == efeito)

    def categoria_do_cargo(self, cargo: str) -> str | None:
        """A categoria canônica deste cargo, ou None se não for reconhecido.

        `None` NÃO significa "outra categoria": significa que não sabemos. A
        diferença é o que impede o sistema de recusar alguém por causa de uma
        grafia que a tabela ainda não conhece — e, do outro lado, o que
        impede de afirmar direito de carreira alheia.
        """
        return self._por_cargo.get(plano(cargo))

    def slug_de(self, categoria: str) -> str:
        return self.slugs.get(categoria, "")

    def versao_de(self, slug: str) -> int:
        return self.versoes.get(slug, 0)

    @property
    def assinatura(self) -> str:
        """Quais catálogos, em que versão, produziram um veredicto.

        Vai junto do veredicto guardado. Quando o Tema 1.302 for julgado, a
        reavaliação muda o resultado — e isto é o que prova por quê.
        """
        return " ".join(
            f"{slug}@{self.versoes[slug]}" for slug in sorted(self.versoes)
        )

    def restrito_a(self, categorias) -> "Catalogo":
        """Só as categorias contratadas — mas com a tabela de cargos inteira.

        Filtrar os cargos junto faria uma carreira vizinha deixar de ser
        reconhecida, e quem é dela sairia como "confirmar a carreira" em vez
        de "esta não é a sua carreira".
        """
        manter = set(categorias)
        slugs = {c: s for c, s in self.slugs.items() if c in manter}
        return replace(
            self,
            categorias=tuple(c for c in self.categorias if c in manter),
            slugs=slugs,
            versoes={s: v for s, v in self.versoes.items()
                     if s in set(slugs.values())},
            entendimentos=tuple(e for e in self.entendimentos
                                if e.categoria in manter),
            acoes=tuple(a for a in self.acoes if a.categoria in manter),
        )

    def homologando(self, ids: tuple[str, ...]) -> "Catalogo":
        """Uma cópia com estas entradas homologadas.

        Existe para TESTE. Homologar no arquivo é ato de advogado; homologar
        aqui deixa a suíte exercitar o motor sem que alguém precise assinar
        um catálogo de mentira.
        """
        alvo = set(ids)
        return replace(
            self,
            entendimentos=tuple(
                replace(e, homologado="S") if e.id in alvo else e
                for e in self.entendimentos
            ),
            acoes=tuple(
                replace(a, homologado="S") if a.id in alvo else a
                for a in self.acoes
            ),
        )


VAZIO = Catalogo(
    categorias=(), cargos={}, slugs={}, versoes={}, entendimentos=(), acoes=()
)


def plano(texto: str) -> str:
    """Minúsculo, sem acento, sem pontuação, espaços colapsados.

    A normalização que faz "Auditor-Fiscal" e "auditor fiscal" casarem. Mora
    aqui, e não em `participacao`, porque é o catálogo que guarda as grafias.
    """
    sem = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or ""))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^\w\s]", " ", sem).lower().split())


def _tupla(valor) -> tuple[str, ...]:
    if not valor:
        return ()
    if isinstance(valor, str):
        return (valor,)
    return tuple(str(v) for v in valor)


def _conferir(e: Entendimento) -> list[str]:
    """A autópsia. Uma entrada defeituosa não entra em silêncio."""
    erros: list[str] = []
    if not e.id.strip():
        erros.append("entendimento sem id")
    if e.trilha not in TRILHAS:
        erros.append(
            f"{e.id}: trilha {e.trilha!r} não existe "
            f"(use {' / '.join(TRILHAS)})"
        )
    if e.situacao not in SITUACOES:
        erros.append(f"{e.id}: situação {e.situacao!r} desconhecida")
    if e.efeito and e.efeito not in EFEITOS:
        erros.append(
            f"{e.id}: efeito {e.efeito!r} não é aplicado por nenhum motor — "
            f"uma regra que ninguém lê é pior que regra nenhuma"
        )
    if e.esta_homologado:
        # Homologar sem fonte é assinar sem ler.
        if not e.fonte.strip() or e.fonte.strip().startswith("PREENCHER"):
            erros.append(f"{e.id}: homologado sem fonte citada")
        if not e.tese.strip() or e.tese.strip().startswith("PREENCHER"):
            erros.append(f"{e.id}: homologado sem a tese transcrita")
    return erros


def _conferir_acao(a: AcaoColetiva) -> list[str]:
    """A autópsia da ação coletiva.

    Homologar sem período coberto seria afirmar que sabemos quem a ação
    alcança quando não sabemos — e é desse período que sai "em quais ações
    esta pessoa participa".
    """
    erros: list[str] = []
    if not a.id.strip():
        erros.append("ação coletiva sem id")
    if a.periodo_inicio and a.periodo_fim and a.periodo_inicio > a.periodo_fim:
        erros.append(
            f"{a.id}: período coberto invertido "
            f"({a.periodo_inicio} a {a.periodo_fim})"
        )
    if a.esta_homologado:
        if not (a.periodo_inicio.strip() and a.periodo_fim.strip()):
            erros.append(
                f"{a.id}: homologada sem o período coberto — sem ele não há "
                f"como dizer quem participa"
            )
        if not a.categoria.strip():
            erros.append(f"{a.id}: homologada sem a categoria alcançada")
        if not a.fonte.strip() or a.fonte.strip().startswith("PREENCHER"):
            erros.append(f"{a.id}: homologada sem fonte citada")
    return erros


def carregar(caminho: Path | str) -> Catalogo:
    """O catálogo de UMA categoria. O nome do arquivo é o slug."""
    caminho = Path(caminho)
    try:
        dados = tomllib.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErroDeCatalogo(f"catálogo não encontrado em {caminho}") from None
    except tomllib.TOMLDecodeError as e:
        raise ErroDeCatalogo(f"{caminho} não é TOML válido: {e}") from None

    cabeca = dados.get("catalogo") or {}
    slug = caminho.stem
    categoria = str(cabeca.get("categoria", "")).strip()
    erros: list[str] = []

    # Catálogo sem categoria é catálogo de ninguém — e, na prática, de todos:
    # qualquer cargo casaria, porque não haveria com o que não casar.
    if not categoria:
        erros.append(
            f"{caminho.name}: o catálogo não declara a categoria que ele "
            f"alcança, e sem ela não há a quem ele se aplique"
        )
    grafias = tuple(
        g for g in (plano(x) for x in _tupla(cabeca.get("cargos"))) if g
    )
    if categoria and not grafias:
        erros.append(
            f"{caminho.name}: nenhuma grafia de cargo declarada em `cargos`. "
            f"Sem elas ninguém desta carreira é reconhecido, e todo filiado "
            f"fica INDETERMINADO para sempre"
        )

    entradas: list[Entendimento] = []
    for bruto in dados.get("entendimentos") or []:
        dele = str(bruto.get("categoria", "")).strip() or categoria
        if dele != categoria:
            erros.append(
                f"{caminho.name}: o entendimento {bruto.get('id')!r} declara "
                f"a categoria {dele!r}, e o arquivo é de {categoria!r}"
            )
        entradas.append(Entendimento(
            id=str(bruto.get("id", "")),
            categoria=categoria,
            tribunal=str(bruto.get("tribunal", "")),
            tema=str(bruto.get("tema", "")),
            recursos=_tupla(bruto.get("recursos")),
            numero_cnj=str(bruto.get("numero_cnj", "")),
            relator=str(bruto.get("relator", "")),
            orgao=str(bruto.get("orgao", "")),
            situacao=str(bruto.get("situacao", "a_conferir")),
            julgado_em=str(bruto.get("julgado_em", "")),
            afetado_em=str(bruto.get("afetado_em", "")),
            suspensao_nacional=bool(bruto.get("suspensao_nacional", False)),
            questao=str(bruto.get("questao", "")),
            tese=str(bruto.get("tese", "")),
            trilha=str(bruto.get("trilha", AMBAS)),
            efeito=str(bruto.get("efeito", "")),
            criterios=_tupla(bruto.get("criterios")),
            fonte=str(bruto.get("fonte", "")),
            observacoes=str(bruto.get("observacoes", "")),
            homologado=str(bruto.get("homologado", "N")),
        ))

    acoes: list[AcaoColetiva] = []
    for bruto in dados.get("acoes_coletivas") or []:
        dela = str(bruto.get("categoria", "")).strip() or categoria
        if dela != categoria:
            # Contaminação cruzada escrita à mão. Ninguém perceberia: a ação
            # entraria no catálogo de uma carreira falando de outra.
            erros.append(
                f"{caminho.name}: a ação {bruto.get('id')!r} declara a "
                f"categoria {dela!r}, e o arquivo é de {categoria!r}"
            )
        acoes.append(AcaoColetiva(
            id=str(bruto.get("id", "")),
            descricao=str(bruto.get("descricao", "")),
            numero_cnj=str(bruto.get("numero_cnj", "")),
            numeracao_antiga=str(bruto.get("numeracao_antiga", "")),
            jurisdicao=str(bruto.get("jurisdicao", "")),
            autor=str(bruto.get("autor", "")),
            situacao=str(bruto.get("situacao", "")),
            categoria=categoria,
            periodo_inicio=str(bruto.get("periodo_inicio", "")),
            periodo_fim=str(bruto.get("periodo_fim", "")),
            exige_rol=bool(bruto.get("exige_rol", False)),
            juizo=str(bruto.get("juizo", "")),
            fonte=str(bruto.get("fonte", "")),
            observacoes=str(bruto.get("observacoes", "")),
            homologado=str(bruto.get("homologado", "N")),
        ))

    erros += [p for e in entradas for p in _conferir(e)]
    erros += [p for a in acoes for p in _conferir_acao(a)]
    vistos = [e.id for e in entradas] + [a.id for a in acoes]
    repetidos = sorted({i for i in vistos if vistos.count(i) > 1})
    if repetidos:
        erros.append(
            f"{caminho.name}: ids repetidos: {', '.join(repetidos)}"
        )
    if erros:
        raise ErroDeCatalogo("; ".join(erros))

    return Catalogo(
        categorias=(categoria,),
        cargos={categoria: grafias},
        slugs={categoria: slug},
        versoes={slug: int(cabeca.get("versao", 0))},
        entendimentos=tuple(entradas),
        acoes=tuple(acoes),
    )


def juntar(catalogos: list[Catalogo]) -> Catalogo:
    """Vários catálogos de categoria num só, com as travas do cruzamento.

    AS TRÊS COISAS QUE SÓ DÁ PARA CONFERIR AQUI, e as três são silenciosas se
    ninguém conferir:

    1. **id repetido entre arquivos.** Dois "GIFA-2006" diferentes e o motor
       pega um deles — qual, depende da ordem de leitura do diretório;
    2. **a mesma grafia de cargo em duas categorias.** O pior caso: a pessoa
       é posta na carreira errada, e nada reclama;
    3. **duas categorias com o mesmo nome.** Uma apagaria a outra ao juntar.
    """
    erros: list[str] = []
    categorias: list[str] = []
    cargos: dict[str, tuple[str, ...]] = {}
    slugs: dict[str, str] = {}
    versoes: dict[str, int] = {}
    entendimentos: list[Entendimento] = []
    acoes: list[AcaoColetiva] = []
    dono_do_cargo: dict[str, str] = {}

    for cat in catalogos:
        for categoria in cat.categorias:
            if categoria in cargos:
                erros.append(
                    f"a categoria {categoria!r} aparece em dois catálogos "
                    f"({slugs[categoria]} e {cat.slug_de(categoria)})"
                )
                continue
            categorias.append(categoria)
            cargos[categoria] = cat.cargos.get(categoria, ())
            slugs[categoria] = cat.slug_de(categoria)
            for grafia in (*cargos[categoria], plano(categoria)):
                anterior = dono_do_cargo.get(grafia)
                if anterior and anterior != categoria:
                    erros.append(
                        f"o cargo {grafia!r} é reivindicado por {anterior!r} "
                        f"e por {categoria!r} — uma das duas venceria por "
                        f"ordem de leitura do diretório, e a pessoa iria "
                        f"para a carreira errada"
                    )
                dono_do_cargo[grafia] = categoria
        versoes.update(cat.versoes)
        entendimentos += list(cat.entendimentos)
        acoes += list(cat.acoes)

    vistos = [e.id for e in entendimentos] + [a.id for a in acoes]
    repetidos = sorted({i for i in vistos if vistos.count(i) > 1})
    if repetidos:
        erros.append(
            f"id em mais de um catálogo de categoria: {', '.join(repetidos)}"
        )
    if erros:
        raise ErroDeCatalogo("; ".join(erros))

    return Catalogo(
        categorias=tuple(categorias),
        cargos=cargos,
        slugs=slugs,
        versoes=versoes,
        entendimentos=tuple(entendimentos),
        acoes=tuple(acoes),
    )


def carregar_categorias(
    pasta: Path | str, slugs: tuple[str, ...] | None = None
) -> Catalogo:
    """O catálogo de uma entidade: só as categorias que ela contratou.

    A PASTA INTEIRA É CONFERIDA, mesmo que a entidade tenha contratado uma
    categoria só. As travas do cruzamento — mesmo cargo em duas categorias,
    mesmo id em dois arquivos — são defeitos que põem pessoa na carreira
    errada, e um defeito desses não pode ficar esperando o contrato que o
    revele. Se o acervo está torto, ninguém é atendido.

    Da conferência sobra a tabela de cargos INTEIRA, e só as ações e os
    entendimentos das categorias contratadas.

    `slugs=None` serve a pasta inteira, e é para conferir o acervo. **Tupla
    vazia devolve catálogo VAZIO, nunca a pasta inteira**: ausência de
    declaração é "nenhuma categoria", e tratá-la como "todas" entregaria a um
    sindicato o catálogo do outro.
    """
    pasta = Path(pasta)
    if slugs is not None and not slugs:
        return VAZIO

    todos = juntar([carregar(a) for a in sorted(pasta.glob("*.toml"))])
    if slugs is None:
        return todos

    faltando = sorted(s for s in slugs if not (pasta / f"{s}.toml").is_file())
    if faltando:
        # Erro de digitação no cadastro deixaria o sindicato sem catálogo e
        # ninguém entenderia por quê. Falha alto.
        raise ErroDeCatalogo(
            "categoria declarada sem catálogo em disco: "
            + ", ".join(faltando)
            + f" (procurado em {pasta})"
        )
    pedidos = set(slugs)
    return todos.restrito_a(
        c for c, slug in todos.slugs.items() if slug in pedidos
    )
