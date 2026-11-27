"""
O Proto, para quem trabalha no escritório contratado.

É o mesmo assistente do filiado e da diretoria, com o terceiro leitor. As
regras são as mesmas dos outros dois (`nucleo/atendimento.py`):

- **Lista fechada de assuntos.** Sem modelo de linguagem: a pergunta é
  reconhecida por pedaço de palavra, e o que não é da lista cai em "não
  entendi", com a lista do que ele sabe.
- **Só responde com o que a tela já mostra.** Recebe os casos que a rota do
  escritório devolveu — os DELE — e não consulta nada por conta própria. Não
  há uma segunda apuração para dar outro número.
- **A pergunta não é guardada.** Só o assunto reconhecido vai para o log.

MORA NO SERVIDOR, e não no núcleo, de propósito: o núcleo não sabe de
escritório (`tests/testes_repositorio.py`).
"""
from __future__ import annotations

import unicodedata

from . import escritorios

(FILA, PRIMEIRO, FALTA, COMPLETOS, PESSOA, NOVIDADES, AJUDA) = (
    "fila", "primeiro", "falta", "completos", "pessoa", "novidades", "ajuda")
NAO_ENTENDI = "nao_entendi"

SUGESTOES = (
    "Teve novidade nos tribunais?",
    "Quantos casos eu tenho?",
    "O que eu abro primeiro?",
    "De quem falta documento?",
    "Quem está com a documentação completa?",
    "Como está o caso de (nome)?",
)

#: A ORDEM É A PRIORIDADE, do mais específico para o mais geral.
_PISTAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (NOVIDADES, ("novidade", "tribunal", "tribunais", "tese", "tema",
                 "julg", "entendimento", "stj", "stf")),
    (PESSOA, ("como esta", "caso de ", "caso da ", "caso do ", "situacao de",
              "situacao da", "situacao do")),
    (PRIMEIRO, ("primeiro", "comeco", "comecar", "prioridade", "urgente",
                "mais antigo", "aguardando", "nao abri", "abrir")),
    (FALTA, ("falta", "pendente", "pendencia", "faltando")),
    (COMPLETOS, ("complet", "pront", "tudo certo")),
    (FILA, ("quantos", "quantas", "fila", "casos", "resumo", "total")),
    (AJUDA, ("ajuda", "oi", "ola", "bom dia", "boa tarde", "boa noite",
             "o que voce faz", "como funciona", "obrigad")),
)

_ROTULOS = {
    escritorios.ENCAMINHADO: "aguardando o escritório confirmar o recebimento",
    escritorios.RECEBIDO: "recebido, em conferência",
    escritorios.PENDENTE: "com documento faltando",
    escritorios.COMPLETO: "com a documentação completa",
}

#: Palavras da pergunta que não são nome de ninguém.
_VAZIAS = {"como", "esta", "estao", "caso", "casos", "de", "da", "do", "a",
           "o", "os", "as", "situacao", "qual", "que", "e", "exemplo",
           "ficticio", "ficticia"}


def _plano(texto: str) -> str:
    sem = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn")


def entender(pergunta: str) -> str:
    plano = _plano(pergunta).strip()
    if not plano:
        return AJUDA
    for assunto, pistas in _PISTAS:
        if any(p in plano for p in pistas):
            return assunto
    return NAO_ENTENDI


def _n(q: int, um: str, muitos: str) -> str:
    return f"{q} {um if q == 1 else muitos}"


def _dia(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso or "") >= 10 else ""


def _faltas(caso: dict) -> str:
    return ", ".join(escritorios.ROTULOS.get(f, f)
                     for f in caso.get("faltam") or ())


def responder(assunto: str, casos: list[dict],
              pergunta: str = "", novidades: list[dict] | None = None
              ) -> list[str]:
    """As frases da resposta. `casos` é o que a rota do escritório entrega:
    só os dele, e por isso aqui os nomes podem aparecer."""
    por = lambda s: [c for c in casos if c.get("situacao") == s]  # noqa: E731

    if assunto == NOVIDADES:
        # AS FRASES VÊM PRONTAS de `servidor/vigia.py` — as mesmas do painel
        # e do e-mail da manhã. Aqui só se repete o que a tela já diz.
        if not novidades:
            return ["Não há novidade nos tribunais nos últimos trinta dias "
                    "para as carreiras dos seus sindicatos. A lista das "
                    "teses acompanhadas está no fim do painel."]
        return [n["frase"] for n in novidades[:5]] + [
            "Os números são uma simulação: quantas pessoas teriam o caminho "
            "aberto se a tese for conferida por advogado."]

    if assunto == FILA:
        if not casos:
            return ["O sindicato ainda não encaminhou nenhum caso a este "
                    "escritório."]
        return [
            f"Você tem {_n(len(casos), 'caso', 'casos')} encaminhados pelo "
            f"sindicato: {len(por(escritorios.ENCAMINHADO))} aguardando a "
            f"sua confirmação, {len(por(escritorios.RECEBIDO))} em "
            f"conferência, {len(por(escritorios.PENDENTE))} com documento "
            f"faltando e {len(por(escritorios.COMPLETO))} com a "
            f"documentação completa.",
        ]

    if assunto == PRIMEIRO:
        fila = sorted(por(escritorios.ENCAMINHADO),
                      key=lambda c: c.get("encaminhado_em") or "")
        if not fila:
            return ["Não há caso esperando a sua confirmação: você já abriu "
                    "todos os que o sindicato encaminhou."]
        frases = [f"{_n(len(fila), 'caso espera', 'casos esperam')} a sua "
                  f"confirmação de recebimento. Do mais antigo para o mais "
                  f"novo:"]
        frases += [f"{c['nome']} — encaminhado em "
                   f"{_dia(c.get('encaminhado_em') or '')}." for c in fila[:5]]
        if len(fila) > 5:
            frases.append(f"E mais {len(fila) - 5}, na lista abaixo.")
        return frases

    if assunto == FALTA:
        pendentes = por(escritorios.PENDENTE)
        if not pendentes:
            return ["Você não marcou documento faltando em nenhum caso."]
        return [f"Falta documento em {_n(len(pendentes), 'caso', 'casos')}. "
                f"A pessoa vê o pedido na área dela:"] + [
            f"{c['nome']} — {_faltas(c)}." for c in pendentes[:8]]

    if assunto == COMPLETOS:
        prontos = por(escritorios.COMPLETO)
        if not prontos:
            return ["Nenhum caso está com a documentação completa ainda."]
        return [f"{_n(len(prontos), 'caso está', 'casos estão')} com a "
                f"documentação completa:"] + [
            f"{c['nome']} — {c.get('rotulo') or ''}." for c in prontos[:8]]

    if assunto == PESSOA:
        procurados = [p for p in _plano(pergunta).replace("?", " ").split()
                      if p not in _VAZIAS and len(p) > 2]
        achados = [c for c in casos
                   if procurados and all(p in _plano(c.get("nome") or "")
                                         for p in procurados)]
        if not achados:
            return ["Não encontrei esse nome entre os casos que o sindicato "
                    "encaminhou a este escritório. Eu só enxergo os seus."]
        frases = []
        for c in achados[:5]:
            frase = (f"{c['nome']}: {_ROTULOS.get(c.get('situacao'), '')}"
                     f" — {c.get('rotulo') or ''}, encaminhado em "
                     f"{_dia(c.get('encaminhado_em') or '')}.")
            if c.get("situacao") == escritorios.PENDENTE:
                frase += f" Falta: {_faltas(c)}."
            frases.append(frase[0].upper() + frase[1:])
        return frases

    apresentacao = ("Sou o Proto, o assistente automático do portal. Aqui eu "
                    "respondo sobre os casos que o sindicato encaminhou a "
                    "este escritório.")
    if assunto == AJUDA:
        return [apresentacao, "Posso dizer se teve novidade nos tribunais, "
                "quantos casos há, por onde começar, de quem falta "
                "documento e como está o caso de uma pessoa — é só dizer "
                "o nome."]
    return ["Essa eu não sei responder. " + apresentacao,
            "Escolha uma das perguntas abaixo, ou escreva o nome de uma "
            "pessoa."]


# ------------------------------------------- a pergunta do FILIADO sobre isto

#: A pergunta que o filiado fazia por telefone, e a sugestão que a oferece.
PERGUNTA_DO_FILIADO = "Com quem está o meu caso?"

_DO_FILIADO = ("com quem", "encaminh", "escritorio", "advogad", "quem cuida",
               "quem esta cuidando", "meu caso")


def e_sobre_o_encaminhamento(pergunta: str) -> bool:
    """A pergunta do filiado é sobre com quem o caso dele está?

    É RESPONDIDA AQUI, antes de chegar ao Proto do núcleo, porque o núcleo
    não sabe de escritório — e não deve passar a saber por causa de uma
    frase."""
    plano = _plano(pergunta)
    return any(p in plano for p in _DO_FILIADO)


def responder_ao_filiado(encaminhamentos: list[dict]) -> list[str]:
    """Com quem está cada caso DELE, em que pé, e o que ele faz. Recebe o
    que a tela "Minhas ações" já mostra."""
    if not encaminhamentos:
        return ["O seu sindicato ainda não encaminhou nenhum caso seu a um "
                "escritório. Quando encaminhar, aparece aqui e na sua área."]
    frases = []
    for e in encaminhamentos:
        situacao = e.get("situacao")
        frase = f"{e.get('rotulo')}: o seu caso está com {e.get('escritorio')}."
        if situacao == escritorios.ENCAMINHADO:
            frase += (" O sindicato já encaminhou, e o escritório ainda não "
                      "confirmou o recebimento. Você não precisa fazer nada "
                      "agora.")
        elif situacao == escritorios.RECEBIDO:
            frase += (" Ele recebeu e está conferindo os documentos. Você "
                      "não precisa fazer nada agora.")
        elif situacao == escritorios.PENDENTE:
            frase += (f" Ele precisa de: {', '.join(e.get('faltam') or ())}. "
                      f"Envie pelo seu cadastro, aqui no portal.")
        elif situacao == escritorios.COMPLETO:
            frase += (" A documentação está completa: não falta nada da sua "
                      "parte.")
        if e.get("contato"):
            frase += f" Contato do escritório: {e['contato']}."
        frases.append(frase)
    return frases
