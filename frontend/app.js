import React, { useState, useRef, useEffect } from 'react';
import './styles.css';

function App() {
  const [snapshot, setSnapshot] = useState(null);
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [cameraError, setCameraError] = useState(null);
  const [apiError, setApiError] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Initialize camera with better error handling
  useEffect(() => {
    let stream = null;
    
    const initCamera = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: "user" 
          }
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          setCameraError(null);
        }
      } catch (err) {
        console.error("Camera Error:", err);
        setCameraError("Could not access camera. Please check permissions.");
      }
    };

    initCamera();
    
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const takeSnapshot = () => {
    try {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      
      if (!video || !canvas) {
        throw new Error("Camera or canvas not available");
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      const imageQuality = 0.9; // 90% quality
      setSnapshot(canvas.toDataURL('image/jpeg', imageQuality));
    } catch (err) {
      console.error("Snapshot Error:", err);
      setApiError("Failed to capture image");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      // Try multiple connection methods
      const endpoints = [
        'http://127.0.0.1:3000/api/process',  // First try IP
        'http://localhost:3000/api/process',   // Then try localhost
        '/api/process'                         // Fallback to proxy
      ];
      
      let response;
      for (const endpoint of endpoints) {
        try {
          response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              text: query, 
              image: snapshot 
            })
          });
          if (response.ok) break;
        } catch (e) {
          console.log(`Attempt failed: ${endpoint}`);
        }
      }
  
      if (!response?.ok) {
        throw new Error(`
          Connection failed. Please verify:
          1. Flask server is running (see terminal)
          2. No port conflicts (netstat -ano | findstr :5000)
          3. CORS is properly configured
        `);
      }
      
      const data = await response.json();
      setResponse(data);
      
    } catch (err) {
      console.error("API Error:", err);
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRetakePhoto = () => {
    setSnapshot(null);
    setResponse(null);
    setApiError(null);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>AI Avatar Chat</h1>
        <p>Take a selfie and chat with your AI avatar</p>
      </header>

      <main className="main-content">
        <section className="camera-section">
          {cameraError ? (
            <div className="error-message">
              {cameraError}
              <button 
                onClick={() => window.location.reload()}
                className="retry-btn"
              >
                Try Again
              </button>
            </div>
          ) : (
            <>
              <div className="video-container">
                <video 
                  ref={videoRef} 
                  autoPlay 
                  playsInline 
                  muted 
                  className={snapshot ? 'video-hidden' : ''}
                />
                {snapshot && (
                  <div className="preview-container">
                    <img src={snapshot} alt="Your avatar" className="preview" />
                  </div>
                )}
              </div>
              <div className="controls">
                {!snapshot ? (
                  <button 
                    className="snap-btn"
                    onClick={takeSnapshot}
                    disabled={loading || cameraError}
                  >
                    Take Snapshot
                  </button>
                ) : (
                  <button 
                    className="retake-btn"
                    onClick={handleRetakePhoto}
                    disabled={loading}
                  >
                    Retake Photo
                  </button>
                )}
              </div>
            </>
          )}
          <canvas ref={canvasRef} style={{ display: 'none' }} />
        </section>

        <section className="chat-section">
          {apiError && (
            <div className="error-message">
              {apiError}
              {apiError.includes("backend") && (
                <button 
                  onClick={handleSubmit}
                  className="retry-btn"
                >
                  Retry
                </button>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="chat-form">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask me anything..."
              disabled={loading || !snapshot}
              className="chat-input"
              aria-label="Chat input"
            />
            <button
              type="submit"
              disabled={loading || !snapshot || !query.trim()}
              className="submit-btn"
              aria-busy={loading}
            >
              {loading ? (
                <>
                  <span className="spinner" aria-hidden="true"></span> 
                  <span className="sr-only">Processing...</span>
                </>
              ) : 'Send'}
            </button>
          </form>

          {response && (
            <div className="response-container">
              <div className="avatar-response">
                <video 
                  src={response.video} 
                  controls 
                  autoPlay 
                  loop
                  className="avatar-video"
                  aria-label="AI avatar response"
                />
              </div>
              <div className="text-response">
                <p>{response.text}</p>
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <p>© {new Date().getFullYear()} AI Avatar Chat</p>
      </footer>
    </div>
  );
}

export default App;