#!/usr/bin/env python3
"""
A PORTA QUE NÃO EXISTIA: os documentos que o sindicato já tem.

A auditoria achou isto: o ÚNICO jeito de um PDF entrar no sistema era pelo
`/api/cadastro`, que exige a pessoa ter aberto sessão com o código que foi
para o e-mail dela. Se o sindicato tinha 4.000 sentenças numa pasta, não
havia porta — e é dele que vem o acervo documental que já existe.

O PROBLEMA DIFÍCIL AQUI NÃO É LER PDF: é saber **de quem é cada arquivo**.
Casar errado é mostrar a sentença de uma pessoa para outra, e isso é o pior
defeito que este produto pode ter. Por isso são três formas, em ordem de
confiança, e a dúvida nunca vira palpite:

    1. o CPF no NOME do arquivo      — o sindicato nomeou, é declaração dele
    2. o CPF DENTRO do texto         — só quando há um só, e ele fecha
    3. nada                          — vai para a pilha, nominal, com motivo

E duas recusas que não se negociam:

    DOIS CPFs DIFERENTES no mesmo arquivo -> não casa com ninguém. Pode ser
    sentença coletiva, petição com litisconsortes, ou PDF concatenado. Em
    qualquer um dos casos, escolher um dos dois é sortear.

    CPF QUE NÃO ESTÁ NA BASE -> não entra. Um arquivo de outra entidade,
    ou de alguém que o sindicato não declarou, ficaria guardado sob um CPF
    que ninguém ali reconhece.

E O ZIP É ARQUIVO DE FORA. Nome de entrada com `../` escreve onde quiser, e
arquivo que descompacta em gigabytes derruba o servidor. As duas coisas são
testadas aqui.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import documentos_do_sindicato as lote  # noqa: E402

falhas: list[str] = []

A, B = "11144477735", "52998224725"
#: Está na base, mas o arquivo não é dele.
FORA = "01234567890"


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def pdf(linhas: list[str]) -> bytes:
    def esc(t: str) -> str:
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    conteudo = ["BT", "/F1 11 Tf", "14 TL", "40 790 Td"]
    for linha in linhas:
        conteudo += [f"({esc(linha)}) Tj", "T*"]
    conteudo.append("ET")
    fluxo = "\n".join(conteudo).encode("latin-1", "replace")
    objetos = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>stream\n" % len(fluxo) + fluxo + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    desloc = []
    for i, o in enumerate(objetos, 1):
        desloc.append(len(saida))
        saida += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    inicio = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for d in desloc:
        saida += b"%010d 00000 n \n" % d
    saida += (b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objetos) + 1, inicio))
    return bytes(saida)


CORPO = [
    "PODER JUDICIARIO - JUSTICA FEDERAL",
    "SECAO JUDICIARIA DO DISTRITO FEDERAL",
    "",
    "Processo n. 0010391-24.2006.4.01.3400",
    "",
    "SENTENCA",
    "",
    "Ante o exposto, julgo PROCEDENTE o pedido formulado na inicial.",
    "",
    "Documento de exemplo, para demonstracao do sistema.",
]


def _pontuado(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def sentenca(cpf: str = "") -> bytes:
    """Documento de verdade traz o CPF PONTUADO, e é essa forma que o leitor
    reconhece. A restrição é do produto: onze dígitos soltos num texto
    judicial podem ser protocolo, matrícula ou número de guia."""
    corpo = list(CORPO)
    if cpf:
        corpo.insert(4, f"CPF do interessado: {_pontuado(cpf)}")
    return pdf(corpo)


BASE = (A, B, FORA)


# ------------------------------------------------------------ o casamento

def teste_cpf_no_nome_do_arquivo_casa():
    """A forma mais confiável: o sindicato nomeou o arquivo. É declaração
    dele sobre o arquivo dele."""
    secao("de quem é cada arquivo")
    r = lote.casar([("111.444.777-35 - sentenca.pdf", sentenca())], BASE)
    checa(r.casados.get(A) is not None, f"não casou pelo nome: {r.casados}")
    checa(r.casados[A][0].motivo == lote.PELO_NOME,
          f"motivo errado: {r.casados[A][0].motivo}")
    print("  ok     CPF no nome do arquivo")


def teste_cpf_no_texto_casa_quando_e_o_unico():
    r = lote.casar([("doc001.pdf", sentenca(A))], BASE)
    checa(r.casados.get(A) is not None, f"não casou pelo texto: {r.sobraram}")
    checa(r.casados[A][0].motivo == lote.PELO_TEXTO,
          f"motivo errado: {r.casados[A][0].motivo}")
    print("  ok     CPF único dentro do texto")


def teste_o_nome_vence_o_texto():
    """Se os dois existem e discordam, vale o do nome — e a discordância é
    reportada, nunca engolida."""
    r = lote.casar([("111.444.777-35.pdf", sentenca(B))], BASE)
    checa(r.casados.get(A) is not None,
          f"o texto venceu o nome do arquivo: {r.casados}")
    checa(any("discord" in a.lower() or "difere" in a.lower()
              for a in r.avisos),
          f"a discordância entre nome e texto não foi reportada: {r.avisos}")
    print("  ok     o nome vence, e a discordância é dita")


def teste_dois_cpfs_no_texto_nao_casa_com_ninguem():
    """Pode ser coletiva, litisconsórcio ou PDF concatenado. Em qualquer um
    dos casos, escolher um dos dois é sortear — com a sentença de alguém."""
    corpo = list(CORPO)
    corpo.insert(4, f"Interessados: {_pontuado(A)} e {_pontuado(B)}")
    r = lote.casar([("doc002.pdf", pdf(corpo))], BASE)
    checa(r.casados == {}, f"escolheu um CPF entre dois: {r.casados}")
    checa(len(r.sobraram) == 1, f"{r.sobraram}")
    checa("mais de um" in r.sobraram[0].motivo.lower()
          or "dois" in r.sobraram[0].motivo.lower(),
          f"o motivo não explica: {r.sobraram[0].motivo!r}")
    print("  ok     dois CPFs: não casa, e diz por quê")


def teste_sem_cpf_nenhum_vai_para_a_pilha():
    r = lote.casar([("qualquer.pdf", sentenca())], BASE)
    checa(r.casados == {}, "casou um arquivo sem CPF")
    checa(len(r.sobraram) == 1 and r.sobraram[0].arquivo == "qualquer.pdf",
          f"{r.sobraram}")
    print("  ok     sem CPF: vai para a pilha, com nome de arquivo")


def teste_cpf_de_fora_da_base_nao_entra():
    """Guardar um arquivo sob um CPF que a entidade não declarou é guardar
    dado de alguém que não é cliente dela."""
    r = lote.casar([("529.982.247-25.pdf", sentenca())], (A,))
    checa(r.casados == {}, f"aceitou CPF fora da base: {r.casados}")
    checa("base" in r.sobraram[0].motivo.lower(),
          f"o motivo não diz que está fora da base: {r.sobraram[0].motivo!r}")
    print("  ok     CPF fora da base é recusado, não guardado")


def teste_cpf_que_nao_fecha_e_ignorado_como_identificacao():
    """Só CPF que fecha o dígito verificador identifica alguém. Pontuado e
    tudo, `111.444.777-99` é erro de digitação — e casar por ele poria a
    sentença de alguém na conta de outra pessoa."""
    corpo = list(CORPO)
    corpo.insert(4, "CPF do interessado: 111.444.777-99")
    r = lote.casar([("doc003.pdf", pdf(corpo))], BASE)
    checa(r.casados == {}, f"casou por um CPF que não fecha: {r.casados}")
    # E no NOME do arquivo vale a mesma régua.
    r = lote.casar([("111.444.777-99 - sentenca.pdf", sentenca())], BASE)
    checa(r.casados == {}, f"casou pelo nome com CPF que não fecha: {r.casados}")
    print("  ok     CPF que não fecha não identifica ninguém")


# ---------------------------------------------------------- o tipo do papel

def teste_o_tipo_vem_do_nome_quando_o_sindicato_nomeou():
    secao("que papel é este")
    for nome, esperado in (
        ("111.444.777-35 - sentenca.pdf", "sentenca"),
        ("11144477735_certidao_transito.pdf", "certidao_transito"),
        ("11144477735 contribuicao 2004.pdf", "contribuicao"),
    ):
        r = lote.casar([(nome, sentenca())], BASE)
        achado = r.casados[A][0].tipo
        checa(achado == esperado,
              f"{nome!r} -> tipo {achado!r}, esperado {esperado!r}")
    print("  ok     três nomes, três tipos")


def teste_sem_pista_no_nome_o_conteudo_decide_so_quando_e_claro():
    """SÓ QUANDO É CLARO. Um PDF com "julgo procedente" é sentença; um sem
    nada disso é `outro` — e `outro` não é defeito, é a verdade. Chutar o
    tipo faria a tela da pessoa dizer que a sentença dela chegou."""
    r = lote.casar([("111.444.777-35.pdf", sentenca())], BASE)
    checa(r.casados[A][0].tipo == "sentenca",
          f"não reconheceu a sentença pelo conteúdo: {r.casados[A][0].tipo}")

    r = lote.casar([("111.444.777-35 arquivo.pdf",
                     pdf(["Documento qualquer, sem dispositivo nenhum.",
                          "Apenas texto de exemplo para demonstracao.",
                          "Nao se refere a pessoa real, e nao e decisao."]))],
                   BASE)
    checa(r.casados[A][0].tipo == "outro",
          f"chutou um tipo: {r.casados[A][0].tipo}")
    print("  ok     conteúdo decide quando é claro; senão, 'outro'")


# ------------------------------------------------------------------- o zip

def _zip(entradas: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in entradas:
            z.writestr(nome, dados)
    return buffer.getvalue()


def teste_le_o_zip_que_o_sindicato_mandou():
    secao("o zip")
    arquivos = lote.abrir_zip(_zip([
        ("111.444.777-35 - sentenca.pdf", sentenca()),
        ("pasta/529.982.247-25.pdf", sentenca()),
    ]))
    nomes = sorted(n for n, _ in arquivos)
    checa(len(arquivos) == 2, f"leu {len(arquivos)} arquivos: {nomes}")
    # O caminho dentro do zip NÃO vira caminho no disco: só o nome importa.
    checa(all("/" not in n for n in nomes), f"caminho sobreviveu: {nomes}")
    print(f"  ok     {len(arquivos)} arquivos, sem caminho")


def teste_zip_com_caminho_para_fora_e_recusado():
    """`../../etc/x.pdf` escreve onde quiser. É a falha clássica de quem
    descompacta arquivo de fora, e o sindicato manda arquivo de fora."""
    try:
        lote.abrir_zip(_zip([("../../fora.pdf", sentenca())]))
        checa(False, "aceitou caminho que sai da pasta")
    except lote.ZipRecusado as e:
        checa("caminho" in str(e).lower() or "fora" in str(e).lower(),
              f"mensagem obscura: {e}")
        print("  ok     caminho para fora da pasta é recusado")


def teste_zip_que_descompacta_grande_demais_e_recusado():
    """Arquivo pequeno que vira gigabytes derruba o servidor. O tamanho
    DECLARADO é conferido antes de descompactar: conferir depois já é tarde."""
    gigante = _zip([("grande.pdf", b"%PDF-1.4\n" + b"\0" * (40 * 1024 * 1024))])
    try:
        lote.abrir_zip(gigante, teto_total=1024 * 1024)
        checa(False, "aceitou zip que estoura o teto")
    except lote.ZipRecusado as e:
        checa("tamanho" in str(e).lower() or "teto" in str(e).lower()
              or "grande" in str(e).lower(),
              f"mensagem obscura: {e}")
        print("  ok     zip que estoura o teto é recusado antes de abrir")


def teste_zip_ignora_o_que_nao_e_pdf():
    arquivos = lote.abrir_zip(_zip([
        ("111.444.777-35.pdf", sentenca()),
        ("planilha.xlsx", b"PK\x03\x04qualquer"),
        ("__MACOSX/._111.444.777-35.pdf", b"lixo do mac"),
    ]))
    checa(len(arquivos) == 1, f"{[n for n, _ in arquivos]}")
    print("  ok     só PDF entra; lixo do sistema de arquivos sai")


# ------------------------------------------------------- o que sobra importa

def teste_a_pilha_do_que_nao_casou_e_o_produto():
    """Contagem não serve: o sindicato precisa saber QUAIS arquivos ficaram
    de fora, para abrir e decidir. 'Casei 3.812 de 4.000' esconde 188
    sentenças de gente que fica sem resposta."""
    secao("o que sobra")
    r = lote.casar([
        ("111.444.777-35.pdf", sentenca()),
        ("semcpf.pdf", sentenca()),
        ("outro.pdf", sentenca()),
    ], BASE)
    checa(len(r.casados) == 1 and len(r.sobraram) == 2, f"{r}")
    for s in r.sobraram:
        checa(bool(s.arquivo) and bool(s.motivo),
              f"sobra sem nome ou sem motivo: {s}")
    print(f"  ok     {len(r.sobraram)} sobras, cada uma com nome e motivo")


def teste_varios_documentos_da_mesma_pessoa():
    r = lote.casar([
        ("111.444.777-35 - contribuicao 2004.pdf", sentenca()),
        ("111.444.777-35 - contribuicao 2005.pdf", sentenca()),
        ("111.444.777-35 - sentenca.pdf", sentenca()),
    ], BASE)
    checa(len(r.casados.get(A, [])) == 3,
          f"perdeu documento da mesma pessoa: {r.casados}")
    tipos = sorted(d.tipo for d in r.casados[A])
    checa(tipos == ["contribuicao", "contribuicao", "sentenca"], f"{tipos}")
    print("  ok     três documentos da mesma pessoa, sem perder nenhum")


def teste_pdf_ilegivel_vira_sobra_nao_erro():
    """Um arquivo quebrado no meio de 4.000 não pode derrubar a ingestão."""
    r = lote.casar([
        ("111.444.777-35.pdf", b"%PDF-1.4\nisto nao e um pdf de verdade"),
        ("529.982.247-25 - sentenca.pdf", sentenca()),
    ], BASE)
    checa(r.casados.get(B) is not None, "o arquivo bom se perdeu junto")
    print("  ok     PDF quebrado não derruba o lote")


TESTES = [
    teste_cpf_no_nome_do_arquivo_casa,
    teste_cpf_no_texto_casa_quando_e_o_unico,
    teste_o_nome_vence_o_texto,
    teste_dois_cpfs_no_texto_nao_casa_com_ninguem,
    teste_sem_cpf_nenhum_vai_para_a_pilha,
    teste_cpf_de_fora_da_base_nao_entra,
    teste_cpf_que_nao_fecha_e_ignorado_como_identificacao,
    teste_o_tipo_vem_do_nome_quando_o_sindicato_nomeou,
    teste_sem_pista_no_nome_o_conteudo_decide_so_quando_e_claro,
    teste_le_o_zip_que_o_sindicato_mandou,
    teste_zip_com_caminho_para_fora_e_recusado,
    teste_zip_que_descompacta_grande_demais_e_recusado,
    teste_zip_ignora_o_que_nao_e_pdf,
    teste_a_pilha_do_que_nao_casou_e_o_produto,
    teste_varios_documentos_da_mesma_pessoa,
    teste_pdf_ilegivel_vira_sobra_nao_erro,
]


def main() -> int:
    print("=" * 62)
    print("OS DOCUMENTOS QUE O SINDICATO JÁ TEM")
    print("=" * 62)
    for t in TESTES:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{t.__name__} levantou {type(e).__name__}: {e}")
    print()
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
