import os
import re
import time
import uuid
import argparse
import subprocess
import requests
import pandas as pd
import cv2
import easyocr
from collections import Counter
from playwright.sync_api import sync_playwright

# YÜZ ANALİZİ
from face_features import extract_face_features
# ===========================
# BERT RISK MODEL (LOCAL)
# ===========================
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR_NAME = "my_suicide_bert_model"  # proje klasöründe bu isimle durmalı

_tokenizer = None
_model = None
_device = None
_risk_index = None  # logits içinde "risk" sınıfının index'i

def _load_risk_model(script_dir: str):
    global _tokenizer, _model, _device, _risk_index
    if _model is not None:
        return

    model_dir = os.path.join(script_dir, MODEL_DIR_NAME)

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _tokenizer = AutoTokenizer.from_pretrained(model_dir)
    _model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    _model.to(_device)
    _model.eval()

    # Risk sınıfının hangi index olduğu (modeline göre değişebilir)
    # En güvenlisi label2id/id2label'dan bakmak:
    label2id = getattr(_model.config, "label2id", {}) or {}
    id2label = getattr(_model.config, "id2label", {}) or {}

    # yaygın isimler: "suicide", "suicidal", "risk", "LABEL_1" vs.
    candidates = ["suicide", "suicidal", "risk", "LABEL_1", "1"]
    found = None

    for c in candidates:
        if c in label2id:
            found = label2id[c]
            break

    if found is None and id2label:
        # id2label örn: {0:"non-suicide", 1:"suicide"} gibi olabilir
        for k, v in id2label.items():
            if str(v).lower() in candidates:
                found = int(k)
                break

    # Hiç bulamazsa: ikili sınıflandırmada genelde pozitif sınıf index=1 varsay
    _risk_index = int(found) if found is not None else 1

import re

def _is_meaningful_text(text: str) -> bool:
    """
    Gerçekten analiz edilmeye değer metin mi?
    """
    if text is None:
        return False

    s = str(text).strip()

    if s == "":
        return False

    # sadece boşluk / kontrol karakterleri
    if len(s) == 0:
        return False

    # 'none', 'null' gibi stringler
    if s.lower() in ["none", "null", "nan"]:
        return False

    # sadece emoji / noktalama / sayı
    if re.fullmatch(r"[\W\d_]+", s):
        return False

    # çok kısa anlamsız şeyler (örn: "ok", ".", "-")
    if len(s) < 5:
        return False

    return True


def _score_texts(
    texts,
    script_dir: str,
    batch_size: int = 16,
    empty_value: float = 0.0
):
    _load_risk_model(script_dir)

    scores = [empty_value] * len(texts)

    valid_indices = []
    valid_texts = []

    for i, t in enumerate(texts):
        if _is_meaningful_text(t):
            valid_indices.append(i)
            valid_texts.append(str(t).strip())
        else:
            scores[i] = empty_value  # 🔴 BOŞSA KESİN 0.0

    if not valid_texts:
        return scores  # hepsi boşsa direkt dön

    dense_scores = []

    with torch.no_grad():
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]

            enc = _tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            enc = {k: v.to(_device) for k, v in enc.items()}

            out = _model(**enc)
            probs = torch.softmax(out.logits, dim=-1)[:, _risk_index]
            dense_scores.extend(probs.cpu().numpy().astype(float).tolist())

    for idx, score in zip(valid_indices, dense_scores):
        scores[idx] = float(score)

    return scores


def add_risk_columns(df: pd.DataFrame, script_dir: str):
    # hiçbir şeyi silmez, sadece yeni kolon ekler
    if df is None or len(df) == 0:
        return df

    if "caption_raw" in df.columns:
        df["caption_risk"] = _score_texts(df["caption_raw"].tolist(), script_dir)
    else:
        df["caption_risk"] = None

    if "overlay_text_raw" in df.columns:
        df["overlay_risk"] = _score_texts(df["overlay_text_raw"].tolist(), script_dir)
    else:
        df["overlay_risk"] = None

    if "transcript_raw" in df.columns:
        df["transcript_risk"] = _score_texts(df["transcript_raw"].tolist(), script_dir)
    else:
        df["transcript_risk"] = None

    return df


# ======================================================
# GENEL AYARLAR
# ======================================================
CSV_NAME = "tiktok_raw_data.csv"

# ======================================================
# OCR (SABİT OVERLAY METİN)
# ======================================================
ocr_reader = easyocr.Reader(["en", "tr"], gpu=False)

def extract_overlay_text(video_path: str) -> str:
    if not video_path or not os.path.exists(video_path):
        return ""

    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        return ""

    frames = [
        int(frame_count * 0.2),
        int(frame_count * 0.5),
        int(frame_count * 0.8),
    ]

    texts = []

    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            continue

        results = ocr_reader.readtext(frame, detail=0)
        cleaned = [t.strip().lower() for t in results if len(t.strip()) > 3]
        texts.extend(cleaned)

    cap.release()

    if not texts:
        return ""

    counts = Counter(texts)
    repeated = [t for t, c in counts.items() if c >= 2]

    return " ".join(repeated)

# ======================================================
# GÖRSEL ATMOSFER (BRIGHTNESS + BLUR)
# ======================================================
def extract_visual_features(video_path: str):
    if not video_path or not os.path.exists(video_path):
        return {
            "visual_brightness": None,
            "visual_blur": None,
        }

    cap = cv2.VideoCapture(video_path)
    brightness_vals = []
    blur_vals = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_vals.append(gray.mean())
        blur_vals.append(cv2.Laplacian(gray, cv2.CV_64F).var())

    cap.release()

    if not brightness_vals:
        return {
            "visual_brightness": None,
            "visual_blur": None,
        }

    return {
        "visual_brightness": round(float(sum(brightness_vals) / len(brightness_vals)), 2),
        "visual_blur": round(float(sum(blur_vals) / len(blur_vals)), 2),
    }

# ======================================================
# TEMİZLEME
# ======================================================
def temizle(t):
    t = str(t or "")
    t = re.sub(r"http\S+", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

# ======================================================
# VIDEO İNDİRME
# ======================================================
def download_video(url, out):
    apis = [
        f"https://tikwm.com/api/?url={url}",
        f"https://api.vvmd.cc/tk/?url={url}",
    ]
    for api in apis:
        try:
            r = requests.get(api, timeout=20)
            if r.status_code != 200:
                continue
            mp4 = r.json().get("data", {}).get("play", "")
            if not mp4:
                continue

            r2 = requests.get(mp4, stream=True, timeout=30)
            if r2.status_code != 200:
                continue

            with open(out, "wb") as f:
                for c in r2.iter_content(1024 * 64):
                    if c:
                        f.write(c)
            return out
        except:
            pass
    return None

# ======================================================
# TRANSCRIPT (WHISPER – AYRI SCRIPT)
# ======================================================
def extract_transcript(video_path, script_dir):
    if not video_path:
        return ""

    out_txt = os.path.join(script_dir, f"_tr_{uuid.uuid4().hex}.txt")

    subprocess.run(
        ["python", "transcribe_whisper.py", video_path, out_txt],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if os.path.exists(out_txt):
        with open(out_txt, "r", encoding="utf-8") as f:
            txt = f.read()
        os.remove(out_txt)
        return temizle(txt)

    return ""

# ======================================================
# CAPTION AL
# ======================================================
def get_caption(page):
    selectors = [
        '[data-e2e="browse-video-desc"]',
        '[data-e2e="video-desc"]',
        'h1[data-e2e="browse-video-desc"]',
        'h1[data-e2e="video-desc"]',
    ]
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(timeout=12000)
            txt = page.locator(sel).first.text_content()
            if txt and txt.strip():
                return temizle(txt)
        except:
            pass
    return ""

# ======================================================
# TEK VİDEO İŞLE (HAM)
# ======================================================
def process_video(page, source_type, source_value, url, script_dir):
    page.goto(url, timeout=60000)
    time.sleep(2)

    caption_raw = get_caption(page)

    video_file = os.path.join(script_dir, f"v_{uuid.uuid4().hex}.mp4")
    video_path = download_video(url, video_file)

    transcript_raw = extract_transcript(video_path, script_dir)
    overlay_raw = extract_overlay_text(video_path)

    face_info = extract_face_features(video_path)
    visual_info = extract_visual_features(video_path)

    if video_path and os.path.exists(video_path):
        os.remove(video_path)

    return {
        "source_type": source_type,
        "source_value": source_value,
        "video_url": url,
        "caption_raw": caption_raw,
        "transcript_raw": transcript_raw,
        "overlay_text_raw": overlay_raw,
        **face_info,
        **visual_info,
    }

# ======================================================
# LINK TOPLA
# ======================================================
def collect_links(page, limit):
    try:
        links = page.locator("a[href*='/video/']").evaluate_all(
            "els => els.map(e => e.href)"
        )
        return list(dict.fromkeys(links))[:limit]
    except:
        return []

def wait_for_tiktok_ready(page, timeout=180):
    """
    TikTok doğrulama / captcha geçilene kadar bekler.
    Terminal input() YOK.
    """
    print("⏳ TikTok doğrulama kontrol ediliyor...")

    start = time.time()
    while time.time() - start < timeout:
        try:
            url = page.url.lower()

            # hâlâ verify/captcha sayfasındaysa bekle
            if "verify" in url or "captcha" in url:
                time.sleep(2)
                continue

            # Sayfada video linkleri gelmiş mi?
            links = page.locator("a[href*='/video/']").count()
            if links > 0:
                print("✅ Doğrulama geçildi, devam ediliyor.")
                return True

        except:
            pass

        time.sleep(1)

    print("⚠️ Doğrulama bekleme süresi doldu, devam ediliyor.")
    return False


# ======================================================
# HASHTAG & USER SCRAPE
# ======================================================
def scrape_hashtag(tag, limit, script_dir, headless=0):
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(headless), channel="chrome")
        page = browser.new_page()

        page.goto(f"https://www.tiktok.com/tag/{tag}", timeout=120000)
        page.goto(f"https://www.tiktok.com/tag/{tag}", timeout=120000)

        wait_for_tiktok_ready(page)

        page.mouse.wheel(0, 8000)
        time.sleep(2)


        page.mouse.wheel(0, 8000)
        time.sleep(2)

        links = collect_links(page, limit)
        for i, v in enumerate(links, 1):
            print(f"[{i}/{len(links)}] {v}")
            rows.append(process_video(page, "hashtag", tag, v, script_dir))

        browser.close()

    return pd.DataFrame(rows)


def scrape_user(username, limit, script_dir, headless=0):
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(headless), channel="chrome")
        page = browser.new_page()

        page.goto(f"https://www.tiktok.com/@{username}", timeout=120000)
        page.goto(f"https://www.tiktok.com/@{username}", timeout=120000)

        wait_for_tiktok_ready(page)

        page.mouse.wheel(0, 8000)
        time.sleep(2)


        page.mouse.wheel(0, 8000)
        time.sleep(2)

        links = collect_links(page, limit)
        for i, v in enumerate(links, 1):
            print(f"[{i}/{len(links)}] {v}")
            rows.append(process_video(page, "user", username, v, script_dir))

        browser.close()

    return pd.DataFrame(rows)

# ======================================================
# CSV YAZ (APPEND + DUPLICATE KORUMA)
# ======================================================
def append_csv(csv_path, df):
    if df is None or len(df) == 0:
        print("ℹ️ Yeni veri yok.")
        return

    if os.path.exists(csv_path):
        old_df = pd.read_csv(csv_path)

        if "video_url" in old_df.columns:
            existing = set(old_df["video_url"].astype(str))
            before = len(df)
            df = df[~df["video_url"].astype(str).isin(existing)]
            print(f"🧹 Duplicate silindi: {before - len(df)}")

        if len(df) == 0:
            print("ℹ️ Tüm videolar daha önce kayıtlı.")
            return

        for col in old_df.columns:
            if col not in df.columns:
                df[col] = None
        df = df[old_df.columns]

        df.to_csv(csv_path, mode="a", header=False, index=False, encoding="utf-8-sig")
        print(f"✅ {len(df)} yeni satır eklendi.")
    else:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"🆕 CSV oluşturuldu ({len(df)} satır).")

# ======================================================
# MAIN
# ======================================================
# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--mode", choices=["hashtag", "user"], required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)

    # UI ile uyumlu opsiyonlar
    parser.add_argument(
        "--analyze",
        type=int,
        choices=[0, 1],
        default=1,
        help="1 ise risk analizi yapar ve çıktı CSV üretir",
    )
    parser.add_argument(
        "--headless",
        type=int,
        choices=[0, 1],
        default=0,
        help="1 ise tarayıcı headless (görünmez) çalışır",
    )
    parser.add_argument(
        "--out_csv",
        default="tiktok_analyzed.csv",
        help="Çıktı CSV dosya adı (varsa üzerine yazılır)",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, CSV_NAME)

    # ---------------- SCRAPE ----------------
    if args.mode == "hashtag":
        df = scrape_hashtag(
            args.query,
            args.limit,
            script_dir,
            headless=args.headless,
        )
    else:
        df = scrape_user(
            args.query,
            args.limit,
            script_dir,
            headless=args.headless,
        )

    if df is None or len(df) == 0:
        print("⚠️ Veri bulunamadı, işlem sonlandırıldı.")
        exit(0)

    # Ham CSV her zaman append edilir
    append_csv(csv_path, df)
    print("✅ HAM VERİ TOPLAMA TAMAMLANDI")

    # ---------------- ANALYZE ----------------
    if args.analyze == 1:
        analyzed_path = os.path.join(script_dir, args.out_csv)

        print("🔎 Risk analizi (yalnızca bu çalıştırma) başlıyor...")
        df = add_risk_columns(df, script_dir)
        print("✅ Risk analizi bitti.")

        # OVERWRITE: aynı isimde dosya varsa üstüne yazar
        df.to_csv(analyzed_path, index=False, encoding="utf-8-sig")
        print(
            f"✅ ANALYZED CSV oluşturuldu: {analyzed_path} (satır: {len(df)})"
        )
    else:
        print("ℹ️ Analyze kapalı, analyzed CSV üretilmedi.")
