import os
import base64
import subprocess
from flask import Flask, request, jsonify,render_template
from flask_cors import CORS
import requests
import replicate
import io
from PIL import Image
from datetime import datetime

app = Flask(__name__)
CORS(app)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.route("/")
def home():
    return render_template("app.js")

# Configuration
CONFIG = {
    "REPLICATE_API_KEY": "",
    "HUGGINGFACE_API_KEY": "",
    "ELEVENLABS_API_KEY": "your-elevenlabs-key",
    "WAV2LIP_PATH": "./Wav2Lip",
    "TEMP_FOLDER": "./temp",
    "AI_MODEL": "facebook/blenderbot-400M-distill",
    "TTS_VOICE_ID": "21m00Tcm4TlvDq8ikWAM",
    "AVATAR_MODEL": ""
}

# Create temp folder if not exists
os.makedirs(CONFIG["TEMP_FOLDER"], exist_ok=True)

class AvatarGenerator:
    @staticmethod
    def generate(prompt, image_data):
        """Generate avatar image from selfie"""
        try:
            if image_data.startswith("data:"):
                image_bytes = base64.b64decode(image_data.split(",")[1])
                image_url = AvatarGenerator.upload_to_replicate(image_bytes)
            else:
                image_url = image_data

            output = replicate.run(
                CONFIG["AVATAR_MODEL"],
                input={
                    "prompt": f"{prompt}, high-quality digital avatar, detailed facial features",
                    "image": image_url,
                    "strength": 0.65,
                    "guidance_scale": 7.5,
                    "num_inference_steps": 30
                }
            )
            return AvatarGenerator.url_to_base64(output[0])
        
        except Exception as e:
            print(f"⚠️ Avatar generation error: {str(e)}")
            return image_data

    @staticmethod
    def upload_to_replicate(image_bytes):
        """Upload image to Replicate's temporary storage"""
        response = requests.post(
            "https://api.replicate.com/v1/uploads",
            headers={"Authorization": f"Token {CONFIG['REPLICATE_API_KEY']}"},
            json={"name": f"avatar_input_{datetime.now().timestamp()}.jpg"}
        )
        upload_url = response.json()["upload_url"]
        requests.put(upload_url, data=image_bytes)
        return response.json()["url"]

    @staticmethod
    def url_to_base64(image_url):
        """Convert image URL to base64 data URI"""
        response = requests.get(image_url)
        img_bytes = io.BytesIO(response.content)
        return f"data:image/jpeg;base64,{base64.b64encode(img_bytes.getvalue()).decode('utf-8')}"

class AIAssistant:
    @staticmethod
    def generate_response(prompt):
        """Generate text response using HuggingFace model"""
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{CONFIG['AI_MODEL']}",
                headers={"Authorization": f"Bearer {CONFIG['HUGGINGFACE_API_KEY']}"},
                json={"inputs": prompt}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('generated_text', "Sorry, I couldn't generate a response.")
            return f"API Error: {response.status_code}"
        
        except Exception as e:
            print(f"⚠️ AI response error: {str(e)}")
            return "I'm having trouble responding right now."

class VoiceSynthesizer:
    @staticmethod
    def text_to_speech(text, output_path):
        """Convert text to speech using ElevenLabs"""
        try:
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{CONFIG['TTS_VOICE_ID']}",
                headers={
                    "xi-api-key": CONFIG["ELEVENLABS_API_KEY"],
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5
                    }
                }
            )
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"⚠️ TTS error: {str(e)}")
            return False

class LipSyncEngine:
    @staticmethod
    def sync(face_path, audio_path, output_path):
        """Run Wav2Lip synchronization"""
        try:
            subprocess.run([
                "python", f"{CONFIG['WAV2LIP_PATH']}/inference.py",
                "--checkpoint_path", f"{CONFIG['WAV2LIP_PATH']}/checkpoints/wav2lip_gan.pth",
                "--face", face_path,
                "--audio", audio_path,
                "--outfile", output_path,
                "--pads", "0", "10", "0", "0"
            ], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Lip sync error: {str(e)}")
            return False

@app.route('/api/process', methods=['POST'])
def process_request():
    """Main processing endpoint"""
    try:
        data = request.json
        if not data or 'text' not in data or 'image' not in data:
            return jsonify({"error": "Missing required fields"}), 400

        # Generate unique filenames for this session
        session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        avatar_path = f"{CONFIG['TEMP_FOLDER']}/avatar_{session_id}.jpg"
        audio_path = f"{CONFIG['TEMP_FOLDER']}/audio_{session_id}.wav"
        output_path = f"{CONFIG['TEMP_FOLDER']}/output_{session_id}.mp4"

        # Step 1: Generate AI response
        ai_text = AIAssistant.generate_response(data['text'])
        
        # Step 2: Generate avatar
        avatar_data = AvatarGenerator.generate(ai_text, data['image'])
        with open(avatar_path, "wb") as f:
            f.write(base64.b64decode(avatar_data.split(",")[1]))
        
        # Step 3: Convert text to speech
        if not VoiceSynthesizer.text_to_speech(ai_text, audio_path):
            return jsonify({"error": "TTS service failed"}), 500
        
        # Step 4: Lip sync
        if not LipSyncEngine.sync(avatar_path, audio_path, output_path):
            return jsonify({"error": "Lip sync failed"}), 500
        
        # Prepare response
        with open(output_path, "rb") as f:
            video_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Clean up temporary files
        for file in [avatar_path, audio_path, output_path]:
            try:
                os.remove(file)
            except:
                pass
        
        return jsonify({
            "success": True,
            "text": ai_text,
            "video": f"data:video/mp4;base64,{video_data}",
            "avatar": avatar_data
        })
        
    except Exception as e:
        print(f"⚠️ System error: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5001,debug=False,threaded=True)