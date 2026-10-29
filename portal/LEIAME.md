# Portal de coleta — como rodar

```bash
cd portal
npm install
npm run dev        # http://127.0.0.1:5173
npm run teste      # 27 testes de validação
```

Precisa de Node 20+. Nada mais: o portal não tem servidor nem banco por
enquanto.

## O que já funciona

As sete etapas da jornada de `ESPEC_PORTAL.md`, com:

* **CPF e número de processo conferidos na hora**, por dígito verificador —
  e as mesmas contas do nosso Python, travadas por vetores compartilhados
  (ver abaixo);
* **aviso, não recusa**, quando o processo não é do TRF1;
* **"não sei"** como resposta completa no processo — porque chute é pior que
  campo vazio;
* **recusa de documento ilegível na hora**, com a leitura feita **no próprio
  navegador**: o documento não sai do aparelho da pessoa para ser conferido;
* **busca do CPF dentro do documento**, que pega quem sobe o arquivo do
  cônjuge por engano;
* **rascunho salvo** a cada passo — sem guardar o conteúdo dos documentos;
* **"Próximo" travado** até a etapa estar completa, e a lista do que falta
  escrita na tela em vez de só o botão cinza;
* progresso que deixa **voltar**, nunca pular adiante.

## Modelo de procuração

Na etapa 6, o botão **Baixar modelo de procuração** gera o documento com os
dados que a pessoa já preencheu, pronto para imprimir ou salvar em PDF.

Ele existe porque receber 15 mil procurações com redações diferentes significa
conferir 15 mil documentos, cada um com um problema distinto. E porque **duas
cláusulas costumam faltar**, e as duas travam o processo depois:

* **poderes para executar** — promover cumprimento de sentença, receber e dar
  quitação, levantar valores, requerer precatório/RPV. Procuração só para
  "defesa de direitos" pode não bastar numa execução, e a falha aparece quando
  o juiz manda regularizar, com o prazo correndo;
* **poderes para substabelecer** — sem isso, cada troca de advogado trava o
  caso.

**Duas coisas que o modelo não decide, de propósito:**

1. **para quem a procuração é dada.** Direto ao advogado, ou ao sindicato que
   substabelece? É decisão jurídica pendente (pergunta 14), então a função
   recebe o caminho como parâmetro em vez de escolher;
2. **quem é o outorgado.** Nome, OAB e endereço saem como `[MARCADORES]`.
   Inventar advogado ou número de OAB num documento que vai ser assinado por
   milhares de pessoas é inaceitável, e um teste garante que continua assim.

## Termo de privacidade

No rodapé e na etapa 2. Três decisões que são de substância, não de redação:

1. **A base legal não é consentimento.** O tratamento existe para instruir e
   propor ação judicial — exercício regular de direitos em processo e execução
   de contrato. Uma caixa de "aceito os termos" sugeriria que a pessoa pode
   retirar o consentimento e apagar tudo no meio de um processo, o que **não é
   verdade**. Então o termo informa, e diz o limite com todas as letras: o que
   já está nos autos não pode ser retirado.
2. **O controlador não é inventado.** Quem é o controlador, o encarregado e o
   canal de contato depende de como escritório e sindicato se organizarem.
   Saem como marcadores, e a tela mostra aviso de pendência enquanto estiverem
   em branco. `temPendencia()` existe para barrar isso antes de ir ao ar.
3. **O termo descreve o que o sistema faz de verdade** — inclusive que, nesta
   versão, os documentos são lidos no navegador e não saem do aparelho da
   pessoa. Termo que descreve sistema inexistente é pior que termo nenhum.

## O que NÃO funciona ainda, e é dito na tela

| | Depende de |
|---|---|
| envio do código de acesso | servidor do portal |
| envio ao escritório | servidor do portal |
| OCR de foto | servidor, ou ~10 MB de modelo no navegador |

As telas **declaram** isso em vez de simular sucesso. Tela que finge que
enviou é pior que tela que avisa que ainda não envia.

## A trava contra divergência

O dígito verificador existe em dois lugares: `portal/src/lib/validacao.ts` e
`src/sindilote/processo_cnj.py`. Duplicar algoritmo é como se cria divergência
silenciosa — então os dois são testados contra `compartilhado/
vetores_validacao.json`:

```bash
npm run teste                                   # lado TypeScript
python3 ../tests/testes_conformidade_portal.py  # lado Python
```

Se divergirem, reprova de um lado ou do outro. Quem mudar um, roda os dois.

E dois erros meus que esses testes pegaram, registrados porque voltam fácil:

1. **vetor escrito à mão.** Troquei o tribunal de um número de processo e
   mantive o dígito verificador — mas o dígito depende do número inteiro.
   Agora os válidos são **gerados** pelo nosso validador, e um teste
   recalcula cada um.
2. **`BigInt` não é preciosismo.** São 20 dígitos, acima do inteiro seguro do
   JavaScript. Com `Number`, o dígito de `99999992026401340000` sai **63** em
   vez de **48** — errado só em parte dos casos, que é o pior tipo de erro.

## Marca

A paleta é neutra de propósito, com os nomes de cor em `tailwind.config.js`.
**Não há identidade visual do Sindifisco nem de escritório**, e o cabeçalho
diz "protótipo". Usar a marca de alguém antes de autorização não é economia
de tempo.
