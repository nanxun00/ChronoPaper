"""科大讯飞语音听写（流式版）WebSocket API。"""
from __future__ import annotations

import audioop
import base64
import hashlib
import hmac
import json
import time
import wave
from datetime import datetime
from pathlib import Path
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket

from src.utils.logging_config import setup_logger

logger = setup_logger("XFyunASR")

XFYUN_IAT_HOST = "iat-api.xfyun.cn"
XFYUN_IAT_PATH = "/v2/iat"
FRAME_SIZE = 8000
FRAME_INTERVAL = 0.04
TARGET_SAMPLE_RATE = 16000


def _build_auth_url(api_key: str, api_secret: str) -> str:
    date = format_date_time(mktime(datetime.now().timetuple()))
    signature_origin = (
        f"host: {XFYUN_IAT_HOST}\n"
        f"date: {date}\n"
        f"GET {XFYUN_IAT_PATH} HTTP/1.1"
    )
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": XFYUN_IAT_HOST})
    return f"wss://{XFYUN_IAT_HOST}{XFYUN_IAT_PATH}?{query}"


def _append_words_from_payload(payload: dict, words: list[str]) -> None:
    data = payload.get("data") or {}
    result = data.get("result") or {}
    for item in result.get("ws") or []:
        for cw in item.get("cw") or []:
            word = (cw.get("w") or "").strip()
            if word:
                words.append(word)


def _send_pcm_frames(ws: websocket.WebSocket, pcm_bytes: bytes, *, app_id: str) -> None:
    business = {
        "language": "zh_cn",
        "domain": "iat",
        "accent": "mandarin",
        "vad_eos": 10000,
    }
    chunks = [pcm_bytes[i : i + FRAME_SIZE] for i in range(0, len(pcm_bytes), FRAME_SIZE)]
    if not chunks:
        chunks = [b""]

    first_chunk = chunks[0]
    frame = {
        "common": {"app_id": app_id},
        "business": business,
        "data": {
            "status": 0,
            "format": "audio/L16;rate=16000",
            "encoding": "raw",
            "audio": base64.b64encode(first_chunk).decode("utf-8"),
        },
    }
    ws.send(json.dumps(frame))
    time.sleep(FRAME_INTERVAL)

    for chunk in chunks[1:]:
        frame = {
            "data": {
                "status": 1,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(chunk).decode("utf-8"),
            }
        }
        ws.send(json.dumps(frame))
        time.sleep(FRAME_INTERVAL)

    frame = {
        "data": {
            "status": 2,
            "format": "audio/L16;rate=16000",
            "encoding": "raw",
            "audio": "",
        }
    }
    ws.send(json.dumps(frame))


def transcribe_pcm(
    pcm_bytes: bytes,
    *,
    app_id: str,
    api_key: str,
    api_secret: str,
) -> str:
    if not pcm_bytes:
        return ""
    if not app_id or not api_key or not api_secret:
        raise ValueError("XFyun credentials are not configured")

    url = _build_auth_url(api_key, api_secret)
    words: list[str] = []

    ws = websocket.create_connection(url, timeout=30)
    try:
        _send_pcm_frames(ws, pcm_bytes, app_id=app_id)
        while True:
            try:
                ws.settimeout(5)
                message = ws.recv()
            except websocket.WebSocketTimeoutException:
                break
            if not message:
                break
            payload = json.loads(message)
            code = int(payload.get("code", -1))
            if code != 0:
                raise RuntimeError(payload.get("message") or f"XFyun ASR error code={code}")

            data = payload.get("data") or {}
            _append_words_from_payload(payload, words)

            if int(data.get("status", 0)) == 2:
                ws.settimeout(0.5)
                while True:
                    try:
                        tail = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        break
                    if not tail:
                        break
                    tail_payload = json.loads(tail)
                    if int(tail_payload.get("code", -1)) != 0:
                        raise RuntimeError(tail_payload.get("message") or "XFyun ASR tail error")
                    _append_words_from_payload(tail_payload, words)
                break
    finally:
        ws.close()

    return "".join(words).strip()


def audio_file_to_pcm(file_path: str | Path) -> bytes:
    """读取 WAV/PCM 为 16kHz 单声道 PCM（纯 Python，无需 ffmpeg）。"""
    src = Path(file_path)
    if not src.is_file():
        raise FileNotFoundError(f"audio file not found: {src}")

    suffix = src.suffix.lower()
    if suffix == ".pcm":
        return src.read_bytes()

    if suffix != ".wav":
        raise ValueError(
            f"不支持的音频格式: {suffix or '(无扩展名)'}，请上传 16kHz 单声道 WAV 或 PCM"
        )

    with wave.open(str(src), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise ValueError("仅支持 16bit PCM 音频")

    if channels > 1:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
        channels = 1

    if frame_rate != TARGET_SAMPLE_RATE:
        frames, _ = audioop.ratecv(
            frames,
            sample_width,
            channels,
            frame_rate,
            TARGET_SAMPLE_RATE,
            None,
        )

    if len(frames) < TARGET_SAMPLE_RATE // 5:
        raise ValueError("录音太短，请按住说话至少 1 秒")

    return frames


def transcribe_audio_file(
    file_path: str | Path,
    *,
    app_id: str,
    api_key: str,
    api_secret: str,
) -> str:
    pcm_bytes = audio_file_to_pcm(file_path)
    return transcribe_pcm(
        pcm_bytes,
        app_id=app_id,
        api_key=api_key,
        api_secret=api_secret,
    )
