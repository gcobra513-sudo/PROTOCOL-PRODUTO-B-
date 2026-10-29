#!/usr/bin/env python3
"""Confere a entrega do portal — o nosso lado do contrato de dados.

Roda sobre a pasta que o portal exporta e responde, por filiado: dá para
trabalhar com isso, ou falta coisa? Antes de qualquer peça, antes da triagem.

Checa o que ESTA etapa pode checar sozinha:

  - CPF com dígito verificador
  - número do processo com dígito verificador (Res. CNJ 65/2008) e se é TRF1
  - presença dos documentos obrigatórios
  - **PDF com texto selecionável** — procuração que é só imagem não pode ser
    conferida por máquina, e o QC reprova a peça lá na frente
  - **CPF do cadastro presente no texto dos documentos** — pega documento de
    outra pessoa na pasta errada
  - SHA-256 de cada arquivo, para procedência

Produz relatório agregado: se 4 mil pastas falham pelo MESMO motivo, o
problema é do portal, não das pessoas — e a correção é lá, não aqui.

Uso:
    python3 ferramentas/conferir_entrega.py --entrega entrega/
    python3 ferramentas/conferir_entrega.py --entrega entrega/ --planilha saida.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo.processo_cnj import conferir as conferir_processo  # noqa: E402

# Nomes fixos por tipo. LIDOS DO CONTRATO COMPARTILHADO, não repetidos aqui:
# o portal lê o mesmo arquivo. Enquanto cada lado tinha a sua lista, três dos
# seis nomes divergiam — e a divergência só apareceria quando a primeira
# entrega de verdade chegasse, com todas as pastas reprovando por arquivo
# faltando.
CONTRATO = json.loads(
    (RAIZ / "compartilhado" / "contrato_entrega.json").read_text(encoding="utf-8")
)
OBRIGATORIOS = tuple(CONTRATO["obrigatorios"])
SE_TEM_PROCESSO = tuple(CONTRATO["se_tem_processo"])
DESEJAVEIS = tuple(CONTRATO["desejaveis"])

# Termos que indicam poderes para executar. Ausência NÃO reprova: a redação
# varia muito e reprovar por isso geraria falso positivo em massa. Sinaliza.
PADRAO_PODERES = re.compile(
    r"execu|cumprimento de senten|receber e dar quita|levantar valor", re.I
)


def sha256(caminho: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def texto_do_pdf(caminho: pathlib.Path) -> str:
    """Extrai texto. Devolve "" quando o PDF é imagem (ou está corrompido)."""
    try:
        import pypdf
    except ImportError:
        return ""
    try:
        r = pypdf.PdfReader(str(caminho))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:
        return ""


def _so_digitos(v: str) -> str:
    return re.sub(r"\D", "", str(v or ""))


def cpf_valido(cpf: str) -> bool:
    d = _so_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for corte in (9, 10):
        soma = sum(int(d[i]) * (corte + 1 - i) for i in range(corte))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[corte]):
            return False
    return True


def conferir_pasta(pasta: pathlib.Path, registro: dict) -> dict:
    """Confere uma pasta de filiado contra a linha dele no manifesto."""
    cpf = registro.get("cpf", "")
    tem_processo = (registro.get("tem_processo") or "").strip().lower()
    numero = registro.get("numero_processo") or ""

    problemas: list[str] = []
    avisos: list[str] = []
    arquivos: dict[str, str] = {}

    # ---- cadastro ----
    if not cpf_valido(cpf):
        problemas.append("cpf_invalido")
    # `data_nascimento` entra aqui porque é dela que sai a prioridade de
    # tramitação. Uma pasta que chegue ao motor sem ela faria o lote inteiro
    # perder "Idoso(a)" — e o erro só apareceria quando ninguém mais olhasse.
    for campo in ("nome_completo", "logradouro", "municipio", "uf", "cep",
                  "data_nascimento"):
        if not (registro.get(campo) or "").strip():
            problemas.append(f"campo_vazio:{campo}")

    situacao = (registro.get("situacao") or "").strip().lower()
    if situacao not in ("ativo", "aposentado", "pensionista"):
        problemas.append(f"situacao_invalida:{situacao or 'vazia'}")
    elif situacao != "ativo" and not (registro.get("data_aposentadoria") or "").strip():
        problemas.append("sem_data_aposentadoria")

    # ---- processo de origem ----
    if tem_processo == "sim":
        falhas = conferir_processo(numero, exigir_trf1=True)
        for f in falhas:
            problemas.append(f"processo:{f}")
    elif tem_processo == "nao_sei":
        avisos.append("processo_desconhecido: precisa ser descoberto pelo CPF")
    elif tem_processo == "nao":
        avisos.append("declarou não ter processo: sem título, não há o que executar")
    else:
        problemas.append("tem_processo_nao_informado")

    # ---- declarações ----
    if (registro.get("ja_tem_execucao") or "").strip().lower() == "sim":
        problemas.append("DECLAROU_EXECUCAO_EM_CURSO: risco de duplicidade")
    if (registro.get("ja_recebeu_acordo") or "").strip().lower() == "sim":
        problemas.append("DECLAROU_ACORDO: pode já estar satisfeito")
    if not (registro.get("ciencia_e_iniciativa") or "").strip():
        problemas.append("sem_declaracao_de_ciencia")

    # ---- documentos ----
    if not pasta.is_dir():
        problemas.append("pasta_ausente")
        return _resultado(registro, problemas, avisos, arquivos)

    esperados = list(OBRIGATORIOS) + (
        list(SE_TEM_PROCESSO) if tem_processo == "sim" else []
    )
    for nome in esperados:
        caminho = pasta / nome
        if not caminho.is_file():
            problemas.append(f"documento_ausente:{nome}")
            continue
        arquivos[nome] = sha256(caminho)

        texto = texto_do_pdf(caminho)
        if not texto.strip():
            # O erro mais caro da entrega: imagem sem camada de texto.
            problemas.append(f"sem_texto_selecionavel:{nome}")
            continue
        if cpf_valido(cpf) and _so_digitos(cpf) not in _so_digitos(texto):
            avisos.append(f"cpf_nao_encontrado_no_documento:{nome}")

        if nome == "procuracao.pdf" and not PADRAO_PODERES.search(texto):
            avisos.append("procuracao_sem_mencao_a_poderes_de_execucao")

    for nome in DESEJAVEIS:
        if (pasta / nome).is_file():
            arquivos[nome] = sha256(pasta / nome)
        else:
            avisos.append(f"documento_desejavel_ausente:{nome}")

    # arquivo na pasta que ninguém pediu: pode ser documento trocado de tipo
    conhecidos = set(OBRIGATORIOS) | set(SE_TEM_PROCESSO) | set(DESEJAVEIS)
    for extra in sorted(p.name for p in pasta.iterdir() if p.is_file()):
        if extra not in conhecidos:
            avisos.append(f"arquivo_inesperado:{extra}")

    return _resultado(registro, problemas, avisos, arquivos)


def _resultado(registro, problemas, avisos, arquivos) -> dict:
    return {
        "id_externo": registro.get("id_externo", ""),
        "cpf": registro.get("cpf", ""),
        "numero_processo": registro.get("numero_processo", ""),
        "estado": "COMPLETO" if not problemas else "INCOMPLETO",
        "problemas": problemas,
        "avisos": avisos,
        "arquivos": arquivos,
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--entrega", required=True, help="pasta exportada pelo portal")
    p.add_argument("--manifesto", default=None, help="padrão: <entrega>/manifesto.csv")
    p.add_argument("--planilha", default=None,
                   help="CSV de saída só com os COMPLETOS, pronto para triar")
    p.add_argument("--relatorio", default=None, help="JSON com todos os detalhes")
    args = p.parse_args()

    entrega = pathlib.Path(args.entrega)
    manifesto = pathlib.Path(args.manifesto or entrega / "manifesto.csv")
    if not manifesto.is_file():
        print(f"ERRO: não encontrei {manifesto}", file=sys.stderr)
        return 2

    with open(manifesto, newline="", encoding="utf-8") as fh:
        registros = list(csv.DictReader(fh))
    if not registros:
        print(f"{manifesto} está vazio", file=sys.stderr)
        return 1

    resultados = []
    for reg in registros:
        pasta = entrega / _so_digitos(reg.get("cpf", ""))
        resultados.append(conferir_pasta(pasta, reg))

    completos = [r for r in resultados if r["estado"] == "COMPLETO"]
    incompletos = [r for r in resultados if r["estado"] == "INCOMPLETO"]

    cont_prob: dict[str, int] = {}
    cont_avisos: dict[str, int] = {}
    for r in resultados:
        for x in r["problemas"]:
            chave = x.split(":")[0]
            cont_prob[chave] = cont_prob.get(chave, 0) + 1
        for x in r["avisos"]:
            chave = x.split(":")[0]
            cont_avisos[chave] = cont_avisos.get(chave, 0) + 1

    print("=" * 62)
    print("CONFERÊNCIA DA ENTREGA DO PORTAL")
    print("=" * 62)
    print(f"  filiados no manifesto ....... {len(registros)}")
    print(f"  COMPLETOS ................... {len(completos)}")
    print(f"  INCOMPLETOS ................. {len(incompletos)}")
    if cont_prob:
        print("\n  problemas (quantos filiados cada um afeta):")
        for k, n in sorted(cont_prob.items(), key=lambda kv: -kv[1]):
            print(f"    {n:>7}  {k}")
    if cont_avisos:
        print("\n  avisos (não impedem, mas vale olhar):")
        for k, n in sorted(cont_avisos.items(), key=lambda kv: -kv[1]):
            print(f"    {n:>7}  {k}")

    if incompletos:
        print("\n  exemplos:")
        for r in incompletos[:6]:
            print(f"    [{r['id_externo'] or r['cpf']}] {r['problemas'][0]}")

    # O recado que mais importa: problema em massa é problema do portal.
    if registros and cont_prob:
        pior, n = max(cont_prob.items(), key=lambda kv: kv[1])
        if n / len(registros) > 0.2:
            print(
                f"\n  *** {n} de {len(registros)} filiados ({n/len(registros):.0%}) "
                f"falham por '{pior}'. Isso é defeito do portal ou da instrução "
                f"dada às pessoas — corrigir lá, não aqui, caso por caso. ***"
            )

    if args.planilha:
        campos = list(registros[0].keys())
        cpfs_ok = {_so_digitos(r["cpf"]) for r in completos}
        with open(args.planilha, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            for reg in registros:
                if _so_digitos(reg.get("cpf", "")) in cpfs_ok:
                    w.writerow(reg)
        print(f"\n  planilha dos completos -> {args.planilha}")

    if args.relatorio:
        pathlib.Path(args.relatorio).write_text(
            json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"  relatório detalhado    -> {args.relatorio}")

    return 0 if completos else 1


if __name__ == "__main__":
    raise SystemExit(main())
