from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freefire_kill_sender import (
    LiveChatMessage,
    LivepixEvent,
    bot_cooldown_release_key,
    chat_command_token,
    is_timer_countable_chat_message,
    livepix_should_announce_event_rule,
    normalize_chat_command,
    send_tikfinity_direct_message,
    tikfinity_chatbot_message_payload,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def chat_message(
    username: str,
    comment: str,
    platform: str = "TikTok",
    source: str = "TikFinity WebSocket",
) -> LiveChatMessage:
    return LiveChatMessage(username=username, comment=comment, platform=platform, source=source)


def livepix_event(event_id: str, created_at: datetime, source: str = "webhook") -> LivepixEvent:
    return LivepixEvent(
        event_id=event_id,
        kind="payment",
        reference=event_id,
        username="Apoiador",
        message="Boa live",
        amount=500,
        currency="BRL",
        created_at=created_at.isoformat(timespec="seconds"),
        source=source,
    )


def verify_commands() -> None:
    check(normalize_chat_command("boa") == "!boa", "comando sem ! deve normalizar")
    check(chat_command_token("!boa tudo bem") == ("!boa", "tudo bem"), "comando simples nao reconhecido")
    check(chat_command_token("@Aizen !boa, salve") == ("!boa", "salve"), "comando apos mencao nao reconhecido")
    check(chat_command_token("fala !boa") == ("", ""), "texto comum nao deve virar comando")


def verify_timer_counting() -> None:
    check(is_timer_countable_chat_message(chat_message("Pedro", "salve")), "chat real deveria contar para timer")
    check(
        not is_timer_countable_chat_message(chat_message("Jarvis", "Boa tarde"), pending_bot_messages=["Boa tarde"]),
        "resposta pendente do bot nao deve contar para timer",
    )
    check(
        not is_timer_countable_chat_message(chat_message("AizenTimer", "timer", platform="Timer", source="timer")),
        "timer nao deve alimentar outro timer",
    )
    check(
        not is_timer_countable_chat_message(chat_message("Livepix", "pagamento", platform="Livepix", source="livepix")),
        "Livepix local nao deve contar como chat real",
    )
    check(
        not is_timer_countable_chat_message(chat_message("Jarvis", "qualquer coisa"), ignored_usernames=["jarvis"]),
        "usuario ignorado nao deve contar para timer",
    )


def verify_cooldown_release() -> None:
    last_sent = {"!boa": 100.0}
    check(
        bot_cooldown_release_key({"commandCooldownKey": "!boa", "commandCooldownStartedAt": 100.0}, last_sent) == "!boa",
        "cooldown do comando enviado deve ser liberavel em falha",
    )
    check(
        bot_cooldown_release_key({"commandCooldownKey": "!boa", "commandCooldownStartedAt": 80.0}, last_sent) == "",
        "cooldown antigo nao deve ser liberado por falha de tentativa nova",
    )
    check(
        bot_cooldown_release_key({"command": "!boa", "commandCooldownStartedAt": 100.0}, last_sent) == "",
        "payload sem marcador interno nao deve liberar cooldown",
    )


def verify_tikfinity_chatbot_payload() -> None:
    class Bridge:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        def broadcast_json(self, payload: dict[str, object]) -> int:
            self.payloads.append(payload)
            return 1

    payload = tikfinity_chatbot_message_payload(
        {
            "message": "  tudo   bem e vc?  ",
            "username": "AIZEN OFC",
            "deliveryId": "cmd-1",
            "command": "!boa",
        }
    )
    check(set(payload) == {"action", "args"}, "payload direto deve ter somente action e args no topo")
    check(payload["action"] == "sendChatbotMessage", "action do TikFinity deve postar mensagem no chatbot")
    check(payload["args"]["message"] == "tudo bem e vc?", "mensagem deve ser normalizada em args.message")
    check(payload["args"]["text"] == "tudo bem e vc?", "args.text deve acompanhar a mensagem")
    check(payload["args"]["username"] == "AIZEN OFC", "username deve ser preservado")
    check(payload["args"]["command"] == "!boa", "argumentos extras do comando devem continuar no pacote")
    bridge = Bridge()
    detail = send_tikfinity_direct_message(bridge, {"message": "Boa tarde", "username": "Jarvis"})
    check(detail.startswith("TikFinity recebeu pacote sendChatbotMessage"), "envio direto deve relatar action correta")
    check(bridge.payloads == [tikfinity_chatbot_message_payload({"message": "Boa tarde", "username": "Jarvis"})], "envio direto deve transmitir pacote oficial")


def verify_livepix_alerts() -> None:
    now = datetime(2026, 7, 17, 12, 0, 0)
    session_started_at = now - timedelta(minutes=10)
    recent_alerts: dict[tuple[str, str], float] = {}
    fresh = livepix_event("fresh-1", now - timedelta(minutes=2))
    check(
        livepix_should_announce_event_rule(
            fresh,
            was_known=False,
            announce_enabled=True,
            session_started_at=session_started_at,
            recent_alerts=recent_alerts,
            now=now,
            monotonic_now=1000.0,
        ),
        "Livepix novo deveria anunciar",
    )
    check(
        not livepix_should_announce_event_rule(
            fresh,
            was_known=False,
            announce_enabled=True,
            session_started_at=session_started_at,
            recent_alerts=recent_alerts,
            now=now,
            monotonic_now=1001.0,
        ),
        "Livepix repetido nao deveria anunciar",
    )
    old = livepix_event("old-1", now - timedelta(hours=2))
    check(
        not livepix_should_announce_event_rule(
            old,
            was_known=False,
            announce_enabled=True,
            session_started_at=session_started_at,
            recent_alerts=recent_alerts,
            now=now,
            monotonic_now=1002.0,
        ),
        "Livepix antigo nao deveria anunciar",
    )
    known = livepix_event("known-1", now - timedelta(minutes=1))
    check(
        not livepix_should_announce_event_rule(
            known,
            was_known=True,
            announce_enabled=True,
            session_started_at=session_started_at,
            recent_alerts=recent_alerts,
            now=now,
            monotonic_now=1003.0,
        ),
        "Livepix ja conhecido nao deveria anunciar",
    )
    test_event = livepix_event("test-1", now - timedelta(days=1), source="test")
    check(
        livepix_should_announce_event_rule(
            test_event,
            was_known=False,
            announce_enabled=True,
            session_started_at=session_started_at,
            recent_alerts=recent_alerts,
            now=now,
            monotonic_now=1004.0,
        ),
        "Evento teste manual deve continuar anunciando",
    )


def main() -> int:
    verify_commands()
    verify_timer_counting()
    verify_cooldown_release()
    verify_tikfinity_chatbot_payload()
    verify_livepix_alerts()
    print("Runtime chat/Livepix OK: comandos, temporizador e alertas antigos validados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
