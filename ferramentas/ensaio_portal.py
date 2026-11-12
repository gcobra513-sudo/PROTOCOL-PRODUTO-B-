#!/usr/bin/env python3
"""O ensaio de navegador, ponta a ponta: Chromium de verdade.

ESTE ARQUIVO ESTAVA PROMETIDO E NÃO EXISTIA. Até 02/11/2026 o
`servidor/LEIAME.md` mandava rodá-lo e descrevia em detalhe o que ele fazia
— sete etapas num Chromium, cinco PDFs, o protocolo lido na tela. Nunca
existiu em commit nenhum. Estava escrito, então passava por verificado: a
mesma doença que a auditoria achou sete vezes nos comentários do código,
um andar acima.

O QUE SÓ ELE PEGA. Os testes do servidor provam o que ele ACEITA. Os do
portal provam o que a tela DIZ. Entre os dois mora a classe de defeito que
nenhum dos dois alcança: **o navegador mandando um nome de campo que o
servidor não espera** — e ela não dá erro, dá campo vazio no disco.

O QUE ELE FAZ:

1. semeia uma entidade de demonstração num diretório temporário, com rol de
   filiados e de gestores, todos CADASTROS DECLARADAMENTE FICTÍCIOS;
2. gera cinco documentos dos três jeitos que chegam na vida real: PDF com
   camada de texto, PDF de SCANNER e FOTO (JPG). Os dois últimos eram
   recusados; hoje entram e ficam aguardando leitura humana, e a foto é
   embrulhada num PDF pelo próprio navegador;
3. compila o portal apontando para um servidor em MODO ENSAIO;
4. sobe o servidor e um servidor estático para o portal compilado;
5. dirige o Chromium: entra pelo portão lendo o código NA TELA, preenche as
   etapas, anexa os PDFs, envia e lê o protocolo na tela;
6. CONFERE O DISCO do lado de fora do navegador — a entrega, o diário e o
   manifesto — e, quando há banco: o gestor ABRE a sentença de scanner na
   fila de leitura, registra o que leu, e a fila esvazia; depois apaga o
   filiado pelo painel e mede que não sobrou nada — nem as leituras.

Sai 0 se tudo isso aconteceu, 1 se não, e diz o que falhou.

    python3 ferramentas/ensaio_portal.py
    PROTOCOL_DATABASE_URL='postgresql://...' python3 ferramentas/ensaio_portal.py

SEM `PROTOCOL_DATABASE_URL` a metade do apagamento é PULADA, e o resumo diz
isso. Metade pulada não está ensaiada.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RAIZ_DO_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_DO_REPO))

# CPFs SINTÉTICOS, com dígito verificador válido e declarados como exemplo.
# Nome plausível com CPF válido numa página é indistinguível de pessoa real;
# o rótulo no nome é o que mantém a distinção visível a quem olhar a tela.
CPF_FILIADO = "111.444.777-35"
CPF_GESTOR = "529.982.247-25"
NOME_FILIADO = "FULANA DE TAL (CADASTRO DE EXEMPLO)"
#: Quem entra pela PLANILHA do sindicato, e nunca passou pelo portal.
CPF_DA_PLANILHA = "390.533.447-05"
NOME_DA_PLANILHA = "BELTRANO DE TAL (CADASTRO DE EXEMPLO)"
#: Quem JÁ entra no portal e aparece na planilha com OUTRO e-mail. É a
#: trava de T26: a troca fica pedida, e o código continua indo para o de
#: antes.
CPF_DA_TROCA = "862.883.667-57"
NOME_DA_TROCA = "SICRANA DE TAL (CADASTRO DE EXEMPLO)"
EMAIL_DE_ANTES = "sicrana@exemplo.invalid"
EMAIL_DA_PLANILHA = "outro-endereco@exemplo.invalid"
SEGREDO_DO_ENSAIO = "segredo-do-ensaio-de-navegador"

#: UMA ENTIDADE NOVA POR EXECUÇÃO, e isto foi um defeito que o próprio
#: ensaio pegou em mim. A raiz de dados é temporária, mas o BANCO é
#: compartilhado com a suíte — e a metade do apagamento grava um
#: **tombstone**, que a aplicação não pode apagar (o GRANT nega DELETE, de
#: propósito). Com apelido fixo, o tombstone da execução anterior ficava no
#: banco e o portão passava a recusar o código: o ensaio funcionava uma vez
#: e nunca mais. O prefixo `demo-` continua, porque é ele que dispensa a
#: trava de região.
APELIDO = f"demo-ensaio-{os.getpid()}-{int(time.time())}"


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _esperar(url: str, segundos: float = 40.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except urllib.error.HTTPError:
            return True          # respondeu, mesmo que com 4xx: está no ar
        except Exception:
            time.sleep(0.3)
    return False


def _pdf(linhas: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    import io

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        c.drawString(60, y, linha)
        y -= 16
    c.save()
    return buffer.getvalue()


def _semear(raiz: pathlib.Path) -> None:
    import csv

    from servidor import entidades

    ent = entidades.Cadastro(raiz).criar(APELIDO, "Sindicato de Demonstração")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, linhas in (
        ("filiados.csv", [(CPF_FILIADO, "filiada@exemplo.invalid"),
                          (CPF_GESTOR, "gestor@exemplo.invalid"),
                          (CPF_DA_TROCA, EMAIL_DE_ANTES)]),
        ("gestores.csv", [(CPF_GESTOR, "gestor@exemplo.invalid")]),
    ):
        with open(pasta / nome, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cpf", "email"])
            w.writerows(linhas)
    # O DOMÍNIO DO SINDICATO, CONFIADO POR QUEM OPERA. Todos os cadastros
    # do ensaio estão em `exemplo.invalid`, como os filiados de um sindicato
    # de verdade estão no domínio da repartição — e, fora dos provedores
    # comuns, um domínio só recebe três pessoas sem conferência. Sem esta
    # linha a pessoa da planilha ficaria esperando (foi o que o ensaio
    # mostrou quando a regra entrou). É o passo que nós damos uma vez por
    # sindicato: `ferramentas/trocas_de_email.py ... confiar <domínio>`.
    from servidor import trocas

    (pasta / trocas.ARQUIVO_DE_DOMINIOS).write_text("exemplo.invalid\n",
                                                    encoding="utf-8")


def _pdf_de_scanner() -> bytes:
    """Um PDF sem camada de texto: o que sai de um scanner."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    import io

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.rect(80, 500, 420, 240, fill=1)
    c.save()
    return buffer.getvalue()


def _foto(caminho: pathlib.Path) -> None:
    """Uma FOTO de verdade, em JPEG, como a que sai de um celular.

    Pillow vem com o reportlab, que este ensaio já exige. A imagem é um
    "papel" branco com linhas escuras — fictícia, e sem dado de ninguém.
    """
    from PIL import Image, ImageDraw

    imagem = Image.new("RGB", (1600, 1200), "white")
    desenho = ImageDraw.Draw(imagem)
    desenho.text((80, 60), "COMPROVANTE DE EXEMPLO (FOTO FICTICIA)",
                 fill="black")
    for y in range(160, 1100, 60):
        desenho.line((80, y, 1500, y), fill=(60, 60, 60), width=3)
    imagem.save(caminho, "JPEG", quality=88)


def _pdfs(pasta: pathlib.Path) -> list[tuple[str, list[str]]]:
    """Cinco documentos, dos TRÊS jeitos que chegam na vida real.

        2 comprovantes   PDF com camada de texto — a máquina lê
        1 comprovante    FOTO (JPG) — o navegador embrulha num PDF
        a sentença       PDF de SCANNER — entra, e fica aguardando leitura
        a certidão       PDF com camada de texto

    A foto e o scanner estão aqui porque eram RECUSADOS: o cadastro inteiro
    caía com 422. A decisão de 10/11/2026 foi aceitar e marcar, e este é o
    único lugar que prova a foto de ponta a ponta — o canvas que a converte
    só existe em navegador.

    Devolve [(rótulo na tela, caminhos)].
    """
    pasta.mkdir(parents=True, exist_ok=True)
    contribuicoes = []
    for ano in (2022, 2023):
        caminho = pasta / f"contribuicao-{ano}.pdf"
        caminho.write_bytes(_pdf([
            "COMPROVANTE DE CONTRIBUICAO SINDICAL (DOCUMENTO DE EXEMPLO)",
            f"Exercicio: {ano}",
            f"Filiado: {NOME_FILIADO}",
            f"CPF: {CPF_FILIADO}",
            "Este documento e ficticio e serve apenas ao ensaio automatizado.",
        ]))
        contribuicoes.append(str(caminho))
    foto = pasta / "comprovante-fotografado.jpg"
    _foto(foto)
    contribuicoes.append(str(foto))

    sentenca = pasta / "sentenca-escaneada.pdf"
    sentenca.write_bytes(_pdf_de_scanner())
    certidao = pasta / "certidao.pdf"
    certidao.write_bytes(_pdf([
        "CERTIDAO DE TRANSITO EM JULGADO (DOCUMENTO DE EXEMPLO)",
        f"Interessado: {NOME_FILIADO} - CPF {CPF_FILIADO}",
        "Certifico o transito em julgado. Documento ficticio de ensaio.",
    ]))
    return [
        ("Comprovantes de contribuição ao sindicato", contribuicoes),
        ("Sentença, se você tiver", [str(sentenca)]),
        ("Certidão de trânsito em julgado, se você tiver", [str(certidao)]),
    ]


def _planilha_xlsx(caminho: pathlib.Path) -> None:
    """A planilha do sindicato em .XLSX, que é o que ele tem de verdade — e
    com o CPF guardado como NÚMERO, que é como o Excel o guarda quando
    ninguém formata a coluna."""
    import openpyxl

    livro = openpyxl.Workbook()
    folha = livro.active
    folha.append(["CPF", "Nome Completo", "E-mail", "Cargo"])
    folha.append([int("".join(c for c in CPF_DA_PLANILHA if c.isdigit())),
                  NOME_DA_PLANILHA, "beltrano@exemplo.invalid",
                  "Auditor Fiscal da Receita Federal"])
    folha.append([CPF_DA_TROCA, NOME_DA_TROCA, EMAIL_DA_PLANILHA,
                  "Auditor Fiscal da Receita Federal"])
    livro.save(caminho)


def _compilar_portal(api: str, destino: pathlib.Path) -> None:
    ambiente = {**os.environ, "VITE_API": api}
    r = subprocess.run(
        ["npx", "vite", "build", "--outDir", str(destino), "--emptyOutDir"],
        cwd=RAIZ_DO_REPO / "portal", env=ambiente,
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"a compilação do portal falhou:\n{r.stdout}\n{r.stderr}")


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--manter", action="store_true",
                   help="não apaga o diretório temporário no fim")
    p.add_argument("--verboso", action="store_true",
                   help="imprime cada passo do navegador enquanto acontece")
    args = p.parse_args()

    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("openpyxl não está instalado, e sem ele não há planilha .xlsx "
              "para o gestor enviar", file=sys.stderr)
        return 2
    for exigido in ("npx", "node"):
        if not shutil.which(exigido):
            print(f"{exigido} não está nesta máquina, e o ensaio precisa dele",
                  file=sys.stderr)
            return 2
    try:
        import reportlab  # noqa: F401
    except ImportError:
        print("reportlab não está instalado, e sem ele não há PDF com camada "
              "de texto para anexar", file=sys.stderr)
        return 2

    banco_url = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()
    raiz = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-portal-"))
    dist = raiz / "dist"
    porta_api, porta_web = _porta_livre(), _porta_livre()
    api = f"http://127.0.0.1:{porta_api}"
    web = f"http://127.0.0.1:{porta_web}"
    processos: list[subprocess.Popen] = []
    falhas: list[str] = []
    log_do_servidor: pathlib.Path | None = None

    print("ENSAIO DE NAVEGADOR — portal do filiado, ponta a ponta")
    print(f"  dados em {raiz}")
    print(f"  api {api}   portal {web}")
    try:
        _semear(raiz)
        documentos = _pdfs(raiz / "pdfs")
        _planilha_xlsx(raiz / "pdfs" / "base-do-sindicato.xlsx")
        print(f"  {sum(len(d[1]) for d in documentos)} documentos: 3 PDFs com "
              f"texto, 1 de scanner, 1 foto")

        print("  compilando o portal…")
        _compilar_portal(api, dist)

        ambiente = {
            **os.environ,
            "PROTOCOL_MODO_ENSAIO": "1",
            # SEGREDO FIXO, e não o gerado na hora pelo modo ensaio: a
            # conferência de fora do navegador precisa recalcular o marcador
            # do CPF (HMAC do segredo) para medir o portão. Com segredo
            # sorteado, `vestigios` mediria o marcador de outra pessoa — ou
            # seja, mediria zero sempre, que é o pior resultado possível
            # para uma medição.
            "PROTOCOL_SEGREDO": SEGREDO_DO_ENSAIO,
            "PROTOCOL_RAIZ": str(raiz),
            "PROTOCOL_ORIGENS": web,
            "PROTOCOL_EMISSOES_POR_CPF_HORA": "50",
            "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": "200",
        }
        if banco_url:
            ambiente["PROTOCOL_DATABASE_URL"] = banco_url
        # O LOG DO SERVIDOR VAI PARA ARQUIVO, não para um cano. Num cano
        # ele só pode ser lido matando o processo, e é justamente quando o
        # ensaio falha que ele precisa ser lido com o servidor ainda vivo —
        # a causa costuma estar nele, não na tela.
        log_do_servidor = raiz / "servidor.log"
        with open(log_do_servidor, "w") as fh:
            processos.append(subprocess.Popen(
                [sys.executable, "-m", "servidor", "--porta", str(porta_api)],
                cwd=RAIZ_DO_REPO, env=ambiente,
                stdout=fh, stderr=subprocess.STDOUT, text=True,
            ))
        processos.append(subprocess.Popen(
            [sys.executable, "-m", "http.server", str(porta_web),
             "--bind", "127.0.0.1", "--directory", str(dist)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        if not _esperar(f"{api}/saude"):
            raise RuntimeError(
                "o servidor não subiu:\n"
                + log_do_servidor.read_text(errors="replace")[-2000:]
            )
        if not _esperar(web):
            raise RuntimeError("o portal compilado não está sendo servido")
        print("  servidor e portal no ar")

        cfg = {
            "web": web, "api": api, "entidade": APELIDO, "saida": str(raiz),
            "verboso": args.verboso,
            "documentos": documentos,
            "filiado": {
                "cpf": CPF_FILIADO, "nome": NOME_FILIADO,
                "email": "filiada@exemplo.invalid",
                "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
                "filiadoDesde": "2004-03",
            },
            "gestor": {"cpf": CPF_GESTOR},
            "planilha": {"caminho": str(raiz / "pdfs" / "base-do-sindicato.xlsx"),
                         "nome": NOME_DA_PLANILHA,
                         "cpf": CPF_DA_PLANILHA},
            "fazerPainel": bool(banco_url),
            # O computador da sede: duas pessoas no MESMO navegador.
            "sede": {
                "primeira": {"cpf": CPF_DA_TROCA, "nome": NOME_DA_TROCA,
                             "email": EMAIL_DE_ANTES},
                "segunda": {"cpf": CPF_FILIADO},
            },
        }
        # UMA CHAMADA POR FASE, e a ORDEM é o que importa: o cadastro
        # grava, a conferência lê o disco, e só então o painel apaga. Numa
        # chamada só, a conferência do cadastro rodaria depois do
        # apagamento e acharia tudo vazio — e foi exatamente esse o
        # primeiro defeito que este ensaio pegou. Era meu.
        # ANTES DE TUDO, o computador da sede — e antes do cadastro porque
        # nada aqui é enviado: são duas pessoas no mesmo navegador, e o que
        # se mede é o que uma deixa para a outra.
        print("  dirigindo o Chromium — o computador da sede…")
        da_sede = _dirigir(cfg, "sede", falhas)
        if not falhas:
            falhas += _conferir_a_sede(da_sede.get("sede"))
        if not falhas:
            da_volta = _dirigir(cfg, "volta", falhas)
            if not falhas and (da_volta.get("volta") or {}).get(
                    "nomeRecuperado") != NOME_DA_TROCA:
                falhas.append(
                    "a DONA do rascunho voltou, passou pelo portão e não "
                    "reencontrou o que tinha digitado: "
                    f"{(da_volta.get('volta') or {}).get('nomeRecuperado')!r}")
            if not falhas and (da_volta.get("volta") or {}).get(
                    "sobrouAoSair"):
                falhas.append(
                    "\"Sair e apagar\" deixou dado da pessoa na tela ou no "
                    "navegador")

        print("  dirigindo o Chromium — o filiado…")
        dados = _dirigir(cfg, "cadastro", falhas)
        protocolo = dados.get("protocolo", "")
        if protocolo:
            falhas += _conferir_o_disco(raiz, protocolo)
            if not dados.get("avisouImagem"):
                falhas.append(
                    "a tela do recibo não avisou que dois documentos "
                    "chegaram como imagem e vão ser lidos por uma pessoa"
                )

        if banco_url and not falhas:
            print("  dirigindo o Chromium — o gestor lê a fila…")
            da_fila = _dirigir(cfg, "conferencia", falhas)
            if not falhas:
                falhas += _conferir_a_leitura(raiz, banco_url,
                                              da_fila.get("conferencia"))
                falhas += _conferir_a_lista(da_fila.get("lista"))
                falhas += _conferir_a_planilha(raiz, da_fila.get("planilha"),
                                               da_fila.get("lista"))

        if banco_url and not falhas:
            print("  dirigindo o Chromium — o gestor…")
            do_painel = _dirigir(cfg, "painel", falhas)
            falhas += _conferir_o_apagamento(raiz, banco_url,
                                             do_painel.get("apagamento"))
        elif banco_url:
            print("  o apagamento pelo painel não foi ensaiado: o cadastro "
                  "já falhou, e apagar o que não entrou certo não mede nada")
    except Exception as e:  # noqa: BLE001
        falhas.append(str(e))
    finally:
        for proc in processos:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=10)
        # LIDO ANTES DA LIMPEZA. A primeira versão lia depois, e o arquivo
        # já tinha ido junto com o diretório temporário — um diagnóstico
        # que só existia quando não era preciso.
        if falhas and log_do_servidor and log_do_servidor.is_file():
            cauda = [l for l in log_do_servidor.read_text(errors="replace")
                     .splitlines() if l.strip()][-14:]
            if cauda:
                print("\n  o servidor disse:")
                for linha in cauda:
                    print(f"    {linha}")
        if args.manter:
            print(f"\n  o diretório ficou em {raiz}")
        else:
            shutil.rmtree(raiz, ignore_errors=True)

    print()
    if falhas:
        print(f"ENSAIO FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    if not banco_url:
        print("ENSAIO PASSOU — mas SEM BANCO: a metade do apagamento pelo "
              "painel foi PULADA, e metade pulada não está ensaiada.")
        return 0
    print("ENSAIO PASSOU, inteiro.")
    return 0


def _dirigir(cfg: dict, fase: str, falhas: list[str]) -> dict:
    """Roda uma fase do condutor e devolve o que ele mediu.

    Erro de console do navegador CONTA COMO FALHA. Num React, "funcionou
    mas gritou" é um defeito que a pessoa vê como tela em branco meia hora
    depois, e que nenhuma asserção de unidade alcança.
    """
    r = subprocess.run(
        ["node", str(RAIZ_DO_REPO / "ferramentas" / "ensaio" / "portal.cjs"),
         json.dumps({**cfg, "fase": fase})],
        capture_output=True, text=True, timeout=600,
    )
    if "<<<ENSAIO>>>" not in r.stdout:
        raise RuntimeError(
            f"o condutor não devolveu resultado na fase {fase}:\n"
            f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
        )
    dados = json.loads(r.stdout.split("<<<ENSAIO>>>")[1].split("<<<FIM>>>")[0])
    for passo in dados.get("passos", []):
        print(f"    · {passo}")
    if dados.get("gritos"):
        falhas.append("o navegador gritou no console: "
                      + " | ".join(dados["gritos"][:5]))
    if dados.get("falha"):
        f = dados["falha"]
        falhas.append(f"o navegador parou na fase {fase}: {f.get('erro')}")
        if f.get("visivel"):
            print("\n  o que estava na tela:\n    "
                  + f["visivel"][:800].replace("\n", "\n    "))
        for chave in ("imagem", "html"):
            if f.get(chave):
                print(f"  {chave}: {f[chave]}")
    return dados


def _conferir_o_disco(raiz: pathlib.Path, protocolo: str) -> list[str]:
    """A conferência do lado de fora do navegador.

    É AQUI QUE O ENSAIO GANHA O SALÁRIO. A tela dizendo "enviado" prova que
    o React chegou ao fim; só o disco prova que o que chegou ao servidor foi
    o que a pessoa digitou. Campo com nome errado não dá erro — dá campo
    vazio no diário, e a tela continua dizendo "enviado".
    """
    from servidor import deposito, entidades, validacao

    problemas: list[str] = []
    ent = entidades.Cadastro(raiz).resolver(APELIDO)
    pasta = ent.pasta(raiz)
    digitos = validacao.so_digitos(CPF_FILIADO)

    diario = deposito.ler_diario(pasta)
    meus = [r for r in diario if r.get("protocolo") == protocolo]
    if not meus:
        return [f"o protocolo {protocolo} que a TELA mostrou não está no "
                f"diário ({len(diario)} registro(s))"]
    linha = meus[0].get("linha") or {}

    esperado = {
        "cpf": digitos,
        "nome_completo": NOME_FILIADO,
        "email": "filiada@exemplo.invalid",
        "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
        "situacao": "aposentado",
        "filiado_desde": "2004-03",
    }
    for campo, valor in esperado.items():
        veio = str(linha.get(campo, "")).strip()
        if campo == "cpf":
            veio = validacao.so_digitos(veio)
        if veio != valor:
            problemas.append(
                f"o campo {campo!r} chegou ao diário como {veio!r} e a tela "
                f"mandou {valor!r} — é o defeito que só este ensaio pega"
            )

    entrega = ent.entrega(raiz) / digitos
    pdfs = sorted(x.name for x in entrega.glob("*.pdf")) if entrega.is_dir() else []
    if len(pdfs) != 5:
        problemas.append(f"anexei 5 PDFs e chegaram {len(pdfs)}: {pdfs}")

    # A FOTO E O SCANNER. O navegador mandou uma foto JPG; o que tem de
    # estar no disco é um PDF, que ABRE, e que o diário marca como
    # aguardando leitura — junto com a sentença de scanner.
    esperando = sorted(meus[0].get("aguardando_leitura") or [])
    if esperando != ["contribuicao-3.pdf", "sentenca.pdf"]:
        problemas.append(
            f"o diário devia marcar a foto e o scanner como aguardando "
            f"leitura, e marcou {esperando}"
        )
    da_foto = entrega / "contribuicao-3.pdf"
    if da_foto.is_file():
        try:
            from pypdf import PdfReader

            leitor = PdfReader(str(da_foto))
            pagina = leitor.pages[0]
            imagens = pagina.get("/Resources", {}).get("/XObject", {})
            if len(leitor.pages) != 1 or not imagens:
                problemas.append(
                    "a foto chegou, mas o PDF não tem uma página com a imagem"
                )
        except Exception as e:  # noqa: BLE001
            problemas.append(
                f"a foto virou um PDF que NÃO ABRE no servidor: {e}"
            )
    else:
        problemas.append("a foto não chegou ao disco como contribuicao-3.pdf")

    manifesto = ent.entrega(raiz) / deposito.MANIFESTO
    if not manifesto.is_file():
        problemas.append("o manifesto não foi gerado")
    elif digitos not in manifesto.read_text(encoding="utf-8"):
        problemas.append("o manifesto não tem a linha deste CPF")
    return problemas


def _conferir_a_leitura(raiz: pathlib.Path, url: str, na_tela) -> list[str]:
    """O que o gestor registrou NA TELA contra o arquivo de leituras e o
    banco. A fila tinha a foto e a sentença de scanner; depois de ele ler as
    duas, o arquivo tem os dois registros COM AUTOR e a fila está vazia."""
    from servidor import banco, conferencia, entidades

    if not na_tela or not na_tela.get("abriu"):
        return ["o gestor não conseguiu abrir o documento da fila"]
    problemas: list[str] = []
    ent = entidades.Cadastro(raiz).resolver(APELIDO)
    registros = conferencia.ler(ent.pasta(raiz))
    por_tipo = {r.get("tipo"): r for r in registros}
    if (por_tipo.get("sentenca") or {}).get("fatos") != {
            "dispositivo": "procedente"}:
        problemas.append(
            f"a leitura da sentença não chegou como o gestor registrou: "
            f"{(por_tipo.get('sentenca') or {}).get('fatos')}"
        )
    if (por_tipo.get("contribuicao") or {}).get("fatos") != {
            "periodo": "2022-01/2022-12"}:
        problemas.append(
            f"a leitura do comprovante não chegou como o gestor registrou: "
            f"{(por_tipo.get('contribuicao') or {}).get('fatos')}"
        )
    if not all(r.get("quem") for r in registros) or len(registros) != 2:
        problemas.append(f"esperava 2 leituras com autor, há {len(registros)}")
    if banco.aguardando_leitura(url, APELIDO) != (0, 0):
        problemas.append(
            f"o gestor leu tudo e a fila não esvaziou: "
            f"{banco.aguardando_leitura(url, APELIDO)}"
        )
    return problemas


def _conferir_a_lista(da_tela) -> list[str]:
    """A lista "nome por nome" e a planilha que o gestor BAIXOU.

    Confere o arquivo como o navegador o recebeu: é ele que o sindicato leva
    para os sistemas dele. Na tela o CPF vem mascarado; na planilha, inteiro.
    """
    from servidor import validacao

    if not da_tela:
        return ["o gestor não chegou à lista nome por nome"]
    problemas: list[str] = []
    digitos = validacao.so_digitos(CPF_FILIADO)
    if not da_tela.get("viuNome"):
        problemas.append("a lista não mostrou o nome de quem se cadastrou")
    if da_tela.get("cpfInteiroNaTela"):
        problemas.append("a TELA mostrou o CPF inteiro; ele só sai na planilha")
    planilha = da_tela.get("planilha") or ""
    if not planilha.startswith("\ufeff"):
        problemas.append("a planilha baixada não tem a marca de UTF-8")
    linhas = planilha.lstrip("\ufeff").split("\r\n")
    if not linhas[0].startswith("cpf;nome;"):
        problemas.append(f"cabeçalho inesperado na planilha: {linhas[0][:60]!r}")
    if not any(l.startswith(f"{digitos};{NOME_FILIADO};") for l in linhas):
        problemas.append("a planilha baixada não traz a pessoa, com CPF e nome")
    return problemas


def _conferir_a_planilha(raiz: pathlib.Path, enviada, lista) -> list[str]:
    """A planilha que o gestor mandou pelo navegador, conferida no disco.

    O arquivo de acervo tem de registrar QUEM enviou, e a pessoa da
    planilha — que nunca passou pelo portal — tem de estar na base que o
    gestor baixou, com o CPF que o Excel guardava como número.
    """
    from servidor import entidades, validacao

    if not enviada or not enviada.get("gravou"):
        return ["o gestor não conseguiu enviar a planilha pelo painel"]
    problemas: list[str] = []
    ent = entidades.Cadastro(raiz).resolver(APELIDO)
    acervo_ = ent.pasta(raiz) / "acervo.jsonl"
    if not acervo_.is_file():
        return ["a planilha confirmada não gravou o acervo"]
    registro = json.loads(acervo_.read_text(encoding="utf-8").splitlines()[-1])
    if not registro.get("enviado_por"):
        problemas.append("o acervo não registra quem enviou a planilha")
    problemas += _conferir_o_acesso(ent.pasta(raiz), enviada)
    digitos = validacao.so_digitos(CPF_DA_PLANILHA)
    baixada = (lista or {}).get("planilha") or ""
    if f"{digitos};{NOME_DA_PLANILHA};" not in baixada:
        problemas.append(
            "quem entrou pela planilha .xlsx não está na base que o gestor "
            "baixou — ou o CPF guardado como número chegou torto"
        )
    return problemas


def _conferir_a_sede(da_tela) -> list[str]:
    """T23, medido no navegador: o que a segunda pessoa do computador da
    sede encontra da primeira.

    Três momentos, e os três têm de vir vazios: antes de ela se
    identificar (a tela não sabe quem é, então não mostra o que é de
    ninguém), depois de ela entrar com o CPF dela, e no que ficou guardado
    no navegador — onde o próximo curioso olharia.
    """
    if not da_tela:
        return ["o ensaio do computador da sede não rodou"]
    problemas = []
    if da_tela.get("caiuDentroDoCadastro"):
        problemas.append(
            "NO COMPUTADOR DA SEDE a segunda pessoa abriu o portal e caiu "
            "DENTRO do cadastro da primeira, sem passar pelo portão")
    for chave, quando in (
        ("vazouAntesDoPortao", "ANTES de se identificar"),
        ("vazouDepoisDoPortao", "DEPOIS de entrar com o CPF dela"),
        ("ficouNoNavegador", "guardado no navegador, depois de ela entrar"),
    ):
        if da_tela.get(chave):
            problemas.append(
                f"NO COMPUTADOR DA SEDE a segunda pessoa encontrou, {quando}, "
                f"{len(da_tela[chave])} dado(s) da primeira (nome, CPF ou "
                f"e-mail)")
    return problemas


def _conferir_o_acesso(pasta: pathlib.Path, enviada: dict) -> list[str]:
    """T26, conferido dos dois lados: na TELA e no DISCO.

    Na tela: quem veio só pela planilha ENTROU pelo portão, num navegador
    limpo; e o gestor leu que a troca de e-mail não vale por ali.

    No disco: o rol ganhou a pessoa nova, o e-mail de quem já entrava NÃO
    mudou, e a troca está na fila de quem opera. A tela dizer "não vale" com
    o rol já trocado seria o pior resultado possível — e só o disco mostra.
    """
    from servidor import rol, trocas, validacao

    problemas: list[str] = []
    if not enviada.get("novaEntrou"):
        problemas.append("quem veio só pela planilha do gestor NÃO conseguiu "
                         "entrar no portal")
    tela = (enviada.get("acesso") or "").lower()
    if "já pode entrar" not in tela:
        problemas.append("o painel não disse que a pessoa nova já pode entrar")
    if "não vale" not in tela or "e-mail de antes" not in tela:
        problemas.append("o painel não disse que a troca de e-mail NÃO vale "
                         "pela planilha")
    lista = rol.carregar(pasta)
    nova = validacao.so_digitos(CPF_DA_PLANILHA)
    antiga = validacao.so_digitos(CPF_DA_TROCA)
    if lista.email_de(nova) != "beltrano@exemplo.invalid":
        problemas.append("a pessoa nova da planilha não entrou no rol")
    if lista.email_de(antiga) != EMAIL_DE_ANTES:
        problemas.append("A PLANILHA TROCOU O E-MAIL DE QUEM JÁ ENTRAVA: o "
                         f"rol diz {lista.email_de(antiga)!r}")
    pedido = trocas.estado(pasta).pendentes.get(antiga)
    if not pedido or pedido.get("para") != EMAIL_DA_PLANILHA:
        problemas.append("a troca de e-mail pedida não ficou na fila de "
                         "quem opera")
    return problemas


def _conferir_o_apagamento(raiz: pathlib.Path, url: str,
                           apagamento_na_tela) -> list[str]:
    """O que a TELA disse contra o que o DISCO E O BANCO dizem.

    A tela afirmando "nada sobrou" é a afirmação do servidor repetida pelo
    React. Quem mede é esta função, de fora dos dois: ela chama a mesma
    varredura que a ferramenta de linha de comando chama, com o portão de
    verdade, e exige lista vazia.
    """
    from servidor import acesso, apagamento, entidades

    if not apagamento_na_tela:
        return ["o navegador não chegou a apagar ninguém pelo painel"]
    if apagamento_na_tela.get("disse") != "nada sobrou":
        return [f"o painel disse {apagamento_na_tela.get('disse')!r} em vez "
                f"de que terminou"]

    problemas: list[str] = []
    ent = entidades.Cadastro(raiz).resolver(APELIDO)
    portao = acesso.Portao(raiz, SEGREDO_DO_ENSAIO)
    sobrou = apagamento.vestigios(url, ent, raiz, CPF_FILIADO, portao=portao)
    if sobrou:
        problemas.append(
            "a tela disse que nada sobrou e a medição achou "
            f"{len(sobrou)}: " + "; ".join(sobrou[:6])
        )
    # E o vizinho NÃO foi levado junto: o gestor continua no rol e no portão.
    if not apagamento.vestigios(url, ent, raiz, CPF_GESTOR, portao=portao):
        problemas.append(
            "o apagamento levou o gestor junto, ou o rol dele desapareceu — "
            "quem não pediu para sair tem de continuar lá"
        )
    return problemas


if __name__ == "__main__":
    raise SystemExit(main())
