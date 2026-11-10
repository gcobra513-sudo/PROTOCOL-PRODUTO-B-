"""A leitura que uma PESSOA faz do documento que a máquina não lê.

Scanner e foto passaram a entrar (10/11/2026), e a fila ficou com entrada e
contador e SEM SAÍDA: quem mandava foto da sentença ficava em "falta a
leitura da sentença já entregue" para sempre. Este módulo é a saída.

QUEM LÊ É O SINDICATO, pelo painel dele — decisão de 10/11/2026. O gestor
abre o documento, e registra uma de duas coisas:

    lido      o que o documento diz, nos poucos campos que o motor usa
    ilegivel  nem uma pessoa conseguiu — e aí o sindicato sabe a quem pedir
              de novo

O QUE O GESTOR REGISTRA VIRA FATO, e fato alimenta o motor. Por isso:

- só entram valores que EXISTEM: o dispositivo é um de quatro, a data é uma
  data de verdade e não está no futuro. Texto livre não vira fato;
- todo registro tem AUTOR (o marcador do gestor, nunca o CPF dele) e data;
- o fato entra como `metodo = "pessoa"`, e é assim que se distingue para
  sempre do que a máquina leu. Se os dois discordarem, o motor não escolhe:
  a divergência derruba o fato, e alguém olha.

A AUTORIDADE É UM ARQUIVO APPEND-ONLY, `leituras.jsonl`, e não o banco. A
leitura humana não é derivável de nada: se morasse só na projeção, perder o
banco seria perder o trabalho do gestor. O banco se refaz daqui
(`banco.projetar_leituras`).

O arquivo guarda o CPF do filiado e o que a sentença dele diz — é dado
pessoal, e sai no apagamento a pedido (`remover_pessoa`).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib

from nucleo import leitura, processo_cnj

from . import deposito, validacao

ARQUIVO = "leituras.jsonl"

LIDO = "lido"
ILEGIVEL = "ilegivel"
RESULTADOS = (LIDO, ILEGIVEL)

#: Teto da observação livre. Ela vai para o trecho do fato, não é fato.
TETO_DA_OBSERVACAO = 300

DISPOSITIVOS = (*leitura.DISPOSITIVOS_COM_TITULO,
                *leitura.DISPOSITIVOS_SEM_TITULO)


def _competencia(valor: str) -> str | None:
    """AAAA-MM de verdade, ou None."""
    try:
        ano, mes = valor.split("-")
        dt.date(int(ano), int(mes), 1)
    except (ValueError, AttributeError):
        return None
    return f"{int(ano):04d}-{int(mes):02d}" if len(ano) == 4 else None


def validar(tipo: str, resultado: str, fatos, observacao: str = ""
            ) -> tuple[dict[str, str], list[str]]:
    """(fatos limpos, problemas). Lista vazia de problemas = pode gravar.

    OS CAMPOS DEPENDEM DO TIPO DO DOCUMENTO, e são só os que o motor usa:
    pedir ao gestor que transcreva a sentença inteira é pedir um trabalho
    que ninguém faz, e que ninguém usaria.

        sentenca           o dispositivo (obrigatório), o número do processo
        certidao_transito  a data do trânsito em julgado (obrigatória)
        contribuicao       o período que o comprovante cobre (obrigatório)
        qualquer outro     nada — só registra que foi lido
    """
    problemas: list[str] = []
    if resultado not in RESULTADOS:
        return {}, [f"resultado desconhecido: {resultado!r} "
                    f"(use {' ou '.join(RESULTADOS)})"]
    if len(observacao or "") > TETO_DA_OBSERVACAO:
        problemas.append(
            f"a observação tem {len(observacao)} caracteres e o limite é "
            f"{TETO_DA_OBSERVACAO}"
        )
    if not isinstance(fatos, dict):
        return {}, problemas + ["os fatos lidos têm de vir como campos"]
    if resultado == ILEGIVEL:
        # Quem não conseguiu ler não afirma nada sobre o conteúdo.
        if any(str(v).strip() for v in fatos.values()):
            problemas.append("documento ilegível não pode trazer fato lido")
        return {}, problemas

    limpos: dict[str, str] = {}
    f = {k: str(v or "").strip() for k, v in fatos.items()}

    if tipo == "sentenca":
        if f.get("dispositivo") not in DISPOSITIVOS:
            problemas.append(
                "diga o que a sentença decidiu: " + ", ".join(DISPOSITIVOS)
            )
        else:
            limpos["dispositivo"] = f["dispositivo"]
        numero = validacao.so_digitos(f.get("numero_processo", ""))
        if numero:
            if processo_cnj.valido(numero):
                limpos["numero_processo"] = numero
            else:
                problemas.append(
                    "o número do processo não fecha no dígito verificador"
                )
    elif tipo == "certidao_transito":
        try:
            data = dt.date.fromisoformat(f.get("transito_em_julgado", ""))
        except ValueError:
            data = None
        if data is None:
            problemas.append("a data do trânsito em julgado não é uma data "
                             "(use AAAA-MM-DD)")
        elif data > dt.date.today():
            problemas.append("a data do trânsito em julgado está no futuro")
        elif data.year < 1988:
            problemas.append("a data do trânsito em julgado é anterior a "
                             "1988 — confira")
        else:
            limpos["transito_em_julgado"] = data.isoformat()
    elif tipo == "contribuicao":
        inicio = _competencia(f.get("periodo_inicio", ""))
        fim = _competencia(f.get("periodo_fim", ""))
        if not inicio or not fim:
            problemas.append("diga o período que o comprovante cobre, de "
                             "AAAA-MM a AAAA-MM")
        elif fim < inicio:
            problemas.append("o período termina antes de começar")
        else:
            # A mesma forma que `nucleo.leitura` usa para o período lido
            # pela máquina: quem consome não distingue as duas origens pela
            # forma, só pelo método.
            limpos["periodo"] = f"{inicio}/{fim}"
    return limpos, problemas


def registrar(pasta_entidade: pathlib.Path, *, entidade: str, cpf: str,
              documento: str, tipo: str, resultado: str,
              fatos: dict[str, str], observacao: str, quem: str) -> dict:
    """Acrescenta a leitura ao arquivo, com fsync, e devolve o registro.

    ANTES DO BANCO, pela mesma razão do diário de cadastro: se o banco
    falhar, a leitura está gravada e a projeção se refaz.
    """
    registro = {
        "lido_em": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "entidade": entidade,
        "cpf": validacao.so_digitos(cpf),
        "documento": documento,
        "tipo": tipo,
        "resultado": resultado,
        "fatos": dict(fatos),
        "observacao": (observacao or "").strip(),
        "quem": quem,
    }
    pasta_entidade.mkdir(parents=True, exist_ok=True)
    deposito.anexar_com_fsync(
        pasta_entidade / ARQUIVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return registro


def ler(pasta_entidade: pathlib.Path) -> list[dict]:
    """Todas as leituras registradas, na ordem. Linha ilegível é pulada."""
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return []
    saida = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict):
            saida.append(registro)
    return saida


def achados_de(registro: dict) -> list[leitura.Achado]:
    """Os fatos de UMA leitura, na forma que o resto do produto consome.

    `CERTO`, porque uma pessoa leu e respondeu por isso — com `metodo`
    "pessoa", que é o que mantém a origem visível. O TRECHO não é um trecho
    do documento (não há texto de onde recortar): diz quem leu e quando, que
    é a justificativa que este fato tem.
    """
    if registro.get("resultado") != LIDO:
        return []
    quando = str(registro.get("lido_em", ""))[:10]
    trecho = (f"lido por uma pessoa do sindicato em {quando} "
              f"(marcador {str(registro.get('quem', ''))[:8]})")
    observacao = str(registro.get("observacao") or "").strip()
    if observacao:
        trecho += f": {observacao}"
    return [
        leitura.Achado(tipo=tipo, valor=str(valor), confianca=leitura.CERTO,
                       trecho=trecho, posicao=0, metodo="pessoa")
        for tipo, valor in sorted((registro.get("fatos") or {}).items())
    ]


def remover_pessoa(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira as leituras desta pessoa. Para o apagamento a pedido.

    O arquivo guarda o CPF dela e o que a sentença dela diz: é dado pessoal,
    e "append-only" quer dizer "não se edita", não "não se apaga nunca". A
    linha de quem NÃO pediu para sair fica byte a byte, inclusive a que não
    der para interpretar.
    """
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return 0
    digitos = validacao.so_digitos(cpf)
    guardadas: list[str] = []
    sairam = 0
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            guardadas.append(bruta)
            continue
        if isinstance(registro, dict) and validacao.so_digitos(
                str(registro.get("cpf", ""))) == digitos:
            sairam += 1
            continue
        guardadas.append(bruta)
    if not sairam:
        return 0
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                 deposito.MODO_ARQUIVO)
    try:
        os.write(fd, ("".join(l + "\n" for l in guardadas)).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(caminho)
    return sairam
