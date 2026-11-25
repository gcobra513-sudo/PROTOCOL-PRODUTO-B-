/**
 * Os acessos da demonstração: com que CPF FICTÍCIO entrar, dito na tela.
 *
 * Quem abre o link de uma demonstração não tem como adivinhar um CPF que
 * entre. O servidor, e só em modo de demonstração, manda a lista; aqui ela é
 * só conferida e formatada. Sem a marca de demonstração vinda do servidor,
 * não há lista — o portal não decide sozinho que algo é demonstração.
 */
import { enderecoDaArea } from "./entrada";
import type { Entidade } from "./envio";

export interface AcessoDaDemo {
  quem: string;
  /** Já formatado, como a pessoa vai digitar. */
  cpf: string;
  area: "cadastro" | "painel";
  gestor: boolean;
}

export function acessosDaDemonstracao(e: Entidade | null): AcessoDaDemo[] {
  if (!e?.demonstracao || !Array.isArray(e.acessos_da_demonstracao)) return [];
  const saida: AcessoDaDemo[] = [];
  for (const a of e.acessos_da_demonstracao) {
    if (!a || !/^\d{11}$/.test(a.cpf) || !a.quem) continue;
    const c = a.cpf;
    saida.push({
      quem: a.quem,
      cpf: `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}`,
      area: a.area === "painel" ? "painel" : "cadastro",
      gestor: a.area === "painel",
    });
  }
  return saida;
}

/** Uma parada do roteiro: o que abrir, com que CPF, o que mostrar e o que
 *  dizer enquanto mostra. */
export interface Parada {
  id: "painel" | "filiado" | "primeiro-acesso";
  titulo: string;
  /** Quem a pessoa finge ser nesta parada. */
  quem: string;
  cpf: string;
  link: string;
  botao: string;
  /** O que apontar na tela, na ordem. */
  mostrar: string[];
  /** A frase que resume a parada para quem está assistindo. */
  falar: string;
}

/**
 * O roteiro de uma apresentação, montado a partir dos acessos que o
 * servidor mandou.
 *
 * A ORDEM É A DA CONVERSA COM UMA DIRETORIA: primeiro o que o sindicato
 * ganha (o painel), depois o que o filiado vê, e por último como é chegar
 * pela primeira vez. Começar pelo cadastro do filiado, como a demonstração
 * fazia, punha o presidente do sindicato para assistir a um formulário.
 *
 * PARADA SEM ACESSO NÃO EXISTE: o botão levaria a um portão pedindo um CPF
 * que ninguém na sala tem.
 */
export function roteiroDaDemonstracao(acessos: AcessoDaDemo[], apelido: string): Parada[] {
  const gestor = acessos.find((a) => a.gestor);
  const filiados = acessos.filter((a) => !a.gestor);
  const novato = filiados.find((a) => /n[ãa]o entrou/i.test(a.quem));
  const filiado = filiados.find((a) => a !== novato);
  const saida: Parada[] = [];
  if (gestor) {
    saida.push({
      id: "painel",
      titulo: "O painel do sindicato",
      quem: gestor.quem,
      cpf: gestor.cpf,
      link: enderecoDaArea("painel", apelido),
      botao: "Abrir o painel do sindicato",
      mostrar: [
        "Os quatro números do topo: quantos filiados há na base, com quantos o sindicato não consegue falar, quem já se cadastrou e quem ainda não.",
        "“O que resolver primeiro”: o que está segurando mais gente, e de quem é a vez — do sindicato, do filiado ou do tribunal.",
        "A aba Filiados: a lista nome por nome, com os contatos, que sai em planilha. Toque em “Já pode” para ver quem tem tudo pronto.",
        "A aba Documentos para ler: as fotos que a máquina não leu e esperam uma pessoa.",
        "A aba Pergunte ao Proto: toque em “Com quantos eu não consigo falar?”.",
      ],
      falar:
        "O sindicato só enviou a planilha que já tinha. No mesmo dia ficou sabendo com quem não consegue falar e o que precisa resolver primeiro.",
    });
  }
  if (filiado) {
    saida.push({
      id: "filiado",
      titulo: "A área do filiado",
      quem: filiado.quem,
      cpf: filiado.cpf,
      link: enderecoDaArea("area", apelido),
      botao: "Abrir a Minha área do filiado",
      mostrar: [
        "A entrada sem senha: CPF e um código de seis números.",
        "A Minha área: os documentos que chegaram, as ações e os processos, tudo numa tela.",
        "Minhas ações: este filiado tem “Caminho aberto, já conferido” na ação de exemplo, com o período dele e o que ainda falta para o valor.",
        "Pergunte ao Proto: toque em “Meus documentos chegaram?”.",
      ],
      falar:
        "O filiado vê sozinho o que antes perguntava por telefone na sede: se o documento chegou, em que ação está e o que falta.",
    });
  }
  if (novato) {
    saida.push({
      id: "primeiro-acesso",
      titulo: "O primeiro acesso de um filiado",
      quem: novato.quem,
      cpf: novato.cpf,
      link: enderecoDaArea("cadastro", apelido),
      botao: "Abrir o cadastro",
      mostrar: [
        "O cadastro em passos curtos, feito para o celular.",
        "Os dados que o sindicato já tinha vêm preenchidos: a pessoa confere, não digita de novo.",
        "O documento pode ser uma foto do papel.",
      ],
      falar:
        "Quem nunca entrou faz o cadastro pelo celular, sem criar senha, conferindo o que o sindicato já sabia.",
    });
  }
  return saida;
}
