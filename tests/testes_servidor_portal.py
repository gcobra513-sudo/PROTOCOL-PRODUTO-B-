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
#: Um terceiro, para os cenários com filiado + gestor + mais alguém. Dígito
#: válido e declaradamente fictício, como os outros.
TERCEIRO_CPF = "529.982.247-25"


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


def pacote(cpf: str = CPF, com_judicial: bool = False) -> list[tuple]:
    """Os arquivos do envio, no formato multipart.

    OBRIGATÓRIO É SÓ A CONTRIBUIÇÃO, e ela aceita vários: é o que prova o
    período de filiação. Sentença e certidão entram só se a pessoa tiver —
    quem não tem recebe resposta do mesmo jeito, a dela é sobre ajuizar.
    """
    base = [
        (
            "contribuicao-1.pdf",
            [
                "SINDICATO - COMPROVANTE DE CONTRIBUICAO",
                f"Filiada: FULANA DE TAL (CADASTRO DE EXEMPLO)  CPF {cpf}",
                "Competencia: 01/2003 a 12/2003",
                "Contribuicao mensal descontada em folha, sem interrupcao no",
                "periodo acima, conforme registros da secretaria.",
            ],
        ),
        (
            "contribuicao-2.pdf",
            [
                "SINDICATO - COMPROVANTE DE CONTRIBUICAO",
                f"Filiada: FULANA DE TAL (CADASTRO DE EXEMPLO)  CPF {cpf}",
                "Competencia: 01/2004 a 12/2004",
                "Contribuicao mensal descontada em folha, sem interrupcao no",
                "periodo acima, conforme registros da secretaria.",
            ],
        ),
    ]
    if com_judicial:
        base.append((
            "sentenca.pdf",
            [
                "PODER JUDICIARIO - JUSTICA FEDERAL",
                "PROCESSO: 0010391-24.2006.4.01.3400",
                f"AUTORA: FULANA DE TAL (CADASTRO DE EXEMPLO)  CPF {cpf}",
                "Ante o exposto, JULGO PROCEDENTE o pedido para condenar a",
                "Uniao ao pagamento das diferencas devidas.",
            ],
        ))
    return [
        ("arquivos", (nome, pdf_com_texto(linhas), "application/pdf"))
        for nome, linhas in base
    ]


def linha(cpf: str = CPF, **trocas) -> dict:
    """A conta do filiado, no contrato do Produto B.

    Sem procuração, sem endereço, sem matrícula: o B responde uma pergunta,
    não distribui processo. O que ele precisa é cargo (define a categoria) e
    filiação (define o período) — e é o cruzamento dos dois que diz de quais
    ações a pessoa faz parte.
    """
    base = {
        "cpf": cpf,
        "nome_completo": "FULANA DE TAL (CADASTRO DE EXEMPLO)",
        "email": "fulana@exemplo.org",
        "telefone": "(62) 99999-0000",
        "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
        "situacao": "aposentado",
        "unidade": "Delegacia da Receita Federal em Goiania",
        "data_nascimento": "1958-06-27",
        "data_ingresso": "1992-04-01",
        "data_aposentadoria": "2018-06-30",
        "filiado_desde": "1992-05",
        # Vazio é resposta: ainda filiada.
        "filiado_ate": "",
        "tem_processo": "nao_sei",
        "numeros_de_processo": "",
        "ja_executou": "nao",
        "tem_acao_propria": "nao",
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
        limite_por_origem: int = 0,
        proxies: tuple[str, ...] = (),
        origens: tuple[str, ...] = (),
        categorias: tuple[str, ...] = ("auditor-fiscal-receita-federal",),
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
            "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": str(
                limite_por_origem or limite_de_emissoes or 500
            ),
        }
        if proxies:
            ambiente["PROTOCOL_PROXIES_CONFIAVEIS"] = ",".join(proxies)
        if origens:
            ambiente["PROTOCOL_ORIGENS"] = ",".join(origens)
        self.cfg = carregar(ambiente)
        cadastro = mod_entidades.Cadastro(self.raiz)
        self.ent = cadastro.criar("demo-teste", "Sindicato de Teste",
                                  categorias=categorias)
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


def teste_o_limite_por_origem_nao_e_escolhido_por_quem_pede():
    """A CHAVE DA CONTAGEM NÃO PODE SER UM CABEÇALHO DO PEDIDO.

    `/api/acesso/codigo` é a única rota aberta que emite credencial, e a
    única contagem global que ela tem é a de emissões por origem por hora.
    `acesso.py` declara o que essa contagem sustenta: "impede varrer CPFs
    para descobrir quem é filiado. Sem ela, a resposta 'não está no rol'
    entrega o rol inteiro a quem tiver paciência."

    `_origem` devolvia o primeiro valor de `X-Forwarded-For` sempre que o
    cabeçalho existia. Como é cabeçalho de pedido, quem pede escolhia a
    chave: trocando o valor, cada pedido caía num balde novo. Auditoria
    independente mediu — com o limite em 3, vinte pedidos com o cabeçalho
    variando deram vinte 202.

    E a hipótese do comentário era falsa nas duas implantações possíveis:
    sem proxy o cabeçalho vem do atacante; com proxy conforme, o proxy
    ACRESCENTA ao fim da lista, então o primeiro valor continua sendo o que
    o cliente escreveu.
    """
    secao("limite por origem")
    c = Cenario(limite_por_origem=3)
    vistos = []
    for i in range(8):
        r = c.cliente.post(
            "/api/acesso/codigo",
            json={"entidade": "demo-teste", "cpf": CPF},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        )
        vistos.append(r.status_code)
    checa(vistos[:3] == [202, 202, 202] and set(vistos[3:]) == {429},
          f"girar X-Forwarded-For furou o limite por origem: {vistos}")
    print("  ok     o cabeçalho não escolhe o balde da contagem")


def teste_atras_de_proxy_declarado_o_cabecalho_volta_a_valer():
    """A CORREÇÃO NÃO PODE QUEBRAR QUEM ESTÁ ATRÁS DE PROXY.

    Ignorar o cabeçalho sempre faria a contagem por origem valer para o
    mundo inteiro junto — e aí o primeiro sindicato com atendimento
    presencial fecharia o portão para a fila toda. O cabeçalho volta a
    valer, mas só quando quem fala com o servidor é um proxy DECLARADO na
    configuração, e aí o valor que conta é o ÚLTIMO, que é o que aquele
    proxy acrescentou.
    """
    c = Cenario(limite_por_origem=3, proxies=("testclient",))
    # Dois clientes distintos atrás do mesmo proxy contam separado: cada um
    # gasta a sua cota e nenhum derruba o outro.
    for cliente_real in ("198.51.100.7", "198.51.100.8"):
        vistos = []
        for _ in range(4):
            r = c.cliente.post(
                "/api/acesso/codigo",
                json={"entidade": "demo-teste", "cpf": CPF},
                headers={"X-Forwarded-For": f"9.9.9.9, {cliente_real}"},
            )
            vistos.append(r.status_code)
        checa(vistos[:3] == [202, 202, 202] and vistos[3] == 429,
              f"atrás de proxy declarado a contagem não valeu para "
              f"{cliente_real}: {vistos}")
    # E O VALOR MENTIDO PELO CLIENTE NÃO CONTA: os dois laços acima mandaram
    # `9.9.9.9` como primeiro valor. Se fosse ele a chave, o segundo cliente
    # já teria chegado recusado no primeiro pedido.
    print("  ok     atrás de proxy declarado, vale o último valor")


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
        ("arquivos", ("contribuicao-1.pdf", b"GIF89a\x00\x00", "application/pdf"))
    ]
    r = c.enviar(token, linha(), nao_pdf)
    checa(r.status_code == 422, "arquivo que não é PDF devia dar 422")

    token = c.token()
    so_imagem = [
        ("arquivos", ("contribuicao-1.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf"))
    ]
    r = c.enviar(token, linha(), so_imagem)
    checa(
        r.status_code == 422 and "texto selecionável" in r.json()["detail"]["erro"],
        "PDF sem camada de texto devia ser recusado AQUI, não no escritório",
    )

    # INVERTIDO EM RELAÇÃO AO PRODUTO A, e de propósito: lá, declarar
    # "tenho processo" passava a EXIGIR sentença e certidão. No Produto B
    # não exige — a pessoa pode saber o número e não ter os papéis em mãos, e
    # bloquear por isso a deixaria sem resposta nenhuma, justamente ela, que
    # é quem mais precisa.
    token = c.token()
    r = c.enviar(token, linha(tem_processo="sim",
                              numeros_de_processo=PROCESSO), pacote())
    checa(
        r.status_code == 200,
        f"declarar processo passou a exigir documento: "
        f"{r.status_code} {r.text[:200]}",
    )

    # Mas o obrigatório continua obrigatório: sem comprovante de
    # contribuição não há como saber o período de filiação, e sem ele não há
    # resposta nenhuma.
    token = c.token()
    sem_contribuicao = [
        ("arquivos", ("sentenca.pdf", pdf_com_texto(["SENTENCA", "x" * 200]),
                      "application/pdf"))
    ]
    r = c.enviar(token, linha(), sem_contribuicao)
    checa(r.status_code == 422,
          "sem comprovante de contribuição o cadastro devia reprovar")
    print("  ok     nome fora do contrato, não-PDF, só-imagem; contribuição "
          "obrigatória e judicial opcional")


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


def teste_o_manifesto_nao_entrega_formula_viva_ao_excel():
    """O CAMPO DE TEXTO DO FILIADO VIRAVA FÓRMULA NA PLANILHA DO SINDICATO.

    `manifesto.csv` é escrito para ser ABERTO POR GENTE — o próprio código
    diz isso, ao escolher `\r\n` "porque esta planilha é aberta por gente,
    no Excel em português". E o Excel, o LibreOffice e o Google Sheets
    tratam uma célula que começa com `=`, `+`, `-` ou `@` como fórmula.

    Então um filiado que digitasse `=HYPERLINK(...)` no nome tinha isso
    executado na máquina de quem abrisse o arquivo — e quem abre é o gestor
    do sindicato, que confia no arquivo porque fomos nós que o geramos.
    Travessia de fronteira: filiado -> gestor, por um canal em que o gestor
    não tem como desconfiar.

    O conteúdo NÃO É ALTERADO: o nome continua sendo o que a pessoa
    escreveu, e quem lê o CSV por programa lê o mesmo texto. O que muda é
    que a célula deixa de ser interpretada como fórmula.
    """
    secao("o manifesto não vira fórmula")
    import json as _json

    c = Cenario()
    perigosos = {
        "nome_completo": '=HYPERLINK("http://exemplo.invalid","clique")',
        "unidade": "+1+1",
        "cargo": "-2-2",
        "telefone": "@SUM(1,1)",
    }
    dados = linha(CPF)
    dados.update(perigosos)
    r = c.enviar(c.token(CPF), dados, pacote(CPF))
    checa(r.status_code == 200,
          f"o cadastro falhou: {r.status_code} {r.text[:200]}")

    bruto = (c.raiz / "demo-teste" / "entrega" / "manifesto.csv").read_text(
        encoding="utf-8")

    # Nenhuma CÉLULA pode começar com um dos gatilhos de fórmula. Olho
    # célula por célula, com o leitor de CSV de verdade: procurar a string
    # no arquivo inteiro confundiria `=` dentro de um texto com `=` no
    # começo da célula, que é o que importa.
    import csv as _csv
    import io as _io

    gatilhos = ("=", "+", "-", "@", "\t", "\r")
    for numero, registro in enumerate(
        _csv.reader(_io.StringIO(bruto, newline="")), start=1
    ):
        for coluna, celula in enumerate(registro):
            checa(not celula.startswith(gatilhos),
                  f"linha {numero}, coluna {coluna}: a célula {celula!r} "
                  f"começa com gatilho de fórmula e o Excel vai executá-la")

    # E O DADO NÃO PODE TER SIDO PERDIDO. Neutralizar não é apagar: o
    # sindicato tem de continuar vendo o que a pessoa escreveu.
    #
    # A comparação é sobre as células JÁ LIDAS, não sobre o texto cru do
    # arquivo: um valor com aspas sai do escritor de CSV com as aspas
    # duplicadas, e procurá-lo cru acusaria perda que não houve. Foi o que
    # aconteceu na primeira versão deste teste.
    celulas = {c for registro in _csv.reader(_io.StringIO(bruto, newline=""))
               for c in registro}
    for valor in perigosos.values():
        checa(valor in celulas or f"'{valor}" in celulas,
              f"o valor {valor!r} desapareceu do manifesto — neutralizar "
              f"não é apagar. Células: {sorted(celulas)[:6]}")
    print("  ok     nenhuma célula do manifesto começa com fórmula")


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




TESTES = [
    teste_saude_e_entidade,
    teste_rol_ausente_fecha_o_portao,
    teste_cpf_fora_do_rol_nao_se_distingue,
    teste_codigo_errado_e_forca_bruta,
    teste_limite_de_emissoes,
    teste_o_limite_por_origem_nao_e_escolhido_por_quem_pede,
    teste_atras_de_proxy_declarado_o_cabecalho_volta_a_valer,
    teste_cadastro_exige_sessao,
    teste_cpf_do_formulario_tem_que_bater_com_a_sessao,
    teste_arquivos_recusados,
    teste_linha_recusada,
    teste_token_vale_um_envio,
    teste_reenvio_guarda_o_anterior,
    teste_isolamento_entre_entidades,
    teste_o_manifesto_nao_entrega_formula_viva_ao_excel,
    teste_manifesto_se_refaz_do_diario,
]


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
    from nucleo import cadastro as conta

    estadual = _numero_estadual()
    base = linha(numeros_de_processo=f"{PROCESSO};{estadual};{PROCESSO}")
    problemas = conta.conferir(base)
    checa(problemas == [],
          f"recusou lista legítima de acompanhamento: {problemas}")

    limpa = conta.normalizar(base)
    partes = [p for p in limpa["numeros_de_processo"].split(";") if p]
    checa(len(partes) == 2,
          f"não removeu o número repetido: {partes}")
    checa(all(p.isdigit() and len(p) == 20 for p in partes),
          f"não normalizou para 20 dígitos: {partes}")
    checa(partes[0] == processo_cnj.so_digitos(PROCESSO),
          "a ordem de chegada não foi preservada — a primeira menção é a que "
          "a pessoa digitou primeiro")
    print("  ok     aceita TRF1 e TJDFT na mesma lista, normaliza e deduplica")


def teste_acompanhar_recusa_numero_que_nao_fecha():
    from nucleo import cadastro as conta

    dv = int(PROCESSO.split("-")[1][:2])
    torto = PROCESSO.replace(f"-{dv:02d}.", f"-{(dv + 1) % 100:02d}.", 1)
    problemas = conta.conferir(linha(numeros_de_processo=torto))
    checa(problemas != [],
          f"aceitou número de acompanhamento com dígito errado ({torto})")
    print("  ok     dígito errado no acompanhamento reprova")


def teste_acompanhar_tem_teto():
    """Teto porque o campo é livre e vem de fora: 200 números numa linha é
    erro de quem digitou ou abuso de quem testou, e nos dois casos a coleta
    seguinte faria 200 consultas de 30 s por causa de uma linha."""
    from nucleo import cadastro as conta

    maximo = conta.MAXIMO_DE_PROCESSOS
    demais = ";".join([PROCESSO] * (maximo + 1))
    checa(conta.conferir(linha(numeros_de_processo=demais)) != [],
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
    from nucleo import cadastro as conta

    checa(conta.conferir(linha(numero_processo=PROCESSO_OUTRO_TRIBUNAL)) != [],
          "numero_processo deixou de exigir TRF1 — a execução iria para a "
          "vara errada")
    checa(conta.conferir(linha(numeros_de_processo=PROCESSO_OUTRO_TRIBUNAL)) == [],
          "acompanhar devia aceitar outro tribunal")
    print("  ok     numero_processo exige TRF1; acompanhar aceita qualquer um")


def teste_quer_aviso_so_aceita_sim_ou_vazio():
    from nucleo import cadastro as conta

    checa(conta.conferir(linha(quer_aviso="sim")) == [],
          "recusou o opt-in marcado")
    checa(conta.conferir(linha(quer_aviso="")) == [],
          "recusou o opt-in não marcado")
    checa(conta.conferir(linha(quer_aviso="talvez")) != [],
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
    c.cadastrar(CPF, numeros_de_processo=PROCESSO)
    c.cadastrar(OUTRO_CPF, numeros_de_processo=PROCESSO_OUTRO_TRIBUNAL)

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
    c.cadastrar(OUTRO_CPF, numeros_de_processo=PROCESSO_OUTRO_TRIBUNAL)
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
    c.cadastrar(CPF, numeros_de_processo=PROCESSO, quer_aviso="sim")

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


def _expirar_codigos(c) -> None:
    """Envelhece os códigos vivos, para não esperar 15 minutos no teste."""
    import sqlite3

    from servidor.acesso import ARQUIVO

    cx = sqlite3.connect(c.raiz / ARQUIVO)
    cx.execute("UPDATE codigos SET expira_em = '2000-01-01T00:00:00+00:00' "
               "WHERE usado_em IS NULL")
    cx.commit()
    cx.close()


def teste_falha_de_envio_nao_revela_filiacao():
    """O 502 ERA ALCANÇÁVEL SÓ PARA QUEM ESTÁ NO ROL.

    `pedir_codigo` devolve 202 e para, logo, quando `destino is None` — CPF
    fora dos dois róis. Só depois disso vinha o `correio.enviar`, e o
    `except` dele levantava 502. Ou seja: qualquer falha de entrega era, por
    construção, uma AFIRMAÇÃO de que aquele CPF está no cadastro.

    E não é estado exótico. Em produção o remetente é sempre SMTP, e
    `send_message` levanta quando o relay recusa o destinatário — um e-mail
    velho ou digitado errado numa linha de `filiados.csv`, que é rotina numa
    base de sindicato, dá um 502 permanente e estável para exatamente aquele
    CPF.

    `app.py` abre dizendo: "O QUE A RESPOSTA NUNCA DIZ: se um CPF está ou não
    no rol da entidade." O teste estrutural que existia percorre cinco
    estados do `gestores.csv` — mas nenhum deles passa pelo ramo de ENVIO, e
    era ali que a igualdade caía.
    """
    secao("falha de envio não revela filiação")
    from servidor import remetente as mod_remetente

    original = mod_remetente.ParaArquivo.enviar

    def quebrado(self, *a, **k):
        raise RuntimeError("relay recusou o destinatário")

    mod_remetente.ParaArquivo.enviar = quebrado
    try:
        c = Cenario()
        dentro = _corpo_comparavel(c.cliente.post(
            "/api/acesso/codigo",
            json={"entidade": "demo-teste", "cpf": CPF}))
        fora = _corpo_comparavel(c.cliente.post(
            "/api/acesso/codigo",
            json={"entidade": "demo-teste", "cpf": OUTRO_CPF}))
    finally:
        mod_remetente.ParaArquivo.enviar = original

    checa(dentro == fora,
          f"com o envio falhando, a resposta revela filiação: "
          f"dentro={dentro} fora={fora}")
    checa(dentro[0] == 202,
          f"a falha de envio virou status próprio: {dentro}")
    print("  ok     envio quebrado responde igual dentro e fora do rol")


def teste_terceiro_nao_tranca_o_filiado_fora_do_portao():
    """TRÊS PEDIDOS ANÔNIMOS TIRAVAM UMA PESSOA NOMEADA DO PORTÃO.

    O teto por CPF é contado por `cpf_hash`, e `/api/acesso/codigo` é
    anônima: quem pede não prova relação nenhuma com aquele CPF. Então um
    terceiro gastava a cota de um filiado com três pedidos.

    E o bloqueio era completo, não uma corrida, porque as duas janelas não
    se encaixavam: o código vale 15 minutos e a contagem olha 60. Do minuto
    15 ao 60 a vítima não tinha código válido E não conseguia emitir outro.
    Este portão é a única porta: sem ele a pessoa não envia cadastro, não lê
    o próprio cadastro, não lê as próprias ações nem os próprios processos.

    A regra passa a ser: recusa ENQUANTO existe código vivo — e aí a
    mensagem é verdadeira, porque o código está na caixa de entrada dela.
    Sem código vivo, recusar não protege ninguém e só tranca o dono.
    """
    secao("o teto não tranca o dono do CPF")
    # O teto por ORIGEM fica alto de propósito: o que está sob teste é o
    # teto por CPF, e esbarrar no outro faria o teste falhar por motivo
    # errado — que foi o que aconteceu na primeira tentativa.
    c = Cenario(limite_de_emissoes=3, limite_por_origem=500)

    for _ in range(3):
        c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-teste", "cpf": CPF})

    # Enquanto o código VIVE, recusar é honesto: ela tem um na caixa.
    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-teste", "cpf": CPF})
    checa(r.status_code == 429,
          f"deixou de limitar o volume de e-mail: {r.status_code}")

    # Expirado o código, a vítima TEM de conseguir entrar.
    _expirar_codigos(c)
    r = c.cliente.post("/api/acesso/codigo",
                       json={"entidade": "demo-teste", "cpf": CPF})
    checa(r.status_code == 202,
          f"a pessoa ficou trancada fora do portão sem ter código válido: "
          f"{r.status_code} {r.text[:200]}")

    # E o código tem de SERVIR — 202 com código inútil não é acesso.
    codigo = r.json().get("codigo_do_ensaio")
    checa(bool(codigo), f"202 sem código utilizável: {r.json()}")
    r2 = c.cliente.post("/api/acesso/conferir",
                        json={"entidade": "demo-teste", "cpf": CPF,
                              "codigo": codigo})
    checa(r2.status_code == 200 and r2.json().get("token"),
          f"o código novo não abriu sessão: {r2.status_code} "
          f"{r2.text[:200]}")
    print("  ok     recusa só enquanto há código vivo; o dono sempre entra")


def teste_openapi_nao_fica_aberto_em_producao():
    """O ESQUEMA DA API NÃO É DOCUMENTAÇÃO PÚBLICA DESTE PRODUTO.

    `criar_app` já desligava `docs_url` e `redoc_url`, mas `openapi_url`
    fica em `/openapi.json` por padrão — e ele publica, a um anônimo, a
    lista de rotas, a forma de cada corpo e cada resposta, e os nomes
    internos. Não é vulnerabilidade por si: é o mapa que torna todo o resto
    mais fácil, inclusive enumerar rotas que ninguém divulgou.

    Em MODO ENSAIO continua ligado de propósito: lá não há dado de pessoa, e
    quem está desenvolvendo precisa dele. A diferença entre os dois é o
    ponto do teste — desligar nos dois seria pagar conveniência por nada.
    """
    secao("o esquema da API não é público")
    import tempfile as _tempfile

    from fastapi.testclient import TestClient

    from servidor import entidades as mod_entidades
    from servidor.app import criar_app
    from servidor.config import carregar

    # Em ensaio: continua servindo, porque é ferramenta de quem desenvolve.
    c = Cenario()
    r = c.cliente.get("/openapi.json")
    checa(r.status_code == 200,
          f"o ensaio perdeu o esquema, que é ferramenta de desenvolvimento: "
          f"{r.status_code}")

    # Fora do ensaio: não serve.
    raiz = Path(_tempfile.mkdtemp(prefix="openapi-teste-"))
    _NASCIDOS.append(raiz)
    mod_entidades.Cadastro(raiz).criar("demo-prod", "Demonstração")
    cfg = carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_SEGREDO": "segredo-de-teste-com-tamanho-suficiente",
        "PROTOCOL_SMTP_HOST": "smtp.exemplo.invalid",
        "PROTOCOL_SMTP_REMETENTE": "naoresponda@exemplo.invalid",
        "PROTOCOL_REGIAO": "sa-east-1",
        "PROTOCOL_AGENDAR": "0",
    })
    checa(cfg.modo_ensaio is False, "o cenário de produção saiu em ensaio")
    producao = TestClient(criar_app(cfg))
    for rota in ("/openapi.json", "/docs", "/redoc"):
        r = producao.get(rota)
        checa(r.status_code == 404,
              f"{rota} responde {r.status_code} em produção, e devia ser 404")

    # E O QUE O MONITOR PRECISA CONTINUA DE PÉ: desligar o esquema não pode
    # ter derrubado a saúde junto.
    r = producao.get("/saude")
    checa(r.status_code == 200, f"a saúde caiu junto: {r.status_code}")
    print("  ok     esquema servido em ensaio, 404 em produção")


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
    from nucleo import cadastro as conta

    maximo = conta.MAXIMO_DE_PROCESSOS
    formatados = ";".join(
        processo_cnj.normalizar(numero("%07d" % (1000 + i), "01", "3400"))
        for i in range(maximo)
    )
    # Formatados de verdade, com pontuação, como o portal exibe.
    bonitos = ";".join(
        processo_cnj.decompor(processo_cnj.so_digitos(n)).formatado
        for n in formatados.split(";")
    )
    problemas = conta.conferir(linha(numeros_de_processo=bonitos))
    checa(problemas == [],
          f"{maximo} números formatados foram recusados: {problemas}")
    print(f"  ok     {maximo} números formatados cabem no campo")


TESTES.extend([
    teste_pedir_codigo_responde_igual_dentro_e_fora_do_rol,
    teste_falha_de_envio_nao_revela_filiacao,
    teste_openapi_nao_fica_aberto_em_producao,
    teste_terceiro_nao_tranca_o_filiado_fora_do_portao,
    teste_rol_em_latin1_nao_fecha_o_portao,
    teste_acompanhar_aceita_20_numeros_formatados,
])


# ======================================================= minhas ações (7c)
#
# A TELA QUE O CADASTRO PROMETE. O último aviso de `Confirmar.tsx` diz: "a
# gente lê os seus documentos e mostra de quais ações você faz parte e o que
# pode ser feito em cada uma". Até aqui o motor calculava isso e ninguém via.
#
# E o que esta rota NÃO pode fazer é tão importante quanto o que ela faz:
# nenhuma das travas do portão pode ser frouxa por ser "só consulta". É
# consulta de dado sensível de uma pessoa nomeada.


def teste_minhas_acoes_exige_sessao():
    secao("minhas ações")
    c = Cenario()
    for cabecalho in ({}, {"Authorization": "Bearer invalido"}):
        r = c.cliente.get("/api/minhas-acoes", headers=cabecalho)
        checa(r.status_code == 401,
              f"consulta aberta sem sessão válida: {r.status_code}")
    print("  ok     sem sessão válida, 401")


def teste_minhas_acoes_nao_aceita_cpf_por_parametro():
    """Mesma trava de `/api/meus-processos`: aceitar CPF de fora
    transformaria a consulta na pesquisa de filiação que o portão se recusa a
    ser."""
    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "fulano@exemplo.org"),
                                  (OUTRO_CPF, "outro@exemplo.org")])
    c.cadastrar(OUTRO_CPF)
    r = c.cliente.get(f"/api/minhas-acoes?cpf={OUTRO_CPF}",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code} {r.text[:200]}")
    corpo = r.json()
    checa(corpo["oportunidades"] == [],
          f"o parâmetro cpf foi obedecido e vazou: {corpo}")
    checa(corpo["filiado"] == "",
          f"vazou o nome de quem não abriu a sessão: {corpo['filiado']!r}")
    print("  ok     parâmetro cpf é ignorado, não obedecido")


def teste_entidade_sem_categoria_nao_recebe_veredicto_nem_erro():
    """FAIL-CLOSED, e sem parecer defeito. Um sindicato cuja categoria não
    foi declarada não pode receber o catálogo dos outros — e também não pode
    receber erro 500, que mandaria a pessoa ligar."""
    c = Cenario(categorias=())
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"deu erro em vez de resposta: {r.status_code}")
    corpo = r.json()
    checa(corpo["oportunidades"] == [] and corpo["acoes"] == [],
          f"entidade sem categoria recebeu veredicto: {corpo}")
    checa(corpo["categorias"] == [], f"veio {corpo['categorias']}")
    checa(bool(corpo.get("aviso", "").strip()),
          "não explicou por que a lista está vazia")
    print("  ok     sem categoria contratada: lista vazia, com explicação")


def teste_o_filiado_ve_as_acoes_da_categoria_contratada():
    c = Cenario()
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code} {r.text[:300]}")
    corpo = r.json()
    checa("GIFA-2006" in [a["id"] for a in corpo["acoes"]],
          f"a ação da categoria contratada não apareceu: {corpo['acoes']}")
    checa("GIFA-2006" in [o["referencia"] for o in corpo["oportunidades"]],
          "a oportunidade da ação não apareceu")
    checa(corpo["filiado"].startswith("FULANA"),
          f"o nome do filiado não veio: {corpo['filiado']!r}")
    checa("auditor-fiscal-receita-federal@" in corpo["catalogo"],
          f"a assinatura do catálogo não veio: {corpo['catalogo']!r}")
    print(f"  ok     {len(corpo['acoes'])} ação(ões), "
          f"{len(corpo['oportunidades'])} oportunidade(s)")


def teste_outra_categoria_nao_ve_a_acao():
    """O isolamento que o exemplo da PFDF/PMDF exige: a ação da GIFA é da
    carreira de Auditor-Fiscal, e um sindicato de outra categoria não a vê."""
    c = Cenario(categorias=("analista-tributario-receita-federal",))
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"não respondeu: {r.status_code}")
    corpo = r.json()
    checa("GIFA-2006" not in [a["id"] for a in corpo["acoes"]],
          f"VAZOU a ação de outra categoria: {corpo['acoes']}")
    print("  ok     a ação de outra categoria não aparece")


def teste_nada_homologado_nada_de_PODE():
    """A trava que vem de fora do código: nada nominal sai sem advogado. O
    catálogo em disco tem `homologado = "N"` em tudo, e nenhuma resposta pode
    dizer PODE enquanto for assim."""
    c = Cenario()
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    pode = [o for o in r.json()["oportunidades"] if o["veredicto"] == "PODE"]
    checa(pode == [],
          f"disse PODE com o catálogo não homologado: {pode}")
    print("  ok     catálogo não homologado: nenhum PODE")


def teste_toda_pendencia_chega_com_dono_e_as_tres_chaves():
    """O que faz a tela cortar telefonema. Saco único de pendências é o que
    faz a pessoa ligar para descobrir o que é tarefa dela."""
    from nucleo import pendencia

    c = Cenario()
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    corpo = r.json()
    grupos = corpo["pendencias"]
    checa([g["quem"] for g in grupos] == list(pendencia.DONOS),
          f"as três chaves não vieram na ordem: {[g['quem'] for g in grupos]}")
    for g in grupos:
        checa(bool(g["titulo"]) and bool(g["explicacao"]),
              f"{g['quem']} sem texto para a pessoa ler")
    for o in corpo["oportunidades"]:
        for f in o["falta"]:
            checa(f["quem"] in pendencia.DONOS,
                  f"falta sem dono conhecido na resposta: {f}")
    com_itens = [g["quem"] for g in grupos if g["itens"]]
    checa(bool(com_itens), "nenhuma pendência veio, e o catálogo não está "
                           "homologado — devia haver pelo menos a conferência")
    print(f"  ok     pendências por dono: {', '.join(com_itens)}")


def teste_a_resposta_diz_que_nao_e_parecer():
    """Nada nominal sai sem homologação humana, e a pessoa tem de ler isso na
    própria resposta — não no rodapé de uma página que ela não abriu."""
    c = Cenario()
    c.cadastrar(CPF)
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    aviso = r.json().get("aviso", "").lower()
    checa("parecer" in aviso, f"a resposta não diz que não é parecer: {aviso!r}")
    checa("escritório" not in aviso and "escritorio" not in aviso,
          f"REGRA ZERO: o aviso do filiado fala de escritório: {aviso!r}")
    print("  ok     a resposta diz que não é parecer")


def teste_quem_nao_tem_cadastro_recebe_lista_vazia_e_nao_erro():
    """Quem passou pelo portão mas ainda não cadastrou existe: é a pessoa que
    entrou para ver antes de enviar. Erro aqui a manda ligar."""
    c = Cenario()
    r = c.cliente.get("/api/minhas-acoes",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 200, f"deu erro: {r.status_code} {r.text[:200]}")
    corpo = r.json()
    checa(corpo["oportunidades"] == [] and corpo["filiado"] == "",
          f"inventou resposta para quem não cadastrou: {corpo}")
    checa(bool(corpo.get("aviso", "").strip()), "não explicou o vazio")
    print("  ok     sem cadastro: vazio com explicação, não erro")


TESTES.extend([
    teste_minhas_acoes_exige_sessao,
    teste_minhas_acoes_nao_aceita_cpf_por_parametro,
    teste_entidade_sem_categoria_nao_recebe_veredicto_nem_erro,
    teste_o_filiado_ve_as_acoes_da_categoria_contratada,
    teste_outra_categoria_nao_ve_a_acao,
    teste_nada_homologado_nada_de_PODE,
    teste_toda_pendencia_chega_com_dono_e_as_tres_chaves,
    teste_a_resposta_diz_que_nao_e_parecer,
    teste_quem_nao_tem_cadastro_recebe_lista_vazia_e_nao_erro,
])


# ========================================== panorama do sindicato (8)
#
# A MESMA RESPOSTA DO FILIADO, SOMADA. `completude` conta o estado da BASE —
# quem não se alcança, que campo falta —, que é o retrato da primeira semana.
# O panorama responde a pergunta da terceira: "o que eu faço primeiro?".
#
# As travas são as do painel, inteiras: é lista NOMINAL de quem tem o quê, e
# "é só um resumo" não a torna menos sensível.


def teste_panorama_exige_token_de_gestor():
    secao("panorama do sindicato")
    c = Cenario()
    r = c.cliente.get("/api/entidade/demo-teste/panorama")
    checa(r.status_code == 401,
          f"panorama aberto sem autenticação: {r.status_code}")
    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization": f"Bearer {c.token(CPF)}"})
    checa(r.status_code == 403,
          f"token de filiado abriu o panorama: {r.status_code}")
    print("  ok     sem token, 401; com token de filiado, 403")


def teste_panorama_nao_atravessa_entidade():
    c = Cenario(entidades_extra=(("demo-outra", "Outro Sindicato"),))
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    c.escrever_gestores("demo-outra", [(OUTRO_CPF, "gestor@exemplo.org")])
    c.escrever_rol("demo-outra", [(CPF, "fulano@exemplo.org")])
    token = c.token(OUTRO_CPF, apelido="demo-teste")
    r = c.cliente.get("/api/entidade/demo-outra/panorama",
                      headers={"Authorization": f"Bearer {token}"})
    # O MESMO CPF É GESTOR DAS DUAS, e ainda assim a sessão não atravessa:
    # a sessão é de UMA entidade, e quem quer ver a outra entra por ela.
    checa(r.status_code in (401, 403, 404),
          f"sessão de demo-teste abriu o panorama de demo-outra: "
          f"{r.status_code}")
    print("  ok     nem o gestor das duas atravessa com uma sessão só")


def teste_gestor_ve_o_panorama_da_propria_base():
    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "fulano@exemplo.org"),
                                  (OUTRO_CPF, "gestor@exemplo.org")])
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "gestor@exemplo.org")])
    c.cadastrar(CPF)

    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization": f"Bearer {c.token(OUTRO_CPF)}"})
    checa(r.status_code == 200,
          f"não respondeu: {r.status_code} {r.text[:300]}")
    corpo = r.json()
    checa(corpo["pessoas"] == 1, f"contou {corpo['pessoas']} pessoas")
    checa("GIFA-2006" in [a["acao"] for a in corpo["por_acao"]],
          f"a ação da categoria contratada não apareceu: {corpo['por_acao']}")
    checa(bool(corpo["gargalos"]), "nenhum gargalo apurado")
    checa(bool(corpo["manchete"].strip()), "veio sem manchete")
    checa(corpo["leu_documentos"] is False,
          "disse que leu documentos, e o panorama não abre PDF")
    print(f"  ok     {corpo['manchete']}")


def teste_os_gargalos_vem_do_maior_para_o_menor_com_dono():
    from nucleo import pendencia

    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "a@exemplo.org"),
                                  (OUTRO_CPF, "b@exemplo.org"),
                                  (TERCEIRO_CPF, "c@exemplo.org")])
    c.escrever_gestores("demo-teste", [(TERCEIRO_CPF, "c@exemplo.org")])
    c.cadastrar(CPF)
    c.cadastrar(OUTRO_CPF)

    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization":
                               f"Bearer {c.token(TERCEIRO_CPF)}"})
    gargalos = r.json()["gargalos"]
    quantidades = [g["pessoas"] for g in gargalos]
    checa(quantidades == sorted(quantidades, reverse=True),
          f"não vieram do maior para o menor: {quantidades}")
    for g in gargalos:
        checa(g["quem"] in pendencia.DONOS, f"gargalo sem dono: {g}")
        checa(g["titulo"] and g["explicacao"],
              f"gargalo sem texto para o gestor ler: {g}")
    checa(gargalos[0]["pessoas"] == 2,
          f"o maior gargalo devia segurar as 2 pessoas: {gargalos[0]}")
    print(f"  ok     {len(gargalos)} gargalos, maior com "
          f"{gargalos[0]['pessoas']} pessoas")


def teste_o_panorama_so_mostra_gente_da_propria_entidade():
    """A trava que importa, e ela é NOMINAL: os exemplos trazem nome."""
    c = Cenario(entidades_extra=(("demo-outra", "Outro Sindicato"),))
    c.escrever_rol("demo-teste", [(CPF, "a@exemplo.org"),
                                  (TERCEIRO_CPF, "c@exemplo.org")])
    c.escrever_rol("demo-outra", [(OUTRO_CPF, "b@exemplo.org")])
    c.escrever_gestores("demo-teste", [(TERCEIRO_CPF, "c@exemplo.org")])
    c.cadastrar(CPF, nome_completo="FULANA DAQUI (CADASTRO DE EXEMPLO)")
    c.enviar(c.token(OUTRO_CPF, apelido="demo-outra"),
             linha(OUTRO_CPF, nome_completo="BELTRANO DE FORA (EXEMPLO)"),
             pacote(OUTRO_CPF))

    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization":
                               f"Bearer {c.token(TERCEIRO_CPF)}"})
    corpo = r.json()
    nomes = [n for g in corpo["gargalos"] for n in g["exemplos"]]
    checa(corpo["pessoas"] == 1,
          f"contou gente de outra entidade: {corpo['pessoas']}")
    checa(not any("FORA" in n for n in nomes),
          f"VAZOU nome de outra entidade: {nomes}")
    checa(any("DAQUI" in n for n in nomes),
          f"não trouxe o nome de quem é desta entidade: {nomes}")
    print("  ok     só gente da própria entidade, e com nome")


def teste_entidade_sem_categoria_tem_panorama_vazio_e_nao_erro():
    c = Cenario(categorias=())
    c.escrever_rol("demo-teste", [(CPF, "a@exemplo.org"),
                                  (OUTRO_CPF, "b@exemplo.org")])
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "b@exemplo.org")])
    c.cadastrar(CPF)
    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization": f"Bearer {c.token(OUTRO_CPF)}"})
    checa(r.status_code == 200, f"deu erro em vez de resposta: {r.status_code}")
    corpo = r.json()
    checa(corpo["por_acao"] == [] and corpo["gargalos"] == [],
          f"entidade sem categoria recebeu panorama: {corpo}")
    checa("categoria" in corpo["manchete"].lower(),
          f"a manchete não explica o vazio: {corpo['manchete']!r}")
    print("  ok     sem categoria: vazio com explicação, não erro")


def teste_quem_entregou_sentenca_nao_e_cobrado_dela_no_painel():
    """O número falso que quase foi dito ao diretor: sem olhar os arquivos
    entregues, "falta a sentença" apareceria para a base inteira."""
    from nucleo import pendencia

    c = Cenario()
    c.escrever_rol("demo-teste", [(CPF, "a@exemplo.org"),
                                  (OUTRO_CPF, "b@exemplo.org")])
    c.escrever_gestores("demo-teste", [(OUTRO_CPF, "b@exemplo.org")])
    # `pacote(com_judicial=True)` manda sentença e certidão junto.
    c.enviar(c.token(CPF), linha(CPF), pacote(CPF, com_judicial=True))

    r = c.cliente.get("/api/entidade/demo-teste/panorama",
                      headers={"Authorization": f"Bearer {c.token(OUTRO_CPF)}"})
    donos = {g["quem"] for g in r.json()["gargalos"]
             if "sentença" in g["o_que"].lower()}
    checa(pendencia.VOCE not in donos,
          f"cobrou a sentença de quem já entregou: {donos}")
    print("  ok     sentença entregue não é cobrada da pessoa")


TESTES.extend([
    teste_panorama_exige_token_de_gestor,
    teste_panorama_nao_atravessa_entidade,
    teste_gestor_ve_o_panorama_da_propria_base,
    teste_os_gargalos_vem_do_maior_para_o_menor_com_dono,
    teste_o_panorama_so_mostra_gente_da_propria_entidade,
    teste_entidade_sem_categoria_tem_panorama_vazio_e_nao_erro,
    teste_quem_entregou_sentenca_nao_e_cobrado_dela_no_painel,
])


if __name__ == "__main__":
    raise SystemExit(main())
