"""
Os documentos que o SINDICATO já tem — a porta que não existia.

Até aqui, o único jeito de um PDF entrar era pelo `/api/cadastro`, que exige
a pessoa ter aberto sessão com o código que foi para o e-mail dela. Se o
sindicato tinha 4.000 sentenças numa pasta, não havia porta — e é dele que
vem o acervo documental que já existe.

O PROBLEMA DIFÍCIL AQUI NÃO É LER PDF: é saber **de quem é cada arquivo**.
Casar errado é mostrar a sentença de uma pessoa para outra, e esse é o pior
defeito que este produto pode ter — pior que não ter o documento.

Três formas, em ordem de confiança, e a dúvida nunca vira palpite:

    1. o CPF no NOME do arquivo   o sindicato nomeou: é declaração dele
    2. o CPF DENTRO do texto      só quando há UM só, e ele fecha
    3. nada                       vai para a pilha, nominal, com motivo

E duas recusas que não se negociam:

    DOIS CPFs DIFERENTES no mesmo arquivo. Pode ser sentença coletiva,
    petição com litisconsortes, ou PDF concatenado por alguém. Em qualquer
    um dos casos, escolher um dos dois é sortear — com a sentença de alguém.

    CPF QUE NÃO ESTÁ NA BASE da entidade. Guardá-lo seria guardar dado de
    quem aquele sindicato não declarou atender.

A PILHA DO QUE NÃO CASOU É O PRODUTO, tanto quanto o que casou: "casei 3.812
de 4.000" esconde 188 sentenças de gente que vai ficar sem resposta. Cada
sobra sai com o nome do arquivo e o motivo, para alguém abrir e decidir.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from nucleo import leitura

from . import documentos, validacao

#: Como o arquivo foi casado com a pessoa. Vai no registro: quando alguém
#: contestar "esse documento não é meu", a resposta tem de dizer por quê.
PELO_NOME = "cpf_no_nome_do_arquivo"
PELO_TEXTO = "cpf_no_texto"

#: Teto do que um zip pode descompactar. Arquivo pequeno que vira gigabytes
#: derruba o servidor, e o zip vem de fora.
TETO_TOTAL = 2 * 1024 * 1024 * 1024
#: Teto por arquivo, igual ao do portal.
TETO_ARQUIVO = 25 * 1024 * 1024

#: Pistas de tipo no nome do arquivo. O sindicato costuma nomear, e o nome
#: dele vale mais que a nossa leitura do conteúdo.
_PISTAS = (
    ("certidao_transito", ("certidao", "transito", "transitado")),
    ("sentenca", ("sentenca", "sentença", "acordao", "acórdão", "decisao")),
    ("contribuicao", ("contribuicao", "contribuição", "contracheque",
                      "ficha", "mensalidade")),
    ("procuracao", ("procuracao", "procuração")),
)

#: Onde vai o que não dá para classificar. NÃO é defeito: é a verdade.
#: Chutar o tipo faria a tela da pessoa dizer que a sentença dela chegou.
OUTRO = "outro"

_SEM_ACENTO = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
                            "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")


class ZipRecusado(ValueError):
    """O arquivo compactado não pode ser aberto com segurança."""


@dataclass(frozen=True)
class Documento:
    arquivo: str
    tipo: str
    corpo: bytes
    motivo: str
    achados: tuple = ()


@dataclass(frozen=True)
class Sobra:
    """Um arquivo que não casou com ninguém, e por quê."""

    arquivo: str
    motivo: str


@dataclass
class Resultado:
    casados: dict[str, list[Documento]] = field(default_factory=dict)
    sobraram: list[Sobra] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _plano(texto: str) -> str:
    return str(texto or "").translate(_SEM_ACENTO).lower()


def tipo_pelo_nome(arquivo: str) -> str:
    """O tipo que o NOME do arquivo declara, ou "" se ele não declara nada."""
    plano = _plano(arquivo)
    for tipo, pistas in _PISTAS:
        if any(p in plano for p in pistas):
            return tipo
    return ""


def tipo_pelo_conteudo(achados) -> str:
    """O tipo que o TEXTO permite afirmar — e só quando é claro.

    Usa os mesmos leitores do resto do produto: se houver trânsito em julgado
    sem dispositivo, é certidão; se houver dispositivo, é sentença. Sem nem
    um nem outro, `outro` — e `outro` é resposta, não falha.
    """
    tipos = {a.tipo for a in achados or ()}
    if "dispositivo" in tipos:
        return "sentenca"
    if "transito_em_julgado" in tipos:
        return "certidao_transito"
    return OUTRO


def _cpfs_no_texto(achados) -> list[str]:
    vistos: list[str] = []
    for a in achados or ():
        if a.tipo != "cpf":
            continue
        digitos = validacao.so_digitos(a.valor)
        # Número de 11 dígitos num texto pode ser qualquer coisa. Só CPF que
        # fecha o dígito verificador identifica alguém.
        if validacao.cpf_valido(digitos) and digitos not in vistos:
            vistos.append(digitos)
    return vistos


def _cpf_no_nome(arquivo: str) -> list[str]:
    vistos: list[str] = []
    for bruto in re.findall(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{11}", arquivo):
        digitos = validacao.so_digitos(bruto)
        if validacao.cpf_valido(digitos) and digitos not in vistos:
            vistos.append(digitos)
    return vistos


def abrir_zip(dados: bytes, teto_total: int = TETO_TOTAL,
              teto_arquivo: int = TETO_ARQUIVO) -> list[tuple[str, bytes]]:
    """Os PDFs de dentro do zip, SEM caminho.

    DUAS DEFESAS, e as duas porque o zip vem de fora:

    **O caminho nunca vira caminho.** `../../etc/x.pdf` escreve onde quiser —
    é a falha clássica de quem descompacta arquivo alheio. Aqui só o nome
    final é usado, e entrada que sai da pasta é recusada em vez de aparada:
    aparar em silêncio esconderia um arquivo malicioso no meio do lote.

    **O tamanho é conferido ANTES de descompactar**, pelo declarado no
    índice. Conferir depois já é tarde: a memória já foi.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as e:
        raise ZipRecusado(f"não é um arquivo .zip legível: {e}") from None

    total = 0
    for info in z.infolist():
        if info.is_dir():
            continue
        nome = info.filename.replace("\\", "/")
        if nome.startswith("/") or ".." in nome.split("/"):
            raise ZipRecusado(
                f"a entrada {info.filename!r} aponta para FORA da pasta. Um "
                f"zip que escreve onde quiser não é aberto aqui"
            )
        total += info.file_size
        if info.file_size > teto_arquivo:
            raise ZipRecusado(
                f"{nome!r} tem {info.file_size} bytes descompactado e o teto "
                f"por arquivo é {teto_arquivo}"
            )
    if total > teto_total:
        raise ZipRecusado(
            f"o zip descompacta {total} bytes e o teto total é {teto_total}. "
            f"Mande em partes"
        )

    saida: list[tuple[str, bytes]] = []
    for info in z.infolist():
        if info.is_dir():
            continue
        nome = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
        # Lixo que o macOS e o Windows põem dentro do zip.
        if not nome or nome.startswith("._") or nome.startswith("."):
            continue
        if not nome.lower().endswith(".pdf"):
            continue
        saida.append((nome, z.read(info)))
    return saida


def casar(arquivos, cpfs_da_base) -> Resultado:
    """De quem é cada arquivo. O que não dá para dizer vai para a pilha.

    `cpfs_da_base` são os CPFs que a entidade declarou atender — do acervo e
    dos cadastros. Um arquivo de quem não está lá não entra.
    """
    base = {validacao.so_digitos(c) for c in cpfs_da_base or ()}
    r = Resultado()

    for arquivo, corpo in arquivos or ():
        try:
            achados = documentos.ler_pdf(corpo)
        except Exception:  # noqa: BLE001
            # Um arquivo quebrado no meio de 4.000 não derruba a ingestão.
            # Ele ainda pode casar pelo nome, e aí entra sem fato extraído.
            achados = []

        do_nome = _cpf_no_nome(arquivo)
        do_texto = _cpfs_no_texto(achados)

        if len(do_nome) > 1:
            r.sobraram.append(Sobra(
                arquivo,
                f"o nome do arquivo traz mais de um CPF ({len(do_nome)}), e "
                f"escolher um deles seria sortear",
            ))
            continue

        if do_nome:
            cpf, motivo = do_nome[0], PELO_NOME
            if do_texto and cpf not in do_texto:
                r.avisos.append(
                    f"{arquivo}: o CPF do nome do arquivo DISCORDA do que "
                    f"está no texto. Valeu o do nome — é declaração do "
                    f"sindicato —, mas vale conferir"
                )
        elif len(do_texto) > 1:
            r.sobraram.append(Sobra(
                arquivo,
                f"o texto traz mais de um CPF ({len(do_texto)}). Pode ser "
                f"coletiva, litisconsórcio ou PDF concatenado — e escolher "
                f"um deles seria sortear com a sentença de alguém",
            ))
            continue
        elif do_texto:
            cpf, motivo = do_texto[0], PELO_TEXTO
        else:
            r.sobraram.append(Sobra(
                arquivo,
                "nenhum CPF no nome nem no texto. Renomeie com o CPF ou "
                "confira se o PDF tem camada de texto",
            ))
            continue

        if cpf not in base:
            r.sobraram.append(Sobra(
                arquivo,
                f"o CPF encontrado não está na base desta entidade — "
                f"confira se a planilha de filiados está atualizada",
            ))
            continue

        tipo = tipo_pelo_nome(arquivo) or tipo_pelo_conteudo(achados)
        r.casados.setdefault(cpf, []).append(
            Documento(arquivo=arquivo, tipo=tipo, corpo=corpo, motivo=motivo,
                      achados=tuple(achados))
        )

    return r
