/**
 * A entrega: o que o portal produz para o motor consumir.
 *
 * Formato ditado por `compartilhado/contrato_entrega.json` e conferido por
 * `ferramentas/conferir_entrega.py`:
 *
 *     entrega/
 *       manifesto.csv            uma linha por filiado, colunas do contrato
 *       52601815906/             pasta com os 11 dígitos do CPF
 *         procuracao.pdf
 *         identidade.pdf
 *         comprovante_residencia.pdf
 *         ...
 *
 * POR QUE AS COLUNAS NÃO ESTÃO ESCRITAS AQUI: elas vêm do contrato. Enquanto
 * cada lado tinha a sua lista, três dos seis nomes de arquivo divergiam — e a
 * divergência só apareceria na primeira entrega de verdade, com todas as
 * pastas reprovando por arquivo faltando.
 *
 * LIMITE DESTA VERSÃO, dito de frente: sem servidor, o pacote é baixado pela
 * própria pessoa e entregue ao escritório por fora. Não é o fluxo final — o
 * final é o portal enviar. Mas é um pacote que o motor já consome, e isso
 * fecha o laço hoje em vez de depois.
 */
import { CONTRATO, type Rascunho } from "./tipos";
import { soDigitos } from "./validacao";

/** Escapa um campo para CSV: aspas duplas e quebra de linha quebram arquivo. */
function campoCsv(valor: string): string {
  const v = valor ?? "";
  return /[",\n\r;]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

/** Os números a acompanhar, como o contrato pede: só dígitos, sem repetição,
 *  juntos pelo separador. A primeira menção vence — é a que a pessoa digitou
 *  primeiro, e inverter isso trocaria a ordem que ela escolheu. */
export function numerosParaAcompanhar(numeros: string[]): string {
  const vistos: string[] = [];
  for (const bruto of numeros ?? []) {
    const d = soDigitos(bruto);
    if (d && !vistos.includes(d)) vistos.push(d);
  }
  return vistos.join(CONTRATO.acompanhamento.separador);
}

/** Uma linha do manifesto, na ordem exata das colunas do contrato. */
export function linhaDoManifesto(r: Rascunho): Record<string, string> {
  const p = r.pessoais;
  const f = r.funcional;
  const d = r.declaracoes;
  return {
    id_externo: soDigitos(p.cpf),
    cpf: p.cpf,
    nome_completo: p.nome,
    matricula: p.matricula,
    rg: p.rg,
    data_nascimento: p.dataNascimento,
    email: p.email,
    telefone: p.telefone,
    cep: p.cep,
    logradouro: p.logradouro,
    numero: p.numero,
    complemento: p.complemento,
    bairro: p.bairro,
    municipio: p.municipio,
    uf: p.uf,
    cargo: f.cargo,
    situacao: f.situacao,
    unidade: f.unidade,
    data_ingresso: f.dataIngresso,
    data_aposentadoria: f.dataAposentadoria,
    tem_processo: r.processo.temProcesso,
    numero_processo:
      r.processo.temProcesso === "sim" ? r.processo.numero : "",
    observacao_processo: r.processo.observacao,
    // Campos do Produto B. Viajam no JSON que o servidor recebe e NÃO entram
    // no manifesto.csv — `manifestoCsv` escreve só `colunas_manifesto`, e o
    // manifesto é do Produto A, que não sabe de acompanhamento.
    acompanhar: numerosParaAcompanhar(r.processo.acompanhar),
    quer_aviso: d.querAviso ? "sim" : "",
    ja_tem_execucao: d.jaExecutou,
    ja_recebeu_acordo: d.jaRecebeu,
    outro_advogado: d.outroAdvogado,
    // Vazio significa "não declarou", e o verificador reprova. Então só
    // escrevemos algo quando a pessoa marcou de fato.
    ciencia_e_iniciativa: d.cienciaEIniciativa ? "sim" : "",
  };
}

export function manifestoCsv(registros: Rascunho[]): string {
  const colunas: string[] = CONTRATO.colunas_manifesto;
  const linhas = [colunas.join(",")];
  for (const r of registros) {
    const linha = linhaDoManifesto(r);
    linhas.push(colunas.map((c) => campoCsv(linha[c] ?? "")).join(","));
  }
  // \r\n porque o Excel em português abre melhor, e esta planilha vai ser
  // aberta por gente, não só por programa.
  return `${linhas.join("\r\n")}\r\n`;
}

/**
 * O recibo que a pessoa leva: o que foi registrado e o hash de cada arquivo.
 *
 * Os hashes importam por procedência: se o arquivo for trocado no caminho
 * entre o portal e o escritório, o verificador de entrega percebe.
 */
export function reciboJson(r: Rascunho): string {
  return JSON.stringify(
    {
      gerado_em: new Date().toISOString(),
      contrato: "compartilhado/contrato_entrega.json",
      pasta: soDigitos(r.pessoais.cpf),
      cadastro: linhaDoManifesto(r),
      documentos: r.documentos.map((d) => ({
        arquivo: d.nomeFinal,
        enviado_como: d.nomeOriginal,
        bytes: d.tamanho,
        sha256: d.sha256,
        cpf_encontrado_no_documento: d.cpfEncontrado,
      })),
      aviso:
        "Este recibo não é comprovante de protocolo. Nenhuma ação foi " +
        "apresentada em juízo com base neste cadastro.",
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
