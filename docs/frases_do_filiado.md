# As frases do motor, para revisão

Gerado por `python3 ferramentas/frases.py --gravar` — não edite à mão: para mudar uma frase, mude no código (o arquivo está em cada item) e gere de novo.

São **30** frases. Cada uma tem dois leitores: o **sindicato** (é o que fica no veredicto guardado) e o **filiado** (é o que ele lê na tela dele). O que está entre chaves muda de pessoa para pessoa.

## 1. `nucleo/motor.py`

- **Para os dois:** não há título a executar: execução cobra o que uma decisão já determinou, e sem sentença transitada não há o que cobrar

## 2. `nucleo/motor.py`

- **Sindicato lê:** a sentença foi entregue e ainda não se pôde concluir se há título. Sem essa resposta não dá para dizer que pode executar
- **Filiado lê:** a sua sentença foi entregue e ainda não deu para concluir se há título. Sem essa resposta não dá para dizer que você pode executar

## 3. `nucleo/motor.py`

- **Sindicato lê:** não se sabe se há título. Sem essa resposta não dá para dizer que pode executar
- **Filiado lê:** não sabemos se você tem título. Sem essa resposta não dá para dizer que você pode executar

## 4. `nucleo/motor.py`

- **Para os dois:** {acao.rotulo}: a ação coletiva não consta como transitada em julgado

## 5. `nucleo/motor.py`

- **Para os dois:** a resposta sobre o rol de {acao.rotulo} veio de um arquivo ENVIADO pelo sindicato, não conferido contra os autos

## 6. `nucleo/motor.py`

- **Sindicato lê:** esta pessoa está FORA do rol de substituídos, e o {tema.rotulo} — que decide exatamente se quem está fora do rol pode executar — ainda não foi julgado.{suspensao} Protocolar agora é apostar com o processo dela
- **Filiado lê:** o seu nome está FORA do rol de substituídos, e o {tema.rotulo} — que decide exatamente se quem está fora do rol pode executar — ainda não foi julgado.{suspensao} Entrar com a execução agora seria apostar com o seu processo

## 7. `nucleo/motor.py`

- **Sindicato lê:** esta pessoa não consta do rol de substituídos da ação coletiva, e há decisões extinguindo execução por ilegitimidade nesse caso
- **Filiado lê:** o seu nome não consta do rol de substituídos da ação coletiva, e há decisões extinguindo execução por ilegitimidade nesse caso

## 8. `nucleo/motor.py`

- **Sindicato lê:** {acao.rotulo}: não se sabe se esta pessoa consta do rol
- **Filiado lê:** {acao.rotulo}: ainda não sabemos se o seu nome consta do rol

## 9. `nucleo/motor.py`

- **Sindicato lê:** esta pessoa já executou este título — executar de novo criaria dois processos para a mesma dívida
- **Filiado lê:** você já executou este título — executar de novo criaria dois processos para a mesma dívida

## 10. `nucleo/motor.py`

- **Sindicato lê:** a resposta de que não houve execução anterior foi DECLARADA pela pessoa, não conferida contra base de execuções
- **Filiado lê:** a resposta de que não houve execução anterior foi DECLARADA por você, não conferida contra base de execuções

## 11. `nucleo/motor.py`

- **Sindicato lê:** não é possível afirmar que não há execução em curso para este CPF
- **Filiado lê:** não é possível afirmar que não há execução em curso em seu nome

## 12. `nucleo/motor.py`

- **Sindicato lê:** {periodo.meses_prescritos} mês(es) do período de participação já prescreveram e não entram na conta
- **Filiado lê:** {periodo.meses_prescritos} mês(es) do seu período de participação já prescreveram e não entram na conta

## 13. `nucleo/motor.py`

- **Sindicato lê:** {e.rotulo}: dispensa a liquidação prévia quando a pessoa comprova documentalmente o enquadramento e o crédito sai por cálculo aritmético simples
- **Filiado lê:** {e.rotulo}: dispensa a liquidação prévia quando você comprova com documentos o enquadramento e o crédito sai por cálculo aritmético simples

## 14. `nucleo/motor.py`

- **Sindicato lê:** {e.rotulo} é da categoria {e.categoria}, e o cargo informado é de outra carreira ({fatos.cargo})
- **Filiado lê:** {e.rotulo} é da categoria {e.categoria}, e o cargo que você informou é de outra carreira ({fatos.cargo})

## 15. `nucleo/motor.py`

- **Sindicato lê:** o cargo {fatos.cargo} não foi reconhecido, e é ele que diz se este entendimento é da carreira dela
- **Filiado lê:** o cargo que você informou ({fatos.cargo}) não foi reconhecido, e é ele que diz se este entendimento é da sua carreira

## 16. `nucleo/motor.py`

- **Sindicato lê:** a pessoa não informou o cargo, e é ele que define a categoria
- **Filiado lê:** você não informou o cargo, e é ele que define a categoria

## 17. `nucleo/motor.py`

- **Para os dois:** {e.rotulo} ainda não tem tese fixada — não há entendimento firmado em que apoiar a ação

## 18. `nucleo/motor.py`

- **Sindicato lê:** esta pessoa já tem ação própria sobre o mesmo objeto; ajuizar de novo é litispendência
- **Filiado lê:** você já tem ação própria sobre o mesmo objeto; ajuizar de novo é litispendência

## 19. `nucleo/motor.py`

- **Sindicato lê:** não se sabe se já existe ação própria
- **Filiado lê:** não sabemos se você já tem ação própria sobre o mesmo assunto

## 20. `nucleo/motor.py`

- **Sindicato lê:** {e.rotulo}: o catálogo não traz critério algum, então não há como dizer que esta pessoa se enquadra
- **Filiado lê:** {e.rotulo}: o catálogo não traz critério algum, então não há como dizer que você se enquadra

## 21. `nucleo/motor.py`

- **Para os dois:** {e.rotulo}: enquadramento a conferir contra {'; '.join(e.criterios)}

## 22. `nucleo/participacao.py`

- **Sindicato lê:** o cargo {filiado.cargo} não foi reconhecido. Pode ser a mesma carreira escrita de outro jeito — e recusar por causa disso seria tirar direito por grafia
- **Filiado lê:** o cargo que você informou ({filiado.cargo}) não foi reconhecido. Pode ser a mesma carreira escrita de outro jeito, e ninguém perde direito por grafia: o sindicato confere

## 23. `nucleo/participacao.py`

- **Sindicato lê:** a pessoa não informou o cargo, e é ele que define a categoria
- **Filiado lê:** você não informou o cargo, e é ele que define a categoria

## 24. `nucleo/participacao.py`

- **Sindicato lê:** esta ação alcança a categoria {acao.categoria}, e o cargo informado é de outra carreira ({filiado.cargo})
- **Filiado lê:** esta ação alcança a categoria {acao.categoria}, e o cargo que você informou é de outra carreira ({filiado.cargo})

## 25. `nucleo/participacao.py`

- **Para os dois:** {rotulo}: a ação não declara o período que cobre

## 26. `nucleo/participacao.py`

- **Sindicato lê:** não se sabe desde quando esta pessoa é filiada, e é isso que decide de quais ações ela faz parte
- **Filiado lê:** não sabemos desde quando vai a sua filiação, e é isso que decide de quais ações você faz parte

## 27. `nucleo/participacao.py`

- **Sindicato lê:** a filiação ({_texto(desde)} a {_texto(ate)}) não tem mês em comum com o período da ação ({acao.periodo_inicio} a {acao.periodo_fim}): {quando}
- **Filiado lê:** a sua filiação ({_texto(desde)} a {_texto(ate)}) não tem mês em comum com o período da ação ({acao.periodo_inicio} a {acao.periodo_fim}): você {quando}

## 28. `nucleo/participacao.py`

- **Sindicato lê:** esta ação tem rol de substituídos e esta pessoa não consta dele
- **Filiado lê:** esta ação tem rol de substituídos e o seu nome não consta desse rol

## 29. `nucleo/participacao.py`

- **Sindicato lê:** {rotulo} tem rol de substituídos, e não se sabe se esta pessoa consta dele
- **Filiado lê:** {rotulo} tem rol de substituídos, e ainda não sabemos se o seu nome consta desse rol

## 30. `nucleo/participacao.py`

- **Sindicato lê:** filiada de {_texto(desde)} a {_texto(ate)}, e a ação cobre {acao.periodo_inicio} a {acao.periodo_fim}
- **Filiado lê:** a sua filiação vai de {_texto(desde)} a {_texto(ate)}, e a ação cobre {acao.periodo_inicio} a {acao.periodo_fim}
