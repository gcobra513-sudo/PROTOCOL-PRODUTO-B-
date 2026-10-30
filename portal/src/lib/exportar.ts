/**
 * A conta, no formato que o servidor recebe.
 *
 * AS COLUNAS NÃO ESTÃO ESCRITAS AQUI: vêm de
 * `compartilhado/contrato_cadastro.json`, o mesmo arquivo que
 * `nucleo/cadastro.py` lê. Enquanto cada lado tinha a sua lista, três dos
 * seis nomes de arquivo divergiam — e a divergência só apareceria na
 * primeira entrega de verdade, com tudo reprovando por arquivo faltando.
 */
import {
  CONTRATO,
  type Rascunho,
  type TipoDocumento,
  nomeDeArquivo,
} from "./tipos";
import { soDigitos } from "./validacao";

/** Os números de processo como o contrato pede: só dígitos, sem repetição,
 *  na ordem de chegada. A primeira menção vence — é a que a pessoa digitou
 *  primeiro, e inverter trocaria a ordem que ela escolheu. */
export function numerosParaAcompanhar(numeros: string[]): string {
  const vistos: string[] = [];
  for (const bruto of numeros ?? []) {
    const d = soDigitos(bruto);
    if (d && !vistos.includes(d)) vistos.push(d);
  }
  return vistos.join(";");
}

/** A conta, campo a campo, na forma que o servidor valida. */
export function linhaDoCadastro(r: Rascunho): Record<string, string> {
  const i = r.identificacao;
  const c = r.carreira;
  return {
    cpf: i.cpf,
    nome_completo: i.nome,
    email: i.email,
    telefone: i.telefone,
    cargo: c.cargo,
    situacao: c.situacao,
    unidade: c.unidade,
    data_nascimento: i.dataNascimento,
    data_ingresso: c.dataIngresso,
    data_aposentadoria: c.dataAposentadoria,
    filiado_desde: r.filiacao.desde,
    // Vazio é resposta: ainda filiado. Não se inventa data de saída.
    filiado_ate: r.filiacao.ate,
    tem_processo: r.judicial.temProcesso,
    numeros_de_processo: numerosParaAcompanhar(r.judicial.numeros),
    ja_executou: r.judicial.jaExecutou,
    tem_acao_propria: r.judicial.temAcaoPropria,
    // "sim" ou vazio, nunca booleano: o contrato é de texto dos dois lados.
    quer_aviso: r.querAviso ? "sim" : "",
  };
}

/** O nome de cada arquivo enviado, por tipo e por ordem.
 *
 *  Vários do mesmo tipo é o caso NORMAL na contribuição: um comprovante por
 *  ano. O índice é por tipo, não global, senão `contribuicao-3.pdf` poderia
 *  ser o primeiro contracheque de alguém. */
export function nomearDocumentos(r: Rascunho): Map<number, string> {
  const contagem = new Map<TipoDocumento, number>();
  const nomes = new Map<number, string>();
  r.documentos.forEach((d, posicao) => {
    const i = contagem.get(d.tipo) ?? 0;
    contagem.set(d.tipo, i + 1);
    nomes.set(posicao, nomeDeArquivo(d.tipo, i));
  });
  return nomes;
}

/**
 * O recibo que a pessoa leva: o que foi registrado e o hash de cada arquivo.
 *
 * Os hashes importam por procedência: se o arquivo for trocado no caminho, dá
 * para perceber.
 */
export function reciboJson(r: Rascunho): string {
  const nomes = nomearDocumentos(r);
  return JSON.stringify(
    {
      gerado_em: new Date().toISOString(),
      contrato: "compartilhado/contrato_cadastro.json",
      contrato_versao: CONTRATO._versao,
      cpf: soDigitos(r.identificacao.cpf),
      cadastro: linhaDoCadastro(r),
      documentos: r.documentos.map((d, posicao) => ({
        arquivo: nomes.get(posicao),
        tipo: d.tipo,
        enviado_como: d.nomeOriginal,
        bytes: d.tamanho,
        sha256: d.sha256,
        tem_texto: d.temTexto,
        cpf_encontrado_no_documento: d.cpfEncontrado,
      })),
      aviso:
        "Este recibo não é parecer. Nenhuma ação foi apresentada em juízo " +
        "com base neste cadastro.",
    },
    null,
    2,
  );
}

export function baixar(nome: string, conteudo: string, tipo: string): void {
  const blob = new Blob([conteudo], { type: `${tipo};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}
