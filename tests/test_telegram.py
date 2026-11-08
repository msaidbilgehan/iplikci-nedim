"""The Telegram bot as a way in (ADR-0021): the pairing, the documents its paired chat sends it taken in like an
upload and answered, everything from another chat passed over, each message handled once whoever reads it, and the
service's ear that keeps reading. No test reaches the network or the keyring: the bot is a fake in memory."""

import io
import json
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from iplikci import cli, egress
from iplikci.app import background, intake, kinds, notify, telegram
from iplikci.app.workspace import Busy, Workspace
from iplikci.domain.codes import Actor, Channel, ChannelStage, SourceKind
from iplikci.fakes import teb
from iplikci.ingest.telegram import BotWatcher, Heard
from iplikci.notify import channels
from iplikci.notify.channels import FILE_LIMIT, TOO_LARGE, SendError
from iplikci.settings import config, secrets
from iplikci.storage import documents, feed_state, jobs

from conftest import FEBRUARY, JANUARY

TZ = timezone(timedelta(hours=3))
NOON = datetime(2026, 11, 2, 12, 0, tzinfo=TZ)
TOKEN = "123456789:" + "A" * 35
CHAT = 4242  # the user's one-to-one chat with the bot
STRANGER = 9999
COMPANY = "ÖRNEK TEKNOLOJİ A.Ş."


@dataclass
class Bot:
    """Telegram's Bot API for one bot, in memory: the messages waiting for it, the files its chats sent, the messages
    it sent, and every call made. refuse: the HTTP status every call answers with (401 a revoked token, 409 another
    read waiting); unreachable: no call gets through."""

    updates: list[dict[str, object]] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    sent: list[dict[str, str]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    refuse: int = 0
    unreachable: bool = False

    def post_for(self, token: str):
        assert token == TOKEN

        def post(method: str, form):
            self.calls.append(method)
            if self.unreachable:
                raise egress.Unreachable("api.telegram.org adresine ulaşılamadı (URLError)")
            if self.refuse:
                return self.refuse, json.dumps({"ok": False, "description": f"Hata {self.refuse}"}).encode()
            result: object = {}
            if method == "getMe":
                result = {"username": "ornek_bot"}
            elif method == "getUpdates":
                result = [u for u in self.updates if int(str(u["update_id"])) >= int(form["offset"])]
            elif method == "getFile":
                data = self.files.get(form["file_id"])
                if data is None:
                    return 400, json.dumps({"ok": False, "description": "Bad Request: invalid file_id"}).encode()
                result = {
                    "file_id": form["file_id"],
                    "file_path": f"documents/{form['file_id']}",
                    "file_size": len(data),
                }
            else:
                self.sent.append(dict(form))
            return 200, json.dumps({"ok": True, "result": result}).encode()

        return post

    def fetch_for(self, token: str):
        assert token == TOKEN

        def fetch(path: str) -> tuple[int, bytes]:
            self.calls.append(f"file:{path}")
            if self.unreachable:
                raise egress.Unreachable("api.telegram.org adresine ulaşılamadı (URLError)")
            return 200, self.files[path.removeprefix("documents/")]

        return fetch

    def message(self, number: int, chat: int = CHAT, private: bool = True, **fields: object) -> None:
        self.updates.append(
            {
                "update_id": number,
                "message": {
                    "message_id": 100 + number,
                    "chat": {"id": chat, "type": "private" if private else "group"},
                    "from": {"id": chat if private else 7},
                    **fields,
                },
            }
        )

    def document(self, number: int, name: str, data: bytes, chat: int = CHAT, private: bool = True) -> None:
        self.files[f"dosya{number}"] = data
        info = {"file_id": f"dosya{number}", "file_name": name, "file_size": len(data)}
        self.message(number, chat, private, document=info)

    def answers(self) -> list[str]:
        return [f["text"] for f in self.sent]


@pytest.fixture
def ws(ws) -> Workspace:
    ws.layout.settings.write_text('[identity]\nbusiness_names = ["Örnek Teknoloji"]\n', encoding="utf-8")
    return Workspace.load(ws.home)


@pytest.fixture
def keyring(monkeypatch) -> dict[str, str]:
    kept: dict[str, str] = {}
    monkeypatch.setattr(secrets, "store", lambda secret, value: kept.update({secret.account: value}) or True)
    monkeypatch.setattr(secrets, "load", lambda secret: kept.get(secret.account))
    monkeypatch.setattr(secrets, "delete", lambda secret: kept.pop(secret.account, None))
    return kept


@pytest.fixture
def bot(monkeypatch) -> Bot:
    """The fake bot in place of the Bot API and Telegram's file server."""
    fake = Bot()
    monkeypatch.setattr(notify, "bot_calls", lambda settings, timeout=30.0: fake.post_for)
    monkeypatch.setattr(telegram, "file_calls", lambda settings: fake.fetch_for)
    return fake


@pytest.fixture
def paired(ws, keyring, bot) -> Bot:
    """A bot whose token is kept and whose chat with the user paired."""
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    config.update(ws.layout.settings, "notify", {"telegram_chat": CHAT})
    bot.calls.clear()
    return bot


def queued(ws) -> list[jobs.Job]:
    with ws.db() as db:
        rows = db.rows(
            "SELECT id FROM jobs WHERE kind = ? AND status = ? ORDER BY id", (kinds.TELEGRAM_DOCUMENT, "queued")
        )
        return [job for r in rows if (job := jobs.get(db, int(r["id"]))) is not None]


def run_documents(ws) -> list[int]:
    """Run the queued document jobs as the worker would; what each kept."""
    handler = background.handlers(ws)[kinds.TELEGRAM_DOCUMENT]
    kept: list[int] = []
    for job in queued(ws):
        kept.append(int(str(handler(job.payload))))
        with ws.db() as db:
            jobs.finish(db, job.id, "2026-11-02T09:00:00+00:00")
    return kept


def left_behind(ws) -> list[str]:
    """What the documents sent to the bot left in the upload area."""
    root = ws.layout.staging / "yuklemeler"
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def archive(ws) -> list[documents.DocumentRow]:
    with ws.db() as db:
        return documents.every(db)


def zipped(**members: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buffer.getvalue()


# --- the Bot API ---------------------------------------------------------------------------------------


def answer(result: object) -> tuple[int, bytes]:
    return 200, json.dumps({"ok": True, "result": result}).encode()


def test_the_bots_messages_are_read_with_their_chat_their_sender_and_their_file():
    updates = [
        {
            "update_id": 7,
            "message": {"message_id": 1, "text": "/start ab12cd34", "chat": {"id": 42, "type": "private"}},
        },
        {"update_id": 8, "edited_message": {"message_id": 2, "text": "düzeltildi", "chat": {"id": 42}}},
        {
            "update_id": 9,
            "message": {
                "message_id": 3,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 42},
                "document": {"file_id": "BQAC", "file_name": "ekstre.pdf", "file_size": 2048},
            },
        },
        {
            "update_id": 10,
            "message": {"message_id": 4, "chat": {"id": -5, "type": "group"}, "photo": [{"file_id": "x"}]},
        },
        {"update_id": 11, "message": {"message_id": 5, "text": "sohbet yok"}},
    ]
    asked: list[dict[str, str]] = []
    found, after = channels.updates(lambda m, f: asked.append(dict(f)) or answer(updates), 7, wait=25)
    assert asked == [{"offset": "7", "timeout": "25", "allowed_updates": '["message"]'}]
    assert after == 12  # what is no message is counted too: Telegram may forget it
    start, document, photo = found
    assert (start.update, start.chat, start.private, start.start_code) == (7, 42, True, "ab12cd34")
    assert document.document == channels.FileInfo("BQAC", "ekstre.pdf", 2048)
    assert (document.sender, document.message, document.start_code) == (42, 3, "")
    assert (photo.private, photo.photo, photo.document) == (False, True, None)


@pytest.mark.parametrize(
    ("text", "code"), [("/start ef56", "ef56"), ("/start@ornek_bot ef56", "ef56"), ("/start", ""), ("start ef56", "")]
)
def test_only_a_start_with_a_code_carries_a_pairing_code(text, code):
    assert channels.Update(1, 42, True, 42, 1, text).start_code == code


def test_a_file_is_fetched_from_where_telegram_names_it():
    fetched: list[str] = []

    def post(method, form):
        assert (method, form) == ("getFile", {"file_id": "BQAC"})
        return answer({"file_path": "documents/file 3.pdf", "file_size": 3})

    data = channels.download(post, lambda path: fetched.append(path) or (200, b"%PD"), "BQAC")
    assert data == b"%PD" and fetched == ["documents/file%203.pdf"]


def test_a_file_larger_than_a_bot_may_fetch_is_refused_before_or_after_it_comes():
    def post(method, form):
        return answer({"file_path": "documents/x.pdf", "file_size": FILE_LIMIT + 1})

    with pytest.raises(SendError) as told:
        channels.download(post, lambda path: pytest.fail("fetched"), "BQAC")
    assert told.value.status == TOO_LARGE and "20 MB" in str(told.value)

    def unsized(method, form):
        return answer({"file_path": "documents/x.pdf"})

    with pytest.raises(SendError) as cut:
        channels.download(unsized, lambda path: (200, b"x" * 11), "BQAC", limit=10)
    assert cut.value.status == TOO_LARGE


def test_a_file_that_cannot_be_fetched_never_shows_its_address():
    def post(method, form):
        return answer({"file_path": "documents/x.pdf"})

    def broken(path):
        raise ValueError(f"https://api.telegram.org/file/bot{TOKEN}/{path} bozuk")

    with pytest.raises(SendError) as failed:
        channels.download(post, broken, "BQAC")
    assert TOKEN not in str(failed.value) and failed.value.status == 0
    with pytest.raises(SendError) as gone:
        channels.download(post, lambda path: (404, b"Not Found"), "BQAC")
    assert gone.value.status == 404


def test_an_answer_quotes_the_message_it_answers():
    sent: list[dict[str, str]] = []
    channels.reply(lambda m, f: sent.append(dict(f)) or answer({}), 42, "Arşive alındı", to=7)
    channels.reply(lambda m, f: sent.append(dict(f)) or answer({}), 42, "Merhaba")
    assert json.loads(sent[0]["reply_parameters"]) == {"message_id": 7, "allow_sending_without_reply": True}
    assert "reply_parameters" not in sent[1] and sent[1]["chat_id"] == "42"


# --- pairing -------------------------------------------------------------------------------------------


def test_a_bot_is_paired_by_the_code_its_chat_sends(ws, keyring, bot):
    assert notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for) == notify.TokenSet("ornek_bot", True)
    assert keyring == {"telegram-bot": TOKEN}
    pairing = telegram.start_pairing(ws, NOON)
    assert pairing.link == f"https://t.me/ornek_bot?start={pairing.code}"
    bot.message(1, chat=7, text="/start yanlis")
    bot.message(2, chat=8, text="/start ğğğ")  # no ASCII: compared as bytes, never a crash
    assert not telegram.check_pairing(ws, NOON)
    bot.message(3, text=f"/start {pairing.code}")
    assert telegram.check_pairing(ws, NOON)
    assert config.load(ws.layout.settings).notify.telegram_chat == CHAT
    [greeting] = bot.sent
    assert greeting["chat_id"] == str(CHAT) and greeting["text"].startswith("Telegram bağlandı\n")
    assert "dosya olarak" in greeting["text"]  # documents are taken: the greeting says how to send them
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.TELEGRAM]
    assert state.ready and state.note == "@ornek_bot botuyla eşleşti."
    assert telegram.check_pairing(ws, NOON)  # asked again: paired, Telegram not asked
    assert bot.calls.count("getUpdates") == 2


def test_a_pairing_code_lasts_ten_minutes(ws, keyring, bot):
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    telegram.start_pairing(ws, NOON)
    with pytest.raises(notify.NotifyError, match="süresi doldu"):
        telegram.check_pairing(ws, NOON + timedelta(minutes=11))


def test_the_code_found_by_the_services_ear_pairs_the_chat_a_check_then_sees(ws, keyring, bot):
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    pairing = telegram.start_pairing(ws)
    bot.message(1, text=f"/start {pairing.code}")
    assert telegram.listen(ws, wait=0) is Heard.READ
    bot.refuse = 409  # were Telegram asked now, the ear's waiting read would hold it
    assert telegram.check_pairing(ws)
    assert config.load(ws.layout.settings).notify.telegram_chat == CHAT


def test_a_check_while_the_ear_waits_for_the_bots_messages_is_no_failure(ws, keyring, bot):
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    telegram.start_pairing(ws)
    bot.refuse = 409
    assert telegram.check_pairing(ws) is False


# --- documents -----------------------------------------------------------------------------------------


def test_a_document_sent_to_the_bot_is_taken_in_and_answered(ws, paired):
    paired.document(1, "Şubat Hesap Hareketleri.xls", FEBRUARY)
    assert telegram.listen(ws, wait=0) is Heard.READ
    assert archive(ws) == [] and paired.sent == []  # queued for the worker, nothing kept yet
    assert run_documents(ws) == [1]
    [doc] = archive(ws)
    with ws.db() as db:
        [source] = documents.sources(db, doc.sha256)
    assert (source.kind, source.original) == (SourceKind.TELEGRAM, "Şubat Hesap Hareketleri.xls")
    [said] = paired.sent
    assert json.loads(said["reply_parameters"])["message_id"] == 101  # it answers the message that brought it
    assert said["text"] == f"{doc.display_name}: arşive alındı (1 satır; bakiyeyi denetleyecek kadar satır yok)"
    assert left_behind(ws) == []


def test_the_same_document_sent_again_is_told_known(ws, paired):
    paired.document(1, "ocak.xls", teb.account_export(JANUARY))
    paired.document(2, "ocak-yeniden.xls", teb.account_export(JANUARY))
    telegram.listen(ws, wait=0)
    assert run_documents(ws) == [1, 0]
    assert len(archive(ws)) == 1
    assert paired.answers()[1] == "ocak-yeniden.xls: zaten arşivde"


def test_a_zip_is_answered_document_by_document(ws, paired):
    members = {"ocak.xls": teb.account_export(JANUARY), "sirket.xls": teb.account_export(JANUARY, holder=COMPANY)}
    paired.document(1, "belgeler.zip", zipped(**members))
    telegram.listen(ws, wait=0)
    assert run_documents(ws) == [1]
    [said] = paired.answers()
    first, second = said.split("\n")
    assert first.endswith("Hesap Hareketleri.xls: arşive alındı (2 satır; bakiye 1/1 satır tutarlı)")
    assert second == "sirket.xls: şirket belgesi; alınmadı"


def test_a_file_that_is_no_document_is_answered_with_why(ws, paired):
    paired.document(1, "notlar.txt", b"bir not")
    telegram.listen(ws, wait=0)
    assert run_documents(ws) == [0]
    assert archive(ws) == []
    [said] = paired.answers()
    assert said.startswith("notlar.txt: alınmadı; belge değil")
    assert left_behind(ws) == []


def test_a_document_from_another_chat_is_never_fetched_nor_answered(ws, paired):
    paired.document(1, "ekstre.xls", FEBRUARY, chat=STRANGER)
    paired.message(2, chat=STRANGER, text="merhaba")
    assert telegram.listen(ws, wait=0) is Heard.READ
    assert queued(ws) == [] and paired.sent == []
    assert "getFile" not in paired.calls and not any(c.startswith("file:") for c in paired.calls)


def test_what_cannot_be_taken_is_answered_with_what_to_do_instead(ws, paired):
    paired.message(1, photo=[{"file_id": "foto"}])
    paired.message(2, document={"file_id": "buyuk", "file_name": "arsiv.zip", "file_size": FILE_LIMIT + 1})
    paired.message(3, text="ne yapabilirim?")
    telegram.listen(ws, wait=0)
    photo, large, words = paired.answers()
    assert photo.startswith("Fotoğraf okunamaz") and "dosya olarak" in photo
    assert "20 MB sınırından büyük" in large and "Belge ekle" in large
    assert words.startswith("Bankanızdan indirdiğiniz belgeyi")
    assert queued(ws) == []


def test_a_paired_group_takes_no_documents(ws, paired):
    config.update(ws.layout.settings, "notify", {"telegram_chat": -100})
    paired.document(1, "ekstre.xls", FEBRUARY, chat=-100, private=False)
    paired.message(2, chat=-100, private=False, text="selam")
    telegram.listen(ws, wait=0)
    [said] = paired.answers()  # words in a group get no help
    assert queued(ws) == [] and "yalnızca botla bire bir sohbetten" in said


def test_each_message_is_handled_once_whoever_reads_it(ws, paired):
    paired.document(1, "subat.xls", FEBRUARY)
    calls = paired.post_for(TOKEN)

    def stale(method, form):  # a read made before the other one saved where it stopped: the same messages again
        return calls(method, {**form, "offset": "0"} if method == "getUpdates" else form)

    assert telegram.read(ws, stale, 0) == 1
    assert telegram.read(ws, stale, 0) == 0
    assert len(queued(ws)) == 1


def test_with_documents_off_the_bot_is_not_read_and_a_queued_document_is_left(ws, paired, keyring):
    paired.document(1, "subat.xls", FEBRUARY)
    telegram.listen(ws, wait=0)
    telegram.set_documents(ws, False, Actor.USER)
    keyring.clear()  # reading it would be a failure now
    assert telegram.listen(ws, wait=0) is Heard.NOTHING
    assert run_documents(ws) == [0]
    assert archive(ws) == [] and not any(c.startswith("file:") for c in paired.calls)
    assert not notify.status(ws).telegram_documents


def test_a_document_that_cannot_come_now_is_tried_again_and_fetched_once(ws, paired, monkeypatch):
    paired.document(1, "subat.xls", FEBRUARY)
    telegram.listen(ws, wait=0)
    [job] = queued(ws)
    paired.unreachable = True
    with pytest.raises(SendError):  # the worker tries again later
        telegram.take_document(ws, job.payload)
    paired.unreachable = False
    real = intake.apply

    def busy(*args, **kwargs):
        monkeypatch.setattr(intake, "apply", real)
        raise Busy("başka bir işlem belgeleri okuyor")

    monkeypatch.setattr(intake, "apply", busy)
    with pytest.raises(Busy):  # fetched, then the archive was busy
        telegram.take_document(ws, job.payload)
    assert telegram.take_document(ws, job.payload) == 1
    assert sum(c.startswith("file:") for c in paired.calls) == 1  # the fetched file waited for the next attempt
    assert len(archive(ws)) == 1


def test_a_file_telegram_will_not_give_is_answered_and_not_tried_again(ws, paired):
    paired.message(1, document={"file_id": "silinmis", "file_name": "ekstre.pdf", "file_size": 10})
    telegram.listen(ws, wait=0)
    assert run_documents(ws) == [0]
    [said] = paired.answers()
    assert said == "ekstre.pdf: Telegram'dan alınamadı (Telegram reddetti: Bad Request: invalid file_id)."


# --- the service's ear ---------------------------------------------------------------------------------


def test_nothing_is_read_without_a_paired_bot_and_the_keyring_rests(ws, bot):
    assert telegram.listen(ws, wait=0) is Heard.NOTHING  # the conftest keyring refuses: not reached
    assert bot.calls == []


def test_a_refused_token_stops_the_bot_until_it_is_entered_anew(ws, paired):
    paired.refuse = 401
    assert telegram.listen(ws, wait=0) is Heard.NOTHING
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.TELEGRAM]
    assert state.stage is ChannelStage.STOPPED
    paired.calls.clear()
    assert telegram.listen(ws, wait=0) is Heard.NOTHING and paired.calls == []
    paired.refuse = 0
    notify.set_telegram_token(ws, TOKEN, Actor.USER, paired.post_for)
    assert telegram.listen(ws, wait=0) is Heard.READ


def test_a_read_another_one_took_or_that_failed_says_so(ws, paired):
    paired.refuse = 409
    assert telegram.listen(ws, wait=0) is Heard.TAKEN
    paired.refuse = 0
    paired.unreachable = True
    assert telegram.listen(ws, wait=0) is Heard.FAILED


def test_the_ear_reads_again_at_once_waits_when_idle_and_longer_after_each_failure(monkeypatch):
    heard = iter([Heard.READ, Heard.NOTHING, Heard.FAILED, Heard.FAILED, Heard.TAKEN, Heard.READ])
    waits: list[float] = []
    done = threading.Event()

    def listen() -> Heard:
        found = next(heard, None)
        if found is None:
            done.set()
            raise RuntimeError("bitti")  # an error waits as a failed read; the ear goes on
        return found

    ear = BotWatcher(listen, idle_check=10, taken_wait=5, first_wait=1, longest_wait=3, pause=0.5)
    stop = ear._stop

    def wait(seconds: float) -> bool:
        waits.append(seconds)
        if done.is_set():
            stop.set()
        return stop.is_set()

    monkeypatch.setattr(stop, "wait", wait)
    ear._loop()
    assert waits == [0.5, 10, 1, 2, 5, 0.5, 1]


def test_the_worker_runs_a_document_job_and_the_system_screen_names_it(ws):
    assert kinds.TELEGRAM_DOCUMENT in background.handlers(ws)
    assert kinds.LABELS[kinds.TELEGRAM_DOCUMENT] == "Telegram'dan gelen belge"


# --- the command line ----------------------------------------------------------------------------------


def test_documents_from_the_bot_are_turned_off_and_on_from_the_command_line(ws, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    assert cli.main(["telegram", "belgeler", "kapat"]) == 0
    assert "kapatıldı" in capsys.readouterr().out
    assert config.load(ws.layout.settings).notify.telegram_documents is False
    assert cli.main(["bildirim", "durum"]) == 0
    assert "Telegram'dan belge alma: kapalı" in capsys.readouterr().out
    assert cli.main(["telegram", "belgeler", "ac"]) == 0
    assert config.load(ws.layout.settings).notify.telegram_documents is True
    with ws.db() as db:
        assert feed_state.load(db, notify.BOT) is None  # no bot was needed for the switch
