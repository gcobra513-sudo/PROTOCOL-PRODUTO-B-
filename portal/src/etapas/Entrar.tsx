/**
 * Etapa 1 — Entrar: CPF e código de acesso.
 *
 * SEM SENHA, de propósito. Criar senha é a principal causa de abandono nesse
 * tipo de cadastro, e guardar senha de 15 mil pessoas é um problema de
 * segurança que não precisamos ter.
 *
 * PARA ONDE VAI O CÓDIGO, e por que isso importa mais que parece: para o
 * e-mail que a ENTIDADE tem em cadastro, não para um e-mail digitado aqui. Se
 * a pessoa escolhesse o endereço, eu digitaria o CPF de outra pessoa, poria o
 * meu e-mail e entregaria documentos no nome dela. O código viraria enfeite.
 *
 * E a tela NÃO diz se o CPF está ou não no cadastro da entidade. Dizer
 * transformaria esta página numa consulta de filiação para quem tivesse
 * paciência de testar CPFs. A mensagem é a mesma nos dois casos; só num deles
 * sai e-mail.
 *
 * SEM SERVIDOR a etapa continua funcionando: confere o CPF e segue. O que ela
 * não faz é fingir que mandou código.
 */
import { KeyRound, Mail } from "lucide-react";
import { useState } from "react";

import { Aviso, Botao, Campo, Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import { conferirCpf, formatarCpf } from "../lib/validacao";

export function Entrar({
  cpf,
  onCpf,
  entidade,
  temToken,
  onToken,
}: {
  cpf: string;
  onCpf: (v: string) => void;
  entidade: string;
  temToken: boolean;
  onToken: (token: string) => void;
}) {
  const [tocado, setTocado] = useState(false);
  const [pedido, setPedido] = useState<api.CodigoPedido | null>(null);
  const [codigo, setCodigo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  const problemas = tocado ? conferirCpf(cpf) : [];
  const cpfOk = conferirCpf(cpf).length === 0;
  const comServidor = api.servidorLigado();

  async function pedirCodigo() {
    setErro("");
    setOcupado(true);
    try {
      setPedido(await api.pedirCodigo(entidade, cpf));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  async function entrar() {
    setErro("");
    setOcupado(true);
    try {
      const { token } = await api.conferirCodigo(entidade, cpf, codigo);
      onToken(token);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Cartao
      titulo="Entrar"
      explicacao={
        comServidor ? (
          <>
            Informe o seu CPF. Enviamos um código para o e-mail que a sua
            entidade tem em cadastro — <strong>sem criar senha</strong>.
          </>
        ) : (
          <>
            Informe o seu CPF para começar.{" "}
            <strong>Você não precisa criar senha.</strong>
          </>
        )
      }
    >
      <Campo
        rotulo="CPF"
        obrigatorio
        inputMode="numeric"
        autoComplete="off"
        placeholder="000.000.000-00"
        valor={formatarCpf(cpf)}
        onChange={(v) => {
          onCpf(formatarCpf(v));
          setPedido(null);
          setErro("");
        }}
        onBlur={() => setTocado(true)}
        problemas={problemas}
        ajuda="Conferimos o CPF na hora, antes de você continuar."
        disabled={temToken}
      />

      {!comServidor ? (
        <Aviso tom="neutro">
          <span className="flex items-start gap-2">
            <Mail className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              <strong>Este portal está sem servidor configurado.</strong> O
              cadastro é conferido aqui no seu aparelho e, no fim, você baixa
              um pacote para você mesmo guardar. Nada é transmitido.
            </span>
          </span>
        </Aviso>
      ) : temToken ? (
        <Aviso tom="bom">
          Acesso confirmado. Pode seguir para o cadastro.
        </Aviso>
      ) : !pedido ? (
        <>
          <Botao onClick={pedirCodigo} disabled={!cpfOk || ocupado}>
            <Mail className="h-4 w-4" aria-hidden="true" />
            {ocupado ? "Enviando…" : "Enviar código"}
          </Botao>
          {!entidade ? (
            <Aviso tom="alerta">
              Este endereço não identifica nenhuma entidade. Use o link que a
              sua entidade enviou — ele termina com{" "}
              <code>?entidade=…</code>.
            </Aviso>
          ) : null}
        </>
      ) : (
        <>
          <Aviso tom="neutro">
            {pedido.aviso} O código vale por {pedido.minutos} minutos.
          </Aviso>
          {pedido.codigoDoEnsaio ? (
            <Aviso tom="alerta">
              <strong>Modo ensaio:</strong> o código é{" "}
              <code>{pedido.codigoDoEnsaio}</code>. Num servidor de verdade ele
              chega por e-mail e nunca aparece nesta tela.
            </Aviso>
          ) : null}
          <Campo
            rotulo="Código recebido"
            obrigatorio
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            valor={codigo}
            onChange={(v) => setCodigo(v.replace(/\D/g, "").slice(0, 6))}
            ajuda="Seis dígitos. Confira também o spam."
          />
          <div className="flex flex-wrap gap-3">
            <Botao onClick={entrar} disabled={codigo.length !== 6 || ocupado}>
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              {ocupado ? "Conferindo…" : "Entrar"}
            </Botao>
            <Botao
              tipo="secundario"
              onClick={pedirCodigo}
              disabled={ocupado}
            >
              Enviar outro código
            </Botao>
          </div>
        </>
      )}

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
    </Cartao>
  );
}
