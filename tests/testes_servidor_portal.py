#!/usr/bin/env python3
"""
O servidor do portal, exercitado por HTTP de ponta a ponta.

POR QUE ESTA SUÍTE BATE NO HTTP E NÃO NAS FUNÇÕES

Porque o que protege o cadastro não é nenhuma função isolada: é a ordem em que
elas são chamadas. O portão confere o código, a sessão guarda de quem é, a
validação recusa a linha, o depósito grava. Testar cada peça deixa passar
exatamente o furo que importa — alguém que chama o depósito sem passar pelo
portão, ou que manda um CPF no formulário diferente do que abriu a sessão.

E o último teste fecha o laço: pega a entrega que o servidor acabou de gravar
e manda `ferramentas/conferir_entrega.py` consumir, sem adaptação. Se o
servidor produz algo que o motor recusa, é aqui que aparece — não no
escritório, dias depois.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

falhas: list[str] = []

#: As pastas criadas pelos cenários, para apagar no fim. Cada cenário criava
#: uma e ninguém apagava: 112 sobras em /tmp depois de alguns dias. Nenhuma
#: tem dado de gente — são CPFs sintéticos — mas suíte que acumula lixo acaba
#: sendo a suíte que enche o disco no dia errado.
_NASCIDOS: list[Path] = []


def _limpar() -> None:
    for pasta in _NASCIDOS:
        shutil.rmtree(pasta, ignore_errors=True)
    _NASCIDOS.clear()


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)
        print(f"  FALHA  {msg}")


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# --------------------------------------------------------------------- PDFs


def pdf_com_texto(linhas: list[str]) -> bytes:
    """PDF de uma página com texto extraível de verdade.

    Não serve `b"%PDF-1.4\\n% texto"`: o servidor confere a camada de texto
    com pypdf, e um comentário não é texto de página. Um dublê mais frouxo que
    o original produz verde que mente.
    """

    def esc(t: str) -> str:
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    conteudo = ["BT", "/F1 11 Tf", "14 TL", "40 760 Td"]
    for linha in linhas:
        conteudo += [f"({esc(linha)}) Tj", "T*"]
    conteudo.append("ET")
    fluxo = "\n".join(conteudo).encode("latin-1", "replace")

    objetos = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>\nstream\n" % len(fluxo) + fluxo + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    saida = io.BytesIO()
    saida.write(b"%PDF-1.4\n")
    deslocamentos = []
    for i, obj in enumerate(objetos, start=1):
        deslocamentos.append(saida.tell())
        saida.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    inicio = saida.tell()
    saida.write(b"xref\n0 %d\n" % (len(objetos) + 1))
    saida.write(b"0000000000 65535 f \n")
    for d in deslocamentos:
        saida.write(b"%010d 00000 n \n" % d)
    saida.write(
        b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objetos) + 1, inicio)
    )
    return saida.getvalue()


from servidor import rol
from nucleo import processo_cnj

CPF = "526.018.159-06"
CPF_DIGITOS = "52601815906"
OUTRO_CPF = "111.444.777-35"


def numero(sequencial: str, tribunal: str, origem: str, ano: str = "2019") -> str:
    """Um número CNJ com o dígito verificador CALCULADO.

    Escrever o número à mão já custou um teste vermelho nesta própria suíte: o
    `0001234-56...` que eu digitei tem dígito 70, e o validador — certo —
    reprovou. Vetor de teste escrito à mão testa a minha aritmética, não o
    código.
    """
    dv = processo_cnj.calcular_verificador(sequencial, ano, "4", tribunal, origem)
    return f"{sequencial}-{dv}.{ano}.4.{tribunal}.{origem}"


PROCESSO = numero("0001234", "01", "3400")
PROCESSO_OUTRO_TRIBUNAL = numero("0001234", "05", "8300")


def pacote(cpf: str = CPF, com_processo: bool = True) -> list[tuple]:
    """Os arquivos do envio, no formato que o httpx manda como multipart."""
    base = [
        (
            "procuracao.pdf",
            [
                "PROCURACAO",
                f"Outorgante: FULANO DE TAL, CPF {cpf}, servidor publico,",
                "nomeia e constitui seu bastante procurador, conferindo",
                "poderes para propor execucao de sentenca e promover o",
                "cumprimento do titulo judicial, substabelecer e dar",
                "quitacao.",
            ],
        ),
        (
            "identidade.pdf",
            [
                "REGISTRO GERAL",
                f"Nome: FULANO DE TAL   CPF: {cpf}",
                "Filiacao: BELTRANO DE TAL e CICRANA DE TAL",
                "Data de nascimento: 10/03/1968   Naturalidade: Goiania GO",
                "Orgao expedidor: SSP GO",
            ],
        ),
        (
            "comprovante_residencia.pdf",
            [
                "FATURA DE ENERGIA ELETRICA",
                f"Titular: FULANO DE TAL   CPF {cpf}",
                "Endereco: Rua das Acacias, 100, Setor Central",
                "Municipio: Goiania   UF: GO   CEP 74000-000",
                "Referencia: setembro de 2026",
            ],
        ),
    ]
    if com_processo:
        base += [
            (
                "sentenca.pdf",
                [
                    "SENTENCA",
                    f"Processo {PROCESSO}",
                    f"Autor: FULANO DE TAL, CPF {cpf}",
                    "Reu: UNIAO FEDERAL",
                    "Julgo procedente o pedido e condeno a re ao pagamento",
                    "das diferencas remuneratorias apuradas em liquidacao.",
                ],
            ),
            (
                "certidao_transito.pdf",
                [
                    "CERTIDAO DE TRANSITO EM JULGADO",
                    f"Certifico que a sentenca proferida no processo {PROCESSO}",
                    f"em que figura FULANO DE TAL, CPF {cpf}, transitou em",
                    "julgado, nada havendo de recurso pendente de julgamento.",
                ],
            ),
        ]
    return [
        ("arquivos", (nome, pdf_com_texto(linhas), "application/pdf"))
        for nome, linhas in base
    ]


def linha(cpf: str = CPF, **trocas) -> dict:
    base = {
        "id_externo": "".join(c for c in cpf if c.isdigit()),
        "cpf": cpf,
        "nome_completo": "Fulano de Tal",
        "matricula": "123456",
        "rg": "1234567",
        # Obrigatória desde 27/10/2026: é dela que sai a prioridade de
        # tramitação. 68 anos na data de referência.
        "data_nascimento": "1958-06-27",
        "email": "fulano@exemplo.org",
        "telefone": "(62) 99999-0000",
        "cep": "74000-000",
        "logradouro": "Rua das Acacias",
        "numero": "100",
        "complemento": "",
        "bairro": "Setor Central",
        "municipio": "Goiania",
        "uf": "GO",
        "cargo": "Auditor Fiscal",
        "situacao": "aposentado",
        "unidade": "Delegacia da Receita Federal",
        "data_ingresso": "1992-04-01",
        "data_aposentadoria": "2018-06-30",
        "tem_processo": "sim",
        "numero_processo": PROCESSO,
        "observacao_processo": "",
        "ja_tem_execucao": "nao",
        "ja_recebeu_acordo": "nao",
        "outro_advogado": "nao",
        "ciencia_e_iniciativa": "sim",
    }
    base.update(trocas)
    return base


# ------------------------------------------------------------------- cenário


class Cenario:
    """Um servidor em modo ensaio, com uma entidade e um rol."""

    def __init__(
        self,
        com_rol: bool = True,
        entidades_extra: tuple = (),
        limite_de_emissoes: int = 0,
        origens: tuple[str, ...] = (),
    ) -> None:
        from fastapi.testclient import TestClient

        from servidor import entidades as mod_entidades
        from servidor.app import criar_app
        from servidor.config import carregar

        self.raiz = Path(tempfile.mkdtemp(prefix="portal-teste-"))
        _NASCIDOS.append(self.raiz)
        # Os testes que NÃO são sobre o limite por hora pedem vários códigos,
        # e esbarrar no limite deles faria o teste falhar por motivo errado —
        # que é o que acabou de acontecer. Quem testa o limite pede o limite.
        ambiente = {
            "PROTOCOL_MODO_ENSAIO": "1",
            "PROTOCOL_RAIZ": str(self.raiz),
            "PROTOCOL_EMISSOES_POR_CPF_HORA": str(limite_de_emissoes or 50),
            "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": str(limite_de_emissoes or 500),
        }
        if origens:
            ambiente["PROTOCOL_ORIGENS"] = ",".join(origens)
        self.cfg = carregar(ambiente)
        cadastro = mod_entidades.Cadastro(self.raiz)
        self.ent = cadastro.criar("demo-teste", "Sindicato de Teste")
        for apelido, nome in entidades_extra:
            cadastro.criar(apelido, nome)
        if com_rol:
            self.escrever_rol("demo-teste", [(CPF, "fulano@exemplo.org")])
        self.cliente = TestClient(criar_app(self.cfg))

    def escrever_rol(self, apelido: str, pares: list[tuple[str, str]]) -> None:
        pasta = self.raiz / apelido
        pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "filiados.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cpf", "email", "nome"])
            for cpf, email in pares:
                w.writerow([cpf, email, "Fulano de Tal"])

    def escrever_gestores(self, apelido: str,
                          pares: list[tuple[str, str]]) -> None:
        pasta = self.raiz / apelido
        pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "gestores.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cpf", "email"])
            for cpf, email in pares:
                w.writerow([cpf, email])

    def cadastrar(self, cpf: str = CPF, **trocas):
        """Um cadastro completo, pelo caminho de produção."""
        return self.enviar(self.token(cpf), linha(cpf, **trocas), pacote(cpf))

    def token(self, cpf: str = CPF, apelido: str = "demo-teste") -> str:
        r = self.cliente.post(
            "/api/acesso/codigo", json={"entidade": apelido, "cpf": cpf}
        )
        codigo = r.json()["codigo_do_ensaio"]
        r = self.cliente.post(
            "/api/acesso/conferir",
            json={"entidade": apelido, "cpf": cpf, "codigo": codigo},
        )
        return r.json()["token"]

    def enviar(self, token: str, dados: dict, arquivos: list[tuple]):
        return self.cliente.post(
            "/api/cadastro",
            data={"token": token, "linha": json.dumps(dados)},
            files=arquivos,
        )


# -------------------------------------------------------------------- testes


def teste_saude_e_entidade():
    secao("saúde e entidade")
    c = Cenario()
    r = c.cliente.get("/saude")
    checa(r.status_code == 200 and r.json()["ok"], "saúde não responde")
    checa(
        r.json()["modo_ensaio"] is True,
        "a saúde devia dizer que está em modo ensaio",
    )
    r = c.cliente.get("/api/entidade/demo-teste")
    checa(r.json()["nome"] == "Sindicato de Teste", "nome da entidade errado")
    r = c.cliente.get("/api/entidade/nao-existe")
    checa(r.status_code == 404, "entidade inexistente devia dar 404")
    # Maiúscula no link é erro de digitação de gente, não ataque.
    r = c.cliente.get("/api/entidade/DEMO-Teste")
    checa(r.status_code == 200, "o apelido devia aceitar maiúscula do usuário")
    print("  ok     saúde, entidade e apelido com maiúscula")


def teste_rol_ausente_fecha_o_portao():
    secao("portão sem rol")
    c = Cenario(com_rol=False)
    r = c.cliente.post(
        "/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": CPF}
    )
    checa(r.status_code == 202, "pedido de código devia ser aceito")
    checa(
        "codigo_do_ensaio" not in r.json(),
        "SEM ROL NÃO PODE SAIR CÓDIGO: o portão estaria aberto para qualquer "
        "CPF válido",
    )
    print("  ok     sem rol, nenhum código é entregue")


def teste_cpf_fora_do_rol_nao_se_distingue():
    secao("não revelar filiação")
    c = Cenario()
    dentro = c.cliente.post(
        "/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": CPF}
    )
    fora = c.cliente.post(
        "/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": OUTRO_CPF}
    )
    checa(
        dentro.status_code == fora.status_code,
        "status diferente para quem está e quem não está no rol",
    )
    checa(
        dentro.json()["aviso"] == fora.json()["aviso"],
        "o aviso difere e vira consulta de filiação",
    )
    checa(
        "codigo_do_ensaio" not in fora.json(),
        "saiu código para CPF que não está no rol",
    )
    r = c.cliente.post(
        "/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": "111"}
    )
    checa(r.status_code == 400, "CPF malformado devia ser recusado na hora")
    print("  ok     quem está e quem não está no rol recebem a mesma resposta")


def teste_codigo_errado_e_forca_bruta():
    secao("código")
    c = Cenario()
    c.cliente.post("/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": CPF})
    for tentativa in range(4):
        r = c.cliente.post(
            "/api/acesso/conferir",
            json={"entidade": "demo-teste", "cpf": CPF, "codigo": "000000"},
        )
        checa(
            r.status_code == 401,
            f"tentativa {tentativa + 1} errada devia dar 401, deu {r.status_code}",
        )
    r = c.cliente.post(
        "/api/acesso/conferir",
        json={"entidade": "demo-teste", "cpf": CPF, "codigo": "000000"},
    )
    checa(r.status_code == 429, "a 5ª errada devia queimar o código (429)")
    print("  ok     código errado 5 vezes queima o código")


def teste_limite_de_emissoes():
    secao("limite de emissões")
    c = Cenario(limite_de_emissoes=3)
    vistos = []
    for _ in range(4):
        r = c.cliente.post(
            "/api/acesso/codigo", json={"entidade": "demo-teste", "cpf": CPF}
        )
        vistos.append(r.status_code)
    checa(
        vistos[:3] == [202, 202, 202] and vistos[3] == 429,
        f"esperava três emissões e um 429, veio {vistos}",
    )
    print("  ok     três códigos por hora, o quarto é recusado")


def teste_cadastro_exige_sessao():
    secao("cadastro sem sessão")
    c = Cenario()
    r = c.enviar("token-inventado", linha(), pacote())
    checa(r.status_code == 401, f"token inventado devia dar 401, deu {r.status_code}")
    print("  ok     sem sessão válida não grava")


def teste_cpf_do_formulario_tem_que_bater_com_a_sessao():
    secao("sessão x formulário")
    c = Cenario()
    c.escrever_rol(
        "demo-teste",
        [(CPF, "fulano@exemplo.org"), (OUTRO_CPF, "outro@exemplo.org")],
    )
    token = c.token(CPF)
    r = c.enviar(token, linha(OUTRO_CPF), pacote(OUTRO_CPF))
    checa(
        r.status_code == 403,
        f"cadastrar outro CPF com a própria sessão devia dar 403, deu "
        f"{r.status_code}",
    )
    print("  ok     não dá para cadastrar outra pessoa com o próprio código")


def teste_arquivos_recusados():
    secao("arquivos")
    c = Cenario()

    token = c.token()
    ruim = [("arquivos", ("../../etc/passwd", b"%PDF-1.4\n", "application/pdf"))]
    r = c.enviar(token, linha(), ruim)
    checa(r.status_code == 422, "nome de arquivo fora do contrato devia dar 422")
    checa(
        not (c.raiz / "demo-teste" / "entrega" / CPF_DIGITOS).exists(),
        "GRAVOU com nome de arquivo inválido",
    )

    token = c.token()
    nao_pdf = [
        ("arquivos", ("procuracao.pdf", b"GIF89a\x00\x00", "application/pdf"))
    ]
    r = c.enviar(token, linha(), nao_pdf)
    checa(r.status_code == 422, "arquivo que não é PDF devia dar 422")

    token = c.token()
    so_imagem = [
        ("arquivos", ("procuracao.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf"))
    ]
    r = c.enviar(token, linha(), so_imagem)
    checa(
        r.status_code == 422 and "texto selecionável" in r.json()["detail"]["erro"],
        "PDF sem camada de texto devia ser recusado AQUI, não no escritório",
    )

    token = c.token()
    r = c.enviar(token, linha(), pacote(com_processo=False))
    checa(
        r.status_code == 422,
        "quem declarou ter processo tem que mandar sentença e trânsito",
    )
    print("  ok     nome fora do contrato, não-PDF, só-imagem e pacote incompleto")


def teste_linha_recusada():
    secao("linha do manifesto")
    c = Cenario()

    token = c.token()
    r = c.enviar(token, linha(**{"data_aposentadoira": "2018-06-30"}), pacote())
    checa(
        r.status_code == 422,
        "coluna com nome errado tem que ser erro, não descarte em silêncio",
    )

    token = c.token()
    # O dígito errado é o certo com um a mais, para não depender da minha conta.
    dv = int(PROCESSO.split("-")[1][:2])
    torto = PROCESSO.replace(f"-{dv:02d}.", f"-{(dv + 1) % 100:02d}.", 1)
    r = c.enviar(token, linha(numero_processo=torto), pacote())
    checa(r.status_code == 422, f"dígito verificador errado devia reprovar ({torto})")

    token = c.token()
    # Um processo íntegro, mas do TRF5. A execução é no TRF1.
    r = c.enviar(token, linha(numero_processo=PROCESSO_OUTRO_TRIBUNAL), pacote())
    checa(r.status_code == 422, "processo de outro tribunal devia reprovar")

    token = c.token()
    r = c.enviar(token, linha(ciencia_e_iniciativa=""), pacote())
    checa(r.status_code == 422, "sem a declaração final não pode gravar")

    token = c.token()
    r = c.enviar(token, linha(nome_completo="x" * 500), pacote())
    checa(r.status_code == 422, "campo acima do teto devia reprovar")
    print("  ok     coluna errada, processo inválido, sem declaração, campo gigante")


def teste_token_vale_um_envio():
    secao("token de uso único")
    c = Cenario()
    token = c.token()
    r = c.enviar(token, linha(), pacote())
    checa(r.status_code == 200, f"o envio bom falhou: {r.text[:200]}")
    r = c.enviar(token, linha(), pacote())
    checa(
        r.status_code == 401,
        "o mesmo token enviou duas vezes: um token vazado substituiria os "
        "documentos da pessoa à vontade",
    )
    print("  ok     um token, um envio")


def teste_reenvio_guarda_o_anterior():
    secao("reenvio")
    c = Cenario()
    primeiro = c.enviar(c.token(), linha(), pacote()).json()
    segundo = c.enviar(
        c.token(), linha(telefone="(62) 98888-1111"), pacote()
    ).json()
    checa(
        segundo["substituiu_protocolo"] == primeiro["protocolo"],
        "o recibo devia dizer qual protocolo foi substituído",
    )
    historico = c.raiz / "demo-teste" / "historico" / CPF_DIGITOS
    checa(
        historico.is_dir() and any(historico.iterdir()),
        "o envio anterior tinha que ir para o histórico, não desaparecer",
    )
    manifesto = (
        c.raiz / "demo-teste" / "entrega" / "manifesto.csv"
    ).read_text("utf-8")
    linhas = [l for l in manifesto.splitlines() if l.strip()]
    checa(
        len(linhas) == 2,
        f"o manifesto devia ter cabeçalho + 1 linha, tem {len(linhas)}",
    )
    checa("98888-1111" in manifesto, "o manifesto ficou com o cadastro antigo")
    print("  ok     reenvio corrige o cadastro e guarda o anterior")


def teste_isolamento_entre_entidades():
    secao("isolamento")
    c = Cenario(entidades_extra=(("demo-outro", "Outro Sindicato"),))
    c.escrever_rol("demo-outro", [(OUTRO_CPF, "outro@exemplo.org")])
    c.enviar(c.token(), linha(), pacote())
    nossa = c.raiz / "demo-teste" / "entrega" / CPF_DIGITOS
    alheia = c.raiz / "demo-outro" / "entrega" / CPF_DIGITOS
    checa(nossa.is_dir(), "a entrega não foi gravada na entidade certa")
    checa(
        not alheia.exists(),
        "a entrega apareceu na pasta da OUTRA entidade",
    )
    # Uma sessão aberta numa entidade não serve na outra: a entidade vem da
    # sessão, não do pedido, então nem há como pedir.
    token = c.token(OUTRO_CPF, apelido="demo-outro")
    r = c.enviar(token, linha(OUTRO_CPF), pacote(OUTRO_CPF))
    checa(r.status_code == 200, f"o envio da outra entidade falhou: {r.text[:150]}")
    checa(
        (c.raiz / "demo-outro" / "entrega" / "11144477735").is_dir(),
        "a segunda entidade não recebeu a própria entrega",
    )
    checa(
        not (c.raiz / "demo-teste" / "entrega" / "11144477735").exists(),
        "a entrega da segunda entidade vazou para a primeira",
    )
    print("  ok     cada entidade escreve só na própria pasta")


def teste_manifesto_se_refaz_do_diario():
    secao("manifesto derivado")
    from servidor import deposito, entidades as mod_entidades

    c = Cenario()
    c.enviar(c.token(), linha(), pacote())
    manifesto = c.raiz / "demo-teste" / "entrega" / "manifesto.csv"
    antes = manifesto.read_text("utf-8")
    manifesto.unlink()
    ent = mod_entidades.Cadastro(c.raiz).resolver("demo-teste")
    deposito.reconstruir_manifesto(ent, c.raiz)
    checa(
        manifesto.read_text("utf-8") == antes,
        "o manifesto reconstruído do diário saiu diferente do original",
    )
    print("  ok     manifesto apagado se refaz igual a partir do diário")


def teste_entrega_passa_no_verificador():
    secao("o laço fechado")
    c = Cenario()
    r = c.enviar(c.token(), linha(), pacote())
    checa(r.status_code == 200, f"o envio falhou: {r.text[:300]}")
    if r.status_code != 200:
        return

    entrega = c.raiz / "demo-teste" / "entrega"
    p = subprocess.run(
        [
            sys.executable,
            "ferramentas/conferir_entrega.py",
            "--entrega",
            str(entrega),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=180,
    )
    saida = (p.stdout or "") + (p.stderr or "")
    checa(
        p.returncode == 0,
        f"o verificador do motor REPROVOU a entrega do servidor:\n{saida[-1200:]}",
    )
    checa(
        "documento_ausente" not in saida and "sem_texto_selecionavel" not in saida,
        f"o verificador achou problema de documento:\n{saida[-800:]}",
    )
    recibo = r.json()
    checa(
        recibo["protocolo"].startswith("PRT-"),
        f"protocolo em formato inesperado: {recibo['protocolo']}",
    )
    checa(
        len(recibo["arquivos"]) == 5
        and all(len(h) == 64 for h in recibo["arquivos"].values()),
        "o recibo devia trazer o sha256 dos cinco arquivos",
    )
    print("  ok     a entrega do servidor é aprovada pelo motor, sem adaptação")


TESTES = [
    teste_saude_e_entidade,
    teste_rol_ausente_fecha_o_portao,
    teste_cpf_fora_do_rol_nao_se_distingue,
    teste_codigo_errado_e_forca_bruta,
    teste_limite_de_emissoes,
    teste_cadastro_exige_sessao,
    teste_cpf_do_formulario_tem_que_bater_com_a_sessao,
    teste_arquivos_recusados,
    teste_linha_recusada,
    teste_token_vale_um_envio,
    teste_reenvio_guarda_o_anterior,
    teste_isolamento_entre_entidades,
    teste_manifesto_se_refaz_do_diario,
    teste_entrega_passa_no_verificador,
]


def main() -> int:
    print("=" * 70)
    print("SERVIDOR DO PORTAL")
    print("=" * 70)
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401
    except ImportError as e:
        print(f"PULADO: {e}. pip install fastapi httpx python-multipart")
        return 0

    for teste in TESTES:
        try:
            teste()
        except Exception as e:  # noqa: BLE001
            import traceback

            falhas.append(f"{teste.__name__}: {e}")
            print(f"  ERRO   {teste.__name__}: {e}")
            traceback.print_exc()

    _limpar()

    print("\n" + "-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s)")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0




def teste_modo_ensaio_so_atende_entidade_de_demonstracao():
    """A trava que torna seguro publicar o servidor em modo ensaio.

    Em modo ensaio o código de acesso volta na RESPOSTA HTTP. Isso é o certo
    para teste e inaceitável com gente real — e um servidor publicado assim
    fica a um cadastro de distância de virar vazamento: basta alguém
    registrar um sindicato de verdade e subir o rol.

    Então o modo ensaio atende SÓ entidades cujo apelido começa com `demo-`.
    Qualquer outra é recusada, com o motivo escrito.
    """
    from servidor import entidades as mod_entidades

    c = Cenario(com_rol=False)
    cadastro = mod_entidades.Cadastro(c.raiz)
    cadastro.criar("demo-sindicato", "Sindicato de Demonstração")
    c.escrever_rol("demo-sindicato", [(CPF, "fulano@exemplo.org")])
    # Uma entidade que NÃO é de demonstração, criada aqui de propósito.
    cadastro.criar("sindicato-real", "Sindicato de Verdade")
    c.escrever_rol("sindicato-real", [(CPF, "fulano@exemplo.org")])

    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-sindicato", "cpf": CPF})
    checa(r.status_code == 202,
          f"entidade demo devia ser atendida em ensaio, deu {r.status_code}")
    checa("codigo_do_ensaio" in r.json(),
          "a entidade demo não recebeu o código do ensaio")

    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "sindicato-real", "cpf": CPF})
    checa(r.status_code == 403,
          f"entidade NÃO-demo devia ser recusada em ensaio, deu "
          f"{r.status_code}")
    checa("ensaio" in r.text.lower(),
          f"a recusa não explica que o servidor está em ensaio: {r.text[:160]}")
    checa("codigo_do_ensaio" not in r.text,
          "VAZOU o código do ensaio para uma entidade que não é de demonstração")
    print("  ok     modo ensaio só atende entidade de demonstração")


TESTES.append(teste_modo_ensaio_so_atende_entidade_de_demonstracao)




def teste_a_entidade_se_declara_demonstracao():
    """Quem abre a página precisa saber que não é para valer.

    O servidor em ensaio tem disco volátil e rol sintético. Nada ali é
    serviço de verdade — e quem chega pelo link não tem como adivinhar isso.
    Então a própria resposta da entidade diz.
    """
    c = Cenario()
    r = c.cliente.get("/api/entidade/demo-teste")
    checa(r.status_code == 200, f"entidade não respondeu: {r.status_code}")
    corpo = r.json()
    checa(corpo.get("demonstracao") is True,
          f"a entidade não se declarou demonstração: {corpo}")
    checa(bool(corpo.get("aviso_demonstracao")),
          "veio a marca de demonstração sem texto para mostrar na tela")
    checa("document" in (corpo.get("aviso_demonstracao") or "").lower(),
          f"o aviso não fala de documento: {corpo.get('aviso_demonstracao')!r}")
    print("  ok     a entidade se declara demonstração")


TESTES.append(teste_a_entidade_se_declara_demonstracao)


# ---------------------------------------------------------- acompanhamento (B)

def _numero_estadual(sequencial: str = "0007654", tribunal: str = "07",
                     origem: str = "0001", ano: str = "2019") -> str:
    """Um número do TJDFT: segmento 8, não 4. O `numero()` acima fixa o 4
    porque o Produto A só vive na Justiça Federal; o acompanhamento do
    Produto B não tem esse limite — são 65 tribunais no DataJud."""
    dv = processo_cnj.calcular_verificador(sequencial, ano, "8", tribunal, origem)
    return f"{sequencial}-{dv}.{ano}.8.{tribunal}.{origem}"


def teste_acompanhar_aceita_qualquer_tribunal_e_nao_repete():
    secao("acompanhamento: N processos, 65 tribunais")
    from servidor import validacao

    estadual = _numero_estadual()
    base = linha(acompanhar=f"{PROCESSO};{estadual};{PROCESSO}")
    problemas = validacao.conferir_linha(base)
    checa(problemas == [],
          f"recusou lista legítima de acompanhamento: {problemas}")

    limpa = validacao.normalizar_linha(base)
    partes = [p for p in limpa["acompanhar"].split(";") if p]
    checa(len(partes) == 2,
          f"não removeu o número repetido: {partes}")
    checa(all(p.isdigit() and len(p) == 20 for p in partes),
          f"não normalizou para 20 dígitos: {partes}")
    checa(partes[0] == processo_cnj.so_digitos(PROCESSO),
          "a ordem de chegada não foi preservada — a primeira menção é a que "
          "a pessoa digitou primeiro")
    print("  ok     aceita TRF1 e TJDFT na mesma lista, normaliza e deduplica")


def teste_acompanhar_recusa_numero_que_nao_fecha():
    from servidor import validacao

    dv = int(PROCESSO.split("-")[1][:2])
    torto = PROCESSO.replace(f"-{dv:02d}.", f"-{(dv + 1) % 100:02d}.", 1)
    problemas = validacao.conferir_linha(linha(acompanhar=torto))
    checa(problemas != [],
          f"aceitou número de acompanhamento com dígito errado ({torto})")
    print("  ok     dígito errado no acompanhamento reprova")


def teste_acompanhar_tem_teto():
    """Teto porque o campo é livre e vem de fora: 200 números numa linha é
    erro de quem digitou ou abuso de quem testou, e nos dois casos a coleta
    seguinte faria 200 consultas de 30 s por causa de uma linha."""
    from servidor import validacao

    maximo = validacao.CONTRATO["acompanhamento"]["maximo"]
    demais = ";".join([PROCESSO] * (maximo + 1))
    checa(validacao.conferir_linha(linha(acompanhar=demais)) != [],
          f"aceitou mais de {maximo} números de acompanhamento")
    print(f"  ok     acompanhamento tem teto de {maximo} números")


def teste_numero_do_processo_continua_exigindo_trf1():
    """REGRESSÃO DELIBERADA, e a razão precisa ficar escrita.

    `numero_processo` é o processo da SENTENÇA DE ORIGEM, e é dele que sai o
    juízo da execução (CPC, art. 516, II). O Produto A protocola no TRF1: uma
    sentença do TRF5 se executa no TRF5, e protocolar no TRF1 seria
    incompetência garantida. Então aqui a trava fica.

    Quem quer apenas ACOMPANHAR processo de outro tribunal usa `acompanhar`,
    que aceita os 65. São campos diferentes porque são perguntas diferentes.
    """
    from servidor import validacao

    checa(validacao.conferir_linha(linha(numero_processo=PROCESSO_OUTRO_TRIBUNAL)) != [],
          "numero_processo deixou de exigir TRF1 — a execução iria para a "
          "vara errada")
    checa(validacao.conferir_linha(linha(acompanhar=PROCESSO_OUTRO_TRIBUNAL)) == [],
          "acompanhar devia aceitar outro tribunal")
    print("  ok     numero_processo exige TRF1; acompanhar aceita qualquer um")


def teste_quer_aviso_so_aceita_sim_ou_vazio():
    from servidor import validacao

    checa(validacao.conferir_linha(linha(quer_aviso="sim")) == [],
          "recusou o opt-in marcado")
    checa(validacao.conferir_linha(linha(quer_aviso="")) == [],
          "recusou o opt-in não marcado")
    checa(validacao.conferir_linha(linha(quer_aviso="talvez")) != [],
          "aceitou valor que não é sim nem vazio")
    print("  ok     opt-in de aviso aceita só sim ou vazio")


TESTES.extend([
    teste_acompanhar_aceita_qualquer_tribunal_e_nao_repete,
    teste_acompanhar_recusa_numero_que_nao_fecha,
    teste_acompanhar_tem_teto,
    teste_numero_do_processo_continua_exigindo_trf1,
    teste_quer_aviso_so_aceita_sim_ou_vazio,
])

# ------------------------------------------------------------- consulta (B)

def teste_meus_processos_exige_sessao():
    secao("consulta do filiado")
    c = Cenario()
    for cabecalho in ({}, {"Authorization": "Bearer invalido"}):
        r = c.cliente.get("/api/meus-processos", headers=cabecalho)
        checa(r.status_code == 401,
              f"consulta aberta sem sessão válida: {r.status_code}")
    print("  ok     sem sessão válida, 401")


def teste_filiado_so_ve_os_processos_dele():
    """A rota NÃO aceita CPF por parâmetro: ela filtra pelo CPF que abriu a
    sessão. Aceitar parâmetro transformaria a consulta na pesquisa de
    filiação que o portão se recusa a ser."""
    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "fulano@exemplo.org"),
                                  (OUTRO_CPF, "outro@exemplo.org")])
    c.cadastrar(CPF, acompanhar=PROCESSO)
    c.cadastrar(OUTRO_CPF, acompanhar=PROCESSO_OUTRO_TRIBUNAL)

    r = c.cliente.get("/api/meus-processos",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code} {r.text[:200]}")
    numeros = {p["numero"] for p in r.json()["processos"]}
    meu = processo_cnj.so_digitos(PROCESSO)
    do_outro = processo_cnj.so_digitos(PROCESSO_OUTRO_TRIBUNAL)
    checa(numeros == {meu},
          f"deveria ver só o processo dele; veio {numeros}")
    checa(do_outro not in numeros, "VAZOU o processo do outro filiado")
    print("  ok     o filiado vê só o que é dele")


def teste_consulta_nao_aceita_cpf_por_parametro():
    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "fulano@exemplo.org"),
                                  (OUTRO_CPF, "outro@exemplo.org")])
    c.cadastrar(OUTRO_CPF, acompanhar=PROCESSO_OUTRO_TRIBUNAL)
    r = c.cliente.get(f"/api/meus-processos?cpf={OUTRO_CPF}",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code}")
    checa(r.json()["processos"] == [],
          f"o parâmetro cpf foi obedecido e vazou: {r.json()}")
    print("  ok     parâmetro cpf é ignorado, não obedecido")


def teste_cadastro_nao_altera_o_rol():
    """Se o filiado pudesse trocar o próprio e-mail, o código de acesso
    viraria enfeite: eu digito o CPF de outra pessoa, ponho o meu e-mail e
    vejo o cadastro dela. O filiado PROPÕE; o sindicato homologa."""
    secao("o e-mail do portão vem do sindicato")
    c = Cenario()
    antes = rol.carregar(c.ent.pasta(c.raiz)).email_de(CPF)
    r = c.cadastrar(CPF, email="invasor@exemplo.org")
    checa(r.status_code == 200, f"o cadastro falhou: {r.status_code} {r.text[:200]}")
    depois = rol.carregar(c.ent.pasta(c.raiz)).email_de(CPF)
    checa(depois == antes,
          f"o rol foi alterado pelo cadastro: {antes} -> {depois}")
    print(f"  ok     o rol seguiu com {antes!r}, não com o e-mail enviado")


def teste_completude_exige_token_de_gestor():
    secao("painel do gestor")
    c = Cenario()
    r = c.cliente.get("/api/entidade/demo-teste/completude")
    checa(r.status_code == 401, f"painel aberto sem autenticação: {r.status_code}")

    # Token legítimo, mas de filiado: não é gestor.
    r = c.cliente.get("/api/entidade/demo-teste/completude",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 403,
          f"token de filiado abriu o painel do sindicato: {r.status_code}")
    print("  ok     sem token, 401; com token de filiado, 403")


def teste_gestor_ve_o_retrato_da_propria_entidade():
    c = Cenario()
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    c.cadastrar(CPF, acompanhar=PROCESSO, quer_aviso="sim")

    r = c.cliente.get("/api/entidade/demo-teste/completude",
                      headers={"Authorization": f"Bearer {c.token(OUTRO_CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code} {r.text[:200]}")
    corpo = r.json()
    retrato = corpo["retrato"]
    # Sem acervo ingerido, quem se cadastrou conta como FORA DO ACERVO — e
    # está certo: o sindicato ainda não mandou a base dele. `tem_acervo`
    # existe para a tela poder dizer isso em vez de mostrar zeros sem
    # explicação.
    checa(corpo["tem_acervo"] is False,
          "disse que tem acervo sem nenhuma ingestão")
    checa(retrato["fora_do_acervo"] == 1,
          f"o cadastro não apareceu: {retrato}")
    checa(retrato["cadastrados"] == 0,
          f"contou como cadastrado alguém que não está no acervo: {retrato}")
    checa(retrato["querem_aviso"] == 1,
          f"opt-in não contado: {retrato}")
    checa(retrato["acompanhando"] == 1 and retrato["processos_acompanhados"] == 1,
          f"acompanhamento não contado: {retrato}")
    checa("manchete" in corpo and corpo["manchete"],
          "o painel veio sem manchete")
    print("  ok     gestor vê o retrato, com manchete e tem_acervo=False")


def teste_gestor_de_uma_entidade_nao_abre_o_painel_de_outra():
    c = Cenario(entidades_extra=(("demo-outra", "Outro Sindicato"),))
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    c.escrever_rol("demo-outra", [(CPF, "fulano@exemplo.org")])
    token = c.token(OUTRO_CPF, apelido="demo-teste")
    r = c.cliente.get("/api/entidade/demo-outra/completude",
                      headers={"Authorization": f"Bearer {token}"})
    checa(r.status_code in (401, 403, 404),
          f"token de demo-teste abriu demo-outra: {r.status_code}")
    print("  ok     token não atravessa entidade")


def teste_gestor_fora_do_rol_de_filiados_recebe_codigo():
    """O gerente do sindicato não é necessariamente filiado. Se o código só
    fosse para quem está em filiados.csv, não haveria como ele entrar."""
    c = Cenario()
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-teste", "cpf": OUTRO_CPF})
    checa(r.status_code == 202, f"não emitiu: {r.status_code}")
    checa("codigo_do_ensaio" in r.json(),
          f"gestor fora do rol não recebeu código: {r.json()}")
    print("  ok     gestor recebe código pelo rol de gestores")


TESTES.extend([
    teste_meus_processos_exige_sessao,
    teste_filiado_so_ve_os_processos_dele,
    teste_consulta_nao_aceita_cpf_por_parametro,
    teste_cadastro_nao_altera_o_rol,
    teste_completude_exige_token_de_gestor,
    teste_gestor_ve_o_retrato_da_propria_entidade,
    teste_gestor_de_uma_entidade_nao_abre_o_painel_de_outra,
    teste_gestor_fora_do_rol_de_filiados_recebe_codigo,
])


def teste_painel_diz_o_NOME_de_quem_nao_se_alcanca():
    """A spec pede "a lista nominal de quem precisa ser procurado" (§1).

    CPF é pouco melhor que contagem: o gestor não liga para um número, liga
    para a Carla. O nome está no acervo; não mostrá-lo seria guardar a
    informação útil e entregar a inútil.
    """
    import json as _json

    c = Cenario()
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    pasta = c.ent.pasta(c.raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "acervo.jsonl").write_text(
        _json.dumps({
            "ingerido_em": "2026-10-29T12:00:00+00:00",
            "pessoas": [{
                "cpf": "24843803480",
                "linha_no_arquivo": 7,
                "campos": {"nome_completo": "CARLA DE EXEMPLO (FICTICIO)",
                           "cpf": "248.438.034-80", "email": ""},
                "achados": [{"coluna": "email", "estado": "FALTA",
                             "detalhe": "sem e-mail o código não tem para onde ir"}],
            }],
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    r = c.cliente.get("/api/entidade/demo-teste/completude",
                      headers={"Authorization": f"Bearer {c.token(OUTRO_CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code} {r.text[:200]}")
    lista = r.json().get("inalcancaveis") or []
    checa(len(lista) == 1, f"a lista nominal veio com {len(lista)} item(ns)")
    if lista:
        checa("CARLA" in (lista[0].get("nome") or ""),
              f"veio sem nome: {lista[0]}")
        checa("e-mail" in (lista[0].get("motivo") or ""),
              f"veio sem motivo: {lista[0]}")
    print("  ok     o painel diz o nome, não só o CPF")


TESTES.append(teste_painel_diz_o_NOME_de_quem_nao_se_alcanca)


def teste_cors_permite_o_cabecalho_authorization():
    """ACHADO CONDUZINDO O NAVEGADOR DE VERDADE, em 29/10/2026.

    O portal e o servidor vivem em origens DIFERENTES em produção — o portal
    na Netlify, o servidor na Render. As telas de consulta mandam
    `Authorization: Bearer ...`, e o CORS estava liberando só
    `content-type`: o preflight reprovava e as duas telas não carregavam
    nada. Zero testes Python pegavam isso, porque o TestClient não faz
    preflight de navegador.

    Este teste faz o preflight na mão. É a única defesa que resta contra
    alguém mexer em `allow_headers` e quebrar a consulta de novo.
    """
    c = Cenario(origens=("https://portal.exemplo.org",))
    r = c.cliente.options(
        "/api/meus-processos",
        headers={
            "Origin": "https://portal.exemplo.org",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    checa(r.status_code == 200,
          f"o preflight do navegador reprovou: {r.status_code}")
    permitidos = (r.headers.get("access-control-allow-headers") or "").lower()
    checa("authorization" in permitidos,
          f"Authorization não está entre os cabeçalhos permitidos: "
          f"{permitidos!r} — as telas de consulta não carregariam")
    print("  ok     o preflight aceita Authorization")


TESTES.append(teste_cors_permite_o_cabecalho_authorization)


# ------------------------------------------------- achados da revisão (C1, I5)

def _corpo_comparavel(r):
    """A resposta como quem está de fora a vê: status e corpo."""
    try:
        corpo = dict(r.json())
    except Exception:  # noqa: BLE001
        corpo = {"_texto": r.text}
    # O código do ensaio volta só para quem ESTÁ no rol — é a diferença
    # legítima, e em produção ele não existe. Fora dele, tudo tem de bater.
    corpo.pop("codigo_do_ensaio", None)
    corpo.pop("ensaio", None)
    return r.status_code, corpo


def teste_pedir_codigo_responde_igual_dentro_e_fora_do_rol():
    """C1 — ACHADO NA REVISÃO, reproduzido.

    `gestores.csv` malformado fazia a busca do e-mail do gestor levantar
    ValueError SÓ no ramo em que o CPF não estava em `filiados.csv`. Resultado:
    202 para quem está no rol, 500 para quem não está — um oráculo de filiação
    sindical, sem autenticação, para qualquer CPF. Filiação sindical é dado
    sensível (LGPD, art. 11).

    Este teste é a defesa estrutural que faltava: percorre TODOS os estados dos
    dois arquivos e exige a MESMA resposta para dentro e fora do rol.
    """
    secao("o portão não revela filiação (C1)")
    import csv as _csv

    estados = {
        "sem gestores.csv": None,
        "gestores.csv normal": "cpf,email\n529.982.247-25,g@exemplo.org\n",
        "gestores.csv com ';' (Excel pt-BR)": "cpf;email\n529.982.247-25;g@exemplo.org\n",
        "gestores.csv sem cabeçalho certo": "documento,contato\n529.982.247-25,g@exemplo.org\n",
        "gestores.csv vazio": "",
    }
    for rotulo, conteudo in estados.items():
        c = Cenario()
        caminho = c.ent.pasta(c.raiz) / "gestores.csv"
        if conteudo is None:
            caminho.unlink(missing_ok=True)
        else:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(conteudo, encoding="utf-8")

        dentro = _corpo_comparavel(c.cliente.post(
            "/api/acesso/codigo",
            json={"entidade": "demo-teste", "cpf": CPF}))
        fora = _corpo_comparavel(c.cliente.post(
            "/api/acesso/codigo",
            json={"entidade": "demo-teste", "cpf": OUTRO_CPF}))
        checa(dentro == fora,
              f"[{rotulo}] a resposta revela filiação: dentro={dentro} "
              f"fora={fora}")
    print(f"  ok     resposta idêntica em {len(estados)} estados do gestores.csv")


def teste_rol_em_latin1_nao_fecha_o_portao():
    """I5 — ACHADO NA REVISÃO.

    `rol.py` abria só com utf-8-sig. A MESMA exportação de Excel que
    `acervo.py` foi ensinado a ler em três encodings derrubava o portão
    inteiro: UnicodeDecodeError vira ValueError, o servidor loga ROL INVÁLIDO
    e devolve 202 para todo mundo. O sindicato veria o painel acender e o
    portal recusar silenciosamente cada filiado.
    """
    c = Cenario()
    caminho = c.ent.pasta(c.raiz) / "filiados.csv"
    caminho.write_bytes(
        f"cpf;email;nome\n{CPF};fulano@exemplo.org;JOSÉ DA CONCEIÇÃO\n"
        .encode("latin-1")
    )
    lista = rol.carregar(c.ent.pasta(c.raiz))
    checa(lista.email_de(CPF) == "fulano@exemplo.org",
          f"rol em latin-1 com ';' não foi lido: {lista.por_cpf}")

    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-teste", "cpf": CPF})
    checa("codigo_do_ensaio" in r.json(),
          "o portão não emitiu código com rol em latin-1 — ele fecharia para "
          "todos os filiados do sindicato")
    print("  ok     rol em latin-1 com ';' abre o portão")


def teste_acompanhar_aceita_20_numeros_formatados():
    """I6 — ACHADO NA REVISÃO.

    O teto era 20*21=420 caracteres, mas o contrato anuncia 20 números e o
    portal mostra o número FORMATADO (25 caracteres). Na prática o campo
    parava perto de 16, e a mensagem culpava o tamanho em caracteres em vez
    da causa.
    """
    from servidor import validacao

    maximo = validacao.ACOMPANHAMENTO["maximo"]
    formatados = ";".join(
        processo_cnj.normalizar(numero("%07d" % (1000 + i), "01", "3400"))
        for i in range(maximo)
    )
    # Formatados de verdade, com pontuação, como o portal exibe.
    bonitos = ";".join(
        processo_cnj.decompor(processo_cnj.so_digitos(n)).formatado
        for n in formatados.split(";")
    )
    problemas = validacao.conferir_linha(linha(acompanhar=bonitos))
    checa(problemas == [],
          f"{maximo} números formatados foram recusados: {problemas}")
    print(f"  ok     {maximo} números formatados cabem no campo")


TESTES.extend([
    teste_pedir_codigo_responde_igual_dentro_e_fora_do_rol,
    teste_rol_em_latin1_nao_fecha_o_portao,
    teste_acompanhar_aceita_20_numeros_formatados,
])


if __name__ == "__main__":
    raise SystemExit(main())
