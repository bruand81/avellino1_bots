from django.contrib import admin

# Register your models here.
from coca_bot.models import Iscritti, AppLogs


class IscrittiAdmin(admin.ModelAdmin):
    list_display = ('codice_socio', 'nome', 'cognome', 'codice_fiscale', 'branca', 'telegram')
    # list_filter = ('codice_socio', 'nome', 'cognome', 'codice_fiscale', 'branca')
    sortable_by = ('codice_socio', 'nome', 'cognome', 'codice_fiscale', 'branca')
    search_fields = ('codice_socio', 'nome', 'cognome', 'codice_fiscale', 'branca')

class AppLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'command', 'log_time')
    list_filter = ('username', 'command')
    sortable_by = ('id', 'username', 'command', 'log_time')
    search_fields = ('username', 'command', 'log_time')

admin.site.register(Iscritti, IscrittiAdmin)
admin.site.register(AppLogs, AppLogAdmin)