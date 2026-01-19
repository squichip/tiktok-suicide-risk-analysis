import cv2
import os
from deepface import DeepFace

# ======================================================
# FACE FEATURES (5 FRAME – 1 TANESİ YETER)
# ======================================================

def extract_face_features(video_path: str):
    """
    Videodan 5 farklı frame alır.
    Eğer bu frame'lerin herhangi birinde yüz bulunursa:
        - face_detected = True
        - dominant emotion + score döner
    Hiçbir frame'de yüz yoksa:
        - face_detected = False
        - emotion = None
        - score = 0.0
    """

    if not video_path or not os.path.exists(video_path):
        return {
            "face_detected": False,
            "face_dominant_emotion": None,
            "face_emotion_score": 0.0,
        }

    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if frame_count <= 0:
        cap.release()
        return {
            "face_detected": False,
            "face_dominant_emotion": None,
            "face_emotion_score": 0.0,
        }

    # Videonun %10, %30, %50, %70, %90 noktaları
    frame_indices = [
        int(frame_count * 0.10),
        int(frame_count * 0.30),
        int(frame_count * 0.50),
        int(frame_count * 0.70),
        int(frame_count * 0.90),
    ]

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        try:
            analysis = DeepFace.analyze(
                frame,
                actions=["emotion"],
                enforce_detection=True,
                silent=True,
            )

            if isinstance(analysis, list):
                analysis = analysis[0]

            dominant = analysis.get("dominant_emotion")
            emotions = analysis.get("emotion", {})

            if dominant and dominant in emotions:
                score = float(emotions[dominant])

                cap.release()
                return {
                    "face_detected": True,
                    "face_dominant_emotion": dominant,
                    "face_emotion_score": round(score, 2),
                }

        except Exception:
            # Bu frame'de yüz yok → diğer frame'e geç
            continue

    cap.release()

    # Hiçbir frame'de yüz bulunamadı
    return {
        "face_detected": False,
        "face_dominant_emotion": None,
        "face_emotion_score": 0.0,
    }
