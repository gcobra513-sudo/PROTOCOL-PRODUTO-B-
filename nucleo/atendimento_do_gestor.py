"""
O Proto do gestor: as perguntas da diretoria, respondidas na hora.

POR QUE EXISTE. O Proto nasceu para o filiado parar de ligar para a sede.
Quem atende esse telefone, e quem responde à diretoria "quantos somos? com
quantos consigo falar? o que eu resolvo primeiro?", é o gestor — e as
respostas JÁ ESTÃO no painel dele. Perguntar é mais fácil que procurar.

AS MESMAS TRÊS REGRAS DO PROTO DO FILIADO (`nucleo/atendimento.py`):

- NÃO É MODELO DE LINGUAGEM. O assunto é reconhecido pelas palavras, numa
  lista fechada. O que não reconhece, diz que não entendeu.
- NÃO APURA NADA. Recebe o que as rotas do painel (`completude` e
  `panorama`) já responderam e escreve em frases. Uma segunda apuração
  seria um segundo número para a mesma base.
- A DÚVIDA NUNCA VIRA RESPOSTA. Sem como saber, diz que não sabe — nunca um
  zero. E valor não se calcula.

E UMA QUE É SÓ DAQUI: A CONVERSA CONTA, NÃO NOMEIA. O gestor pode ver os
nomes — eles estão na aba Filiados, e a planilha baixada fica registrada.
Mas uma conversa é texto solto numa tela, que se lê em voz alta e se copia
para um grupo. Aqui sai quantos são e EM QUE ABA está a lista.
"""
from __future__ import annotations

from .atendimento import _plano
from .pendencia import CONFERENCIA, ROTULO_CURTO, TRIBUNAL

(BASE, CONTATO, PORTAL, LEITURA, PRIMEIRO, PENDENCIAS, PODEM, ENVIOS, VALOR,
 AJUDA) = ("base", "contato", "portal", "leitura", "primeiro", "pendencias",
           "podem", "envios", "valor", "ajuda")
NAO_ENTENDI = "nao_entendi"
ASSUNTOS = (BASE, CONTATO, PORTAL, LEITURA, PRIMEIRO, PENDENCIAS, PODEM,
            ENVIOS, VALOR, AJUDA, NAO_ENTENDI)

#: O que ele sabe responder, do jeito que a diretoria pergunta. É a lista
#: inteira: não há assunto escondido.
SUGESTOES = (
    "Quantos filiados estão na base?",
    "Com quantos eu não consigo falar?",
    "Quantos já entraram no portal?",
    "Quantos documentos esperam leitura?",
    "O que resolver primeiro?",
    "Quantos já podem fazer alguma coisa?",
    "Como envio a planilha?",
)

#: Assunto -> pedaços de palavra, já sem acento. A ORDEM É A PRIORIDADE, do
#: mais específico para o mais geral: "quantos filiados entraram no portal"
#: é pergunta do portal, não da base, e por isso `base` é a última.
_PISTAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (VALOR, ("quanto vale", "valor", "dinheiro", "calculo", "vai receber",
             "vamos receber")),
    (ENVIOS, ("envio", "enviar", "mando", "mandar", "subir", "planilha",
              "rol de", "apagamento", "apagar")),
    (LEITURA, ("leitura", "para ler", "pra ler", "eu ler", "esperam",
               "esperando", "fila")),
    (CONTATO, ("contato", "falar", "alcanc", "ligar", "sem e-mail",
               "sem email", "sem telefone")),
    (PORTAL, ("portal", "entraram", "entrou", "cadastraram", "cadastrou",
              "cadastrad")),
    (PRIMEIRO, ("primeiro", "prioridade", "por onde", "comeco", "comecar",
                "resolver")),
    (PODEM, ("podem", "pronta", "pronto", "cobrar", "executar", "ajuizar",
             "aptos")),
    (PENDENCIAS, ("pendenc", "pendent", "depende", "trava", "gargalo",
                  "tribunal", "falta")),
    (BASE, ("quantos filiados", "quantas pessoas", "base", "acervo",
            "total", "quantos somos", "quantos sao")),
    (AJUDA, ("ajuda", "oi", "ola", "bom dia", "boa tarde", "boa noite",
             "o que voce faz", "como funciona", "obrigad")),
)


def entender(pergunta: str) -> str:
    """De que assunto é a pergunta — ou `NAO_ENTENDI`. Vazia é ajuda."""
    texto = _plano(pergunta)
    if not texto:
        return AJUDA
    palavras = set(texto.replace("?", " ").replace(",", " ").split())
    for assunto, pistas in _PISTAS:
        for pista in pistas:
            if (pista in palavras) if len(pista) <= 3 else (pista in texto):
                return assunto
    return NAO_ENTENDI


def _n(n: int, um: str, muitos: str) -> str:
    return f"1 {um}" if n == 1 else f"{n} {muitos}"


def _linha_do_gargalo(g: dict) -> str:
    return (f"{g['o_que']}: {_n(g['pessoas'], 'pessoa', 'pessoas')}, e "
            f"{ROTULO_CURTO.get(g['quem'], g['quem'])}.")


def responder(assunto: str, *, completude: dict | None = None,
              panorama: dict | None = None) -> list[str]:
    """As frases da resposta, um parágrafo por item.

    Recebe o que as rotas do painel devolveram — só o que o assunto pede —
    e NÃO consulta nada por conta própria.
    """
    completude, panorama = completude or {}, panorama or {}
    r = completude.get("retrato") or {}
    gargalos = panorama.get("gargalos") or []

    if assunto == BASE:
        frases = [completude.get("manchete") or
                  "Não consegui ler o retrato da base agora."]
        faltas = list((r.get("falta_por_campo") or {}).items())[:3]
        if faltas:
            frases.append("O que mais falta na planilha: " + "; ".join(
                f"{campo} ({quantos})" for campo, quantos in faltas) + ".")
        frases.append("A lista inteira, nome por nome, está na aba Filiados.")
        return frases

    if assunto == CONTATO:
        if "inalcancaveis" not in r:
            return ["Não consegui ler o retrato da base agora."]
        fora, total = r["inalcancaveis"], r.get("total", 0)
        if not total:
            return ["Você ainda não enviou a base de filiados; sem ela não "
                    "há como dizer com quem dá para falar. O envio fica na "
                    "aba Envios e pedidos."]
        if not fora:
            return [f"Dá para falar com todos os {total} da sua base: cada "
                    "um tem um e-mail que serve."]
        return [f"De {_n(total, 'filiado', 'filiados')} na sua base, você "
                f"não alcança {fora}: falta um e-mail que sirva.",
                "Quem são, e o motivo de cada um, está na aba Filiados, em "
                "“Quem você não alcança”. A planilha da base traz os "
                "telefones que constam."]

    if assunto == PORTAL:
        if "cadastrados" not in r:
            return ["Não consegui ler o retrato da base agora."]
        return [f"{_n(r['cadastrados'], 'filiado da sua base já entrou', 'filiados da sua base já entraram')} "
                f"no portal e {_n(r.get('sem_cadastro', 0), 'ainda não entrou', 'ainda não entraram')}.",
                "Na aba Filiados dá para ver só quem entrou ou só quem "
                "falta."]

    if assunto == LEITURA:
        fila = panorama.get("aguardando_leitura")
        if not fila or fila.get("sem_banco"):
            # Zero afirmaria que não há nada esperando.
            return ["Não consigo contar a fila de leitura agora. Confira na "
                    "aba Documentos para ler."]
        if not fila["documentos"] and not fila.get("ilegiveis"):
            return ["Não há documento esperando leitura agora."]
        frases = []
        if fila["documentos"]:
            frases.append(
                f"{_n(fila['documentos'], 'documento espera', 'documentos esperam')} "
                f"a sua leitura, de {_n(fila['pessoas'], 'pessoa', 'pessoas')}. "
                "São fotos ou cópias que a máquina não conseguiu ler.")
        if fila.get("ilegiveis"):
            frases.append(
                f"{_n(fila['ilegiveis'], 'documento não deu', 'documentos não deram')} "
                "para ler nem por pessoa: é preciso pedir de novo ao filiado.")
        frases.append("Eles estão na aba Documentos para ler.")
        return frases

    if assunto == PRIMEIRO:
        if "gargalos" not in panorama:
            return ["Não consegui apurar as pendências da base agora."]
        # O MAIOR QUE O SINDICATO DESTRAVA — a mesma escolha do cartão "O
        # que resolver primeiro". O maior da base pode depender do filiado
        # ou do tribunal, e apontá-lo mandaria o sindicato trabalhar no que
        # não depende dele. A lista já vem do maior para o menor.
        seu = next((g for g in gargalos if g["quem"] == CONFERENCIA), None)
        if seu is None:
            frases = ["Hoje não há pendência que dependa do sindicato."]
        else:
            frases = [f"O que destrava mais gente e depende do sindicato: "
                      f"{seu['o_que']} — "
                      f"{_n(seu['pessoas'], 'pessoa', 'pessoas')}."]
        presos = max((g["pessoas"] for g in gargalos
                      if g["quem"] == TRIBUNAL), default=0)
        if presos:
            frases.append(
                f"{_n(presos, 'pessoa espera', 'pessoas esperam')} um "
                "julgamento: isso não depende do sindicato nem delas.")
        frases.append("O detalhe está na aba Resumo, em “O que resolver "
                      "primeiro”.")
        return frases

    if assunto == PENDENCIAS:
        if "gargalos" not in panorama:
            return ["Não consegui apurar as pendências da base agora."]
        if not gargalos:
            return ["Não há pendência na base agora."]
        return (["As maiores pendências da base, e de quem dependem:"]
                + [_linha_do_gargalo(g) for g in gargalos[:4]]
                + ["A lista completa está na aba Resumo."])

    if assunto == PODEM:
        if "aptos" not in panorama:
            return ["Não consegui apurar isso agora."]
        aptos = panorama["aptos"]
        frases = [
            (f"{_n(aptos, 'pessoa da base tem', 'pessoas da base têm')} ao "
             "menos uma coisa que já pode fazer.") if aptos else
            "Hoje ninguém da base aparece como podendo fazer alguma coisa. "
            "Isso não quer dizer que não têm direito: quer dizer que ainda "
            "falta algo para afirmar — e o que falta está nas pendências."]
        for a in (panorama.get("por_acao") or [])[:4]:
            frases.append(
                f"{a['rotulo']}: {a['participam']} participam, e de "
                f"{a['indeterminados']} ainda não deu para dizer.")
        frases.append("Nada disso é parecer: antes de qualquer medida em "
                      "nome de alguém, um advogado confere e assina.")
        return frases

    if assunto == ENVIOS:
        return ["Tudo que o sindicato envia fica na aba Envios e pedidos: a "
                "planilha de filiados, os documentos que o sindicato já "
                "guarda, o rol de substituídos e o pedido de apagamento de "
                "um filiado.",
                "A planilha pode ir do jeito que está, em Excel ou CSV. "
                "Nada é gravado antes de você conferir o que ela traz."]

    if assunto == VALOR:
        return ["Não calculamos valor. Sem a ficha financeira de cada "
                "pessoa e o que a sentença fixou, qualquer número seria "
                "chute — e um número errado vira promessa."]

    if assunto == AJUDA:
        return ["Sou o Proto, o assistente automático do portal. Respondo "
                "com o que está no painel do sindicato, na hora — não sou "
                "uma pessoa, e não dou parecer.",
                "Pode perguntar quantos filiados há na base, com quantos "
                "dá para falar, quantos entraram no portal, o que há para "
                "ler e o que resolver primeiro."]

    return ["Não entendi a pergunta, e prefiro dizer isso a responder outra "
            "coisa.",
            "Sei responder sobre o tamanho da base, o contato com os "
            "filiados, quem entrou no portal, os documentos para ler, as "
            "pendências e onde enviar cada coisa."]
