"""O que o SINDICATO entrega: a planilha da base e os documentos que ele tem.

POR QUE ESTE MÓDULO EXISTE. A ingestão morava dentro de duas ferramentas de
linha de comando, e por isso só entrava no produto pelas mãos de quem tem
acesso ao servidor. Quando a planilha e os documentos passaram a entrar
também pela WEB, o caminho errado seria escrever a rota copiando o miolo das
ferramentas: dois caminhos para a mesma coisa divergem, e o que roda sozinho
é o que ninguém olha — a regra que `agenda.tarefas_padrao` já escreve.

Então o miolo desceu para cá, e a ferramenta e a rota chamam as MESMAS
funções. O que cada uma tem de seu é só a casca: uma imprime, a outra
responde em JSON.

AS TRAVAS QUE VIERAM JUNTO, e que a rota herda sem reescrever:

- quem pediu para sair NÃO volta pela planilha (LGPD art. 18, VI), e sem
  conseguir ler os tombstones NADA é gravado — falha fechada;
- o retrato é recalculado DEPOIS de tirar os apagados, porque ele é
  indexado por CPF;
- o documento do sindicato entra com `origem = 'sindicato'`, que é o que
  impede o reenvio de um filiado de apagá-lo, e com `tem_texto` MEDIDO;
- a planilha LIGA O ACESSO de quem é novo e NÃO troca o e-mail de quem já
  entra (`plano_do_portao`): a troca vira pedido em `trocas.py`.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib

from . import acervo, completude, deposito, rol, trocas, validacao
from . import documentos_do_sindicato as lote
from .entidades import Entidade

ARQUIVO_DO_ACERVO = "acervo.jsonl"


class IngestaoRecusada(Exception):
    """Não deu para gravar com segurança. Nada foi gravado."""


# ------------------------------------------------------------- a planilha

def sem_apagados(pessoas: list, *, banco_url: str, apelido: str,
                 marcador_de) -> tuple[list, int]:
    """(pessoas que podem entrar, quantas foram tiradas por tombstone).

    QUEM PEDIU PARA SAIR NÃO VOLTA PELA PLANILHA. O apagamento a pedido não
    se sustentaria se a próxima planilha do sindicato recriasse a pessoa — e
    ela VAI estar lá, porque a planilha é o cadastro dele e nós não mexemos
    nela.

    FALHA FECHADA: sem conseguir ler os tombstones não dá para saber quem
    pediu para sair, e gravar assim pode ressuscitar alguém. Levanta
    `IngestaoRecusada`.

    Sem banco não há tombstone para consultar, e a lista volta inteira — é o
    modo de arquivo, sem projeção.
    """
    if not banco_url:
        return list(pessoas), 0
    from . import banco

    try:
        marcados = banco.tombstones(banco_url, apelido)
        if not marcados:
            return list(pessoas), 0
        ficam = [p for p in pessoas if marcador_de(p.cpf) not in marcados]
    except Exception as e:  # noqa: BLE001
        raise IngestaoRecusada(
            f"não deu para conferir quem foi apagado a pedido ({e}). Sem "
            f"esta conferência a ingestão pode recriar quem pediu para sair"
        ) from None
    return ficam, len(pessoas) - len(ficam)


@dataclasses.dataclass
class PlanoDoPortao:
    """O que esta planilha muda em QUEM CONSEGUE ENTRAR — e o que não muda.

    Só contagens saem daqui para a resposta: os pares ficam para a gravação.
    """

    #: (cpf, e-mail) de quem não tinha destino no portão. Entra direto.
    novos: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    #: (cpf, e-mail de hoje, e-mail da planilha). NÃO vale: vira pedido.
    trocas: list[tuple[str, str, str]] = dataclasses.field(
        default_factory=list)
    #: quem tinha troca pedida e a planilha voltou a concordar com o portão.
    retiradas: list[str] = dataclasses.field(default_factory=list)
    #: novos sem e-mail que sirva: entram na base e não têm como entrar.
    sem_email: int = 0
    #: a mesma pessoa com dois e-mails na planilha: nenhum é escolhido.
    divergentes: int = 0
    #: trocas que quem opera já recusou, e a planilha continua pedindo.
    recusadas: int = 0
    #: no rol de filiados e fora desta planilha. CONTINUAM entrando.
    fora_da_planilha: int = 0

    def para_json(self) -> dict:
        return {
            "novos": len(self.novos),
            "trocas_aguardando": len(self.trocas),
            "trocas_recusadas": self.recusadas,
            "sem_email": self.sem_email,
            "divergentes": self.divergentes,
            "fora_da_planilha": self.fora_da_planilha,
        }


def plano_do_portao(pasta: pathlib.Path, pessoas: list) -> PlanoDoPortao:
    """Lê a planilha contra o portão de HOJE. Não escreve nada.

    A REGRA INTEIRA: quem já tem destino no portão não muda de destino por
    causa de uma planilha.

    "Já tem destino" olha os DOIS róis, na ordem do portão. Olhar só
    `filiados.csv` deixaria o CPF de um gestor parecer novo — ele entraria
    no rol de filiados com o e-mail da planilha, e como o portão consulta
    esse rol primeiro, o código do gestor passaria a ir para lá.

    A PLANILHA NÃO TIRA NINGUÉM DO ACESSO. Se tirasse, a regra teria porta
    dos fundos: uma planilha sem a pessoa, outra com ela e o e-mail novo, e
    ela voltaria como "nova". Quem sai do acesso sai por quem opera o
    servidor, ou pelo apagamento a pedido.

    `pessoas` tem de ter passado por `sem_apagados`: quem pediu para sair
    não está no rol, e sem o filtro voltaria como novo.

    FALHA FECHADA: com um rol que não dá para ler não se sabe quem já entra,
    e tratar todos como novos seria a troca de e-mail em massa que a regra
    existe para impedir. Levanta `IngestaoRecusada`.
    """
    try:
        try:
            filiados = rol.carregar(pasta).por_cpf
        except rol.RolAusente:
            filiados = {}
        gestores = rol.carregar_gestores(pasta).por_cpf
    except ValueError as e:
        raise IngestaoRecusada(
            f"o cadastro de acesso desta entidade não pôde ser lido ({e}). "
            f"Sem ele não dá para saber quem já entra"
        ) from None
    pedidos = trocas.estado(pasta)

    # Por CPF, os e-mails USÁVEIS que a planilha traz — sem repetir o mesmo
    # endereço escrito com outra caixa.
    por_cpf: dict[str, dict[str, str]] = {}
    for p in pessoas:
        if not validacao.cpf_valido(p.cpf):
            continue
        usaveis = por_cpf.setdefault(p.cpf, {})
        email = (p.campos.get("email") or "").strip()
        if rol.email_serve(email):
            usaveis.setdefault(email.casefold(), email)

    plano = PlanoDoPortao()
    for cpf, usaveis in por_cpf.items():
        atual = filiados.get(cpf) or gestores.get(cpf)
        if len(usaveis) > 1:
            # Divergência não se resolve sozinha — e aqui escolher seria
            # decidir para onde vai a credencial da pessoa.
            plano.divergentes += 1
            continue
        if not usaveis:
            if atual is None:
                plano.sem_email += 1
            continue
        (email,) = usaveis.values()
        if atual is None:
            plano.novos.append((cpf, email))
        elif rol.mesmo_email(atual, email):
            if cpf in pedidos.pendentes:
                plano.retiradas.append(cpf)
        elif pedidos.foi_recusada(cpf, email):
            plano.recusadas += 1
        else:
            plano.trocas.append((cpf, atual, email))
    plano.fora_da_planilha = sum(1 for cpf in filiados if cpf not in por_cpf)
    return plano


def _aplicar_ao_portao(pasta: pathlib.Path, plano: PlanoDoPortao,
                       quem: str) -> None:
    rol.acrescentar(pasta, plano.novos)
    pedidos = trocas.estado(pasta).pendentes
    for cpf, de, para in plano.trocas:
        ja = pedidos.get(cpf)
        # O mesmo pedido de novo não é pedido novo: a planilha é reenviada
        # toda vez que o sindicato atualiza a base.
        if ja and rol.mesmo_email(ja.get("para", ""), para):
            continue
        trocas.pedir(pasta, cpf=cpf, de=de, para=para, quem=quem)
    for cpf in plano.retiradas:
        trocas.retirar(pasta, cpf)


def gravar_planilha(ent: Entidade, raiz: pathlib.Path, pessoas: list, *,
                    origem: str, banco_url: str, marcador_de,
                    quem: str = "") -> dict:
    """Grava a planilha: o arquivo primeiro, o banco depois, o acesso por fim.

    CONFERE DE NOVO QUEM PEDIU PARA SAIR, AQUI, e com o apagamento parado.
    Quem chama já filtrou — mas filtrou para mostrar a prévia, um instante
    (ou vários minutos, no caso da web) antes. Um apagamento que chegasse
    nesse intervalo era desfeito por esta função. `marcador_de` é exigido,
    sem padrão, para que nenhum caminho novo grave sem essa conferência.

    O retrato é calculado sobre o que VAI SER GRAVADO: a primeira versão
    gravava o retrato calculado antes do filtro, e como ele é indexado por
    CPF, cada planilha reenviada escrevia em disco o CPF de quem tinha
    pedido para sair.

    `quem` é o marcador de quem enviou, quando veio pela web. Pela linha de
    comando fica vazio: lá quem roda é o operador, e o registro dele é o do
    servidor.
    """
    pasta = ent.pasta(raiz)
    with deposito.travada(pasta, deposito.TRAVA_DO_APAGAMENTO):
        pessoas, apagadas = sem_apagados(
            pessoas, banco_url=banco_url, apelido=ent.apelido,
            marcador_de=marcador_de)
        feito = _gravar_planilha(ent, pasta, pessoas, origem=origem,
                                 banco_url=banco_url, quem=quem)
    return {**feito, "apagadas": apagadas}


def _gravar_planilha(ent: Entidade, pasta: pathlib.Path, pessoas: list, *,
                     origem: str, banco_url: str, quem: str) -> dict:
    retrato = completude.retratar(pessoas)
    # ANTES de gravar qualquer coisa: se o rol não dá para ler, isto levanta
    # e a planilha não entra pela metade — base nova com acesso velho é o
    # estado em que o sindicato vê a pessoa no painel e ela não entra.
    plano = plano_do_portao(pasta, pessoas)
    registro = {
        "ingerido_em": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "origem": pathlib.PurePath(origem).name,
        "retrato": dataclasses.asdict(retrato),
        "pessoas": [
            {
                "cpf": p.cpf,
                "linha_no_arquivo": p.linha_no_arquivo,
                "campos": p.campos,
                "achados": [
                    {"coluna": a.coluna, "estado": a.estado,
                     "detalhe": a.detalhe}
                    for a in p.achados
                ],
            }
            for p in pessoas
        ],
    }
    if quem:
        registro["enviado_por"] = quem
    deposito.anexar_com_fsync(
        pasta / ARQUIVO_DO_ACERVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )
    projetadas = 0
    if banco_url:
        from . import banco

        projetadas = banco.projetar_acervo(banco_url, ent.apelido, pessoas)
    # O ACESSO POR ÚLTIMO. Se a base falhar acima, ninguém ganha código para
    # entrar num portal que não o conhece; e reenviar a planilha conserta,
    # porque quem já entrou no rol deixa de ser novo.
    _aplicar_ao_portao(pasta, plano, quem)
    return {"retrato": retrato, "projetadas": projetadas,
            "arquivo": pasta / ARQUIVO_DO_ACERVO, "portao": plano}


# ----------------------------------------------------------- os documentos

def cpfs_da_base(banco_url: str, apelido: str,
                 pasta: pathlib.Path) -> set[str]:
    """Quem a entidade declarou atender. Do banco quando há banco; do rol em
    disco quando não há — e o rol é o mínimo, porque é por ele que alguém
    recebe código de acesso."""
    cpfs: set[str] = set()
    if banco_url:
        from . import banco

        for r in banco.base(banco_url, apelido):
            digitos = validacao.so_digitos(r["linha"].get("cpf", ""))
            if digitos:
                cpfs.add(digitos)
    if not cpfs:
        try:
            cpfs = {validacao.so_digitos(k)
                    for k in rol.carregar(pasta).por_cpf}
        except Exception:  # noqa: BLE001
            cpfs = set()
    return {c for c in cpfs if c}


def gravar_documentos(ent: Entidade, raiz: pathlib.Path,
                      resultado: lote.Resultado, banco_url: str) -> int:
    """Grava os documentos que CASARAM. Devolve quantos.

    OS BYTES VÃO PARA A ENTREGA, com o nome do contrato: é a pasta que quem
    confere abre, e ela já tem uma convenção. O documento do sindicato entra
    do mesmo jeito que o do filiado — o que os distingue é `origem`, no
    banco.

    O NOME DO ARQUIVO NO DISCO É CALCULADO AQUI, do tipo: o nome que o
    sindicato deu ao arquivo nunca vira caminho.
    """
    entrega = ent.entrega(raiz)
    gravados = 0
    for cpf, docs in resultado.casados.items():
        destino = entrega / cpf
        destino.mkdir(parents=True, exist_ok=True)
        por_tipo: dict[str, int] = {}
        for d in docs:
            indice = por_tipo.get(d.tipo, 0) + 1
            por_tipo[d.tipo] = indice
            nome = (f"{d.tipo}.pdf" if indice == 1 and d.tipo != lote.OUTRO
                    else f"{d.tipo}-{indice}.pdf")
            (destino / nome).write_bytes(d.corpo)
            gravados += 1

        if banco_url:
            from . import banco

            for d in docs:
                soma = hashlib.sha256(d.corpo).hexdigest()
                # `tem_texto` É MEDIDO, documento por documento: o arquivo
                # casa também pelo CPF no NOME, e um de scanner casa assim
                # sem texto nenhum. Esse espera uma pessoa ler.
                _abre, tem_texto, _n = validacao.examinar_pdf(d.corpo)
                with banco.sessao(banco_url, ent.apelido) as cur:
                    cur.execute(
                        # `origem = 'sindicato'`: é o que impede o reenvio
                        # de um filiado de apagar o que o sindicato entregou.
                        "INSERT INTO documento (entidade, cpf, tipo, sha256,"
                        " tem_texto, origem) "
                        "VALUES (%s,%s,%s,%s,%s,'sindicato') "
                        "ON CONFLICT (entidade, cpf, tipo, sha256) "
                        "DO UPDATE SET tem_texto = EXCLUDED.tem_texto,"
                        " origem = 'sindicato'",
                        (ent.apelido, cpf, d.tipo, soma, tem_texto),
                    )
                banco.guardar_achados(banco_url, ent.apelido, cpf, soma,
                                      d.achados)
    return gravados
