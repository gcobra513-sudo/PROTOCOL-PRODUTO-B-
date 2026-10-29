# Referência de UI do portal — guardada, não implementada

Modelo de interface escolhido pelo cliente, recebido em 26/10/2026. **Nada
aqui foi implementado ainda**: a decisão foi terminar a máquina primeiro e
atacar o portal depois.

## O que foi definido

Um **formulário multietapas** (multistep form) em React, com:

- **stack**: TypeScript + Tailwind CSS + shadcn/ui, componentes em
  `components/ui/`
- **animação**: `framer-motion` nas transições entre etapas e nos itens
- **ícones**: `lucide-react`
- **indicador de progresso** no topo, com os passos clicáveis apenas para
  voltar (não dá para pular adiante)
- **validação por etapa**: o botão "Próximo" só habilita quando os campos
  obrigatórios daquela etapa estão preenchidos
- **toast** de confirmação ao enviar (`sonner`)

## Componentes shadcn necessários

`button`, `input`, `label`, `card`, `radio-group`, `checkbox`, `select`,
`textarea`

## Dependências npm

```
clsx  tailwind-merge  class-variance-authority  lucide-react
@radix-ui/react-slot  @radix-ui/react-label  @radix-ui/react-radio-group
@radix-ui/react-checkbox  @radix-ui/react-select
framer-motion  sonner
```

## Observação sobre o modelo de exemplo

O código de referência vem de um formulário de *onboarding de cliente de
site* (nome, profissão, orçamento, estilo visual). **A estrutura serve; o
conteúdo não.** As etapas do nosso portal são as sete da jornada definida em
`ESPEC_PORTAL.md`:

| Etapa | Conteúdo | Validação obrigatória |
|---|---|---|
| 1 | Entrar (CPF + código por e-mail/SMS) | CPF com dígito verificador |
| 2 | Ver o que vai ser pedido | — |
| 3 | Dados pessoais | CPF, endereço completo |
| 4 | Situação funcional | cargo, situação, datas |
| 5 | **Processo de origem** | **dígito verificador do número** + aviso se não é TRF1 + opção "não sei" |
| 6 | Documentos | **OCR obrigatório**; recusa se o texto não for legível; CPF procurado no documento |
| 7 | Declarações | quatro perguntas + ciência e iniciativa |

## O que o modelo de referência NÃO cobre, e é obrigatório

Quando chegar a hora de implementar, estes pontos vêm de `ESPEC_PORTAL.md` e
não estão no exemplo:

1. **upload de arquivo com OCR e recusa** — o exemplo não tem upload nenhum;
2. **validação de CPF e de número de processo** com dígito verificador. O
   algoritmo do processo está pronto e testado em
   `src/sindilote/processo_cnj.py`, e precisa ser portado para TypeScript (ou
   chamado por API);
3. **salvar rascunho e continuar depois** — o exemplo guarda estado só em
   memória, e perder o preenchimento no meio é a principal causa de abandono;
4. **opção "não sei"** nos campos de processo e declarações;
5. **exportação** em `manifesto.csv` + `manifesto.json` com SHA-256, mais
   pastas por CPF com nomes fixos de arquivo;
6. **modelo de procuração** para baixar, com poderes de executar e de
   substabelecer;
7. **termo de privacidade** e canal para direitos do titular.

## Decisão de arquitetura a tomar antes de começar

Onde ficam as validações. Duas opções:

- **portar para TypeScript**: validação instantânea no navegador, sem rede.
  Custo: o algoritmo passa a existir em dois lugares e pode divergir.
- **expor como API** do nosso lado: uma fonte só da verdade, e o portal
  consulta. Custo: depende de rede e de o serviço estar no ar.

A segunda é melhor para consistência e é o que eu recomendaria — com a
primeira como validação de formato só (tamanho, caracteres), para a pessoa não
esperar a rede a cada dígito.
