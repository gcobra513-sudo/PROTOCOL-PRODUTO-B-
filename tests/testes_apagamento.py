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
    banco.reconstruir(URL, "demo-a", [_registro_do_diario(A, "PRT-A")],
                      consentimento_novo=True)

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

def _portao_de_teste(raiz):
    """Um portão só para ter `marcar_cpf` com segredo estável no teste."""
    from servidor import acesso

    return acesso.Portao(raiz / ".portao", "segredo-de-teste-apagamento")


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

    banco.reconstruir(URL, "demo-c", deposito.ler_diario(ent.pasta(raiz)),
                      consentimento_novo=True)
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
    banco.reconstruir(URL, apelido, [_registro_do_diario(cpf, "PRT-V-1")],
                      consentimento_novo=True)
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
    achados = apagamento.vestigios(URL, ent, raiz, A,
                                   portao=_portao_de_teste(raiz))
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
    checa(apagamento.vestigios(URL, ent, raiz, _cpf(999_111),
                                portao=_portao_de_teste(raiz)) == [],
          "inventou vestígio de quem nunca existiu")
    print("  ok     quem nunca existiu não deixa vestígio")



# ------------------------------------------ apagar: a ordem e a retomada

def teste_depois_de_apagar_nao_sobra_nada():
    """A ASSERÇÃO CENTRAL DA SPEC, e ela é uma medição, não uma afirmação."""
    secao("apagar: a ordem e a retomada")
    from servidor import apagamento, banco

    ent, raiz = _semear_em_todo_lugar("demo-h", A)
    portao = _portao_de_teste(raiz)
    antes = apagamento.vestigios(URL, ent, raiz, A,
                                   portao=_portao_de_teste(raiz))
    checa(len(antes) >= 6, f"a semeadura não pegou: {antes}")

    saida = apagamento.apagar(URL, ent, raiz, A,
                              motivo="pedido do titular",
                              pedido_por="gestor@exemplo.invalid",
                              portao=portao)

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
                          portao=portao)
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
                      portao=portao)

    pasta = ent.pasta(raiz)
    (pasta / rol.ARQUIVO).write_text(
        f"cpf,email\n{C},voltou@exemplo.invalid\n", encoding="utf-8")
    checa(apagamento.vestigios(URL, ent, raiz, C,
                                portao=_portao_de_teste(raiz)),
          "vestigios não viu a linha reposta à mão")

    segunda = apagamento.apagar(URL, ent, raiz, C, motivo="", pedido_por="",
                                portao=portao)
    checa(segunda["vestigios"] == [],
          f"a segunda passada não fechou: {segunda['vestigios']}")
    print("  ok     vestigios enxerga o reposto, e a retomada fecha")


def teste_apagar_duas_vezes_deixa_dois_tombstones():
    """A tabela é log. Dois pedidos, dois registros — e o segundo não quebra."""
    from servidor import apagamento, banco

    ent, raiz = _semear_em_todo_lugar("demo-k", D)
    portao = _portao_de_teste(raiz)
    apagamento.apagar(URL, ent, raiz, D, motivo="primeiro", pedido_por="g1",
                      portao=portao)
    segunda = apagamento.apagar(URL, ent, raiz, D, motivo="segundo",
                                pedido_por="g2",
                                portao=portao)
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
                      portao=portao)

    gravados, pulados = banco.reconstruir(URL, "demo-l", backup,
                                          marcar_cpf=portao.marcar_cpf)
    checa(pulados == 1, f"não pulou o apagado: gravados={gravados} "
                        f"pulados={pulados}")
    checa(banco.registro_do_cpf(URL, "demo-l", A) is None,
          "a restauração de backup ressuscitou quem pediu para sair")
    print("  ok     restaurar backup não ressuscita o apagado")


def teste_esquecer_o_filtro_falha_fechado():
    """ESQUECER NÃO PODE SIGNIFICAR "NÃO FILTRE".

    A primeira forma era invertida: `marcar_cpf=None` queria dizer "deixe
    passar", e o único caminho de recuperação de histórico é uma chamada à
    mão — que é exatamente a que esquece o parâmetro. Quem esquecesse
    ressuscitava quem pediu para sair, em silêncio.

    Agora, numa entidade que TEM apagamento registrado, a função recusa em
    vez de adivinhar. E quem quer declarar consentimento novo diz isso.
    """
    from servidor import apagamento, banco, deposito

    ent, raiz = _semear_em_todo_lugar("demo-m", B)
    portao = _portao_de_teste(raiz)
    backup = deposito.ler_diario(ent.pasta(raiz))
    apagamento.apagar(URL, ent, raiz, B, motivo="", pedido_por="",
                      portao=portao)

    recusou = False
    try:
        banco.reconstruir(URL, "demo-m", backup)
    except ValueError:
        recusou = True
    checa(recusou,
          "esqueceu o filtro e projetou de qualquer jeito — é assim que "
          "uma recuperação à mão ressuscita quem pediu para sair")

    # E a declaração explícita de consentimento novo continua passando.
    gravados, pulados = banco.reconstruir(URL, "demo-m", backup,
                                          consentimento_novo=True)
    checa(pulados == 0 and gravados >= 1,
          f"consentimento novo foi barrado: gravados={gravados} "
          f"pulados={pulados}")
    print("  ok     esquecer recusa; declarar consentimento novo passa")



# ------------------------------- a ingestão da planilha pula e relata

def teste_a_ingestao_pula_o_apagado_e_relata():
    """D2: PULA E AVISA. Pular calado faria o sindicato reenviar o mesmo CPF
    para sempre sem saber que a planilha dele está desatualizada — e
    silêncio é o que este produto evita em todo lugar.

    E NUNCA imprime o CPF pulado: a pessoa pediu para sair.
    """
    secao("a ingestão da planilha")
    import subprocess

    from servidor import banco

    ent, raiz = _entidade_em_disco("demo-n")
    portao = _portao_de_teste(raiz)
    banco.marcar_tombstone(URL, "demo-n", portao.marcar_cpf(A),
                           motivo="", pedido_por="")

    planilha = raiz / "planilha.csv"
    planilha.write_text(
        "cpf,email,nome\n"
        f"{A},a@exemplo.invalid,PESSOA A (FICTÍCIO)\n"
        f"{B},b@exemplo.invalid,PESSOA B (FICTÍCIO)\n"
        f"{C},c@exemplo.invalid,PESSOA C (FICTÍCIO)\n",
        encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(RAIZ / "ferramentas" / "ingerir_acervo.py"),
         "--acervo", str(planilha), "--entidade", "demo-n",
         "--raiz", str(raiz), "--banco", URL],
        capture_output=True, text=True,
        env={**os.environ, "PROTOCOL_SEGREDO": "segredo-de-teste-apagamento"},
    )
    saida = r.stdout + r.stderr
    checa("apagada" in saida.lower() and "1" in saida,
          f"não relatou que pulou alguém apagado:\n{saida[-600:]}")
    checa(A not in saida, "imprimiu o CPF de quem pediu para sair")

    from servidor import acervo as mod_acervo

    gravado = ent.pasta(raiz) / "acervo.jsonl"
    import json as _json

    cpfs = set()
    for bruto in gravado.read_text(encoding="utf-8").splitlines():
        if bruto.strip():
            for pessoa in _json.loads(bruto).get("pessoas") or ():
                cpfs.add(pessoa["cpf"])
    checa(A not in cpfs, f"gravou no acervo quem foi apagado: {cpfs}")
    checa({B, C} <= cpfs, f"levou os vizinhos junto: {cpfs}")
    print("  ok     pulou o apagado, relatou, e não imprimiu o CPF")



# ------------------------------------------- a ferramenta de retomada

def teste_a_ferramenta_apaga_e_confere():
    """A ferramenta serve a duas coisas: terminar um apagamento interrompido
    e RESPONDER se um pedido foi atendido, sem acreditar em ninguém.

    Sai com 1 quando sobra vestígio, para servir dentro de script."""
    secao("a ferramenta de retomada")
    import subprocess

    ent, raiz = _semear_em_todo_lugar("demo-o", A)
    ambiente = {**os.environ,
                "PROTOCOL_SEGREDO": "segredo-de-teste-apagamento",
                "PROTOCOL_DATABASE_URL": URL}
    comando = [sys.executable,
               str(RAIZ / "ferramentas" / "apagar_filiado.py"),
               "--entidade", "demo-o", "--cpf", A,
               "--raiz", str(raiz), "--banco", URL]

    antes = subprocess.run(comando + ["--conferir"], capture_output=True,
                           text=True, env=ambiente)
    checa(antes.returncode == 1,
          f"--conferir devia sair 1 com vestígio, saiu {antes.returncode}")
    checa("SOBRARAM" in antes.stdout, f"não listou o que sobrou:\n{antes.stdout}")

    r = subprocess.run(comando + ["--motivo", "pedido do titular",
                                  "--pedido-por", "g@exemplo.invalid"],
                       capture_output=True, text=True, env=ambiente)
    checa(r.returncode == 0,
          f"o apagamento saiu {r.returncode}:\n{r.stdout}\n{r.stderr}")
    checa("nada sobrou" in r.stdout, f"não confirmou o fim:\n{r.stdout}")
    checa(A not in r.stdout + r.stderr, "a ferramenta imprimiu o CPF")

    depois = subprocess.run(comando + ["--conferir"], capture_output=True,
                            text=True, env=ambiente)
    checa(depois.returncode == 0,
          f"--conferir ainda acha vestígio:\n{depois.stdout}")
    print("  ok     confere, apaga, e confere de novo — sem imprimir CPF")



# ===================================================================
# AS SOBREVIVÊNCIAS QUE A CAÇA ADVERSARIAL ACHOU
#
# `vestigios` devolvia VAZIO e sobrava dado em quatro lugares. A raiz é
# uma: ele varria POR CPF, e dado pessoal também mora onde o CPF não é
# índice — chave de dicionário, pasta indexada por protocolo, arquivo por
# raiz em vez de por entidade.
#
# Medir pela metade é pior que declarar: uma declaração se desconfia, uma
# medição se acredita. E `vestigios` vazio é a única prova que o produto
# oferece ao sindicato para responder ao titular em 15 dias.
# ===================================================================

def teste_o_retrato_do_acervo_nao_guarda_o_cpf_apagado():
    """S1. `remover_pessoa` tirava a pessoa da lista `pessoas` e deixava o
    bloco `retrato` intacto — e três campos dele são chaveados por CPF:
    `inalcancaveis_por_cpf` (chave), `falta_nominal` (item da lista) e
    `divergencias` (chave, com nome e e-mail no valor).

    O comentário que eu escrevi dizia que o `retrato` é "sobre o ARQUIVO e
    não sobre gente". Era falso.
    """
    secao("as sobrevivências da caça adversarial")
    import json as _json

    from servidor import acervo, deposito

    ent, raiz = _entidade_em_disco("demo-p")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / "acervo.jsonl"
    deposito.anexar_com_fsync(caminho, _json.dumps({
        "ingerido_em": "2026-11-02", "origem": "planilha.xlsx",
        "retrato": {
            "pessoas": 2,
            "inalcancaveis_por_cpf": {A: "sem e-mail", B: "sem e-mail"},
            "falta_nominal": {"email": [A, B]},
            "divergencias": {A: [{"campo": "nome", "acervo": "X"}]},
        },
        "pessoas": [{"cpf": A, "linha_no_arquivo": 2, "campos": {},
                     "achados": []},
                    {"cpf": B, "linha_no_arquivo": 3, "campos": {},
                     "achados": []}],
    }, ensure_ascii=False) + "\n")

    acervo.remover_pessoa(caminho, A)
    bruto = caminho.read_text(encoding="utf-8")
    checa(A not in bruto,
          f"o CPF apagado sobreviveu no acervo:\n{bruto[:400]}")
    registro = _json.loads(bruto.splitlines()[0])
    checa(B in registro["retrato"]["inalcancaveis_por_cpf"],
          "levou o vizinho junto do retrato")
    checa(registro["retrato"]["pessoas"] == 2,
          "mexeu na contagem do arquivo, que é sobre o arquivo")
    print("  ok     o retrato perde o apagado e mantém o vizinho")


def teste_o_retrato_de_verdade_nao_guarda_cpf_nenhum():
    """O dublê era o buraco. Os testes acima escrevem o retrato À MÃO, com
    as três chaves que eu SEI que são indexadas por CPF — e um teste assim
    só prova que `_limpar_retrato` conhece as chaves que o teste conhece.
    Foi exatamente um retrato de dublê (`{"pessoas": 1}`) que deixou o C1
    passar pela suíte inteira.

    Aqui o retrato é o DE VERDADE, `dataclasses.asdict(retratar(...))`, e a
    conferência é estrutural: depois de limpar, VARRE o retrato inteiro —
    chaves e valores, em qualquer profundidade — e exige que o CPF não
    apareça em lugar nenhum. Um campo novo indexado por CPF no `Retrato`
    quebra este teste no dia em que for criado, que é o dia certo.
    """
    import dataclasses as _dc

    from servidor import acervo, completude

    def _varrer(no, agulha: str, caminho: str = "retrato") -> list[str]:
        """Onde a agulha aparece, com o caminho até lá."""
        if isinstance(no, dict):
            saida = []
            for chave, valor in no.items():
                if agulha in str(chave):
                    saida.append(f"{caminho}[{chave!r}] (chave)")
                saida += _varrer(valor, agulha, f"{caminho}[{chave!r}]")
            return saida
        if isinstance(no, (list, tuple)):
            return [achado for i, item in enumerate(no)
                    for achado in _varrer(item, agulha, f"{caminho}[{i}]")]
        return [caminho] if agulha in str(no) else []

    # A e B sem e-mail, o que os põe em `inalcancaveis_por_cpf`; as colunas
    # exigidas vazias os põem em `falta_nominal`; e o cadastro de A no
    # diário discordando do acervo o põe em `divergencias`. Os três campos
    # do retrato que são indexados por CPF, pelo caminho de verdade.
    def _sem_email(cpf: str, nome: str) -> "acervo.Pessoa":
        return acervo.Pessoa(
            cpf=cpf, linha_no_arquivo=2,
            campos={"nome_completo": nome, "email": "", "cargo": ""},
            achados=(acervo.Achado("email", acervo.FALTA, "sem e-mail"),),
        )

    pessoas = [_sem_email(A, "FULANA DE TAL (CADASTRO DE EXEMPLO)"),
               _sem_email(B, "BELTRANO DE TAL (CADASTRO DE EXEMPLO)")]
    diario = [{"linha": {"cpf": A,
                         "nome_completo": "OUTRO NOME (CADASTRO DE EXEMPLO)"}}]
    retrato = _dc.asdict(completude.retratar(pessoas, diario))

    antes = _varrer(retrato, A)
    checa(antes,
          "o retrato de verdade não trouxe o CPF em lugar nenhum, então "
          "este teste não está medindo nada — conferir `retratar`")

    mudou = acervo._limpar_retrato(retrato, A)
    checa(mudou, "_limpar_retrato disse que não mexeu em nada")

    sobrou = _varrer(retrato, A)
    checa(not sobrou,
          "o CPF apagado sobreviveu no retrato de verdade, em:\n  "
          + "\n  ".join(sobrou))
    checa(_varrer(retrato, B),
          "levou o vizinho junto: o retrato perdeu o CPF de quem NÃO pediu "
          "para sair")
    print(f"  ok     retrato real: {len(antes)} lugar(es) com o CPF, "
          f"0 depois, vizinho intacto")


def teste_vestigios_olha_o_retrato():
    """S1, o outro lado: se alguém puser o CPF no retrato por outro
    caminho, a varredura tem de ver."""
    import json as _json

    from servidor import apagamento, deposito

    ent, raiz = _entidade_em_disco("demo-q")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    deposito.anexar_com_fsync(pasta / "acervo.jsonl", _json.dumps({
        "ingerido_em": "2026-11-02", "origem": "x.xlsx",
        "retrato": {"inalcancaveis_por_cpf": {A: "sem e-mail"}},
        "pessoas": [],
    }, ensure_ascii=False) + "\n")
    achados = apagamento.vestigios(URL, ent, raiz, A,
                                   portao=_portao_de_teste(raiz))
    checa(any("retrato" in v for v in achados),
          f"vestigios não olhou o retrato do acervo: {achados}")
    print("  ok     vestigios enxerga o CPF no retrato")


def teste_apagar_revoga_a_sessao_e_esquece_o_marcador():
    """S3, e é a mais grave: a sessão aberta continuava VALENDO.

    Com o token na mão, `POST /api/cadastro` passa pelo portão e reprojeta
    a pessoa inteira — o apagamento era reversível num pedido para quem
    tivesse o token. E o `cpf_hash` sobrevivia nas tabelas `codigos` e
    `sessoes`, que ninguém apagava.
    """
    from servidor import acesso, apagamento

    ent, raiz = _semear_em_todo_lugar("demo-r", A)
    portao = _portao_de_teste(raiz)
    codigo = portao.emitir("demo-r", A, "127.0.0.1")
    token = portao.conferir("demo-r", A, codigo)
    checa(portao.abrir_sessao(token) is not None, "a semeadura não abriu sessão")

    apagamento.apagar(URL, ent, raiz, A, motivo="", pedido_por="",
                      portao=portao)

    morreu = False
    try:
        portao.abrir_sessao(token)
    except acesso.SessaoInvalida:
        morreu = True
    checa(morreu, "a sessão de quem foi apagado continua abrindo — o "
                  "apagamento é reversível para quem tem o token")

    import sqlite3

    cx = sqlite3.connect(raiz / ".portao" / acesso.ARQUIVO)
    marca = portao.marcar_cpf(A)
    restou = sum(
        cx.execute(f"SELECT count(*) FROM {t} WHERE cpf_hash = ?",
                   (marca,)).fetchone()[0]
        for t in ("codigos", "sessoes")
    )
    cx.close()
    checa(restou == 0, f"o marcador sobreviveu no portão: {restou} linha(s)")
    print("  ok     a sessão morre e o marcador sai do portão")


def teste_remover_do_rol_le_por_nome_de_coluna():
    """S5. `remover` cortava pela PRIMEIRA coluna; `_carregar` lê por NOME
    de coluna. Rol com matrícula na frente — o formato que o próprio módulo
    diz esperar — era lido pelo portão e nunca apagado, e `apagar` nunca
    convergia, enquanto a ferramenta mandava "rode de novo, é seguro".
    """
    from servidor import rol

    ent, raiz = _entidade_em_disco("demo-s")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / rol.ARQUIVO).write_text(
        "matricula;cpf;email\n"
        f"0001;{A};a@exemplo.invalid\n"
        f"0002;{B};b@exemplo.invalid\n",
        encoding="utf-8")

    checa(rol.carregar(pasta).email_de(A) == "a@exemplo.invalid",
          "a semeadura não foi lida pelo portão")
    saiu = rol.remover(pasta, A)
    checa(saiu == 1, f"não tirou a linha com matrícula na frente: {saiu}")
    checa(rol.carregar(pasta).email_de(A) is None,
          "o CPF continua legível pelo portão depois de apagado")
    checa(rol.carregar(pasta).email_de(B) == "b@exemplo.invalid",
          "levou o vizinho junto")
    print("  ok     remove por nome de coluna, não por posição")


def teste_apagar_limpa_a_area_de_montagem():
    """S2. Uma queda entre montar e trocar deixa o PDF em `.parcial/`, que
    é indexado por PROTOCOLO e não por CPF — nem `apagar` nem `vestigios`
    tinham por onde achá-lo."""
    from servidor import apagamento, deposito

    ent, raiz = _entidade_em_disco("demo-t")
    pasta = ent.pasta(raiz)
    _anexar_ao_diario(ent, raiz, [_registro_do_diario(A, "PRT-T-1")])
    montagem = pasta / deposito.PARCIAL / "PRT-T-1"
    montagem.mkdir(parents=True, exist_ok=True)
    (montagem / "sentenca.pdf").write_bytes(b"%PDF-1.4\n(EXEMPLO FICTICIO)")

    # ANTES do apagamento a montagem NÃO é vestígio de ninguém apagado —
    # é só um envio que caiu no meio. Vestígio é o que sobra DEPOIS.
    portao = _portao_de_teste(raiz)
    saida = apagamento.apagar(URL, ent, raiz, A, motivo="", pedido_por="",
                              portao=portao)
    checa(not montagem.exists(),
          "o PDF com a sentença ficou na área de montagem depois de apagar")
    checa(saida["vestigios"] == [], f"sobrou coisa: {saida['vestigios']}")

    # E SE ELA VOLTAR, a varredura tem de ver. O protocolo sobrevive no
    # registro redigido, e registro redigido é de alguém apagado — é por
    # aí que uma pasta indexada por PROTOCOLO fica atribuível.
    montagem.mkdir(parents=True, exist_ok=True)
    (montagem / "sentenca.pdf").write_bytes(b"%PDF-1.4\n(EXEMPLO)")
    depois = apagamento.vestigios(URL, ent, raiz, A, portao=portao)
    checa(any("montagem" in v for v in depois),
          f"vestigios não viu a montagem de um envio apagado: {depois}")
    print("  ok     a área de montagem é limpa, e vigiada se voltar")



def teste_apagar_nao_destroi_recebimento_de_outra_ingestao():
    """I1. O `DELETE FROM recebimento ... NOT EXISTS` não tinha predicado
    ligando-o à pessoa: varria TODO recebimento órfão visível.

    A camada 1 é o "o que exatamente nos mandaram?" e é irreversível.
    Destruir a procedência de uma planilha que não tem nada a ver com o
    pedido é o oposto do que o apagamento deve fazer — e a contagem
    devolvida atribuía as duas ao pedido dela.
    """
    from servidor import banco

    ent, raiz = _entidade_em_disco("demo-u")
    # Um recebimento ÓRFÃO semeado direto — uma ingestão antiga cujas
    # afirmações já foram consolidadas. Semeá-lo pela própria função com
    # defeito não dava: ela já o apagava, que é o defeito.
    with banco.sessao(URL, "demo-u") as cur:
        cur.execute(
            "INSERT INTO recebimento (entidade, tipo, origem, payload, "
            "sha256) VALUES (%s,'acervo',%s,%s::jsonb,%s)",
            ("demo-u", "planilha-antiga.xlsx", '{"linhas":9}', "f" * 64),
        )
        cur.execute("SELECT count(*) FROM recebimento")
        orfaos_antes = cur.fetchone()[0]
    checa(orfaos_antes >= 1,
          "a semeadura não deixou recebimento órfão para o teste medir")

    banco.projetar_acervo(URL, "demo-u", [_pessoa_do_acervo(A, 3)])
    saiu = banco.apagar_pessoa(URL, "demo-u", A)

    with banco.sessao(URL, "demo-u") as cur:
        cur.execute("SELECT count(*) FROM recebimento")
        depois = cur.fetchone()[0]
    checa(depois >= orfaos_antes,
          f"apagar a pessoa destruiu recebimento de outra ingestão: "
          f"{orfaos_antes} antes, {depois} depois. Contagem devolvida: "
          f"{saiu}")
    print("  ok     recebimento de outra ingestão sobrevive")


def teste_a_redacao_nao_destroi_a_linha_truncada_de_terceiro():
    """I3. A volta pelo `ler_diario` é lossy: linha truncada por queda vira
    `{"_ilegivel": n}`, e reescrever o arquivo a partir disso APAGA os bytes
    crus — que são a única prova de que aquele envio existiu.

    Apagar a pessoa A destruía, em silêncio e para sempre, o fragmento do
    envio de B. O resto do sistema tolera essas linhas de propósito.
    """
    from servidor import deposito

    ent, raiz = _entidade_em_disco("demo-v")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    _anexar_ao_diario(ent, raiz, [_registro_do_diario(A, "PRT-V-X")])
    truncada = '{"protocolo": "PRT-TRUNCADA", "linha": {"cpf": "9'
    with open(pasta / deposito.DIARIO, "a", encoding="utf-8") as fh:
        fh.write(truncada + "\n")
    _anexar_ao_diario(ent, raiz, [_registro_do_diario(B, "PRT-V-Y")])

    deposito.redigir_no_diario(ent, raiz, A)

    bruto = (pasta / deposito.DIARIO).read_text(encoding="utf-8")
    checa(truncada in bruto,
          "a redação destruiu a linha truncada de outro envio — era a única "
          "prova de que ele existiu")
    checa("PRT-V-Y" in bruto, "levou o registro do vizinho junto")
    print("  ok     a linha truncada de terceiro sobrevive à redação")


def teste_medir_pela_metade_e_recusado_em_vez_de_silenciado():
    """Adiado 1, e ele era maior do que o rótulo "menor" dizia.

    `vestigios` pulava DOIS lugares em silêncio: sem URL não conferia o
    banco, sem `portao` não conferia códigos e sessões. Os dois estavam
    escritos no docstring — e docstring não é medição. A lista voltava VAZIA,
    e lista vazia é a única prova que o sindicato tem para responder ao
    titular dentro dos 15 dias da lei.

    Ou seja: o jeito mais fácil de obter "nada sobrou" era medir menos.

    Agora recusa. Os dois caminhos de produção já passavam os dois
    argumentos, então isto não tira capacidade de ninguém — tira a
    possibilidade de uma resposta ao titular apoiada em meia medição.
    """
    secao("os adiados")
    from servidor import apagamento

    ent, raiz = _entidade_em_disco("demo-med")
    portao = _portao_de_teste(raiz)

    for rotulo, chamada in (
        ("sem banco", lambda: apagamento.vestigios("", ent, raiz, A,
                                                   portao=portao)),
        ("sem portão", lambda: apagamento.vestigios(URL, ent, raiz, A,
                                                    portao=None)),
    ):
        caiu = ""
        try:
            chamada()
        except ValueError as e:
            caiu = str(e)
        checa(caiu, f"{rotulo}: mediu pela metade e devolveu lista, "
                    f"em vez de recusar")
        checa(A not in caiu, f"{rotulo}: o CPF foi para a mensagem de erro")

    # E com os dois, mede normalmente.
    checa(apagamento.vestigios(URL, ent, raiz, A, portao=portao) == [],
          "com banco e portão, uma entidade vazia devia medir zero")
    print("  ok     sem banco ou sem portão, recusa medir em vez de dar vazio")


def teste_remover_do_rol_preserva_o_byte_de_quem_fica():
    """Adiado 2. O docstring de `rol.remover` diz "REESCREVE PRESERVANDO O
    DIALETO" e a escrita era `encoding="utf-8"` com `"\\n".join`.

    Duas perdas silenciosas, nas duas pontas do mesmo arquivo:

    1. LATIN-1 VIRAVA UTF-8. O rol vem do Excel em português e muitas vezes
       em latin-1 — `_carregar` aprendeu isso derrubando o portão inteiro
       uma vez. Reescrever em utf-8 funciona para nós (`_decodificar` tenta
       os dois), e quebra para o SINDICATO: ele abre o mesmo arquivo no
       Excel dele e vê `JOSÃ‰` onde estava `JOSÉ`.
    2. CRLF VIRAVA LF. Arquivo do Windows entra, arquivo de Unix sai.

    Nenhuma das duas apaga dado errado, e por isso ficaram adiadas. As duas
    mexem num arquivo que é do sindicato, não nosso, e que ele repõe à mão —
    então a medida certa é a dura: o BYTE de quem fica tem de sobreviver
    idêntico.
    """
    from servidor import rol

    ent, raiz = _entidade_em_disco("demo-enc")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)

    # Excel brasileiro: ';', CRLF, latin-1, e o CPF na SEGUNDA coluna.
    original = (
        "matricula;cpf;email;nome\r\n"
        f"001;{A};a@exemplo.invalid;JOSÉ DE ALENCAR (EXEMPLO)\r\n"
        f"002;{B};b@exemplo.invalid;MARIA JOÃO (EXEMPLO)\r\n"
    ).encode("latin-1")
    caminho = pasta / rol.ARQUIVO
    caminho.write_bytes(original)
    # Prova de que é latin-1 de verdade, e não utf-8 por acidente:
    caixa = original
    erro = ""
    try:
        caixa.decode("utf-8")
    except UnicodeDecodeError as e:
        erro = str(e)
    checa(erro, "o arquivo do teste decodifica como utf-8, então ele não "
                "exercita a perda de latin-1")

    sairam = rol.remover(pasta, A)
    checa(sairam == 1, f"devia sair 1 linha, saíram {sairam}")

    depois = caminho.read_bytes()
    linha_de_b = f"002;{B};b@exemplo.invalid;MARIA JOÃO (EXEMPLO)".encode(
        "latin-1")
    checa(linha_de_b in depois,
          "a linha de quem NÃO pediu para sair mudou de bytes: "
          f"{depois!r}")
    checa(b"matricula;cpf;email;nome" in depois, "o cabeçalho mudou")
    checa(b"\r\n" in depois, f"o CRLF foi perdido: {depois!r}")
    checa(A.encode() not in depois, "o CPF apagado sobreviveu")

    # E o rol continua legível pelo caminho normal, que é o que importa
    # para o portão.
    carregado = rol.carregar(pasta)
    checa(carregado.email_de(B), "o rol deixou de responder por quem ficou")
    print("  ok     o rol mantém latin-1, CRLF e o byte de quem fica")


def teste_a_ferramenta_usa_o_portao_DE_VERDADE():
    """Adiado 3, e o rótulo "menor" escondia o S3 voltando pela linha de
    comando.

    O adiado dizia: "a ferramenta constrói um `Portao` inteiro só para um
    HMAC". Medido, não era isso. O servidor abre o portão em `cfg.raiz`
    (`dados_portal/acesso.sqlite3`); a ferramenta abria em
    `raiz/".portao-ferramenta"` — OUTRO BANCO, vazio.

    Consequência, que é a mesma do S3 que a revisão já tinha achado uma vez:
    `apagar` chama `portao.esquecer()` nesse banco vazio, então o CÓDIGO E A
    SESSÃO DA PESSOA CONTINUAM VIVOS; e `vestigios` chama
    `marcadores_de()` no mesmo banco vazio, então a ferramenta imprime
    "nada sobrou" com a sessão aberta. O apagamento feito pela ferramenta
    era reversível, e a ferramenta afirmava o contrário.

    O HMAC casava por acaso: ele só depende do segredo, não do arquivo. Foi
    isso que deixou o defeito invisível — o tombstone ficava certo.
    """
    import subprocess

    from servidor import acesso

    ent, raiz = _semear_em_todo_lugar("demo-pf", A)
    segredo = "segredo-de-teste-apagamento"

    # A sessão viva, no portão QUE O SERVIDOR USA.
    verdadeiro = acesso.Portao(raiz, segredo)
    codigo = verdadeiro.emitir("demo-pf", A, origem="teste")
    verdadeiro.conferir("demo-pf", A, codigo)
    checa(verdadeiro.marcadores_de("demo-pf", A) >= 2,
          "o teste não conseguiu deixar código e sessão vivos")

    ambiente = {**os.environ, "PROTOCOL_SEGREDO": segredo,
                "PROTOCOL_DATABASE_URL": URL}
    comando = [sys.executable,
               str(RAIZ / "ferramentas" / "apagar_filiado.py"),
               "--entidade", "demo-pf", "--cpf", A,
               "--raiz", str(raiz), "--banco", URL]

    antes = subprocess.run(comando + ["--conferir"], capture_output=True,
                           text=True, env=ambiente)
    checa("portão" in antes.stdout,
          f"--conferir não viu o código e a sessão vivos:\n{antes.stdout}")

    r = subprocess.run(comando + ["--motivo", "pedido", "--pedido-por", "g"],
                       capture_output=True, text=True, env=ambiente)
    checa(r.returncode == 0, f"saiu {r.returncode}:\n{r.stdout}\n{r.stderr}")
    checa(verdadeiro.marcadores_de("demo-pf", A) == 0,
          "a ferramenta disse que apagou e a sessão da pessoa continua "
          "viva: o apagamento é reversível")
    checa(not (raiz / ".portao-ferramenta").exists(),
          "a ferramenta deixou um banco de acesso descartável no disco do "
          "sindicato")
    print("  ok     a ferramenta revoga a sessão no portão do servidor")


def teste_o_marcador_de_cpf_nao_precisa_de_banco():
    """A outra metade do adiado 3: quem só precisa do HMAC não deve abrir —
    nem CRIAR — um banco de acesso.

    `Portao.__init__` faz `mkdir` e roda o esquema. A ingestão da planilha
    só quer reconhecer tombstones, e pagava um diretório e um SQLite por
    isso, no disco do sindicato.
    """
    from servidor import acesso

    ent, raiz = _entidade_em_disco("demo-hmac")
    segredo = "segredo-de-teste-apagamento"
    pasta = raiz / ".nao-deve-existir"

    direto = acesso.marcador_de_cpf(segredo, "526.018.159-06")
    checa(not pasta.exists() and not (raiz / "acesso.sqlite3").exists(),
          "calcular o marcador criou arquivo no disco")

    # E é O MESMO marcador do portão: um segundo cálculo de HMAC seria um
    # segundo jeito de errar, e tombstone com marcador diferente não casa.
    pelo_portao = acesso.Portao(pasta, segredo).marcar_cpf("52601815906")
    checa(direto == pelo_portao,
          f"marcador diferente do portão: {direto[:8]} vs {pelo_portao[:8]}")
    print("  ok     o marcador sai do segredo, sem tocar o disco")


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
    teste_esquecer_o_filtro_falha_fechado,
    teste_a_ingestao_pula_o_apagado_e_relata,
    teste_a_ferramenta_apaga_e_confere,
    teste_o_retrato_do_acervo_nao_guarda_o_cpf_apagado,
    teste_o_retrato_de_verdade_nao_guarda_cpf_nenhum,
    teste_medir_pela_metade_e_recusado_em_vez_de_silenciado,
    teste_remover_do_rol_preserva_o_byte_de_quem_fica,
    teste_a_ferramenta_usa_o_portao_DE_VERDADE,
    teste_o_marcador_de_cpf_nao_precisa_de_banco,
    teste_vestigios_olha_o_retrato,
    teste_apagar_revoga_a_sessao_e_esquece_o_marcador,
    teste_remover_do_rol_le_por_nome_de_coluna,
    teste_apagar_limpa_a_area_de_montagem,
    teste_apagar_nao_destroi_recebimento_de_outra_ingestao,
    teste_a_redacao_nao_destroi_a_linha_truncada_de_terceiro,
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
