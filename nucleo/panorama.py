"""
O panorama: a resposta do filiado, somada, para quem dirige o sindicato.

A PERGUNTA DO GESTOR NÃO É A DO FILIADO. O filiado pergunta *"e eu?"*. O
diretor pergunta **"o que eu faço primeiro?"** — e a resposta útil não é uma
lista de 4.812 pessoas, é uma frase:

    Homologar a GIFA destrava 1.204 pessoas.

Uma decisão, mil pessoas. Nada no produto dizia isso. `completude` conta o
estado da BASE — quem não se alcança, que campo falta — e para aí, que é o
retrato certo da primeira semana e não ajuda a decidir na terceira.

POR ISSO OS GARGALOS SAEM ORDENADOS POR QUANTAS PESSOAS DESTRAVAM, e
separados por quem destrava. É a mesma divisão da tela do filiado
(`pendencia.py`), usada ao contrário: lá serve para a pessoa saber que não
precisa ligar; aqui, para o sindicato saber o que resolver primeiro — e o que
não adianta tentar, porque depende de um tribunal julgar.

**NÃO LÊ DOCUMENTO, e isso é declarado no resultado.** Rodar a leitura de PDF
da base inteira a cada carregamento de painel é consulta de minutos para
responder uma tela. O que decide participação — cargo e período de filiação —
está no cadastro. E para as pendências basta saber QUAIS ARQUIVOS chegaram,
que o diário já guarda: quem entregou a sentença está esperando leitura, não
providência. Ler o que ela diz é outra etapa, e é por pessoa.

Sem essa distinção, "falta a sentença" apareceria para toda a base, inclusive
para quem já mandou a dela — e um número falso dito a um diretor de sindicato
com a nossa assinatura é o pior defeito que este módulo pode ter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import cadastro as conta
from . import entendimentos as ent
from . import motor
from . import participacao as part
from . import pendencia

#: Quantos nomes acompanham cada gargalo. Contagem não serve para agir — o
#: gestor não liga para um número —, mas devolver a base inteira a cada
#: carregamento é outro problema, de tamanho e de exposição.
EXEMPLOS_PADRAO = 8


@dataclass(frozen=True)
class PorAcao:
    """Quantas pessoas cada ação coletiva alcança, nesta base."""

    acao: str
    rotulo: str
    participam: int = 0
    indeterminados: int = 0
    nao_participam: int = 0
    #: Meses de participação somados, SÓ de quem participa. É a base do
    #: cálculo do valor, quando ele existir — somar os meses de quem não
    #: participa inflaria a conta antes de ela existir.
    meses_somados: int = 0


@dataclass(frozen=True)
class Gargalo:
    """Uma pendência, e quantas pessoas ela segura."""

    quem: str
    o_que: str
    pessoas: int
    #: Alguns nomes, para o gestor poder agir. Limitado de propósito.
    exemplos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Panorama:
    #: TODA a base: a planilha do sindicato mais quem se cadastrou.
    pessoas: int = 0
    #: Destes, quantos já mandaram documento pelo portal.
    #:
    #: São dois números diferentes e o gestor precisa dos dois: quantos ele
    #: tem, e de quantos já temos o que falta para responder. Antes só existia
    #: o segundo — e um sindicato com 4.812 filiados e 200 cadastrados via um
    #: painel de 200.
    cadastrados: int = 0
    categorias: tuple[str, ...] = ()
    catalogo: str = ""
    por_acao: tuple[PorAcao, ...] = ()
    #: Do maior para o menor. A ordem É a informação.
    gargalos: tuple[Gargalo, ...] = ()
    #: Quantas pessoas têm ao menos uma oportunidade com veredicto PODE.
    #: Enquanto nada estiver homologado, isto é zero — corretamente.
    aptos: int = 0
    #: Declarado, não implícito: nenhum PDF foi lido para montar isto, e
    #: deixar o diretor supor que foi o faria confiar numa coluna que
    #: ninguém conferiu.
    leu_documentos: bool = False

    def manchete(self) -> str:
        # "CADASTRADA" NÃO SERVE MAIS. Desde que a planilha do sindicato
        # virou base, a maioria das pessoas aqui nunca entrou no portal — e
        # chamá-las de cadastradas sugere ao gestor que elas já mandaram
        # documento. Visto no vivo, com uma planilha de quatro e zero
        # cadastros.
        if not self.pessoas:
            return "Não há ninguém na base: nem planilha, nem cadastro."
        if not self.categorias:
            return (
                f"{self.pessoas} pessoa(s) na base, e nenhuma categoria "
                f"declarada para este sindicato — sem ela não há ação a "
                f"cruzar com os dados delas."
            )
        if not self.gargalos:
            return f"{self.pessoas} pessoa(s) na base, sem pendências."
        maior = self.gargalos[0]
        # DE QUEM É O GARGALO VAI NA FRASE. Sem isso, a manchete apontava o
        # maior da base — que pode ser pendência do próprio filiado — e o
        # painel logo abaixo apontava o maior que o SINDICATO resolve: duas
        # frases coladas uma na outra nomeando coisas diferentes como "a"
        # prioridade.
        return (
            f"{self.pessoas} pessoa(s) na base. O que segura mais "
            f"gente agora: {maior.o_que} — {maior.pessoas} pessoa(s), e "
            f"{pendencia.ROTULO_CURTO[maior.quem]}."
        )


#: `contribuicao-3.pdf` -> `contribuicao`. O tipo é o que decide a pendência;
#: o índice só distingue um comprovante do outro.
#:
#: `.pdf` É OPCIONAL de propósito: o diário guarda o nome do arquivo e o
#: banco guarda o TIPO, e as duas pontas chamam esta mesma função. Enquanto
#: ela exigia a extensão, o caminho do banco não reconhecia documento nenhum
#: — e o painel passava a cobrar a sentença de quem já a tinha entregue.
#: Achado pelo teste que compara o panorama das duas fontes.
_TIPO = re.compile(r"^([a-z_]+?)(?:-\d{1,2})?(?:\.pdf)?$")


def tipo_do_arquivo(nome: str) -> str:
    """`contribuicao-3.pdf` -> `contribuicao`; `sentenca` -> `sentenca`."""
    achado = _TIPO.match(str(nome).strip().lower())
    return achado.group(1) if achado else ""


def tipos_entregues(arquivos) -> tuple[str, ...]:
    """Os TIPOS de documento que chegaram, pelo nome ou pelo próprio tipo."""
    vistos: list[str] = []
    for nome in sorted(arquivos or ()):
        tipo = tipo_do_arquivo(nome)
        if tipo and tipo not in vistos:
            vistos.append(tipo)
    return tuple(vistos)


def ultimo_envio_por_cpf(registros) -> dict[str, dict]:
    """O último envio de cada CPF, com os arquivos daquele envio.

    Mesma regra de `completude` e de `deposito.reconstruir_manifesto`:
    reenvio é correção, não filiado novo. Contar envios diria ao diretor que
    ele tem mais gente do que tem.

    Registro ilegível é PULADO, não fatal: `ler_diario` devolve
    `{"_ilegivel": n}` para a linha truncada por queda no meio da escrita, e
    derrubar o painel inteiro por causa dela seria trocar um defeito pequeno
    por um grande.
    """
    por_cpf: dict[str, dict] = {}
    for registro in registros or ():
        if not isinstance(registro, dict):
            continue
        linha = registro.get("linha")
        if not isinstance(linha, dict):
            continue
        cpf = conta.so_digitos(linha.get("cpf") or "")
        if not cpf:
            continue
        por_cpf[cpf] = {
            "linha": linha,
            "entregues": tipos_entregues(registro.get("arquivos") or {}),
            # Quem veio do diário sempre se cadastrou; quem veio da base do
            # banco traz a marca. O padrão `True` preserva o sentido para o
            # caminho sem banco, em que só há cadastro.
            "cadastrou": bool(registro.get("fonte_cadastro", True)),
        }
    return por_cpf


def fatos_do_cadastro(linha: dict, entregues: tuple[str, ...]) -> motor.Fatos:
    """O que o cadastro basta para dizer. **`tem_titulo` fica `None`**: ele
    sai do conteúdo da sentença, e este módulo não abre documento."""
    return motor.Fatos(
        cpf=conta.so_digitos(linha.get("cpf") or ""),
        nome=str(linha.get("nome_completo") or ""),
        cargo=str(linha.get("cargo") or ""),
        situacao=str(linha.get("situacao") or ""),
        data_ingresso=str(linha.get("data_ingresso") or ""),
        data_aposentadoria=str(linha.get("data_aposentadoria") or ""),
        filiado_desde=str(linha.get("filiado_desde") or ""),
        filiado_ate=str(linha.get("filiado_ate") or ""),
        tem_titulo=None,
        ja_executou=conta.resposta_booleana(linha.get("ja_executou") or ""),
        tem_acao_propria=conta.resposta_booleana(
            linha.get("tem_acao_propria") or ""
        ),
        documentos_entregues=entregues,
    )


def montar(
    registros,
    catalogo: ent.Catalogo,
    exemplos: int = EXEMPLOS_PADRAO,
) -> Panorama:
    """O panorama desta entidade, a partir do diário e do catálogo dela.

    `registros` são os de `deposito.ler_diario`. `catalogo` traz SÓ as
    categorias que a entidade contratou — `entendimentos.VAZIO` quando ela
    não declarou nenhuma, e aí não há ação a cruzar, que é o certo.
    """
    pessoas = ultimo_envio_por_cpf(registros)

    contagem: dict[str, list[int]] = {a.id: [0, 0, 0] for a in catalogo.acoes}
    meses: dict[str, int] = {a.id: 0 for a in catalogo.acoes}
    rotulos: dict[str, str] = {a.id: a.rotulo for a in catalogo.acoes}
    # (dono, o_que) -> nomes de quem está preso nela. A chave é o par, e não
    # só o texto: a mesma frase com donos diferentes é pendência diferente.
    presos: dict[tuple[str, str], list[str]] = {}
    aptos = 0

    for cpf, envio in pessoas.items():
        linha = envio["linha"]
        fatos = fatos_do_cadastro(linha, envio["entregues"])
        quem = part.Filiado(
            cpf=fatos.cpf,
            cargo=fatos.cargo,
            situacao=fatos.situacao,
            filiado_desde=fatos.filiado_desde,
            filiado_ate=fatos.filiado_ate,
        )
        for p in part.participacoes(quem, catalogo):
            alvo = contagem[p.acao]
            if p.estado == part.PARTICIPA:
                alvo[0] += 1
                meses[p.acao] += p.meses
            elif p.estado == part.INDETERMINADO:
                alvo[1] += 1
            else:
                alvo[2] += 1

        oportunidades = motor.avaliar(fatos, catalogo)
        if any(o.veredicto == motor.PODE for o in oportunidades):
            aptos += 1
        # UMA PESSOA CONTA UMA VEZ POR PENDÊNCIA, por mais ações que a
        # tenham: "287 pessoas esperam o rol" é gente, não ocorrências.
        # AS DUAS LISTAS. `falta` é o que falta para saber SE pode;
        # `falta_para_valor` é o que falta para saber QUANTO. São perguntas
        # diferentes — e para o gestor as duas são acionáveis, porque uma só
        # informação (a data de ajuizamento da coletiva) pode destravar a
        # conta da base inteira.
        dela = {(f.quem, f.o_que) for o in oportunidades
                for f in (*o.falta, *o.falta_para_valor)}
        nome = fatos.nome or cpf
        for chave in dela:
            presos.setdefault(chave, []).append(nome)

    gargalos = [
        Gargalo(quem=dono, o_que=texto, pessoas=len(nomes),
                exemplos=tuple(sorted(nomes)[:max(exemplos, 0)]))
        for (dono, texto), nomes in presos.items()
    ]
    # Do maior para o menor; empate desfeito pelo dono e pelo texto, para a
    # mesma base dar sempre a mesma ordem — painel que troca de ordem a cada
    # carregamento parece instável mesmo quando os números estão certos.
    gargalos.sort(key=lambda g: (-g.pessoas, pendencia.DONOS.index(g.quem),
                                 g.o_que))

    return Panorama(
        pessoas=len(pessoas),
        cadastrados=sum(1 for e in pessoas.values() if e["cadastrou"]),
        categorias=catalogo.categorias,
        catalogo=catalogo.assinatura,
        por_acao=tuple(
            PorAcao(acao=i, rotulo=rotulos[i], participam=c[0],
                    indeterminados=c[1], nao_participam=c[2],
                    meses_somados=meses[i])
            for i, c in sorted(contagem.items())
        ),
        gargalos=tuple(gargalos),
        aptos=aptos,
        leu_documentos=False,
    )
