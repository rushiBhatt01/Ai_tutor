/* eslint-disable react/no-unescaped-entities */

export default function Box3() {
  
  return (
  
      <div className="p-6 rounded-lg shadow-lg bg-white">
        <h1 className="text-3xl font-semibold mb-4">API-Generated Video Tutorials with Character Animation and Slides! 🎥🤖📝🎨</h1>
        
        <p className="mb-4">
          This API tool helps you create captivating and informative AI-generated video tutorials on any topic! With a charming character featuring facial animation and informative slides, it can explain any topic with ease. The best part? You have full control over the tutorial's creativity, humor, level of explanation, character appearance, and voice. ❤️✨
        </p>
        
        <p className="mb-4">
          Give it a try for free! 🔥 It leverages the powerful capabilities of various tools.
        </p>
        <div>
        <h1 className="text-2xl font-semibold mt-8 mb-4">#Demo Video</h1>
        <iframe className="glass p-5"
        width="560" 
        height="355" 
        src="https://www.youtube.com/embed/-z5eBtuj-LY?si=qU8H_FQy06L59CUG" 
        frameborder="0" 
        allow="accelerometer; 
        autoplay; 
        clipboard-write; 
        encrypted-media; gyroscope; 
        picture-in-picture"
        allowfullscreen>

        </iframe>
        <iframe className="glass p-5"
        width="560" height="315" src="https://www.youtube.com/embed/8dO3aFn58Zo?si=qk8sWbu0r4Zoiq8T" 

        frameborder="10"  
        allowfullscreen>
        </iframe>
        </div>
        <h2 className="text-2xl font-semibold mt-8 mb-4">🚀 Features</h2>
        <ul className="list-disc pl-6 mb-4">
          <li>🧠 The script is generated using Cohere's language model. (You can obtain a trial API key for free!)</li>
          <li>🗣 Seamless integration with Edge TTS for high-quality voiceovers.</li>
          <li>😄 Engaging facial animation powered by SadTalker.</li>
          <li>🖼 Eye-catching and relevant images from Google for slides.</li>
          <li>🎨 Customizable creativity, humor, explanation level, character appearance, and voice.</li>
        </ul>
  
        
        
        <h2 className="text-2xl font-semibold">📝 How it works</h2>
        <p className="mb-4">
          ✨ It all starts with the creation of a script using the create_script function. 📜 This function takes various parameters such as topic, level of explanation, target audience age, creativity, and humor. 🎭 With these parameters in mind, the script is carefully crafted to explain the chosen topic. To accomplish this, we leverage the power of the Cohere API and Langchain. 🤝
        </p>
        
        <p className="mb-4">
          🎙️ Once the script is ready, we move on to the create_audio_image function. This function splits the script into smaller sentences, which are then used to generate audio dialogues using Microsoft's Edge Text-to-Speech (TTS) service. 🗣️ In parallel, we generate a search query for each sentence using Cohere and Langchain once again. These search queries help us retrieve relevant images from Google, which will be used as slides in the presentation. 🖼️
        </p>
  
        <p className="mb-4">
          🎥 With the audio files and character images in place, we proceed to create the videos using the Sadtalker library. 🎬 First, we generate videos for the character animations, and then we transform the still images from Google into slide videos. 🎞️ These slide videos will be seamlessly integrated into the final video presentation. To add an element of randomness, we assign a random number to each video and slide pair. Based on this number, we position the slides and talking character either to the left or right, or even use the image as the background. The talking character may appear in the bottom left or right corner of the screen. 🎯
        </p>
  
        <p className="mb-4">
          📼 Finally, we save the completed video, combining the slide videos and character animation videos. The resulting video is now ready to be shared! 🎉 To bring it all together, we rely on FastAPI for the backend, and for the frontend, we utilize Next.js and Tailwind CSS. 🚀
        </p>
      </div>
    );
  }
