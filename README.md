# Video Downloader API (Python)

API em Python para receber URL de video e baixar localmente.

## Requisitos

- Python 3.10+
- (Opcional) ffmpeg no PATH para melhor suporte a merge/conversao

## Instalar dependencias

```bash
pip install -r requirements.txt
```

## Rodar API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Para customizar pasta de download:

```bash
set DOWNLOAD_DIR=C:\caminho\downloads
```

## Endpoints

- `GET /` (interface web)
- `GET /health`
- `GET /search/youtube?q=termo&limit=10`
- `POST /download` (alias para video)
- `POST /download/video`
- `POST /download/audio` (musica/audio do video)
- `GET /files/{filename}`

Payload aceito:

```json
{
  "url": "https://...",
  "quality": "best"
}
```

Qualidades:

- Video: `best`, `1080`, `720`, `480`, `360`
- Audio: `320`, `192`, `128` (kbps mp3)

### Exemplo de download

```bash
curl -X POST "http://127.0.0.1:8000/download" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

Exemplo de download de audio:

```bash
curl -X POST "http://127.0.0.1:8000/download/audio" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","quality":"320"}'
```

Resposta esperada:

```json
{
  "status": "success",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "...",
  "filename": "...",
  "filepath": "C:/xampp/htdocs/vidown/downloads/...",
  "extractor": "youtube",
  "duration": 123.0
}
```

Depois, baixe o arquivo salvo:

```bash
curl -O "http://127.0.0.1:8000/files/NOME_DO_ARQUIVO"
```

## Observacoes

- "Qualquer tipo de video" depende dos sites suportados pelo `yt-dlp`.
- Use apenas em conteudo que voce tem permissao para baixar.
- Os ficheiros sao assinados automaticamente com `-| https://nauro-vidown.up.railway.app` no final do nome.
- Em Railway, o filesystem do container e efemero: arquivos podem sumir em restart/redeploy.

## Deploy Railway

- `Procfile` e `nixpacks.toml` ja estao prontos.
- O `nixpacks.toml` instala `ffmpeg`.
- A Railway injeta `PORT` automaticamente; o start command ja usa essa variavel.
- Se quiser persistencia real dos arquivos, use storage externo (S3, R2 etc.) e salve la em vez de disco local.

