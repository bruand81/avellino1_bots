from django.core.management import BaseCommand
from django.conf import settings
from django.db import transaction

import pandas as pd

from utils.DataLoader import DataLoader


class Command(BaseCommand):
    def handle(self, *args, **options):
        url = settings.SHAREPOINT_URL
        username = settings.SHAREPOINT_USERNAME
        password = settings.SHAREPOINT_PASSWORD
        documents = settings.DOCUMENTS_URL
        loader = DataLoader(url, username, password, documents)
        print("Caricamento file excel")
        (nuovi, aggiornati) = loader.loadRemoteIntoDb()
        print(f'Ho inserito {nuovi} nuovi iscritti e aggiornato gli altri {aggiornati}')