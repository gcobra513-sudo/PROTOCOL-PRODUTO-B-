"""
Configuração do servidor, lida do ambiente.

PREFIXO: as variáveis deste servidor começam com `PROTOCOL_`; as do motor de
lote começam com `SINDILOTE_`. Dois prefixos num mesmo repositório é um jeito
conhecido de alguém exportar o nome errado e o servidor seguir com o padrão
sem avisar. Por isso `conferir()` reclama em voz alta se encontrar a versão
`SINDILOTE_` de uma variável que é daqui: errar e ser avisado é barato, errar
em silêncio é que custa.

NADA DE SEGREDO COM PADRÃO ÚTIL. Se `PROTOCOL_SEGREDO` não vier do ambiente, o
servidor não inventa um: ele se recusa a subir. Um segredo padrão é o mesmo que
nenhum, com a desvantagem de parecer que existe.
"""

from __future__ import annotations

import os
import pathlib
import secrets
from dataclasses import dataclass, field

# 25 MiB por arquivo. Uma sentença digitalizada grande fica em 5–10 MiB; o
# limite dá folga e ainda barra o envio de vídeo por engano ou de propósito.
LIMITE_ARQUIVO_BYTES = 25 * 1024 * 1024
# Seis arquivos no contrato. O limite do pacote não é 6 × 25 porque ninguém
# manda seis arquivos no máximo do limite; 60 MiB cobre o caso real e corta
# o abuso.
LIMITE_PACOTE_BYTES = 60 * 1024 * 1024

MINUTOS_DO_CODIGO = 15
TENTATIVAS_DO_CODIGO = 5
EMISSOES_POR_CPF_HORA = 3
EMISSOES_POR_ORIGEM_HORA = 20


@dataclass(frozen=True)
class Config:
    raiz: pathlib.Path
    segredo: str
    modo_ensaio: bool
    origens: tuple[str, ...]
    smtp_host: str
    smtp_porta: int
    smtp_usuario: str
    smtp_senha: str
    smtp_remetente: str
    # Quantos códigos a mesma pessoa, e a mesma conexão, podem pedir por hora.
    # Configuráveis porque um sindicato com atendimento presencial — vários
    # filiados atendidos do mesmo computador da sede — bate no limite por
    # origem em meia hora, e aí o portão fecha para quem está na fila.
    emissoes_por_cpf_hora: int = EMISSOES_POR_CPF_HORA
    emissoes_por_origem_hora: int = EMISSOES_POR_ORIGEM_HORA
    #: Recriar a entidade de demonstração ao subir. Necessário onde o disco
    #: não é persistente (plano gratuito), e só funciona em MODO ENSAIO.
    semente_demo: bool = False
    #: Onde este servidor está rodando. Com valor padrão porque `Config` tem
    #: campos obrigatórios posicionais e um campo novo sem padrão quebraria
    #: toda construção existente.
    #:
    #: Entidade REAL só é atendida em região brasileira. Não porque a LGPD
    #: exija armazenamento no Brasil — ela não exige —, mas porque nuvem
    #: estrangeira é transferência internacional, e desde 23/08/2025 isso só
    #: vale com as cláusulas-padrão da ANPD (Res. CD/ANPD 19/2024). Região
    #: brasileira elimina a pergunta em vez de respondê-la.
    regiao: str = ""
    avisos: tuple[str, ...] = field(default=())

    @property
    def tem_remetente(self) -> bool:
        return bool(self.smtp_host and self.smtp_remetente)


class ConfiguracaoInvalida(RuntimeError):
    """Falta algo sem o que o servidor não deve subir."""


# Variáveis daqui que alguém pode exportar com o prefixo do motor por hábito.
_PREFIXO_ERRADO = (
    "SINDILOTE_SEGREDO",
    "SINDILOTE_RAIZ",
    "SINDILOTE_SMTP_HOST",
    "SINDILOTE_ORIGENS",
)


def carregar(ambiente: dict[str, str] | None = None) -> Config:
    amb = dict(os.environ if ambiente is None else ambiente)
    avisos: list[str] = []

    for errada in _PREFIXO_ERRADO:
        if errada in amb:
            certa = errada.replace("SINDILOTE_", "PROTOCOL_", 1)
            avisos.append(
                f"{errada} está no ambiente e NÃO é lida por este servidor. "
                f"O nome certo é {certa}."
            )

    modo_ensaio = amb.get("PROTOCOL_MODO_ENSAIO", "") == "1"

    segredo = amb.get("PROTOCOL_SEGREDO", "").strip()
    if not segredo:
        if not modo_ensaio:
            raise ConfiguracaoInvalida(
                "PROTOCOL_SEGREDO não está definida. Ela assina os códigos de "
                "acesso; sem ela qualquer pessoa forja um. Gere com "
                "`python3 -c \"import secrets;print(secrets.token_urlsafe(32))\"` "
                "e exporte. Para desenvolver sem segredo, exporte "
                "PROTOCOL_MODO_ENSAIO=1 — e aí os códigos aparecem na resposta, "
                "o que não serve para gente de verdade."
            )
        segredo = secrets.token_urlsafe(32)
        avisos.append(
            "MODO ENSAIO: segredo gerado na hora e códigos de acesso "
            "devolvidos na resposta HTTP. Não use com dados de pessoas."
        )

    # NÃO é "dados": essa pasta já existe no repositório com os catálogos
    # públicos do PJe, e parte dela é versionada. Um servidor que grava
    # identidade e procuração de filiado dentro de uma pasta versionada é um
    # `git add .` distraído de distância de virar vazamento. Pasta separada,
    # e `.gitignore` cobrindo ela inteira.
    raiz = pathlib.Path(amb.get("PROTOCOL_RAIZ", "dados_portal")).expanduser()

    regiao = amb.get("PROTOCOL_REGIAO", "").strip()

    origens_cru = amb.get("PROTOCOL_ORIGENS", "").strip()
    if origens_cru:
        origens = tuple(o.strip() for o in origens_cru.split(",") if o.strip())
    elif modo_ensaio:
        origens = ("http://localhost:5173", "http://127.0.0.1:5173")
    else:
        origens = ()
        avisos.append(
            "PROTOCOL_ORIGENS está vazia: nenhum navegador de outra origem "
            "vai conseguir enviar. Defina o endereço do portal."
        )

    smtp_porta_cru = amb.get("PROTOCOL_SMTP_PORTA", "587").strip()
    try:
        smtp_porta = int(smtp_porta_cru)
    except ValueError:
        raise ConfiguracaoInvalida(
            f"PROTOCOL_SMTP_PORTA={smtp_porta_cru!r} não é um número."
        ) from None

    def _inteiro(nome: str, padrao: int) -> int:
        bruto = amb.get(nome, "").strip()
        if not bruto:
            return padrao
        try:
            valor = int(bruto)
        except ValueError:
            raise ConfiguracaoInvalida(f"{nome}={bruto!r} não é um número") from None
        if valor < 1:
            raise ConfiguracaoInvalida(f"{nome} tem que ser pelo menos 1")
        return valor

    cfg = Config(
        regiao=regiao,
        raiz=raiz,
        segredo=segredo,
        modo_ensaio=modo_ensaio,
        origens=origens,
        smtp_host=amb.get("PROTOCOL_SMTP_HOST", "").strip(),
        smtp_porta=smtp_porta,
        smtp_usuario=amb.get("PROTOCOL_SMTP_USUARIO", "").strip(),
        smtp_senha=amb.get("PROTOCOL_SMTP_SENHA", ""),
        smtp_remetente=amb.get("PROTOCOL_SMTP_REMETENTE", "").strip(),
        emissoes_por_cpf_hora=_inteiro(
            "PROTOCOL_EMISSOES_POR_CPF_HORA", EMISSOES_POR_CPF_HORA
        ),
        emissoes_por_origem_hora=_inteiro(
            "PROTOCOL_EMISSOES_POR_ORIGEM_HORA", EMISSOES_POR_ORIGEM_HORA
        ),
        semente_demo=amb.get("PROTOCOL_SEMENTE_DEMO", "") == "1",
        avisos=tuple(avisos),
    )

    if not cfg.tem_remetente and not modo_ensaio:
        raise ConfiguracaoInvalida(
            "Sem PROTOCOL_SMTP_HOST e PROTOCOL_SMTP_REMETENTE o servidor não "
            "tem como entregar o código de acesso, e um portão que não entrega "
            "código é um portão fechado para todo mundo. Configure o envio, ou "
            "suba em PROTOCOL_MODO_ENSAIO=1 para testar sem gente de verdade."
        )

    return cfg
