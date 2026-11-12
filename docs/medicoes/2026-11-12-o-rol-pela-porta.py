"""SONDA: o que muda quando o rol de substituídos ENTRA pela porta nova.

Refaz a medição de 10/11/2026 (`2026-11-10-o-que-da-pode.py`), que mostrou
que nenhum caminho do produto preenchia `no_rol`. Aqui o fato não é posto à
mão: o rol passa por `servidor.substituidos` — o mesmo miolo da rota do
painel — e chega ao motor pelo construtor único, `panorama.fatos_do_cadastro`.

    python3 docs/medicoes/2026-11-12-o-rol-pela-porta.py
"""
import pathlib, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO))
from nucleo import entendimentos, motor, panorama
from servidor import substituidos

cat = entendimentos.carregar_categorias(REPO / "config/categorias", ("auditor-fiscal-receita-federal",))
ids = tuple(a.id for a in cat.acoes) + tuple(e.id for e in cat.entendimentos)
hom = cat.homologando(ids)        # o ajudante de TESTE: tudo homologado em memória

NO_ROL, FORA, DEPOIS, DE_FORA = "11144477735", "52998224725", "39053344705", "16899535009"
pasta = pathlib.Path(tempfile.mkdtemp(prefix="sonda-rol-"))
rol = f"CPF;Nome\n{NO_ROL};EXEMPLO UM (FICTÍCIO)\n{DE_FORA};EXEMPLO DE FORA DA BASE (FICTÍCIO)\n".encode()

def linha(cpf):
    return {"cpf": cpf, "nome_completo": "PESSOA DE EXEMPLO (FICTÍCIA)",
            "cargo": "Auditor Fiscal da Receita Federal", "situacao": "aposentado",
            "filiado_desde": "2004-03", "ja_executou": "nao", "tem_acao_propria": "nao"}

TITULO = {"dispositivo": "procedente", "transito_em_julgado": "2019-08-22"}   # sentença LIDA
def ver(rotulo, cpf, catalogo=hom, lidos=TITULO, entregues=("contribuicao", "sentenca", "certidao_transito")):
    fatos = panorama.fatos_do_cadastro(linha(cpf), entregues, lidos,
                                       rol=substituidos.de_cpf(pasta, cpf))
    print(f"\n{rotulo}")
    for o in motor.avaliar(fatos, catalogo):
        if o.trilha == "executar":
            print(f"   {o.referencia:10} {o.veredicto:9} "
                  + "; ".join(f"[{x.quem}] {x.o_que[:60]}" for x in o.falta))
            for n in o.notas:
                if "rol" in n:
                    print(f"              nota: {n}")

print("catálogo: TUDO homologado em memória (em disco, nada está)")
ver("0) ANTES do rol — a medição de 10/11:", NO_ROL)

lido = substituidos.ler_arquivo(rol, "rol.csv")
plano = substituidos.planejar(lido, {NO_ROL, FORA}, acao="GIFA-2006", completo=True)
substituidos.gravar(pasta, plano, quem="sonda", arquivo="rol.csv", sha256="-")
print(f"\n--- rol enviado, declarado COMPLETO: constam {len(plano.constam)}, "
      f"não constam {len(plano.nao_constam)}, fora da base {plano.fora_da_base} "
      f"(guardado no arquivo? {DE_FORA in (pasta / substituidos.ARQUIVO).read_text()})")

ver("A) No rol, com sentença própria lida:", NO_ROL)
ver("B) FORA de um rol declarado completo:", FORA)
ver("C) Entrou na base DEPOIS do envio (nunca foi comparada):", DEPOIS)
ver("D) No rol, SEM sentença própria — a segunda trava, que é do jurídico:",
    NO_ROL, lidos={}, entregues=("contribuicao",))
ver("E) O caso A com o catálogo COMO ESTÁ EM DISCO (nada homologado):", NO_ROL, catalogo=cat)
