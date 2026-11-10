# A ficha a partir do pedido

Quando o dono pede em texto livre, a ficha DEV nasce antes da lane.

1. Rode `harness.py fichas nova <slug>`, com o slug em minúsculas e algarismos, separados por hífen, e abra o arquivo que ele imprime.
2. Preencha os onze campos, na ordem, a partir do pedido; o que o pedido não diz, deixe `—` ou marque como pergunta ao dono.
   - **Marco:** o marco da passagem a que o pedido pertence, ou `—`.
   - **Depende:** as fichas e pendências de que o pedido precisa, separadas por vírgula, ou `—`.
   - **Tamanho:** `P`, `M` ou `G: <motivo>`.
   - **Prioridade:** `urgente` quando o pedido diz que não espera a fila; `normal` no resto.
   - **Contexto:** `sim` só quando o Context Packet não basta para entender o pedido; `não` no resto.
   - **Fonte:** os IDs da passagem de que o pedido vem, e os arquivos por link.
   - **Objetivo:** o resultado, não a solução, em até duas frases.
   - **Escopo:** o que entra, um item por linha.
   - **Fora:** o que fica para outra ficha, com o ID dela, ou `—`.
   - **Restrições:** as RA e os RNF que valem para o pedido.
   - **Aceite:** o que o dono vê funcionando, um item por linha.
3. Rode `harness.py fichas` e confira que a ficha aparece como `pronta`. Se vier `fora da forma (...)` ou `espera ...`, corrija o campo que a linha aponta.
