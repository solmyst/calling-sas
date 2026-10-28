"""Silero v5 ONNX inference with isolated recurrent state per microphone session.

I/O follows the upstream v5.1.2 OnnxWrapper (MIT, bundled in models/).
No model downloads or telemetry happen at runtime.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort


@lru_cache(maxsize=1)
def model_session():
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(
        str(Path(__file__).parent / "models/silero_vad_v5.onnx"),
        sess_options=options, providers=["CPUExecutionProvider"],
    )


class SileroVad:
    frame_ms = 32

    def __init__(self, session=None):
        self.session = session or model_session()
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)
        self.speech_ms = self.silence_ms = 0
        self.speaking = False

    def process(self, pcm, playback=False):
        if len(pcm) != 1024:
            raise ValueError("Silero requires 512 mono int16 samples at 16 kHz")
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32).reshape(1, -1) / 32768
        value = np.concatenate((self.context, samples), axis=1)
        prediction, self.state = self.session.run(None, {
            "input": value, "state": self.state, "sr": np.array(16000, dtype=np.int64),
        })
        self.context = value[:, -64:].copy()
        probability = float(prediction[0][0])
        rms = float(np.sqrt(np.mean(samples * samples)))
        threshold = 0.72 if playback else 0.58
        # Sustained neural speech plus an energy floor filters keyboard clicks,
        # short coughs and quiet residual echo. AEC remains the echo protection.
        if probability >= threshold and rms >= 0.008:
            self.speech_ms += self.frame_ms
            self.silence_ms = 0
            if not self.speaking and self.speech_ms >= 128:
                self.speaking = True
                return {"type": "vad_speech_start", "engine": "silero-v5",
                        "speech_ms": self.speech_ms, "probability": round(probability, 3)}
        else:
            self.silence_ms += self.frame_ms
            if not self.speaking and self.silence_ms > 64:
                self.speech_ms = 0
            elif self.speaking and self.silence_ms >= 384:
                self.speaking = False
                self.speech_ms = 0
                return {"type": "vad_speech_end", "engine": "silero-v5"}
        return None
