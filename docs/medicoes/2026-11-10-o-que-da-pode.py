"""SONDA: que fatos produzem PODE, e quais deles o produto consegue obter."""
import pathlib, sys, tempfile, dataclasses
REPO = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO))
from nucleo import entendimentos, motor

cat = entendimentos.carregar_categorias(REPO / "config/categorias", ("auditor-fiscal-receita-federal",))
ids = tuple(a.id for a in cat.acoes) + tuple(e.id for e in cat.entendimentos)
hom = cat.homologando(ids)        # o ajudante de TESTE: tudo homologado em memória

base = dict(cpf="11144477735", nome="FULANA (EXEMPLO)", cargo="Auditor Fiscal da Receita Federal",
            situacao="aposentado", filiado_desde="2004-03",
            documentos_entregues=("contribuicao", "sentenca", "certidao_transito"))

def ver(rotulo, **f):
    ops = motor.avaliar(motor.Fatos(**{**base, **f}), hom)
    print(f"\n{rotulo}")
    for o in ops:
        falta = "; ".join(x.o_que[:52] for x in o.falta)
        print(f"   {o.trilha:9} {o.referencia:12} {o.veredicto:9} {falta}")

print(f"catálogo: {len(cat.acoes)} ação(ões), {len(cat.entendimentos)} entendimento(s) — TUDO homologado em memória")
ver("A) O MELHOR que o produto consegue montar hoje (sentença lida, respostas da pessoa):",
    tem_titulo=True, ja_executou=False, tem_acao_propria=False)
ver("B) O mesmo, mais no_rol=True — fato que NENHUM caminho do produto preenche:",
    tem_titulo=True, ja_executou=False, tem_acao_propria=False, no_rol=True)

# C) A SEGUNDA TRAVA, achada depois: a pessoa está no rol de uma coletiva JÁ
#    TRANSITADA, e não mandou sentença nenhuma — porque a sentença é da AÇÃO,
#    não dela, e o portal a pede como "Sentença, se você tiver".
base_sem_docs = {**base, "documentos_entregues": ("contribuicao",)}
ops = motor.avaliar(motor.Fatos(**{**base_sem_docs, "ja_executou": False,
                                   "tem_acao_propria": False, "no_rol": True}), hom)
print("\nC) No rol de coletiva TRANSITADA, sem sentença própria enviada:")
for o in ops:
    if o.trilha == "executar":
        print(f"   {o.trilha:9} {o.referencia:12} {o.veredicto:9} "
              + "; ".join(f"[{x.quem}] {x.o_que}" for x in o.falta))
