import React, { useEffect, useState } from 'react';
import '../globals.css';


const SplashScreen = () => {
  const [isVisible, setIsVisible] = useState(true);
  const [text, setText] = useState('');
  const textToType = "E duGenPro"; // Set the text you want to type

  useEffect(() => {
    let index = 0;
    const timer = setInterval(() => {
      if (index < textToType.length) {
        setText(prevText => prevText + textToType.charAt(index));
        index++;
      } else {
        clearInterval(timer);
        setTimeout(() => {
          setIsVisible(false);
        }, 2000); // Set the timeout to control how long the typing animation should last
      }
    }, 200); // Set the interval to control the typing speed

    return () => clearInterval(timer);
  }, []);

  return (
    <div className={`splashScreen ${isVisible ? 'visible' : 'hidden'}`}>
      <div className="splashContent">
        <h1 className="splashTitle"> {/* Container for the text */}
          <span className="typingText">{text}</span> {/* Element to display the typing animation */}
        </h1>
      </div>
    </div>
  );
};

export default SplashScreen;
