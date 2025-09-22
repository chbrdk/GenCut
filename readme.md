# Video Analysis Agent

Ein vollständiges Docker-basiertes System für Video-Analyse mit KI-Komponenten und automatisierten Workflows.

## 🚀 Features

- **Video-Upload und -Verarbeitung**: Automatische Analyse von hochgeladenen Videos
- **KI-gestützte Szenenerkennung**: Intelligente Aufteilung von Videos in Szenen
- **Sprach-zu-Text**: Automatische Transkription mit Whisper
- **Video-Embeddings**: Generierung von semantischen Video-Embeddings mit ImageBind
- **Voice Cloning**: Audio-Verarbeitung und Stimmklonierung
- **Workflow-Automatisierung**: Integration mit n8n für automatisierte Prozesse

## 🏗️ Architektur

Das System besteht aus 6 Docker-Services:

- **gencut-frontend** (Port 5679): Hauptanwendung mit Flask
- **analyzer** (Port 8000): Video-Analyse und Szenenerkennung
- **whisper** (Port 9000): Speech-to-Text Transkription
- **imagebind-embed** (Port 8750): Video-Embedding Generierung
- **revoice** (Port 5682): Voice Cloning und Audio-Verarbeitung
- **nginx** (Port 5679): Reverse Proxy und statische Dateien

## 🛠️ Installation & Setup

### Voraussetzungen

- Docker & Docker Compose
- macOS (optimiert für macOS Docker-Setup)
- Mindestens 8GB RAM (für KI-Modelle)

### Starten des Systems

```bash
# Repository klonen
git clone <repository-url>
cd video-analysis-agent

# Services starten
docker-compose up -d

# Status überprüfen
docker-compose ps
```

### Services überprüfen

```bash
# Alle Services testen
curl http://localhost:5679  # Frontend
curl http://localhost:8000  # Analyzer
curl http://localhost:9000  # Whisper
curl http://localhost:8750  # ImageBind
curl http://localhost:5682  # Revoice
```

## 📁 Projektstruktur

```
video-analysis-agent/
├── services/
│   ├── analyzer/          # Video-Analyse Service
│   ├── cutdown-generator/ # Hauptanwendung
│   ├── revoice/           # Voice Cloning
│   ├── upload-service/    # Upload-Handler
│   └── whisper/           # Speech-to-Text
├── static/                # Statische Assets
├── templates/             # HTML-Templates
├── docker-compose.yml     # Docker-Konfiguration
├── nginx.conf            # Nginx-Konfiguration
└── README.md             # Diese Datei
```

## 🔧 Konfiguration

### Umgebungsvariablen

- `ELEVENLABS_API_KEY`: API-Schlüssel für ElevenLabs Voice AI
- `FLASK_ENV`: Flask-Umgebung (development/production)
- `ASR_MODEL`: Whisper-Modell (base/large)

### Volume-Mounts

- `videos_data`: Geteilte Video-Daten zwischen Services
- `static_data`: Statische Assets
- `./videos/uploads`: Upload-Verzeichnis
- `./videos/cutdowns`: Generierte Video-Cutdowns

## 🐛 Bekannte Probleme & Lösungen

### Resource Deadlock auf macOS

Das System wurde speziell für macOS optimiert und behebt bekannte Docker Volume-Probleme:

- ImageBind-Gewichte werden direkt in das Docker-Image eingebettet
- Optimierte Volume-Mounting-Strategien
- Automatischer Service-Neustart bei Crashes

### Service-Neustart

```bash
# Einzelnen Service neustarten
docker-compose restart <service-name>

# Alle Services neustarten
docker-compose restart

# Services komplett neu starten
docker-compose down && docker-compose up -d
```

## 📊 Monitoring

### Logs anzeigen

```bash
# Alle Services
docker-compose logs

# Einzelner Service
docker-compose logs <service-name>

# Live-Logs folgen
docker-compose logs -f
```

### Service-Status

```bash
# Status aller Container
docker-compose ps

# Ressourcenverbrauch
docker stats
```

## 🔗 Integration

### n8n Workflow-Automatisierung

Das System ist vollständig in n8n integriert:

- Automatische Webhook-Aufrufe bei Video-Upload
- Status-Updates während der Verarbeitung
- Workflow-Orchestrierung für komplexe Pipelines

### API-Endpunkte

- `POST /upload`: Video-Upload
- `GET /status/<video_id>`: Verarbeitungsstatus
- `GET /download/<video_id>`: Download verarbeiteter Videos

## 📝 Entwicklung

### Lokale Entwicklung

```bash
# Services im Development-Modus
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Einzelnen Service entwickeln
docker-compose up <service-name>
```

### Code-Änderungen

```bash
# Änderungen committen
git add .
git commit -m "Beschreibung der Änderungen"
git push origin main
```

## 📄 Lizenz

Dieses Projekt ist für interne Entwicklung und Forschung bestimmt.

## 🤝 Support

Bei Problemen oder Fragen:

1. Logs überprüfen: `docker-compose logs`
2. Service-Status prüfen: `docker-compose ps`
3. Docker-System neustarten: `docker-compose restart`

---

**Letzte Aktualisierung**: $(date)
**Docker-Version**: Optimiert für macOS Docker Desktop
**Status**: ✅ Produktionsbereit