<div align="center">
  
# 🎥 AI Video Tutorial Generator 🤖📝🎨
  
**Turn any topic into an engaging video tutorial with a realistic AI instructor.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-ai--powered--tutor.vercel.app-00C7B7?style=for-the-badge&logo=vercel)](https://ai-powered-tutor.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)]()

[View Demo](#-demo) • [Features](#-features) • [Installation](#-installation--setup) • [How It Works](#-how-it-works)

</div>

---

## 🌟 Introduction

This AI tool helps you create captivating and informative AI-generated video tutorials on any topic! With a charming character featuring facial animation and informative slides, it can explain any subject with ease. 

> Set the audience level, tone, creativity, and humor to shape exactly how your tutorial is taught.

---

## 🚀 Features

* **🧠 Intelligent Script Generation**  
  Cohere's semantic analysis combined with Langchain creates coherent, audience-targeted teaching scripts from just a simple topic prompt.
* **🗣️ Realistic AI Instructor**  
  SadTalker generates a lifelike character animation that lip-syncs to the narration, giving every tutorial a human face and making content feel personal.
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
  <video src="https://github.com/AkshitIreddy/AI-Powered-Video-Tutorial-Generator/assets/90443032/0a1fb05a-8290-4391-b329-96f04dcae7a1" width="100%" controls></video>
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

### 2️⃣ SadTalker & AI Models
Also install SadTalker (Follow their [official guide](https://github.com/OpenTalker/SadTalker#%EF%B8%8F-1-installation)) inside the `backend` directory.
1. Run the SadTalker `webui.bat` (Windows) or `webui.sh` (Linux/Mac) once. This creates the venv environment and downloads the necessary AI models (`checkpoints` and `gfpgan`).
2. After the models are downloaded, copy the `checkpoints` and `gfpgan` folders from inside `backend/SadTalker/` and paste them directly into the root `backend/` directory.

### 3️⃣ API Keys
Create a `.env` file in your `backend/` directory and add your Cohere API key:
```env
COHERE_API_KEY=your_api_key_here
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
1. Put your desired character portrait in the `characters` directory (must be exactly `640x720` resolution).
2. Choose a voice from the Edge-TTS library. List available voices using:
   ```sh
   edge-tts --list-voices
   ```
3. Once you find a voice you like, map it to your character in the `functions/create_audio_image_function.py` or equivalent:
   ```python
   character_dict = {
     'Benjamin': "en-GB-RyanNeural",
     'Sophia': 'en-IE-EmilyNeural'
   }
   ``` 

---

## 📝 How It Works

**01. Enter your topic**  
Type any subject — from API authentication to machine learning basics. Set the audience level, tone, creativity, and humor to shape how the tutorial is taught.

**02. AI writes the script**  
Cohere and Langchain collaborate to transform your topic into a structured, audience-aware teaching script with clear chapters and natural transitions.

**03. Voice, visuals & video**  
Edge TTS synthesizes natural narration, relevant images are retrieved automatically, and SadTalker animates a realistic AI instructor — all composed into a polished tutorial video.

---

## 📂 Saved Videos
Looking for the tutorials you've already generated? All completed videos are automatically saved in the `backend/prev_videos/` directory inside this repository. You can find both the final videos and intermediate assets organized by timestamp folders there!
