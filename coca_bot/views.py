import json
import os

import requests
from django.http import JsonResponse
from django.views import View
from shlex import split
from django.db.models import Q, QuerySet
from django.core.mail import send_mail
from django.conf import settings

from coca_bot.models import Iscritti, AppLogs
import secrets

from utils.DataLoader import DataLoader

TELEGRAM_URL = "https://api.telegram.org/bot"
TUTORIAL_BOT_TOKEN = os.getenv("TUTORIAL_BOT_TOKEN", "error_token")


# https://api.telegram.org/bot<token>/setWebhook?url=<url>/webhooks/tutorial/
def get_iscritti(search_string):
    return Iscritti.objects.filter(
        Q(cognome__icontains=search_string) |
        Q(nome__icontains=search_string) |
        Q(codice_socio__icontains=search_string) |
        Q(codice_fiscale__icontains=search_string) |
        Q(branca__icontains=search_string)
    )


def get_iscritto_by_codice(search_string: str) -> QuerySet:
    return Iscritti.objects.filter(
        Q(codice_socio__iexact=search_string) |
        Q(codice_fiscale__iexact=search_string)
    )


def get_iscritto_by_telegram(t_user: str) -> QuerySet:
    return Iscritti.objects.filter(
        Q(telegram__iexact=t_user)
    )


def get_iscritto_by_authcode(authcode: str) -> QuerySet:
    return Iscritti.objects.filter(
        Q(authcode__iexact=authcode)
    )


def parse_none_string(string: any) -> str:
    return "-" if string is None else string


class CocaBotView(View):
    def post(self, request, *args, **kwargs):
        t_data = json.loads(request.body)
        t_message = t_data["message"]
        t_chat = t_message["chat"]
        if 'username' in t_message['from'].keys():
            t_user = t_message['from']['username']
        else:
            t_user = None
        # print(t_message)

        try:
            text = t_message["text"].strip().lower()
        except Exception as e:
            return JsonResponse({"ok": "POST request processed"})

        applog = AppLogs(
            username=t_user,
            command=text
        )

        applog.save()

        text = text.lstrip("/")
        s = split(text, posix=True)

        if s[0] == 'info':
            return self.get_info(s, t_user, t_chat)

        if s[0] == 'codicesocio':
            return self.get_codice(s, t_user, t_chat)

        if s[0] == 'generacodice':
            return self.generate_codes(s, t_user, t_chat)
        if s[0] == 'inviacodice':
            if len(s) < 2:
                self.send_message("Non mi hai detto a chi devo mandare il codice!", t_chat["id"])
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

        self.send_message(f'Mi dispice, ma non so cosa significa "{t_message["text"]}", la mia intelligenza è limitata. Usa /help per vedere cosa so fare!',
                          t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def registrami(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if len(s) < 2:
            self.send_message("Non mi hai dato il codice di autorizzazione. Richiedilo ai tuoi capigruppo!", t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})
        nuovo_iscritto_set = get_iscritto_by_telegram(t_user)
        if nuovo_iscritto_set.count() != 1:
            self.send_message("Il codice di autorizzaiozne inviato non è valido!", t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        iscritto_set = get_iscritto_by_telegram(t_user)
        if iscritto_set.count() > 0:
            iscritto = iscritto_set[0]
            self.send_message(f'Questo nick telegram è già registrato per {iscritto.nome} {iscritto.cognome}', t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        nuovo_iscritto = nuovo_iscritto_set[0]
        if nuovo_iscritto.telegram is None:
            nuovo_iscritto.telegram = t_user
            nuovo_iscritto.save(force_update=True)
            self.send_message(f'Complimenti, questo nich è stato registrato per {nuovo_iscritto.nome} {nuovo_iscritto.cognome}',
                              t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        self.send_message(f'{nuovo_iscritto.nome} {nuovo_iscritto.cognome} ha già un account telegram associato', t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def get_codice(self, s, t_user, t_chat):
        if self.check_user(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritti(s[1])

            message_text = ''

            for iscritto in iscritti_set:
                iscritto_text = f'***Codice Socio:*** {iscritto.codice_socio}\n' \
                                f'***Nome:*** {iscritto.nome} {iscritto.cognome}\n' \
                                f'***Branca:*** {iscritto.branca}\n' \
                                f'--------------------------------------\n'
                message_text += iscritto_text

            if message_text == '':
                message_text = 'Nessun iscritto con i criteri di ricerca specificati'

            self.send_message(message_text, t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def get_info(self, s, t_user, t_chat):
        if self.check_user(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritti(s[1])

            # message_text = ''
            if iscritti_set.count() < 1:
                message_text = 'Nessun iscritto con i criteri di ricerca specificati'
                self.send_message(message_text, t_chat["id"])

            for iscritto in iscritti_set:
                print(f'***Nome:*** {iscritto.nome} {iscritto.cognome}')
                iscritto_text = ''
                iscritto_text += f'***Codice Socio:*** {iscritto.codice_socio}\n' \
                                f'***Codice Fiscale:*** {iscritto.codice_fiscale}\n' \
                                f'***Nome:*** {iscritto.nome} {iscritto.cognome}\n' \
                                f'***Sesso:*** {iscritto.sesso}\n' \
                                f'***Data e luogo di nascita:*** {iscritto.data_di_nascita} - {iscritto.comune_di_nascita}\n' \
                                f'***Residenza:*** {iscritto.indirizzo} {iscritto.civico}, {iscritto.cap} {iscritto.comune} ({iscritto.provincia})\n' \
                                f'***Privacy:*** ___2.a___ {"Si" if iscritto.informativa2a else "No"} - ___2.b___ {"Si" if iscritto.informativa2b else "No"} - ___Immagini___ {"Si" if iscritto.consenso_immagini else "No"}\n' \
                                f'***Branca:*** {iscritto.branca}\n' \
                                f'***Cellulare:*** {parse_none_string(iscritto.cellulare)}\n' \
                                f'***Email:*** {parse_none_string(iscritto.email)}\n' \
                                f'***Fo.Ca.:*** {iscritto.livello_foca}\n'
                print(iscritto_text)
                if self.check_admin(t_user, t_chat['id'], False):
                    iscritto_text += f'***Ruolo:*** {iscritto.get_role_display()}\n'
                    iscritto_text += f'***Telegram:*** {"" if iscritto.telegram is None else "@"}{parse_none_string(iscritto.telegram)}\n'
                    iscritto_text += f'***AuthCode:*** {parse_none_string(iscritto.authcode)}\n'
                    iscritto_text += f'***Attivo:*** {"Si" if iscritto.active else "No"}\n'

                print(iscritto_text)
                iscritto_text += f'--------------------------------------'
                self.send_message(iscritto_text, t_chat["id"])
                print(iscritto_text)
                # message_text += iscritto_text
                # print(message_text)
                # message_text += f'--------------------------------------\n'

            # if message_text == '':
            #     message_text = 'Nessun iscritto con i criteri di ricerca specificati'


            # self.send_message(message_text, t_chat["id"])
            # print(f'Messaggio inviato: {message_text}')
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
                iscritto.authcode = secrets.token_urlsafe(6)
                iscritto.save(force_update=True)
                self.send_message(f'Authcode per {iscritto.nome} {iscritto.cognome}: ***{iscritto.authcode}***',
                                  t_chat["id"])

            self.send_message(f'Aggiornati ***{iscritti.count()}*** authcode', t_chat["id"])
        return JsonResponse({"ok": "POST request processed"})

    def crea_admin(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            iscritti_set = get_iscritto_by_codice(s[1])
            if iscritti_set.count() != 1:
                self.send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if not iscritto.role == 'SA':
                iscritto.role = 'AD'
                iscritto.save()
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è ora un amministratore del bot', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                if self.check_super_admin(t_user, t_chat["id"], False):
                    utente_set = get_iscritto_by_telegram(t_user)
                    if utente_set.count() == 1:
                        utente = utente_set[0]
                        if utente.codice_socio == iscritto.codice_socio:
                            self.send_message(f'Non puoi toglierti i poteri da solo!', t_chat["id"])
                            return JsonResponse({"ok": "POST request processed"})
                    else:
                        self.send_message(f'Qualcosa non ha funzionato...', t_chat["id"])
                        return JsonResponse({"ok": "POST request processed"})
                    iscritto.role = 'AD'
                    iscritto.save()
                    self.send_message(f'{iscritto.nome} {iscritto.cognome} è ora un amministratore del bot!', t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})

                self.send_message(f'{iscritto.nome} {iscritto.cognome} è già superamministratore del bot!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
        return JsonResponse({"ok": "POST request processed"})

    def crea_coca(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            iscritti_set = get_iscritto_by_codice(s[1])
            if iscritti_set.count() != 1:
                self.send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA') & (not iscritto.role == 'AD'):
                iscritto.role = 'CA'
                iscritto.save()
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è stato aggiunto in Co.Ca.', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                utente_set = get_iscritto_by_telegram(t_user)
                if utente_set.count() == 1:
                    utente = utente_set[0]
                    if utente.codice_socio == iscritto.codice_socio:
                        self.send_message(f'Non puoi toglierti i poteri da solo!', t_chat["id"])
                        return JsonResponse({"ok": "POST request processed"})
                else:
                    self.send_message(f'Qualcosa non ha funzionato...', t_chat["id"])
                    return JsonResponse({"ok": "POST request processed"})
                iscritto.role = 'CA'
                iscritto.save()
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è stato aggiunto in Co.Ca.!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            self.send_message(f'{iscritto.nome} {iscritto.cognome} è già in Co.Ca.!', t_chat["id"])
            return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def rimuovi_coca(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritto_by_codice(s[1])

            if iscritti_set.count() != 1:
                self.send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA') & (not iscritto.role == 'AD'):
                iscritto.role = 'IS'
                iscritto.save()
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è stato rimosso dalla Co.Ca.!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                self.send_message(f'{iscritto.nome} {iscritto.cognome} non può essere depotenziato da te perché è {iscritto.get_role_display()}!',
                                  t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def rimuovi_admin(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_super_admin(t_user, t_chat["id"]):
            if len(s) < 2:
                self.send_message("Non mi hai dato niente da cercare!", t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritti_set = get_iscritto_by_codice(s[1])

            if iscritti_set.count() != 1:
                self.send_message(f'L\'iscritto {s[1]} non è valido', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

            iscritto = iscritti_set[0]

            if (not iscritto.role == 'SA'):
                iscritto.role = 'IS'
                iscritto.save()
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è stato rimosso dagli amministratori e dalla Co.Ca.!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})
            else:
                self.send_message(f'{iscritto.nome} {iscritto.cognome} è superamministratore, non puoi depotenziarlo!', t_chat["id"])
                return JsonResponse({"ok": "POST request processed"})

        return JsonResponse({"ok": "POST request processed"})

    def aggiorna_lista(self, s: list, t_user: str, t_chat: dict) -> JsonResponse:
        if self.check_admin(t_user, t_chat["id"]):
            url = settings.SHAREPOINT_URL
            username = settings.SHAREPOINT_USERNAME
            password = settings.SHAREPOINT_PASSWORD
            documents = settings.DOCUMENTS_URL
            loader = DataLoader(url, username, password, documents)
            self.send_message(f'Sto leggendo il file excel remoto', t_chat["id"])
            (nuovi, aggiornati) = loader.loadRemoteIntoDb()
            self.send_message(f'Ho inserito {nuovi} nuovi iscritti e aggiornato gli altri {aggiornati}', t_chat["id"])
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
                               f'<p>Accedi al bot con telegram <a href="https://t.me/AV1CoCaBot">https://t.me/AV1CoCaBot</a> e digita il comando /autorizzami {iscritto.authcode}.</p>' \
                               f'<p>Fraternamente,<br/>' \
                               f'Il tuo amico bot di quartiere</p>'
                email_from = settings.EMAIL_FROM
                recipient_list = iscritto.email.split(';')
                send_mail(subject, message, email_from, recipient_list, fail_silently=False, html_message=message_html)
                self.send_message('Email inviata!', chat_id)
                return JsonResponse({"ok": "POST request processed"})
        self.send_message('Non ti ho trovato nell\'elenco, chiedi aiuto ai capigruppo!', chat_id)
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
        help_text += '/help - Mostra questa guida ai comandi\n'
        self.send_message(help_text, chat_id)
        return JsonResponse({"ok": "POST request processed"})

    def get_gendered_string(self, sesso: str, maschile: str, femminile: str) -> str:
        return maschile if sesso == 'M' else femminile

    def send_not_authorized_message(self, chat_id):
        self.send_message('Spiacente, ma non sei autorizzato/a', chat_id)

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

    @staticmethod
    def send_message(message, chat_id):
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        response = requests.post(
            f"{TELEGRAM_URL}{TUTORIAL_BOT_TOKEN}/sendMessage", data=data
        )
