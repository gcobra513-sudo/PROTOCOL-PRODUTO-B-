"""
O rol de filiados que a entidade entrega, e por que ele é obrigatório.

O PORTÃO SÓ É PORTÃO SE O E-MAIL NÃO FOR ESCOLHIDO POR QUEM ENTRA.

A tentação é pedir CPF e e-mail na tela e mandar o código para o e-mail
digitado. Isso não confere nada: eu digito o CPF de outra pessoa, ponho o meu
e-mail, recebo o código e entrego os meus documentos no nome dela — ou, pior,
vejo o cadastro dela. O código viraria enfeite.

Então o código vai para o e-mail **que o sindicato tem em cadastro**. Quem não
está no rol não entra, e isso é resposta certa: o portal atende filiados de uma
entidade que contratou o serviço, não o público. É o que o modelo por sindicato
dá de graça, e é por isso que ele é mais seguro, não só mais defensável.

CONSEQUÊNCIA ASSUMIDA: sem `filiados.csv` nenhum FILIADO recebe código. O
servidor diz isso com todas as letras em vez de deixar passar. Um portão que
abre para todos é pior que um portão fechado, porque parece que existe.

(O GESTOR recebe, desde que a planilha dele passou a criar este arquivo: sem
isso o sindicato novo não teria como enviar a lista. Ele não é "todos" — está
em `gestores.csv`, que também vem da entidade.)

QUEM ESCREVE NESTE ARQUIVO, e é uma lista fechada:

- `acrescentar` — a planilha do sindicato, só para quem é NOVO no portão;
- `trocar_email` — só a ferramenta de quem opera, depois de conferir;
- `remover` — o apagamento a pedido.

A planilha NÃO troca o e-mail de quem já entra e NÃO tira ninguém. As duas
coisas dariam a uma sessão de gestor o poder de redirecionar o código de
outra pessoa — que é exatamente o que o primeiro parágrafo proíbe a quem
digita. O porquê inteiro está em `trocas.py`.

FORMATO, de propósito o mais simples que o sindicato consegue exportar:

    cpf,email
    526.018.159-06,fulano@exemplo.org

Colunas a mais são ignoradas (a exportação do sindicato vem cheia delas);
`cpf` e `email` são exigidas.
"""

from __future__ import annotations

import csv
import fcntl
import functools
import io
import os
import pathlib
import re
import stat
from dataclasses import dataclass

from . import acervo, deposito
from .validacao import cpf_valido, so_digitos

ARQUIVO = "filiados.csv"

#: O rol de GESTORES, mesmo formato e mesmo portão.
#:
#: Existe porque o gerente do sindicato não é necessariamente filiado: se o
#: código só fosse para quem está em `filiados.csv`, não haveria como ele
#: entrar no painel. E ele passa pelo MESMO portão — código de seis dígitos
#: no e-mail que a entidade cadastrou, sem senha — porque inventar um login
#: de gestor seria inventar uma senha para guardar.
#:
#: Ausência deste arquivo NÃO é erro: é sindicato que ainda não configurou
#: painel. Ausência de `filiados.csv` é erro, porque sem ele o portão abriria
#: para todos.
ARQUIVO_GESTORES = "gestores.csv"

#: QUEM REESCREVE O ROL, REESCREVE SOZINHO.
#:
#: O rol tinha um escritor só — o apagamento a pedido, que TIRA a linha.
#: Quando a planilha do gestor passou a ACRESCENTAR, viraram dois, e os dois
#: leem o arquivo inteiro e gravam o arquivo inteiro. Sem trava, a planilha
#: que leu antes do apagamento e gravou depois devolve ao rol a linha de quem
#: acabou de pedir para sair — depois de a varredura de vestígios ter dito
#: que não sobrou nada.
TRAVA = ".rol.trava"


def _com_trava(funcao):
    """Segura a trava da entidade do começo da leitura ao fim da escrita."""

    @functools.wraps(funcao)
    def travada(pasta_entidade: pathlib.Path, *args, **kwargs):
        if not pasta_entidade.is_dir():
            # Sem pasta não há rol para disputar — e criá-la aqui faria
            # `remover` deixar uma pasta vazia para trás em entidade que
            # nunca recebeu nada.
            return funcao(pasta_entidade, *args, **kwargs)
        fd = os.open(pasta_entidade / TRAVA, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return funcao(pasta_entidade, *args, **kwargs)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    return travada


#: O E-MAIL QUE PODE SER ESCRITO NO ROL POR UMA PLANILHA.
#:
#: Mais estreito que o `validacao.EMAIL` de propósito. Aquele serve para
#: dizer ao sindicato "este e-mail não serve"; este decide o que vira LINHA
#: de um CSV que o portão lê. Um endereço com `,` ou `;` dentro é coluna a
#: mais, com quebra de linha é uma pessoa a mais, e começando por `=` é
#: fórmula no dia em que alguém abrir o rol no Excel. Nada disso aparece num
#: endereço que o sindicato use de verdade, então recusar custa pouco.
#:
#: Só ASCII: o rol pode estar em latin-1, e um endereço fora dele não teria
#: como ser escrito sem mudar o arquivo inteiro de codificação.
_EMAIL_DO_ROL = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9.!#$%&'*+/=?^_`{}~-]*"
    r"@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+"
)


def email_serve(email: str) -> bool:
    return len(email) <= 254 and bool(_EMAIL_DO_ROL.fullmatch(email))


def mesmo_email(a: str, b: str) -> bool:
    """Maiúscula não faz outro endereço.

    Pela norma a parte antes do `@` poderia distinguir caixa; na prática
    nenhum provedor distingue, e o Excel do sindicato troca caixa à vontade.
    Tratar `Fulana@` e `fulana@` como endereços diferentes encheria a fila de
    trocas de pedidos que não são troca nenhuma.
    """
    return a.strip().casefold() == b.strip().casefold()


#: QUANTAS PESSOAS um domínio FORA dos provedores comuns recebe no acesso
#: sem ninguém conferir. Passou disso, as novas esperam por quem opera.
#:
#: Existe porque a regra do e-mail repetido compara endereços, e quem
#: controla um domínio escreve quantos endereços quiser — `p1@`, `p2@`,
#: todos caindo na mesma caixa. Não é medição: é um botão. Baixo o bastante
#: para que tomar muitas contas custe muitos domínios; alto o bastante para
#: um casal, ou três colegas de um escritório pequeno, não dependerem de nós.
LIMITE_POR_DOMINIO = 3

#: Os provedores onde cada endereço é uma conta que alguém teve de criar.
#: Neles o limite por domínio não se aplica — metade de qualquer sindicato
#: está no Gmail —, e o que segura é a regra da caixa, abaixo.
#:
#: LISTA ESCRITA À MÃO, não medida numa base real: quando chegar a primeira
#: planilha de verdade, o que estiver fora daqui e for comum aparece como
#: entrada segurada, e a lista se corrige com dado.
PROVEDORES_COMUNS = frozenset({
    "gmail.com", "googlemail.com",
    "hotmail.com", "hotmail.com.br", "outlook.com", "outlook.com.br",
    "live.com", "live.com.br", "msn.com",
    "yahoo.com", "yahoo.com.br", "ymail.com",
    "icloud.com", "me.com", "mac.com",
    "uol.com.br", "bol.com.br", "terra.com.br", "ig.com.br",
    "globo.com", "globomail.com", "r7.com", "zipmail.com.br", "oi.com.br",
    "proton.me", "protonmail.com", "pm.me", "aol.com",
})

_GMAIL = frozenset({"gmail.com", "googlemail.com"})

#: Rótulos que, logo antes de um código de país, são CATEGORIA e não nome:
#: em `exemplo.com.br` quem foi registrado é `exemplo`, não `com`.
_CATEGORIAS = frozenset({
    "com", "org", "net", "gov", "edu", "mil", "jus", "leg", "mp", "def",
    "adv", "eng", "med", "art", "eco", "emp", "ind", "inf", "srv", "tur",
    "coop", "ong", "co", "ac", "ne", "or",
})


def caixa(email: str) -> str:
    """Em que CAIXA este endereço cai — para saber se dois são o mesmo.

    `joana+boleto@x` e `joana@x` são a mesma caixa: o que vem depois do `+`
    é etiqueta. No Gmail o ponto também não distingue, e `googlemail.com` é
    o mesmo serviço. Comparar o TEXTO do endereço deixava uma caixa só
    receber o código de quantas pessoas novas se quisesse, sem comprar
    domínio nem criar conta.

    ERRA PARA O LADO DE JUNTAR. Nem todo provedor trata o `+` como
    etiqueta; num que não trate, duas pessoas de verdade seriam juntadas —
    e o custo é uma entrada segurada, que alguém confere. O erro contrário
    é uma credencial indo para quem não é o dono.
    """
    local, _, dominio = email.strip().casefold().rpartition("@")
    local = local.split("+", 1)[0]
    if dominio in _GMAIL:
        local, dominio = local.replace(".", ""), "gmail.com"
    return f"{local}@{dominio}"


def dominio_registravel(email: str) -> str:
    """De que DONO é o domínio deste endereço: `a.b.exemplo.com.br` ->
    `exemplo.com.br`.

    Contar por domínio inteiro (`a.exemplo.com.br` diferente de
    `b.exemplo.com.br`) não contaria nada: quem tem o domínio cria
    subdomínio de graça.

    É HEURÍSTICA, sem a lista pública de sufixos — que mudaria a cada
    versão e teria de ser baixada. Código de país com uma categoria
    conhecida antes (`com.br`, `gov.br`) guarda três rótulos; o resto,
    dois. Onde erra, erra JUNTANDO: `loja.floripa.br` vira `floripa.br`
    inteiro. O custo é o mesmo de `caixa`: uma entrada segurada a mais.
    """
    rotulos = [r for r in email.strip().casefold().rpartition("@")[2]
               .split(".") if r]
    if len(rotulos) > 2 and len(rotulos[-1]) == 2 \
            and rotulos[-2] in _CATEGORIAS:
        return ".".join(rotulos[-3:])
    return ".".join(rotulos[-2:])


class RolAusente(FileNotFoundError):
    """A entidade não entregou o rol. Não há como conferir ninguém."""


@dataclass(frozen=True)
class Rol:
    caminho: pathlib.Path
    por_cpf: dict[str, str]
    recusados: tuple[str, ...]

    def email_de(self, cpf: str) -> str | None:
        return self.por_cpf.get(so_digitos(cpf))


def carregar(pasta_entidade: pathlib.Path) -> Rol:
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        raise RolAusente(str(caminho))
    return _carregar(caminho)


def carregar_gestores(pasta_entidade: pathlib.Path) -> Rol:
    """Os gestores da entidade. Vazio quando o arquivo não existe.

    Fail-closed na prática: rol de gestores vazio significa que NINGUÉM abre
    o painel, que é o certo — um painel que abre para qualquer um é pior que
    painel nenhum, porque parece seguro.
    """
    caminho = pasta_entidade / ARQUIVO_GESTORES
    if not caminho.is_file():
        return Rol(caminho=caminho, por_cpf={}, recusados=())
    return _carregar(caminho)


def _carregar(caminho: pathlib.Path) -> Rol:
    por_cpf: dict[str, str] = {}
    recusados: list[str] = []
    # O MESMO arquivo que `acervo.py` lê, do mesmo Excel. Abrir só em
    # utf-8-sig derrubava o portão INTEIRO quando a exportação vinha em
    # latin-1: UnicodeDecodeError é ValueError, o servidor loga ROL INVÁLIDO e
    # devolve 202 para todo mundo. O sindicato veria o painel acender e o
    # portal recusar silenciosamente cada filiado.
    #
    # E o separador também: a exportação de Excel em português usa ';'.
    texto = acervo._decodificar(caminho.read_bytes())
    primeira = texto.splitlines()[0] if texto.strip() else ""
    with io.StringIO(texto, newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=acervo._separador(primeira))
        colunas = {(c or "").strip().lower() for c in (leitor.fieldnames or [])}
        if not {"cpf", "email"} <= colunas:
            raise ValueError(
                f"{caminho} precisa das colunas cpf e email; "
                f"tem {sorted(colunas)}"
            )
        for numero, registro in enumerate(leitor, start=2):
            bruto = {
                (k or "").strip().lower(): (v or "").strip()
                for k, v in registro.items()
            }
            digitos = so_digitos(bruto.get("cpf", ""))
            email = bruto.get("email", "")
            if not cpf_valido(digitos):
                recusados.append(f"linha {numero}: CPF inválido")
                continue
            if "@" not in email:
                recusados.append(f"linha {numero}: e-mail inválido")
                continue
            por_cpf[digitos] = email
    return Rol(caminho=caminho, por_cpf=por_cpf, recusados=tuple(recusados))


@_com_trava
def remover(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira este CPF dos dois róis. Devolve quantas linhas saíram.

    ACHA A COLUNA PELO CABEÇALHO, não pela posição — e esta é a correção de
    um defeito que declarava sucesso sem apagar nada.

    A primeira versão cortava por `linha.split(separador)[0]`, supondo o CPF
    na primeira coluna. Mas `_carregar` lê por `csv.DictReader` e só exige
    que o cabeçalho CONTENHA `cpf` e `email`: a ordem é livre, e
    `matricula;cpf;email` é o formato que o docstring deste módulo diz
    esperar ("a exportação do sindicato vem cheia" de colunas a mais). Nesse
    rol, o portão lia a pessoa e `remover` devolvia 0 — para sempre. Com
    e-mail válido o apagamento nunca convergia; sem e-mail válido a varredura
    nem detectava, e a rota respondia "não sobrou nada" com nome e CPF no
    arquivo.

    REESCREVE PRESERVANDO O DIALETO. O rol vem do Excel em português, com
    `;`, e em latin-1 com frequência — `_carregar` aprendeu isso derrubando
    o portão inteiro uma vez. Só a LINHA sai; o cabeçalho e as outras ficam.
    """
    digitos = so_digitos(cpf)
    sairam = 0
    for nome in (ARQUIVO, ARQUIVO_GESTORES):
        caminho = pasta_entidade / nome
        if not caminho.is_file():
            continue
        bruto = caminho.read_bytes()
        texto, encoding = acervo._decodificar_dizendo_como(bruto)
        # O TERMINADOR TAMBÉM É DIALETO. `splitlines()` come CRLF, e
        # `"\n".join` devolvia arquivo de Unix para quem entregou arquivo de
        # Windows. Quem decide é o que está no arquivo, não o nosso sistema.
        fim = "\r\n" if b"\r\n" in bruto else "\n"
        linhas = texto.splitlines()
        if not linhas:
            continue
        separador = acervo._separador(linhas[0])
        cabecalho = [(c or "").strip().lower()
                     for c in linhas[0].split(separador)]
        try:
            coluna = cabecalho.index("cpf")
        except ValueError:
            # Sem coluna `cpf` o arquivo não é um rol — `_carregar` já o
            # recusa. Não mexer é o certo: reescrever um arquivo que não
            # entendemos é pior que deixá-lo como está.
            continue
        guardadas = [linhas[0]]
        for linha in linhas[1:]:
            if not linha.strip():
                continue
            celulas = linha.split(separador)
            valor = celulas[coluna] if coluna < len(celulas) else ""
            if so_digitos(valor) == digitos:
                sairam += 1
                continue
            guardadas.append(linha)
        tmp = caminho.with_suffix(caminho.suffix + ".parcial")
        tmp.write_bytes((fim.join(guardadas) + fim).encode(encoding))
        # A PERMISSÃO É DO ARQUIVO DO SINDICATO. `replace` troca o inode, e
        # sem isto o modo do temporário (guiado pelo umask) passa a valer.
        os.chmod(tmp, stat.S_IMODE(caminho.stat().st_mode))
        tmp.replace(caminho)
    return sairam


def _escrever(caminho: pathlib.Path, conteudo: bytes) -> None:
    """Troca o arquivo inteiro de uma vez: quem lê vê o velho ou o novo."""
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    modo = (stat.S_IMODE(caminho.stat().st_mode) if caminho.is_file()
            else deposito.MODO_ARQUIVO)
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, modo)
    try:
        os.write(fd, conteudo)
        os.fsync(fd)
    finally:
        os.close(fd)
    # `os.open` aplica o umask por cima do modo pedido.
    os.chmod(tmp, modo)
    tmp.replace(caminho)


def _dialeto(caminho: pathlib.Path) -> tuple[list[str], str, str, str]:
    """(linhas, codificação, fim de linha, separador) do rol como ele está."""
    bruto = caminho.read_bytes()
    texto, encoding = acervo._decodificar_dizendo_como(bruto)
    fim = "\r\n" if b"\r\n" in bruto else "\n"
    linhas = texto.splitlines()
    return linhas, encoding, fim, acervo._separador(linhas[0] if linhas else "")


def _celulas(linha: str, separador: str) -> list[str]:
    return next(csv.reader([linha], delimiter=separador), [])


def _linha(celulas: list[str], separador: str) -> str:
    saida = io.StringIO()
    csv.writer(saida, delimiter=separador, lineterminator="").writerow(celulas)
    return saida.getvalue()


@_com_trava
def acrescentar(pasta_entidade: pathlib.Path,
                pares: list[tuple[str, str]]) -> int:
    """Põe gente NOVA no rol de filiados. Devolve quantas linhas entraram.

    SÓ ACRESCENTA. Quem já tem linha válida não é tocado — nem para "atualizar"
    o e-mail: trocar o destino do código de quem já entra é exatamente o que
    este produto não deixa uma planilha fazer sozinha (`trocar_email`, e a
    fila em `trocas.py`).

    CONFERE DE NOVO o que recebe, embora quem chama já tenha conferido: esta
    é a última função antes do arquivo que o portão lê, e uma linha torta
    aqui é uma credencial indo para o endereço errado.

    ESCREVE NO DIALETO DO ARQUIVO — separador, fim de linha, codificação e
    ordem das colunas —, e as linhas de quem já estava ficam byte a byte.
    Sem arquivo, cria um, no formato que o docstring do módulo descreve.
    """
    novos: list[tuple[str, str]] = []
    for cpf, email in pares:
        digitos = so_digitos(cpf)
        if not cpf_valido(digitos):
            raise ValueError("CPF que não fecha não entra no rol")
        if not email_serve(email):
            raise ValueError("este e-mail não pode ser escrito no rol")
        novos.append((digitos, email))
    if not novos:
        return 0

    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        pasta_entidade.mkdir(parents=True, exist_ok=True)
        corpo = "cpf,email\n" + "".join(f"{c},{e}\n" for c, e in novos)
        _escrever(caminho, corpo.encode("utf-8"))
        return len(novos)

    ja = _carregar(caminho).por_cpf     # levanta se o arquivo não é um rol
    linhas, encoding, fim, separador = _dialeto(caminho)
    cabecalho = [c.strip().lower() for c in _celulas(linhas[0], separador)]
    i_cpf, i_email = cabecalho.index("cpf"), cabecalho.index("email")
    acrescimo = []
    for digitos, email in novos:
        if digitos in ja:
            continue
        celulas = [""] * len(cabecalho)
        celulas[i_cpf], celulas[i_email] = digitos, email
        acrescimo.append(_linha(celulas, separador))
        ja[digitos] = email
    if not acrescimo:
        return 0
    bruto = caminho.read_bytes()
    if bruto and not bruto.endswith((b"\n", b"\r")):
        bruto += fim.encode(encoding)
    _escrever(caminho,
              bruto + "".join(l + fim for l in acrescimo).encode(encoding))
    return len(acrescimo)


@_com_trava
def trocar_email(pasta_entidade: pathlib.Path, cpf: str, novo: str) -> int:
    """Troca o e-mail de quem JÁ está no portão. Devolve quantas linhas mudou.

    NÃO É CHAMADA POR ROTA NENHUMA, e isso é a trava: quem chama é a
    ferramenta de quem opera o servidor, depois de conferir a troca por fora.

    Muda o arquivo de onde o portão tira o destino HOJE: `filiados.csv` se a
    pessoa tem linha válida lá, senão `gestores.csv`. Só a célula do e-mail,
    só nas linhas da pessoa; o resto do arquivo fica byte a byte.
    """
    digitos = so_digitos(cpf)
    if not email_serve(novo):
        raise ValueError("este e-mail não pode ser escrito no rol")
    for nome in (ARQUIVO, ARQUIVO_GESTORES):
        caminho = pasta_entidade / nome
        if not caminho.is_file() or digitos not in _carregar(caminho).por_cpf:
            continue
        linhas, encoding, fim, separador = _dialeto(caminho)
        cabecalho = [c.strip().lower() for c in _celulas(linhas[0], separador)]
        i_cpf, i_email = cabecalho.index("cpf"), cabecalho.index("email")
        mudou = 0
        for n, linha in enumerate(linhas[1:], start=1):
            celulas = _celulas(linha, separador)
            if (len(celulas) > max(i_cpf, i_email)
                    and so_digitos(celulas[i_cpf]) == digitos):
                celulas[i_email] = novo
                linhas[n] = _linha(celulas, separador)
                mudou += 1
        if mudou:
            _escrever(caminho,
                      "".join(l + fim for l in linhas).encode(encoding))
        return mudou
    return 0
