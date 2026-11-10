"""O repositório não pode aceitar um commit com dado de filiado.

POR QUE ISTO É UM TESTE, E NÃO UMA LINHA DE DOCUMENTAÇÃO

O `.gitignore` dizia, em comentário, "Dados: NUNCA versionar cadastro de
gente", e cobria `dados/`. Só que a raiz PADRÃO da aplicação é
`dados_portal` — `servidor/config.py` a declara assim. A regra guardava uma
pasta que o padrão não usa, e deixava rastreável a pasta que ele usa: PDF de
sentença, `filiados.csv`, `gestores.csv`, `entidades.json`, o manifesto, o
log de códigos de acesso em claro e o log de e-mails enviados com nome e
número de processo.

Achado por auditoria independente, que mediu com `git check-ignore` em vez de
ler o comentário.

Este estrago é diferente dos outros: um dado que entra num commit e é
empurrado não sai mais com um conserto. Sai reescrevendo história, num
repositório que pode já estar clonado em outro lugar. Por isso a regra passa
a ser conferida por programa, e conferida CONTRA O PADRÃO DO CÓDIGO: se
alguém mudar `PROTOCOL_RAIZ` de padrão e esquecer o `.gitignore`, é aqui que
aparece.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


#: Os arquivos que a aplicação escreve na raiz de dados, e o que cada um
#: carrega. A lista é o que precisa estar coberto — não uma amostra.
ESCRITOS = {
    "demo-a/filiados.csv": "CPF, nome e e-mail de cada filiado",
    "demo-a/gestores.csv": "CPF e e-mail de quem abre o painel",
    "demo-a/acervo.jsonl": "a planilha inteira do sindicato",
    "demo-a/entrega/manifesto.csv": "quem entregou o quê",
    "demo-a/entrega/recebidos.jsonl": "o diário de cadastros",
    "demo-a/entrega/00000000000/sentenca.pdf": "a sentença de uma pessoa",
    "demo-a/movimentos.jsonl": "movimentação processual coletada",
    "entidades.json": "quais sindicatos este servidor atende",
    "codigos_enviados.log": "CÓDIGO DE ACESSO EM CLARO",
    "mensagens_enviadas.log": "corpo do e-mail: nome e processos",
}


def _ignorado(caminho: str) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", "-q", caminho],
        cwd=RAIZ, capture_output=True,
    )
    # 0 = ignorado, 1 = não ignorado, 128 = erro (fora de repositório).
    if r.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore falhou ({r.returncode}): "
            f"{r.stderr.decode(errors='replace')}"
        )
    return r.returncode == 0


def _raiz_padrao() -> str:
    """A raiz que a aplicação usa quando ninguém declara nada.

    Lida do código, não escrita aqui à mão: é justamente a divergência entre
    o padrão e o `.gitignore` que este arquivo existe para pegar.
    """
    from servidor.config import carregar

    cfg = carregar({"PROTOCOL_MODO_ENSAIO": "1"})
    return cfg.raiz.as_posix().rstrip("/")


def t_a_raiz_padrao_esta_ignorada():
    raiz = _raiz_padrao()
    checa(_ignorado(f"{raiz}/qualquer-coisa"),
          f"a raiz de dados PADRÃO ({raiz!r}) não está no .gitignore — "
          f"um commit distraído versiona dado de filiado")


def t_cada_arquivo_que_a_aplicacao_escreve_esta_ignorado():
    raiz = _raiz_padrao()
    for relativo, oquee in ESCRITOS.items():
        caminho = f"{raiz}/{relativo}"
        checa(_ignorado(caminho),
              f"{caminho} está rastreável, e carrega {oquee}")


def t_nada_sensivel_ja_entrou_no_indice():
    """Ignorar depois não desfaz o que já está versionado.

    `git check-ignore` responde sobre a regra, não sobre o índice: arquivo
    já rastreado continua rastreado mesmo depois de entrar no `.gitignore`.
    Então vale perguntar ao índice também.
    """
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ,
                       capture_output=True, text=True, check=True)
    rastreados = r.stdout.splitlines()
    suspeitos = [
        c for c in rastreados
        if c.startswith(("dados/", "dados_portal/"))
        or c.endswith((".pdf", "filiados.csv", "gestores.csv",
                       "entidades.json", "codigos_enviados.log",
                       "mensagens_enviadas.log"))
    ]
    checa(not suspeitos,
          f"arquivos de dado já estão versionados, e ignorar agora não os "
          f"tira do histórico: {suspeitos}")


def t_a_pasta_antiga_continua_ignorada():
    """`dados/` não era a raiz padrão, mas é usada à mão e por ferramenta.

    Consertar o padrão não é motivo para destravar a outra.
    """
    checa(_ignorado("dados/qualquer-coisa"),
          "dados/ deixou de estar ignorada")


def t_escritorio_nao_e_arquitetura():
    """A REGRA ZERO, conferida por programa.

    `CLAUDE.md` diz: "Se um escritório existir na relação, ele foi contratado
    pelo sindicato, e **isso é contrato, não arquitetura**."

    A casa já guardava os TEXTOS — três testes conferem que nenhum aviso,
    pendência ou tela fala de escritório ao filiado. O que não tinha guarda
    era a ESTRUTURA: `entidades.Entidade` tinha um campo `escritorio`, e
    campo é arquitetura. Ele não era lido por ninguém, o que é o pior caso:
    o produto carregava a hipótese do Produto A sem receber nada por ela, e
    cada entidade criada gravava a chave no `entidades.json`.

    A conferência é sobre IDENTIFICADOR, não sobre a palavra: `escritorio`
    sem acento é o jeito de a palavra virar código. A palavra com acento
    continua podendo aparecer em comentário — inclusive para explicar esta
    regra, que é o que `nucleo/pendencia.py` faz.
    """
    import re

    alvo = re.compile(r"\bescritorio\b")
    achados = []
    for pasta in ("nucleo", "servidor", "ferramentas", "portal/src"):
        for caminho in sorted((RAIZ / pasta).rglob("*")):
            if caminho.suffix not in (".py", ".ts", ".tsx"):
                continue
            if ".test." in caminho.name:
                continue
            for n, linha in enumerate(
                caminho.read_text(encoding="utf-8").splitlines(), 1
            ):
                # Comentário é texto, não estrutura. A regra fala de
                # arquitetura, e um comentário que EXPLICA a regra tem de
                # poder nomeá-la.
                nua = linha.strip()
                if nua.startswith(("#", "//", "*", "/*")):
                    continue
                if alvo.search(linha):
                    achados.append(
                        f"{caminho.relative_to(RAIZ)}:{n}: {nua[:70]}")
    checa(not achados,
          "escritório voltou a ser arquitetura, e a Regra Zero diz que ele é "
          "contrato:\n  " + "\n  ".join(achados))


def t_ha_um_so_lugar_que_monta_os_fatos_de_uma_pessoa():
    """`motor.Fatos(` é construído em UM lugar do código de produção.

    Eram dois construtores — um para a tela do filiado, que lia os
    documentos, e um para o painel e para o veredicto guardado, que fixava
    `tem_titulo=None`. Medido em 10/11/2026: a mesma pessoa recebia
    respostas diferentes conforme quem perguntava, e a prova guardada era a
    mais fraca das três.

    Um teste de concordância entre as três superfícies pega a divergência
    DEPOIS que ela existe. Este pega antes: um segundo `motor.Fatos(` em
    código de produção é um segundo jeito de montar os fatos, e é assim que
    a divergência nasce.
    """
    achados = []
    for pasta in ("nucleo", "servidor", "ferramentas"):
        for caminho in sorted((RAIZ / pasta).rglob("*.py")):
            for n, linha in enumerate(
                caminho.read_text(encoding="utf-8").splitlines(), 1
            ):
                if "motor.Fatos(" in linha and not linha.strip().startswith("#"):
                    achados.append(f"{caminho.relative_to(RAIZ)}:{n}")
    checa(len(achados) == 1 and achados[0].startswith("nucleo/panorama.py:"),
          f"os fatos de uma pessoa são montados em mais de um lugar (ou em "
          f"nenhum): {achados}")


TESTES = [
    ("a raiz de dados padrão está ignorada", t_a_raiz_padrao_esta_ignorada),
    ("todo arquivo que a aplicação escreve está ignorado",
     t_cada_arquivo_que_a_aplicacao_escreve_esta_ignorado),
    ("nada sensível já entrou no índice", t_nada_sensivel_ja_entrou_no_indice),
    ("a pasta antiga continua ignorada", t_a_pasta_antiga_continua_ignorada),
    ("escritório não é arquitetura (Regra Zero)",
     t_escritorio_nao_e_arquitetura),
    ("um só lugar monta os fatos de uma pessoa",
     t_ha_um_so_lugar_que_monta_os_fatos_de_uma_pessoa),
]


def main() -> int:
    print("=" * 70)
    print("HIGIENE DO REPOSITÓRIO (dado de filiado nunca vira commit)")
    print("=" * 70)
    for nome, fn in TESTES:
        antes = len(falhas)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{nome}: levantou {type(exc).__name__}: {exc}")
        print(f"  {'FALHA' if len(falhas) > antes else 'ok   '}  {nome}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
