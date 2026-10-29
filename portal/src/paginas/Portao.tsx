/**
 * O portão, para as telas de consulta.
 *
 * É o MESMO portão do cadastro — CPF, código de seis dígitos no e-mail que a
 * entidade tem cadastrado, sem senha — e existe separado de `E1Entrar`
 * porque aquele é um passo do assistente de sete etapas, com o estado do
 * rascunho dentro. Aqui não há rascunho: há uma pessoa querendo ver o que já
 * existe.
 *
 * O que ele NÃO faz, de propósito: não diz se o CPF está no rol. Pedir
 * código devolve a mesma coisa para quem está e para quem não está — a
 * diferença é que num dos casos sai e-mail. Qualquer outra escolha
 * transformaria esta tela numa consulta de filiação.
 */
import { useState } from "react";

import { Aviso, Botao, Campo, Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import { conferirCpf, formatarCpf } from "../lib/validacao";

export function Portao({
  entidade,
  titulo,
  explicacao,
  onToken,
}: {
  entidade: string;
  titulo: string;
  explicacao: string;
  onToken: (token: string, cpf: string) => void;
}) {
  const [cpf, setCpf] = useState("");
  const [codigo, setCodigo] = useState("");
  const [pedido, setPedido] = useState<api.CodigoPedido | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const problemas = cpf ? conferirCpf(cpf) : [];
  const podePedir = problemas.length === 0 && cpf.length > 0 && !ocupado;

  async function pedir() {
    setErro("");
    setOcupado(true);
    try {
      setPedido(await api.pedirCodigo(entidade, cpf));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível pedir o código");
    } finally {
      setOcupado(false);
    }
  }

  async function conferir() {
    setErro("");
    setOcupado(true);
    try {
      const { token } = await api.conferirCodigo(entidade, cpf, codigo);
      onToken(token, cpf);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "código não aceito");
    } finally {
      setOcupado(false);
    }
  }

  if (!api.servidorLigado()) {
    return (
      <Cartao titulo={titulo}>
        <Aviso tom="alerta">
          Esta página precisa do servidor, e ele não está configurado neste
          endereço.
        </Aviso>
      </Cartao>
    );
  }

  if (!entidade) {
    return (
      <Cartao titulo={titulo}>
        <Aviso tom="alerta">
          O link está sem a entidade. Use o endereço que o seu sindicato
          enviou — ele termina com <code>?entidade=...</code>.
        </Aviso>
      </Cartao>
    );
  }

  return (
    <Cartao titulo={titulo} explicacao={explicacao}>
      <Campo
        rotulo="Seu CPF"
        obrigatorio
        inputMode="numeric"
        placeholder="000.000.000-00"
        valor={formatarCpf(cpf)}
        onChange={(v) => setCpf(formatarCpf(v))}
        problemas={problemas}
      />

      {pedido ? (
        <>
          <Aviso tom="bom">
            <p>{pedido.aviso}</p>
            <p className="mt-1">
              O código vale {pedido.minutos} minutos.
            </p>
            {pedido.codigoDoEnsaio ? (
              <p className="mt-2">
                <strong>Demonstração:</strong> o código é{" "}
                <code>{pedido.codigoDoEnsaio}</code>. Num servidor de verdade
                ele só chega por e-mail.
              </p>
            ) : null}
          </Aviso>
          <Campo
            rotulo="Código que chegou no seu e-mail"
            obrigatorio
            inputMode="numeric"
            placeholder="000000"
            valor={codigo}
            onChange={(v) => setCodigo(v.replace(/\D/g, "").slice(0, 6))}
          />
          <Botao
            tipo="principal"
            disabled={codigo.length !== 6 || ocupado}
            onClick={() => void conferir()}
          >
            Entrar
          </Botao>
        </>
      ) : (
        <Botao tipo="principal" disabled={!podePedir} onClick={() => void pedir()}>
          {ocupado ? "Enviando..." : "Receber código por e-mail"}
        </Botao>
      )}

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      <Aviso tom="neutro">
        Não há senha. O código vai para o e-mail que o seu sindicato tem em
        cadastro — é isso que garante que ninguém entra no seu lugar.
      </Aviso>
    </Cartao>
  );
}
