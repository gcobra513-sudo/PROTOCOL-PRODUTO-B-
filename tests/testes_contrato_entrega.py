"""O contrato de dados portal <-> motor, consumido de verdade.

Monta uma entrega no formato que o portal produz — usando o MESMO código
TypeScript, executado por Node — e manda o `conferir_entrega.py` consumir.

POR QUE NÃO BASTA TESTAR OS DOIS LADOS SEPARADO

Testar "o portal gera as colunas do contrato" e "o verificador lê as colunas
do contrato" deixa passar o caso em que ambos leem o contrato e ainda assim
não se entendem — valor em formato diferente, pasta com nome diferente,
arquivo esperado que ninguém gera. O único jeito de saber é um produzir e o
outro consumir.

Foi exatamente o que aconteceu antes: o portal nomeava `residencia.pdf` e o
verificador esperava `comprovante_residencia.pdf`. Três dos seis nomes
divergiam, e a divergência só apareceria na primeira entrega real.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

CONTRATO = json.loads(
    (RAIZ / "compartilhado" / "contrato_entrega.json").read_text(encoding="utf-8")
)
LOTE = RAIZ / "demo" / "saida" / "SINDIFISCO-2026-01"

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


#: Chaves de PROSA: explicação para quem lê, não compromisso entre as pontas.
#: Mudar texto aqui não é mudar contrato, e não deve exigir subir a versão —
#: se exigisse, a trava viraria estorvo e alguém a desligaria.
_PROSA = ("_versao", "_gerado_em", "_sobre", "_notas")

#: A versão e a soma que ESTE teste conhece. Mudar o contrato sem mexer nos
#: dois reprova, e a mensagem de falha já diz os valores novos.
VERSAO_ESPERADA = 2
SOMA_ESPERADA = "d43cbed8d4772498ff6e9c1d805d16f7e960210ce7f97727b9af3c2a33895549"


def soma_do_contrato() -> str:
    """Impressão digital do que as duas pontas realmente combinam."""
    conteudo = {k: v for k, v in CONTRATO.items() if k not in _PROSA}
    bruto = json.dumps(conteudo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def t_contrato_declara_versao():
    checa(isinstance(CONTRATO.get("_versao"), int),
          f"contrato sem _versao inteiro: {CONTRATO.get('_versao')!r}")
    checa(isinstance(CONTRATO.get("_versao"), int) and CONTRATO["_versao"] >= 1,
          f"_versao inválida: {CONTRATO.get('_versao')!r}")


def t_mudar_o_contrato_sem_subir_a_versao_reprova():
    """A trava. O contrato é lido pelos DOIS produtos: o portal produz e o
    motor consome. Uma mudança de forma que passasse sem aviso só apareceria
    na primeira entrega real — foi o que já aconteceu com três dos seis nomes
    de arquivo.
    """
    checa(soma_do_contrato() == SOMA_ESPERADA,
          f"o contrato mudou de forma: suba _versao para "
          f"{(CONTRATO.get('_versao') or 0) + 1} e ponha "
          f"SOMA_ESPERADA = {soma_do_contrato()!r}")
    checa(CONTRATO.get("_versao") == VERSAO_ESPERADA,
          f"_versao é {CONTRATO.get('_versao')!r} e este teste espera "
          f"{VERSAO_ESPERADA} — atualize VERSAO_ESPERADA junto com a soma")


def _verificador():
    spec = importlib.util.spec_from_file_location(
        "conferir_entrega", RAIZ / "ferramentas" / "conferir_entrega.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifesto_pelo_portal() -> Path:
    """Gera o manifesto chamando o código do PORTAL, via Node.

    Não reescrevemos a geração em Python: isso criaria uma TERCEIRA
    implementação para divergir das outras duas.

    O script fica DENTRO de portal/ porque o import é relativo: escrito num
    diretório temporário, o Node procurava `/tmp/portal/src/lib/exportar.ts` e
    não achava — e a primeira versão deste teste tratava isso como "parcial" e
    imprimia `ok`. Teste que não rodou não passou.
    """
    script = RAIZ / "portal" / ".gerar_entrega.mjs"
    script.write_text(
        """
import { manifestoCsv } from "./src/lib/exportar.ts";
import { RASCUNHO_VAZIO } from "./src/lib/tipos.ts";
const base = JSON.parse(process.argv[2]);
const r = {
  ...RASCUNHO_VAZIO,
  pessoais: { ...RASCUNHO_VAZIO.pessoais, ...base.pessoais },
  funcional: { ...RASCUNHO_VAZIO.funcional, ...base.funcional },
  processo: { ...RASCUNHO_VAZIO.processo, ...base.processo },
  declaracoes: { ...RASCUNHO_VAZIO.declaracoes, ...base.declaracoes },
};
process.stdout.write(manifestoCsv([r]));
""".strip(),
        encoding="utf-8",
    )
    return script


def _dados_do_lote() -> tuple[str, str, Path]:
    """Pega um caso do lote de demonstração: CPF real do manifesto e o PDF."""
    registros = [json.loads(l) for l in
                 open(LOTE / "manifesto.jsonl", encoding="utf-8")]
    reg = next(r for r in registros if r["status"] == "PRONTO")
    pdf = LOTE / "pronto" / reg["arquivos"]["pdf"]["nome"]
    return reg["cpf"], reg["nome"], pdf


def t_entrega_do_portal_e_aceita_pelo_motor():
    """O teste que importa: um produz, o outro consome."""
    cpf, nome, pdf = _dados_do_lote()
    digitos = "".join(c for c in cpf if c.isdigit())

    with tempfile.TemporaryDirectory() as tmp:
        entrega = Path(tmp) / "entrega"
        pasta = entrega / digitos
        pasta.mkdir(parents=True)

        # Os documentos, com os nomes DO CONTRATO. Um PDF com camada de texto
        # e com o CPF dentro — é o que o verificador exige.
        for nome_arquivo in (
            list(CONTRATO["obrigatorios"])
            + list(CONTRATO["se_tem_processo"])
        ):
            shutil.copy(pdf, pasta / nome_arquivo)

        # O manifesto, gerado pelo código do portal via Node.
        linha = {
            "pessoais": {
                "dataNascimento": "1958-06-27",
                "nome": nome, "cpf": cpf, "email": "a@b.com",
                "telefone": "61999990000", "cep": "70000-000",
                "logradouro": "Rua das Flores", "numero": "100",
                "bairro": "Centro", "municipio": "Brasília", "uf": "DF",
            },
            "funcional": {
                "cargo": "Auditor-Fiscal", "situacao": "ativo",
                "dataIngresso": "2005-03-01",
            },
            "processo": {
                "temProcesso": "sim",
                "numero": "0000001-91.2026.4.01.3400",
            },
            "declaracoes": {
                "jaExecutou": "nao", "jaRecebeu": "nao",
                "outroAdvogado": "nao", "cienciaEIniciativa": True,
            },
        }
        script = _manifesto_pelo_portal()
        try:
            proc = subprocess.run(
                ["npx", "--yes", "tsx", script.name,
                 json.dumps(linha, ensure_ascii=False)],
                cwd=script.parent, capture_output=True, text=True, timeout=300,
            )
        finally:
            script.unlink(missing_ok=True)
        # FALHA, não "parcial". A primeira versão deste teste devolvia e
        # imprimia `ok` quando o Node não rodava — o teste central do contrato
        # não rodava e ninguém sabia.
        checa(proc.returncode == 0,
              f"o gerador do portal não rodou via Node, então o contrato NÃO "
              f"foi testado de ponta a ponta: {proc.stderr.strip()[-300:]}")
        if proc.returncode != 0:
            return
        (entrega / "manifesto.csv").write_text(proc.stdout, encoding="utf-8")

        # ---- agora o MOTOR consome ----
        mod = _verificador()
        with open(entrega / "manifesto.csv", newline="", encoding="utf-8") as fh:
            registros = list(csv.DictReader(fh))
        checa(len(registros) == 1,
              f"o manifesto do portal deveria ter 1 linha, tem {len(registros)}")
        if not registros:
            return

        resultado = mod.conferir_pasta(pasta, registros[0])
        checa(resultado["estado"] == "COMPLETO",
              f"o motor recusou a entrega do portal: "
              f"problemas={resultado['problemas']} avisos={resultado['avisos']}")
        checa(not resultado["problemas"],
              f"problemas inesperados: {resultado['problemas']}")


def t_colunas_batem_nos_dois_lados():
    """As colunas que o verificador lê existem no contrato."""
    fonte = (RAIZ / "ferramentas" / "conferir_entrega.py").read_text("utf-8")
    import re

    lidas = set(re.findall(r'registro\.get\("([a-z_]+)"', fonte))
    # `.strip()` em cada nome: a tupla no fonte pode estar quebrada em várias
    # linhas, e antes a quebra entrava no nome como "\ndata_nascimento".
    _tuplas = re.findall(r'for campo in \(([^)]*)\)', fonte)
    if _tuplas:
        lidas |= {n.replace('"', "").strip()
                  for n in _tuplas[0].split(",")}
    lidas.discard("")
    colunas = set(CONTRATO["colunas_manifesto"])
    faltando = sorted(lidas - colunas)
    checa(not faltando,
          f"o verificador lê colunas que o contrato não tem: {faltando}")


def t_nomes_de_arquivo_batem_nos_dois_lados():
    mod = _verificador()
    do_contrato = set(CONTRATO["arquivos"].values())
    do_motor = set(mod.OBRIGATORIOS) | set(mod.SE_TEM_PROCESSO) | set(mod.DESEJAVEIS)
    checa(do_motor <= do_contrato,
          f"o motor espera arquivos fora do contrato: {sorted(do_motor - do_contrato)}")
    ts = (RAIZ / "portal" / "src" / "lib" / "tipos.ts").read_text("utf-8")
    checa("CONTRATO.arquivos" in ts,
          "o portal deveria tirar os nomes de arquivo do contrato, não "
          "escrevê-los à mão — foi assim que três dos seis divergiram")


def t_pasta_e_nomeada_pelos_digitos_do_cpf():
    """O verificador procura a pasta por `_so_digitos(cpf)`."""
    mod = _verificador()
    checa(mod._so_digitos("111.444.777-35") == "11144477735",
          "a pasta é nomeada pelos 11 dígitos, sem pontuação")
    nota = CONTRATO["_notas"]["pasta"]
    checa("11 dígitos" in nota and "sem pontuação" in nota,
          "o contrato deveria dizer como a pasta é nomeada")


#: Testes que leem só o contrato. Rodam SEMPRE — inclusive em clone novo, sem
#: lote de demonstração gerado. A trava de versão existe para pegar mudança
#: que ninguém percebeu; uma trava que só roda quando o lote existe não é
#: trava, é sorte.
TESTES_SEM_LOTE = [
    ("contrato declara versão", t_contrato_declara_versao),
    ("mudar o contrato sem subir a versão reprova",
     t_mudar_o_contrato_sem_subir_a_versao_reprova),
    ("colunas batem nos dois lados", t_colunas_batem_nos_dois_lados),
    ("nomes de arquivo batem nos dois lados", t_nomes_de_arquivo_batem_nos_dois_lados),
    ("pasta é nomeada pelos dígitos do CPF", t_pasta_e_nomeada_pelos_digitos_do_cpf),
]

#: Testes que precisam do lote: eles fazem o portal PRODUZIR e o motor
#: CONSUMIR, e sem lote não há PDF nem CPF de onde partir.
TESTES = [
    ("entrega do portal é aceita pelo motor", t_entrega_do_portal_e_aceita_pelo_motor),
]


def _rodar(casos: list) -> None:
    for nome, fn in casos:
        antes = len(falhas)
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            falhas.append(f"{nome}: levantou {type(exc).__name__}: {exc}")
        print(f"  {'FALHA' if len(falhas) > antes else 'ok   '}  {nome}")


def main() -> int:
    print("=" * 70)
    print("CONTRATO DE ENTREGA — o portal produz, o motor consome")
    print("=" * 70)
    _rodar(TESTES_SEM_LOTE)
    if (LOTE / "manifesto.jsonl").is_file():
        _rodar(TESTES)
    else:
        print(f"  --     ponta a ponta PULADO: sem lote em {LOTE}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES_SEM_LOTE) + len(TESTES)} testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
