"""抓取后异步 LLM 批量质量评估（创新度、实验完备性）。"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime

from openai import OpenAI
from sqlalchemy.orm import Session

from src.models.base import SessionLocal
from src.models.paper import Paper
from src.services.quality_scorer import compute_quality_score
from src.settings import get_settings
from src.utils.logging_config import setup_logger

logger = setup_logger("PaperQualityAssessment")


def _deepseek_client() -> OpenAI:
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _parse_llm_json(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def assess_paper_with_llm(title: str, abstract: str) -> tuple[float | None, float | None]:
    settings = get_settings()
    model = settings.translate_model or "deepseek-chat"
    client = _deepseek_client()
    prompt = (
        "Evaluate this academic paper abstract. Return ONLY JSON with two keys:\n"
        '- "innovation": 0-100 (novelty and contribution)\n'
        '- "experiment": 0-100 (experimental rigor and completeness)\n\n'
        f"Title: {title[:500]}\n\nAbstract: {(abstract or '')[:2500]}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert ML paper reviewer. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    data = _parse_llm_json(content)
    inv = data.get("innovation")
    exp = data.get("experiment")
    try:
        inv_f = max(0.0, min(100.0, float(inv))) if inv is not None else None
    except (TypeError, ValueError):
        inv_f = None
    try:
        exp_f = max(0.0, min(100.0, float(exp))) if exp is not None else None
    except (TypeError, ValueError):
        exp_f = None
    return inv_f, exp_f


def _assess_batch(session: Session, paper_ids: list[str]) -> int:
    done = 0
    for pid in paper_ids:
        paper = session.query(Paper).filter(Paper.arxiv_id == pid).first()
        if not paper or not (paper.title or paper.abstract):
            continue
        if paper.llm_innovation_score is not None and paper.llm_experiment_score is not None:
            continue
        try:
            inv, exp = assess_paper_with_llm(paper.title, paper.abstract)
            if inv is not None:
                paper.llm_innovation_score = inv
            if exp is not None:
                paper.llm_experiment_score = exp
            paper.quality_score = compute_quality_score({}, paper)
            paper.quality_assessed_at = datetime.utcnow()
            session.add(paper)
            from src.models.literature import LiteratureEntry

            for entry in session.query(LiteratureEntry).filter(LiteratureEntry.arxiv_id == pid).all():
                entry.quality_score = paper.quality_score
                session.add(entry)
            session.commit()
            done += 1
        except Exception as exc:
            logger.warning("LLM quality assess failed %s: %s", pid, exc)
            session.rollback()
    return done


def schedule_quality_assessment(paper_ids: list[str]) -> None:
    ids = [p for p in paper_ids if p]
    if not ids:
        return

    def _worker():
        session = SessionLocal()
        try:
            count = _assess_batch(session, ids)
            logger.info("LLM quality assessment finished: %s papers", count)
        finally:
            session.close()

    threading.Thread(target=_worker, daemon=True).start()
