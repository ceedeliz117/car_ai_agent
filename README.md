# README - Kavak Sales Bot

## 🚗 Descripción General

Este bot simula el comportamiento de un agente comercial de **Kavak**, ayudando a los usuarios a:

- Consultar información sobre la propuesta de valor de Kavak.
- Buscar autos por marca, modelo, año y precio.
- Simular planes de financiamiento.
- Conectarse directamente por WhatsApp a través de Twilio.
- (BONUS) Consultar **multas vehiculares** mediante un sistema basado en **SQS + modelo de visión computacional** que extrae la información de placas vehiculares.

## ✅ Características Principales

- API REST en Python (FastAPI)
- Integración con Twilio WhatsApp Sandbox
- Consumo de modelos LLM (GPT-4 de OpenAI)
- Búsqueda inteligente en catálogo CSV
- Simulador financiero con tasa fija
- ✨ Bonus: Análisis de placas vía SQS y modelo TFLite

## 📚 Requisitos

- Docker
- Docker Compose
- Make
  - macOS/Linux: Generalmente preinstalado
  - Windows: Instalar con WSL o `choco install make`
- Cuenta en OpenAI (API Key)
- Cuenta en Twilio (Sandbox de WhatsApp)

## ⚙️ Instalación y Uso

1. Clona el repositorio:

```bash
git clone https://github.com/usuario/car_ai_agent.git
cd car_ai_agent
```

2. Configura el archivo `.env`:

```env
OPENAI_API_KEY=tu_clave
TWILIO_ACCOUNT_SID=... (opcional para extensión de SQS)
TWILIO_AUTH_TOKEN=... (opcional para extensión de SQS)
```

3. Ejecuta el bot:

```bash
make install
```

4. Verifica salud:

```bash
curl http://localhost:8000/health
```

5. Usa [ngrok](https://ngrok.com/) para exponer localmente:

```bash
ngrok http 8000
```

⚡ Pruebas locales sin usar WhatsApp:
Puedes probar el bot directamente haciendo peticiones POST al endpoint:

```bash
POST http://localhost:8000/webhook
Form data:
- Body: Tu mensaje de prueba
- From: whatsapp:+521XXXXXXXXXX
```

6. Configura Twilio Sandbox webhook a `https://xxxx.ngrok.io/webhook`

## 🧰 Bonus: Multas con Visión por Computadora

Este bot incluye un flujo adicional para analizar **multas vehiculares** mediante un worker conectado a una cola **AWS SQS**. Este worker usa un modelo entrenado con TensorFlow Lite para procesar imágenes y reconocer placas vehiculares, retornando las multas asociadas.

Esto no estaba incluido en el challenge original, pero suma valor al demostrar integración con servicios cloud y uso de modelos de visión en producción.

## 🔄 Comandos Make Disponibles

- `make install`: Build e inicio del bot con Docker
- `make run`: Ejecuta sin rebuild
- `make stop`: Detiene contenedores
- `make down`: Detiene y elimina volúmenes
- `make logs`: Logs de backend
- `make test`: Corre tests automáticos
- `make clean`: Borra cachés y volúmenes


## 📊 Pruebas Automatizadas
El proyecto incluye una suite de pruebas automáticas usando `pytest` para validar escenarios clave del flujo conversacional del bot:
- Procesamiento de placas y consulta de multas.
- Simulaciones de financiamiento.
- Selección de autos.
- Comportamiento ante respuestas fuera de contexto.

Para ejecutarlas:
```bash
make test
```

## 🚀 Producción y Roadmap

- Despliegue: AWS ECS
- Seguridad: Validar webhook Twilio, manejar secretos con AWS SSM o Vault
- QA: Automatizar tests con GitHub Actions + Pytest
- Observabilidad: Logs estructurados, trazas por usuario
- Evaluación: KPIs de sesión, ratio de alucinaciones, feedback usuario

## 🔹 Diagramas

- Arquitectura General
```text
                        ╔══════════════════════════════╗
                        ║     Usuario en WhatsApp      ║
                        ╚══════════════════════════════╝
                                      │
                                      ▼
                        ╔══════════════════════════════╗
                        ║   Twilio WhatsApp Sandbox    ║
                        ╚══════════════════════════════╝
                                      │ Webhook (POST)
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AWS INFRAESTRUCTURE                                │
│                                                                              │
│  ╔════════════════════════════════════════════════════════════════════╗      │
│  ║      EC2 Instancia Principal (Bot conversacional - FastAPI)       ║      │
│  ║────────────────────────────────────────────────────────────────────║      │
│  ║  - API FastAPI (Webhook /webhook)                                 ║      │
│  ║  - Control de sesión por usuario                                  ║      │
│  ║  - Procesamiento de mensajes (regex, NLP, lógica FSM)             ║      │
│  ║  - Catálogo de autos (CSV cargado con pandas)                     ║      │
│  ║  - Contexto de Kavak (TXT)                                        ║      │
│  ║  - Módulo de financiamiento                                       ║      │
│  ║  - Módulo de recomendación de autos                               ║      │
│  ║  - Módulo de fallback LLM                                         ║      │
│  ║     └─▶ Llama a OpenAI GPT-4 con contextos controlados            ║      │
│  ║  - Envío a SQS si se detecta solicitud de MULTAS (BONUS)          ║      │
│  ╚════════════════════════════════════════════════════════════════════╝      │
│                                      │                                       │
│                                      ▼                                       │
│                         ╔══════════════════════════════╗                     │
│                         ║    OpenAI API (GPT-4)        ║  ◀─ context/prompt  │
│                         ╚══════════════════════════════╝                     │
│                                      ▲                                       │
│                        ┌────────────┘                                       │
│                        │                                                    │
│    ╔════════════════════════════════════════════════════════════════════╗    │
│    ║  EC2 Instancia Secundaria (BONUS: Worker OCR / Multas CDMX)       ║    │
│    ║────────────────────────────────────────────────────────────────────║    │
│    ║  - Corre en contenedor aislado                                     ║    │
│    ║  - Escucha AWS SQS: multas-cdmx-queue                              ║    │
│    ║  - Ejecuta modelo TFLite entrenado en OCR                          ║    │
│    ║  - Analiza imágenes capturadas de portales oficiales               ║    │
│    ║  - Extrae placas y folios, consulta multas y responde              ║    │
│    ╚════════════════════════════════════════════════════════════════════╝    │
│                        ▲                                                    │
│                        │                                                    │
│    ╔════════════════════════════════════════════════════════════════╗       │
│    ║         AWS SQS: multas-cdmx-queue (BONUS de arquitectura)     ║       │
│    ╚════════════════════════════════════════════════════════════════╝       │
└──────────────────────────────────────────────────────────────────────────────┘

```



- Flujo de Prompts/Decisiones
 ```text
                            ╔════════════════════╗
                            ║  MENSAJE ENTRANTE  ║
                            ╚════════════════════╝
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
╔════════════════════╗    ╔═══════════════════════╗       ╔════════════════════════╗
║ ¿Usuario quiere    ║    ║ ¿Esperando decisión   ║       ║ ¿Mensaje contiene      ║
║ cancelar la sesión?║    ║ de financiamiento?    ║       ║ número y hay autos     ║
╚════════════════════╝    ╚═══════════════════════╝       ║ en sesión activa?      ║
       │                       │                            ╚════════════════════════╝
       │Sí                     │Sí                                  │
       ▼                       ▼                                   Sí
[Limpiar sesión]      [Procesar respuesta:                    [Mostrar detalles del auto]
[Mensaje de salida]    “1” = sí / “2” = no]                   [Iniciar flujo de financiamiento]
       │                       │                                    │
       │                       ▼                                    ▼
       │               ╔══════════════════════╗          ╔════════════════════════╗
       │               ║ ¿Esperando enganche? ║          ║ ¿Esperando meses?     ║
       │               ╚══════════════════════╝          ╚════════════════════════╝
       │                       │                                    │
       │                 Sí    ▼                              Sí    ▼
       │                    [Validar enganche]                  [Validar plazo]
       │                    [Solicitar meses]                  [Calcular y mostrar plan]
       │                                                       [Terminar sesión]
       ▼
╔═════════════════════════╗
║ ¿Esperando placa para   ║
║ consulta de multas?     ║
╚═════════════════════════╝
           │
           │Sí
           ▼
   [Mandar mensaje a SQS]
   [Esperar respuesta de multas]
           ▼
    [Responder al usuario]

[...otros flujos simplificados...]
           ▼
╔═════════════════════════╗
║ ¿Mensaje con intención  ║──────▶ [Buscar en catálogo]
║ de búsqueda de auto?    ║
╚═════════════════════════╝

╔═════════════════════════╗
║ ¿Mensaje pregunta abierta? ║────▶ [Llamar a OpenAI con contexto]
╚═════════════════════════╝

╔══════════════════════╗
║ Ninguna opción válida║────▶ [Mensaje de error / fallback]
╚══════════════════════╝
 
```

- Worker de SQS con Modelo de Visión
 ```text
╔══════════════════════════════════════════╗
║      AWS SQS: multas-cdmx-queue         ║
╚══════════════════════════════════════════╝
                    │
                    ▼
         ╔════════════════════════════════╗
         ║  EC2 Instancia Secundaria     ║
         ║    (Worker OCR - Docker)      ║
         ╚════════════════════════════════╝
                    │
          ┌─────────┴────────────────────────────────────────────────┐
          ▼                                                          ▼
  [Recibe evento con placa]                                 [Descarga captcha]
          │                                                          │
          ▼                                                          ▼
 [Modelo OCR (TFLite) extrae texto]                       [Procesamiento imagen]
          │                                                          │
          ▼                                                          ▼
    [Consulta web/CDMX API]                         [Extrae multas del portal]
          │
          ▼
    [Crea respuesta estructurada]
          │
          ▼
    [Responde al bot via polling/respuesta directa]

```

---

🌟 *Proyecto construido para el challenge de AI Engineer con enfoque pragmático, seguro, reproducible y escalable.*
