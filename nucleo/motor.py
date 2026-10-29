"""
O motor do veredicto: dada uma pessoa, o que ela pode fazer.

É A CAIXA 3 DO MAPA, e é o produto. Entra o que se sabe da pessoa; sai a
lista do que ela pode **executar** e do que ela pode **ajuizar**, com o
motivo de cada "não" e o que falta em cada "não sei".

A REGRA QUE ORGANIZA TUDO, e dela decorre o desenho inteiro:

    EXECUTAR EXIGE TÍTULO. AJUIZAR NÃO.

Título é sentença transitada em nome da pessoa, ou ação coletiva em que ela
é substituída. Sem título não há o que executar, por melhor que seja a tese
— e dizer "você pode executar" para quem tem só a tese cria expectativa de
dinheiro em gente aposentada. Esse erro não se conserta com atualização de
software, e por isso ele é a primeira coisa testada.

TRÊS VEREDICTOS, E A ASSIMETRIA É DELIBERADA:

    PODE      desce para o escritório preparar
    NAO_PODE  resposta: sabe-se que não cabe. Custa pouco se errado
    FALTA     lacuna: NÃO é "provavelmente pode". Custa caro se errado

`FALTA` nunca vira `PODE` por falta de informação. É a mesma assimetria de
`elegibilidade.py`, de onde este módulo herda a postura: a dúvida não
resolve a favor de litigar.

E a trava que vem de fora do código: entendimento com `homologado = "N"` não
produz permissão nenhuma. O motor prepara; quem assina é gente.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import entendimentos as ent

EXECUTAR = ent.EXECUTAR
AJUIZAR = ent.AJUIZAR

PODE = "PODE"
NAO_PODE = "NAO_PODE"
FALTA = "FALTA"


@dataclass(frozen=True)
class Fatos:
    """O que se sabe da pessoa.

    `None` é estado de primeira classe e significa **não se sabe** — não
    significa "não". A diferença é o que separa `FALTA` de `NAO_PODE`, e
    tratá-las igual faria o sistema afirmar coisas sobre quem não respondeu.
    """

    cpf: str = ""
    nome: str = ""
    cargo: str = ""
    situacao: str = ""
    data_ingresso: str = ""
    data_aposentadoria: str = ""

    #: Tem sentença transitada em nome dela, ou é substituída em coletiva?
    tem_titulo: bool | None = None
    #: Consta do rol de substituídos da ação coletiva?
    no_rol: bool | None = None
    #: Já executou este título antes, por nós ou por terceiro?
    ja_executou: bool | None = None
    #: Já tem ação própria sobre o mesmo objeto?
    tem_acao_propria: bool | None = None


@dataclass(frozen=True)
class Oportunidade:
    """Uma coisa que esta pessoa pode — ou não — fazer."""

    trilha: str
    referencia: str
    rotulo: str
    veredicto: str
    motivos: tuple[str, ...] = ()
    falta: tuple[str, ...] = ()
    fonte: str = ""
    #: Observações que não decidem nada mas o escritório precisa ler.
    notas: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.veredicto == PODE


@dataclass
class _Juizo:
    """Acumula motivos e decide pelo pior estado encontrado."""

    motivos: list[str] = field(default_factory=list)
    falta: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    impedido: bool = False

    def impede(self, motivo: str) -> None:
        self.impedido = True
        self.motivos.append(motivo)

    def falta_saber(self, o_que: str, motivo: str) -> None:
        self.falta.append(o_que)
        self.motivos.append(motivo)

    def nota(self, texto: str) -> None:
        self.notas.append(texto)

    @property
    def veredicto(self) -> str:
        # NAO_PODE vence FALTA: é resposta, não lacuna. Quem não pode por um
        # motivo conhecido não deve aparecer como "faltam documentos".
        if self.impedido:
            return NAO_PODE
        if self.falta:
            return FALTA
        return PODE


def _homologacao(item, juizo: _Juizo) -> None:
    if not item.esta_homologado:
        juizo.falta_saber(
            "homologação por advogado",
            f"{getattr(item, 'rotulo', item.id)}: ainda não homologado — o "
            f"motor prepara, quem assina é gente",
        )


def _avaliar_executar(
    fatos: Fatos, acao: ent.AcaoColetiva, catalogo: ent.Catalogo
) -> Oportunidade:
    """Pode executar esta ação coletiva?"""
    j = _Juizo()
    _homologacao(acao, j)

    # 1. O TÍTULO, e ele vem antes de tudo. Sem título não há execução, e
    #    nenhuma das perguntas seguintes muda isso.
    if fatos.tem_titulo is False:
        j.impede(
            "não há título a executar: execução cobra o que uma decisão já "
            "determinou, e sem sentença transitada não há o que cobrar"
        )
    elif fatos.tem_titulo is None:
        j.falta_saber(
            "saber se existe sentença transitada em nome desta pessoa",
            "não se sabe se há título. Sem essa resposta não dá para dizer "
            "que pode executar",
        )

    if not acao.transitada:
        j.falta_saber(
            f"trânsito em julgado de {acao.rotulo}",
            f"{acao.rotulo}: a ação coletiva não consta como transitada em "
            f"julgado",
        )

    # 2. O ROL, e aqui entra o entendimento que está VIVO.
    pendentes = [
        e for e in catalogo.por_efeito("legitimidade_fora_do_rol_indeterminada")
        if e.esta_homologado and e.pendente
    ]
    if fatos.no_rol is False:
        if pendentes:
            tema = pendentes[0]
            suspensao = (
                " Há suspensão nacional de processos sobre a matéria."
                if tema.suspensao_nacional else ""
            )
            j.falta_saber(
                f"julgamento do {tema.rotulo}",
                f"esta pessoa está FORA do rol de substituídos, e o "
                f"{tema.rotulo} — que decide exatamente se quem está fora do "
                f"rol pode executar — ainda não foi julgado.{suspensao} "
                f"Protocolar agora é apostar com o processo dela",
            )
        else:
            j.impede(
                "esta pessoa não consta do rol de substituídos da ação "
                "coletiva, e há decisões extinguindo execução por "
                "ilegitimidade nesse caso"
            )
    elif fatos.no_rol is None:
        j.falta_saber(
            "a lista de substituídos da ação coletiva",
            f"{acao.rotulo}: não se sabe se esta pessoa consta do rol",
        )

    # 3. EXECUÇÃO PRÉVIA. Executar duas vezes cria dois processos para a
    #    mesma dívida, e o erro só aparece semanas depois.
    if fatos.ja_executou is True:
        j.impede(
            "esta pessoa já executou este título — executar de novo criaria "
            "dois processos para a mesma dívida"
        )
    elif fatos.ja_executou is None:
        j.falta_saber(
            "a base de execuções já ajuizadas",
            "não é possível afirmar que não há execução em curso para este CPF",
        )

    # 4. LIQUIDAÇÃO. Não decide se pode; decide COMO se faz. Nota, não trava.
    for e in catalogo.por_efeito("dispensa_liquidacao_se_calculo_aritmetico"):
        if e.esta_homologado and not e.pendente:
            j.nota(
                f"{e.rotulo}: dispensa a liquidação prévia quando a pessoa "
                f"comprova documentalmente o enquadramento e o crédito sai "
                f"por cálculo aritmético simples"
            )

    return Oportunidade(
        trilha=EXECUTAR,
        referencia=acao.id,
        rotulo=f"Executar: {acao.rotulo}",
        veredicto=j.veredicto,
        motivos=tuple(j.motivos),
        falta=tuple(j.falta),
        fonte=acao.fonte,
        notas=tuple(j.notas),
    )


def _avaliar_ajuizar(fatos: Fatos, e: ent.Entendimento) -> Oportunidade:
    """Pode entrar com ação nova, com base neste entendimento?"""
    j = _Juizo()
    _homologacao(e, j)

    if e.pendente:
        j.falta_saber(
            f"julgamento do {e.rotulo}",
            f"{e.rotulo} ainda não tem tese fixada — não há entendimento "
            f"firmado em que apoiar a ação",
        )

    # Quem já tem ação própria sobre o mesmo objeto não entra de novo.
    if fatos.tem_acao_propria is True:
        j.impede(
            "esta pessoa já tem ação própria sobre o mesmo objeto; ajuizar "
            "de novo é litispendência"
        )
    elif fatos.tem_acao_propria is None:
        j.falta_saber(
            "saber se esta pessoa já tem ação própria sobre o mesmo objeto",
            "não se sabe se já existe ação própria",
        )

    # Os critérios objetivos do entendimento. Enquanto o catálogo não os
    # traz, não há como afirmar enquadramento — e não afirmar é o certo.
    if not e.criterios:
        j.falta_saber(
            f"critérios objetivos de enquadramento no {e.rotulo}",
            f"{e.rotulo}: o catálogo não traz critério algum, então não há "
            f"como dizer que esta pessoa se enquadra",
        )
    else:
        j.nota(
            f"{e.rotulo}: enquadramento a conferir contra "
            + "; ".join(e.criterios)
        )

    return Oportunidade(
        trilha=AJUIZAR,
        referencia=e.id,
        rotulo=f"Ajuizar: {e.rotulo}",
        veredicto=j.veredicto,
        motivos=tuple(j.motivos),
        falta=tuple(j.falta),
        fonte=e.fonte,
        notas=tuple(j.notas),
    )


def avaliar(fatos: Fatos, catalogo: ent.Catalogo) -> list[Oportunidade]:
    """Tudo o que esta pessoa pode — ou não — fazer, nas duas trilhas.

    Devolve SEMPRE a lista inteira, inclusive os "não pode": o escritório
    precisa saber por que alguém ficou de fora tanto quanto precisa saber
    quem entrou. Lista só com os "pode" esconde o trabalho de corrigir
    cadastro, que é metade do produto.

    A ordem é a da leitura: primeiro quem pode, depois quem falta algo,
    depois quem não pode.
    """
    achadas: list[Oportunidade] = []

    for acao in catalogo.acoes:
        achadas.append(_avaliar_executar(fatos, acao, catalogo))

    for e in catalogo.entendimentos:
        if e.trilha in (AJUIZAR, ent.AMBAS):
            achadas.append(_avaliar_ajuizar(fatos, e))

    ordem = {PODE: 0, FALTA: 1, NAO_PODE: 2}
    return sorted(achadas, key=lambda o: (ordem[o.veredicto], o.referencia))
