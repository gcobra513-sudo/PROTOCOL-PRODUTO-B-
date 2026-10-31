"""
O aviso de movimentação — a promessa que o formulário fazia e ninguém cumpria.

O cadastro pergunta *"quero receber aviso por e-mail quando houver
movimentação nos meus processos"*, guarda a resposta, o painel até conta
quantos marcaram — e **nada nunca lia esse campo**. Opt-in coletado e
ignorado é pior que não ter: a pessoa marcou achando que seria avisada, e
continuou ligando para o sindicato. É justamente a ligação que o produto
promete cortar.

ESTE MÓDULO NÃO MANDA E-MAIL. Ele decide **o que seria mandado**, e devolve
isso como dado. Quem manda é `ferramentas/avisar_movimentacao.py`. A divisão
não é estética: a regra de quem recebe o quê é a parte perigosa, e ela tem de
ser exercitável sem servidor de e-mail, sem banco e sem rede.

AS QUATRO REGRAS QUE NÃO SE QUEBRAM:

**Só quem pediu.** Escrever para quem não marcou não é descuido: é mala
direta com dado sensível, sobre processo judicial de alguém.

**A PRIMEIRA COLETA NÃO AVISA.** No dia em que o sindicato entra, a coleta
traz o histórico inteiro de cada processo — a GIFA tem 600 movimentos — e
todo mundo receberia um e-mail com anos de andamento. Processo visto pela
primeira vez entra como conhecido, calado.

**Um e-mail por pessoa, não por movimento.** Três andamentos no mesmo dia são
três linhas numa mensagem.

**O destino é o e-mail do SINDICATO.** Mesmo motivo do código de acesso: se
fosse o digitado, bastaria alguém cadastrar o CPF de outra pessoa com o
próprio e-mail para passar a receber a movimentação do processo dela.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: O mesmo validador do resto do produto, copiado para não arrastar o
#: `servidor` para dentro do `nucleo` — o núcleo não depende da aplicação.
EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")

#: O ASSUNTO É GENÉRICO DE PROPÓSITO. Ele aparece na notificação do celular,
#: na tela de bloqueio e numa caixa de e-mail que outra pessoa pode estar
#: olhando. "Penhora de bens" ali é vazamento sem precisar abrir nada.
ASSUNTO = "Houve movimentação em um processo seu"

#: O limite, junto da informação e não no rodapé. A movimentação do DataJud
#: tem cerca de um dia de atraso e não substitui publicação — dizer o
#: contrário faria alguém perder prazo confiando na gente.
LIMITE = (
    "Este aviso NÃO é intimação e não substitui a publicação oficial: é a "
    "movimentação que o tribunal registrou, com cerca de um dia de atraso. "
    "Não use para contar prazo."
)


@dataclass(frozen=True)
class Movimento:
    numero: str
    grau: str
    data: str
    nome: str


@dataclass(frozen=True)
class Destinatario:
    cpf: str
    nome: str
    #: O e-mail que o SINDICATO tem em cadastro, nunca o digitado no portal.
    email_do_sindicato: str
    quer_aviso: bool
    processos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mensagem:
    cpf: str
    destino: str
    assunto: str
    corpo: str
    #: As chaves dos movimentos que esta mensagem cobre. Só se marcam como
    #: avisadas DEPOIS de a mensagem sair.
    chaves: tuple[str, ...] = ()


@dataclass
class Resultado:
    avisos: list[Mensagem] = field(default_factory=list)
    #: Tudo o que passa a ser conhecido nesta rodada — inclusive o que NÃO
    #: foi avisado, como o histórico da primeira coleta.
    novas_chaves: set[str] = field(default_factory=set)
    #: cpf -> chaves que esta pessoa NÃO será avisada porque são histórico de
    #: processo visto pela primeira vez.
    #:
    #: Sem gravar isto, a proteção da estreia dura UM DIA: o processo fica
    #: conhecido, o histórico continua não-avisado, e na rodada seguinte a
    #: pessoa recebe os 600 movimentos que a estreia tinha evitado.
    estreia: dict = field(default_factory=dict)
    #: Quem tinha novidade e ficou sem aviso, e por quê. Não é erro
    #: silencioso: é o sindicato que corrige a base.
    sem_destino: list[str] = field(default_factory=list)


def chave(m: Movimento) -> str:
    """O que identifica um movimento. Mesmo critério da coleta: número, grau,
    data e nome — o DataJud não dá identificador estável."""
    return f"{m.numero}|{m.grau}|{m.data}|{m.nome}"


def _corpo(nome: str, por_processo: dict, endereco: str) -> str:
    linhas = [
        f"Olá, {nome}." if nome else "Olá.",
        "",
        "Houve movimentação em processo que você acompanha:",
        "",
    ]
    for numero, movimentos in por_processo.items():
        linhas.append(f"Processo {numero}")
        for m in movimentos:
            linhas.append(f"  {m.data} — {m.nome}")
        linhas.append("")
    if endereco:
        linhas += [f"Para ver o restante, entre em {endereco}", ""]
    linhas += [LIMITE, "", "Não responda a esta mensagem."]
    return "\n".join(linhas) + "\n"


def preparar(
    pessoas,
    movimentos,
    ja_avisados: set[str],
    processos_conhecidos: set[str],
    endereco: str = "",
) -> Resultado:
    """O que seria enviado nesta rodada.

    `processos_conhecidos` são os processos que já foram coletados antes. Um
    processo que NÃO está aí é estreia: tudo dele entra como conhecido e
    ninguém é avisado. Sem essa distinção, o primeiro dia de cada sindicato
    manda a cada pessoa o histórico inteiro do processo dela.

    `endereco` é o link do portal. Vazio, o texto não inventa nenhum — link
    errado num e-mail sobre processo judicial é o melhor jeito de ensinar a
    pessoa a clicar em link falso.
    """
    r = Resultado()

    estreando: set[str] = set()
    por_processo: dict[str, list[Movimento]] = {}
    for m in movimentos or ():
        por_processo.setdefault(m.numero, []).append(m)

    # ESTREIA: memoriza, não avisa.
    novos_por_processo: dict[str, list[Movimento]] = {}
    for numero, lista in por_processo.items():
        for m in lista:
            r.novas_chaves.add(chave(m))
        if numero not in (processos_conhecidos or set()):
            estreando.add(numero)
            continue
        novidades = [m for m in lista if chave(m) not in (ja_avisados or set())]
        if novidades:
            # Do mais novo para o mais velho: quem abre o e-mail quer saber o
            # que aconteceu por último.
            novos_por_processo[numero] = sorted(
                novidades, key=lambda m: (m.data, m.nome), reverse=True
            )

    for p in pessoas or ():
        if not p.quer_aviso:
            continue
        # O histórico dos processos que estreiam, para esta pessoa, entra
        # como tratado — e com o motivo certo, que é "estreia", não
        # "enviado": mentir no log de um aviso que nunca saiu é o pior lugar
        # para mentir, porque é nele que alguém procura quando a pessoa diz
        # "não fui avisada".
        historico = {
            chave(m)
            for numero in estreando if numero in (p.processos or ())
            for m in por_processo[numero]
        }
        if historico:
            r.estreia[p.cpf] = historico
        dela = {
            numero: movs for numero, movs in novos_por_processo.items()
            if numero in (p.processos or ())
        }
        if not dela:
            continue
        destino = (p.email_do_sindicato or "").strip()
        if not EMAIL.match(destino):
            r.sem_destino.append(
                f"{p.cpf}: tinha novidade e o e-mail no cadastro do sindicato "
                f"não serve ({destino!r})"
            )
            continue
        r.avisos.append(Mensagem(
            cpf=p.cpf,
            destino=destino,
            assunto=ASSUNTO,
            corpo=_corpo(p.nome, dela, endereco),
            chaves=tuple(
                chave(m) for movs in dela.values() for m in movs
            ),
        ))

    return r
