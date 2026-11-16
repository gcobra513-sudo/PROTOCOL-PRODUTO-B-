/**
 * O PROTO DO FILIADO: a conversa em que ele pergunta o que perguntaria por
 * telefone — em que processo estou, mudou alguma coisa, meus documentos
 * chegaram, o que falta.
 *
 * NÃO É UMA PESSOA E NÃO É UMA IA GENERATIVA, e a tela diz isso antes de
 * qualquer pergunta. Quem responde é o servidor, com o que já está no
 * cadastro dela; a pergunta não leva CPF e não fica guardada.
 */
import { Conversa } from "../componentes/Conversa";
import { Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import { Portao } from "./Portao";

const ABERTURA = [
  "Olá. Sou o Proto, o assistente automático do portal: respondo na hora, com o que está no seu cadastro.",
  "Não sou uma pessoa e não dou parecer. Escolha uma pergunta abaixo, ou escreva a sua.",
];

const SUGESTOES_INICIAIS = [
  "Em quais processos eu estou?",
  "Mudou alguma coisa nos meus processos?",
  "Meus documentos chegaram?",
  "O que falta eu fazer?",
  "Meus dados estão certos?",
];

export function Atendimento({
  entidade,
  token,
  onToken,
  onSessaoMorta,
  perguntaInicial = "",
  onPerguntaFeita,
}: {
  entidade: string;
  /** A sessão é do `App`, e vale em todas as áreas: vazio = ninguém entrou. */
  token: string;
  onToken: (token: string, cpf: string) => void;
  /** O servidor não aceita mais esta sessão: a tela volta ao portão. */
  onSessaoMorta: () => void;
  /** Pergunta que veio escolhida da Minha área: é feita ao abrir. */
  perguntaInicial?: string;
  onPerguntaFeita?: () => void;
}) {
  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Pergunte ao Proto"
        explicacao="Pergunte pelos seus processos, pelos seus documentos e pelo que falta. Para responder sobre você, precisamos confirmar que é você."
        onToken={onToken}
      />
    );
  }

  return (
    <Cartao
      titulo="Pergunte ao Proto"
      explicacao="O assistente automático do portal: responde com o que está no seu cadastro. A sua pergunta não fica guardada."
    >
      <Conversa
        abertura={ABERTURA}
        sugestoesIniciais={SUGESTOES_INICIAIS}
        perguntar={(p) => api.perguntar(token, p)}
        consultando="Consultando o seu cadastro…"
        onSessaoMorta={onSessaoMorta}
        perguntaInicial={perguntaInicial}
        onPerguntaFeita={onPerguntaFeita}
      />
    </Cartao>
  );
}
