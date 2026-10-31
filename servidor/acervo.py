"""
A ingestão do acervo do sindicato. A planilha como ela vem.

A PRIMEIRA ENTREGA DO PRODUTO B, e a única que não depende de resposta de
ninguém. O sindicato não tem um cadastro limpo: tem exportação de folha,
lista de secretaria, sistema antigo e planilha que alguém juntou à mão. Se a
ingestão exigir arquivo bonito, não ingere nada.

MAS O OPOSTO É PIOR. Engolir e descartar em silêncio produz um número
tranquilizador e falso. **Linha ruim é o produto**: é ela que o gerente
precisa ver. "Não consigo falar com 1.930 dos meus 4.812 filiados" é a
informação que ele não tem hoje, e ela só existe se a linha sem e-mail
aparecer em vez de sumir.

Então nada aqui descarta linha. Cada linha entra, com os achados dela
pendurados, e quem decide o que fazer é gente.

AS DUAS ARMADILHAS, e as duas já morderam este projeto:

**Encoding.** `rol.py` aprendeu o BOM na mão: a exportação de planilha vem
com BOM, o cabeçalho chega como "﻿cpf", não casa com "cpf", e o rol
inteiro fica vazio — sem erro nenhum. Um acervo que lê zero pessoa de um
arquivo cheio parece "o sindicato não tem base".

**Repetição.** `elegibilidade.py` aprendeu que planilha de entidade repete
pessoa: exportação concatenada, junção de duas listas, gente recadastrada. E
aprendeu o que fazer: quando as linhas discordam, TODAS param — inclusive a
primeira. A ordem de uma exportação não é informação sobre nada, e escolher
"a primeira vale" seria sortear qual versão da verdade entra na base.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import pathlib
import re
import unicodedata
from dataclasses import dataclass, field

from nucleo import processo_cnj

from . import validacao

#: Estados de um achado. `OK` existe para não precisar de ausência como
#: resposta: achado é sempre explícito.
OK = "OK"
FALTA = "FALTA"
INVALIDO = "INVALIDO"
DIVERGENTE = "DIVERGENTE"

#: Encodings tentados, nesta ordem. `utf-8-sig` primeiro porque come o BOM
#: quando ele existe e se comporta como `utf-8` quando não; `latin-1` por
#: último porque ele nunca falha — decodifica qualquer byte — e por isso só
#: pode ser a última tentativa, nunca uma anterior.
ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")

#: Separadores candidatos. Decidido por CONTAGEM no cabeçalho, não por
#: `csv.Sniffer`: o Sniffer adivinha pelo conteúdo e erra em arquivo com
#: vírgula dentro de nome entre aspas — e nome composto com vírgula é comum
#: em cadastro de sindicato ("SOUZA, MARIA").
SEPARADORES = (";", "\t", ",")

#: Sinônimo de coluna -> coluna do contrato. A chave é o cabeçalho
#: NORMALIZADO (minúsculo, sem acento, sem pontuação).
#:
#: Esta tabela é a parte que vai crescer quando chegar uma exportação real de
#: sindicato, e crescer aqui não muda mais nada no desenho: coluna que não
#: casa é preservada, não é erro.
APELIDOS: dict[str, str] = {
    "cpf": "cpf",
    "cpf_cnpj": "cpf",
    "cpf_do_filiado": "cpf",
    "n_cpf": "cpf",
    "documento": "cpf",
    "nome": "nome_completo",
    "nome_completo": "nome_completo",
    "nome_do_filiado": "nome_completo",
    "filiado": "nome_completo",
    "email": "email",
    "e_mail": "email",
    "correio_eletronico": "email",
    "matricula": "matricula",
    "matricula_siape": "matricula",
    "siape": "matricula",
    "rg": "rg",
    "identidade": "rg",
    "telefone": "telefone",
    "fone": "telefone",
    "celular": "telefone",
    "cep": "cep",
    "logradouro": "logradouro",
    "endereco": "logradouro",
    "numero": "numero",
    "complemento": "complemento",
    "bairro": "bairro",
    "municipio": "municipio",
    "cidade": "municipio",
    "uf": "uf",
    "estado": "uf",
    "cargo": "cargo",
    "situacao": "situacao",
    "situacao_funcional": "situacao",
    "unidade": "unidade",
    "lotacao": "unidade",
    "data_nascimento": "data_nascimento",
    "data_de_nascimento": "data_nascimento",
    "nascimento": "data_nascimento",
    "dt_nascimento": "data_nascimento",
    "data_ingresso": "data_ingresso",
    "data_de_ingresso": "data_ingresso",
    "admissao": "data_ingresso",
    "data_aposentadoria": "data_aposentadoria",
    "data_de_aposentadoria": "data_aposentadoria",

    # O PERÍODO DE FILIAÇÃO. É ele que cruza com o período da ação coletiva e
    # responde "em quais ações esta pessoa participa" — e ele NÃO ESTAVA
    # AQUI. Sem ele na planilha, o sindicato manda 4.812 pessoas e o motor
    # não responde por nenhuma: a pessoa aposentada tinha de digitar, no
    # celular, desde quando contribui.
    #
    # Nenhum sindicato escreve "filiado_desde". Cada sistema tem o seu nome,
    # e cabeçalho não reconhecido vira texto solto que o motor nunca olha.
    "filiado_desde": "filiado_desde",
    "filiado_em": "filiado_desde",
    "data_filiacao": "filiado_desde",
    "dt_filiacao": "filiado_desde",
    "data_de_filiacao": "filiado_desde",
    "filiacao": "filiado_desde",
    "associado_desde": "filiado_desde",
    "data_de_associacao": "filiado_desde",
    "inicio_da_contribuicao": "filiado_desde",
    "inicio_contribuicao": "filiado_desde",

    # VAZIO É RESPOSTA: significa "ainda filiado". Tratá-lo como omissão
    # tiraria da conta justamente quem está no sindicato hoje.
    "filiado_ate": "filiado_ate",
    "desfiliado_em": "filiado_ate",
    "data_desfiliacao": "filiado_ate",
    "data_de_desfiliacao": "filiado_ate",
    "fim_da_contribuicao": "filiado_ate",
    "fim_contribuicao": "filiado_ate",
    "data_saida": "filiado_ate",

    # OS PROCESSOS QUE O SINDICATO JÁ CONHECE. Hoje a pessoa tem de achar 20
    # dígitos numa papelada e digitar — informação que o sindicato costuma
    # ter. `numero` NÃO entra aqui: é o número do endereço, e já está mapeado.
    "numero_do_processo": "numeros_de_processo",
    "numero_processo": "numeros_de_processo",
    "n_processo": "numeros_de_processo",
    "processo": "numeros_de_processo",
    "processos": "numeros_de_processo",
    "numeros_de_processo": "numeros_de_processo",
    "autos": "numeros_de_processo",
}

#: Competência AAAA-MM. É o formato que o cruzamento usa.
_COMPETENCIA = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

#: As formas em que uma data de filiação chega numa planilha brasileira.
#: Dia inteiro, mês/ano, ano/mês, e com barra, hífen ou ponto.
_FORMAS_DE_DATA = (
    re.compile(r"^(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2})[/\-.](?P<a>\d{4})$"),
    re.compile(r"^(?P<a>\d{4})[/\-.](?P<m>\d{1,2})[/\-.](?P<d>\d{1,2})$"),
    re.compile(r"^(?P<m>\d{1,2})[/\-.](?P<a>\d{4})$"),
    re.compile(r"^(?P<a>\d{4})[/\-.](?P<m>\d{1,2})$"),
)


def competencia(bruto: str, hoje: dt.date | None = None) -> str:
    """A data da planilha em AAAA-MM, ou "" quando não dá para ler.

    DESCARTAR EM SILÊNCIO SERIA O PIOR CAMINHO: a pessoa perderia a
    participação dela por causa de uma célula que o Excel formatou torto, e
    ninguém saberia por quê. Quem chama transforma o "" em achado.

    O DIA É JOGADO FORA de propósito: o cruzamento é mensal, e guardar um dia
    que a planilha às vezes não tem faria competência de mesmo mês parecer
    diferente.
    """
    hoje = hoje or dt.date.today()
    texto = str(bruto or "").strip()
    if not texto:
        return ""
    if _COMPETENCIA.match(texto):
        ano, mes = int(texto[:4]), int(texto[5:7])
    else:
        for forma in _FORMAS_DE_DATA:
            achado = forma.match(texto)
            if achado:
                ano, mes = int(achado.group("a")), int(achado.group("m"))
                break
        else:
            return ""
    if not 1 <= mes <= 12:
        return ""
    # Antes de 1930 é erro de digitação; no futuro é ano de dois dígitos lido
    # errado. Aceitar qualquer um dos dois poria a pessoa fora de toda ação.
    if ano < 1930 or (ano, mes) > (hoje.year, hoje.month):
        return ""
    return f"{ano:04d}-{mes:02d}"


#: Dentro de uma célula, vários processos vêm separados por qualquer coisa.
#: A planilha não avisa qual.
_ENTRE_PROCESSOS = re.compile(r"[;,/\n|]+")


def processos(bruto: str) -> tuple[list[str], list[str]]:
    """(números que fecham, números que não fecham), em dígitos.

    Número cujo dígito verificador não bate é erro de digitação. Acompanhá-lo
    é gastar consulta de 30 segundos e devolver silêncio à pessoa.
    """
    bons: list[str] = []
    ruins: list[str] = []
    for pedaco in _ENTRE_PROCESSOS.split(str(bruto or "")):
        digitos = "".join(c for c in pedaco if c.isdigit())
        if not digitos:
            continue
        if processo_cnj.conferir(digitos, exigir_trf1=False):
            ruins.append(pedaco.strip())
        elif digitos not in bons:
            bons.append(digitos)
    return bons, ruins


class AcervoIlegivel(ValueError):
    """O arquivo não pôde ser lido de jeito nenhum."""


@dataclass(frozen=True)
class Achado:
    """O que há de dizer sobre um campo de uma pessoa."""

    coluna: str
    estado: str
    detalhe: str = ""

    @property
    def impede_contato(self) -> bool:
        """Este achado impede o sindicato de falar com a pessoa?

        Só FALTA e INVALIDO em CPF ou e-mail. **DIVERGENTE não entra**, e a
        distinção não é sutileza: a Maria que aparece duas vezes com cargos
        diferentes continua tendo e-mail que funciona. Contar a divergência
        como "não alcanço" inflaria a manchete do painel com gente que o
        sindicato alcança perfeitamente — e a manchete é o número que vai
        para o cliente.
        """
        return (
            self.coluna in ("cpf", "email")
            and self.estado in (FALTA, INVALIDO)
        )


@dataclass(frozen=True)
class Pessoa:
    """Uma LINHA do acervo — não uma pessoa única.

    Duas linhas com o mesmo CPF produzem duas `Pessoa`, de propósito: fundir
    aqui apagaria o que uma das duas dizia, e é justamente a diferença entre
    elas que o gerente precisa ver.
    """

    cpf: str
    linha_no_arquivo: int
    campos: dict[str, str] = field(default_factory=dict)
    achados: tuple[Achado, ...] = ()

    @property
    def alcancavel(self) -> bool:
        """O sindicato consegue falar com esta pessoa?

        CPF que fecha E e-mail que serve. Os dois, porque o código de acesso
        vai para o e-mail que o sindicato tem em cadastro: sem e-mail válido
        a pessoa não entra no portal e não recebe aviso, e sem CPF válido não
        há como ligá-la a processo nenhum.
        """
        return not any(a.impede_contato for a in self.achados)

    def falta(self) -> list[str]:
        return [a.coluna for a in self.achados if a.estado == FALTA]


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_cabecalho(bruto: str) -> str:
    """'CPF/CNPJ' -> 'cpf_cnpj'. 'Data de Nascimento' -> 'data_de_nascimento'."""
    limpo = _sem_acento(str(bruto or "")).lower().strip()
    saida = []
    for ch in limpo:
        saida.append(ch if ch.isalnum() else "_")
    return "_".join(p for p in "".join(saida).split("_") if p)


def _decodificar(bruto: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return bruto.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AcervoIlegivel("nenhum encoding conhecido decodificou o arquivo")


def _separador(primeira_linha: str) -> str:
    """O que mais aparece no cabeçalho. Empate resolve pela ordem de
    `SEPARADORES`, que põe ';' antes de ',' — a exportação de Excel em
    português usa ';', e é o caso mais comum aqui."""
    contagens = {s: primeira_linha.count(s) for s in SEPARADORES}
    melhor = max(SEPARADORES, key=lambda s: contagens[s])
    return melhor if contagens[melhor] else ","


def _achados_do_campo(coluna: str, valor: str) -> list[Achado]:
    if coluna == "cpf":
        if not valor:
            return [Achado("cpf", FALTA, "linha sem CPF")]
        if not validacao.cpf_valido(valor):
            return [Achado(
                "cpf", INVALIDO,
                f"o CPF {valor!r} não fecha o dígito verificador — é erro de "
                f"cadastro, não afirmação sobre a pessoa",
            )]
        return []
    if coluna == "email":
        if not valor:
            return [Achado("email", FALTA,
                           "sem e-mail o código de acesso não tem para onde ir")]
        if not validacao.EMAIL.match(valor):
            return [Achado("email", INVALIDO, f"e-mail {valor!r} não serve")]
        return []
    if coluna in ("filiado_desde", "filiado_ate"):
        # Vazio NÃO é achado aqui: em `filiado_ate` significa "ainda
        # filiado", e em `filiado_desde` a falta aparece depois, nominal e
        # com dono, pela via normal do produto.
        if valor and not competencia(valor):
            return [Achado(
                coluna, INVALIDO,
                f"{valor!r} não é data que dê para ler. Use AAAA-MM, "
                f"MM/AAAA ou DD/MM/AAAA — e confira se não é ano de dois "
                f"dígitos lido como futuro",
            )]
        return []
    if coluna == "numeros_de_processo":
        _, ruins = processos(valor)
        if ruins:
            return [Achado(
                coluna, INVALIDO,
                f"não fecha o dígito verificador: {', '.join(ruins[:3])}",
            )]
        return []
    if not valor and coluna in validacao.EXIGIDOS:
        return [Achado(coluna, FALTA, f"{coluna} está vazio no acervo")]
    return []


def _achados_de_repeticao(pessoas: list[Pessoa]) -> dict[int, Achado]:
    """Para cada linha repetida que DISCORDA, um achado — em todas elas.

    Repetição idêntica não é divergência: duas linhas iguais são uma
    informação só, e mandar o gerente escolher entre duas coisas idênticas
    seria trabalho inventado.
    """
    por_cpf: dict[str, list[Pessoa]] = {}
    for p in pessoas:
        if p.cpf:
            por_cpf.setdefault(p.cpf, []).append(p)

    saida: dict[int, Achado] = {}
    for cpf, grupo in por_cpf.items():
        if len(grupo) < 2:
            continue
        colunas = {c for p in grupo for c in p.campos}
        divergentes = sorted(
            c for c in colunas
            if len({p.campos.get(c, "") for p in grupo}) > 1
        )
        if not divergentes:
            continue
        linhas = ", ".join(str(p.linha_no_arquivo) for p in grupo)
        for p in grupo:
            saida[p.linha_no_arquivo] = Achado(
                "cpf", DIVERGENTE,
                f"este CPF aparece nas linhas {linhas} com valores diferentes "
                f"em: {', '.join(divergentes)}. Decidir qual vale é do "
                f"sindicato — a ordem na planilha não decide.",
            )
    return saida


def ler(caminho: pathlib.Path | str) -> tuple[list[Pessoa], list[str]]:
    """Lê o acervo. Devolve as pessoas e os problemas DO ARQUIVO.

    A separação importa: problema de arquivo (sem coluna de CPF, encoding
    impossível) impede ler qualquer coisa e é falha fechada. Problema de
    LINHA não impede nada — vira achado e segue.
    """
    caminho = pathlib.Path(caminho)
    problemas: list[str] = []
    try:
        texto = _decodificar(caminho.read_bytes())
    except AcervoIlegivel as e:
        return [], [str(e)]
    except OSError as e:
        return [], [f"não foi possível abrir {caminho}: {e}"]

    primeira = texto.splitlines()[0] if texto.strip() else ""
    if not primeira:
        return [], [f"{caminho} está vazio"]

    leitor = csv.DictReader(io.StringIO(texto), delimiter=_separador(primeira))
    mapa: dict[str, str] = {}
    desconhecidas: dict[str, str] = {}
    origens: dict[str, list[str]] = {}
    for bruto in leitor.fieldnames or []:
        chave = normalizar_cabecalho(bruto)
        if chave in APELIDOS:
            mapa[bruto] = APELIDOS[chave]
            origens.setdefault(APELIDOS[chave], []).append(bruto)
        elif chave:
            # Coluna que o contrato não tem é PRESERVADA. Descartar perderia
            # informação que o sindicato achou importante guardar, e reprovar
            # recusaria a planilha por ela ter uma coluna a mais.
            desconhecidas[bruto] = chave

    # DUAS COLUNAS PARA O MESMO CAMPO. Exportação concatenada traz `CPF` e
    # `CPF/CNPJ`, ou `nome` e `Nome Completo`. Deixar a última vencer em
    # silêncio DESTRÓI o dado quando ela está vazia — e no caso do CPF a
    # pessoa vira "inalcançável por falta de CPF", ganha chave de linha e
    # nunca mais casa com o cadastro dela no portal.
    for destino, brutas in sorted(origens.items()):
        if len(brutas) > 1:
            problemas.append(
                f"{caminho.name}: as colunas {', '.join(repr(b) for b in brutas)} "
                f"apontam todas para {destino!r}. O primeiro valor preenchido "
                f"vence, mas confira a planilha — concatenação de exportações "
                f"costuma ser a causa."
            )

    if "cpf" not in mapa.values():
        problemas.append(
            f"{caminho} não tem coluna de CPF (cabeçalhos lidos: "
            f"{sorted(normalizar_cabecalho(c) for c in leitor.fieldnames or [])}). "
            f"Sem CPF não há como identificar ninguém."
        )
        return [], problemas

    pessoas: list[Pessoa] = []
    for numero, registro in enumerate(leitor, start=2):
        campos: dict[str, str] = {}
        for bruto, valor in registro.items():
            destino = mapa.get(bruto) or desconhecidas.get(bruto)
            if destino is None:
                continue
            limpo = (valor or "").strip()
            # PREENCHIDO VENCE VAZIO. Quando duas colunas apontam para o
            # mesmo campo, a que tem conteúdo manda — a ordem das colunas na
            # planilha não é informação sobre nada.
            if limpo or destino not in campos:
                campos[destino] = limpo

        cpf_digitos = validacao.so_digitos(campos.get("cpf", ""))
        achados: list[Achado] = []
        for coluna in sorted(set(campos) | {"cpf", "email"}):
            achados += _achados_do_campo(coluna, campos.get(coluna, ""))

        # NORMALIZA DEPOIS DE ACHAR, nunca antes: o achado precisa mostrar o
        # que veio na célula — "não dá para ler '15/03/2099'" só ajuda quem
        # vai abrir a planilha se disser o que estava lá.
        #
        # O que não dá para ler vira VAZIO, e o achado acima é quem conta a
        # história. Guardar o texto torto faria o cruzamento comparar contra
        # um mês que não existe.
        for coluna in ("filiado_desde", "filiado_ate"):
            if coluna in campos:
                campos[coluna] = competencia(campos[coluna])
        if "numeros_de_processo" in campos:
            bons, _ = processos(campos["numeros_de_processo"])
            campos["numeros_de_processo"] = ";".join(bons)
        pessoas.append(Pessoa(
            cpf=cpf_digitos,
            linha_no_arquivo=numero,
            campos=campos,
            achados=tuple(achados),
        ))

    repeticoes = _achados_de_repeticao(pessoas)
    if repeticoes:
        pessoas = [
            Pessoa(
                cpf=p.cpf,
                linha_no_arquivo=p.linha_no_arquivo,
                campos=p.campos,
                achados=p.achados + (repeticoes[p.linha_no_arquivo],),
            ) if p.linha_no_arquivo in repeticoes else p
            for p in pessoas
        ]
    return pessoas, problemas
