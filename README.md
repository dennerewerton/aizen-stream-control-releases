# Aizen Stream Control

Aplicativo Windows para lives, lançamento manual de kills, filas Free Fire e sorteios multi-plataforma.

As opcoes gerais ficam na aba `Geral`. `Kills FF` serve para lancar kills manualmente no Jarvis e mostra um overlay interno de ranking na lateral direita. `Fila FF` sincroniza a fila em tempo real com o site. O app pode rodar em varios PCs ao mesmo tempo e tem atualizacao automatica por manifesto remoto.

## Instalar

Gere o instalador:

```powershell
.\build_installer.ps1
```

Arquivos gerados:

```text
dist\AizenStreamControl.exe
dist\AizenStreamControlSetup.exe
```

Use `AizenStreamControlSetup.exe` para instalar. Ele instala por usuario em:

```text
%LOCALAPPDATA%\Programs\Aizen Stream Control
```

Isso evita pedir administrador e permite que o auto-update substitua o executavel ao abrir.

Para conferir a versao do codigo fonte:

```powershell
python freefire_kill_sender.py --version
```

## Rodar em desenvolvimento

```powershell
python -m pip install -r requirements.txt
python freefire_kill_sender.py --gui
```

## Multi-PC

Para usar Fila FF em varios PCs, todos devem usar:

- a mesma `URL base do Jarvis` ou os mesmos endpoints de `Kills FF` e `Fila FF`;
- a mesma `Sala`, por exemplo `principal`;
- nomes diferentes em `Geral > Nome deste PC`.

Quando um PC altera a Fila FF, ele envia o estado para o painel. Os outros PCs leem o painel no intervalo configurado em `Ler fila a cada` e atualizam a tela.

Na aba `Geral`, o card `Jarvis FF` permite informar a URL base do site, preencher automaticamente `/api/freefire-kills` e `/api/freefire-queue`, e testar se Kills/Fila respondem.
Pode colar a raiz do site ou a URL do painel administrativo, como `https://seu-jarvis.squareweb.app/admin`; o app deriva os endpoints na raiz `/api`. Se a URL base estiver preenchida e algum endpoint estiver vazio, salvar ou testar tambem completa o endpoint ausente automaticamente.

## Fila FF

Na aba `Fila FF`, o programa controla a fila de jogadores do Free Fire em tempo real com o Jarvis.

Campos principais:

- `URL da fila/Jarvis`: endpoint que recebe e devolve a fila;
- `Sala`: separa filas diferentes, por exemplo `principal`, `x1`, `squad`;
- `Ler fila a cada`: intervalo para buscar alteracoes feitas em outro PC ou no site;
- `Sincronizar automaticamente`: envia mudancas quando a fila e editada.

Cada linha tem:

- `Nick`;
- `Observação`;
- `Status`: `Na fila`, `Chamado`, `Jogando` ou `Concluido`.

Botoes principais:

- `Adicionar jogador`;
- `Chamar próximo`;
- `Marcar jogando`;
- `Finalizar partida`;
- `Enviar agora`;
- `Buscar Jarvis`;
- `Limpar`.

## Contrato do endpoint

URLs recomendadas no Jarvis:

- Kills FF: `/api/freefire-kills`
- Fila FF: `/api/freefire-queue`

Quando o Jarvis estiver com `FREEFIRE_KILLS_TOKEN` ou `JARVIS_FREEFIRE_KILLS_TOKEN`, preencha o mesmo valor no app em `Geral > Token Jarvis`. O app envia esse valor no header:

```http
X-Aizen-Token: seu-token
X-Aizen-Client-Name: PC LIVE
X-Aizen-Room: principal
```

Para `Kills FF`, o botão `Salvar` envia um snapshot completo do que está no app. A URL configurada pode ser `/api/freefire-kills`; o app deriva automaticamente `/api/freefire-kills/action` e tenta substituir o rank diário e o rank geral sem somar com valores antigos do site:

```json
{
  "source": "aizen-stream-control",
  "mode": "kills_snapshot",
  "action": "replace",
  "scope": "both",
  "app_version": "2.6.77",
  "room": "principal",
  "client_id": "id-unico-do-pc",
  "client_name": "PC LIVE",
  "daily_ranking": [
    { "name": "AIZEN OFC", "kills": 7 }
  ],
  "global_ranking": [
    { "name": "AIZEN OFC", "kills": 7 }
  ]
}
```

Se o Jarvis ainda não aceitar `action: "replace"`, o app usa fallback seguro: zera `daily` e `general` e recria os jogadores com ação `set`, evitando duplicar ou somar com o ranking que já estava no site. As ações administrativas continuam usando `scope` `daily`, `general` ou `both`. A resposta pode devolver o ranking atualizado:

```json
{
  "ok": true,
  "room": "principal",
  "updated_by": "PC LIVE",
  "updated_at": "2026-06-22T19:30:00",
  "revision": 1,
  "players": [
    { "name": "AIZEN OFC", "kills": 7 }
  ]
}
```

Tambem sao aceitos campos equivalentes como `nick`, `nickname`, `username`, `participant`, `player`, `jogador`, `apelido`, `k`, `kill`, `score`, `points` ou `abates`.

Para a aba `Fila FF`, o mesmo endpoint ou outro endpoint pode aceitar `mode: "ff_queue"`.

Payload enviado:

```json
{
  "source": "aizen-stream-control",
  "mode": "ff_queue",
  "app_version": "2.6.0",
  "room": "principal",
  "client_id": "id-unico-do-pc",
  "client_name": "PC LIVE",
  "updated_by": "PC LIVE",
  "updated_at": "2026-06-22T19:30:00",
  "queue": [
    {
      "position": 1,
      "name": "AIZEN OFC",
      "note": "squad",
      "status": "Na fila"
    }
  ]
}
```

Resposta esperada no `GET`:

```json
{
  "ok": true,
  "room": "principal",
  "updated_by": "PC LIVE",
  "updated_at": "2026-06-22T19:30:00",
  "revision": 1,
  "queue": [
    {
      "position": 1,
      "name": "AIZEN OFC",
      "note": "squad",
      "status": "Na fila"
    }
  ]
}
```

Na fila, o app tambem entende aliases comuns como `username`, `participant`, `playerName`, `room`, `sala`, `quantity`, `qty`, `count`, e status em portugues ou ingles como `waiting`, `called`, `playing`, `done` e `finished`.

## Aparencia e tema

Na aba `Aparência`, o usuario pode personalizar o visual do app:

- trocar a imagem/avatar principal;
- escolher presets como `Aizen Red`, `Obsidian Gold`, `Neon Cyan` e `Graphite Pro`;
- editar manualmente as cores de fundo, cards, campos, bordas, texto, destaque e perigo;
- salvar e reabrir automaticamente para aplicar o tema em toda a interface.

As preferencias ficam salvas no `config.json`, na chave `ui_theme`. Para a imagem ficar perfeita, use PNG ou JPG quadrado.

## Livepix

A aba `Livepix` integra a API oficial da Livepix ao Aizen Stream Control.

Recursos incluidos:

- OAuth2 por `client_credentials`;
- teste de conta e sincronizacao de pagamentos/mensagens;
- webhook local para receber eventos em tempo real;
- historico local em `livepix_events.json`;
- painel com total recebido, quantidade de eventos, top apoiador e carteira;
- meta de apoio com overlay dedicado para OBS;
- geracao de checkout de pagamento e mensagem paga;
- criacao de plano e checkout de assinatura recorrente;
- consulta de assinaturas, recompensas, recompensas concedidas, moedas, transacoes e recebiveis;
- ranking top 10 de apoiadores;
- anuncio opcional dos eventos Livepix no `Chat Ao Vivo` e no overlay de chat;
- exportacao de pagina publica HTML com meta, top apoiadores e ultimos eventos;
- controles de alerta: pular, reexibir, autoplay on/off;
- evento de teste para validar dashboard e overlay sem depender de pagamento real.

Para usar:

1. Crie uma aplicacao nas configuracoes da Livepix.
2. Preencha `Client ID`, `Client Secret` e escopos na aba `Livepix`.
3. Clique em `Testar e sincronizar`.
4. Para tempo real, inicie o webhook local e copie a URL gerada para configurar na Livepix. Se o app estiver em outro computador ou atras de NAT, exponha a porta com um tunel HTTPS e use essa URL publica.

## Atualizacao automatica

No programa, a aba `Geral` tem o campo `Manifesto de atualização`. Quando abrir, o app compara a versao remota com a versao instalada. Se a remota for maior, ele baixa o novo `AizenStreamControl.exe`, substitui o executavel atual e reabre sozinho.

Formato do manifesto:

```json
{
  "version": "2.6.41",
  "notes": "Corrige falha ao abrir a Fila FF quando o tema reaproveitava o texto Medalhas como cor.",
  "windows": {
    "portable_url": "https://github.com/dennerewerton/aizen-stream-control-releases/releases/download/v2.6.41/AizenStreamControl.exe",
    "sha256": "hash-sha256-do-exe"
  }
}
```

Para gerar o manifesto depois de publicar o exe:

```powershell
.\build_update_manifest.ps1 -Version "2.6.41" -DownloadUrl "https://github.com/dennerewerton/aizen-stream-control-releases/releases/download/v2.6.41/AizenStreamControl.exe"
```

Envie para o servidor:

- `dist\AizenStreamControl.exe`
- `dist\updates.json`

Depois cole a URL do `updates.json` no campo `Manifesto de atualização`.

Para publicar direto no GitHub Releases, configure uma vez um token com permissao de escrita no repositorio `dennerewerton/aizen-stream-control-releases`:

```powershell
$env:GITHUB_TOKEN="cole_o_token_aqui"
.\publish_github_release.ps1 -Version "2.6.52" -Notes "Faz o seletor Diario/Geral do Kills FF trocar a tabela manual e o overlay de ranking juntos."
```

Esse script cria ou atualiza a release informada, envia `AizenStreamControl.exe` e `updates.json`, e marca a release como latest para todos os apps instalados receberem a atualizacao.

### Revisão 2.6.52

A versão `2.6.52` faz o seletor `Diario/Geral` da aba `Kills FF` trocar também a tabela manual abaixo, usando o ranking correspondente recebido do Jarvis. O seletor da esquerda agora acompanha a aba de ranking da direita e mantém buffers separados para edição diária e geral.

### Revisão 2.6.51

A versão `2.6.51` simplifica o card `Kills FF`: remove o `Rank Jarvis` interno e remove a opção `Ambos`. O lançamento manual agora escolhe diretamente entre as abas `Diario` e `Geral`, enviando as kills somente para o rank selecionado.

### Revisão 2.6.50

A versão `2.6.50` melhora a aba `Kills FF`: o card principal agora tem abas internas para alternar entre `Lançar Kills` e `Rank Jarvis`, com seleção `Diário`/`Geral` no ranking igual ao overlay. O botão `Adicionar jogador` agora abre uma janela dedicada para informar nick, kills e escopo antes de inserir a linha.

### Revisão 2.6.49

A versão `2.6.49` deixa o app mais leve para uso em live: Kills FF e Fila FF usam polling adaptativo, leituras automáticas sem mudança não redesenham tabelas nem alteram textos de status, o Overlay FF não faz leitura remota contínua sem necessidade e a aba `Eventos` foi renomeada para `Logs` para concentrar mensagens técnicas fora das telas principais.

### Revisão 2.6.48

A versão `2.6.48` melhora a estabilidade quando o Windows falha ao resolver `jarvis-da-shopee.squareweb.app`: o app guarda o último ranking válido em cache local, mostra esse ranking no overlay se o DNS cair e agenda uma nova tentativa automática em seguida. Isso evita que o card da lateral direita fique vazio durante oscilações de DNS/internet.

### Revisão 2.6.47

A versão `2.6.47` reforça o overlay da lateral direita em `Kills FF`: o card agora tem botão `Atualizar rank`, mostra o status da leitura no próprio overlay e tenta carregar o ranking ao abrir mesmo quando a URL precisa ser derivada da URL base do Jarvis. Se algum campo da tela impedir salvar a configuração, a leitura usa a última configuração válida em vez de parar silenciosamente.

### Revisão 2.6.46

A versão `2.6.46` corrige o overlay que ainda ficava vazio: o `Overlay FF` agora monta o rank usando o ranking real carregado do Jarvis, priorizando o `Rank do Dia` e usando o `Rank Geral` como fallback. A aba `Kills FF` também faz uma leitura inicial do ranking ao abrir o app e volta a preservar corretamente a opção `Sincronizar automaticamente`.

### Revisão 2.6.45

A versão `2.6.45` corrige a leitura real do ranking do Jarvis: quando `/api/freefire-kills` devolver apenas `players`, o app busca automaticamente `/api/freefire-kills/rank` para carregar `Rank do Dia` e `Rank Geral`. Isso faz a lateral direita de `Kills FF` preencher o overlay com os mesmos dados separados que aparecem no site.

### Revisão 2.6.44

A versão `2.6.44` corrige o overlay de ranking em `Kills FF` para respeitar os dados separados do Jarvis entre `Rank do Dia` e `Rank Geral`, sem preencher uma aba com a mesma prévia da outra. O overlay também ficou maior, removendo estatísticas totais e a observação inferior.

### Revisão 2.6.43

A versão `2.6.43` troca a lateral direita de `Kills FF`: em vez de mostrar link do site, ela exibe um overlay interno de ranking com colunas de rank, jogador e kills, além de abas para alternar entre `Diário` e `Geral`.

### Revisão 2.6.42

A versão `2.6.42` simplifica `Kills FF` para lançamento manual: o app soma as kills digitadas usando a ação `add`, remove a administração/overlay local da aba e deixa a URL oficial do overlay do Jarvis fixa na lateral direita. A `Fila FF` agora coloca o `Resumo de salas` na direita ocupando a altura da aba, move `Adicionar jogador` para uma janela modal e esconde a opção antiga de salas por gifts TikFinity.

### Revisão 2.6.41

A versão `2.6.41` corrige uma falha ao abrir a `Fila FF`: os campos de `ID membro` e `ID FF` agora usam a cor de texto do tema corretamente, sem reaproveitar o último texto de opções como nome de cor.

### Revisão 2.6.40

A versão `2.6.40` adiciona o seletor `Aplicar em` na aba `Kills FF`: ao enviar as kills manuais, o app pode definir os valores somente no rank do dia, somente no rank geral ou nos dois ao mesmo tempo, usando o mesmo endpoint de ações do painel Jarvis.

### Revisão 2.6.39

A versão `2.6.39` aproxima o `Overlay OBS do site` do painel Jarvis: o app agora edita os campos avançados do overlay `/freefire/overlay`, incluindo gap, padding, tamanhos de título/linha/valor, altura da linha, cores e opacidades de fundo, raio, largura do acento e os títulos/cores dos painéis `Geral`, `Dia` e `Fila`.

### Revisão 2.6.38

A versão `2.6.38` melhora a conferência da `Fila FF`: cada linha da lista principal agora mostra `ID membro` e `ID FF`, aproximando a visualização do painel do site e facilitando identificar o cadastro exato que está sendo alterado no Jarvis. O verificador local também cobre a sequência completa das ações de salas do site: limpar, adicionar, renomear, salvar ID FF, somar/remover/definir salas, ordenar, atender e remover.

### Revisão 2.6.37

A versão `2.6.37` melhora a aba `Kills FF`: cada linha das tabelas visuais `Kills Diárias` e `Kills Geral` ganhou a ação `Usar`, que preenche o card `Administrar ranking Jarvis` com jogador, ID FF, chave interna e escopo correto. A tabela da direita continua somente visual, mas fica mais rápida para administrar sem digitar o nick manualmente.

### Revisão 2.6.36

A versão `2.6.36` alinha o botão `Atender próximo` da `Fila FF` ao comportamento do site: ele consome 1 sala do primeiro jogador da fila e, se ainda restarem salas, reenfileira o jogador no final. Isso vale para o fluxo remoto do Jarvis e também para o fallback local.

### Revisão 2.6.35

A versão `2.6.35` deixa `Fila FF` mais fiel ao contrato do Jarvis: o app agora lê `queue.entries`, `summary.total_members` e `summary.total_credits`, usando os totais remotos de membros e salas no painel quando o site enviar esses valores. Isso evita diferença entre os números do app e os números do site.

### Revisão 2.6.34

A versão `2.6.34` deixa a `Fila FF` mais alinhada ao painel do site: entradas são agrupadas primeiro por ID do membro e ID FF, reduzindo duplicidade quando o mesmo jogador aparece com nomes diferentes. O `Resumo de salas` também mostra o ID do membro junto com o ID FF para facilitar conferência.

### Revisão 2.6.33

A versão `2.6.33` melhora `Fila FF`/`Salas FF` com o card `Resumo de salas`, mostrando jogadores únicos, total de salas e separação por aguardando, chamado e jogando. A lista é ordenada por quem tem mais salas, evita duplicidade por nome/ID FF e deixa a tabela principal da direita focada na gestão da fila.

### Revisão 2.6.32

A versão `2.6.32` mantém `Kills FF` dividido como no site, com `Kills Diárias` e `Kills Geral` em tabelas visuais fixas na direita, e completa o card `OBS Kills FF` com os controles avançados do overlay legado: peso, largura máxima, gap, padding, troca automática, sombra, fundo, borda e raio.

### Revisão 2.6.31

A versão `2.6.31` adiciona em `Kills FF` o card `OBS Kills FF`, para editar pelo app o estilo do overlay legado `/freefire-kills/obs`: título, fonte, alinhamento, tamanhos, cores, título/#/medalhas/fundo/borda, além de carregar/salvar no Jarvis e copiar/abrir a URL OBS. O Jarvis recebe a rota segura `/api/freefire-kills/style` com `X-Aizen-Token`.

### Revisão 2.6.30

A versão `2.6.30` adiciona na aba `Fila FF` o card `Adicionar jogador manualmente`, igual ao painel do site, com campos para `Nome`, `ID membro`, `ID FF` e `Salas`, enviando direto para a ação `add_member` do Jarvis.

### Revisão 2.6.29

A versão `2.6.29` adiciona o botão `Reset tudo` em `Kills FF > Administrar ranking Jarvis`, usando a ação `reset` do site para zerar ranking diário e geral ao mesmo tempo, mantendo os jogadores ignorados.

### Revisão 2.6.28

A versão `2.6.28` deixa a aba `Kills FF` igual ao site: ranking diário e ranking geral separados, ambos somente visuais em uma tabela fixa na direita. O app também aceita aliases extras do Jarvis para evitar falha caso o backend envie `general_ranking`/`daily_rank`.

### Revisão 2.6.27

A versão `2.6.27` adiciona na aba `Kills FF` o card `Administrar ranking Jarvis`, com ações equivalentes ao painel do site: somar, remover, definir kills, salvar nome, salvar ID FF, ignorar, reexibir, remover do ranking e resetar diário/geral. O rank da direita permanece somente visual.

### Revisão 2.6.26

A versão `2.6.26` separa o rank da aba `Kills FF` em duas tabelas fixas na direita: `Kills Diárias` e `Kills Geral`. As tabelas sao somente visuais e continuam sendo atualizadas pelo Jarvis.

### Revisão 2.6.25

A versão `2.6.25` adiciona ao app o painel `Salas por Gifts TikFinity` dentro da aba `Fila FF`: configuração de webhook, token, moedas por sala, vínculos TikTok -> membro, moedas acumuladas e histórico recente, usando a rota segura `/api/tikfinity/ff-gifts` do Jarvis.

### Revisão 2.6.24

A versão `2.6.24` aproxima a `Fila FF` do painel admin do site: cada jogador agora tem ações diretas de `Topo`, `Subir`, `Descer`, `Final`, `+1`, `-1`, `Definir`, `Salvar nome`, `Salvar ID FF` e `Remover`, usando a rota segura `/api/freefire-queue/action` quando configurada.

### Revisão 2.6.23

A versão `2.6.23` adiciona na aba `Kills FF` a lista de jogadores ignorados vinda do Jarvis, com contador e botão `Reexibir` por jogador, aproximando o app da área de ignorados do painel admin do site.

### Revisão 2.6.22

A versão `2.6.22` aproxima `Kills FF` do painel admin do site: o ranking visual ganhou ações `+1`, `-1`, `Definir`, editar `Nome`, editar `ID`, `Ignorar`, `Reexibir`, `Zerar diario` e `Zerar geral`, usando a rota segura `/api/freefire-kills/action` do Jarvis.

### Revisão 2.6.21

A versão `2.6.21` faz a aba `Fila FF` usar ações reais do Jarvis quando o jogador já veio do painel: `Chamar próximo` consome uma sala, `Remover` zera o membro, `Limpar` limpa a fila no site, `+1/-1` altera salas no servidor e `Sincronizar` normaliza a fila pelo Jarvis.

### Revisão 2.6.20

A versão `2.6.20` deduplica a `Fila FF` por jogador, preserva IDs vindos do Jarvis para evitar recriação de membros e separa `Kills FF` em ranking visual `Diario` e `Geral` na direita, sem sobrescrever a tabela manual de envio.

### Revisão 2.6.19

A versão `2.6.19` refina a correção da `Fila FF` para preservar as mesmas linhas vindas do Jarvis e impedir apenas a expansão indevida de `rooms` ou `credits` em linhas duplicadas.

### Revisão 2.6.18

A versão `2.6.18` corrige a leitura da `Fila FF` quando o Jarvis envia `rooms` ou `credits`. O app agora mostra uma linha por jogador, exibe a quantidade de salas em uma coluna propria e compacta duplicados salvos anteriormente no `config.json`.

### Revisão 2.6.17

A versão `2.6.17` reorganiza a aba `Kills FF`: as configurações e status ficam na esquerda, com rolagem propria, e a lista de jogadores/kills fica em um painel dedicado na direita ocupando toda a altura disponivel do app.

### Revisão 2.6.16

A versão `2.6.16` adiciona a aba `Temporizador`, para mensagens automaticas do bot em estilo Nightbot/Streamlabs. Cada timer pode ter nome, texto, intervalo, minimo de mensagens novas no chat antes de disparar, estado ligado/desligado e teste manual. O envio usa a mesma configuracao da aba `Comandos`, respeitando o delay seguro global para reduzir risco de spam na live.

### Revisão 2.6.15

A versão `2.6.15` reforça o fechamento do app, fecha overlays e janelas auxiliares de forma centralizada, cancela polls em segundo plano ao sair, melhora o instalador quando já existe uma instância aberta, ajusta o cabeçalho premium e deixa o autocomplete de nicks mais claro no painel `Kills FF`.

## Overlay Kills FF

Na aba `Kills FF`, a lateral direita mostra um overlay interno de ranking. Ele tem:

- coluna de rank;
- nome do jogador;
- quantidade de kills;
- aba `Diário`;
- aba `Geral`.

Quando o Jarvis devolve os rankings depois do lançamento das kills, o overlay usa esses dados separados por aba. Se uma aba ainda não foi retornada pelo Jarvis, ela fica vazia em vez de reaproveitar os dados da outra.

Para validar os contratos localmente:

```powershell
python scripts\verify_jarvis_ff.py --mock
```

Esse modo sobe um Jarvis fake local e valida leitura, escrita, `mode`, `room`, cliente, versao e headers dos tres paineis.

Para validar apenas a derivacao dos endpoints e os parsers locais, sem rede:

```powershell
python scripts\verify_jarvis_ff.py --contracts
```

Para conferir quais endpoints uma URL/configuracao vai usar, sem acessar a rede:

```powershell
python scripts\verify_jarvis_ff.py --base-url "https://seu-jarvis.squareweb.app/admin" --resolve-only
```

Para validar contra o site real:

```powershell
python scripts\verify_jarvis_ff.py --base-url "https://seu-jarvis.squareweb.app" --token "SEU_TOKEN" --room "principal"
```

O verificador imprime as URLs finais de `Kills FF`, `Fila FF` e `Overlay FF` antes de testar, para conferir se a URL base derivou os endpoints certos.

Para checar o site real sem enviar dados de teste, use o modo somente leitura:

```powershell
python scripts\verify_jarvis_ff.py --base-url "https://seu-jarvis.squareweb.app" --token "SEU_TOKEN" --room "principal" --read-only
```

Depois de preencher o `config.json` pelo app, tambem pode validar usando a propria configuracao salva:

```powershell
python scripts\verify_jarvis_ff.py --config config.json --read-only
```

Use `--require-overlay` quando o backend ja tiver `/api/freefire-overlay` e o teste deve falhar se ele nao responder.

## Sorteio pelo chat unificado

Na aba `Sorteio Chat`, o programa le o chat unificado do Social Stream Ninja e coloca na fila quem mandar o comando configurado, por padrao `!sorteio`.

Quando a origem do chat entregar foto do usuario, a fila e o painel do vencedor mostram o avatar do participante. Se a foto nao vier no payload, o app usa as iniciais do nome como fallback.

O sorteio tambem aceita entradas extras para espectadores com badge, gift ou sub. Na aba `Sorteio Chat`, ajuste `Entradas por tipo`:

- `Normal`: quantidade de entradas de um seguidor comum;
- `Fã`: quantidade de entradas quando o evento trouxer badge/campo de fã;
- `Super fã`: quantidade de entradas quando o evento trouxer badge/campo de super fã;
- `Gift`: quantidade de entradas quando o payload indicar presente/moedas/diamantes;
- `Sub`: quantidade de entradas quando o payload indicar assinante/subscriber.

Por padrao, o app usa `Normal = 1`, `Fã = 2`, `Super fã = 3`, `Gift = 5` e `Sub = 10`. A fila continua mostrando cada pessoa uma unica vez, mostra quantas entradas cada um tem e usa os pesos para aumentar a chance.

O anti-fraude impede duplicidade pelo mesmo nome, ignora spam do comando durante o cooldown por usuario e permite incluir ou ignorar moderadores. Ao concluir, o historico salva horario, participantes com entradas, tentativas bloqueadas, vencedores e mensagens finais do vencedor.

Depois que o cronometro termina, clique em `Sortear vencedor`. O programa roda uma roleta com participantes, suspense sonoro, destaque do avatar e confete no vencedor. Depois, mostra somente as mensagens do vencedor, permite `Sortear outro` e salva o historico ao clicar em `Concluir sorteio`.

Os sorteios concluidos ficam salvos em `raffle_history.json`.

## Chat ao vivo por eventos

Na aba `Chat Ao Vivo`, o programa pode receber mensagens por `Webhook local` ou `TikFinity WebSocket`, sem depender de navegador aberto. O modo recomendado e `Webhook local` com token secreto.

Ao clicar em `Iniciar chat`, o app abre uma janela dedicada do chat ao vivo. Essa janela pode ser maximizada, movida para outro monitor e deixada em `Sempre visível`.

Endpoint padrao:

```text
http://127.0.0.1:8765/api/chat-event
```

Payload minimo esperado:

```json
{
  "platform": "tiktok",
  "userId": "123",
  "username": "aizen",
  "nickname": "Aizen",
  "avatarUrl": "https://...",
  "comment": "!sorteio"
}
```

Com o sorteio em `Fonte do sorteio: Eventos do app`, qualquer mensagem recebida pela aba de chat tambem alimenta o sorteio automaticamente enquanto o cronometro estiver ativo.

## Comandos e temporizador

A aba `Comandos` responde automaticamente quando alguem envia um comando configurado no chat, como `!pix`, `!dc`, `!regras` ou `!loja`. As respostas usam o envio configurado em `Streamer.bot WebSocket` ou `Streamer.bot HTTP`, com delay seguro global e cooldown por comando.

A aba `Temporizador` envia mensagens automaticas a cada X segundos, como Nightbot e Streamlabs Bot. Cada linha permite configurar:

- nome interno do timer;
- mensagem que sera enviada;
- intervalo em segundos;
- minimo de mensagens novas no chat desde o ultimo disparo;
- ligado/desligado por timer;
- teste manual antes de usar em live.

Use o campo `Min. chat` para evitar spam quando a live estiver parada. Exemplo: intervalo `600` e minimo `6` faz o bot enviar a mensagem apenas depois de 10 minutos e pelo menos 6 mensagens novas no chat.
