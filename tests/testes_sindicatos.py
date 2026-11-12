#!/usr/bin/env python3
"""
Pôr um sindicato novo para funcionar, sem editar arquivo à mão.

Até aqui, cadastrar um sindicato era um trecho de Python colado no terminal
e um `gestores.csv` escrito no editor. É o primeiro passo com um cliente de
verdade, e era o único sem conferência nenhuma: um slug de categoria com uma
letra trocada derruba toda rota daquele sindicato, e um CPF de gestor torto
deixa o painel fechado sem ninguém entender por quê.

`ferramentas/sindicatos.py` é a entrada. O QUE ESTES TESTES FIXAM:

1. **Ou cria tudo, ou não cria nada.** Categoria que não existe, CPF que não
   fecha, e-mail que não serve: recusa ANTES de gravar qualquer coisa.
2. **Sindicato sem categoria ou sem gestor não é criado.** Sem categoria ele
   não recebe resposta nenhuma; sem gestor ninguém abre o painel.
3. **O e-mail de um gestor não muda por aqui.** Trocar para onde vai o
   código de alguém que já entra é a decisão que este produto mais protege,
   e ela tem ferramenta própria.
4. **Quem criou consegue entrar.** O teste do fim passa pelo portão de
   verdade.
5. **Continua nas mãos de quem opera.** Nenhuma rota nomeia gestor — e isso
   é conferido em `testes_repositorio.py`.
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import stat
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ferramentas import sindicatos  # noqa: E402
from servidor import entidades, rol  # noqa: E402

falhas: list[str] = []
TESTES: list = []

CATEGORIA = "auditor-fiscal-receita-federal"
G1, G2 = "529.982.247-25", "111.444.777-35"
D1, D2 = "52998224725", "11144477735"


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def raiz_nova() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="sindicatos-"))


def rodar(raiz: pathlib.Path, *args: str) -> tuple[int, str]:
    """A ferramenta, como quem opera a chama. (código de saída, o que disse)."""
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        codigo = sindicatos.main(["--raiz", str(raiz), *args])
    return codigo, saida.getvalue()


def existe(raiz: pathlib.Path, apelido: str) -> bool:
    try:
        entidades.Cadastro(raiz).resolver(apelido)
    except LookupError:
        return False
    return True


def pasta_com_trava() -> pathlib.Path:
    pasta = raiz_nova() / "demo-x"
    pasta.mkdir(parents=True)
    return pasta


# ------------------------------------------------------------ nomear gestor

def teste_nomear_cria_o_arquivo_fechado_e_o_portao_le():
    secao("nomear gestor")
    pasta = pasta_com_trava()
    checa(rol.nomear_gestor(pasta, G1, "gestor@exemplo.invalid") == "nomeado",
          "não nomeou")
    caminho = pasta / rol.ARQUIVO_GESTORES
    checa(rol.carregar_gestores(pasta).por_cpf == {D1: "gestor@exemplo.invalid"},
          f"o portão não lê o que foi escrito: {caminho.read_text()!r}")
    checa(stat.S_IMODE(caminho.stat().st_mode) == 0o600,
          f"o arquivo de gestores nasceu aberto: "
          f"{oct(stat.S_IMODE(caminho.stat().st_mode))}")
    antes = caminho.read_bytes()
    checa(rol.nomear_gestor(pasta, D1, "GESTOR@exemplo.invalid") == "ja_era",
          "nomear de novo a mesma pessoa não foi reconhecido")
    checa(caminho.read_bytes() == antes, "nomear de novo reescreveu o arquivo")
    print("  ok     cria com modo 600, o portão lê, e repetir não muda nada")


def teste_cpf_ou_email_que_nao_serve_nao_escreve_nada():
    pasta = pasta_com_trava()
    for cpf, email in (("123.456.789-00", "g@exemplo.invalid"),
                       (G1, "sem-arroba"), (G1, "a@b.c,outro@b.c"),
                       (G1, "=cmd@exemplo.invalid")):
        try:
            rol.nomear_gestor(pasta, cpf, email)
        except ValueError:
            pass
        else:
            checa(False, f"aceitou {cpf!r} / {email!r}")
    checa(not (pasta / rol.ARQUIVO_GESTORES).exists(),
          "uma recusa deixou arquivo para trás")
    print("  ok     CPF que não fecha e e-mail que não serve: recusa, sem gravar")


def teste_o_email_de_quem_ja_e_gestor_nao_muda_por_aqui():
    """Trocar o destino do código de quem JÁ entra é a decisão mais
    protegida do produto (T26). Nomear de novo com outro e-mail seria essa
    troca, feita de passagem — e para um GESTOR, cuja sessão vê a base."""
    pasta = pasta_com_trava()
    rol.nomear_gestor(pasta, G1, "de-antes@exemplo.invalid")
    antes = (pasta / rol.ARQUIVO_GESTORES).read_bytes()
    try:
        rol.nomear_gestor(pasta, G1, "outro@exemplo.invalid")
    except rol.GestorDivergente as e:
        checa("troca" in str(e).lower(), f"a recusa não aponta a saída: {e}")
    else:
        checa(False, "nomear de novo trocou o e-mail do gestor")
    checa((pasta / rol.ARQUIVO_GESTORES).read_bytes() == antes,
          "a recusa mexeu no arquivo")
    print("  ok     gestor já nomeado, outro e-mail: recusa e aponta a troca")


def teste_gestor_que_ja_e_filiado_usa_o_email_de_filiado():
    """O código vai para o e-mail de `filiados.csv` quando a pessoa está lá
    — o de `gestores.csv` só vale para quem não é filiado. Escrever outro
    e-mail aqui criaria um gestor cujo código vai para um endereço que quem
    o nomeou NÃO viu. Divergência não se resolve sozinha: marca e mostra."""
    pasta = pasta_com_trava()
    rol.acrescentar(pasta, [(G1, "filiado@exemplo.invalid")])
    try:
        rol.nomear_gestor(pasta, G1, "gestor@exemplo.invalid")
    except rol.GestorDivergente as e:
        checa("filiad" in str(e).lower(), f"não diz que é filiado: {e}")
        checa("filiado@exemplo.invalid" not in str(e),
              "a recusa escreveu o e-mail inteiro de alguém na mensagem")
    else:
        checa(False, "nomeou gestor com e-mail diferente do de filiado")
    checa(rol.nomear_gestor(pasta, G1, "filiado@exemplo.invalid") == "nomeado",
          "com o MESMO e-mail de filiado devia nomear")
    print("  ok     já é filiado: só com o mesmo e-mail; outro é recusado")


def teste_nomear_preserva_o_arquivo_que_o_sindicato_mandou():
    """`gestores.csv` pode ter vindo do Excel em português: `;`, latin-1,
    CRLF, colunas a mais. As linhas de quem já estava ficam byte a byte."""
    pasta = pasta_com_trava()
    caminho = pasta / rol.ARQUIVO_GESTORES
    original = ("Nome;CPF;Email;Função\r\n"
                f"JOSÉ DE EXEMPLO (FICTÍCIO);{G1};jose@exemplo.invalid;"
                "Secretário\r\n").encode("latin-1")
    caminho.write_bytes(original)
    rol.nomear_gestor(pasta, G2, "nova@exemplo.invalid")
    depois = caminho.read_bytes()
    checa(depois.startswith(original),
          f"as linhas de antes mudaram: {depois[:len(original)]!r}")
    checa(rol.carregar_gestores(pasta).por_cpf
          == {D1: "jose@exemplo.invalid", D2: "nova@exemplo.invalid"},
          f"{rol.carregar_gestores(pasta).por_cpf}")
    checa(depois.endswith(b"\r\n") and b";" in depois[len(original):],
          f"a linha nova não está no dialeto do arquivo: "
          f"{depois[len(original):]!r}")
    print("  ok     `;`, latin-1, CRLF e colunas a mais: preservados")


def teste_destituir_tira_so_de_gestor():
    """Deixar de ser gestor não é deixar de ser filiado: a pessoa continua
    entrando no portal, só não abre mais o painel."""
    pasta = pasta_com_trava()
    rol.acrescentar(pasta, [(G1, "a@exemplo.invalid")])
    rol.nomear_gestor(pasta, G1, "a@exemplo.invalid")
    rol.nomear_gestor(pasta, G2, "b@exemplo.invalid")
    checa(rol.destituir_gestor(pasta, G1) == 1, "não tirou")
    checa(set(rol.carregar_gestores(pasta).por_cpf) == {D2},
          f"gestores: {rol.carregar_gestores(pasta).por_cpf}")
    checa(D1 in rol.carregar(pasta).por_cpf,
          "destituir tirou a pessoa do rol de FILIADOS")
    checa(rol.destituir_gestor(pasta, G1) == 0, "tirou duas vezes")
    print("  ok     sai de gestor, continua filiado")


# ------------------------------------------------------- criar o sindicato

def teste_criar_poe_o_sindicato_de_pe():
    secao("criar o sindicato")
    raiz = raiz_nova()
    codigo, disse = rodar(raiz, "criar", "demo-novo", "Sindicato Novo (Exemplo)",
                          "--categoria", CATEGORIA,
                          "--gestor", f"{G1}=gestor@exemplo.invalid")
    checa(codigo == 0, f"saiu {codigo}: {disse}")
    ent = entidades.Cadastro(raiz).resolver("demo-novo")
    checa(ent.nome == "Sindicato Novo (Exemplo)"
          and ent.categorias == (CATEGORIA,), f"{ent}")
    checa(rol.carregar_gestores(ent.pasta(raiz)).por_cpf
          == {D1: "gestor@exemplo.invalid"}, "o gestor não foi nomeado")
    checa("entidade=demo-novo" in disse and "tela=painel" in disse,
          f"não disse por onde o gestor entra: {disse}")
    checa(D1 not in disse and G1 not in disse,
          "a ferramenta escreveu o CPF inteiro do gestor na saída")
    print("  ok     cria, nomeia o gestor, e diz por onde ele entra")


def teste_criar_e_tudo_ou_nada():
    """Uma letra trocada no slug da categoria derruba TODA rota daquele
    sindicato (`carregar_categorias` falha alto, de propósito). E um gestor
    torto deixaria um sindicato criado que ninguém consegue abrir. Nos dois
    casos a recusa vem antes de qualquer gravação."""
    raiz = raiz_nova()
    casos = (
        (["--categoria", "auditor-fiscal-receita-federa",
          "--gestor", f"{G1}=g@exemplo.invalid"], CATEGORIA),
        (["--categoria", CATEGORIA, "--gestor", "123.456.789-00=g@exemplo.invalid"],
         "cpf"),
        (["--categoria", CATEGORIA, "--gestor", f"{G1}=sem-arroba"], "e-mail"),
        (["--categoria", CATEGORIA, "--gestor", f"{G1}"], "="),
        (["--categoria", CATEGORIA, "--gestor", f"{G1}=a@exemplo.invalid",
          "--gestor", f"{G1}=b@exemplo.invalid"], "duas vezes"),
        (["--gestor", f"{G1}=g@exemplo.invalid"], "categoria"),
        (["--categoria", CATEGORIA], "gestor"),
    )
    for args, pista in casos:
        codigo, disse = rodar(raiz, "criar", "demo-novo", "Sindicato", *args)
        checa(codigo != 0, f"aceitou {args}")
        checa(pista.lower() in disse.lower(),
              f"{args}: a recusa não diz o que está errado ({pista!r}): {disse}")
        checa(not existe(raiz, "demo-novo"),
              f"{args}: recusou e deixou o sindicato criado")
        checa(not (raiz / "demo-novo").exists(),
              f"{args}: recusou e deixou a pasta do sindicato")
    codigo, disse = rodar(raiz, "criar", "Demo Novo", "Sindicato",
                          "--categoria", CATEGORIA,
                          "--gestor", f"{G1}=g@exemplo.invalid")
    checa(codigo != 0 and not (raiz / entidades.ARQUIVO).exists(),
          f"aceitou apelido com espaço e maiúscula: {disse}")
    print("  ok     categoria, CPF, e-mail, falta de gestor: recusa sem criar nada")


def teste_criar_o_que_ja_existe_nao_mexe_no_primeiro():
    raiz = raiz_nova()
    args = ("--categoria", CATEGORIA, "--gestor", f"{G1}=g@exemplo.invalid")
    rodar(raiz, "criar", "demo-novo", "O Primeiro", *args)
    antes = (raiz / entidades.ARQUIVO).read_bytes()
    gestores = (raiz / "demo-novo" / rol.ARQUIVO_GESTORES).read_bytes()
    codigo, disse = rodar(raiz, "criar", "demo-novo", "O Segundo",
                          "--categoria", CATEGORIA,
                          "--gestor", f"{G2}=outro@exemplo.invalid")
    checa(codigo != 0 and "já existe" in disse, f"{codigo}: {disse}")
    checa((raiz / entidades.ARQUIVO).read_bytes() == antes
          and (raiz / "demo-novo" / rol.ARQUIVO_GESTORES).read_bytes()
          == gestores,
          "criar por cima mexeu no sindicato que já existia")
    print("  ok     apelido repetido: recusa, e o primeiro fica como estava")


def teste_a_ferramenta_diz_se_e_demonstracao_ou_de_verdade():
    """`demo-` no apelido muda o que o SERVIDOR faz: ele atende em modo
    ensaio e mostra a faixa de demonstração. Quem cria precisa ler isso na
    hora — um sindicato de verdade criado como `demo-...` receberia a faixa
    dizendo que os dados são apagados."""
    raiz = raiz_nova()
    args = ("--categoria", CATEGORIA, "--gestor", f"{G1}=g@exemplo.invalid")
    _, demo = rodar(raiz, "criar", "demo-novo", "Demonstração", *args)
    _, real = rodar(raiz, "criar", "sind-exemplo", "Sindicato de Exemplo", *args)
    checa("DEMONSTRAÇÃO" in demo, f"não disse que é demonstração: {demo}")
    checa("DEMONSTRAÇÃO" not in real and "de verdade" in real.lower(),
          f"não disse que é um sindicato de verdade: {real}")
    print("  ok     diz, na criação, se é demonstração ou sindicato de verdade")


# ---------------------------------------------------------------- o dia a dia

def teste_listar_mostra_o_que_esta_faltando():
    secao("o dia a dia")
    raiz = raiz_nova()
    rodar(raiz, "criar", "demo-novo", "Sindicato Completo",
          "--categoria", CATEGORIA, "--gestor", f"{G1}=g@exemplo.invalid")
    # Um sindicato criado do jeito ANTIGO: sem categoria e sem gestor.
    entidades.Cadastro(raiz).criar("demo-velho", "Sindicato Incompleto")
    codigo, disse = rodar(raiz, "listar")
    checa(codigo == 0, f"{codigo}: {disse}")
    linhas = {l.split()[0]: l for l in disse.splitlines()
              if l.strip().startswith("demo-")}
    checa("SEM" not in linhas.get("demo-novo", "SEM"),
          f"o completo aparece com falta: {linhas.get('demo-novo')}")
    velho = linhas.get("demo-velho", "")
    checa("SEM CATEGORIA" in velho and "SEM GESTOR" in velho,
          f"o incompleto não aparece com o que falta: {velho!r}")
    print("  ok     listar: cada sindicato, e o que falta em cada um")


def teste_gestor_nomear_tirar_e_listar():
    raiz = raiz_nova()
    rodar(raiz, "criar", "demo-novo", "Sindicato",
          "--categoria", CATEGORIA, "--gestor", f"{G1}=a@exemplo.invalid")
    codigo, disse = rodar(raiz, "gestor", "demo-novo", "nomear", G2,
                          "b@exemplo.invalid")
    checa(codigo == 0, f"{codigo}: {disse}")
    codigo, disse = rodar(raiz, "gestor", "demo-novo", "listar")
    checa("a@exemplo.invalid" in disse and "b@exemplo.invalid" in disse,
          f"{disse}")
    checa(D1 not in disse and D2 not in disse,
          "listar gestores escreveu CPF inteiro")
    codigo, disse = rodar(raiz, "gestor", "demo-novo", "nomear", G2,
                          "outro@exemplo.invalid")
    checa(codigo != 0 and "trocas_de_email" in disse,
          f"trocar e-mail de gestor passou, ou não apontou a ferramenta: {disse}")
    rodar(raiz, "gestor", "demo-novo", "tirar", G2)
    codigo, disse = rodar(raiz, "gestor", "demo-novo", "tirar", G1)
    checa(codigo == 0 and "ninguém" in disse.lower(),
          f"tirou o ÚLTIMO gestor sem avisar que ninguém abre o painel: {disse}")
    codigo, disse = rodar(raiz, "gestor", "demo-nao-existe", "listar")
    checa(codigo != 0, "aceitou sindicato que não existe")
    print("  ok     nomear, listar sem CPF inteiro, tirar — e o aviso do último")


def teste_categorias_mostra_o_que_da_para_contratar():
    raiz = raiz_nova()
    codigo, disse = rodar(raiz, "categorias")
    checa(codigo == 0 and CATEGORIA in disse, f"{codigo}: {disse}")
    print("  ok     categorias: o que existe no catálogo")


# ------------------------------------------- quem criou consegue entrar

def teste_o_gestor_do_sindicato_criado_entra_e_ve_as_acoes():
    """A prova de que a criação serve: o gestor nomeado pela ferramenta pede
    o código, entra, e o painel conhece as ações da categoria contratada."""
    secao("quem criou consegue entrar")
    from fastapi.testclient import TestClient

    from servidor.app import criar_app
    from servidor.config import carregar

    raiz = raiz_nova()
    codigo, disse = rodar(raiz, "criar", "demo-novo", "Sindicato Novo",
                          "--categoria", CATEGORIA,
                          "--gestor", f"{G1}=gestor@exemplo.invalid")
    checa(codigo == 0, disse)
    cliente = TestClient(criar_app(carregar({
        "PROTOCOL_MODO_ENSAIO": "1", "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_AGENDAR": "0",
    })))
    r = cliente.post("/api/acesso/codigo",
                     json={"entidade": "demo-novo", "cpf": G1})
    numero = r.json().get("codigo_do_ensaio", "")
    checa(bool(numero), f"o gestor nomeado não recebeu código: {r.text[:200]}")
    r = cliente.post("/api/acesso/conferir",
                     json={"entidade": "demo-novo", "cpf": G1, "codigo": numero})
    token = r.json().get("token", "")
    r = cliente.get("/api/entidade/demo-novo/rol-de-substituidos",
                    headers={"Authorization": f"Bearer {token}"})
    checa(r.status_code == 200, f"o painel não abriu: {r.status_code} {r.text[:200]}")
    checa([a["acao"] for a in r.json().get("acoes", [])] == ["GIFA-2006"],
          f"o painel não conhece as ações da categoria contratada: {r.text[:200]}")
    # E quem NÃO foi nomeado continua de fora.
    r = cliente.post("/api/acesso/codigo",
                     json={"entidade": "demo-novo", "cpf": G2})
    checa(not r.json().get("codigo_do_ensaio"),
          "CPF que não é gestor recebeu código")
    print("  ok     criado pela ferramenta: o gestor entra, e só ele")


TESTES.extend([
    teste_nomear_cria_o_arquivo_fechado_e_o_portao_le,
    teste_cpf_ou_email_que_nao_serve_nao_escreve_nada,
    teste_o_email_de_quem_ja_e_gestor_nao_muda_por_aqui,
    teste_gestor_que_ja_e_filiado_usa_o_email_de_filiado,
    teste_nomear_preserva_o_arquivo_que_o_sindicato_mandou,
    teste_destituir_tira_so_de_gestor,
    teste_criar_poe_o_sindicato_de_pe,
    teste_criar_e_tudo_ou_nada,
    teste_criar_o_que_ja_existe_nao_mexe_no_primeiro,
    teste_a_ferramenta_diz_se_e_demonstracao_ou_de_verdade,
    teste_listar_mostra_o_que_esta_faltando,
    teste_gestor_nomear_tirar_e_listar,
    teste_categorias_mostra_o_que_da_para_contratar,
    teste_o_gestor_do_sindicato_criado_entra_e_ve_as_acoes,
])


def main() -> int:
    print("=" * 70)
    print("SINDICATOS — pôr um sindicato novo para funcionar")
    print("=" * 70)
    for teste in TESTES:
        antes = len(falhas)
        try:
            teste()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{teste.__name__}: levantou "
                          f"{type(exc).__name__}: {exc}")
            print(f"  FALHA  {teste.__name__}")
        else:
            if len(falhas) > antes:
                print(f"  FALHA  {teste.__name__}")
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
