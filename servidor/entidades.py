"""
As entidades (sindicatos) atendidas pelo portal, e o isolamento entre elas.

POR QUE ISTO É UM MÓDULO E NÃO UM `if`: cada entidade tem a sua pasta de
entrega, e um pedido de uma entidade nunca pode escrever na pasta de outra.
Isso não é conforto de arquitetura — é o requisito central. Os documentos de um
filiado do sindicato A não podem aparecer na entrega que o escritório do
sindicato B abre.

Duas regras seguram isso, e as duas são verificadas:

1. o apelido da entidade NÃO vem do pedido: vem do cadastro. O pedido manda um
   apelido, nós procuramos no cadastro, e só o que está cadastrado existe. Um
   apelido como `../outra` não está cadastrado e portanto não existe;
2. o caminho montado é conferido contra a raiz depois de resolvido. Se não
   estiver dentro, levanta. É cinto e suspensório de propósito: a regra 1 já
   bastaria, e é justamente por isso que a 2 nunca deveria disparar — se
   disparar, alguém mexeu na 1.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from dataclasses import dataclass

ARQUIVO = "entidades.json"
# Minúsculas, dígitos e hífen. Sem ponto, sem barra, sem maiúscula: não é
# economia de caracteres, é que nenhum deles pode virar caminho.
APELIDO = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class EntidadeDesconhecida(LookupError):
    """O apelido não está cadastrado. Fim: não há caminho a montar."""


class EntidadeSuspensa(PermissionError):
    """Cadastrada, mas não recebendo. Devolve 403, não 404."""


class CaminhoForaDaRaiz(RuntimeError):
    """A rede de segurança da regra 2. Só dispara se a regra 1 foi burlada."""


#: Slug de categoria: o nome do arquivo em `config/categorias/`, sem `.toml`.
#: Mesma forma do apelido, e pelo mesmo motivo: nenhum caractere daqui pode
#: virar caminho.
SLUG_CATEGORIA = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


@dataclass(frozen=True)
class Entidade:
    apelido: str
    nome: str
    ativa: bool
    escritorio: str
    criada_em: str
    #: As categorias que esta entidade contratou — os slugs dos catálogos de
    #: `config/categorias/`.
    #:
    #: VAZIO É "NENHUMA", NUNCA "TODAS". Um sindicato sem declaração não
    #: recebe veredicto algum, e é o certo: tratar a ausência como "todas"
    #: entregaria a ele o catálogo das outras categorias, que é exatamente o
    #: vazamento entre clientes que o resto do sistema existe para impedir.
    categorias: tuple[str, ...] = ()

    def pasta(self, raiz: pathlib.Path) -> pathlib.Path:
        raiz_abs = raiz.resolve()
        destino = (raiz_abs / self.apelido).resolve()
        if destino != raiz_abs and raiz_abs not in destino.parents:
            raise CaminhoForaDaRaiz(
                f"{destino} não está dentro de {raiz_abs}"
            )
        return destino

    def entrega(self, raiz: pathlib.Path) -> pathlib.Path:
        """A pasta que `ferramentas/conferir_entrega.py` abre, sem adaptação."""
        return self.pasta(raiz) / "entrega"


def _normalizar(bruto: dict) -> dict[str, Entidade]:
    saida: dict[str, Entidade] = {}
    for apelido, dados in bruto.items():
        if not APELIDO.match(apelido):
            # Não ignoramos em silêncio: um apelido inválido no cadastro é um
            # erro de quem cadastrou, e o sindicato ia ficar sem atendimento
            # sem ninguém entender por quê.
            raise ValueError(
                f"apelido {apelido!r} inválido: use minúsculas, dígitos e "
                f"hífen, de 1 a 40 caracteres"
            )
        if not isinstance(dados, dict) or not str(dados.get("nome", "")).strip():
            raise ValueError(f"entidade {apelido!r} está sem nome")
        categorias = dados.get("categorias") or []
        if isinstance(categorias, str):
            categorias = [categorias]
        for slug in categorias:
            if not SLUG_CATEGORIA.match(str(slug)):
                # Em silêncio, um slug torto deixaria o sindicato sem
                # catálogo e ninguém saberia por quê.
                raise ValueError(
                    f"entidade {apelido!r}: categoria {slug!r} inválida: use "
                    f"minúsculas, dígitos e hífen"
                )
        saida[apelido] = Entidade(
            apelido=apelido,
            nome=str(dados["nome"]).strip(),
            ativa=bool(dados.get("ativa", True)),
            escritorio=str(dados.get("escritorio", "")).strip(),
            criada_em=str(dados.get("criada_em", "")).strip(),
            categorias=tuple(str(s) for s in categorias),
        )
    return saida


class Cadastro:
    """Lê `<raiz>/entidades.json`. Recarrega quando o arquivo muda."""

    def __init__(self, raiz: pathlib.Path) -> None:
        self.raiz = raiz
        self._arquivo = raiz / ARQUIVO
        self._entidades: dict[str, Entidade] = {}
        self._assinatura: tuple[float, int] | None = None

    def _carregar_se_mudou(self) -> None:
        try:
            st = self._arquivo.stat()
        except FileNotFoundError:
            self._entidades = {}
            self._assinatura = None
            return
        assinatura = (st.st_mtime, st.st_size)
        if assinatura == self._assinatura:
            return
        bruto = json.loads(self._arquivo.read_text(encoding="utf-8"))
        self._entidades = _normalizar(bruto)
        self._assinatura = assinatura

    def todas(self) -> list[Entidade]:
        self._carregar_se_mudou()
        return sorted(self._entidades.values(), key=lambda e: e.nome)

    def resolver(self, apelido: str) -> Entidade:
        """O único caminho para uma Entidade. Não existe atalho."""
        self._carregar_se_mudou()
        chave = (apelido or "").strip().lower()
        ent = self._entidades.get(chave)
        if ent is None:
            raise EntidadeDesconhecida(chave)
        if not ent.ativa:
            raise EntidadeSuspensa(chave)
        return ent

    def criar(
        self,
        apelido: str,
        nome: str,
        escritorio: str = "",
        categorias: tuple[str, ...] = (),
    ) -> Entidade:
        self._carregar_se_mudou()
        chave = (apelido or "").strip().lower()
        if not APELIDO.match(chave):
            raise ValueError(f"apelido {chave!r} inválido")
        if chave in self._entidades:
            raise ValueError(f"{chave} já existe")
        # REESCREVE O ARQUIVO INTEIRO a partir do que está em memória, e por
        # isso TODO campo de Entidade tem de aparecer aqui. `categorias`
        # ficava de fora: cadastrar o segundo sindicato apagava em silêncio a
        # declaração do primeiro, e o primeiro parava de receber veredicto
        # sem que ninguém tivesse mexido nele.
        bruto = {
            a: {
                "nome": e.nome,
                "ativa": e.ativa,
                "escritorio": e.escritorio,
                "criada_em": e.criada_em,
                "categorias": list(e.categorias),
            }
            for a, e in self._entidades.items()
        }
        bruto[chave] = {
            "nome": nome.strip(),
            "ativa": True,
            "escritorio": escritorio.strip(),
            "criada_em": dt.date.today().isoformat(),
            "categorias": [str(c) for c in categorias],
        }
        self.raiz.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".json.parcial")
        tmp.write_text(
            json.dumps(bruto, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._arquivo)
        self._assinatura = None
        return self.resolver(chave)


# =====================================================================
# QUEM ESTE SERVIDOR PODE ATENDER
# =====================================================================
#
# UMA DECISÃO, NÃO DUAS. As três travas de código viviam dentro de
# `app._entidade`, e `_entidade` só é chamada por rota HTTP. O laço do
# agendador resolvia entidade por `Cadastro.todas()` e não passava por
# nenhuma delas — então o MESMO servidor devolvia 403 para um sindicato e,
# no mesmo processo, lia os dados nominais dele e mandava o e-mail com
# movimentação processual. Achado por auditoria independente.
#
# A regra estava escrita numa porta e não na outra, que é como este tipo de
# defeito nasce sempre. Agora é uma função, e quem tocar dado nominal por
# um caminho novo tem de passar por ela — ou explicar por que não.

#: Apelido de demonstração. A demonstração passa nas três travas porque lá
#: não há dado pessoal: fechá-la não protegeria ninguém.
PREFIXO_DEMO = "demo-"


@dataclass(frozen=True)
class Recusa:
    """Por que este servidor não atende esta entidade.

    `estado` é o código HTTP que o adaptador usa, e mora aqui porque a
    distinção importa: 403 é "este servidor não serve para isto" e 503 é
    "este servidor não está pronto para isto". Quem chama de fora do HTTP
    ignora o campo e usa `motivo`.
    """

    motivo: str       #: curto, para log e registro
    estado: int       #: o código HTTP correspondente
    explicacao: str   #: o texto que vai para quem recebe a resposta


def atendivel(ent: "Entidade", cfg) -> Recusa | None:
    """`None` quando pode atender; a `Recusa` quando não.

    Na ordem: ensaio, região, auditoria. Ensaio primeiro porque em ensaio a
    região é irrelevante — aquele servidor devolve o código de acesso na
    resposta HTTP e recusa entidade real de qualquer jeito, e a mensagem
    dele explica a situação de verdade.
    """
    from . import banco

    real = not ent.apelido.startswith(PREFIXO_DEMO)
    if not real:
        return None

    if cfg.modo_ensaio:
        return Recusa(
            "ensaio", 403,
            f"este servidor está em MODO ENSAIO, e em ensaio o código de "
            f"acesso volta na própria resposta — o que não pode valer para "
            f"pessoas de verdade. Só entidades de demonstração (apelido "
            f"começando com {PREFIXO_DEMO!r}) são atendidas. Para atender "
            f"{ent.apelido!r}, suba o servidor sem PROTOCOL_MODO_ENSAIO e "
            f"configure o envio de e-mail",
        )

    # É de código pelo mesmo motivo que as outras: procedimento se esquece.
    # "Migrar para São Paulo antes do primeiro sindicato" é uma promessa;
    # isto é uma impossibilidade.
    if not banco.regiao_e_brasileira(cfg.regiao):
        return Recusa(
            "regiao", 503,
            f"este servidor roda na região "
            f"{cfg.regiao or '(não declarada)'}, e entidade real só é "
            f"atendida em região brasileira. Dado de filiado em nuvem "
            f"estrangeira é transferência internacional, que desde "
            f"23/08/2025 exige as cláusulas-padrão da ANPD (Res. CD/ANPD "
            f"19/2024). Declare PROTOCOL_REGIAO como uma região brasileira "
            f"({', '.join(sorted(banco.REGIOES_BRASILEIRAS))}), ou atenda "
            f"só entidades de demonstração",
        )

    # E ESTA É SOBRE AUDITORIA. O esquema tem a tabela `leitura` porque num
    # produto de consulta o vazamento é um `read`: sem ela, "quem viu o dado
    # de quem" é pergunta sem resposta, e é a primeira que alguém faz depois
    # de um incidente.
    if not cfg.tem_banco:
        return Recusa(
            "auditoria", 503,
            "este servidor está sem banco de dados, e por isso não registra "
            "quem leu o dado de quem. Entidade real não é atendida assim: o "
            "registro de leitura é o que torna um vazamento investigável. "
            "Defina PROTOCOL_DATABASE_URL, ou atenda só entidades de "
            "demonstração",
        )

    return None
