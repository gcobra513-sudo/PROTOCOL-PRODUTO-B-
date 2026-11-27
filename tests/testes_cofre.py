#!/usr/bin/env python3
"""
O cofre — onde os documentos das pessoas ficam guardados.

Há dois cofres, e os dois obedecem ao MESMO contrato: a pasta no disco do
servidor (o que sempre existiu) e o depósito privado na nuvem, falado no
padrão S3. Cada teste daqui roda nos dois. É isso que permite trocar um pelo
outro sem que o resto do sistema perceba — e sem que uma regra valha num e
não no outro.

O QUE ESTES TESTES FIXAM:

1. O que se guarda se lê de volta, byte a byte.
2. Reenvio troca o conjunto inteiro, e o anterior vai para o histórico —
   ninguém perde documento por ter corrigido o próprio cadastro.
3. Documento do sindicato entra ao lado, sem apagar o que a pessoa mandou.
4. Uma pessoa não lê o documento de outra, nem um sindicato o de outro.
5. Nome de arquivo e CPF que não têm a forma do contrato são RECUSADOS —
   nenhum pedaço vindo de fora vira caminho.
6. Apagar leva tudo: o atual, o histórico e o que ficou pela metade.
7. O depósito na nuvem só aceita endereço cifrado e região no Brasil.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import cofre  # noqa: E402
from servidor.entidades import Entidade  # noqa: E402

falhas: list[str] = []
TESTES: list = []

BALDE = "cofre-de-teste"


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def ent(apelido: str) -> Entidade:
    return Entidade(apelido=apelido, nome=apelido, ativa=True,
                    criada_em="2026-01-01")


A, B = "00000910066", "00000910147"
SIND, OUTRO = ent("sind-a"), ent("sind-b")


def nos_dois(teste):
    """Roda o mesmo teste no disco e no depósito S3 (de mentira, local)."""

    def rodar() -> None:
        from moto import mock_aws
        import boto3

        with tempfile.TemporaryDirectory() as d:
            teste(cofre.NoDisco(pathlib.Path(d)), "disco")
        with mock_aws():
            cliente = boto3.client(
                "s3", region_name="sa-east-1",
                aws_access_key_id="teste", aws_secret_access_key="teste")
            cliente.create_bucket(
                Bucket=BALDE,
                CreateBucketConfiguration={"LocationConstraint": "sa-east-1"})
            teste(cofre.NoS3(cliente, BALDE), "s3")

    rodar.__name__ = teste.__name__
    TESTES.append(rodar)
    return rodar


@nos_dois
def guarda_e_le_de_volta(c, onde):
    c.trocar(SIND, A, "p1", {"sentenca.pdf": b"%PDF-um", "rg.pdf": b"%PDF-dois"})
    # OS NOMES DO CONTRATO, todos: um cofre que recusa `certidao_transito.pdf`
    # recusa o cadastro de todo mundo. (Aconteceu: a primeira forma não
    # aceitava sublinhado.)
    from servidor import validacao
    for nome in sorted(validacao.NOMES_DE_ARQUIVO) + ["sentenca-2.pdf", "outro-3.pdf"]:
        c.acrescentar(SIND, B, nome, b"x")
    c.apagar(SIND, B, [])
    checa(c.nomes(SIND, A) == ["rg.pdf", "sentenca.pdf"],
          f"[{onde}] nomes: {c.nomes(SIND, A)}")
    checa(c.ler(SIND, A, "sentenca.pdf") == b"%PDF-um", f"[{onde}] leitura")
    checa(c.nomes(SIND, B) == [], f"[{onde}] quem não mandou não tem nada")


@nos_dois
def reenvio_troca_tudo_e_guarda_o_anterior(c, onde):
    c.trocar(SIND, A, "p1", {"sentenca.pdf": b"velha", "rg.pdf": b"rg"})
    foi = c.trocar(SIND, A, "p2", {"sentenca.pdf": b"nova"})
    checa(bool(foi), f"[{onde}] o reenvio diz para onde foi o anterior")
    checa(c.nomes(SIND, A) == ["sentenca.pdf"],
          f"[{onde}] o rg do envio antigo não sobra no atual: {c.nomes(SIND, A)}")
    checa(c.ler(SIND, A, "sentenca.pdf") == b"nova", f"[{onde}] vale o novo")
    checa(c.contar(SIND, A) == {"entrega": 1, "historico": 2},
          f"[{onde}] contagem: {c.contar(SIND, A)}")
    # Três reenvios seguidos não se atropelam no histórico.
    c.trocar(SIND, A, "p3", {"sentenca.pdf": b"3"})
    c.trocar(SIND, A, "p4", {"sentenca.pdf": b"4"})
    checa(c.contar(SIND, A)["historico"] == 4,
          f"[{onde}] histórico de 4: {c.contar(SIND, A)}")


@nos_dois
def primeiro_envio_nao_substitui_nada(c, onde):
    checa(c.trocar(SIND, A, "p1", {"rg.pdf": b"x"}) == "",
          f"[{onde}] primeiro envio não tem anterior")


@nos_dois
def documento_do_sindicato_entra_ao_lado(c, onde):
    c.trocar(SIND, A, "p1", {"sentenca.pdf": b"da pessoa"})
    c.acrescentar(SIND, A, "sentenca-2.pdf", b"do sindicato")
    checa(c.nomes(SIND, A) == ["sentenca-2.pdf", "sentenca.pdf"],
          f"[{onde}] os dois ficam: {c.nomes(SIND, A)}")
    checa(c.ler(SIND, A, "sentenca.pdf") == b"da pessoa",
          f"[{onde}] o da pessoa não foi tocado")
    # E vale para quem nunca enviou nada pelo portal.
    c.acrescentar(SIND, B, "procuracao.pdf", b"x")
    checa(c.nomes(SIND, B) == ["procuracao.pdf"], f"[{onde}] pasta nova")


@nos_dois
def ninguem_le_o_que_nao_e_seu(c, onde):
    c.trocar(SIND, A, "p1", {"rg.pdf": b"da A"})
    c.trocar(OUTRO, A, "p9", {"rg.pdf": b"no outro sindicato"})
    for quem, de in ((SIND, B), (ent("sind-c"), A)):
        try:
            c.ler(quem, de, "rg.pdf")
            checa(False, f"[{onde}] leu o que não existe para {quem.apelido}/{de}")
        except cofre.NaoHa:
            pass
    checa(c.ler(SIND, A, "rg.pdf") == b"da A",
          f"[{onde}] o mesmo CPF em dois sindicatos não se mistura")
    checa(c.ler(OUTRO, A, "rg.pdf") == b"no outro sindicato", f"[{onde}] idem")


@nos_dois
def nada_de_fora_vira_caminho(c, onde):
    c.trocar(SIND, A, "p1", {"rg.pdf": b"x"})
    ruins = ["../rg.pdf", "a/b.pdf", "", ".pdf", "rg.PDF", "rg.pdf/", "rg.exe",
             "..", "rg.pdf\x00", "RG.pdf", "r g.pdf"]
    for nome in ruins:
        for acao in (lambda n=nome: c.ler(SIND, A, n),
                     lambda n=nome: c.acrescentar(SIND, A, n, b"y"),
                     lambda n=nome: c.trocar(SIND, A, "p2", {n: b"y"})):
            try:
                acao()
                checa(False, f"[{onde}] aceitou o nome {nome!r}")
            except cofre.Recusado:
                pass
    for cpf_ruim in ["", "123", "../" + A, A + "/x", "0000091006a", A + "0"]:
        for acao in (lambda x=cpf_ruim: c.nomes(SIND, x),
                     lambda x=cpf_ruim: c.ler(SIND, x, "rg.pdf"),
                     lambda x=cpf_ruim: c.trocar(SIND, x, "p2", {"rg.pdf": b"y"}),
                     lambda x=cpf_ruim: c.apagar(SIND, x, [])):
            try:
                acao()
                checa(False, f"[{onde}] aceitou o CPF {cpf_ruim!r}")
            except cofre.Recusado:
                pass
    for prot in ["", "../p", "a/b", "p 1"]:
        try:
            c.trocar(SIND, A, prot, {"rg.pdf": b"y"})
            checa(False, f"[{onde}] aceitou o protocolo {prot!r}")
        except cofre.Recusado:
            pass
    # A recusa não deixou nada pela metade.
    checa(c.nomes(SIND, A) == ["rg.pdf"] and c.ler(SIND, A, "rg.pdf") == b"x",
          f"[{onde}] recusa não altera o que estava guardado")


@nos_dois
def apagar_leva_tudo_e_so_o_dela(c, onde):
    c.trocar(SIND, A, "p1", {"rg.pdf": b"1"})
    c.trocar(SIND, A, "p2", {"rg.pdf": b"2", "sentenca.pdf": b"s"})
    c.trocar(SIND, B, "p3", {"rg.pdf": b"da B"})
    c.trocar(OUTRO, A, "p4", {"rg.pdf": b"outro sindicato"})
    foram = c.apagar(SIND, A, ["p1", "p2"])
    checa(foram == 3, f"[{onde}] apagou {foram}, eram 3 (2 atuais + 1 histórico)")
    checa(c.nomes(SIND, A) == [] and c.contar(SIND, A) == {},
          f"[{onde}] não sobra nada dela: {c.contar(SIND, A)}")
    checa(c.ler(SIND, B, "rg.pdf") == b"da B", f"[{onde}] a vizinha fica")
    checa(c.ler(OUTRO, A, "rg.pdf") == b"outro sindicato",
          f"[{onde}] o cadastro dela em OUTRO sindicato fica")
    checa(c.apagar(SIND, A, []) == 0, f"[{onde}] apagar de novo é zero")


@nos_dois
def esvaziar_um_sindicato_nao_toca_o_vizinho(c, onde):
    """A demonstração recomeça do zero a cada reinício, e o depósito na nuvem
    não recomeça sozinho: sem isto, o documento fictício de ontem reaparece
    na pasta de quem se cadastrar hoje com o mesmo CPF de teste."""
    c.trocar(ent("sind"), A, "p1", {"rg.pdf": b"1"})
    c.trocar(ent("sind"), A, "p2", {"rg.pdf": b"2"})
    c.trocar(ent("sind"), B, "p3", {"rg.pdf": b"3"})
    c.trocar(ent("sind-a"), A, "p4", {"rg.pdf": b"vizinho"})
    foram = c.esvaziar(ent("sind"))
    checa(foram == 3, f"[{onde}] esvaziou {foram}, eram 3")
    checa(c.nomes(ent("sind"), A) == [] and c.contar(ent("sind"), B) == {},
          f"[{onde}] não sobra nada do sindicato esvaziado")
    checa(c.ler(ent("sind-a"), A, "rg.pdf") == b"vizinho",
          f"[{onde}] `sind` esvaziado alcançou `sind-a`")
    checa(c.esvaziar(ent("sind")) == 0, f"[{onde}] esvaziar de novo é zero")


def t_prefixo_de_cpf_nao_alcanca_o_vizinho():
    """No S3 o "diretório" é só um prefixo de texto. Sem a barra no fim,
    apagar `sind-a/0000091006` levaria junto `sind-a/00000910066`…"""
    from moto import mock_aws
    import boto3

    with mock_aws():
        cliente = boto3.client("s3", region_name="sa-east-1",
                               aws_access_key_id="t", aws_secret_access_key="t")
        cliente.create_bucket(
            Bucket=BALDE,
            CreateBucketConfiguration={"LocationConstraint": "sa-east-1"})
        c = cofre.NoS3(cliente, BALDE)
        c.trocar(ent("sind"), A, "p1", {"rg.pdf": b"a"})
        c.trocar(ent("sind-a"), A, "p1", {"rg.pdf": b"b"})
        c.apagar(ent("sind"), A, ["p1"])
        checa(c.ler(ent("sind-a"), A, "rg.pdf") == b"b",
              "apagar em `sind` alcançou `sind-a`")


TESTES.append(t_prefixo_de_cpf_nao_alcanca_o_vizinho)


def t_o_deposito_na_nuvem_so_no_brasil_e_cifrado():
    bom = {
        "PROTOCOL_COFRE_ENDERECO": "https://exemplo.storage.supabase.co/storage/v1/s3",
        "PROTOCOL_COFRE_REGIAO": "sa-east-1",
        "PROTOCOL_COFRE_BALDE": "documentos",
        "PROTOCOL_COFRE_CHAVE_ID": "id",
        "PROTOCOL_COFRE_SEGREDO": "segredo",
    }
    checa(cofre.ajuste_do_ambiente({}) is None,
          "sem nenhuma variável, o cofre é o disco")
    aj = cofre.ajuste_do_ambiente(bom)
    checa(aj is not None and aj.balde == "documentos", "ajuste completo é aceito")
    checa("segredo" not in repr(aj), "o segredo não aparece ao imprimir o ajuste")

    def recusa(mudanca: dict, porque: str) -> None:
        amb = {**bom, **mudanca}
        amb = {k: v for k, v in amb.items() if v is not None}
        try:
            cofre.ajuste_do_ambiente(amb)
            checa(False, f"aceitou: {porque}")
        except cofre.AjusteRecusado:
            pass

    recusa({"PROTOCOL_COFRE_REGIAO": "us-east-2"}, "região fora do Brasil")
    recusa({"PROTOCOL_COFRE_REGIAO": ""}, "região vazia")
    recusa({"PROTOCOL_COFRE_ENDERECO": "http://exemplo.supabase.co/s3"},
           "endereço sem cifra (http)")
    recusa({"PROTOCOL_COFRE_SEGREDO": None}, "configuração pela metade")
    recusa({"PROTOCOL_COFRE_BALDE": None}, "sem o nome do depósito")
    recusa({"PROTOCOL_COFRE_ENDERECO": None},
           "sem endereço (cairia na AWS dos EUA por omissão)")


TESTES.append(t_o_deposito_na_nuvem_so_no_brasil_e_cifrado)


def t_o_deposito_grava_no_cofre_e_o_diario_fica_no_disco():
    """O caminho de verdade: `deposito.depositar` com o cofre da nuvem. O
    diário e o manifesto ficam no disco; NENHUM PDF fica."""
    from moto import mock_aws
    import boto3

    from servidor import deposito

    linha = {"cpf": A, "nome": "FULANA DE TAL (CADASTRO DE EXEMPLO)"}
    with mock_aws(), tempfile.TemporaryDirectory() as d:
        raiz = pathlib.Path(d)
        cliente = boto3.client("s3", region_name="sa-east-1",
                               aws_access_key_id="t", aws_secret_access_key="t")
        cliente.create_bucket(
            Bucket=BALDE,
            CreateBucketConfiguration={"LocationConstraint": "sa-east-1"})
        c = cofre.NoS3(cliente, BALDE)
        r1 = deposito.depositar(SIND, raiz, linha,
                                {"sentenca.pdf": b"%PDF-1"}, guarda=c)
        r2 = deposito.depositar(SIND, raiz, linha,
                                {"sentenca.pdf": b"%PDF-2"}, guarda=c)
        checa(r1.substituiu == "" and r2.substituiu.startswith(A + "/historico/"),
              f"o recibo diz o que substituiu: {r2.substituiu!r}")
        checa(c.ler(SIND, A, "sentenca.pdf") == b"%PDF-2", "vale o último envio")
        checa(len(deposito.ler_diario(SIND.pasta(raiz))) == 2,
              "o diário tem os dois envios, no disco")
        checa((SIND.entrega(raiz) / deposito.MANIFESTO).is_file(),
              "o manifesto continua no disco")
        pdfs = [str(f) for f in raiz.rglob("*.pdf")]
        checa(pdfs == [], f"sobrou PDF no disco com o cofre na nuvem: {pdfs}")


TESTES.append(t_o_deposito_grava_no_cofre_e_o_diario_fica_no_disco)


def t_o_padrao_segue_o_ambiente():
    """Servidor e ferramentas pegam o MESMO cofre, pelo ambiente — é o que
    impede a ferramenta de apagamento de olhar o disco com os documentos na
    nuvem."""
    with tempfile.TemporaryDirectory() as d:
        raiz = pathlib.Path(d)
        checa(isinstance(cofre.padrao(raiz, {}), cofre.NoDisco),
              "sem variável, disco")
        amb = {
            "PROTOCOL_COFRE_ENDERECO": "https://exemplo.invalid/storage/v1/s3",
            "PROTOCOL_COFRE_REGIAO": "sa-east-1",
            "PROTOCOL_COFRE_BALDE": "documentos",
            "PROTOCOL_COFRE_CHAVE_ID": "id",
            "PROTOCOL_COFRE_SEGREDO": "segredo",
        }
        um = cofre.padrao(raiz, amb)
        checa(isinstance(um, cofre.NoS3), "com as cinco, nuvem")
        checa(cofre.padrao(raiz, amb) is um, "o cliente é reaproveitado")
        try:
            cofre.padrao(raiz, {**amb, "PROTOCOL_COFRE_REGIAO": "us-east-1"})
            checa(False, "padrao aceitou região fora do Brasil")
        except cofre.AjusteRecusado:
            pass


TESTES.append(t_o_padrao_segue_o_ambiente)


def main() -> int:
    print("=" * 70)
    print("COFRE — onde os documentos ficam, no disco e na nuvem")
    print("=" * 70)
    for teste in TESTES:
        try:
            teste()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{teste.__name__}: levantou "
                          f"{type(exc).__name__}: {exc}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
