from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


# ─────────────────────────────────────────
# UTILISATEUR PERSONNALISÉ + RÔLES
# ─────────────────────────────────────────

class User(AbstractUser):
    """
    Utilisateur personnalisé avec rôles :
      - ADMIN   : accès complet (lecture + écriture)
      - VIEWER  : lecture seule
    """
    class Role(models.TextChoices):
        ADMIN  = 'admin',  'Admin / Éditeur'
        VIEWER = 'viewer', 'Visiteur (lecture seule)'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    @property
    def is_admin_or_editor(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


# ─────────────────────────────────────────
# ÉVÉNEMENT
# ─────────────────────────────────────────

class Event(models.Model):
    """Représente un événement réservable."""

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Brouillon'
        PUBLISHED = 'published', 'Publié'
        CANCELLED = 'cancelled', 'Annulé'
        COMPLETED = 'completed', 'Terminé'

    title       = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    location    = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
    date        = models.DateTimeField(verbose_name="Date")
    status      = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Statut",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.date.strftime('%d/%m/%Y')})"


# ─────────────────────────────────────────
# PARTICIPANT
# ─────────────────────────────────────────

class Participant(models.Model):
    """
    Profil d'un participant.

    Deux cas :
      1. Lié à un User (auto-inscription) → nom/email lus depuis User,
         pas de duplication.
      2. Créé par un admin sans compte    → nom/email stockés localement
         dans first_name / last_name / email.

    Les propriétés `full_name` et `contact_email` font le pont
    automatiquement selon le cas.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='participant_profile',
        verbose_name="Compte utilisateur",
        help_text="Laisser vide si le participant n'a pas de compte"
    )

    # Champs locaux — utilisés UNIQUEMENT quand user est None
    first_name = models.CharField(
        max_length=100, blank=True, verbose_name="Prénom",
        help_text="Ignoré si un compte utilisateur est lié"
    )
    last_name = models.CharField(
        max_length=100, blank=True, verbose_name="Nom",
        help_text="Ignoré si un compte utilisateur est lié"
    )
    email = models.EmailField(
        blank=True, verbose_name="Email",
        help_text="Ignoré si un compte utilisateur est lié"
    )

    phone      = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = "Participant"
        verbose_name_plural = "Participants"

    def clean(self):
        # Si pas de compte lié, les champs locaux sont obligatoires
        if not self.user:
            if not self.first_name or not self.last_name:
                raise ValidationError(
                    "Prénom et nom sont obligatoires sans compte utilisateur."
                )
            if not self.email:
                raise ValidationError(
                    "L'email est obligatoire sans compte utilisateur."
                )

    # ── Accesseurs unifiés ──────────────────────────────────────────

    @property
    def full_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return f"{self.first_name} {self.last_name}"

    @property
    def contact_email(self):
        if self.user:
            return self.user.email
        return self.email

    def __str__(self):
        return f"{self.full_name} <{self.contact_email}>"


# ─────────────────────────────────────────
# INSCRIPTION (relation many-to-many dédiée)
# ─────────────────────────────────────────

class Registration(models.Model):
    """
    Table de jointure explicite entre Participant et Event.
    Garantit l'unicité : un participant ne peut s'inscrire
    qu'une seule fois par événement.
    """

    class Status(models.TextChoices):
        PENDING   = 'pending',   'En attente'
        CONFIRMED = 'confirmed', 'Confirmée'
        CANCELLED = 'cancelled', 'Annulée'
        WAITLIST  = 'waitlist',  "Liste d'attente"

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name="Participant",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name="Événement",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Statut",
    )
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    notes         = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        ordering = ['-registered_at']
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        constraints = [
            # Contrainte DB explicitement nommée (remplace unique_together)
            models.UniqueConstraint(
                fields=['participant', 'event'],
                name='unique_participant_per_event',
            )
        ]

    def clean(self):
        # Message d'erreur propre pour les formulaires Django
        if Registration.objects.filter(
            participant=self.participant,
            event=self.event
        ).exclude(pk=self.pk).exists():
            raise ValidationError(
                f"{self.participant.full_name} est déjà inscrit(e) à cet événement."
            )

    def save(self, *args, **kwargs):
        # Garantit que clean() est toujours appelé,
        # même via .create() ou .save() en code pur
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.participant.full_name} → {self.event.title} [{self.get_status_display()}]"