import json
import os
import re
import sys
import traceback

import requests
from django.http import JsonResponse
from django.views import View
from shlex import split
from django.db.models import Q, QuerySet
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime
from datetime import timedelta

from coca_bot.models import Iscritti, AppLogs
import secrets

from utils.DataLoader import DataLoader

TELEGRAM_URL = "https://api.telegram.org/bot"
TUTORIAL_BOT_TOKEN = os.getenv("TUTORIAL_BOT_TOKEN", "error_token")
ISDEBUG = os.getenv("ISDEBUG", "False") == "True"
FORCEANSWER = os.getenv("FORCEANSWER", "False") == "True"


# https://api.telegram.org/bot<token>/setWebhook?url=<url>/webhooks/tutorial/
def get_iscritti(search_string: str, show_only_active: bool = False, show_all: bool = False) -> QuerySet:
    iscritti_set = Iscritti.objects.filter(
        Q(cognome__icontains=search_string) |
        Q(nome__icontains=search_string) |
        Q(codice_socio__icontains=search_string) |
        Q(codice_fiscale__icontains=search_string) |
        Q(branca__icontains=search_string)
    )
    if show_all:
        iscritti_set = Iscritti.objects.all()
    if show_only_active:
        printdebug(f"Show only active - func: {show_only_active}")
        iscritti_set.filter(
            Q(active=True)
        )
    return iscritti_set


def get_iscritto_by_codice(search_string: str, show_only_active: bool = False) -> QuerySet:
    iscritti_set = Iscritti.objects.filter(
        Q(codice_socio__iexact=search_string) |
        Q(codice_fiscale__iexact=search_string)
    )
    if show_only_active:
        printdebug(f"Show only active - func: {show_only_active}")
        iscritti_set.filter(
            Q(active=True)
        )
    return iscritti_set


def get_iscritto_by_telegram(t_user: str) -> QuerySet:
    return Iscritti.objects.filter(
        Q(telegram_id__iexact=str(t_user))
    )


def get_enabled() -> QuerySet:
    return Iscritti.objects.filter(
        Q(telegram__isnull=False)
    ).exclude(
        Q(telegram__iexact='') &
        Q(active=False)
    )


def get_iscritto_by_authcode(authcode: str) -> QuerySet:
    return Iscritti.objects.filter(
        Q(authcode__iexact=authcode)
    )


def get_logs_by_date(days: int) -> QuerySet:
    date_to = datetime.now() - timedelta(days=7)
    return AppLogs.objects.filter(log_time__date__gte=date_to)


def get_logs_by_date_gte(days: int) -> QuerySet:
    date_to = datetime.now() - timedelta(days=7)
    return AppLogs.objects.filter(
        Q(log_time__date__gte=date_to)
    ).order_by('log_time')[:20]


def get_logs_by_date_lt(days: int) -> QuerySet:
    date_to = datetime.now() - timedelta(days=7)
    return AppLogs.objects.filter(
        Q(log_time__date__lt=date_to)
    )


def parse_none_string(string: any) -> str:
    return "\-" if string is None else clean_message(string)


def clean_message(string: str) -> str:
    cleaner = re.compile(r"([_\*\[\]\(\)~`>#\+\-=|{}\.!])", re.MULTILINE)
    string = cleaner.sub(r"\\\1", string)
    return string


def send_message(message, chat_id):
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
    }
    response = requests.post(
        f"{TELEGRAM_URL}{TUTORIAL_BOT_TOKEN}/sendMessage", data=data
    )
    if(response.status_code != 200):
        print(response.status_code)
        print(response.reason)
        print(response.content)
        print(message)
        send_message("Si è verificato un errore sul server\! Riprova più tardi", chat_id)


def printdebug(string:any):
    if ISDEBUG:
        print(string)


def print_mail_field(email:str) -> str:
    if email is None:
        return ' \- '
    else:
        return f"{clean_message(email)}"


class CocaBotView(View):
    def post(self, request, *args, **kwargs):
        if FORCEANSWER:
            print("Answer forced")
            send_message(f"Si è verificato un errore sul server\! Riprova più tardi")
            return JsonResponse({"ok": "POST request processed"})
        t_data = json.loads(request.body)
        print(t_data)
        t_message = t_data["message"]
        t_chat = t_message["chat"]

        if 'id' in t_message['from'].keys():
            t_user = t_message['from']['id']
        else:
            t_user = None

        if 'username' in t_message['from'].keys():
            t_user_name = t_message['from']['username']
        else:
            t_user_name = f"user_{t_user}"


        # print(t_message)

        try:
            text = t_message["text"].strip().lower()
        except Exception as e:
            return JsonResponse({"ok": "POST request processed"})
        printdebug(text)

        applog = AppLogs(
            username=t_user_name,
            command=text
        )

        applog.save()

        text = text.lstrip("/")
        s = split(text, posix=True)

        try:

            if s[0] == 'start':
                send_message(f'Benvenuto sul bot della *Comunità Capi AGESCI Avellino 1*\n'
                             f'Se sei un capo di questa Comunità Capi usa il codice ricevuto per email per registrarti\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            if (s[0] == 'info') | (s[0] == 'socio'):
                return self.get_info(s, t_user, t_chat)

            if (s[0] == 'codicesocio') | (s[0] == 'codice'):
                return self.get_codice(s, t_user, t_chat)

            if s[0] == 'generacodice':
                return self.generate_codes(s, t_user, t_chat)
            if s[0] == 'inviacodice':
                if len(s) < 2:
                    send_message("Non mi hai detto a chi devo mandare il codice\!", t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
                return self.invia_codice_per_mail(s[1], t_chat['id'])

            if s[0] == 'aggiungiadmin':
                return self.crea_admin(s, t_user, t_chat)

            if s[0] == 'aggiungicapo':
                return self.crea_coca(s, t_user, t_chat)

            if s[0] == 'rimuoviadmin':
                return self.rimuovi_admin(s, t_user, t_chat)

            if s[0] == 'rimuovicapo':
                return self.rimuovi_coca(s, t_user, t_chat)

            if s[0] == 'aggiorna':
                return self.aggiorna_lista(s, t_user, t_chat)

            if s[0] == 'help':
                return self.help(t_chat['id'])

            if s[0] == 'registrami':
                return self.registrami(s, t_user, t_chat)

            if s[0] == 'autorizzami':
                return self.registrami(s, t_user, t_chat)

            if s[0] == 'attiva':
                return self.imposta_status(s, t_user, t_chat, True)

            if s[0] == 'disattiva':
                return self.imposta_status(s, t_user, t_chat, False)

            if s[0] == 'attiva':
                return self.imposta_status(s, t_user, t_chat, True)

            if s[0] == 'abilitati':
                return self.abilitati(s, t_user, t_chat)

            if s[0] == 'getlog':
                return self.get_log(s, t_user, t_chat)

            if s[0] == 'clearlog':
                return self.clear_log(s, t_user, t_chat)
        except Exception as e:
            send_message("Si è verificato un errore sul server\! Riprova più tardi")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            printdebug(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return JsonResponse({"ok": "POST request processed"})

        send_message(f'Mi dispice, ma non so cosa significa "{t_message["text"]}", la mia intelligenza è limitata\. Usa /help per vedere cosa so fare\!',
                          t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def clear_log(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_super_admin(t_user, t_chat["id"]):
            get_logs_by_date_lt(7).delete()
            send_message("Fatto\!", t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})
        return JsonResponse({"ok": "POST request processed"})

    def registrami(self, s: list, t_user: str, t_chat: dict, t_user_name: str) -> JsonResponse:
        if len(s) < 2:
            send_message("Non mi hai dato il codice di autorizzazione. Richiedilo ai tuoi capigruppo\!", t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})
        nuovo_iscritto_set = get_iscritto_by_telegram(t_user)
        if nuovo_iscritto_set.count() != 1:
            send_message("Il codice di autorizzaiozne inviato non è valido!", t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        iscritto_set = get_iscritto_by_telegram(t_user)
        if iscritto_set.count() > 0:
            iscritto = iscritto_set[0]
            send_message(f'Questo nick telegram è già registrato per {clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}', t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        nuovo_iscritto = nuovo_iscritto_set[0]
        if nuovo_iscritto.telegram is None:
            if not nuovo_iscritto.active:
                send_message(f'L\'utente {clean_message(nuovo_iscritto.nome)} {clean_message(nuovo_iscritto.cognome)} non è attivo')
            nuovo_iscritto.telegram_id = t_user
            nuovo_iscritto.telegram = t_user
            nuovo_iscritto.save(force_update=True)
            send_message(f'Complimenti, questo nich è stato registrato per {clean_message(nuovo_iscritto.nome)} {clean_message(nuovo_iscritto.cognome)}',
                              t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        send_message(f'{clean_message(nuovo_iscritto.nome)} {clean_message(nuovo_iscritto.cognome)} ha già un account telegram associato', t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def get_codice(self, s, t_user, t_chat):
        if self.check_user(t_user, t_chat["id"]):
            show_all = False
            if len(s) < 2:
                # send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                # return JsonResponse({"ok": "POST request processed"})
                search_string = '*'
                show_all=True
            else:
                search_string = s[1]
                if search_string == "tutti":
                    show_all = True

            if len(s) >= 3:
                show_only_active = (s[2] == 'attivi')
            else:
                show_only_active = True

            printdebug(f"Show only active: {show_only_active}")

            iscritti_set = get_iscritti(search_string, show_only_active=show_only_active, show_all=show_all)

            message_text = ''
            counter = 0

            for iscritto in iscritti_set:
                if (not show_only_active) | iscritto.active:
                    counter += 1
                    iscritto_text = f'*Codice Socio:* {clean_message(str(iscritto.codice_socio))}\n' \
                                    f'*Nome:* {clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}\n' \
                                    f'*Branca:* {clean_message(iscritto.branca)}\n'
                    iscritto_text += f'\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n'
                    send_message(iscritto_text, t_chat["id"])

            if counter < 1:
                message_text = 'Nessun iscritto con i criteri di ricerca specificati'
                send_message(message_text, t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                message_text = f"*Soci trovati:* {counter}"
                send_message(message_text, t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            # send_message(message_text, t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def get_info(self, s, t_user, t_chat):
        if self.check_user(t_user, t_chat["id"]):
            show_all = False
            if len(s) < 2:
                # send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                # return JsonResponse({"ok": "POST request processed"})
                search_string = '*'
                show_all = True
            else:
                search_string = s[1]
                if search_string == "tutti":
                    show_all = True

            if len(s) >= 3:
                show_only_active = (s[2] == 'attivi')
            else:
                show_only_active = True

            printdebug(f"Show only active: {show_only_active}")

            iscritti_set = get_iscritti(search_string, show_only_active=show_only_active, show_all=show_all)

            # message_text = ''
            if iscritti_set.count() < 1:
                message_text = 'Nessun iscritto con i criteri di ricerca specificati'
                send_message(message_text, t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            counter = 0

            try:
                for iscritto in iscritti_set:
                    if (not show_only_active) | iscritto.active:
                        counter+=1
                        printdebug(f'*Nome:* {iscritto.nome} {iscritto.cognome}')
                        iscritto_text = ''
                        iscritto_text += f'*Codice Socio:* {clean_message(str(iscritto.codice_socio))}\n' \
                                        f'*Codice Fiscale:* {clean_message(iscritto.codice_fiscale)}\n' \
                                        f'*Nome:* {clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}\n' \
                                        f'*Sesso:* {clean_message(iscritto.sesso)}\n' \
                                        f'*Data e luogo di nascita:* {clean_message(str(iscritto.data_di_nascita))} \- {clean_message(iscritto.comune_di_nascita)}\n' \
                                        f'*Residenza:* {clean_message(iscritto.indirizzo)} {clean_message(iscritto.civico)}, {clean_message(iscritto.cap)} {clean_message(iscritto.comune)} \({clean_message(iscritto.provincia)}\)\n' \
                                        f'*Privacy:* *_2\.a_* {"Si" if iscritto.informativa2a else "No"} \- *_2\.b_* {"Si" if iscritto.informativa2b else "No"} \- *_Immagini_* {"Si" if iscritto.consenso_immagini else "No"}\n' \
                                        f'*Branca:* {clean_message(iscritto.branca)}\n' \
                                        f'*Cellulare:* {parse_none_string(iscritto.cellulare)}\n' \
                                        f'*Email:* {print_mail_field(iscritto.email)}\n' \
                                        f'*Fo\.Ca\.:* {clean_message(iscritto.livello_foca)}\n'
                        # print(iscritto_text)
                        if self.check_admin(t_user, t_chat['id'], False):
                            iscritto_text += f'*Ruolo:* {clean_message(iscritto.get_role_display())}\n'
                            iscritto_text += f'*Telegram:* {"" if iscritto.telegram is None else "@"}{parse_none_string(iscritto.telegram)}\n'
                            iscritto_text += f'*AuthCode:* {parse_none_string(iscritto.authcode)}\n'
                            iscritto_text += f'*Attivo:* {"Si" if iscritto.active else "No"}\n'

                        # print(iscritto_text)
                        iscritto_text += f'\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n'
                        printdebug(iscritto_text)
                        send_message(iscritto_text, t_chat["id"])
                if counter < 1:
                    message_text = 'Nessun iscritto con i criteri di ricerca specificati'
                    send_message(message_text, t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
                else:
                    message_text = f"*Soci trovati:* {counter}"
                    send_message(message_text, t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
            except Exception as e:
                printdebug(e)
                if ISDEBUG:
                    traceback.print_exc(file=sys.stdout)
                raise e

            # if message_text == '':
            #     message_text = 'Nessun iscritto con i criteri di ricerca specificati'


            # self.send_message(message_text, t_chat["id"])
            # print(f'Messaggio inviato: {message_text}')
        return JsonResponse({"ok": "POST request processed"})

    def abilitati(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            iscritti_set = get_enabled()
            text=''
            for iscritto in iscritti_set:
                text += f"@{iscritto.telegram}: {clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}\n"

            if iscritti_set.count() < 1:
                text = 'Non trovo iscritti abilitati'
            send_message(text, t_chat['id'])

        return JsonResponse({"ok": "POST request processed"})

    def generate_codes(self, s, t_user, t_chat):
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) > 1:
                if s[1] == 'tutti':
                    iscritti = Iscritti.objects.filter(
                        Q(coca=True)
                    )
                else:
                    iscritti = get_iscritti(s[1]).filter(
                        Q(coca=True)
                    )
            else:
                iscritti = Iscritti.objects.filter(
                    Q(coca=True) &
                    Q(authcode__isnull=True)
                )

            for iscritto in iscritti:
                authcode = secrets.token_urlsafe(6)
                iscritto.authcode = authcode
                iscritto.save(force_update=True)
                send_message(f'Authcode per {clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}: *{clean_message(iscritto.authcode)}*',
                                  t_chat["id"])

            send_message(f'Aggiornati *{iscritti.count()}* authcode', t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def crea_admin(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                send_message("Non mi hai dato niente da cercare\!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            iscritti_set = get_iscritto_by_codice(s[1])
            if iscritti_set.count() != 1:
                send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if not iscritto.role == 'SA':
                iscritto.role = 'AD'
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è ora un amministratore del bot', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                if self.check_super_admin(t_user, t_chat["id"], False):
                    utente_set = get_iscritto_by_telegram(t_user)
                    if utente_set.count() == 1:
                        utente = utente_set[0]
                        if utente.codice_socio == iscritto.codice_socio:
                            send_message(f'Non puoi toglierti i poteri da solo\!', t_chat["id"])
                            return JsonResponse({"ok": "POST request processed"})
                    else:
                        send_message(f'Qualcosa non ha funzionato', t_chat["id"])
                        return JsonResponse({"ok": "POST request processed"})
                    iscritto.role = 'AD'
                    iscritto.save()
                    send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è ora un amministratore del bot\!', t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})

                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è già superamministratore del bot\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
        return JsonResponse({"ok": "POST request processed"})

    def crea_coca(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                send_message("Non mi hai dato niente da cercare\!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            iscritti_set = get_iscritto_by_codice(s[1])
            if iscritti_set.count() != 1:
                send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA') & (not iscritto.role == 'AD'):
                iscritto.role = 'CA'
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è stato aggiunt{self.get_gendered_string(iscritto.sesso, "o", "a")} in Co\.Ca\.', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                utente_set = get_iscritto_by_telegram(t_user)
                if utente_set.count() == 1:
                    utente = utente_set[0]
                    if utente.codice_socio == iscritto.codice_socio:
                        send_message(f'Non puoi toglierti i poteri da solo\!', t_chat["id"])
                        return JsonResponse({"ok": "POST request processed"})
                else:
                    send_message(f'Qualcosa non ha funzionato...', t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
                iscritto.role = 'CA'
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)}è stato aggiunt{self.get_gendered_string(iscritto.sesso, "o", "a")} in Co\.Ca\.\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def imposta_status(self, s: list, t_user: str, t_chat: dict, status:bool) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                send_message("Non mi hai dato niente da cercare\!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            iscritti_set = get_iscritto_by_codice(s[1])
            if iscritti_set.count() != 1:
                send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA') & (not iscritto.role == 'AD'):
                iscritto.active = status
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è stato {"" if status else "dis"}attivat{self.get_gendered_string(iscritto.sesso,"o", "a")}', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                utente_set = get_iscritto_by_telegram(t_user)
                if utente_set.count() == 1:
                    utente = utente_set[0]
                    if utente.codice_socio == iscritto.codice_socio:
                        send_message(f'Non puoi toglierti i poteri da solo\!', t_chat["id"])
                        return JsonResponse({"ok": "POST request processed"})
                else:
                    send_message(f'Qualcosa non ha funzionato...', t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
                iscritto.active = status
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è stato {"" if status else "dis"}attivat{self.get_gendered_string(iscritto.sesso, "o", "a")}', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def rimuovi_coca(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                send_message("Non mi hai dato niente da cercare\!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritto_by_codice(s[1])

            if iscritti_set.count() != 1:
                send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA') & (not iscritto.role == 'AD'):
                iscritto.role = 'IS'
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è stato rimoss{self.get_gendered_string(iscritto.sesso, "o", "a")} dalla Co\.Ca\.\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} non può essere depotenziat{self.get_gendered_string(iscritto.sesso, "o", "a")} da te perché è {clean_message(iscritto.get_role_display())}\!',
                                  t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def rimuovi_admin(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_super_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                send_message("Non mi hai dato niente da cercare\!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritto_by_codice(s[1])

            if iscritti_set.count() != 1:
                send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA'):
                iscritto.role = 'IS'
                iscritto.save()
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è stato rimoss{self.get_gendered_string(iscritto.sesso, "o", "a")} dagli amministratori e dalla Co\.Ca\.\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                send_message(f'{clean_message(iscritto.nome)} {clean_message(iscritto.cognome)} è superamministratore, non puoi depotenziarl{self.get_gendered_string(iscritto.sesso, "o", "a")}\!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def get_log(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_super_admin(t_user, t_chat["id"]):
            max_days = 7
            if len(s) > 1:
                try:
                    max_days = int(s[1])
                except:
                    max_days = 7
            log_set = get_logs_by_date_gte(max_days)
            for logentry in log_set:
                text=clean_message(f"{logentry.log_time}: {logentry.username} - {logentry.command}")
                send_message(text,t_chat['id'])

        return JsonResponse({"ok": "POST request processed"})


    def aggiorna_lista(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            url = settings.SHAREPOINT_URL
            username = settings.SHAREPOINT_USERNAME
            password = settings.SHAREPOINT_PASSWORD
            documents = settings.DOCUMENTS_URL
            loader = DataLoader(url, username, password, documents)
            send_message(f'Sto leggendo il file excel remoto', t_chat["id"])
            (nuovi, aggiornati) = loader.loadRemoteIntoDb()
            send_message(f'Ho inserito {nuovi} nuovi iscritti e aggiornato gli altri {aggiornati}', t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def invia_codice_per_mail(self, to_user: str, chat_id: int) -> JsonResponse:
        iscritto_set = get_iscritto_by_codice(to_user)
        iscritto_set.filter(
            Q(authcode__isnull=False) |
            Q(email__isnull=False)
        )
        if iscritto_set.count() == 1:
            iscritto = iscritto_set[0]
            if (not iscritto.authcode is None) & (not iscritto.email is None):
                subject = "Accesso al bot telegram della Comunità Capi Avellino 1"
                message = f'Ciao {iscritto.nome} {iscritto.cognome},\n' \
                          f'Per accedere al bot devi essere autenticat{self.get_gendered_string(iscritto.sesso, "o", "a")}.\n' \
                          f'Il tuo codice autorizzazione e\' {iscritto.authcode}' \
                          f'Accedi al bot con telegram t.me/AV1CoCaBot e digita il comando /registrami {iscritto.authcode}.\n' \
                          f'Fraternamente,\n' \
                          f'Il tuo amico bot di quartiere'
                message_html = f'<p>Ciao {iscritto.nome} {iscritto.cognome},</p>' \
                               f'<p>Per accedere al bot devi essere autenticat{self.get_gendered_string(iscritto.sesso, "o", "a")}.<br/>' \
                               f'Il tuo codice autorizzazione &egrave; <strong>{iscritto.authcode}</strong></p>' \
                               f'<p>Accedi al bot con telegram <a href="https://t.me/AV1CoCaBot">https://t.me/AV1CoCaBot</a> e digita il comando /registrami {iscritto.authcode}.</p>' \
                               f'<p>Fraternamente,<br/>' \
                               f'Il tuo amico bot di quartiere</p>'
                email_from = settings.EMAIL_FROM
                recipient_list = iscritto.email.split(';')
                send_mail(subject, message, email_from, recipient_list, fail_silently=False, html_message=message_html)
                send_message('Email inviata\!', chat_id)
                return JsonResponse({"ok": "POST request processed"})
        send_message('Non ti ho trovato nell\'elenco, chiedi aiuto ai capigruppo\!', chat_id)
        return JsonResponse({"ok": "POST request processed"})

    def help(self, chat_id: int) -> JsonResponse:
        help_text = ''
        help_text += '/info - Ottiene le info di un socio del gruppo, si può cercare per cognome, nome, codice socio, codice fiscale o unità [L/C, E/G, R/S, Adulti]\n'
        help_text += '/codicesocio - Ottiene il codice socio di un socio del gruppo, si può cercare per cognome, nome, codice socio, codice fiscale o unità [L/C, E/G, R/S, Adulti]\n'
        help_text += '/generacodice - Genera il codice di autorizzazione per potersi abilitare all\'uso del bot\n'
        help_text += '/inviacodice - Invia il di autorizzazione per potersi abilitare all\'uso del bot all\'indirizzo email registrato su Buonastrada, si può cercare per codice socio, codice fiscale\n'
        help_text += '/registrami - Registra l\'account telegram al bot. Richiede codice di autorizzazione\n'
        help_text += '/aggiungiadmin - Aggiunge un amministratore del bot. Solo per amministratori\n'
        help_text += '/aggiungicapo - Aggiunge un un capo del gruppo. Solo per amministratori\n'
        help_text += '/rimuoviadmin - Rimuove un amministratore del bot. Solo per amministratori\n'
        help_text += '/rimuovicapo - Rimuove un un capo del gruppo. Solo per amministratori\n'
        help_text += '/aggiorna - Aggiorna la lista soci dal file excel su onedrive. Solo per amministratori\n'
        help_text += '/attiva - Attiva un iscritto. Solo per amministratorii\n'
        help_text += '/disattiva - Disattiva un iscritto. Solo per amministratori\n'
        help_text += '/abilitati - Lista abilitati. Solo per amministratori\n'
        help_text += '/help - Mostra questa guida ai comandi\n'
        send_message(clean_message(help_text), chat_id)
        return JsonResponse({"ok": "POST request processed"})

    def get_gendered_string(self, sesso: str, maschile: str, femminile: str) -> str:
        return maschile if sesso == 'M' else femminile

    def send_not_authorized_message(self, chat_id):
        send_message('Spiacente, ma non sei autorizzato/a', chat_id)

    def check_user(self, t_user, chat_id, send_message_back=True):
        return self.check_role(t_user, chat_id, ['SA', 'AD', 'CA'], send_message_back)

    def check_admin(self, t_user, chat_id, send_message_back=True):
        return self.check_role(t_user, chat_id, ['SA', 'AD'], send_message_back)

    def check_super_admin(self, t_user, chat_id, send_message_back=True):
        return self.check_role(t_user, chat_id, ['SA'], send_message_back)

    def check_role(self, t_user: str, chat_id: int, roles: list, send_message_back=True):
        if t_user is None:
            if send_message_back:
                self.send_not_authorized_message(chat_id)
            return False

        try:
            user: Iscritti = Iscritti.objects.get(telegram=t_user)
        except Iscritti.DoesNotExist:
            # print("Ko")
            if send_message_back:
                self.send_not_authorized_message(chat_id)
            return False
        except Iscritti.MultipleObjectsReturned:
            # print("Ko")
            if send_message_back:
                self.send_not_authorized_message(chat_id)
            return False
        except:
            # print("Ko")
            if send_message_back:
                self.send_not_authorized_message(chat_id)
            return False

        if user.role in roles:
            # print("Ok")
            return True & user.active
        else:
            # print("Ko")
            if send_message_back:
                self.send_not_authorized_message(chat_id)
            return False

    def check_role_for_iscritto(self, search_string: str, roles: list):
        try:
            user: Iscritti = Iscritti.objects.get(
                Q(codice_socio=search_string) |
                Q(codice_fiscale__iexact=search_string)
            )
        except Iscritti.DoesNotExist:
            return False
        except Iscritti.MultipleObjectsReturned:
            return False
        except:
            return False

        if user.role in roles:
            return True & user.active
        else:
            return False
