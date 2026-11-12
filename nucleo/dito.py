"""
Uma frase, dois leitores.

O motor explica cada resposta, e a explicação tem dois destinos:

    o veredicto guardado   a PROVA. Lido por advogado e por gestor, fala da
                           pessoa em terceira: "esta pessoa consta do rol".
    a tela do filiado      lida pela própria pessoa. A mesma frase, ali, lê
                           como dossiê sobre outra — ela não sabe que é dela
                           que se fala.

Trocar "esta pessoa" por "você" no texto pronto não serve: "esta pessoa é
filiada" concorda com *pessoa*, e viraria "você é filiada" para um homem.
Por isso a frase é escrita DUAS VEZES, aqui na origem, por quem sabe o que
ela diz. E a do filiado nunca usa adjetivo que dependa de quem lê: "a sua
filiação vai de…", não "você é filiada desde…".

`Dito` continua sendo `str`, e o valor dele é a frase do SINDICATO. Tudo o
que já lia frase — o veredicto guardado, as comparações, o JSON — continua
lendo o que lia. O que muda é que não existe mais frase com um leitor só:
o motor recusa texto cru (`exigir`), e quem escreve uma frase nova é
obrigado a escrever a outra.
"""
from __future__ import annotations


class Dito(str):
    """A frase do sindicato, carregando a do filiado em `.voce`."""

    voce: str

    def __new__(cls, sindicato: str, voce: str) -> "Dito":
        if not str(sindicato).strip() or not str(voce).strip():
            raise ValueError("frase vazia: os dois leitores precisam da sua")
        frase = super().__new__(cls, sindicato)
        frase.voce = str(voce)
        return frase


def dito(sindicato: str, voce: str) -> Dito:
    """A mesma coisa, dita ao sindicato e dita ao próprio filiado."""
    return Dito(sindicato, voce)


def ambos(texto: str) -> Dito:
    """Uma frase que não fala de ninguém e serve aos dois leitores.

    Usar esta função é DECLARAR que a frase foi lida pensando no filiado —
    é diferente de esquecer de escrever a segunda.
    """
    return Dito(texto, texto)


def exigir(frase: object, onde: str) -> Dito:
    """A frase, se tem os dois leitores. `TypeError` se é texto cru.

    Falha fechada, e cedo: uma frase só em terceira pessoa não chega à tela
    do filiado calada — ela não passa do lugar onde nasceu.
    """
    if not isinstance(frase, Dito):
        raise TypeError(
            f"{onde}: frase com um leitor só ({str(frase)[:60]!r}). Escreva "
            f"com `dito(sindicato, voce)`, ou `ambos(texto)` se ela não fala "
            f"de ninguém"
        )
    return frase


def para_voce(frase: object) -> str:
    """O que o FILIADO lê."""
    return exigir(frase, "para_voce").voce


def nao_homologado(rotulo: str) -> Dito:
    """A MESMA frase em `motor` e em `participacao`, de propósito: as duas
    conferem a homologação — cinto e suspensório —, e com redações
    diferentes a pessoa lia a mesma pendência duas vezes."""
    return dito(
        f"{rotulo}: ainda não homologado — o motor prepara, quem assina "
        f"é gente",
        f"{rotulo}: um advogado ainda não conferiu e assinou esta parte. "
        f"O sistema prepara; quem assina é gente",
    )
