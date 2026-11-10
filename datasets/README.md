# Instantâneo público de referência

O arquivo `bronze-2026-11-10.zip` contém os 169 envelopes públicos das APIs de Dados Abertos utilizados na demonstração, com os bytes originais preservados. `SHA256SUMS` permite verificar o pacote.

São dados publicados pelas instituições, sem dados de clientes, consentimentos ou credenciais. A coleta de referência ocorreu em 10/11/2026; o conteúdo não representa uma cotação atual. Os direitos e condições dos dados continuam pertencendo às respectivas fontes.

Para reproduzir, extraia o ZIP em `data/replay-source`, importe essa pasta com `observatory import`, execute `verify` e `build`. O workflow Pages faz essa sequência sem depender da máquina de origem ou de rede com os bancos.
