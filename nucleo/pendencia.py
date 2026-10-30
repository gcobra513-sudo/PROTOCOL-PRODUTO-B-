"""
Quem destrava cada pendência.

A PARTE INFORMACIONAL DO PRODUTO MORA AQUI, e ela não é enfeite da tela: é o
que corta o telefonema. A lista de faltas era texto corrido, tudo no mesmo
saco:

    falta: homologação por advogado; os comprovantes de contribuição;
           o rol de substituídos; julgamento do STJ Tema 1.302

Quem lê isso liga para o sindicato. Não por não entender, mas porque não dá
para saber o que ELA tem de fazer. Separado por quem destrava, a mesma lista
responde sozinha — e a terceira linha é a que mais poupa ligação: "esperando
o STJ" é resposta completa, e nenhum telefonema a melhora.

POR QUE O DONO É DECLARADO NA ORIGEM, e não deduzido do texto depois. Deduzir
por palavra na frase ("se contém 'rol', então...") erra calado no dia em que
alguém reescrever a frase — e errar aqui é mandar uma pessoa providenciar o
que ela não tem como providenciar. Quem escreve a falta sabe de quem ela é, e
é lá que isso fica escrito.
"""
from __future__ import annotations

from dataclasses import dataclass

#: O filiado resolve: mandar um documento, responder uma pergunta sobre ele
#: mesmo. É a única categoria em que faz sentido pedir algo a ele.
VOCE = "VOCE"
#: O sindicato resolve: homologar, trazer o rol de substituídos, conferir a
#: base de execuções. Não é com o filiado, e dizer que é gera a ligação.
CONFERENCIA = "CONFERENCIA"
#: Ninguém resolve: depende de um tribunal julgar. Nem nós podemos nada.
TRIBUNAL = "TRIBUNAL"

#: A ordem de leitura: primeiro o que a pessoa pode fazer hoje, depois o que
#: está em andamento, por último o que só o tempo resolve.
DONOS = (VOCE, CONFERENCIA, TRIBUNAL)

#: O QUE A PESSOA LÊ. Quem fala com o filiado é o SINDICATO — nunca um
#: escritório. Se um escritório existe na relação, ele foi contratado pelo
#: sindicato, e isso é contrato, não coisa de tela.
TITULOS = {
    VOCE: "O que depende de você",
    CONFERENCIA: "O que o sindicato está conferindo",
    TRIBUNAL: "O que depende do tribunal",
}

EXPLICACOES = {
    VOCE: (
        "Você consegue resolver estes itens agora, e cada um melhora a "
        "resposta. Entre de novo e envie — não precisa refazer o cadastro."
    ),
    CONFERENCIA: (
        "Já está com o sindicato e não depende de você. Nada aqui é "
        "afirmado antes de um advogado conferir e assinar."
    ),
    TRIBUNAL: (
        "Depende de um tribunal julgar, e não há o que fazer senão "
        "aguardar. Avisamos quando sair, e ligar não antecipa."
    ),
}


@dataclass(frozen=True)
class Falta:
    """Uma coisa que falta, e de quem ela é.

    `o_que` é FRASE PARA SER LIDA, não código de erro: ela aparece em lista
    sob o título do dono, e "preencher campo obrigatório" não diz qual.
    """

    quem: str
    o_que: str

    def __post_init__(self) -> None:
        if self.quem not in DONOS:
            raise ValueError(
                f"falta sem dono conhecido: {self.quem!r} "
                f"(use {' / '.join(DONOS)})"
            )


def agrupar(faltas) -> dict[str, tuple[str, ...]]:
    """As faltas por dono, na ordem de leitura, sem repetir.

    DEVOLVE SEMPRE AS TRÊS CHAVES, inclusive vazias: grupo vazio é
    informação — significa "nada aqui" —, e deixar a chave de fora obrigaria
    cada tela a adivinhar a diferença entre "nada" e "não calculado".

    A primeira menção vence, porque a ordem em que o motor achou é a ordem em
    que ele avaliou, e reordenar trocaria uma prioridade que não é nossa.
    """
    grupos: dict[str, list[str]] = {dono: [] for dono in DONOS}
    for falta in faltas or ():
        if falta.quem not in grupos:
            # Fail-closed: um dono inventado iria para nenhum grupo e a
            # pendência desapareceria da tela sem ninguém notar.
            raise ValueError(f"dono desconhecido em {falta!r}: {falta.quem!r}")
        if falta.o_que not in grupos[falta.quem]:
            grupos[falta.quem].append(falta.o_que)
    return {dono: tuple(itens) for dono, itens in grupos.items()}
