/**
 * A confirmação. Duas caixas, e elas fazem coisas diferentes.
 *
 *   a declaração   é obrigatória: os dados são meus e são verdadeiros
 *   o aviso        é opcional e NÃO vem marcado. Opt-in pré-marcado não é
 *                  opt-in, e é também o que sustenta a gente poder escrever
 *                  para a pessoa depois
 */
import { Aviso, Caixa, Cartao } from "../componentes/ui";
import { DOCUMENTOS, type Rascunho } from "../lib/tipos";

export function Confirmar({
  rascunho,
  onConfirmar,
  onQuerAviso,
}: {
  rascunho: Rascunho;
  onConfirmar: (v: boolean) => void;
  onQuerAviso: (v: boolean) => void;
}) {
  const porTipo = new Map<string, number>();
  for (const d of rascunho.documentos) {
    porTipo.set(d.tipo, (porTipo.get(d.tipo) ?? 0) + 1);
  }

  return (
    <Cartao
      titulo="Conferir e enviar"
      explicacao="Depois de enviar você pode voltar e corrigir — ninguém acerta
        tudo de primeira."
    >
      <div className="rounded-md border border-borda bg-papel p-4 text-[15px] text-tinta">
        <p>
          <strong>{rascunho.identificacao.nome || "(sem nome)"}</strong>
        </p>
        <p className="mt-1 text-tinta/75">
          {rascunho.carreira.cargo || "(sem cargo)"} ·{" "}
          {rascunho.carreira.situacao || "(sem situação)"}
        </p>
        <p className="mt-1 text-tinta/75">
          Filiado desde {rascunho.filiacao.desde || "—"}
          {rascunho.filiacao.ate ? ` até ${rascunho.filiacao.ate}` : " (ainda filiado)"}
        </p>
        <ul className="mt-3 space-y-1 text-sm text-tinta/75">
          {DOCUMENTOS.map((espec) => (
            <li key={espec.tipo}>
              {espec.rotulo}: <strong>{porTipo.get(espec.tipo) ?? 0}</strong>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-md border border-borda bg-papel p-4">
        <Caixa
          marcado={rascunho.confirmou}
          onChange={onConfirmar}
          rotulo={
            <strong>
              Declaro que as informações e os documentos que enviei são meus e
              são verdadeiros.
            </strong>
          }
          detalhe="E que aviso o sindicato se algo mudar."
        />
      </div>

      <div className="rounded-md border border-borda bg-papel p-4">
        <Caixa
          marcado={rascunho.querAviso}
          onChange={onQuerAviso}
          rotulo={
            <strong>
              Quero receber aviso por e-mail quando houver movimentação nos
              meus processos.
            </strong>
          }
          detalhe="Opcional, e dá para mudar depois. Sem isso a gente não te
            escreve — você ainda pode entrar e consultar quando quiser."
        />
      </div>

      <Aviso tom="neutro">
        <strong>O que acontece depois:</strong> a gente lê os seus documentos e
        mostra de quais ações você faz parte e o que pode ser feito em cada
        uma. <strong>Isso não é parecer</strong> — nada é apresentado em juízo
        com base neste cadastro.
      </Aviso>
    </Cartao>
  );
}
