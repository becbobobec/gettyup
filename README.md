# Celebrity News & Event Bot

Bot para Telegram que monitora artistas e envia alertas de:

1. Eventos/aparições públicas
2. Celebrity Sightings/candids
3. Novos projetos: filmes, séries, castings, trailers, datas de lançamento e entrevistas relevantes

Fontes:

- Google News RSS
- Getty Images
- WireImage
- Shutterstock Editorial

## Configurar no GitHub

Vá em:

Settings → Secrets and variables → Actions → New repository secret

Crie:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## Editar artistas

Altere o arquivo:

`artists.txt`

Um artista por linha.

## Rodar manualmente

Actions → Celebrity News & Event Bot → Run workflow

## Frequência

Por padrão, roda de hora em hora.

Edite:

`.github/workflows/celebrity-news-event-bot.yml`

Linha:

```yaml
- cron: "0 * * * *"
```

## Observação

O bot não baixa imagens, não acessa conteúdo pago e não burla login. Ele apenas monitora páginas públicas e RSS.
