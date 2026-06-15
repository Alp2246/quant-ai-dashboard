"""
alpha_engine.main
-----------------
Production-grade asyncio orchestrator.

Calistirma:
    python main.py
    python main.py --tick 30          # her 30 saniyede tetiklesin
    python main.py --once             # tek tur calistir, cik
    python main.py --health           # config saglik dokumu, cik

Davranis:
    * Sonsuz dongu: her TICK_SECONDS bir TUM gorevleri paralel calistirir.
    * Her gorev kendi timeout'una sahip (TASK_TIMEOUT).
    * Bir gorev cokerse digerlerini etkilemez; hata loglanir ve devam.
    * SIGINT / SIGTERM: aktif gorevleri tamamlayip duzgun kapanir.
    * Heartbeat dosyasi yazilir (dis monitoring icin).
    * Tick uzun surerse ust uste binmez (overrun korumasi).

Genisletme (Adim 2+):
    Yeni gorev eklemek icin register_task() ile orchestrator'a tanit:
        from src.ingestion.sec_edgar import poll as sec_poll
        orchestrator.register_task("sec_edgar", sec_poll)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from config import settings, setup_logging


LOG = setup_logging()
TaskFn = Callable[["TaskContext"], Awaitable[None]]


# ---------------------------------------------------------------------------
#  Task context - her tetiklemeyle gorevlere verilen meta bilgi
# ---------------------------------------------------------------------------
@dataclass
class TaskContext:
    tick_id: int
    tick_started_at: datetime
    settings: object = field(default_factory=lambda: settings)

    def elapsed_ms(self) -> int:
        return int((datetime.now(timezone.utc) - self.tick_started_at).total_seconds() * 1000)


@dataclass
class TaskStats:
    name: str
    runs: int = 0
    errors: int = 0
    last_status: str = "pending"
    last_duration_ms: int = 0
    last_error: Optional[str] = None
    last_run_at: Optional[datetime] = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "runs": self.runs,
            "errors": self.errors,
            "last_status": self.last_status,
            "last_duration_ms": self.last_duration_ms,
            "last_error": self.last_error,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }


# ---------------------------------------------------------------------------
#  Orchestrator
# ---------------------------------------------------------------------------
class Orchestrator:
    def __init__(self, tick_seconds: int, task_timeout: int) -> None:
        self.tick_seconds = max(5, int(tick_seconds))
        self.task_timeout = max(5, int(task_timeout))
        self.tasks: dict[str, TaskFn] = {}
        self.stats: dict[str, TaskStats] = {}
        self._shutdown = asyncio.Event()
        self._tick_id = 0

    # ---- Registry ---------------------------------------------------------
    def register_task(self, name: str, fn: TaskFn) -> None:
        if name in self.tasks:
            LOG.warning("Task '%s' uzerine yazildi", name)
        self.tasks[name] = fn
        self.stats[name] = TaskStats(name=name)
        LOG.info("Task kayitli: %s", name)

    # ---- Tek tetik --------------------------------------------------------
    async def _run_one(self, name: str, fn: TaskFn, ctx: TaskContext) -> None:
        st = self.stats[name]
        t0 = time.perf_counter()
        st.runs += 1
        st.last_run_at = datetime.now(timezone.utc)
        try:
            await asyncio.wait_for(fn(ctx), timeout=self.task_timeout)
            st.last_status = "ok"
            st.last_error = None
        except asyncio.TimeoutError:
            st.errors += 1
            st.last_status = "timeout"
            st.last_error = f"timeout>{self.task_timeout}s"
            LOG.error("[tick=%d] %s TIMEOUT (>%ds)", ctx.tick_id, name, self.task_timeout)
        except asyncio.CancelledError:
            st.last_status = "cancelled"
            LOG.warning("[tick=%d] %s CANCELLED", ctx.tick_id, name)
            raise
        except Exception as exc:
            st.errors += 1
            st.last_status = "error"
            st.last_error = f"{type(exc).__name__}: {exc}"
            LOG.error(
                "[tick=%d] %s ERROR: %s\n%s",
                ctx.tick_id, name, exc, traceback.format_exc(limit=4),
            )
        finally:
            st.last_duration_ms = int((time.perf_counter() - t0) * 1000)

    async def _tick(self) -> None:
        self._tick_id += 1
        tick_id = self._tick_id
        ctx = TaskContext(tick_id=tick_id, tick_started_at=datetime.now(timezone.utc))

        if not self.tasks:
            LOG.warning("[tick=%d] Kayitli gorev yok - bos tur", tick_id)
            return

        # Once veri topla, sonra analiz + Telegram (ayni tick'in sinyalleri)
        POST_PHASE = frozenset({"alpha_notify", "signal_prune", "heartbeat"})
        ingest = [(n, fn) for n, fn in self.tasks.items() if n not in POST_PHASE]
        post = [(n, fn) for n, fn in self.tasks.items() if n in POST_PHASE]

        LOG.info("[tick=%d] ingest=%d post=%d", tick_id, len(ingest), len(post))
        if ingest:
            await asyncio.gather(
                *[self._run_one(name, fn, ctx) for name, fn in ingest],
                return_exceptions=False,
            )
        if post:
            await asyncio.gather(
                *[self._run_one(name, fn, ctx) for name, fn in post],
                return_exceptions=False,
            )

        elapsed = ctx.elapsed_ms()
        ok = sum(1 for s in self.stats.values() if s.last_status == "ok")
        err = sum(1 for s in self.stats.values() if s.last_status in ("error", "timeout"))
        LOG.info("[tick=%d] tamamlandi %dms (ok=%d err=%d)",
                 tick_id, elapsed, ok, err)
        self._write_heartbeat(elapsed)

    # ---- Heartbeat & saglik ----------------------------------------------
    def _write_heartbeat(self, last_tick_ms: int) -> None:
        try:
            payload = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "tick_id": self._tick_id,
                "last_tick_ms": last_tick_ms,
                "tasks": [s.as_dict() for s in self.stats.values()],
            }
            settings.HEARTBEAT_FILE.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            LOG.debug("heartbeat yazilamadi: %s", exc)

    # ---- Ana dongu --------------------------------------------------------
    async def run_forever(self) -> None:
        LOG.info("Orchestrator basliyor: tick=%ds, task_timeout=%ds, tasks=%d",
                 self.tick_seconds, self.task_timeout, len(self.tasks))

        # 0. tick: hemen bir tur
        await self._tick()

        while not self._shutdown.is_set():
            try:
                await asyncio.wait_for(self._shutdown.wait(),
                                       timeout=self.tick_seconds)
                break  # shutdown geldi
            except asyncio.TimeoutError:
                pass  # tick zamani

            # Overrun korumasi: onceki tick hala calisiyorsa eski olur,
            # ama _tick await ediliyor zaten; burada paralel tur ACMIYORUZ.
            try:
                await self._tick()
            except Exception as exc:
                LOG.exception("Tick disinda beklenmeyen hata: %s", exc)

        LOG.info("Orchestrator durduruluyor (grace=%ds)", settings.SHUTDOWN_GRACE)

    async def run_once(self) -> None:
        await self._tick()

    def request_shutdown(self, source: str = "manual") -> None:
        if not self._shutdown.is_set():
            LOG.info("Shutdown istegi alindi (%s)", source)
            self._shutdown.set()


# ---------------------------------------------------------------------------
#  Sinyal yakalama - Windows + Unix uyumlu
# ---------------------------------------------------------------------------
def _install_signal_handlers(orchestrator: Orchestrator,
                              loop: asyncio.AbstractEventLoop) -> None:
    def _handler(sig_name: str) -> None:
        orchestrator.request_shutdown(sig_name)

    if sys.platform == "win32":
        # Windows: loop.add_signal_handler desteklenmez; KeyboardInterrupt'i
        # try/except ile yakalayacagiz (asagida run() icinde).
        return

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handler, sig.name)
        except (NotImplementedError, RuntimeError):
            pass


# ---------------------------------------------------------------------------
#  Task registry - Adim 2+ ile gercek modullerden import edilecek
# ---------------------------------------------------------------------------
async def _heartbeat_task(ctx: TaskContext) -> None:
    """
    Placeholder gorev. Tek isi yasiyoruz demek + log atmak.
    Adim 2'de bunun yerine sec_edgar.poll, reddit.poll vb. gelecek.
    """
    LOG.debug("[heartbeat] tick=%d t=%s tickers=%d",
              ctx.tick_id, ctx.tick_started_at.isoformat(),
              len(ctx.settings.TICKERS))


async def _prune_task(ctx: TaskContext) -> None:
    """SignalBus icindeki >24h sinyalleri her tick'te temizle."""
    from src.common.signal_bus import get_signal_bus
    bus = get_signal_bus()
    await bus.prune()


def _build_orchestrator() -> Orchestrator:
    orc = Orchestrator(
        tick_seconds=settings.TICK_SECONDS,
        task_timeout=settings.TASK_TIMEOUT,
    )

    # --- Adim 2: ingestion scanner'lari ---
    if settings.sec_enabled:
        from src.ingestion.sec_edgar import poll as sec_poll
        orc.register_task("sec_edgar", sec_poll)
        # Form 4 = insider buying (CEO/CFO kendi parasiyla hisse alimi)
        from src.ingestion.sec_form4 import poll as form4_poll
        orc.register_task("sec_form4", form4_poll)
    else:
        LOG.warning("SEC EDGAR DISABLED (SEC_USER_AGENT eksik)")

    if settings.reddit_enabled:
        from src.ingestion.reddit import poll as reddit_poll
        orc.register_task("reddit", reddit_poll)
    else:
        LOG.info("Reddit API yok -> public RSS + Google News (hesap/onay gerekmez)")
        from src.ingestion.reddit_rss import poll as reddit_rss_poll
        from src.ingestion.google_news import poll as news_poll
        orc.register_task("reddit_rss", reddit_rss_poll)
        orc.register_task("google_news", news_poll)

    if settings.polygon_enabled:
        from src.ingestion.polygon_options import poll as polygon_poll
        orc.register_task("polygon_options", polygon_poll)
    else:
        LOG.warning("Polygon DISABLED (POLYGON_API_KEY eksik)")

    # Adim 3: analiz + Telegram (ingestion'dan SONRA calisir)
    if settings.telegram_enabled:
        from src.analytics.alpha_notify import poll as alpha_poll
        orc.register_task("alpha_notify", alpha_poll)
        from src.jobs.master_score_poll import poll as master_score_poll
        orc.register_task("master_score", master_score_poll)
    else:
        LOG.warning("Telegram DISABLED - ALPHA uyari gonderilmez")

    orc.register_task("heartbeat", _heartbeat_task)
    orc.register_task("signal_prune", _prune_task)
    return orc


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QuantAI Alpha Engine orchestrator")
    p.add_argument("--tick", type=int, default=None,
                   help="Tetik araligi (saniye). Verilirse .env'i ezer.")
    p.add_argument("--once", action="store_true",
                   help="Tek tur calistir ve cik.")
    p.add_argument("--health", action="store_true",
                   help="Config sagligi yazdir ve cik.")
    return p.parse_args()


def _print_health() -> None:
    health = settings.health_summary()
    print(json.dumps(health, indent=2, default=str))
    missing = []
    if not settings.sec_enabled:
        missing.append("SEC_USER_AGENT (zorunlu: ad + e-posta)")
    if not settings.reddit_enabled:
        missing.append("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET")
    if not settings.polygon_enabled:
        missing.append("POLYGON_API_KEY (options unusual activity)")
    if not settings.telegram_enabled:
        missing.append("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    if missing:
        print("\nEksik / opsiyonel ayarlar:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("\nTum kaynaklar yapilandirilmis.")


async def _run() -> int:
    args = _parse_args()

    if args.health:
        _print_health()
        return 0

    orc = _build_orchestrator()
    if args.tick is not None:
        orc.tick_seconds = max(5, int(args.tick))
        LOG.info("CLI override: tick=%ds", orc.tick_seconds)

    loop = asyncio.get_running_loop()
    _install_signal_handlers(orc, loop)

    try:
        if args.once:
            await orc.run_once()
        else:
            await orc.run_forever()
    except KeyboardInterrupt:
        orc.request_shutdown("KeyboardInterrupt")
    finally:
        # Acik aiohttp session'lari + reddit client temizle
        try:
            from src.common.http_client import get_http_client
            await get_http_client().aclose()
        except Exception:
            pass
        try:
            from src.ingestion.reddit import _get_singleton as _rs
            await _rs().aclose()
        except Exception:
            pass
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        LOG.info("Ctrl+C - cikiliyor")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
