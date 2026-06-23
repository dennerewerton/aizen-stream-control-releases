# Aizen Stream Control

Aplicativo Windows para lives, kills manuais em tempo real e sorteios multi-plataforma.

As opcoes gerais ficam na aba `Geral`. Os paineis `Kills FF`, `Fila FF` e `Overlay FF` ficam sincronizados com o painel admin do Jarvis, podem rodar em varios PCs ao mesmo tempo e tem atualizacao automatica por manifesto remoto.

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

Todos os PCs devem usar:

- a mesma `URL base do Jarvis` ou os mesmos endpoints de `Kills FF` e `Fila FF`;
- a mesma `Sala`, por exemplo `principal`;
- nomes diferentes em `Geral > Nome deste PC`.

Quando um PC altera a tabela, ele envia o estado para o painel. Os outros PCs leem o painel no intervalo configurado em `Ler painel a cada` e atualizam a tela.

Na aba `Geral`, o card `Jarvis FF` permite informar a URL base do site, preencher automaticamente `/api/freefire-kills`, `/api/freefire-queue` e `/api/freefire-overlay`, e testar se Kills/Fila/Overlay respondem via `GET`.
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

O painel deve aceitar `POST` para receber o estado:

```json
{
  "source": "aizen-stream-control",
  "mode": "manual",
  "app_version": "2.6.0",
  "sync_version": 2,
  "room": "principal",
  "client_id": "id-unico-do-pc",
  "client_name": "PC LIVE",
  "updated_by": "PC LIVE",
  "updated_at": "2026-06-22T19:30:00",
  "players": [
    { "name": "AIZEN OFC", "kills": 7 }
  ]
}
```

Para refletir edicoes feitas no painel ou em outro PC, o mesmo endpoint deve aceitar `GET` e responder:

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
  "version": "2.6.22",
  "notes": "Kills FF com acoes reais do Jarvis no ranking: +1/-1, definir, editar nome/ID, ignorar, reexibir e resetar.",
  "windows": {
    "portable_url": "https://github.com/dennerewerton/aizen-stream-control-releases/releases/download/v2.6.22/AizenStreamControl.exe",
    "sha256": "hash-sha256-do-exe"
  }
}
```

Para gerar o manifesto depois de publicar o exe:

```powershell
.\build_update_manifest.ps1 -Version "2.6.22" -DownloadUrl "https://github.com/dennerewerton/aizen-stream-control-releases/releases/download/v2.6.22/AizenStreamControl.exe"
```

Envie para o servidor:

- `dist\AizenStreamControl.exe`
- `dist\updates.json`

Depois cole a URL do `updates.json` no campo `Manifesto de atualização`.

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

## Overlay FF

Na aba `Overlay FF`, o app combina em uma unica tela os dados sincronizados de `Kills FF` e `Fila FF`. O preview mostra o mesmo layout da janela de overlay, com ranking de kills, resumo da fila, total de kills, jogadores e salas ativas.

Botoes principais:

- `Abrir overlay`: abre uma janela sempre visivel para usar no jogo ou no OBS;
- `Atualizar Jarvis`: busca Kills FF, Fila FF e Overlay FF imediatamente;
- `Buscar overlay`, `Buscar kills` e `Buscar fila`: atualizam cada fonte separadamente;
- `Salvar`: guarda opacidade, tamanho e opcoes do overlay.

O overlay usa as mesmas URLs configuradas nas abas `Kills FF` e `Fila FF`, entao qualquer mudanca lida ou enviada para o Jarvis atualiza tambem a janela do overlay.

Se o site tiver o endpoint `/api/freefire-overlay`, o app tambem envia e busca continuamente um snapshot combinado com `players`, `queue`, `summary` e `options`. Se esse endpoint ficar vazio, o Overlay FF continua sincronizado localmente a partir de Kills FF e Fila FF.

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
