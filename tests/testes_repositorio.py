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
    "demo-a/leituras.jsonl": "o que a sentença de cada pessoa diz",
    "demo-a/trocas_de_email.jsonl": "CPF e e-mails de troca pedida",
    "demo-a/dominios_confiados.txt": "os domínios de e-mail do sindicato",
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


def t_so_quem_opera_troca_o_email_de_quem_ja_entra():
    """Nenhuma ROTA alcança a troca de e-mail de quem já está no portão.

    A trava de T26 é esta: a planilha do gestor põe gente nova no acesso e
    PEDE a troca de quem já entra; quem faz a troca valer é a ferramenta de
    quem opera o servidor. Os testes de comportamento provam que a rota da
    planilha não troca. Este prova que não apareceu OUTRA rota que troque —
    que é como a trava se perde: alguém acha razoável um botão de "aprovar"
    no painel, e uma sessão de gestor volta a valer todas as contas.

    Conta as chamadas no código de produção. `trocar_email` tem um chamador
    (`trocas.aprovar`), e `aprovar` tem um (a ferramenta).
    """
    onde: dict[str, list[str]] = {"rol.trocar_email(": [],
                                  "trocas.aprovar(": [],
                                  "trocas.confiar_dominio(": []}
    for pasta in ("nucleo", "servidor", "ferramentas"):
        for caminho in sorted((RAIZ / pasta).rglob("*.py")):
            for n, linha in enumerate(
                caminho.read_text(encoding="utf-8").splitlines(), 1
            ):
                if linha.strip().startswith("#"):
                    continue
                for chamada in onde:
                    if chamada in linha:
                        onde[chamada].append(
                            str(caminho.relative_to(RAIZ)))
    checa(onde["rol.trocar_email("] == ["servidor/trocas.py"],
          f"`rol.trocar_email` tem de ter UM chamador, `trocas.aprovar`: "
          f"{onde['rol.trocar_email(']}")
    # CONFIAR NUM DOMÍNIO libera, de uma vez, todo mundo que esperava por
    # causa dele. Numa rota, seria a mesma sessão de gestor que mandou a
    # planilha se autorizando.
    checa(onde["trocas.confiar_dominio("]
          == ["ferramentas/trocas_de_email.py"],
          f"`trocas.confiar_dominio` só pode ser chamada pela ferramenta "
          f"de quem opera: {onde['trocas.confiar_dominio(']}")
    checa(onde["trocas.aprovar("] == ["ferramentas/trocas_de_email.py"],
          f"`trocas.aprovar` só pode ser chamada pela ferramenta de quem "
          f"opera, nunca por rota: {onde['trocas.aprovar(']}")


#: módulo que o código importa -> pacote que o `pip` instala, quando os
#: nomes diferem.
_PACOTE_DO_MODULO = {
    "multipart": "python-multipart",
    # O starlette é a base do fastapi e vem com ele, na versão que ele
    # exige: declará-lo à parte seria fixar uma versão contra a outra.
    "starlette": "fastapi",
}


def t_o_servidor_instala_tudo_o_que_importa():
    """`servidor/requirements.txt` é o que uma implantação instala. Tudo o
    que o servidor, o núcleo e as ferramentas que o agendador roda importam
    de fora da biblioteca padrão tem de estar lá.

    MEDIDO em 12/11/2026, num ambiente limpo: instalado só por esse arquivo,
    o servidor subia e respondia — e não tinha `psycopg`. O import do banco
    é tardio (dentro de função), então nada quebrava na subida: quebrava na
    primeira consulta. Com o banco fora o portão falha fechado, e ninguém
    recebe código. A suíte nunca viu isso porque roda no ambiente de quem
    desenvolve, onde tudo já está instalado.
    """
    import ast
    import sys

    declarados = set()
    for linha in (RAIZ / "servidor" / "requirements.txt").read_text(
            encoding="utf-8").splitlines():
        nome = linha.split("#")[0].strip()
        for corte in ("[", ">", "<", "=", "~", "!", " "):
            nome = nome.split(corte)[0]
        if nome:
            declarados.add(nome.lower())

    arquivos = sorted((RAIZ / "servidor").glob("*.py")) \
        + sorted((RAIZ / "nucleo").glob("*.py")) \
        + [RAIZ / "ferramentas" / f"{n}.py" for n in (
            "coletar_movimentacao", "avisar_movimentacao",
            "reavaliar_oportunidades", "avisar_pedidos", "trocas_de_email",
            "ingerir_acervo", "ingerir_documentos", "apagar_filiado")]
    locais = {"servidor", "nucleo", "ferramentas"}
    faltam: dict[str, str] = {}
    for caminho in arquivos:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                modulos = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0:
                modulos = [no.module or ""]
            else:
                continue
            for modulo in modulos:
                topo = modulo.split(".")[0]
                if (not topo or topo in locais
                        or topo in sys.stdlib_module_names):
                    continue
                pacote = _PACOTE_DO_MODULO.get(topo, topo).lower()
                if pacote not in declarados:
                    faltam.setdefault(pacote, str(caminho.relative_to(RAIZ)))
    checa(not faltam,
          f"importado e FORA de servidor/requirements.txt (uma implantação "
          f"não teria): {faltam}")


def _ambiente_de_exemplo() -> tuple[dict[str, str], set[str]]:
    """(variáveis definidas no exemplo, TODOS os nomes PROTOCOL_ que ele
    cita — inclusive os comentados em "nunca em produção")."""
    import re

    texto = (RAIZ / "implantacao" / "protocol.env.exemplo").read_text(
        encoding="utf-8")
    definidas: dict[str, str] = {}
    for linha in texto.splitlines():
        if linha.startswith("PROTOCOL_") and "=" in linha:
            nome, _, valor = linha.partition("=")
            definidas[nome] = valor
    return definidas, set(re.findall(r"PROTOCOL_[A-Z_]+[A-Z]", texto))


def t_o_ambiente_de_exemplo_e_o_que_o_servidor_le():
    """`implantacao/protocol.env.exemplo` é por onde alguém configura a
    produção. Variável que o servidor lê e o exemplo não cita é variável
    que ninguém vai definir; nome que o exemplo cita e o servidor não lê é
    configuração que parece valer e não vale — o mesmo engano que
    `config._PREFIXO_ERRADO` existe para denunciar.

    E PREENCHIDO, O EXEMPLO TEM DE BASTAR: o servidor sobe fora do modo
    ensaio, sem nenhum aviso de configuração faltando.
    """
    import re

    sys.path.insert(0, str(RAIZ))
    from servidor import config

    lidas = set(re.findall(
        r"PROTOCOL_[A-Z_]+[A-Z]",
        (RAIZ / "servidor" / "config.py").read_text(encoding="utf-8")))
    definidas, citadas = _ambiente_de_exemplo()
    checa(lidas - citadas == set(),
          f"o servidor lê e o exemplo de implantação não cita: "
          f"{sorted(lidas - citadas)}")
    checa(citadas - lidas == set(),
          f"o exemplo cita nome que o servidor NÃO lê: "
          f"{sorted(citadas - lidas)}")
    checa("PROTOCOL_MODO_ENSAIO" not in definidas
          and "PROTOCOL_SEMENTE_DEMO" not in definidas,
          "o exemplo de PRODUÇÃO liga o modo ensaio ou a semente de "
          "demonstração")
    for nome in ("PROTOCOL_SEGREDO", "PROTOCOL_DATABASE_URL",
                 "PROTOCOL_SMTP_SENHA"):
        checa(definidas.get(nome) == "",
              f"o exemplo traz valor em {nome}: segredo não mora no "
              f"repositório")

    preenchido = {k: v or "preenchido-na-maquina" for k, v in
                  definidas.items()}
    preenchido["PROTOCOL_EMAIL_DE_QUEM_OPERA"] = "nos@exemplo.invalid"
    # Vazio DE PROPÓSITO no exemplo: com o Caddy, quem entrega as páginas é
    # ele. Preenchido, teria de ser uma pasta de verdade.
    preenchido["PROTOCOL_PORTAL_ESTATICO"] = ""
    preenchido["PROTOCOL_DATABASE_URL"] = "postgresql://exemplo.invalid/x"
    try:
        cfg = config.carregar(preenchido)
    except config.ConfiguracaoInvalida as e:
        checa(False, f"o exemplo, preenchido, não sobe: {e}")
        return
    checa(not cfg.modo_ensaio and cfg.tem_banco and cfg.tem_remetente
          and cfg.avisos == (),
          f"o exemplo, preenchido, sobe com aviso de coisa faltando: "
          f"{cfg.avisos}")


def t_os_caminhos_da_implantacao_concordam():
    """O serviço, o Caddy, a cópia e o passo a passo falam dos MESMOS
    lugares. Um caminho diferente num dos quatro só aparece na máquina, no
    dia de subir."""
    pasta = RAIZ / "implantacao"
    servico = (pasta / "protocol.service").read_text(encoding="utf-8")
    caddy = (pasta / "Caddyfile").read_text(encoding="utf-8")
    copia = (pasta / "protocol-copia.service").read_text(encoding="utf-8")
    passo = (pasta / "LEIAME.md").read_text(encoding="utf-8")
    definidas, _ = _ambiente_de_exemplo()
    raiz_de_dados = definidas["PROTOCOL_RAIZ"]
    checa(f"ReadWritePaths={raiz_de_dados}" in servico,
          "o serviço não deixa o servidor escrever na raiz de dados do "
          "exemplo de ambiente")
    checa(f" {raiz_de_dados} " in copia,
          "a cópia diária não copia a raiz de dados do exemplo de ambiente")
    checa("--porta 8000" in servico and "127.0.0.1:8000" in caddy,
          "o Caddy e o serviço discordam da porta")
    checa("--host 127.0.0.1" in servico
          and definidas["PROTOCOL_PROXIES_CONFIAVEIS"] == "127.0.0.1",
          "o servidor tem de escutar só em 127.0.0.1 e confiar só no Caddy "
          "local")
    for caminho in ("/srv/protocol/app", "/srv/protocol/venv",
                    "/srv/protocol/portal", "/etc/protocol/protocol.env",
                    raiz_de_dados, "/var/backups/protocol"):
        checa(caminho in passo,
              f"o passo a passo não cria nem cita {caminho}")
    # `source` no arquivo de ambiente parte a URL do banco no `&` — visto
    # ao ensaiar esta pasta. O passo a passo não pode ensinar isso.
    checa("com-ambiente.sh" in passo
          and "\nsource " not in passo and "\n. /etc/protocol" not in passo,
          "o passo a passo carrega o ambiente com `source`, ou não usa "
          "`com-ambiente.sh`")
    # Só as DATADAS são migração. `conferir_*.sql` mora na mesma pasta e é
    # consulta de conferência — não muda nada, e não é para "aplicar".
    migracoes = sorted(p.name for p in
                       (RAIZ / "servidor" / "migracoes").glob("[0-9]*.sql"))
    checa(len(migracoes) >= 2, f"não achei as migrações datadas: {migracoes}")
    checa("conferir_forma.sql" in passo,
          "o passo a passo não manda CONFERIR a forma do banco depois de "
          "migrar")
    checa(all(m in passo for m in migracoes),
          f"o passo a passo não manda aplicar todas as migrações: "
          f"{migracoes}")


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
    ("só quem opera troca o e-mail de quem já entra",
     t_so_quem_opera_troca_o_email_de_quem_ja_entra),
    ("o servidor instala tudo o que importa",
     t_o_servidor_instala_tudo_o_que_importa),
    ("o ambiente de exemplo é o que o servidor lê",
     t_o_ambiente_de_exemplo_e_o_que_o_servidor_le),
    ("os caminhos da implantação concordam",
     t_os_caminhos_da_implantacao_concordam),
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
