"""
O retrato da base: o que o gerente do sindicato vê, e é a primeira coisa que
ele vê do produto.

NÃO É "QUEM TEM DIREITO". É o estado da base dele, que é informação que ele
não tem hoje e que sai do arquivo que ele mesmo mandou:

    Você tem 4.812 filiados no acervo.
    NÃO consegue falar com 1.930 deles.

Essa frase é o produto na primeira semana. E por isso este módulo é o que
tem menos licença para errar: um erro de contagem aqui não é defeito de
software, é uma afirmação falsa dita a um diretor de sindicato com a nossa
assinatura.

AS TRÊS REGRAS DE CONTAGEM, cada uma aprendida de um jeito diferente:

**Conta pessoa, não linha.** Planilha de entidade repete pessoa — exportação
concatenada, junção de listas, gente recadastrada. Quem aparece duas vezes,
uma sem e-mail e outra com, é alcançável.

**Divergência não é inalcançabilidade.** Quem aparece duas vezes com cargos
diferentes continua tendo e-mail que funciona. As duas coisas são problemas,
e são problemas diferentes.

**Reenvio não é pessoa nova.** O diário recebe uma linha por envio e nunca é
reescrito. O retrato olha o ÚLTIMO envio de cada CPF, pelo mesmo desenho de
`deposito.reconstruir_manifesto`.

E uma regra de utilidade, não de aritmética: **a falta é nominal.** Contagem
agregada não serve para agir — "faltam 1.930 e-mails" não diz a quem ligar.
Por isso `falta_nominal` existe ao lado de `falta_por_campo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import acervo, validacao

#: Campos que só o PORTAL responde. Nunca são atributo do cadastro do
#: sindicato, então cobrá-los do acervo afirma que registros do diretor estão
#: defeituosos quando nenhum está.
SO_DO_PORTAL: tuple[str, ...] = ("tem_processo",)


@dataclass(frozen=True)
class Retrato:
    """O estado da base, num instante."""

    #: Linhas lidas do acervo. Diferente de `total` quando há repetição, e a
    #: diferença é informação: ela mede a sujeira da exportação.
    linhas: int = 0
    #: Pessoas distintas no acervo. É este o denominador da manchete.
    total: int = 0
    alcancaveis: int = 0
    inalcancaveis: int = 0
    #: Linhas marcadas como divergentes — linhas, não pessoas: são as linhas
    #: que o gerente vai abrir para decidir.
    divergentes: int = 0

    cadastrados: int = 0
    sem_cadastro: int = 0
    #: Quem se cadastrou pelo portal e NÃO está no acervo. Filiado novo que
    #: entrou antes do sindicato reexportar a planilha. Ignorá-lo esconderia
    #: exatamente quem o sindicato quer ver.
    fora_do_acervo: int = 0

    com_processo: int = 0
    nao_sabe_o_processo: int = 0
    sem_processo: int = 0

    acompanhando: int = 0
    #: Processos DISTINTOS a acompanhar. É o que dimensiona a coleta: cada um
    #: custa uma consulta de 22 a 43 s ao DataJud.
    processos_acompanhados: int = 0
    querem_aviso: int = 0

    #: Colunas exigidas que a planilha NÃO trouxe. Diferente de "trouxe e
    #: está vazia", e a diferença é o que o gerente precisa: uma se resolve
    #: reexportando, a outra ligando para a pessoa.
    colunas_ausentes: tuple[str, ...] = ()
    #: Campo -> {cpf: [{campo, acervo, cadastro}]}. Divergência NÃO se resolve
    #: sozinha: marca e mostra, nunca escolhe.
    divergencias: dict[str, list[dict]] = field(default_factory=dict)
    falta_por_campo: dict[str, int] = field(default_factory=dict)
    falta_nominal: dict[str, list[str]] = field(default_factory=dict)
    inalcancaveis_por_cpf: dict[str, str] = field(default_factory=dict)

    @property
    def fracao_inalcancavel(self) -> float:
        return self.inalcancaveis / self.total if self.total else 0.0

    def manchete(self) -> str:
        if not self.total:
            return "O acervo está vazio."
        return (
            f"Você tem {self.total} filiados no acervo. NÃO consegue falar "
            f"com {self.inalcancaveis} deles "
            f"({self.fracao_inalcancavel:.0%})."
        )


def _ultimo_envio_por_cpf(diario: list[dict]) -> dict[str, dict]:
    """O último envio de cada CPF. Uma linha por envio entra; uma por pessoa
    sai — reenvio é correção, não filiado novo."""
    por_cpf: dict[str, dict] = {}
    for registro in diario:
        linha = registro.get("linha")
        if not isinstance(linha, dict):
            continue
        cpf = validacao.so_digitos(linha.get("id_externo") or linha.get("cpf") or "")
        if cpf:
            por_cpf[cpf] = linha
    return por_cpf


def retratar(
    pessoas: list[acervo.Pessoa],
    diario: list[dict] | None = None,
) -> Retrato:
    """Cruza o acervo com o diário de cadastro e devolve o retrato.

    `diario` são os registros de `deposito.ler_diario`. Vazio é estado
    legítimo: é o sindicato que mandou a planilha e ainda não convocou
    ninguém.
    """
    cadastros = _ultimo_envio_por_cpf(diario or [])

    # ---- alcançabilidade, por PESSOA ----
    # Uma pessoa é alcançável se QUALQUER linha dela serve. A chave de quem
    # não tem CPF legível é a linha, para que ela não desapareça na agregação.
    alcanca: dict[str, bool] = {}
    motivo: dict[str, str] = {}
    campos_por_cpf: dict[str, dict[str, str]] = {}
    for p in pessoas:
        # A chave cai para a LINHA sempre que o CPF não serve para
        # identificar — vazio OU inválido. `000.000.000-00` é endêmico em
        # exportação de sindicato, e agrupar por ele fundiria pessoas
        # distintas: as demais sumiriam do denominador E da lista nominal de
        # quem ligar, que é exatamente quem mais precisa ser procurado.
        chave = (
            p.cpf
            if p.cpf and validacao.cpf_valido(p.cpf)
            else f"linha-{p.linha_no_arquivo}"
        )
        alcanca[chave] = alcanca.get(chave, False) or p.alcancavel
        if not p.alcancavel and chave not in motivo:
            motivo[chave] = "; ".join(
                a.detalhe for a in p.achados if a.impede_contato
            )
        # Os campos de todas as linhas da pessoa, com valor preenchido
        # ganhando de vazio: duas linhas incompletas podem se completar.
        acumulado = campos_por_cpf.setdefault(chave, {})
        for coluna, valor in p.campos.items():
            if valor or coluna not in acumulado:
                acumulado[coluna] = valor

    # As chaves do ACERVO, congeladas antes de o diário entrar. Sem isto, o
    # CPF que só existe no diário entra em `campos_por_cpf` e passa a parecer
    # que estava no acervo — e `fora_do_acervo` dá zero sempre.
    chaves_do_acervo = set(campos_por_cpf)

    # As colunas que a planilha REALMENTE trouxe. Coluna ausente não é coluna
    # vazia: uma se resolve reexportando, a outra ligando para a pessoa, e
    # contá-las juntas enchia o topo de "O que falta" com linhas dizendo
    # "= todo mundo".
    colunas_do_acervo = set().union(*(p.campos.keys() for p in pessoas)) \
        if pessoas else set()

    # O cadastro no portal supre o que faltava no acervo: continuar cobrando
    # informação que já chegou mandaria o sindicato atrás do próprio rabo.
    # Mas DIVERGÊNCIA não é suprimento: quando os dois dizem coisas
    # diferentes, marca e mostra — nunca escolhe.
    divergencias: dict[str, list[dict]] = {}
    for cpf, linha in cadastros.items():
        acumulado = campos_por_cpf.setdefault(cpf, {})
        for coluna in validacao.COLUNAS:
            valor = (linha.get(coluna) or "").strip()
            if not valor:
                continue
            anterior = acumulado.get(coluna, "")
            if anterior and anterior != valor:
                divergencias.setdefault(cpf, []).append(
                    {"campo": coluna, "acervo": anterior, "cadastro": valor}
                )
                continue       # o do acervo fica até o sindicato homologar
            acumulado[coluna] = valor
        if cpf in alcanca and (linha.get("email") or "").strip() and \
                validacao.EMAIL.match(linha["email"].strip()):
            # Só promove quem ESTÁ no acervo: o denominador da manchete é o
            # acervo, e quem veio só pelo portal entra em `fora_do_acervo`.
            alcanca[cpf] = True
            motivo.pop(cpf, None)

    fora = [c for c, ok in alcanca.items() if not ok]

    # ---- o que falta, agregado e nominal ----
    exigidas = tuple(
        c for c in validacao.EXIGIDOS
        if c not in SO_DO_PORTAL and (c in colunas_do_acervo or not pessoas)
    )
    ausentes = tuple(sorted(
        c for c in validacao.EXIGIDOS
        if c not in SO_DO_PORTAL and pessoas and c not in colunas_do_acervo
    ))

    falta_por_campo: dict[str, int] = {}
    falta_nominal: dict[str, list[str]] = {}
    for chave in chaves_do_acervo:
        campos = campos_por_cpf.get(chave, {})
        for coluna in exigidas:
            if not campos.get(coluna, "").strip():
                falta_por_campo[coluna] = falta_por_campo.get(coluna, 0) + 1
                falta_nominal.setdefault(coluna, []).append(chave)

    # ---- o que o diário conta ----
    no_acervo = chaves_do_acervo & set(cadastros)
    respostas = {"sim": 0, "nao_sei": 0, "nao": 0}
    acompanhando = 0
    processos: set[str] = set()
    querem_aviso = 0
    for linha in cadastros.values():
        resposta = (linha.get("tem_processo") or "").strip()
        if resposta in respostas:
            respostas[resposta] += 1
        numeros = validacao.numeros_de_acompanhamento(linha.get("acompanhar", ""))
        if numeros:
            acompanhando += 1
            processos.update(numeros)
        if (linha.get("quer_aviso") or "").strip() == "sim":
            querem_aviso += 1

    return Retrato(
        linhas=len(pessoas),
        # O denominador da manchete é o ACERVO. Somar quem veio só pelo
        # portal fazia a tela dizer "Você tem 2 filiados no acervo" ao lado
        # de "Você ainda não enviou a sua base".
        total=len(chaves_do_acervo),
        alcancaveis=len(chaves_do_acervo) - len(fora),
        inalcancaveis=len(fora),
        divergentes=sum(
            1 for p in pessoas
            if any(a.estado == acervo.DIVERGENTE for a in p.achados)
        ),
        cadastrados=len(no_acervo),
        sem_cadastro=len(chaves_do_acervo - set(cadastros)),
        fora_do_acervo=len(set(cadastros) - chaves_do_acervo),
        com_processo=respostas["sim"],
        nao_sabe_o_processo=respostas["nao_sei"],
        sem_processo=respostas["nao"],
        acompanhando=acompanhando,
        processos_acompanhados=len(processos),
        querem_aviso=querem_aviso,
        falta_por_campo=dict(
            sorted(falta_por_campo.items(), key=lambda kv: -kv[1])
        ),
        colunas_ausentes=ausentes,
        divergencias=divergencias,
        falta_nominal=falta_nominal,
        inalcancaveis_por_cpf={c: motivo.get(c, "") for c in fora},
    )
