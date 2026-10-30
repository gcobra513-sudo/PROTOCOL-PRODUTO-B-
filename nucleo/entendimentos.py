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
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
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


class ErroDeCatalogo(ValueError):
    """Defeito no catálogo. Nominal, para virar motivo legível."""


@dataclass(frozen=True)
class Entendimento:
    id: str
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
    versao: int
    categoria: str
    entendimentos: tuple[Entendimento, ...]
    acoes: tuple[AcaoColetiva, ...]

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
    caminho = Path(caminho)
    try:
        dados = tomllib.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErroDeCatalogo(f"catálogo não encontrado em {caminho}") from None
    except tomllib.TOMLDecodeError as e:
        raise ErroDeCatalogo(f"{caminho} não é TOML válido: {e}") from None

    cabeca = dados.get("catalogo") or {}
    entradas: list[Entendimento] = []
    for bruto in dados.get("entendimentos") or []:
        entradas.append(Entendimento(
            id=str(bruto.get("id", "")),
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
        acoes.append(AcaoColetiva(
            id=str(bruto.get("id", "")),
            descricao=str(bruto.get("descricao", "")),
            numero_cnj=str(bruto.get("numero_cnj", "")),
            numeracao_antiga=str(bruto.get("numeracao_antiga", "")),
            jurisdicao=str(bruto.get("jurisdicao", "")),
            autor=str(bruto.get("autor", "")),
            situacao=str(bruto.get("situacao", "")),
            categoria=str(bruto.get("categoria", "")),
            periodo_inicio=str(bruto.get("periodo_inicio", "")),
            periodo_fim=str(bruto.get("periodo_fim", "")),
            exige_rol=bool(bruto.get("exige_rol", False)),
            juizo=str(bruto.get("juizo", "")),
            fonte=str(bruto.get("fonte", "")),
            observacoes=str(bruto.get("observacoes", "")),
            homologado=str(bruto.get("homologado", "N")),
        ))

    erros = [p for e in entradas for p in _conferir(e)]
    erros += [p for a in acoes for p in _conferir_acao(a)]
    vistos = [e.id for e in entradas] + [a.id for a in acoes]
    repetidos = sorted({i for i in vistos if vistos.count(i) > 1})
    if repetidos:
        erros.append(f"ids repetidos no catálogo: {', '.join(repetidos)}")
    if erros:
        raise ErroDeCatalogo("; ".join(erros))

    return Catalogo(
        versao=int(cabeca.get("versao", 0)),
        categoria=str(cabeca.get("categoria", "")),
        entendimentos=tuple(entradas),
        acoes=tuple(acoes),
    )
