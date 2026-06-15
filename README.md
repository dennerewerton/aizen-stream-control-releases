# Free Fire Kill Sender

Utilitario local para Windows. Ao apertar um atalho, ele tira print da tela, le a tabela de kills do Free Fire e envia para o Discord no formato:

```text
(nome jogador, quantidade de kills)
```

## Como configurar

1. Instale dependencias:

```powershell
python -m pip install -r requirements.txt
```

2. Copie o exemplo de configuracao:

```powershell
Copy-Item config.example.json config.json
```

3. Edite `config.json` e coloque o webhook do Discord em `discord_webhook_url`, ou abra o executavel e preencha pela janela.

O jeito mais simples de mandar para outro bot do Discord e criar um webhook no canal onde esse bot consegue ler mensagens.

Se o Jarvis Bot tiver um endpoint HTTP proprio, coloque a URL em `jarvis_endpoint_url`. Nesse modo o programa manda JSON para o Jarvis em vez de mandar pelo webhook. Use `https://` quando o servidor tiver HTTPS.

O programa reconhece dois layouts:

- tabela antiga com colunas `PLAYER / K / D / DMG`;
- tela final com colunas `APELIDO / K / D / A / DMG`.

## Testar com uma imagem salva

```powershell
python freefire_kill_sender.py --image "C:\Users\Aizen\Pictures\BlueStacks\Screenshot_2026.06.14_16.58.09.454.png" --dry-run --debug
```

## Rodar com atalho

```powershell
python freefire_kill_sender.py --watch
```

Atalho padrao: `CTRL+SHIFT+F12`.

Se o atalho nao registrar, troque `hotkey` no `config.json` ou rode o terminal como administrador.

## Gerar executavel

```powershell
.\build_exe.ps1
```

O arquivo final fica em:

```text
dist\FreeFireKillSender.exe
```

Ao abrir o executavel, escolha o atalho, configure Discord/Jarvis e clique em `Iniciar em segundo plano`. Depois pode minimizar a janela; o atalho continua ativo enquanto o app estiver aberto.

Na opcao `Captura`, use:

- `Monitor principal`: captura apenas o monitor principal do Windows;
- `Monitor da janela ativa`: captura o monitor onde o Free Fire/BlueStacks estiver ativo;
- `Janela ativa`: captura só a janela ativa;
- `Todos os monitores`: comportamento antigo.

No campo `Ignorar jogadores`, coloque os nomes que nao devem aparecer no rank, separados por virgula. Exemplo:

```text
AIZEN OFC, LOUD
```

A comparacao ignora maiusculas/minusculas, mas o nome precisa bater com o nome final depois das correcoes de OCR.

## Integrar com o Jarvis Bot

Voce tem dois caminhos.

### Opcao simples: webhook no Discord

Crie um webhook no canal do Discord, cole no campo `Webhook Discord` e deixe `Endpoint Jarvis` vazio.

O Jarvis Bot precisa ler mensagens desse canal e aceitar mensagens de webhook. Em muitos bots existe algo como `if (message.author.bot) return;`; nesse caso, ajuste para nao ignorar esse webhook especifico.

### Opcao direta: endpoint HTTP do Jarvis

Se o Jarvis Bot tiver um pequeno servidor HTTP, cole a URL no campo `Endpoint Jarvis`, por exemplo:

```text
http://127.0.0.1:3000/freefire-kills
```

Para seu endpoint hospedado na Square Cloud, use:

```text
https://jarvis-da-shopee.squareweb.app/api/freefire-kills
```

O programa vai enviar JSON assim:

```json
{
  "content": "Kills da partida\n\n(ruan loko', 3)",
  "players": [
    { "name": "ruan loko'", "kills": 3 }
  ]
}
```

Exemplo em Node.js/Express:

```js
app.post('/freefire-kills', express.json(), async (req, res) => {
  const { content, players } = req.body
  console.log(players)
  await channel.send(content)
  res.sendStatus(204)
})
```

## Ajustar OCR

Se algum nick sair errado, adicione uma entrada em `name_corrections`:

```json
"nome lido errado": "nome correto"
```

Se a resolucao do emulador mudar e os recortes ficarem fora do lugar, ajuste os valores em `layout` usando `reference_size` como base.
