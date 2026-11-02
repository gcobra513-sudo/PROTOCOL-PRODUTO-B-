"""Apagamento a pedido — LGPD art. 18, VI.

O produto guarda nome, CPF, e-mail, sentença e número de processo de gente
aposentada, e filiação sindical é dado sensível (art. 11). Um pedido de
eliminação tem de ser atendido, e a lei dá 15 dias.

O QUE ESTES TESTES PROVAM, e é diferente de "a função foi chamada": que
depois de apagar **não sobra nada** — e a prova é uma varredura de banco,
disco, CSV e diário, não um campo `apagado = true`. Campo desses é uma
AFIRMAÇÃO, e a auditoria de 31/10 derrubou sete afirmações assim neste
mesmo repositório.

SEM BANCO ESTA SUÍTE É PULADA, e o resumo diz isso. Suíte pulada não está
testada.

Spec: `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`
"""
from __future__ import annotations

import os
import pathlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

URL = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def preparar() -> None:
    from servidor import banco

    banco.criar_esquema(URL, recriar=True)


# --------------------------------------------------------- o tombstone

def teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf():
    """O tombstone é a prova de que a remoção foi deliberada.

    Guarda QUEM foi apagado (por marcador), QUANDO, e A PEDIDO DE QUEM —
    sem o dado. É isso que transforma "append-only" em "não se edita" em
    vez de "não se apaga nunca".
    """
    secao("o tombstone")
    from servidor import banco

    banco.marcar_tombstone(URL, "demo-a", "marcador-de-teste",
                           motivo="pedido do titular",
                           pedido_por="gestor@exemplo.invalid")

    checa(banco.tombstones(URL, "demo-a") == {"marcador-de-teste"},
          f"o tombstone não foi lido de volta: "
          f"{banco.tombstones(URL, 'demo-a')}")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT motivo, pedido_por FROM tombstone")
        linha = cur.fetchone()
    checa(linha == ("pedido do titular", "gestor@exemplo.invalid"),
          f"o pedido não ficou registrado: {linha}")
    print("  ok     o tombstone guarda o pedido, por marcador")


def teste_o_tombstone_nao_atravessa_entidade():
    """Apagar numa entidade não pode apagar na outra, nem ser visto por ela."""
    from servidor import banco

    banco.marcar_tombstone(URL, "demo-b", "marcador-da-b",
                           motivo="", pedido_por="")
    checa("marcador-da-b" not in banco.tombstones(URL, "demo-a"),
          "a entidade A vê o tombstone da B")
    checa("marcador-de-teste" not in banco.tombstones(URL, "demo-b"),
          "a entidade B vê o tombstone da A")
    print("  ok     tombstone não atravessa entidade")



# ------------------------------------------- semeadura (dados fictícios)

def _cpf(n: int) -> str:
    """CPF sintético com dígito que fecha. A base é o índice, não ninguém."""
    base = [int(c) for c in f"{n:09d}"]
    for peso0 in (10, 11):
        soma = sum(d * (peso0 - i) for i, d in enumerate(base))
        base.append((soma * 10 % 11) % 10)
    return "".join(map(str, base))


A = _cpf(3001)
B = _cpf(3002)
C = _cpf(3003)
D = _cpf(3004)


def _pessoa_do_acervo(cpf: str, linha: int = 2):
    from servidor import acervo

    return acervo.Pessoa(cpf=cpf, linha_no_arquivo=linha, campos={
        "nome_completo": f"PESSOA {cpf} (CADASTRO FICTÍCIO)",
        "email": f"exemplo-{cpf}@exemplo.invalid",
        "unidade": "UNIDADE DE EXEMPLO",
    })


def _registro_do_diario(cpf: str, protocolo: str) -> dict:
    return {
        "protocolo": protocolo,
        "recebido_em": "2026-11-02T00:00:00+00:00",
        "entidade": "demo-a",
        "linha": {
            "cpf": cpf,
            "nome_completo": f"PESSOA {cpf} (CADASTRO FICTÍCIO)",
            "email": f"exemplo-{cpf}@exemplo.invalid",
            "cargo": "Auditor Fiscal da Receita Federal",
            "situacao": "aposentado",
            "filiado_desde": "2004-03",
        },
        "arquivos": {"contribuicao": "a" * 64},
    }


# ----------------------------------------------- as exclusões no banco

def teste_apagar_pessoa_limpa_o_que_e_dela():
    secao("as exclusões no banco")
    from servidor import banco

    # A MESMA ingestão de acervo traz as duas pessoas, de propósito: é o
    # caso em que apagar demais estragaria o dado de terceiro.
    banco.projetar_acervo(URL, "demo-a",
                          [_pessoa_do_acervo(A, 2), _pessoa_do_acervo(B, 3)])
    # O retorno é ignorado: a T7 muda a assinatura, e o que este teste
    # prova não é o valor devolvido (ver ruling no livro de registro).
    banco.reconstruir(URL, "demo-a", [_registro_do_diario(A, "PRT-A")])

    saiu = banco.apagar_pessoa(URL, "demo-a", A)

    checa(saiu.get("pessoa_afirmacao", 0) > 0 and saiu.get("pessoa") == 1,
          f"não apagou as linhas da pessoa: {saiu}")
    checa(banco.registro_do_cpf(URL, "demo-a", A) is None,
          "a pessoa continua na base depois de apagada")
    checa("leitura" not in saiu and "processo" not in saiu
          and "movimento" not in saiu,
          f"tocou tabela que a spec manda não tocar: {saiu}")
    print("  ok     as linhas da pessoa saíram")


def teste_apagar_nao_estraga_o_dado_de_terceiro():
    """APAGAR DEMAIS É IRREVERSÍVEL, e aqui está o caminho para isso.

    `projetar_acervo` grava UM `recebimento` por INGESTÃO, compartilhado
    por todas as pessoas da planilha. Apagar esse recebimento junto com uma
    pessoa anularia o `recebimento_id` de todas as outras — e a coluna é
    `ON DELETE SET NULL`, então o estrago é silencioso.

    A outra pessoa da mesma ingestão tem de continuar inteira, e com a
    procedência dela intacta.
    """
    from servidor import banco

    # AUTOSSUFICIENTE DE PROPÓSITO. A primeira versão deste teste só lia, e
    # por isso passava ANTES de `apagar_pessoa` existir — nada apagava, e a
    # outra pessoa sobrevivia à toa. Teste que passa sem o código é um
    # achado sobre o teste.
    banco.projetar_acervo(URL, "demo-a",
                          [_pessoa_do_acervo(C, 4), _pessoa_do_acervo(D, 5)])
    banco.apagar_pessoa(URL, "demo-a", C)

    outra = banco.registro_do_cpf(URL, "demo-a", D)
    checa(outra is not None,
          "apagou a pessoa errada: a outra da mesma ingestão desapareceu")
    checa(outra and outra["linha"].get("nome_completo"),
          f"a outra pessoa ficou sem nome: {outra}")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa_afirmacao "
                    "WHERE cpf = %s AND recebimento_id IS NULL", (D,))
        orfas = cur.fetchone()[0]
    checa(orfas == 0,
          f"{orfas} afirmações da outra pessoa perderam a procedência")
    print("  ok     a outra pessoa da mesma ingestão ficou intacta")


def teste_apagar_nao_atravessa_entidade():
    from servidor import banco

    banco.projetar_acervo(URL, "demo-b", [_pessoa_do_acervo(A, 2)])
    banco.apagar_pessoa(URL, "demo-a", A)
    checa(banco.registro_do_cpf(URL, "demo-b", A) is not None,
          "apagar na entidade A apagou a mesma pessoa na B")
    print("  ok     apagar não atravessa entidade")



# --------------------------------------------- a redação no diário

def _entidade_em_disco(apelido: str = "demo-a"):
    """Uma entidade de verdade numa raiz temporária, com diário."""
    import tempfile

    from servidor import entidades

    raiz = pathlib.Path(tempfile.mkdtemp(prefix="apagamento-"))
    ent = entidades.Cadastro(raiz).criar(apelido, "Sindicato de Exemplo")
    return ent, raiz


def _anexar_ao_diario(ent, raiz, registros: list[dict]) -> None:
    import json as _json

    from servidor import deposito

    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    for r in registros:
        deposito.anexar_com_fsync(
            pasta / deposito.DIARIO,
            _json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n",
        )


def teste_a_redacao_mantem_o_protocolo_e_perde_o_conteudo():
    """A REDAÇÃO É O QUE FAZ "append-only" SIGNIFICAR "não se edita".

    O diário é a autoridade do produto. Remover a linha inteira perderia a
    evidência de que houve um envio e tornaria inexistente o protocolo que
    a pessoa tem nas mãos. Então o registro fica, e o CONTEÚDO sai.

    E `reconstruir` já pula registro sem `linha` — é isso que faz a redação
    bastar sem mudar a projeção.
    """
    secao("a redação no diário")
    from servidor import deposito

    ent, raiz = _entidade_em_disco()
    _anexar_ao_diario(ent, raiz, [
        _registro_do_diario(A, "PRT-A-1"),
        _registro_do_diario(B, "PRT-B-1"),
        _registro_do_diario(A, "PRT-A-2"),
    ])

    quantos = deposito.redigir_no_diario(ent, raiz, A)
    checa(quantos == 2, f"devia redigir os 2 envios dela, redigiu {quantos}")

    registros = deposito.ler_diario(ent.pasta(raiz))
    checa(len(registros) == 3,
          f"a redação mudou o número de linhas do diário: {len(registros)}")

    redigidos = [r for r in registros if r.get("apagado_em")]
    checa(len(redigidos) == 2, f"só {len(redigidos)} ficaram redigidos")
    for r in redigidos:
        checa(bool(r.get("protocolo")) and bool(r.get("recebido_em")),
              f"perdeu o protocolo, e a pessoa tem esse número na mão: {r}")
        checa("linha" not in r and "arquivos" not in r,
              f"sobrou conteúdo no registro redigido: {r}")

    sobrou = [r for r in registros if r.get("linha", {}).get("cpf") == B]
    checa(len(sobrou) == 1 and sobrou[0]["linha"].get("nome_completo"),
          "redigiu o registro da OUTRA pessoa")
    print("  ok     protocolo mantido, conteúdo apagado, vizinho intacto")


def teste_a_projecao_ignora_registro_redigido():
    """A razão de a redação bastar: `reconstruir` pula registro sem `linha`.

    Se não pulasse, projetar um diário redigido levantaria ou gravaria
    pessoa sem CPF — e o apagamento teria de mexer na projeção também.
    """
    from servidor import banco, deposito

    ent, raiz = _entidade_em_disco("demo-c")
    _anexar_ao_diario(ent, raiz, [_registro_do_diario(A, "PRT-C-1")])
    deposito.redigir_no_diario(ent, raiz, A)

    banco.reconstruir(URL, "demo-c", deposito.ler_diario(ent.pasta(raiz)))
    checa(banco.registro_do_cpf(URL, "demo-c", A) is None,
          "projetar um diário redigido ressuscitou a pessoa")
    print("  ok     a projeção ignora registro redigido")



# ------------------------------------- os dois formatos de arquivo

def teste_remover_do_rol_preserva_o_dialeto_e_os_vizinhos():
    """O rol vem do Excel em português, com ';'. Reescrever errado fecha o
    portão para o sindicato inteiro — `_carregar` já aprendeu isso."""
    secao("os dois formatos de arquivo")
    from servidor import rol

    ent, raiz = _entidade_em_disco("demo-d")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / rol.ARQUIVO).write_text(
        "cpf;email;nome\n"
        f"{A};a@exemplo.invalid;PESSOA A (FICTÍCIO)\n"
        f"{B};b@exemplo.invalid;PESSOA B (FICTÍCIO)\n"
        f"{C};c@exemplo.invalid;PESSOA C (FICTÍCIO)\n",
        encoding="utf-8")
    (pasta / rol.ARQUIVO_GESTORES).write_text(
        f"cpf;email\n{A};gestor@exemplo.invalid\n", encoding="utf-8")

    quantas = rol.remover(pasta, A)
    checa(quantas == 2, f"devia tirar 1 linha de cada arquivo, tirou {quantas}")

    lista = rol.carregar(pasta)
    checa(lista.email_de(A) is None, "o CPF apagado continua no rol")
    checa(lista.email_de(B) == "b@exemplo.invalid"
          and lista.email_de(C) == "c@exemplo.invalid",
          f"a reescrita estragou os vizinhos: {lista.por_cpf}")
    checa(rol.carregar_gestores(pasta).email_de(A) is None,
          "o CPF apagado continua no rol de gestores")
    print("  ok     saiu dos dois róis, dialeto e vizinhos preservados")


def teste_remove_a_pessoa_de_TODAS_as_ingestoes_do_acervo():
    """O `acervo.jsonl` é UMA LINHA POR INGESTÃO, com `pessoas` dentro.

    Não é uma linha por pessoa. Quem tratar como tal limpa só a última
    ingestão e deixa a pessoa em todas as anteriores — e o sindicato que
    manda planilha toda semana tem dezenas delas.
    """
    import json as _json

    from servidor import acervo, deposito

    ent, raiz = _entidade_em_disco("demo-e")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / "acervo.jsonl"

    for marca in ("primeira", "segunda"):
        deposito.anexar_com_fsync(caminho, _json.dumps({
            "ingerido_em": f"2026-11-0{1 if marca == 'primeira' else 2}",
            "origem": f"planilha-{marca}.xlsx",
            "retrato": {"pessoas": 2},
            "pessoas": [
                {"cpf": A, "linha_no_arquivo": 2,
                 "campos": {"nome_completo": "PESSOA A (FICTÍCIO)"},
                 "achados": []},
                {"cpf": B, "linha_no_arquivo": 3,
                 "campos": {"nome_completo": "PESSOA B (FICTÍCIO)"},
                 "achados": []},
            ],
        }, ensure_ascii=False) + "\n")

    quantas = acervo.remover_pessoa(caminho, A)
    checa(quantas == 2,
          f"removeu de só uma ingestão das duas: {quantas}")

    linhas = [_json.loads(l) for l in
              caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
    checa(len(linhas) == 2,
          f"apagou a linha de ingestão inteira: sobraram {len(linhas)}")
    for linha in linhas:
        cpfs = {p["cpf"] for p in linha["pessoas"]}
        checa(A not in cpfs, f"a pessoa sobrou numa ingestão: {cpfs}")
        checa(B in cpfs, f"levou a vizinha junto: {cpfs}")
        checa(linha.get("origem"), "perdeu a procedência do arquivo")
    print("  ok     saiu das 2 ingestões, vizinha e procedência intactas")



# ------------------------------------------------ vestigios: a medição

def _semear_em_todo_lugar(apelido: str, cpf: str):
    """A mesma pessoa nos SEIS lugares onde ela pode existir."""
    import json as _json

    from servidor import banco, deposito, rol

    ent, raiz = _entidade_em_disco(apelido)
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)

    # 1 e 2: banco (acervo e cadastro)
    banco.projetar_acervo(URL, apelido, [_pessoa_do_acervo(cpf, 2)])
    banco.reconstruir(URL, apelido, [_registro_do_diario(cpf, "PRT-V-1")])
    # 3: o diário em disco
    _anexar_ao_diario(ent, raiz, [_registro_do_diario(cpf, "PRT-V-1")])
    # 4: o PDF entregue
    entrega = ent.entrega(raiz) / cpf
    entrega.mkdir(parents=True, exist_ok=True)
    (entrega / "sentenca.pdf").write_bytes(b"%PDF-1.4\n(EXEMPLO FICTICIO)")
    # 5: o PDF de um reenvio anterior — o lugar que se esquece
    guarda = pasta / deposito.HISTORICO / cpf / "20261101T000000"
    guarda.mkdir(parents=True, exist_ok=True)
    (guarda / "contribuicao.pdf").write_bytes(b"%PDF-1.4\n(EXEMPLO)")
    # 6: o rol
    (pasta / rol.ARQUIVO).write_text(
        f"cpf,email,nome\n{cpf},v@exemplo.invalid,PESSOA (FICTÍCIO)\n",
        encoding="utf-8")
    # 7: o acervo em disco
    deposito.anexar_com_fsync(pasta / "acervo.jsonl", _json.dumps({
        "ingerido_em": "2026-11-02", "origem": "planilha.xlsx",
        "retrato": {"pessoas": 1},
        "pessoas": [{"cpf": cpf, "linha_no_arquivo": 2,
                     "campos": {"nome_completo": "PESSOA (FICTÍCIO)"},
                     "achados": []}],
    }, ensure_ascii=False) + "\n")
    return ent, raiz


def teste_vestigios_acha_a_pessoa_em_todos_os_lugares():
    """A MEDIÇÃO É O QUE SUBSTITUI UM CAMPO `apagado = true`.

    Um campo desses é uma AFIRMAÇÃO, e a auditoria de 31/10 derrubou sete
    afirmações assim neste repositório. Esta função não afirma: ela varre.

    O `historico/` está aqui de propósito — é o lugar que se esquece, e
    é onde mora o PDF de sentença de um reenvio anterior.
    """
    secao("vestigios: a medição")
    from servidor import apagamento

    ent, raiz = _semear_em_todo_lugar("demo-f", A)
    achados = apagamento.vestigios(URL, ent, raiz, A)
    juntos = " | ".join(achados)

    for onde in ("banco", "diário", "entrega", "historico", "rol", "acervo"):
        checa(any(onde in v for v in achados),
              f"vestigios não olhou em {onde}: {juntos}")
    checa(A not in juntos, f"vestigios publicou o CPF em claro: {juntos}")
    print(f"  ok     {len(achados)} vestígios, nos seis lugares, sem CPF")


def teste_vestigios_de_quem_nunca_existiu_e_vazio():
    """Vazio é a resposta de "não sobrou nada", e é o que `apagar` confere."""
    from servidor import apagamento

    ent, raiz = _entidade_em_disco("demo-g")
    checa(apagamento.vestigios(URL, ent, raiz, _cpf(999_111)) == [],
          "inventou vestígio de quem nunca existiu")
    print("  ok     quem nunca existiu não deixa vestígio")



# ------------------------------------------ apagar: a ordem e a retomada

def _portao_de_teste(raiz):
    """Um portão só para ter `marcar_cpf` com segredo estável no teste."""
    from servidor import acesso

    return acesso.Portao(raiz / ".portao", "segredo-de-teste-apagamento")


def teste_depois_de_apagar_nao_sobra_nada():
    """A ASSERÇÃO CENTRAL DA SPEC, e ela é uma medição, não uma afirmação."""
    secao("apagar: a ordem e a retomada")
    from servidor import apagamento, banco

    ent, raiz = _semear_em_todo_lugar("demo-h", A)
    portao = _portao_de_teste(raiz)
    antes = apagamento.vestigios(URL, ent, raiz, A)
    checa(len(antes) >= 6, f"a semeadura não pegou: {antes}")

    saida = apagamento.apagar(URL, ent, raiz, A,
                              motivo="pedido do titular",
                              pedido_por="gestor@exemplo.invalid",
                              marcar_cpf=portao.marcar_cpf)

    checa(saida["vestigios"] == [],
          f"sobrou coisa depois de apagar: {saida['vestigios']}")
    checa(portao.marcar_cpf(A) in banco.tombstones(URL, "demo-h"),
          "o tombstone não foi gravado")
    import json as _json
    checa(A not in _json.dumps(saida),
          f"o CPF saiu na resposta do apagamento: {saida}")
    print("  ok     não sobrou nada, e o tombstone ficou")


def teste_sem_banco_nada_e_apagado():
    """FALHA FECHADA. Apagar sem conseguir registrar é o pior resultado: a
    pessoa pediu para sair, o dado some, e não há prova de que alguém
    pediu. Então o tombstone vem primeiro, e se ele não grava nada começa."""
    from servidor import apagamento, deposito

    ent, raiz = _semear_em_todo_lugar("demo-i", B)
    portao = _portao_de_teste(raiz)
    antes = len(deposito.ler_diario(ent.pasta(raiz)))

    levantou = False
    try:
        apagamento.apagar("postgresql://ninguem@/nada?host=/tmp/nao-existe",
                          ent, raiz, B, motivo="", pedido_por="",
                          marcar_cpf=portao.marcar_cpf)
    except Exception:  # noqa: BLE001
        levantou = True

    checa(levantou, "não reclamou de não conseguir gravar o tombstone")
    depois = deposito.ler_diario(ent.pasta(raiz))
    checa(len(depois) == antes
          and all(r.get("linha") for r in depois),
          "o diário foi redigido sem tombstone — apagamos sem registro")
    print("  ok     sem tombstone, nada é apagado")


def teste_o_apagamento_e_retomavel():
    """O operador repõe o rol à mão e a pessoa volta ao arquivo. A spec
    declara esse buraco; `vestigios` é o que avisa, e a segunda passada
    fecha."""
    from servidor import apagamento, rol

    ent, raiz = _semear_em_todo_lugar("demo-j", C)
    portao = _portao_de_teste(raiz)
    apagamento.apagar(URL, ent, raiz, C, motivo="", pedido_por="",
                      marcar_cpf=portao.marcar_cpf)

    pasta = ent.pasta(raiz)
    (pasta / rol.ARQUIVO).write_text(
        f"cpf,email\n{C},voltou@exemplo.invalid\n", encoding="utf-8")
    checa(apagamento.vestigios(URL, ent, raiz, C),
          "vestigios não viu a linha reposta à mão")

    segunda = apagamento.apagar(URL, ent, raiz, C, motivo="", pedido_por="",
                                marcar_cpf=portao.marcar_cpf)
    checa(segunda["vestigios"] == [],
          f"a segunda passada não fechou: {segunda['vestigios']}")
    print("  ok     vestigios enxerga o reposto, e a retomada fecha")


def teste_apagar_duas_vezes_deixa_dois_tombstones():
    """A tabela é log. Dois pedidos, dois registros — e o segundo não quebra."""
    from servidor import apagamento, banco

    ent, raiz = _semear_em_todo_lugar("demo-k", D)
    portao = _portao_de_teste(raiz)
    apagamento.apagar(URL, ent, raiz, D, motivo="primeiro", pedido_por="g1",
                      marcar_cpf=portao.marcar_cpf)
    segunda = apagamento.apagar(URL, ent, raiz, D, motivo="segundo",
                                pedido_por="g2",
                                marcar_cpf=portao.marcar_cpf)
    checa(segunda["vestigios"] == [],
          f"a segunda chamada reclamou: {segunda['vestigios']}")
    with banco.sessao(URL, "demo-k") as cur:
        cur.execute("SELECT count(*) FROM tombstone")
        quantos = cur.fetchone()[0]
    checa(quantos == 2, f"o segundo pedido não ficou registrado: {quantos}")
    print("  ok     dois pedidos, dois tombstones")



# ------------------------------- a restauração de backup não ressuscita

def teste_restaurar_backup_nao_ressuscita_quem_foi_apagado():
    """O CENÁRIO MAIS PROVÁVEL DE TODOS, e o tombstone sozinho não cobria.

    O operador restaura um snapshot do diário anterior ao pedido e roda a
    recuperação. Sem consultar o tombstone, `reconstruir` traz a pessoa de
    volta e ninguém percebe — o apagamento é desfeito pela função que
    existe para consertar as coisas.
    """
    secao("a restauração de backup")
    from servidor import apagamento, banco, deposito

    ent, raiz = _semear_em_todo_lugar("demo-l", A)
    portao = _portao_de_teste(raiz)

    # O backup: o diário como estava ANTES do pedido.
    backup = deposito.ler_diario(ent.pasta(raiz))
    checa(any(r.get("linha") for r in backup), "o backup saiu vazio")

    apagamento.apagar(URL, ent, raiz, A, motivo="", pedido_por="",
                      marcar_cpf=portao.marcar_cpf)

    gravados, pulados = banco.reconstruir(URL, "demo-l", backup,
                                          marcar_cpf=portao.marcar_cpf)
    checa(pulados == 1, f"não pulou o apagado: gravados={gravados} "
                        f"pulados={pulados}")
    checa(banco.registro_do_cpf(URL, "demo-l", A) is None,
          "a restauração de backup ressuscitou quem pediu para sair")
    print("  ok     restaurar backup não ressuscita o apagado")


def teste_sem_marcar_cpf_a_recuperacao_nao_filtra():
    """A ASSIMETRIA É DELIBERADA, e vale explicar.

    `/api/cadastro` projeta o envio que a PRÓPRIA PESSOA acabou de fazer, e
    isso é consentimento NOVO — não pode ser barrado por um tombstone
    antigo. A recuperação de um diário velho é outra coisa, e essa tem de
    ser barrada. Quem distingue as duas é quem chama: passar `marcar_cpf` é
    dizer "estou reprojetando histórico, filtre".
    """
    from servidor import apagamento, banco, deposito

    ent, raiz = _semear_em_todo_lugar("demo-m", B)
    portao = _portao_de_teste(raiz)
    backup = deposito.ler_diario(ent.pasta(raiz))
    apagamento.apagar(URL, ent, raiz, B, motivo="", pedido_por="",
                      marcar_cpf=portao.marcar_cpf)

    gravados, pulados = banco.reconstruir(URL, "demo-m", backup)
    checa(pulados == 0,
          f"filtrou sem ninguém pedir, e isso barraria consentimento novo: "
          f"pulados={pulados}")
    checa(gravados >= 1, f"não gravou o registro: {gravados}")
    print("  ok     sem marcar_cpf não filtra — consentimento novo passa")


TESTES = [
    teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf,
    teste_o_tombstone_nao_atravessa_entidade,
    teste_apagar_pessoa_limpa_o_que_e_dela,
    teste_apagar_nao_estraga_o_dado_de_terceiro,
    teste_apagar_nao_atravessa_entidade,
    teste_a_redacao_mantem_o_protocolo_e_perde_o_conteudo,
    teste_a_projecao_ignora_registro_redigido,
    teste_remover_do_rol_preserva_o_dialeto_e_os_vizinhos,
    teste_remove_a_pessoa_de_TODAS_as_ingestoes_do_acervo,
    teste_vestigios_acha_a_pessoa_em_todos_os_lugares,
    teste_vestigios_de_quem_nunca_existiu_e_vazio,
    teste_depois_de_apagar_nao_sobra_nada,
    teste_sem_banco_nada_e_apagado,
    teste_o_apagamento_e_retomavel,
    teste_apagar_duas_vezes_deixa_dois_tombstones,
    teste_restaurar_backup_nao_ressuscita_quem_foi_apagado,
    teste_sem_marcar_cpf_a_recuperacao_nao_filtra,
]


def main() -> int:
    print("=" * 70)
    print("APAGAMENTO A PEDIDO (LGPD art. 18, VI)")
    print("=" * 70)
    if not URL:
        print("PULADO: defina PROTOCOL_DATABASE_URL. Suíte pulada não está "
              "testada.")
        return 0
    preparar()
    for teste in TESTES:
        try:
            teste()
        except Exception as e:  # noqa: BLE001
            import traceback

            falhas.append(f"{teste.__name__} levantou "
                          f"{type(e).__name__}: {e}")
            traceback.print_exc()
    print("-" * 70)
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
