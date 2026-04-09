from django.contrib import admin

# Register your models here.

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count, Prefetch
from django.utils.html import format_html

from .models import User, Event, Participant, Registration


# ─────────────────────────────────────────
# USER
# ─────────────────────────────────────────

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Étend l'admin User de base pour afficher et éditer le champ `role`.
    """
    list_display  = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter   = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Rôle applicatif', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Rôle applicatif', {'fields': ('role',)}),
    )


# ─────────────────────────────────────────
# INSCRIPTION (inline pour Event et Participant)
# ─────────────────────────────────────────

class RegistrationInlineForEvent(admin.TabularInline):
    """Inscriptions affichées directement dans la page d'un événement."""
    model               = Registration
    extra               = 0
    fields              = ('participant', 'status', 'registered_at', 'notes')
    readonly_fields     = ('registered_at',)
    autocomplete_fields = ('participant',)

    def get_queryset(self, request):
        # Évite le N+1 sur participant + user dans l'inline
        return super().get_queryset(request).select_related('participant__user')


class RegistrationInlineForParticipant(admin.TabularInline):
    """Inscriptions affichées directement dans la page d'un participant."""
    model               = Registration
    extra               = 0
    fields              = ('event', 'status', 'registered_at', 'notes')
    readonly_fields     = ('registered_at',)
    autocomplete_fields = ('event',)

    def get_queryset(self, request):
        # Évite le N+1 sur event dans l'inline
        return super().get_queryset(request).select_related('event')


# ─────────────────────────────────────────
# EVENT
# ─────────────────────────────────────────

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display    = ('title', 'location', 'date', 'status', 'nb_registrations')
    list_filter     = ('status', 'date')
    search_fields   = ('title', 'location', 'description')
    date_hierarchy  = 'date'
    readonly_fields = ('created_at', 'updated_at')
    inlines         = [RegistrationInlineForEvent]

    fieldsets = (
        ('Informations générales', {
            'fields': ('title', 'description', 'location', 'status')
        }),
        ('Dates', {
            'fields': ('date',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['publish_events', 'cancel_events']

    def get_queryset(self, request):
        # Annote le nombre d'inscriptions en une seule requête
        # → évite 1 requête COUNT par ligne dans la liste
        return super().get_queryset(request).annotate(
            _nb_registrations=Count('registrations')
        )

    @admin.display(description="Inscriptions", ordering='_nb_registrations')
    def nb_registrations(self, obj):
        # Lit la valeur annotée, pas de requête supplémentaire
        return format_html('<b>{}</b>', obj._nb_registrations)

    @admin.action(description="Publier les événements sélectionnés")
    def publish_events(self, request, queryset):
        updated = queryset.update(status=Event.Status.PUBLISHED)
        self.message_user(request, f"{updated} événement(s) publié(s).")

    @admin.action(description="Annuler les événements sélectionnés")
    def cancel_events(self, request, queryset):
        updated = queryset.update(status=Event.Status.CANCELLED)
        self.message_user(request, f"{updated} événement(s) annulé(s).")


# ─────────────────────────────────────────
# PARTICIPANT
# ─────────────────────────────────────────

class HasAccountFilter(admin.SimpleListFilter):
    title          = "compte lié"
    parameter_name = "has_account"

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Avec compte'),
            ('no',  'Sans compte'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(user__isnull=False)
        if self.value() == 'no':
            return queryset.filter(user__isnull=True)
        return queryset


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display    = ('full_name_display', 'contact_email_display', 'phone', 'has_account', 'nb_registrations')
    list_filter     = (HasAccountFilter,)
    search_fields   = ('first_name', 'last_name', 'email', 'user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)
    inlines         = [RegistrationInlineForParticipant]

    fieldsets = (
        ('Compte lié', {
            'fields': ('user',),
            'description': (
                "Si un compte est sélectionné, le nom et l'email "
                "sont lus depuis ce compte (pas de doublon)."
            ),
        }),
        ('Coordonnées locales', {
            'fields': ('first_name', 'last_name', 'email', 'phone'),
            'description': "Remplir uniquement si aucun compte n'est lié.",
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        # select_related('user') → évite 1 requête par ligne pour accéder
        #   à user.first_name / user.email dans full_name et contact_email
        # annotate(_nb_registrations) → évite 1 COUNT par ligne
        return (
            super().get_queryset(request)
            .select_related('user')
            .annotate(_nb_registrations=Count('registrations'))
        )

    @admin.display(description="Nom", ordering='last_name')
    def full_name_display(self, obj):
        return obj.full_name

    @admin.display(description="Email")
    def contact_email_display(self, obj):
        return obj.contact_email

    @admin.display(description="Compte ?", boolean=True)
    def has_account(self, obj):
        # user déjà chargé via select_related → pas de requête
        return obj.user is not None

    @admin.display(description="Inscriptions", ordering='_nb_registrations')
    def nb_registrations(self, obj):
        # Lit la valeur annotée, pas de requête supplémentaire
        return obj._nb_registrations


# ─────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display        = ('participant', 'event', 'status', 'registered_at')
    list_filter         = ('status', 'event__status', 'registered_at')
    search_fields       = (
        'participant__first_name', 'participant__last_name',
        'participant__email', 'participant__user__email',
        'event__title',
    )
    readonly_fields     = ('registered_at',)
    autocomplete_fields = ('participant', 'event')
    date_hierarchy      = 'registered_at'

    fieldsets = (
        (None, {
            'fields': ('participant', 'event', 'status', 'notes')
        }),
        ('Métadonnées', {
            'fields': ('registered_at',),
            'classes': ('collapse',),
        }),
    )

    actions = ['confirm_registrations', 'cancel_registrations']

    def get_queryset(self, request):
        # Charge participant + son user + event en une seule requête
        # → évite le N+1 sur __str__ de participant (qui accède à user)
        return (
            super().get_queryset(request)
            .select_related('participant__user', 'event')
        )

    @admin.action(description="Confirmer les inscriptions sélectionnées")
    def confirm_registrations(self, request, queryset):
        updated = queryset.update(status=Registration.Status.CONFIRMED)
        self.message_user(request, f"{updated} inscription(s) confirmée(s).")

    @admin.action(description="Annuler les inscriptions sélectionnées")
    def cancel_registrations(self, request, queryset):
        updated = queryset.update(status=Registration.Status.CANCELLED)
        self.message_user(request, f"{updated} inscription(s) annulée(s).")