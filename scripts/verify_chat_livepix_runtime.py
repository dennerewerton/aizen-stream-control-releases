from __future__ import annotations

import json
import socket
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import freefire_kill_sender as app_runtime

from freefire_kill_sender import (
    LiveChatMessage,
    LivepixEvent,
    bot_cooldown_release_key,
    chat_command_token,
    is_timer_countable_chat_message,
    livepix_amount_cents,
    livepix_amount_cents_from_paths,
    livepix_is_rate_limit_detail,
    livepix_should_announce_event_rule,
    parse_livepix_event,
    normalize_chat_command,
    normalize_youtube_live_chat_url,
    TikfinityRaffleWorker,
    connect_plain_websocket_client,
    read_websocket_frame,
    send_tikfinity_direct_message,
    streamerbot_custom_event_payload,
    tikfinity_direct_delivery_payload,
    TikfinityDirectBridgeServer,
    tikfinity_chatbot_message_payload,
    websocket_frame,
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


def verify_youtube_raffle_url_normalization() -> None:
    check(
        normalize_youtube_live_chat_url("https://www.youtube.com/watch?v=abcDEF_1234")
        == "https://www.youtube.com/live_chat?is_popout=1&v=abcDEF_1234",
        "URL watch do YouTube deve virar chat pop-out",
    )
    check(
        normalize_youtube_live_chat_url("https://youtu.be/abcDEF_1234?t=12")
        == "https://www.youtube.com/live_chat?is_popout=1&v=abcDEF_1234",
        "URL youtu.be deve virar chat pop-out",
    )
    check(
        normalize_youtube_live_chat_url("abcDEF_1234")
        == "https://www.youtube.com/live_chat?is_popout=1&v=abcDEF_1234",
        "ID de video do YouTube deve virar chat pop-out",
    )


def verify_raffle_accepts_tiktok_and_youtube() -> None:
    logs: list[str] = []
    worker = TikfinityRaffleWorker("", "!sorteio", 60, logs.append, source_mode="events")
    worker.handle_live_chat_event(
        LiveChatMessage(
            username="Pedro",
            comment="!sorteio",
            user_id="tt-1",
            platform="TikTok",
            message_id="tt-msg-1",
        )
    )
    worker.handle_live_chat_event(
        LiveChatMessage(
            username="Pedro",
            comment="!sorteio",
            user_id="yt-1",
            platform="YouTube",
            message_id="yt-msg-1",
        )
    )
    items = sorted(worker.participant_items(), key=lambda item: item.platform)
    check(len(items) == 2, "TikTok e YouTube devem entrar no mesmo sorteio")
    check({item.platform for item in items} == {"TikTok", "YouTube"}, "participantes devem preservar plataforma")
    check(worker.total_entries() == 2, "entradas de TikTok e YouTube devem somar")

    same_platform = TikfinityRaffleWorker("", "!sorteio", 60, logs.append, source_mode="events")
    same_platform.handle_live_chat_event(
        LiveChatMessage(username="Maria", comment="!sorteio", user_id="yt-a", platform="YouTube", message_id="yt-a-1")
    )
    same_platform.handle_live_chat_event(
        LiveChatMessage(username="Maria", comment="!sorteio", user_id="yt-b", platform="YouTube", message_id="yt-b-1")
    )
    check(same_platform.participant_count() == 1, "nome duplicado na mesma plataforma deve continuar bloqueado")
    check(
        any(item.get("reason") == "nome duplicado" and item.get("platform") == "YouTube" for item in same_platform.blocked_history_items()),
        "bloqueio de nome duplicado deve registrar plataforma",
    )


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
            self.ready_clients = 1

        def broadcast_json(self, payload: dict[str, object]) -> int:
            self.payloads.append(payload)
            return 1

        def client_count(self) -> int:
            return 1

        def ready_client_count(self) -> int:
            return self.ready_clients

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
    event_payload = streamerbot_custom_event_payload(payload)
    check(event_payload["event"] == {"source": "General", "type": "Custom"}, "ponte direta deve emitir General.Custom")
    check(
        json.loads(event_payload["data"]) == payload,
        "data do General.Custom deve conter o pacote sendChatbotMessage serializado",
    )
    first_attempt_payload, first_attempt_label = tikfinity_direct_delivery_payload(
        {"message": "Boa tarde", "username": "Jarvis", "attempt": 1}
    )
    check(first_attempt_label.startswith("evento General.Custom"), "primeira tentativa deve usar General.Custom")
    check(first_attempt_payload.get("event") == {"source": "General", "type": "Custom"}, "primeira tentativa deve envelopar evento")
    retry_payload, retry_label = tikfinity_direct_delivery_payload(
        {"message": "Boa tarde", "username": "Jarvis", "attempt": 2, "retry": True}
    )
    check(retry_label.startswith("pacote direto"), "reenvio deve usar fallback direto")
    check(set(retry_payload) == {"action", "args"}, "fallback direto deve manter o pacote TikFinity cru")
    bridge = Bridge()
    detail = send_tikfinity_direct_message(bridge, {"message": "Boa tarde", "username": "Jarvis"})
    check(detail.startswith("TikFinity recebeu evento General.Custom sendChatbotMessage"), "envio direto deve relatar evento correto")
    sent_payload = bridge.payloads[0] if bridge.payloads else {}
    check(sent_payload.get("event") == {"source": "General", "type": "Custom"}, "envio direto deve transmitir evento General.Custom")
    check(
        json.loads(str(sent_payload.get("data") or "{}"))
        == tikfinity_chatbot_message_payload({"message": "Boa tarde", "username": "Jarvis"}),
        "envio direto deve transmitir pacote oficial dentro de data",
    )
    retry_bridge = Bridge()
    retry_detail = send_tikfinity_direct_message(
        retry_bridge,
        {"message": "Boa tarde", "username": "Jarvis", "attempt": 2, "retry": True},
    )
    check(retry_detail.startswith("TikFinity recebeu pacote direto sendChatbotMessage"), "retry deve relatar fallback direto")
    check(
        retry_bridge.payloads == [tikfinity_chatbot_message_payload({"message": "Boa tarde", "username": "Jarvis", "attempt": 2, "retry": True})],
        "retry deve transmitir pacote direto oficial",
    )

    waiting_bridge = Bridge()
    waiting_bridge.ready_clients = 0
    previous_ready_wait = app_runtime.TIKFINITY_DIRECT_READY_WAIT_SECONDS
    app_runtime.TIKFINITY_DIRECT_READY_WAIT_SECONDS = 0.01
    try:
        send_tikfinity_direct_message(waiting_bridge, {"message": "Nao enviar ainda", "username": "Jarvis"})
    except RuntimeError as exc:
        check("ainda nao assinou" in str(exc), "ponte sem Subscribe deve explicar a assinatura pendente")
    else:
        raise AssertionError("ponte conectada sem Subscribe nao deveria aceitar envio como sucesso")
    finally:
        app_runtime.TIKFINITY_DIRECT_READY_WAIT_SECONDS = previous_ready_wait
    check(waiting_bridge.payloads == [], "ponte sem Subscribe nao deve receber pacote do bot")


def read_json_frame_until(sock: socket.socket, predicate: callable, timeout: float = 4.0) -> dict[str, object]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            opcode, payload = read_websocket_frame(sock)
        except socket.timeout:
            continue
        check(opcode == 0x1, f"frame websocket inesperado: opcode {opcode}")
        try:
            message = json.loads(payload.decode("utf-8"))
        except Exception as exc:
            raise AssertionError(f"frame websocket sem JSON valido: {exc}") from exc
        if isinstance(message, dict) and predicate(message):
            return message
    raise AssertionError("frame websocket esperado nao chegou na ponte direta")


def verify_tikfinity_direct_bridge_socket_delivery() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    url = f"ws://127.0.0.1:{port}/"
    logs: list[str] = []
    server = TikfinityDirectBridgeServer(url, logs.append)
    server.start()
    sock: socket.socket | None = None
    try:
        sock = connect_plain_websocket_client(url, timeout=3)
        hello = read_json_frame_until(sock, lambda item: item.get("request") == "Hello")
        check(hello.get("info", {}).get("name") == app_runtime.APP_NAME, "ponte deve enviar Hello compativel com Streamer.bot")
        subscribe_id = "verify-subscribe"
        sock.sendall(
            websocket_frame(
                0x1,
                json.dumps(
                    {"request": "Subscribe", "id": subscribe_id, "events": {"General": ["Custom"]}},
                    ensure_ascii=False,
                ),
                mask=True,
            )
        )
        subscribe_response = read_json_frame_until(sock, lambda item: item.get("id") == subscribe_id)
        check(subscribe_response.get("status") == "ok", "ponte deve aceitar Subscribe do TikFinity")
        detail = send_tikfinity_direct_message(server, {"message": "Boa tarde", "username": "Jarvis"})
        check("General.Custom" in detail, "envio direto deve relatar General.Custom")
        event = read_json_frame_until(
            sock,
            lambda item: isinstance(item.get("event"), dict)
            and item["event"].get("source") == "General"
            and item["event"].get("type") == "Custom",
        )
        data = json.loads(str(event.get("data") or "{}"))
        check(data.get("action") == "sendChatbotMessage", "evento real da ponte deve carregar sendChatbotMessage")
        check(data.get("args", {}).get("message") == "Boa tarde", "evento real da ponte deve carregar a mensagem")
        check(data.get("args", {}).get("username") == "Jarvis", "evento real da ponte deve carregar o usuario")
        retry_detail = send_tikfinity_direct_message(
            server,
            {"message": "Boa noite", "username": "Jarvis", "attempt": 2, "retry": True},
        )
        check("pacote direto" in retry_detail, "retry real da ponte deve usar pacote direto")
        raw_message = read_json_frame_until(sock, lambda item: item.get("action") == "sendChatbotMessage")
        check(raw_message.get("args", {}).get("message") == "Boa noite", "retry real deve carregar a mensagem direta")
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        server.stop()


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


def verify_livepix_amount_parsing() -> None:
    check(livepix_amount_cents("R$ 4,00") == 400, "valor BRL com virgula deve virar centavos")
    check(livepix_amount_cents("4.00") == 400, "valor decimal em texto deve virar centavos")
    check(livepix_amount_cents(4.0) == 400, "float inteiro da API deve representar reais")
    check(
        livepix_amount_cents_from_paths({"amountCents": 400.0}, (("amountCents",), ("amount",))) == 400,
        "campo amountCents float deve continuar sendo centavos",
    )
    decimal_event = parse_livepix_event({"id": "pix-decimal", "amount": 4.0, "username": "Apoiador"}, "payment", "api")
    cents_event = parse_livepix_event({"id": "pix-cents", "amountCents": 400.0, "username": "Apoiador"}, "payment", "api")
    check(decimal_event is not None and decimal_event.amount == 400, "evento com amount decimal deve ficar em centavos")
    check(cents_event is not None and cents_event.amount == 400, "evento com amountCents deve preservar centavos")


def verify_livepix_rate_limit_detection() -> None:
    check(livepix_is_rate_limit_detail("429 limite de requisicoes da Livepix"), "429 deve ser rate limit")
    check(livepix_is_rate_limit_detail("Too Many Requests"), "too many requests deve ser rate limit")
    check(livepix_is_rate_limit_detail("rate limit exceeded"), "rate limit em ingles deve ser reconhecido")
    check(not livepix_is_rate_limit_detail("401 credenciais invalidas"), "401 nao deve ser tratado como rate limit")


def main() -> int:
    verify_commands()
    verify_youtube_raffle_url_normalization()
    verify_raffle_accepts_tiktok_and_youtube()
    verify_timer_counting()
    verify_cooldown_release()
    verify_tikfinity_chatbot_payload()
    verify_tikfinity_direct_bridge_socket_delivery()
    verify_livepix_alerts()
    verify_livepix_amount_parsing()
    verify_livepix_rate_limit_detection()
    print("Runtime chat/Livepix OK: comandos, temporizador, sorteio YouTube/TikTok e alertas validados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
