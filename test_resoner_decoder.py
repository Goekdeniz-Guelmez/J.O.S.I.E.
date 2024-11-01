import torch
import pyaudio
import numpy as np
from args import ModelArgs
from audio import AudioEncoderDecoder
from reasoner import ReasonerTransformer

# Initialize audio parameters
RATE = 16000  # Sample rate
CHUNK = 16000 // 4  # Buffer size
FORMAT = pyaudio.paFloat32
CHANNELS = 1

# Initialize models
audio = AudioEncoderDecoder(ModelArgs)
model = ReasonerTransformer(ModelArgs)


def generate_audio_chunk():
    """Generate a single chunk of audio"""
    # Sample input tokens
    inp = torch.tensor([[312, 1542, 3456, 23, 4, 51, 34, 7]])
    
    # Generate text and audio streams
    text_stream, audio_stream = model(inp)
    
    # Decode audio
    output = audio.decode(audio_stream)
    
    # Convert to numpy array
    audio_output = output.squeeze().detach().numpy()
    
    return audio_output



def main():
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # Open stream
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        output=True,
        frames_per_buffer=CHUNK
    )
    
    print("Starting continuous audio generation... (Ctrl+C to stop)")
    
    try:
        while True:
            # Generate and play audio
            audio_output = generate_audio_chunk()
            stream.write(audio_output.astype(np.float32).tobytes())
            
    except KeyboardInterrupt:
        print("\nStopping audio generation...")
        
    finally:
        # Clean up
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()