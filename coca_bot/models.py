from django.db import models
from django.utils.translation import gettext_lazy as _


# Create your models here.
class Iscritti(models.Model):
    id = models.AutoField(primary_key=True)
    codice_fiscale = models.TextField(null=False, unique=True)
    codice_socio = models.TextField(null=False)
    nome = models.TextField(null=False)
    cognome = models.TextField(null=False)
    sesso = models.CharField(max_length=1, choices=(
        ('M', _('Maschio')),
        ('F', _('Femmina'))
    ))
    data_di_nascita = models.DateField(null=False)
    comune_di_nascita = models.TextField(null=False, default="Avellino")
    indirizzo = models.TextField(null=False)
    civico = models.TextField()
    comune = models.TextField(null=False, default="Avellino")
    provincia = models.CharField(null=False, max_length=2, default="AV")
    cap = models.TextField(null=False, default="83100")
    informativa2a = models.BooleanField(null=False, default=True, verbose_name="Consenso privacy 2.a")
    informativa2b = models.BooleanField(null=False, default=True, verbose_name="Consenso privacy 2.b")
    consenso_immagini = models.BooleanField(null=False, default=True, verbose_name="Consenso immagini")
    livello_foca = models.TextField(null=True, default=None)
    coca = models.BooleanField(null=False, default=False)
    branca = models.TextField(null=False, choices=(
        ('Branca L/C', _('Branca L/C')),
        ('Branca E/G', _('Branca E/G')),
        ('Branca R/S', _('Branca R/S')),
        ('Adulti', _('Co.Ca.'))
    ))
    cellulare = models.TextField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    telegram = models.TextField(null=True, blank=True)
    telegram_id = models.TextField(null=True, blank=True)
    authcode = models.TextField(null=True, blank=True)
    active = models.BooleanField(null=False, default=True)
    role = models.CharField(max_length=2, choices=(
        ('SA', _('Super Admin')),
        ('AD', _('Admin')),
        ('CA', _('Capo')),
        ('IS', _('Iscritto')),
    ), default='IS')

    class Meta:
        verbose_name = 'Iscritto'
        verbose_name_plural = 'Iscritti'


class AppLogs(models.Model):
    log_time = models.DateTimeField(auto_now_add=True)
    username = models.TextField(blank=False)
    command = models.TextField(blank=False)

    class Meta:
        verbose_name = 'Log'
        verbose_name_plural = 'Logs'