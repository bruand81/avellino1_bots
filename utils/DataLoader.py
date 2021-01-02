from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.files.file import File
import pandas as pd
import tempfile
import os
from django.db import transaction

from coca_bot.models import Iscritti
import numpy as np


class DataLoader(object):
    _url = None
    _username = None
    _password = None
    _document = None
    _abs_file_url = None

    def __init__(self, url, username, password, document):
        self._url = url
        self._username = username
        self._password = password
        self._document = document
        self._abs_file_url = f'{self._url}{self._document}'

    def loadRemoteToDataframe(self) -> pd.DataFrame:
        if (not self._abs_file_url) | (not self._username) | (not self._password) | (not self._url) | (
        not self._document):
            data = f'- username: {self._username}\n' \
                   f'- password: {self._password}\n' \
                   f'- url: {self._url}\n' \
                   f'- document: {self._document}\n' \
                   f'- full_url: {self._abs_file_url}\n'
            raise Exception(f'Dati richiesti mancanti\n{data}')
        user_credentials = UserCredential(self._username, self._password)
        with tempfile.TemporaryDirectory() as local_path:
            file_name = os.path.basename(self._abs_file_url)
            with open(os.path.join(local_path, file_name), 'wb') as local_file:
                file = File.from_url(self._abs_file_url).with_credentials(user_credentials).download(
                    local_file).execute_query()
                # print("'{0}' file has been downloaded into {1}".format(file.serverRelativeUrl, local_file.name))
                df = pd.read_excel(local_file.name, engine='openpyxl', converters={'ProvinciaResidenza': str})
                df['DataDiNascita'] = pd.to_datetime(df.DataNascita).dt.strftime('%Y-%m-%d')
                return df

    def loadRemoteIntoDb(self) -> (int, int):
        df = self.loadRemoteToDataframe()
        records = df.to_records()
        nuovi = 0
        aggiornati = 0
        with transaction.atomic():
            for record in records:
                cellulare = None if str(record.Cellulare) == 'nan' else record.Cellulare
                email = None if str(record.Email) == 'nan' else record.Email
                iscritto, created = Iscritti.objects.update_or_create(
                    codice_fiscale=str(record.CodiceFiscale).strip(),
                    defaults={
                        'codice_fiscale': str(record.CodiceFiscale).strip(),
                        'codice_socio': str(record.CodiceSocio).strip(),
                        'nome': record.Nome.strip(),
                        'cognome': record.Cognome.strip(),
                        'sesso': record.Sesso.strip(),
                        'data_di_nascita': record.DataDiNascita,
                        'comune_di_nascita': record.ComuneNascita.strip(),
                        'indirizzo': record.Indirizzo.strip(),
                        'civico': record.Civico.strip(),
                        'comune': record.ComuneResidenza.strip(),
                        'provincia': (str(record.ProvinciaResidenza).strip())[:2].upper(),
                        'cap': str(record.Cap).strip(),
                        'informativa2a': (record.Informativa2a == 'Si'),
                        'informativa2b': (record.Informativa2b == 'Si'),
                        'consenso_immagini': (record.ConsensoImmagini == 'Si'),
                        'livello_foca': record.LivelloFoCa.strip(),
                        'coca': (record.CUN == 'G'),
                        'branca': record.Branca.strip(),
                        'cellulare': cellulare if cellulare is None else str(cellulare).strip(),
                        'email': email if email is None else email.strip(),
                    })
                if created:
                    nuovi += 1
                else:
                    aggiornati += 1

        return nuovi, aggiornati
                # print(f'{"CREATO" if created else "AGGIORNATO"} {iscritto.nome} {iscritto.cognome}')
