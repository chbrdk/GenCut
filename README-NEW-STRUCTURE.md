# 🎬 Video Analysis Agent - Neue Services-Struktur

## 🏗️ Überblick

Der Video Analysis Agent wurde **umorganisiert** in eine **saubere Services-Architektur**. Alle Services laufen jetzt in einem einzigen, gut organisierten Stack.

## 🗂️ Neue Struktur

```
video-analysis-agent/
├── services/                    # Alle Services organisiert
│   ├── cutdown-generator/      # Video-Cutdown Generation (ehemals upload-service)
│   ├── revoice/               # Video-Revoicing & Lip-Sync
│   ├── analyzer/              # Video-Analyse & Szenen-Erkennung
│   └── whisper/               # Speech-to-Text
├── videos/                     # Geteilte Video-Daten
│   ├── uploads/               # Hochgeladene Videos
│   ├── cutdowns/              # Generierte Cutdowns
│   ├── screenshots/           # Video-Screenshots
│   ├── separated/             # Audio/Video-Separation
│   └── revoiced/              # Revoicing-Ergebnisse
├── temp/                       # Temporäre Dateien
├── models/                     # ML-Modelle (Whisper etc.)
├── docker-compose.yml          # Services-Konfiguration
└── build-and-run.sh           # Ein-Klick Setup
```

## 🛠️ Services

### 1. **Cutdown Generator** (Port: 5679) 📋
- **Funktion**: Video-Cutdown-Erstellung
- **Ehemals**: `upload-service`
- **Pfad**: `services/cutdown-generator/`

### 2. **Revoice Service** (Port: 5680) 💋
- **Funktion**: Video-Upload und Revoicing/Lip-Sync
- **Neu**: Aus CENTRALSPACE integriert
- **Pfad**: `services/revoice/`

### 3. **Analyzer** (Port: 8000) 🎬
- **Funktion**: Video-Analyse, Szenen-Erkennung
- **Pfad**: `services/analyzer/`

### 4. **Whisper** (Port: 9000) 🎙️
- **Funktion**: Speech-to-Text
- **Pfad**: `services/whisper/`

### 5. **Storybook** (Port: 6006) 📚
- **Funktion**: UI-Komponenten
- **Pfad**: `../component-library`

## 🚀 Setup & Installation

### **Ein-Klick Setup:**
```bash
cd video-analysis-agent
./build-and-run.sh
```

### **Manueller Start:**
```bash
# 1. Netzwerke erstellen
docker network create n8n-network
docker network create video-network

# 2. Services builden und starten
docker-compose up -d

# 3. Status prüfen
docker-compose ps
```

## 📡 API Endpoints

### Cutdown Generator (Port 5679)
| Endpoint | Method | Description |
|----------|---------|-------------|
| `/upload` | POST | Video für Cutdown hochladen |
| `/health` | GET | Service-Status |

### Revoice Service (Port 5680)
| Endpoint | Method | Description |
|----------|---------|-------------|
| `/upload` | POST | Video für Revoicing hochladen |
| `/status/<video_id>` | GET | Revoicing-Status prüfen |
| `/videos/<folder>/<filename>` | GET | Videos abrufen |
| `/sessions` | GET | Alle Sessions anzeigen |
| `/health` | GET | Service-Status |

### Analyzer (Port 8000)
| Endpoint | Method | Description |
|----------|---------|-------------|
| `/analyze` | POST | Video analysieren |
| `/health` | GET | Service-Status |

### Whisper (Port 9000)
| Endpoint | Method | Description |
|----------|---------|-------------|
| `/transcribe` | POST | Audio transkribieren |
| `/health` | GET | Service-Status |

## 🔄 Workflows

### **Cutdown-Workflow:**
1. **Upload** → `http://localhost:5679/upload`
2. **Processing** → Analyzer erkennt Szenen
3. **Result** → Cutdown wird generiert
4. **Download** → `/videos/cutdowns/<filename>`

### **Revoice-Workflow:**
1. **Upload** → `http://localhost:5680/upload`
2. **Processing** → N8N Webhook Integration
3. **Status** → `/status/<video_id>`
4. **Download** → `/videos/revoiced/<filename>`

## 🎯 Integration mit N8N

### **Webhook URLs:**
- **Revoice**: `http://revoice:5679/webhook/revoice-upload`
- **Cutdown**: `http://cutdown-generator:5679/webhook/cutdown-upload`

### **Container-Netzwerke:**
- **n8n-network**: Für N8N Integration
- **video-network**: Für Service-Kommunikation

## 📊 Monitoring & Logs

### **Service-Status:**
```bash
# Alle Services prüfen
docker-compose ps

# Logs anzeigen
docker-compose logs -f cutdown-generator
docker-compose logs -f revoice
docker-compose logs -f analyzer
docker-compose logs -f whisper
```

### **Health-Checks:**
```bash
curl http://localhost:5679/health  # Cutdown Generator
curl http://localhost:5680/health  # Revoice Service
curl http://localhost:8000/health  # Analyzer
curl http://localhost:9000/health  # Whisper
```

## 🧪 Testing

### **Upload Tests:**
```bash
# Cutdown Upload
curl -F "video=@test.mp4" http://localhost:5679/upload

# Revoice Upload
curl -F "video=@test.mp4" http://localhost:5680/upload
```

### **Status Tests:**
```bash
# Revoice Status
curl http://localhost:5680/status/VIDEO_ID

# Sessions Overview
curl http://localhost:5680/sessions
```

## 🔧 Konfiguration

### **Ports:**
- `5679`: Cutdown Generator
- `5680`: Revoice Service  
- `8000`: Analyzer
- `9000`: Whisper
- `6006`: Storybook

### **Volumes:**
```yaml
volumes:
  - ./videos/uploads:/app/videos/uploads
  - ./videos/cutdowns:/app/videos/cutdowns
  - ./videos/screenshots:/app/videos/screenshots
  - ./videos/revoiced:/app/videos/revoiced
  - ./temp:/app/temp
```

## 🎉 Vorteile der neuen Struktur

### ✅ **Was ist besser:**
- **Organisiert**: Alle Services in `services/` Ordner
- **Sauber**: Klare Trennung von Funktionen
- **Einfach**: Ein Docker-Compose für alles
- **Skalierbar**: Services können unabhängig entwickelt werden
- **Wartbar**: Einfache Updates und Erweiterungen

### ✅ **Keine Komplexität mehr:**
- ❌ Kein CENTRALSPACE-Overhead
- ❌ Keine Volume-Konflikte  
- ❌ Keine Network-Issues
- ✅ **Ein Stack für alles**
- ✅ **Geteilte Volumes**
- ✅ **Einheitliche Architektur**

## 🔄 Migration von CENTRALSPACE

**CENTRALSPACE ist nicht mehr nötig!** Alle Features sind jetzt im Video Analysis Agent:

- **Upload Service** → `services/revoice/`
- **Video Processor** → `services/analyzer/`
- **Shared Data** → `videos/` Volumes
- **N8N Integration** → Über Netzwerke

## 📞 Support

### **Services neustarten:**
```bash
docker-compose restart cutdown-generator
docker-compose restart revoice
docker-compose restart analyzer
```

### **Komplett neu builden:**
```bash
./build-and-run.sh
```

### **Troubleshooting:**
```bash
# Netzwerke prüfen
docker network ls

# Services prüfen
docker-compose ps

# Logs prüfen
docker-compose logs --tail=50 revoice
```

---

🎬 **Video Analysis Agent** ist jetzt **einfacher, sauberer und wartbarer**! 🚀 