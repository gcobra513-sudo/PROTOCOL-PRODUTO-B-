/**
 * MINHA ÁREA: a primeira tela de quem entrou.
 *
 * Antes, quem entrava caía direto num formulário de seis etapas, e as outras
 * áreas — ações, processos, perguntas — ficavam num menu lateral que muita
 * gente não abre. Aqui está tudo que é da pessoa, numa tela só, com um botão
 * grande para cada coisa: quem tem pouca prática com computador não precisa
 * descobrir onde as coisas moram.
 *
 * ELA NÃO DÁ VEREDICTO. Resume o que as outras áreas dizem e manda para
 * elas; as frases vêm de `lib/minhaArea.ts`, que tem os testes disso.
 */
import { FileText, Gavel, ListChecks, MessagesSquare } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Aviso, Botao, Cartao, cn } from "../componentes/ui";
import * as api from "../lib/envio";
import {
  cartaoDasAcoes,
  cartaoDoCadastro,
  cartaoDosProcessos,
  oQueFaltaVoce,
  PERGUNTAS_AO_PROTO,
  primeiroNome,
  type CartaoDaArea,
  type Consulta,
} from "../lib/minhaArea";
import { sessaoMorreu } from "../lib/sessao";
import { Portao } from "./Portao";

function Bloco({
  icone,
  titulo,
  cartao,
  onIr,
}: {
  icone: ReactNode;
  titulo: string;
  cartao: CartaoDaArea;
  onIr: (tela: api.Tela) => void;
}) {
  return (
    <section className="flex flex-col rounded-xl bg-carta p-5 shadow-cartao sm:p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-lilas text-acento">
          {icone}
        </span>
        <h2 className="text-xl font-semibold text-tinta">{titulo}</h2>
      </div>
      <p
        className={cn(
          "mt-4 flex-1 text-[17px] leading-relaxed",
          cartao.estado === "alerta" ? "text-alerta" : "text-tinta/80",
        )}
      >
        {cartao.frase}
      </p>
      <div className="mt-5">
        <Botao onClick={() => onIr(cartao.tela)}>{cartao.acao}</Botao>
      </div>
    </section>
  );
}

export function MinhaArea({
  entidade,
  token,
  onToken,
  onSessaoMorta,
  onIr,
  onPerguntar,
}: {
  entidade: string;
  /** A sessão é do `App`, e vale em todas as áreas: vazio = ninguém entrou. */
  token: string;
  onToken: (token: string, cpf: string) => void;
  onSessaoMorta: () => void;
  onIr: (tela: api.Tela) => void;
  /** Abre o Proto já com a pergunta feita. */
  onPerguntar: (pergunta: string) => void;
}) {
  const [cadastro, setCadastro] = useState<Consulta<api.MeuCadastro>>(null);
  const [acoes, setAcoes] = useState<Consulta<api.MinhasAcoes>>(null);
  const [processos, setProcessos] = useState<Consulta<api.MeusProcessos>>(null);

  useEffect(() => {
    if (!token) return;
    // CADA CONSULTA FALHA SOZINHA: se os processos não respondem, o cartão
    // deles diz isso e os outros dois continuam valendo. Só a sessão morta
    // derruba a tela inteira.
    const tentar = <T,>(pedido: Promise<T>, guardar: (v: Consulta<T>) => void) =>
      void pedido.then(guardar).catch((e) => {
        if (sessaoMorreu(e)) onSessaoMorta();
        else guardar("erro");
      });
    tentar(api.meuCadastro(token), setCadastro);
    tentar(api.minhasAcoes(token), setAcoes);
    tentar(api.meusProcessos(token), setProcessos);
  }, [token]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Minha área"
        explicacao="Entre para ver o que é seu: seus documentos, suas ações, seus processos. Sem senha: o código vai para o e-mail que o seu sindicato tem em cadastro."
        onToken={onToken}
      />
    );
  }

  const nome = primeiroNome(
    acoes && acoes !== "erro" ? acoes.filiado : "",
  );
  const falta = oQueFaltaVoce(acoes);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta sm:text-3xl">
          {nome ? `Olá, ${nome}.` : "Olá."}
        </h1>
        <p className="mt-1 text-[17px] text-tinta/70">
          Aqui está tudo que é seu neste portal.
        </p>
      </div>

      {falta.length ? (
        <Cartao
          titulo="O que falta você fazer"
          explicacao="Só o que depende de você. O que depende do sindicato ou do tribunal aparece em Minhas ações."
        >
          <ul className="list-disc space-y-2 pl-5 text-[17px] leading-relaxed text-tinta">
            {falta.slice(0, 5).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {falta.length > 5 ? (
            <p className="text-sm text-tinta/70">
              E mais {falta.length - 5}. A lista inteira está em Minhas ações.
            </p>
          ) : null}
          <Botao onClick={() => onIr("cadastro")}>Enviar o que falta</Botao>
        </Cartao>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Bloco
          icone={<FileText className="h-5 w-5" aria-hidden="true" />}
          titulo="Meu cadastro e documentos"
          cartao={cartaoDoCadastro(cadastro)}
          onIr={onIr}
        />
        <Bloco
          icone={<ListChecks className="h-5 w-5" aria-hidden="true" />}
          titulo="Minhas ações"
          cartao={cartaoDasAcoes(acoes)}
          onIr={onIr}
        />
        <Bloco
          icone={<Gavel className="h-5 w-5" aria-hidden="true" />}
          titulo="Meus processos"
          cartao={cartaoDosProcessos(processos)}
          onIr={onIr}
        />
        <section className="flex flex-col rounded-xl bg-carta p-5 shadow-cartao sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-roxo text-white">
              <MessagesSquare className="h-5 w-5" aria-hidden="true" />
            </span>
            <h2 className="text-xl font-semibold text-tinta">Pergunte ao Proto</h2>
          </div>
          <p className="mt-4 text-[17px] leading-relaxed text-tinta/80">
            O assistente do portal. Responde na hora, com o que está no seu
            cadastro.
          </p>
          <div className="mt-4 flex flex-1 flex-col gap-2">
            {PERGUNTAS_AO_PROTO.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => onPerguntar(p)}
                className="rounded-lg bg-lilas px-4 py-3 text-left text-base font-medium text-acento hover:bg-lilas/70"
              >
                {p}
              </button>
            ))}
          </div>
        </section>
      </div>

      <Aviso tom="neutro">
        Isto não é parecer e não promete dinheiro. A movimentação dos
        processos não é intimação e não serve para contar prazo.
      </Aviso>
    </div>
  );
}
