"""
O portão: emitir um código, conferir o código, abrir uma sessão.

O QUE ESTE BANCO GUARDA, E O QUE NÃO GUARDA

Nada aqui é reversível para a pessoa. O CPF entra como HMAC, o código entra
como HMAC, o token de sessão entra como HMAC — todos com `PROTOCOL_SEGREDO`.
Quem levar este arquivo não sai com uma lista de CPFs nem com um código
utilizável.

Isso NÃO é para esconder o CPF do servidor: a entrega guarda o CPF em claro,
porque ela é o cadastro e tem que ser legível por quem confere. É para que a
tabela de autenticação, que é a que um atacante quer, não seja também um
despejo de dados pessoais.

AS TRÊS CONTAGENS, e o que cada uma impede

1. **tentativas por código** (5): impede adivinhar seis dígitos por força
   bruta. Na 5ª errada o código morre — não "espera um pouco", morre. Pedir
   outro é barato para quem é dono do e-mail e caro para quem não é;
2. **emissões por CPF por hora** (3): impede usar o portal como máquina de
   mandar e-mail para a caixa de outra pessoa. Esgotada a cota, a recusa
   vale **só enquanto existe um código vivo** para aquele CPF — porque a
   rota é anônima e o teto é contado pelo CPF da VÍTIMA: três pedidos de um
   terceiro trancavam uma pessoa nomeada fora da única porta do produto.
   Com código vivo, recusar é honesto (ela o tem na caixa); sem código
   vivo, recusar não protege ninguém;
3. **emissões por origem por hora** (20): impede varrer CPFs para descobrir
   quem é filiado. Sem ela, a resposta "não está no rol" entrega o rol inteiro
   a quem tiver paciência.

E, pelo mesmo motivo da 3: a resposta de emissão é **a mesma** para quem está
no rol e para quem não está. Quem não está simplesmente não recebe e-mail.
Dizer "este CPF não é filiado" seria responder a pergunta que o atacante veio
fazer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import pathlib
import secrets
import sqlite3
from dataclasses import dataclass

from .config import (
    EMISSOES_POR_CPF_HORA,
    EMISSOES_POR_ORIGEM_HORA,
    MINUTOS_DO_CODIGO,
    TENTATIVAS_DO_CODIGO,
)
from .validacao import so_digitos

ARQUIVO = "acesso.sqlite3"
HORAS_DA_SESSAO = 4

ESQUEMA = """
CREATE TABLE IF NOT EXISTS codigos (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  entidade      TEXT NOT NULL,
  cpf_hash      TEXT NOT NULL,
  codigo_hash   TEXT NOT NULL,
  criado_em     TEXT NOT NULL,
  expira_em     TEXT NOT NULL,
  tentativas    INTEGER NOT NULL DEFAULT 0,
  usado_em      TEXT
);
CREATE INDEX IF NOT EXISTS ix_codigos_busca
  ON codigos (entidade, cpf_hash, expira_em);

CREATE TABLE IF NOT EXISTS sessoes (
  token_hash    TEXT PRIMARY KEY,
  entidade      TEXT NOT NULL,
  cpf_hash      TEXT NOT NULL,
  criado_em     TEXT NOT NULL,
  expira_em     TEXT NOT NULL,
  usado_em      TEXT
);

CREATE TABLE IF NOT EXISTS emissoes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  origem_hash   TEXT NOT NULL,
  criado_em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_emissoes_origem
  ON emissoes (origem_hash, criado_em);
"""


class ExcessoDeTentativas(PermissionError):
    """Barrado por contagem. A mensagem diz qual, sem dizer se o CPF existe."""


class CodigoInvalido(PermissionError):
    """Não existe, expirou, já foi usado ou errou. De propósito indistinguível."""


class SessaoInvalida(PermissionError):
    """Token ausente, expirado ou já gasto."""


@dataclass(frozen=True)
class Sessao:
    entidade: str
    cpf_hash: str


def _agora() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(momento: dt.datetime) -> str:
    return momento.isoformat(timespec="seconds")


def marcar_com(segredo, valor: str) -> str:
    """HMAC do valor com o segredo. Aceita `str` ou `bytes` no segredo."""
    if isinstance(segredo, str):
        segredo = segredo.encode("utf-8")
    return hmac.new(
        segredo, (valor or "").encode("utf-8"), hashlib.sha256
    ).hexdigest()


def marcador_de_cpf(segredo, cpf: str) -> str:
    """O marcador de um CPF, sem abrir nem CRIAR banco de acesso.

    POR QUE ISTO É FUNÇÃO DE MÓDULO: `Portao.__init__` faz `mkdir` e roda o
    esquema SQLite. Quem só precisa reconhecer um tombstone — a ingestão da
    planilha, por exemplo — pagava um diretório e um banco por um HMAC, no
    disco do sindicato. E pior: o hábito de construir um portão descartável
    para "ter o marcador" levou a ferramenta de apagamento a REVOGAR SESSÃO
    NO BANCO ERRADO, deixando a sessão da pessoa viva enquanto imprimia que
    nada sobrou. O marcador depende só do segredo; o resto do portão, não.
    """
    return marcar_com(segredo, so_digitos(cpf))


class Portao:
    def __init__(
        self,
        raiz: pathlib.Path,
        segredo: str,
        emissoes_por_cpf_hora: int = EMISSOES_POR_CPF_HORA,
        emissoes_por_origem_hora: int = EMISSOES_POR_ORIGEM_HORA,
    ) -> None:
        self.raiz = raiz
        self._segredo = segredo.encode("utf-8")
        self._por_cpf = emissoes_por_cpf_hora
        self._por_origem = emissoes_por_origem_hora
        raiz.mkdir(parents=True, exist_ok=True)
        self._caminho = raiz / ARQUIVO
        with self._conectar() as cx:
            cx.executescript(ESQUEMA)

    def _conectar(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self._caminho, timeout=10, isolation_level=None)
        # WAL para dois processos do uvicorn não se trancarem na leitura.
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=FULL")
        return cx

    def marcar(self, valor: str) -> str:
        """HMAC com o segredo. Sem o segredo não se recalcula o marcador."""
        return marcar_com(self._segredo, valor)

    def marcar_cpf(self, cpf: str) -> str:
        """O marcador de um CPF, SEMPRE pelos 11 dígitos.

        Delega a `marcador_de_cpf` para haver UM cálculo só. Dois jeitos de
        calcular o mesmo HMAC é um jeito a mais de errar, e marcador
        diferente faz o tombstone não casar com o CPF que chega.

        Existe porque não existir custou um defeito: a emissão marcava
        "52601815906" e a conferência marcava "526.018.159-06". Mesmo CPF,
        marcador diferente, e o portão recusava a pessoa certa — ou seja,
        recusaria todo mundo que digitasse com ponto, que é como as pessoas
        digitam. Marcar CPF por este método é a única forma permitida.
        """
        return marcador_de_cpf(self._segredo, cpf)

    # ---------------------------------------------------------------- emitir

    def _contar(self, cx, sql: str, parametros: tuple) -> int:
        return int(cx.execute(sql, parametros).fetchone()[0])

    def emitir(
        self, entidade: str, cpf: str, origem: str
    ) -> str:
        """Gera e devolve o código. Quem chama decide a quem entregar.

        Devolver o código aqui é de propósito: este módulo não sabe e não quer
        saber o e-mail da pessoa. Quem sabe é o rol, e quem entrega é o
        remetente. Juntar as três coisas num método só seria o jeito mais
        rápido de, num refatoramento futuro, mandar o código para o e-mail que
        o navegador pediu.
        """
        agora = _agora()
        limite = _iso(agora - dt.timedelta(hours=1))
        cpf_hash = self.marcar_cpf(cpf)
        origem_hash = self.marcar(origem)

        with self._conectar() as cx:
            cx.execute("BEGIN IMMEDIATE")
            por_origem = self._contar(
                cx,
                "SELECT COUNT(*) FROM emissoes "
                "WHERE origem_hash = ? AND criado_em >= ?",
                (origem_hash, limite),
            )
            if por_origem >= self._por_origem:
                raise ExcessoDeTentativas(
                    "muitos pedidos de código desta conexão na última hora"
                )
            por_cpf = self._contar(
                cx,
                "SELECT COUNT(*) FROM codigos "
                "WHERE entidade = ? AND cpf_hash = ? AND criado_em >= ?",
                (entidade, cpf_hash, limite),
            )
            if por_cpf >= self._por_cpf:
                # RECUSA SÓ ENQUANTO EXISTE CÓDIGO VIVO.
                #
                # Este teto é contado por `cpf_hash`, e a rota que o aciona
                # é anônima: quem pede não prova relação nenhuma com aquele
                # CPF. Então um terceiro gastava a cota de um filiado
                # nomeado com três pedidos — e o bloqueio era completo, não
                # uma corrida, porque as janelas não se encaixavam: o
                # código vale 15 minutos e a contagem olha 60. Do minuto 15
                # ao 60 a pessoa não tinha código válido E não conseguia
                # emitir outro. Este portão é a única porta do produto.
                #
                # Recusar com um código vivo na caixa dela é honesto: ela
                # TEM o que precisa, e o teto segue protegendo a caixa de
                # ser usada como máquina de mandar e-mail — que é o que o
                # cabeçalho deste módulo diz que ele protege. Recusar SEM
                # código vivo não protege ninguém: só tranca o dono.
                vivos = self._contar(
                    cx,
                    "SELECT COUNT(*) FROM codigos WHERE entidade = ? "
                    "AND cpf_hash = ? AND usado_em IS NULL AND expira_em >= ?",
                    (entidade, cpf_hash, _iso(agora)),
                )
                if vivos:
                    raise ExcessoDeTentativas(
                        "já enviamos um código para o e-mail que o cadastro "
                        "tem, e ele ainda vale; confira a sua caixa de "
                        "entrada e o spam"
                    )

            # Seis dígitos, sorteados com secrets. `randint` do módulo random
            # é previsível e aqui o número é credencial.
            codigo = f"{secrets.randbelow(1_000_000):06d}"
            # Os códigos anteriores do mesmo CPF morrem: dois códigos válidos
            # ao mesmo tempo dobram a chance de acerto de quem adivinha.
            cx.execute(
                "UPDATE codigos SET usado_em = ? "
                "WHERE entidade = ? AND cpf_hash = ? AND usado_em IS NULL",
                (_iso(agora), entidade, cpf_hash),
            )
            cx.execute(
                "INSERT INTO codigos "
                "(entidade, cpf_hash, codigo_hash, criado_em, expira_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    entidade,
                    cpf_hash,
                    self.marcar(codigo),
                    _iso(agora),
                    _iso(agora + dt.timedelta(minutes=MINUTOS_DO_CODIGO)),
                ),
            )
            cx.execute(
                "INSERT INTO emissoes (origem_hash, criado_em) VALUES (?, ?)",
                (origem_hash, _iso(agora)),
            )
            cx.execute("COMMIT")
        return codigo

    # --------------------------------------------------------------- conferir

    def conferir(self, entidade: str, cpf: str, codigo: str) -> str:
        """Confere o código e devolve o token da sessão."""
        agora = _agora()
        cpf_hash = self.marcar_cpf(cpf)
        with self._conectar() as cx:
            cx.execute("BEGIN IMMEDIATE")
            linha = cx.execute(
                "SELECT id, codigo_hash, tentativas FROM codigos "
                "WHERE entidade = ? AND cpf_hash = ? AND usado_em IS NULL "
                "AND expira_em >= ? ORDER BY id DESC LIMIT 1",
                (entidade, cpf_hash, _iso(agora)),
            ).fetchone()
            if linha is None:
                cx.execute("COMMIT")
                raise CodigoInvalido("código inválido ou expirado")

            ident, esperado, tentativas = linha
            if tentativas + 1 >= TENTATIVAS_DO_CODIGO and not hmac.compare_digest(
                esperado, self.marcar(codigo)
            ):
                # Queima o código na última tentativa errada.
                cx.execute(
                    "UPDATE codigos SET tentativas = ?, usado_em = ? "
                    "WHERE id = ?",
                    (tentativas + 1, _iso(agora), ident),
                )
                cx.execute("COMMIT")
                raise ExcessoDeTentativas(
                    "código errado vezes demais; peça um novo"
                )

            if not hmac.compare_digest(esperado, self.marcar(codigo)):
                cx.execute(
                    "UPDATE codigos SET tentativas = ? WHERE id = ?",
                    (tentativas + 1, ident),
                )
                cx.execute("COMMIT")
                raise CodigoInvalido("código inválido ou expirado")

            token = secrets.token_urlsafe(32)
            cx.execute(
                "UPDATE codigos SET usado_em = ? WHERE id = ?",
                (_iso(agora), ident),
            )
            cx.execute(
                "INSERT INTO sessoes "
                "(token_hash, entidade, cpf_hash, criado_em, expira_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    self.marcar(token),
                    entidade,
                    cpf_hash,
                    _iso(agora),
                    _iso(agora + dt.timedelta(hours=HORAS_DA_SESSAO)),
                ),
            )
            cx.execute("COMMIT")
        return token

    # ---------------------------------------------------------------- sessão

    def abrir_sessao(self, token: str, *, para_enviar: bool = False) -> Sessao:
        """A sessão deste token, ou `SessaoInvalida`.

        `para_enviar` é a pergunta do cadastro: esta sessão ainda pode
        ENVIAR? Uma sessão que já enviou continua valendo para LER até
        expirar. Antes ela morria inteira, e quem acabava de se cadastrar
        precisava de outro código para ver as próprias ações — medido em
        12/11/2026: quatro áreas, quatro códigos, contra um limite de três
        por hora.
        """
        agora = _iso(_agora())
        ainda_nao_enviou = " AND usado_em IS NULL" if para_enviar else ""
        with self._conectar() as cx:
            linha = cx.execute(
                "SELECT entidade, cpf_hash FROM sessoes "
                "WHERE token_hash = ? AND expira_em >= ?" + ainda_nao_enviou,
                (self.marcar(token or ""), agora),
            ).fetchone()
        if linha is None:
            raise SessaoInvalida("sessão inválida ou expirada")
        return Sessao(entidade=linha[0], cpf_hash=linha[1])

    def encerrar_sessao(self, token: str) -> None:
        """"Sair". Apaga a sessão no servidor: tirar o token só da tela
        deixaria a credencial valendo por horas para quem a achasse. Token
        que não existe não é erro — e não pode ser, senão a rota vira jeito
        de testar se um token vale."""
        with self._conectar() as cx:
            cx.execute("DELETE FROM sessoes WHERE token_hash = ?",
                       (self.marcar(token or ""),))

    def gastar_sessao(self, token: str) -> None:
        """Um token vale um ENVIO. Reenvio começa de novo pelo código.

        Sem isto, um token vazado permite reenviar o cadastro de alguém quantas
        vezes quiser pelas próximas quatro horas — e cada reenvio substitui os
        documentos da pessoa. O que se gasta é o envio, não a leitura: ver
        `abrir_sessao`.
        """
        with self._conectar() as cx:
            cx.execute(
                "UPDATE sessoes SET usado_em = ? WHERE token_hash = ?",
                (_iso(_agora()), self.marcar(token or "")),
            )

    def confere_com(self, sessao: Sessao, cpf: str) -> bool:
        """O CPF enviado é o mesmo que abriu a sessão?

        O token diz quem a pessoa é. O formulário diz de quem é o cadastro. Se
        os dois não baterem, alguém entrou com o próprio código e está
        cadastrando outra pessoa.
        """
        return hmac.compare_digest(sessao.cpf_hash, self.marcar_cpf(cpf))


    def esquecer(self, entidade: str, cpf: str) -> int:
        """Apaga do portão tudo o que aponta para esta pessoa, e REVOGA a
        sessão aberta dela. Devolve quantas linhas saíram.

        A REVOGAÇÃO É O PONTO, não a limpeza. Um token de sessão vale 4
        horas (`HORAS_DA_SESSAO`), e sem isto ele continuava valendo depois
        do apagamento: quem o tivesse na mão mandava um cadastro novo, e
        `POST /api/cadastro` reprojetava a pessoa inteira. O mecanismo
        escolhido para o apagamento — não entregar código NOVO — era
        contornável por até quatro horas com a credencial já emitida.

        `emissoes` não entra: ela é indexada por origem (a conexão), não por
        pessoa, e não guarda nada que aponte para alguém.
        """
        marca = self.marcar_cpf(cpf)
        saiu = 0
        with self._conectar() as cx:
            cx.execute("BEGIN IMMEDIATE")
            for tabela in ("codigos", "sessoes"):
                cur = cx.execute(
                    f"DELETE FROM {tabela} "
                    f"WHERE entidade = ? AND cpf_hash = ?",
                    (entidade, marca),
                )
                saiu += cur.rowcount
            cx.execute("COMMIT")
        return saiu


    def marcadores_de(self, entidade: str, cpf: str) -> int:
        """Quantas linhas do portão ainda apontam para esta pessoa.

        Existe para a varredura do apagamento poder MEDIR o portão sem
        importar este módulo nem conhecer o esquema dele.
        """
        marca = self.marcar_cpf(cpf)
        with self._conectar() as cx:
            return sum(
                cx.execute(
                    f"SELECT count(*) FROM {t} "
                    f"WHERE entidade = ? AND cpf_hash = ?",
                    (entidade, marca),
                ).fetchone()[0]
                for t in ("codigos", "sessoes")
            )
