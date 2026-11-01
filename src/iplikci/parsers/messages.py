"""What a kept e-mail is when no reader of message bodies took it (Phase 4, F01).

A bank sends far more than money notices: campaigns, announcements, security and card notices. Saying knowingly that
such a message moves no money is what the coverage measure of F01 counts. A message that carries documents is read
through them. A message no rule knows keeps MESSAGE_REASON: it may be a money notice no reader reads yet, and it
stays in sight until one does.

The rules look at the sender's domain and the subject; only a subject that says nothing makes them read the body's
opening sentence, for a change of fees it announces. They were drawn from the mailbox's inventory (`iplikci dev
eposta-envanteri`). A subject that names money moving (an extract, a receipt, a transfer, a premium, a debt) is never
called a campaign or an announcement, unless the bank itself labels it so.
"""

import re

from ..domain.text import fold
from .common import MESSAGE_REASON
from .mail import Mail

# Raised whenever the rules change: the messages no reader took are then classified again (registry.signature).
VERSION = 3

CAMPAIGN = "kampanya ve tanıtım — para hareketi yok"
ANNOUNCEMENT = "duyuru ve bilgilendirme — para hareketi yok"
SECURITY = "güvenlik ve hesap ayarı bildirimi — para hareketi yok"
CARD = "kart ve başvuru bildirimi — para hareketi yok"
ELSEWHERE = "ayrıntısı internet şubesinde — e-postada para hareketi yok"
REMINDER = "ödeme hatırlatması — para hareketi yok"
ATTACHED = "e-posta iletisi; ekindeki belgeler ayrıca okunur"
NO_MONEY = frozenset({CAMPAIGN, ANNOUNCEMENT, SECURITY, CARD, ELSEWHERE, REMINDER})


def _words(*words: str) -> re.Pattern[str]:
    """Any of words in a folded subject, each starting at a word's start."""
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + ")")


# The bank's own label in front of a subject ("Kampanya: …", "Tanıtım: …").
_LABELLED = re.compile(r"^(?:KAMPANYA|TANITIM)\b")
_SECURITY = _words(
    "SIFRE",
    "GUVENLIK",
    "GUVENLIG",
    "DOLANDIRICILIK",
    "DOGRULA",
    "YENI CIHAZ",
    "TANIMLAMA",
    "ADRES",
    "TERCIH",
    "KULLANDIRILMAMASI",
    "KONTAK BILGI",
)
_CARD = _words(
    "KARTINIZ TESLIM", "KARTINIZI TESLIM", "KART TESLIM", "KURYE", "KART YENILEME", "BASVURU", "LIMIT ARTISI"
)
# A payment that is due, not one made: İş Bankası's weekly card payments, a loan's next due date.
_REMINDER = _words("HAFTASI ODEME BILGILERI", "VADE TARIHI BILGILENDIRME", "HATIRLATMA")
# A change to fees, rates or terms is announced, whatever money words the subject also holds.
_CHANGE = _words("DEGISIKLIK", "DEGISIKLIG", "GUNCELLEN")
_OPENING = 400  # characters of the body's text that hold its greeting and opening sentence
# A body that sends the reader to online banking for the details ("… İnternet/Mobil Şube'den kontrol edebilirsiniz",
# Garanti's monthly HGS message), when it holds no amount, tells of no money itself.
_ELSEWHERE = _words("KONTROL EDEBILIRSINIZ", "GORUNTULEYEBILIRSINIZ", "INCELEYEBILIRSINIZ")
_AMOUNT = re.compile(r"\d,\d{2}\b|\d\.\d{3}\b")
# Money moving, or money owed: a subject with these is a notice no reader reads yet, not a campaign.
_MONEY = _words(
    "EKSTRE",
    "HESAP OZETI",
    "DEKONT",
    "TRANSFER",
    "PARA CIKIS",
    "PARA GIRIS",
    "TAHSIL",
    "PRIM",
    "SGK",
    "BAG-KUR",
    "BAGKUR",
    "BORCUNUZ",
    "FATURA",
    "ODENMIS",
    "VADE TARIHI",
    "DONEM UCRETI",
    "BAKIYE",
    "MAAS",
    "HAVALE",
    "EFT",
    "FAST",
    "ISLEM SONUC",
    "TAKSIDIN",
)
_CAMPAIGN = _words(
    "KAMPANYA",
    "FIRSAT",
    "DAVET",
    "BONUS",
    "MAXIPUAN",
    "INDIRIM",
    "HEDIYE",
    "KAZAN",
    "CEKILIS",
    "AYRICALIK",
    "TAKSIT",
    "MASRAFSIZ",
    "SIZE OZEL",
    "BASVURUN",
    "KESFEDIN",
    "YARARLANIN",
    "HOS GELDIN",
    "HOSGELDIN",
    "KUTLU OLSUN",
    "KUTLARIZ",
    "MUTLU BAYRAM",
    "WEBINAR",
    "ETKINLIG",
    "ETKINLIK",
    "PROGRAM",
    "MASTERCLASS",
    "MENTORLUK",
    "GIRISIM",
    "STARTUP",
    "START-UP",
    "IS BIRLIG",
    "KITABI",
    "SUBELERIMIZ",
    "MOBIL'DE",
    "ARTIK",
)
_ANNOUNCEMENT = _words(
    "TATIL",
    "SAATLERI",
    "PIYASA",
    "BORSA",
    "HALKA ARZ",
    "RAPOR",
    "STRATEJI",
    "UCRET",
    "TARIFE",
    "YASAL",
    "SUBEMIZ",
    "LIMITLERIMIZ",
    "LIMITI",
    "NEMA",
    "YENILENDI",
    "KAPANIYOR",
    "HIZMET",
    "ANKET",
    "MEMNUNIYET",
    "SIZE DESTEK",
    "TAMAMLADINIZ",
)


def message_reason(mail: Mail) -> str:
    """Why a message no reader took is kept unprocessed: what it is when its sender and subject say so, else
    MESSAGE_REASON. The order matters. A campaign sender or the bank's own label comes first. What never moves
    money follows (security and card notices, reminders of a payment due, announced changes, a body without amounts
    that leaves the details to online banking). Then a subject that names money moving keeps the message unknown,
    before the looser words of announcements and campaigns are tried."""
    if mail.attached:
        return ATTACHED
    # The first label of the sender's domain: banks send campaigns from "kampanya." and announcements from "bilgi.".
    subject, label = fold(mail.subject), mail.sender.split(".", 1)[0]
    if label == "kampanya" or _LABELLED.search(subject):
        return CAMPAIGN
    for words, reason in ((_SECURITY, SECURITY), (_CARD, CARD), (_REMINDER, REMINDER), (_CHANGE, ANNOUNCEMENT)):
        if words.search(subject):
            return reason
    if _ELSEWHERE.search(fold(mail.text)) and not _AMOUNT.search(mail.text):
        return ELSEWHERE
    if _MONEY.search(subject):
        return MESSAGE_REASON
    if label == "bilgi":
        return ANNOUNCEMENT
    if _CAMPAIGN.search(subject):
        return CAMPAIGN
    if _ANNOUNCEMENT.search(subject):
        return ANNOUNCEMENT
    # A subject that says nothing ("BİLGİLENDİRME"): the body's opening sentence may announce a change of fees.
    return ANNOUNCEMENT if _CHANGE.search(fold(mail.text[:_OPENING])) else MESSAGE_REASON
