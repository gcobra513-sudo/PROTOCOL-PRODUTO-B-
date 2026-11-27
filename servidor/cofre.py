"""
O cofre: onde os documentos das pessoas ficam guardados.

SÃO DOIS, COM O MESMO CONTRATO. `NoDisco` é a pasta do servidor, do jeito que
sempre foi (`entrega/<cpf>/`, `historico/<cpf>/…`), e continua sendo o que a
demonstração e os testes usam. `NoS3` é um depósito privado na nuvem, falado
no padrão S3 — que a Supabase, a AWS e o Google aceitam, de modo que trocar
de fornecedor é trocar o endereço na configuração, e não reescrever isto.

SÓ OS PDFs MORAM AQUI. O diário, o rol e as planilhas continuam onde estão:
são pequenos, e é o diário — não o cofre — que diz quem enviou o quê. O
cofre é burro de propósito: guarda bytes sob (sindicato, CPF, nome) e nada
decide.

AS TRÊS REGRAS QUE ESTE ARQUIVO EXISTE PARA GARANTIR:

**Nada vindo de fora vira caminho.** Sindicato, CPF, protocolo e nome de
arquivo passam por uma forma fechada antes de compor qualquer chave. No S3
não existe `..`, mas existe prefixo: `sind/0000091006` é prefixo de
`sind/00000910066`, e é por isso que toda listagem termina em barra.

**Um sindicato não alcança o outro.** A chave começa pelo apelido, que vem
do cadastro e nunca do pedido. Não há operação aqui que receba um caminho
pronto.

**O depósito na nuvem fica no Brasil e fala cifrado.** A região é conferida
contra uma lista, e `http://` é recusado. Configuração pela metade não cai
no disco em silêncio: o servidor não sobe. Na dúvida, falha fechado.

A ORDEM DO REENVIO NO S3 — copiar o antigo para o histórico, apagar o
antigo, gravar o novo — é a que GRITA se cair no meio: sobra pasta vazia com
linha no diário, e o verificador reprova. A ordem "gravar por cima e limpar
depois" deixaria um conjunto misturado, metade de cada envio, com cara de
inteiro. É a mesma escolha de `deposito.py`: entre o erro que aparece e o
que não aparece, o que aparece.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import shutil
from dataclasses import dataclass, field

from .entidades import APELIDO, Entidade

#: A forma do contrato: minúsculas, dígitos, hífen, sublinhado — e `.pdf`
#: (`certidao_transito.pdf`, `sentenca-2.pdf`). Sem espaço, sem barra, sem
#: ponto no meio. O nome que o usuário deu ao arquivo nunca chega aqui; quem
#: nomeia é `validacao` e `ingestao`.
_NOME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62})\.pdf\Z")
_CPF = re.compile(r"^[0-9]{11}\Z")
_PROTOCOLO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}\Z")

ENTREGA = "entrega"
HISTORICO = "historico"
PARCIAL = ".parcial"

MODO_PASTA = 0o700
MODO_ARQUIVO = 0o600

#: Onde o depósito pode estar. "Dado de filiado não sai do Brasil" deixa de
#: ser combinado e vira conferência: região fora desta lista não sobe.
#: (`sa-east-1` é São Paulo na AWS e na Supabase; `southamerica-east1`, no
#: Google.)
REGIOES_NO_BRASIL = frozenset({"sa-east-1", "southamerica-east1"})


class Recusado(ValueError):
    """Um identificador não tem a forma do contrato. Nada foi tocado."""


class NaoHa(LookupError):
    """Não existe esse documento para essa pessoa nesse sindicato."""


class AjusteRecusado(ValueError):
    """A configuração do depósito na nuvem está errada ou pela metade."""


def _conferir(ent: Entidade, cpf: str, *, nomes=(), protocolos=()) -> None:
    # O apelido já foi validado no cadastro; conferir de novo custa nada e
    # tira deste arquivo a dependência de que todo chamador tenha passado
    # por lá.
    if not APELIDO.match(ent.apelido):
        raise Recusado("sindicato fora da forma")
    if not isinstance(cpf, str) or not _CPF.match(cpf):
        raise Recusado("o cofre exige CPF de 11 dígitos")
    for nome in nomes:
        if not isinstance(nome, str) or not _NOME.match(nome):
            raise Recusado("nome de arquivo fora do contrato")
    for p in protocolos:
        if not isinstance(p, str) or not _PROTOCOLO.match(p):
            raise Recusado("protocolo fora da forma")


def _marca(protocolo: str) -> str:
    # O PROTOCOLO VAI NO NOME: só com o segundo, dois reenvios da mesma
    # pessoa no mesmo segundo cairiam no mesmo lugar do histórico.
    agora = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S")
    return f"{agora}-{protocolo}"


# ----------------------------------------------------------------- disco


class NoDisco:
    """A pasta do servidor. O formato é o que `conferir_entrega.py` abre."""

    def __init__(self, raiz: pathlib.Path) -> None:
        self._raiz = pathlib.Path(raiz)

    def _atual(self, ent: Entidade, cpf: str) -> pathlib.Path:
        return ent.pasta(self._raiz) / ENTREGA / cpf

    def _historico(self, ent: Entidade, cpf: str) -> pathlib.Path:
        return ent.pasta(self._raiz) / HISTORICO / cpf

    def nomes(self, ent: Entidade, cpf: str) -> list[str]:
        _conferir(ent, cpf)
        pasta = self._atual(ent, cpf)
        if not pasta.is_dir():
            return []
        return sorted(a.name for a in pasta.glob("*.pdf") if a.is_file())

    def ler(self, ent: Entidade, cpf: str, nome: str) -> bytes:
        _conferir(ent, cpf, nomes=[nome])
        try:
            return (self._atual(ent, cpf) / nome).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            raise NaoHa(nome) from None

    def trocar(self, ent: Entidade, cpf: str, protocolo: str,
               arquivos: dict[str, bytes]) -> str:
        _conferir(ent, cpf, nomes=arquivos, protocolos=[protocolo])
        pasta = ent.pasta(self._raiz)

        # Montados de lado e trocados de uma vez.
        montagem = pasta / PARCIAL / protocolo
        if montagem.exists():
            shutil.rmtree(montagem)
        montagem.mkdir(parents=True)
        os.chmod(montagem, MODO_PASTA)
        for nome, corpo in arquivos.items():
            alvo = montagem / nome
            alvo.write_bytes(corpo)
            os.chmod(alvo, MODO_ARQUIVO)

        entrega = pasta / ENTREGA
        entrega.mkdir(parents=True, exist_ok=True)
        os.chmod(entrega, MODO_PASTA)
        destino = entrega / cpf

        substituiu = ""
        if destino.exists():
            guarda = self._historico(ent, cpf) / _marca(protocolo)
            guarda.parent.mkdir(parents=True, exist_ok=True)
            destino.replace(guarda)
            substituiu = str(guarda.relative_to(pasta))

        montagem.replace(destino)
        try:
            (pasta / PARCIAL).rmdir()
        except OSError:
            pass
        return substituiu

    def acrescentar(self, ent: Entidade, cpf: str, nome: str,
                    corpo: bytes) -> None:
        _conferir(ent, cpf, nomes=[nome])
        destino = self._atual(ent, cpf)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / nome).write_bytes(corpo)

    def contar(self, ent: Entidade, cpf: str) -> dict[str, int]:
        _conferir(ent, cpf)
        achado = {}
        for rotulo, alvo in ((ENTREGA, self._atual(ent, cpf)),
                             (HISTORICO, self._historico(ent, cpf))):
            if alvo.is_dir():
                n = sum(1 for f in alvo.rglob("*") if f.is_file())
                if n:
                    achado[rotulo] = n
        return achado

    def apagar(self, ent: Entidade, cpf: str, protocolos) -> int:
        protocolos = list(protocolos)
        _conferir(ent, cpf, protocolos=protocolos)
        pasta = ent.pasta(self._raiz)
        alvos = [self._atual(ent, cpf), self._historico(ent, cpf)]
        # A ÁREA DE MONTAGEM é indexada por protocolo: um envio que caiu
        # entre montar e trocar deixa o documento ali.
        alvos += [pasta / PARCIAL / p for p in protocolos]
        foram = 0
        for alvo in alvos:
            if alvo.is_dir():
                foram += sum(1 for f in alvo.rglob("*") if f.is_file())
                shutil.rmtree(alvo)
        return foram


    def esvaziar(self, ent: Entidade) -> int:
        """Tira TODOS os documentos de um sindicato. Só a demonstração
        chama, ao recomeçar do zero."""
        _conferir(ent, "00000000000")
        pasta = ent.pasta(self._raiz)
        foram = 0
        for alvo in (pasta / ENTREGA, pasta / HISTORICO, pasta / PARCIAL):
            if alvo.is_dir():
                # O manifesto mora em `entrega/` e não é documento de ninguém.
                foram += sum(1 for f in alvo.rglob("*.pdf") if f.is_file())
                for filho in alvo.iterdir():
                    if filho.is_dir():
                        shutil.rmtree(filho)
        return foram


# -------------------------------------------------------------------- S3


class NoS3:
    """Um depósito privado, no padrão S3.

    A chave é `<sindicato>/<cpf>/atual/<nome>` e
    `<sindicato>/<cpf>/historico/<quando>-<protocolo>/<nome>`.

    O CPF ESTÁ NA CHAVE, em claro, e é decisão: o banco que mora no mesmo
    projeto já guarda o CPF em claro (`documento.cpf`), então escondê-lo
    aqui não protegeria nada — e um embaralhamento com segredo criaria um
    jeito novo de perder documento: perdeu o segredo, perdeu o endereço de
    todos.
    """

    def __init__(self, cliente, balde: str) -> None:
        self._s3 = cliente
        self._balde = balde

    # A BARRA NO FIM É A REGRA: sem ela, o prefixo de um CPF ou de um
    # sindicato alcança o vizinho cujo nome começa igual.
    @staticmethod
    def _da_pessoa(ent: Entidade, cpf: str) -> str:
        return f"{ent.apelido}/{cpf}/"

    def _atual(self, ent: Entidade, cpf: str) -> str:
        return self._da_pessoa(ent, cpf) + "atual/"

    def _chaves(self, prefixo: str) -> list[str]:
        assert prefixo.endswith("/"), "listagem sem barra alcança o vizinho"
        chaves: list[str] = []
        continua = None
        while True:
            extra = {"ContinuationToken": continua} if continua else {}
            pagina = self._s3.list_objects_v2(
                Bucket=self._balde, Prefix=prefixo, **extra)
            chaves += [o["Key"] for o in pagina.get("Contents", [])]
            if not pagina.get("IsTruncated"):
                return chaves
            continua = pagina["NextContinuationToken"]

    def _gravar(self, chave: str, corpo: bytes) -> None:
        self._s3.put_object(Bucket=self._balde, Key=chave, Body=corpo,
                            ContentType="application/pdf")

    def nomes(self, ent: Entidade, cpf: str) -> list[str]:
        _conferir(ent, cpf)
        prefixo = self._atual(ent, cpf)
        return sorted(
            c[len(prefixo):] for c in self._chaves(prefixo)
            if _NOME.match(c[len(prefixo):])
        )

    def ler(self, ent: Entidade, cpf: str, nome: str) -> bytes:
        _conferir(ent, cpf, nomes=[nome])
        try:
            resposta = self._s3.get_object(
                Bucket=self._balde, Key=self._atual(ent, cpf) + nome)
        except self._s3.exceptions.NoSuchKey:
            raise NaoHa(nome) from None
        return resposta["Body"].read()

    def trocar(self, ent: Entidade, cpf: str, protocolo: str,
               arquivos: dict[str, bytes]) -> str:
        _conferir(ent, cpf, nomes=arquivos, protocolos=[protocolo])
        atual = self._atual(ent, cpf)
        antigos = self._chaves(atual)

        substituiu = ""
        if antigos:
            guarda = (f"{self._da_pessoa(ent, cpf)}{HISTORICO}/"
                      f"{_marca(protocolo)}/")
            for chave in antigos:
                self._s3.copy_object(
                    Bucket=self._balde, Key=guarda + chave[len(atual):],
                    CopySource={"Bucket": self._balde, "Key": chave})
            # Só depois de TODOS copiados. Ver o cabeçalho para a ordem.
            for chave in antigos:
                self._s3.delete_object(Bucket=self._balde, Key=chave)
            substituiu = guarda.rstrip("/")[len(ent.apelido) + 1:]

        for nome, corpo in arquivos.items():
            self._gravar(atual + nome, corpo)
        return substituiu

    def acrescentar(self, ent: Entidade, cpf: str, nome: str,
                    corpo: bytes) -> None:
        _conferir(ent, cpf, nomes=[nome])
        self._gravar(self._atual(ent, cpf) + nome, corpo)

    def contar(self, ent: Entidade, cpf: str) -> dict[str, int]:
        _conferir(ent, cpf)
        base = self._da_pessoa(ent, cpf)
        achado: dict[str, int] = {}
        for chave in self._chaves(base):
            resto = chave[len(base):]
            rotulo = ENTREGA if resto.startswith("atual/") else HISTORICO
            achado[rotulo] = achado.get(rotulo, 0) + 1
        return achado

    def apagar(self, ent: Entidade, cpf: str, protocolos) -> int:
        # Os protocolos não mudam nada aqui — no S3 não há área de montagem,
        # tudo dela mora sob o prefixo dela — mas são conferidos do mesmo
        # jeito, para os dois cofres recusarem as mesmas coisas.
        _conferir(ent, cpf, protocolos=list(protocolos))
        chaves = self._chaves(self._da_pessoa(ent, cpf))
        for chave in chaves:
            self._s3.delete_object(Bucket=self._balde, Key=chave)
        return len(chaves)


    def esvaziar(self, ent: Entidade) -> int:
        """Tira TODOS os documentos de um sindicato. Só a demonstração
        chama, ao recomeçar do zero."""
        _conferir(ent, "00000000000")
        # COM A BARRA: `sind/` não é prefixo de `sind-a/`.
        chaves = self._chaves(f"{ent.apelido}/")
        for chave in chaves:
            self._s3.delete_object(Bucket=self._balde, Key=chave)
        return len(chaves)


# ---------------------------------------------------------- configuração

_VARIAVEIS = {
    "endereco": "PROTOCOL_COFRE_ENDERECO",
    "regiao": "PROTOCOL_COFRE_REGIAO",
    "balde": "PROTOCOL_COFRE_BALDE",
    "chave_id": "PROTOCOL_COFRE_CHAVE_ID",
    "segredo": "PROTOCOL_COFRE_SEGREDO",
}


@dataclass(frozen=True)
class Ajuste:
    endereco: str
    regiao: str
    balde: str
    chave_id: str = field(repr=False)
    #: FORA DO `repr`: um ajuste impresso num log de erro não leva a chave.
    segredo: str = field(repr=False)


def ajuste_do_ambiente(amb) -> Ajuste | None:
    """O depósito na nuvem, se configurado. `None` é "use o disco".

    TUDO OU NADA. Quatro variáveis de cinco não é "quase configurado": é um
    servidor que o operador acha que grava na nuvem e grava no disco — que,
    numa hospedagem sem disco permanente, some no reinício. Não sobe.
    """
    valores = {k: (amb.get(v) or "").strip() for k, v in _VARIAVEIS.items()}
    if not any(valores.values()):
        return None
    faltam = [_VARIAVEIS[k] for k, v in valores.items() if not v]
    if faltam:
        raise AjusteRecusado(
            "depósito de documentos configurado pela metade — falta "
            + ", ".join(sorted(faltam)))
    if not valores["endereco"].startswith("https://"):
        raise AjusteRecusado(
            f"{_VARIAVEIS['endereco']} precisa começar com https:// — "
            "documento de filiado não trafega sem cifra")
    if valores["regiao"] not in REGIOES_NO_BRASIL:
        raise AjusteRecusado(
            f"{_VARIAVEIS['regiao']}={valores['regiao']!r} não é uma região "
            "no Brasil — dado de filiado não sai do país. Aceitas: "
            + ", ".join(sorted(REGIOES_NO_BRASIL)))
    return Ajuste(**valores)


_clientes: dict = {}


def padrao(raiz: pathlib.Path, amb=None):
    """O cofre que ESTE processo deve usar, pelo ambiente.

    É O PADRÃO DE TODO MUNDO — servidor e ferramentas de linha de comando —
    e isso é de propósito. Se cada chamador escolhesse, bastaria um esquecer
    para a ferramenta de apagamento olhar o disco, não achar nada e declarar
    "não sobrou documento" com todos eles inteiros na nuvem.
    """
    ajuste = ajuste_do_ambiente(os.environ if amb is None else amb)
    if ajuste is None:
        return NoDisco(raiz)
    # O cliente é reaproveitado: abrir conexão cifrada a cada documento
    # custaria mais que o documento.
    if ajuste not in _clientes:
        _clientes.clear()
        _clientes[ajuste] = abrir(raiz, ajuste)
    return _clientes[ajuste]


def abrir(raiz: pathlib.Path, ajuste: Ajuste | None):
    """O cofre deste servidor: o da nuvem se há ajuste, senão o disco."""
    if ajuste is None:
        return NoDisco(raiz)
    # Importado AQUI: quem usa o disco não carrega a biblioteca da nuvem.
    import boto3
    from boto3.session import Config

    cliente = boto3.client(
        "s3",
        endpoint_url=ajuste.endereco,
        region_name=ajuste.regiao,
        aws_access_key_id=ajuste.chave_id,
        aws_secret_access_key=ajuste.segredo,
        config=Config(
            signature_version="s3v4",
            # `path`: o depósito vai no caminho, não no nome do servidor —
            # é o que a Supabase e os compatíveis esperam.
            s3={"addressing_style": "path"},
            # Um depósito lento não pode prender o pedido de uma pessoa
            # para sempre.
            connect_timeout=10, read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
    return NoS3(cliente, ajuste.balde)
