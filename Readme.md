<div align="center">
  
# 🎥 AI Video Tutorial Generator (Wav2Lip Integration) 🤖📝🎨
  
**Turn any topic into an engaging video tutorial with a realistic AI instructor using Wav2Lip.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-ai--powered--tutor.vercel.app-00C7B7?style=for-the-badge&logo=vercel)](https://ai-powered-tutor.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)]()

[View Demo](#-demo) • [Features](#-features) • [Installation](#-installation--setup) • [How It Works](#-how-it-works)

</div>

---

## 🌟 Introduction

This AI tool helps you create captivating and informative AI-generated video tutorials on any topic! Featuring realistic **Wav2Lip** facial lip-syncing animations and dynamic visual slides, it explains any subject with ease.

> Set the audience level, tone, creativity, and humor to shape exactly how your tutorial is taught.

---

## 🚀 Features

* **🧠 Intelligent Script Generation**  
  Cohere's semantic analysis combined with Langchain creates coherent, audience-targeted teaching scripts from just a simple topic prompt.
* **🗣️ Realistic AI Instructor (Wav2Lip)**  
  Wav2Lip generates precise, lifelike lip-sync animations from audio narration onto character portraits, giving every tutorial a personalized face.
* **🎙️ Natural Voice Synthesis**  
  Microsoft Edge TTS produces clear, expressive narration with tunable energy and pacing—no robotic monotone.
* **🖼️ Automated Visual Retrieval**  
  Relevant images and slides are dynamically fetched for each script segment to build a visually engaging narrative.
* **⚡ API-First Architecture**  
  Every capability is exposed through clean API endpoints for easy programmatic integration into your own tools.
* **🎛️ Fully Customizable Output**  
  Control audience age, explanation depth, creativity level, and humor.

---

## ✨ Demo

<div align="center">
  <table>
    <tr>
      <td align="center"><b>The Interface</b></td>
      <td></td>
    </tr>
    <tr>
      <td width="50%" valign="middle"><video src="demo.mp4" width="100%" controls></video></td>
    </tr>
  </table>
</div>

---

## 🚨 Installation & Setup

> **Note:** Open up a terminal and navigate to the `backend` directory before starting.

### 1️⃣ Python Environment

**For Windows:**
```sh
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**For Linux or Mac:**
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2️⃣ Wav2Lip & Model Checkpoints
Ensure the Wav2Lip model checkpoint files are placed inside `backend/Wav2Lip/checkpoints/`:
1. Download `wav2lip_gan.pth` (or `wav2lip.pth`).
2. Place the `.pth` files in `backend/Wav2Lip/checkpoints/` (e.g. `backend/Wav2Lip/checkpoints/wav2lip_gan.pth`).

### 3️⃣ Environment & API Keys
Create a `.env` file in your `backend/` directory and add your keys and environment configuration:
```env
COHERE_API_KEY=your_api_key_here
ENVIRONMENT=local
```

---

## 🔌 How to Use

1. **Start the Frontend Development Server:**
   Open a terminal, go to `frontend/topic2explanation`, and run:
   ```sh
   npm run dev
   ```

2. **Start the Backend API:**
   Open another terminal, go to the `backend` folder, and run:
   ```sh
   uvicorn main:app
   ```

---

## 🎨 Customizability 

Want to change the character and voice? 
1. Put your desired character portrait in the `characters` directory (must be standard resolution e.g. `640x720`).
2. Choose a voice from the Edge-TTS library. List available voices using:
   ```sh
   edge-tts --list-voices
   ```
3. Once you find a voice you like, map it to your character in `functions/create_audio_image_function.py`:
   ```python
   character_dict = {
     'Benjamin': "en-IE-ConnorNeural",
     'Sophia': 'ar-SA-ZariyahNeural'
   }
   ``` 

---

## 📝 How It Works

**01. Enter your topic**  
Type any subject — from API authentication to machine learning basics. Set the audience level, tone, creativity, and humor to shape how the tutorial is taught.

**02. AI writes the script**  
Cohere and Langchain collaborate to transform your topic into a structured, audience-aware teaching script with clear chapters and natural transitions.

**03. Voice, visuals & Wav2Lip video**  
Edge TTS synthesizes natural narration, relevant images are retrieved automatically, and Wav2Lip animates the realistic AI instructor with synchronized lip movements — all composed into a polished tutorial video.

---

## 📂 Saved Videos
Looking for the tutorials you've already generated? All completed videos are automatically saved in the `frontend/topic2explanation/public/prev_videos/` directory inside this repository. You can find both the final videos and intermediate assets organized by timestamp folders there!

