<div align="center">
  
# 🎥 AI-Powered Video Tutorial Generator 🤖📝🎨

**Turn any topic into an engaging video tutorial featuring an AI instructor, synchronized lip movements with Wav2Lip, animated Manim scenes, and CLIP-ranked visuals.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)]()
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js&logoColor=white)]()
[![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20Enabled-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)]()

[Features](#-features) • [Architecture](#-architecture) • [Prerequisites](#-prerequisites) • [Setup & Installation](#-setup--installation) • [Configuration](#-configuration--environment-variables) • [Running the App](#-running-the-application) • [Customization](#-customizing-avatars--voices)

</div>

---

## 🌟 Overview

The **AI-Powered Video Tutorial Generator** is an end-to-end multimedia pipeline that turns any subject prompt (e.g., *"How OAuth 2.0 Works"*, *"Binary Search Explained"*, *"Neural Networks"*) into a full educational video tutorial.

The system plans pedagogical chapters, scripts narration tuned to audience age and expertise, synthesizes expressive speech, generates dynamic animations or searches for relevant imagery, lip-syncs a presenter avatar using high-performance **Wav2Lip**, and stitches everything into a 16:9 tutorial video with a picture-in-picture presenter.

---

## 🚀 Features

- **🧠 Intelligent Script Generation & Storyboarding**
  - Powered by LLMs (**Cerebras `gpt-oss-120b`**, **Google Gemini**, or **Cohere**) orchestrated with **LangChain** and **LangGraph**.
  - Formats scripts with pedagogical pacing, scene-by-scene timing, and clean pronunciation markers for Text-to-Speech.
- **🗣️ High-Performance Wav2Lip Lip-Sync**
  - Synthesizes realistic presenter mouth movements onto character portraits.
  - **Batch In-Memory Execution:** Preloads PyTorch and face detection models once to eliminate cold-start overhead, providing multi-fold speedups on NVIDIA GPUs.
- **🎨 Hybrid Visual Engine**
  - **Manim Animations:** Renders programmatic mathematical, algorithmic, and diagrammatic scenes directly via Python code execution.
  - **Multi-Provider Image Retrieval:** Fetches relevant slides and images from Pixabay, Unsplash, Wikimedia Commons, and Giphy.
  - **CLIP Semantic Reranking:** Leverages OpenAI CLIP (`clip-vit-base-patch32`) to semantically match and rank visual assets against narration queries.
- **🎙️ Natural Voice Synthesis**
  - Microsoft Edge-TTS integration produces clear, expressive audio across dozens of accents and languages without robotic monotone.
- **🎬 Automated Composition & Stitching**
  - Composites slide visuals, Manim animations, and the animated Wav2Lip presenter into a unified 16:9 presentation layout with smooth audio-video synchronization.
- **🔄 Fault-Tolerant Pipeline State**
  - Resumable stage checkpoints (`checkpoint_manager.py`) and DAG evaluation ensure failed or interrupted renders can resume without recomputing completed stages.

---

## 🏗️ Architecture

```
User Prompt (Topic, Level, Age, Tone)
        │
        ▼
[1. Script & Storyboard Planning] ──── (Cerebras / Gemini / Cohere via LangGraph)
        │
        ├──────────────────────────────────────────┐
        ▼                                          ▼
[2. Voice Synthesis]                       [3. Visual Pipeline]
   (Edge-TTS -> Audio Chunks)                 (Parallel Dispatch)
        │                                          │
        ▼                                    ┌─────┴──────────────┐
[4. Wav2Lip Lip-Sync]                        ▼                    ▼
   (In-Memory GPU Batch Engine)      [Manim Renderer]    [Image Search + CLIP]
   (Avatar Face + Narration)         (Math/Code scenes)  (Pixabay/Unsplash/Giphy)
        │                                    │                    │
        └───────────────────┬────────────────┴────────────────────┘
                            ▼
              [5. Video Composition & Stitching]
                 (OpenCV + FFmpeg Concat & PIP)
                            │
                            ▼
                    Final Tutorial MP4
```

---

## 📋 Prerequisites

Before installing, ensure your system has the following tools installed and available in your environment path:

1. **Python 3.10+** (Python 3.10 or 3.11 recommended).
2. **Node.js 18+** & **npm** (for the Next.js frontend).
3. **FFmpeg**: Must be installed and accessible via system `PATH`.
   - *Windows (via winget):* `winget install Gyan.FFmpeg`
   - *Ubuntu/Debian:* `sudo apt install ffmpeg`
   - *macOS (via Homebrew):* `brew install ffmpeg`
   - Verify by running `ffmpeg -version` in your terminal.
4. **NVIDIA GPU + CUDA** *(Highly Recommended)*:
   - For fast Wav2Lip inference and CLIP processing. A GPU with 4GB+ VRAM (e.g. GTX 1650 or higher) is recommended.
   - CPU inference is supported as a fallback.

---

## 🛠️ Setup & Installation

### Step 1: Clone the Repository & Submodules

Clone this repository and initialize its submodules (required for Wav2Lip):

```bash
git clone https://github.com/rushiBhatt01/Ai_tutor.git
cd Ai_tutor
git submodule update --init --recursive
```

---

### Step 2: Download Model Weights (Wav2Lip & Face Detection)

Wav2Lip requires pre-trained model weights. Place the checkpoints in the following locations:

1. **Wav2Lip Generator Checkpoint**:
   - Download `wav2lip_gan.pth` (or `wav2lip.pth`) from the official [Wav2Lip repository](https://github.com/Rudrabha/Wav2Lip#getting-the-weights).
   - Place the file inside:
     ```
     backend/Wav2Lip/checkpoints/wav2lip_gan.pth
     ```
2. **Face Detection Checkpoint (S3FD)**:
   - Ensure `s3fd.pth` is available at:
     ```
     backend/Wav2Lip/face_detection/detection/sfd/s3fd.pth
     ```

---

### Step 3: Backend Setup

1. Open a terminal and navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   - **Windows:**
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **Linux / macOS:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```

3. Install the dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   > **GPU Note for PyTorch:** If you have an NVIDIA GPU, ensure PyTorch is installed with CUDA support. You can verify this inside Python:
   > ```python
   > import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))
   > ```

4. Create your `.env` file inside `backend/`:
   ```bash
   cp .env.example .env   # Or create a new .env file
   ```
   Configure your API keys (see [Configuration section](#-configuration--environment-variables) below).

---

### Step 4: Frontend Setup

1. Open another terminal and navigate to the frontend directory:
   ```bash
   cd frontend/topic2explanation
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the `backend/` directory. Populate it with the keys for the services you want to enable:

```env
# Runtime environment
ENVIRONMENT=local

# Primary LLM Options (At least one is required)
CEREBRAS_API_KEY="your-cerebras-key"
CEREBRAS_MODEL="gpt-oss-120b"
GEMINI_API_KEY="your-gemini-key"
COHERE_API_KEY="your-cohere-key"

# Visual Media Search Providers
PIXABAY_API_KEY="your-pixabay-key"
UNSPLASH_ACCESS_KEY="your-unsplash-key"
giphy="your-giphy-key"

# Pipeline Feature Flags
IMAGE_PROVIDERS="pixabay,wikimedia_commons,unsplash"
IMAGE_SEARCH_ENABLED=true
MANIM_ENABLED=true

# Optional MongoDB Database (Leave empty for local filesystem runs)
MONGO_URI=""
```

---

## 🚀 Running the Application

### 1. Start the Backend API

From the `backend/` directory (with your `.venv` activated):

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
- API Documentation (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)

### 2. Start the Frontend UI

From the `frontend/topic2explanation/` directory:

```bash
npm run dev
```
Open your browser and navigate to **[http://localhost:3000](http://localhost:3000)**.

---

## 🎨 Customizing Avatars & Voices

### Changing or Adding Characters
1. Place a high-quality portrait image (`.png` or `.jpg`) in `backend/characters/` (e.g. `backend/characters/MyPresenter.png`).
2. Recommended portrait resolution: `640x720` or clear square portrait with the face centrally positioned.

### Changing Edge-TTS Voices
1. List all available multi-lingual voices using the Edge-TTS CLI:
   ```bash
   edge-tts --list-voices
   ```
2. Map your character to a voice in [backend/functions/create_audio_image_function.py](file:///c:/Users/Rushi/OneDrive/Desktop/FILES/DEVPROJECT/API-BASED-Video-Tutorial-Generator/backend/functions/create_audio_image_function.py):
   ```python
   character_dict = {
       "Benjamin": "en-IE-ConnorNeural",
       "Sophia": "en-US-JennyNeural",
       "MyPresenter": "en-GB-SoniaNeural"
   }
   ```

---

## 📁 Project Structure

```
├── backend/
│   ├── Wav2Lip/                  # Wav2Lip submodule & checkpoints
│   │   ├── checkpoints/          # Put wav2lip_gan.pth here
│   │   └── inference.py          # Optimized batch in-memory lip-sync
│   ├── characters/               # Presenter portrait images (Benjamin, Sophia, face.png)
│   ├── functions/                # Pipeline orchestrator modules
│   │   ├── video_main_function.py         # Main generation pipeline
│   │   ├── create_script_function.py      # LLM script planning
│   │   ├── create_storyboard_function.py  # Storyboard segment generation
│   │   ├── create_speech_function.py      # Edge-TTS voice synthesis
│   │   ├── create_video_from_audio_function.py # Wav2Lip batch invoker
│   │   ├── manim_renderer.py              # Dynamic Manim animation renderer
│   │   ├── semantic_visual_matcher.py     # CLIP text-image semantic reranker
│   │   ├── image_providers.py             # Pixabay/Unsplash/Wikimedia search
│   │   ├── combine_videos_function.py     # Video stitching & PIP layout
│   │   └── checkpoint_manager.py          # Resumable stage state management
│   ├── main.py                   # FastAPI application entry point
│   └── requirements.txt          # Python dependencies
│
├── frontend/
│   └── topic2explanation/       # Next.js 14 Web Application
│       ├── app/                  # React UI components & routes
│       └── public/prev_videos/   # Rendered video outputs and cache
│
├── checkpoints/                  # Global pipeline checkpoints
├── cache/                        # Cached search queries and media assets
└── Readme.md                     # Documentation
```

---

## ❓ Troubleshooting

- **`ffmpeg: command not found`**  
  Ensure FFmpeg is installed and added to your system's `PATH`. Restart your terminal after installing.
- **Wav2Lip runs slowly on CPU**  
  Verify that your NVIDIA drivers and CUDA-enabled PyTorch are installed (`torch.cuda.is_available()` returns `True`). The project uses optimized batch execution that processes all chunks in memory once GPU acceleration is active.
- **Missing `wav2lip_gan.pth`**  
  Ensure the checkpoint is downloaded and placed into `backend/Wav2Lip/checkpoints/wav2lip_gan.pth`.
- **Manim installation on Linux/macOS**  
  If Manim scenes fail to render, ensure system libraries like Cairo and Pango are installed (`sudo apt install libcairo2-dev libpango1.0-dev`).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
