"""Apagamento a pedido — LGPD art. 18, VI.

QUEM ACIONA É O SINDICATO. Ele tem a relação com o filiado e foi ele que nos
confiou o dado; sob a LGPD ele tende a ser o CONTROLADOR e nós o operador, e
é o controlador que responde ao titular.

ESTE MÓDULO NÃO DECLARA, ELE MEDE. Não existe campo `apagado = true` no
esquema, e a ausência é deliberada: um campo desses é uma AFIRMAÇÃO.

E A MEDIÇÃO JÁ FALHOU UMA VEZ, o que vale mais que o princípio. A primeira
versão varria POR CPF — tabela com coluna `cpf`, pasta chamada `<cpf>` — e
devolvia VAZIO com dado pessoal em quatro lugares, porque dado pessoal
também mora onde o CPF não é índice:

- **chave de dicionário**: o `retrato` do `acervo.jsonl` tem o CPF como
  CHAVE de `inalcancaveis_por_cpf` e de `divergencias`, e como ITEM de
  `falta_nominal`. Um comentário meu afirmava que o `retrato` é "sobre o
  ARQUIVO e não sobre gente". Era falso;
- **pasta indexada por protocolo**: `.parcial/<protocolo>/` guarda os PDFs
  de um envio que caiu entre montar e trocar;
- **arquivo por raiz, não por entidade**: `codigos_enviados.log` e
  `mensagens_enviadas.log`;
- **banco que não é o Postgres**: o `acesso.sqlite3` do portão, onde a
  SESSÃO ABERTA continuava valendo — e com ela o apagamento era reversível
  por até quatro horas para quem tivesse o token.

Por isso a varredura tem DUAS camadas: os lugares nomeados, e uma VARREDURA
DE BYTES nos arquivos de texto sob a raiz. A segunda é a rede: o que ela não
conhece, ela acha de qualquer jeito. O que ela NÃO pega é conteúdo binário
comprimido — um CPF dentro de um PDF —, e é por isso que as pastas por CPF
continuam sendo olhadas por caminho.

Spec: `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`
"""
from __future__ import annotations

import contextlib
import pathlib
import shutil

from . import acervo, banco, conferencia, deposito, rol, trocas, validacao
from .entidades import Entidade

#: Extensões que a varredura de bytes abre. PDF fica de fora de propósito: o
#: conteúdo pode estar comprimido, um `grep` não o acha, e varrer megabytes
#: de binário por nada custaria a cada conferência. Os PDFs são cobertos por
#: CAMINHO, que é o que o produto controla.
_TEXTO = {".csv", ".json", ".jsonl", ".log", ".txt", ".md", ""}

#: Teto por arquivo na varredura. Um diário de sindicato grande passa de
#: centenas de MB, e abrir tudo a cada conferência não se paga.
_TETO_VARREDURA = 64 * 1024 * 1024

#: Teto de `motivo` e `pedido_por`. As colunas são `text` sem limite e o teto
#: de corpo HTTP é dimensionado para PDF, então sem isto o registro de um
#: apagamento aceita megabytes de texto. 500 cabe num motivo de verdade
#: ("pedido do titular por e-mail em 02/11/2026, protocolo interno 1234") com
#: folga larga.
#:
#: QUEM PASSA DO TETO É RECUSADO, NÃO CORTADO. Cortar em silêncio guardaria
#: no registro legal algo diferente do que o gestor escreveu — e é esse
#: registro que responde quem mandou apagar e por quê.
TETO_DO_TEXTO = 500


def vestigios(url: str, ent: Entidade, raiz: pathlib.Path, cpf: str, *,
              portao, email: str = "") -> list[str]:
    """O que AINDA existe desta pessoa, em qualquer lugar.

    Vazio é a única prova aceitável de que o apagamento terminou, e é o que
    o sindicato usa para responder ao titular dentro dos 15 dias da lei.
    Por isso medir pela metade é pior que declarar: uma declaração se
    desconfia, uma medição se acredita.

    RECUSA MEDIR SEM BANCO E SEM PORTÃO, e isto é a correção de um defeito
    meu. Antes, `url` vazia pulava o banco e `portao=None` pulava os códigos
    e sessões — os dois EM SILÊNCIO, com os dois pulos anotados aqui no
    docstring. Docstring não é medição: a lista voltava vazia, e o jeito
    mais fácil de obter "nada sobrou" passava a ser medir menos. Os dois
    caminhos de produção sempre passaram os dois argumentos, então recusar
    não tira capacidade de ninguém — tira a possibilidade de uma resposta ao
    titular apoiada em meia medição.

    `email` permite varrer os logs do remetente de arquivo, que guardam o
    endereço e não o CPF. Quem chama captura o e-mail ANTES de tirar o rol.
    """
    if not url:
        raise ValueError(
            "não dá para medir o apagamento sem o banco: as tabelas de "
            "consulta são o lugar com mais cópias da pessoa, e lista vazia "
            "sem conferi-las afirmaria um apagamento não medido"
        )
    if portao is None:
        raise ValueError(
            "não dá para medir o apagamento sem o portão: o código e a "
            "sessão de acesso sobrevivem ao resto, e uma sessão viva torna "
            "o apagamento reversível por horas"
        )
    digitos = validacao.so_digitos(cpf)
    achados: list[str] = []
    if len(digitos) != 11:
        return achados
    marca = portao.marcar_cpf(digitos)[:12]
    pasta = ent.pasta(raiz)

    with banco.sessao(url, ent.apelido) as cur:
        for tabela in banco._TABELAS_DO_APAGAMENTO:
            cur.execute(
                f"SELECT count(*) FROM {tabela} WHERE cpf = %s",
                (digitos,),
            )
            quantas = cur.fetchone()[0]
            if quantas:
                achados.append(
                    f"banco: {quantas} linha(s) em {tabela} ({marca})"
                )

    # O PORTÃO. Não é só dado parado: a linha de `sessoes` é um token de
    # portador vivo, e com ele a pessoa volta inteira num só pedido.
    quantas = portao.marcadores_de(ent.apelido, digitos)
    if quantas:
        achados.append(
            f"portão: {quantas} linha(s) de código/sessão ({marca})"
        )

    # OS LUGARES NOMEADOS. Dão o RÓTULO, que é o que o operador usa para
    # consertar. A varredura de bytes, adiante, é a rede — e ela PULA o que
    # já foi nomeado aqui, para não transformar um diagnóstico preciso
    # ("rol: linha em filiados.csv") num genérico ("texto: CPF em ...").
    cobertos: set[pathlib.Path] = set()

    diario = pasta / deposito.DIARIO
    cobertos.add(diario)
    for registro in deposito.ler_diario(pasta):
        linha = registro.get("linha")
        if (isinstance(linha, dict)
                and validacao.so_digitos(linha.get("cpf") or "") == digitos):
            achados.append(
                f"diário: envio {registro.get('protocolo', '?')} com "
                f"conteúdo ({marca})"
            )

    # O ROL PELA PRESENÇA DO CPF NA LINHA, não por `email_de`.
    #
    # A primeira versão perguntava `rol.carregar(pasta).email_de(cpf)`, e
    # isso é `None` para quem está no arquivo SEM e-mail válido — pessoa que
    # `_carregar` aceita na linha e deixa fora de `por_cpf`. Resultado: nome
    # e CPF no `filiados.csv`, e a varredura dizia que não sobrou nada.
    for nome_do_rol in (rol.ARQUIVO, rol.ARQUIVO_GESTORES):
        caminho = pasta / nome_do_rol
        cobertos.add(caminho)
        if caminho.is_file() and _procurar(caminho, digitos, ""):
            achados.append(f"rol: linha em {nome_do_rol} ({marca})")

    # AS LEITURAS HUMANAS. O arquivo guarda o CPF e o que a sentença da
    # pessoa diz, lido pelo gestor. A varredura de bytes o acharia de
    # qualquer jeito; nomeá-lo aqui dá o rótulo que o operador usa.
    leituras = pasta / conferencia.ARQUIVO
    cobertos.add(leituras)
    if leituras.is_file() and _procurar(leituras, digitos, ""):
        achados.append(f"leituras: registro de leitura humana ({marca})")

    # AS TROCAS DE E-MAIL PEDIDAS. CPF e dois e-mails, num arquivo que
    # nasceu depois do apagamento — o tipo de lugar que ele esquece.
    pedidos = pasta / trocas.ARQUIVO
    cobertos.add(pedidos)
    if pedidos.is_file() and _procurar(pedidos, digitos, ""):
        achados.append(f"trocas: pedido de troca de e-mail ({marca})")

    # O ACERVO, pessoas E retrato. O `retrato` é indexado por CPF em três
    # campos, e foi a cegueira que a caça adversarial achou.
    acervo_jsonl = pasta / "acervo.jsonl"
    cobertos.add(acervo_jsonl)
    if acervo_jsonl.is_file() and _procurar(acervo_jsonl, digitos, ""):
        achados.append(f"acervo: linha de planilha ou retrato ({marca})")

    manifesto = ent.entrega(raiz) / deposito.MANIFESTO
    cobertos.add(manifesto)
    if manifesto.is_file() and _procurar(manifesto, digitos, ""):
        achados.append(f"manifesto: linha em {deposito.MANIFESTO} ({marca})")

    # AS PASTAS POR CAMINHO, que é o que pega os PDFs.
    for rotulo, alvo in (
        ("entrega", ent.entrega(raiz) / digitos),
        ("historico", pasta / deposito.HISTORICO / digitos),
    ):
        if alvo.is_dir():
            quantos = sum(1 for f in alvo.rglob("*") if f.is_file())
            achados.append(f"{rotulo}: {quantos} arquivo(s) ({marca})")

    # A ÁREA DE MONTAGEM, indexada por PROTOCOLO e não por CPF. Um envio que
    # caiu entre montar e trocar deixa a sentença ali. `depositar` escreve o
    # diário ANTES de montar, então todo protocolo em `.parcial` tem registro
    # — e registro redigido é de alguém que foi apagado.
    montagem = pasta / deposito.PARCIAL
    if montagem.is_dir():
        redigidos = {r.get("protocolo") for r in deposito.ler_diario(pasta)
                     if r.get("apagado_em")}
        for sub in sorted(montagem.iterdir()):
            if sub.is_dir() and sub.name in redigidos:
                quantos = sum(1 for f in sub.rglob("*") if f.is_file())
                achados.append(
                    f"montagem: {quantos} arquivo(s) em "
                    f".parcial/{sub.name} de envio apagado"
                )

    # A VARREDURA DE BYTES, a rede que pega o que eu não soube nomear: o
    # `retrato` do acervo, o manifesto, o rol de qualquer formato, e os logs
    # do remetente de arquivo na raiz.
    for caminho in _arquivos_de_texto(pasta, raiz):
        if caminho in cobertos:
            continue
        encontrado = _procurar(caminho, digitos, email)
        if encontrado:
            try:
                onde = caminho.relative_to(raiz)
            except ValueError:
                onde = caminho
            achados.append(f"texto: {encontrado} em {onde} ({marca})")

    return achados


def _arquivos_de_texto(pasta: pathlib.Path, raiz: pathlib.Path):
    """Os arquivos de texto da entidade, MAIS os logs da raiz.

    Os logs ficam na raiz e não na pasta da entidade (`remetente.py`), e foi
    por isso que a primeira varredura não os viu: ela só olhava a entidade.
    """
    candidatos: list[pathlib.Path] = []
    if pasta.is_dir():
        candidatos += [f for f in pasta.rglob("*") if f.is_file()]
    candidatos += [raiz / "codigos_enviados.log",
                   raiz / "mensagens_enviadas.log"]
    for caminho in candidatos:
        try:
            if (caminho.is_file() and caminho.suffix.lower() in _TEXTO
                    and caminho.stat().st_size <= _TETO_VARREDURA):
                yield caminho
        except OSError:
            continue


def _procurar(caminho: pathlib.Path, digitos: str, email: str) -> str:
    """Diz O QUE achou, nunca o valor. Vestígio com o CPF dentro seria um
    segundo lugar com dado pessoal — e esta lista vai para uma resposta."""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if digitos in texto:
        return "CPF"
    if email and email in texto:
        return "e-mail"
    return ""


@contextlib.contextmanager
def se_ainda_esta(url: str, ent: Entidade, raiz: pathlib.Path, cpf: str):
    """Para quem roda sozinho e grava POR PESSOA: segura a trava do
    apagamento e entrega `True` se a pessoa ainda está na base.

        with apagamento.se_ainda_esta(url, ent, raiz, cpf) as esta:
            if not esta:
                continue        # saiu a pedido no meio da rodada
            ...gravar, ou mandar o e-mail...

    AS TAREFAS AGENDADAS leem a base no começo e agem pessoa por pessoa
    depois — minutos, numa base grande. Medido em 12/11/2026: quem era
    apagado nesse intervalo recebia o e-mail de aviso assim mesmo, e tinha
    o veredicto guardado. A conferência tem de ser FEITA DE NOVO na hora de
    agir, e com o apagamento parado: conferir e soltar a trava antes de
    gravar deixaria a mesma janela, só que menor.

    A trava é por pessoa, e não pela rodada inteira, para um apagamento
    pedido no painel esperar um e-mail, e não quatro mil.
    """
    with deposito.travada(ent.pasta(raiz), deposito.TRAVA_DO_APAGAMENTO):
        yield banco.pessoa_esta_na_base(url, ent.apelido, cpf)


def apagar(url: str, ent: Entidade, raiz: pathlib.Path, cpf: str, *,
           motivo: str, pedido_por: str, portao) -> dict:
    """Apaga esta pessoa de tudo, e CONFERE no fim — com a planilha parada.

    A trava é a mesma que `ingestao.gravar_planilha` segura: uma planilha
    que conferiu os apagados antes e gravasse depois devolveria a pessoa.
    O porquê está em `deposito.TRAVA_DO_APAGAMENTO`.
    """
    with deposito.travada(ent.pasta(raiz), deposito.TRAVA_DO_APAGAMENTO):
        return _apagar(url, ent, raiz, cpf, motivo=motivo,
                       pedido_por=pedido_por, portao=portao)


def _apagar(url: str, ent: Entidade, raiz: pathlib.Path, cpf: str, *,
            motivo: str, pedido_por: str, portao) -> dict:
    """O apagamento em si. Quem chama é `apagar`, com a trava tomada.

    A ORDEM É O DESENHO, e cada passo está onde está por um motivo:

    1. **O TOMBSTONE, commitado sozinho.** É ele que torna a operação
       retomável e que ativa o bloqueio de reingestão imediatamente. Na
       mesma transação das exclusões, uma falha o desfaria junto — a pessoa
       teria pedido para sair, o processo teria caído, e não haveria
       registro de que alguém pediu nada. Se ele não grava, NADA começa.

    2. **O PORTÃO, logo depois.** A sessão aberta vale 4 horas, e enquanto
       ela vive o apagamento é REVERSÍVEL: com o token, um cadastro novo
       reprojeta a pessoa inteira. Revogar cedo fecha a janela.

    3. **O DIÁRIO, antes do banco.** O diário é a AUTORIDADE; o banco é
       projeção dele. Apagando o banco primeiro, uma falha antes da redação
       deixa o diário intacto — e a próxima `banco.reconstruir`, que é a
       operação de RECUPERAÇÃO, ressuscita a pessoa.

    4. Os arquivos, os róis, o acervo e os logs.  5. O banco.  6. A medição.

    O `portao` é INJETADO e não importado: o apagamento não decide nada
    sobre autenticação, só precisa esquecer o que o portão guarda.
    """
    for rotulo, texto in (("motivo", motivo), ("pedido_por", pedido_por)):
        if len(texto or "") > TETO_DO_TEXTO:
            raise ValueError(
                f"{rotulo} tem {len(texto)} caracteres e o limite é "
                f"{TETO_DO_TEXTO}"
            )
    digitos = validacao.so_digitos(cpf)
    if len(digitos) != 11:
        raise ValueError("apagar exige CPF de 11 dígitos")

    pasta = ent.pasta(raiz)

    # CAPTURADOS ANTES DE QUALQUER REMOÇÃO, porque depois não dá: o e-mail
    # sai do rol, e os protocolos deixam de ser atribuíveis à pessoa quando
    # o diário é redigido.
    email = ""
    try:
        email = rol.carregar(pasta).email_de(digitos) or ""
    except Exception:  # noqa: BLE001
        # Rol ausente ou malformado não impede apagar — só nos deixa sem o
        # e-mail para varrer os logs, e isso vai dito no resultado.
        pass
    protocolos = [
        r["protocolo"] for r in deposito.ler_diario(pasta)
        if isinstance(r.get("linha"), dict)
        and validacao.so_digitos(r["linha"].get("cpf") or "") == digitos
        and r.get("protocolo")
    ]

    # 1. O TOMBSTONE PRIMEIRO. Se isto levantar, propaga e nada mais roda.
    banco.marcar_tombstone(url, ent.apelido, portao.marcar_cpf(digitos),
                           motivo, pedido_por)

    # 2. O portão: revoga a sessão viva e esquece os marcadores.
    do_portao = portao.esquecer(ent.apelido, digitos)

    # 3. O diário, que é a autoridade.
    redigidos = deposito.redigir_no_diario(ent, raiz, digitos)

    # 4. Arquivos, róis, acervo e logs.
    arquivos = 0
    alvos = [ent.entrega(raiz) / digitos,
             pasta / deposito.HISTORICO / digitos]
    alvos += [pasta / deposito.PARCIAL / p for p in protocolos]
    for alvo in alvos:
        if alvo.is_dir():
            arquivos += sum(1 for f in alvo.rglob("*") if f.is_file())
            shutil.rmtree(alvo)

    saiu_do_rol = rol.remover(pasta, digitos)
    saiu_do_acervo = _remover_do_acervo(pasta, digitos)
    sairam_leituras = conferencia.remover_pessoa(pasta, digitos)
    sairam_trocas = trocas.remover_pessoa(pasta, digitos)
    das_mensagens = _limpar_logs(raiz, digitos, email)

    # 5. O banco.
    do_banco = banco.apagar_pessoa(url, ent.apelido, digitos)

    # 6. A CONFERÊNCIA. Medir, não declarar.
    return {
        "marcador": portao.marcar_cpf(digitos)[:12],
        "banco": do_banco,
        "portao": do_portao,
        "diario": redigidos,
        "arquivos": arquivos,
        "rol": saiu_do_rol,
        "acervo": saiu_do_acervo,
        "leituras": sairam_leituras,
        "trocas": sairam_trocas,
        "logs": das_mensagens,
        "email_conhecido": bool(email),
        "vestigios": vestigios(url, ent, raiz, digitos, portao=portao,
                               email=email),
    }


def _remover_do_acervo(pasta: pathlib.Path, cpf: str) -> int:
    return acervo.remover_pessoa(pasta / "acervo.jsonl", cpf)


def _limpar_logs(raiz: pathlib.Path, cpf: str, email: str) -> int:
    """Tira as linhas desta pessoa dos logs do remetente de ARQUIVO.

    `ParaArquivo` é o remetente de desenvolvimento, mas quem o escolhe é só
    a ausência de `PROTOCOL_SMTP_HOST` NAQUELE ambiente — um cron sem a
    variável, não apenas o modo ensaio. E os arquivos guardam o e-mail, o
    código de acesso e o corpo do aviso, que começa com o nome da pessoa.

    Ficam na RAIZ, fora de qualquer pasta de entidade: foi por isso que a
    primeira versão da varredura não os viu.
    """
    saiu = 0
    for nome in ("codigos_enviados.log", "mensagens_enviadas.log"):
        caminho = raiz / nome
        if not caminho.is_file():
            continue
        linhas = caminho.read_text(encoding="utf-8",
                                   errors="replace").splitlines()
        ficam = [linha for linha in linhas
                 if cpf not in linha and not (email and email in linha)]
        if len(ficam) != len(linhas):
            saiu += len(linhas) - len(ficam)
            tmp = caminho.with_suffix(caminho.suffix + ".parcial")
            tmp.write_text("\n".join(ficam) + ("\n" if ficam else ""),
                           encoding="utf-8")
            tmp.replace(caminho)
    return saiu
