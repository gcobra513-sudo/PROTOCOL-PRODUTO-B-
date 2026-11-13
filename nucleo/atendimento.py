"""
O atendimento ao filiado: as perguntas de sempre, respondidas na hora.

POR QUE EXISTE. O filiado liga para a sede: em que processo estou? mudou
alguma coisa? vocês receberam meus documentos? o que falta? São perguntas
cuja resposta JÁ ESTÁ nas telas do portal — e que continuam chegando por
telefone, porque perguntar é mais fácil que procurar.

O QUE ISTO NÃO É: um modelo de linguagem. "Dado de filiado não sai do
Brasil, nem para modelo de linguagem" é regra deste repositório, e mandar a
pergunta de um filiado — com a situação dele junto — para um serviço de IA
de fora seria exatamente isso. Aqui o assunto é reconhecido PELAS PALAVRAS,
numa lista fechada, e a resposta é montada com o que as rotas das telas
devolvem. Menos esperto do que parece, e por isso previsível: ele não
inventa, não deduz e não promete.

DUAS REGRAS QUE VALEM AQUI COMO NO RESTO:

- NÃO APURA NADA. Este módulo recebe o que `minhas-acoes`, `meus-processos`
  e `meu-cadastro` já responderam e só escreve em frases. Uma segunda
  apuração seria uma segunda resposta para a mesma pessoa.
- A DÚVIDA NUNCA VIRA PERMISSÃO. "Falta informação" é dito como falta, com
  o que falta. E valor não se calcula: diz que não calcula, e por quê.
"""
from __future__ import annotations

import unicodedata

PROCESSOS, NOVIDADES, DOCUMENTOS, FALTA, DIREITOS, VALOR, DADOS, AJUDA = (
    "processos", "novidades", "documentos", "falta", "direitos", "valor",
    "dados", "ajuda")
NAO_ENTENDI = "nao_entendi"

#: O que ele sabe responder, do jeito que o filiado pergunta. Vai para a
#: tela como sugestão — e é a lista inteira: não há assunto escondido.
SUGESTOES = (
    "Em quais processos eu estou?",
    "Mudou alguma coisa nos meus processos?",
    "Meus documentos chegaram?",
    "O que falta eu fazer?",
    "O que eu posso fazer hoje?",
    "Meus dados estão certos?",
)

#: Assunto -> pedaços de palavra que o denunciam, já sem acento. A ORDEM É A
#: PRIORIDADE: "quanto vou receber do processo" é pergunta de valor, não de
#: processo, e por isso `valor` vem antes.
_PISTAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (VALOR, ("quanto", "valor", "dinheiro", "calculo")),
    (NOVIDADES, ("mudou", "mudanca", "novidade", "andamento", "andou",
                 "moviment")),
    (DOCUMENTOS, ("document", "comprovante", "sentenca", "certidao",
                  "enviei", "receberam", "chegaram", "chegou", "anex")),
    (FALTA, ("falta", "pendenc", "pendent", "preciso fazer", "o que fazer",
             "devo fazer")),
    (DIREITOS, ("direito", "posso", "executar", "ajuizar", "cobrar",
                "receber", "entrar com")),
    (PROCESSOS, ("processo", "inscrit", "acao", "acoes", "faco parte",
                 "participo")),
    (DADOS, ("meus dados", "cadastro", "e-mail", "email", "telefone",
             "endereco", "atualizad")),
    (AJUDA, ("ajuda", "oi", "ola", "bom dia", "boa tarde", "boa noite",
             "o que voce faz", "como funciona", "obrigad")),
)

_DOCUMENTOS = {
    "contribuicao": "comprovante de contribuição",
    "sentenca": "sentença",
    "certidao_transito": "certidão de trânsito em julgado",
}

_VEREDICTOS = {
    "PODE": "já pode",
    "NAO_PODE": "não pode",
    "FALTA": "ainda não dá para dizer",
}


def _plano(texto: str) -> str:
    sem = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn").strip()


def entender(pergunta: str) -> str:
    """De que assunto é a pergunta — ou `NAO_ENTENDI`.

    Pergunta vazia é pedido de ajuda. Pergunta que não bate com nada NÃO é
    encaixada no assunto mais próximo: responder a pergunta errada com
    segurança é pior que dizer que não entendeu.
    """
    texto = _plano(pergunta)
    if not texto:
        return AJUDA
    palavras = set(texto.replace("?", " ").replace(",", " ").split())
    for assunto, pistas in _PISTAS:
        for pista in pistas:
            # Pista curta ("oi") só vale como palavra inteira: como pedaço,
            # ela mora dentro de "noite" e de "dois".
            if (pista in palavras) if len(pista) <= 3 else (pista in texto):
                return assunto
    return NAO_ENTENDI


def _numero(n: str) -> str:
    d = "".join(c for c in n if c.isdigit())
    if len(d) != 20:
        return n
    return f"{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}"


def _tipos(arquivos: list[str]) -> list[str]:
    vistos: list[str] = []
    for nome in arquivos:
        base = nome.rsplit(".", 1)[0]
        tipo = base.rstrip("0123456789").rstrip("-")
        rotulo = _DOCUMENTOS.get(tipo, tipo.replace("_", " "))
        if rotulo not in vistos:
            vistos.append(rotulo)
    return vistos


def responder(assunto: str, *, acoes: dict | None = None,
              processos: dict | None = None,
              cadastro: dict | None = None) -> list[str]:
    """As frases da resposta, um parágrafo por item.

    Recebe o que as rotas das telas devolveram — só o que o assunto pede —
    e NÃO consulta nada por conta própria.
    """
    acoes, processos, cadastro = acoes or {}, processos or {}, cadastro or {}

    if assunto == PROCESSOS:
        frases = []
        lista = processos.get("processos") or []
        if lista:
            frases.append(
                ("O processo ligado ao seu cadastro é " if len(lista) == 1
                 else "Os processos ligados ao seu cadastro são ")
                + "; ".join(_numero(p["numero"]) for p in lista) + ".")
        else:
            frases.append("Não há nenhum número de processo ligado ao seu "
                          "cadastro.")
        das_acoes = acoes.get("acoes") or []
        if das_acoes:
            frases.append("Ações coletivas consideradas para a sua carreira: "
                          + "; ".join(a["rotulo"] for a in das_acoes) + ".")
        if acoes.get("aviso"):
            frases.append(acoes["aviso"])
        return frases

    if assunto == NOVIDADES:
        lista = processos.get("processos") or []
        if not lista:
            return ["Não há processo ligado ao seu cadastro para acompanhar."]
        frases = []
        for p in lista:
            m = p.get("ultimo_movimento")
            if m:
                frases.append(f"{_numero(p['numero'])}: o último andamento "
                              f"registrado é “{m['nome']}”, de "
                              f"{str(m['data'])[:10]}.")
            else:
                frases.append(f"{_numero(p['numero'])}: ainda não há "
                              f"andamento registrado.")
        conferido = str(processos.get("conferido_em") or "")[:10]
        frases.append(f"A última conferência no tribunal foi em {conferido}."
                      if conferido else
                      "Ainda não conferimos o tribunal para estes processos.")
        if processos.get("limite"):
            frases.append(processos["limite"])
        return frases

    if assunto == DOCUMENTOS:
        tipos = _tipos(cadastro.get("documentos") or [])
        frases = ["Já recebemos de você: " + ", ".join(tipos) + "."
                  if tipos else
                  "Ainda não recebemos nenhum documento seu pelo portal."]
        seus = [i for g in acoes.get("pendencias") or [] if g["quem"] == "VOCE"
                for i in g["itens"]]
        frases.append("Ainda depende de você: " + "; ".join(seus) + "."
                      if seus else
                      "Não há documento seu pendente agora.")
        return frases

    if assunto == FALTA:
        grupos = [g for g in acoes.get("pendencias") or [] if g["itens"]]
        if not grupos:
            return [acoes.get("aviso") or "Não há pendência registrada no "
                    "seu cadastro agora."]
        return [f"{g['titulo']}: " + "; ".join(g["itens"]) + "."
                for g in grupos]

    if assunto == DIREITOS:
        ops = acoes.get("oportunidades") or []
        if not ops:
            return [acoes.get("aviso") or "Ainda não há ação avaliada para "
                    "o seu cadastro."]
        frases = []
        for o in ops:
            estado = _VEREDICTOS.get(o["veredicto"], "ainda não dá para dizer")
            frase = f"{o['rotulo']} — {estado}."
            if o["veredicto"] != "PODE" and o.get("motivos"):
                frase += " " + "; ".join(o["motivos"]) + "."
            frases.append(frase)
        frases.append("Isto não é parecer: nada é apresentado em juízo sem "
                      "um advogado conferir e assinar.")
        return frases

    if assunto == VALOR:
        return ["Não calculamos valor. Para chegar a um número faltam a sua "
                "ficha financeira, mês a mês, e o que a sentença fixou — e "
                "sem os dois qualquer valor seria um chute.",
                "O que dá para dizer hoje é de quais ações você faz parte e "
                "o que falta em cada uma."]

    if assunto == DADOS:
        if not cadastro.get("conhecido"):
            return [cadastro.get("aviso") or "Ainda não temos cadastro seu."]
        campos = cadastro.get("campos") or {}
        cheios = sum(1 for v in campos.values() if v)
        return [f"Temos {cheios} informação(ões) no seu cadastro. Para ver "
                "e corrigir, abra “Meu cadastro”: o que você corrigir fica "
                "marcado para o sindicato conferir.",
                "O e-mail do seu acesso é o que o sindicato tem em cadastro; "
                "para trocá-lo, fale com o sindicato."]

    if assunto == AJUDA:
        return ["Sou o Proto, o assistente automático do portal. Respondo com o que "
                "está no seu cadastro, na hora — não sou uma pessoa, e não "
                "dou parecer.",
                "Pode perguntar pelos seus processos, pelos seus documentos, "
                "pelo que falta, ou pelo que você pode fazer hoje."]

    return ["Não entendi a pergunta, e prefiro dizer isso a responder outra "
            "coisa.",
            "Sei responder sobre os seus processos, os seus documentos, o "
            "que falta e o que você pode fazer hoje. Para outros assuntos, "
            "fale com o sindicato."]
