from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from .models import User, Event, Participant, Registration


# ─────────────────────────────────────────
# USER
# ─────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active')
        read_only_fields = ('id', 'is_active')


class UserCreateSerializer(serializers.ModelSerializer):
    """Utilisé uniquement à la création pour gérer le mot de passe."""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'password')
        read_only_fields = ('id',)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ─────────────────────────────────────────
# EVENT
# ─────────────────────────────────────────

class EventSerializer(serializers.ModelSerializer):
    nb_registrations = serializers.SerializerMethodField(read_only=True)
 
    class Meta:
        model  = Event
        fields = (
            'id', 'title', 'description', 'location',
            'date', 'status', 'nb_registrations',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
 
    def get_nb_registrations(self, obj):
        if hasattr(obj, '_nb_registrations'):
            return obj._nb_registrations
        return obj.registrations.count()
    
    
# ─────────────────────────────────────────
# PARTICIPANT
# ─────────────────────────────────────────

class ParticipantSerializer(serializers.ModelSerializer):
    full_name     = serializers.CharField(read_only=True)
    contact_email = serializers.CharField(read_only=True)

    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model  = Participant
        fields = (
            'id', 'user',
            'first_name', 'last_name', 'email', 'phone',
            'full_name', 'contact_email',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'user', 'full_name', 'contact_email', 'created_at', 'updated_at')

    def validate(self, data):
        user = getattr(self.instance, 'user', None)
        if not user:
            if not data.get('first_name') or not data.get('last_name'):
                raise serializers.ValidationError(
                    "Prénom et nom sont obligatoires sans compte utilisateur."
                )
            if not data.get('email'):
                raise serializers.ValidationError(
                    "L'email est obligatoire sans compte utilisateur."
                )
        return data


class ParticipantWriteSerializer(ParticipantSerializer):
    """Serializer d'écriture réservé aux admins : permet de lier/délier un User."""
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta(ParticipantSerializer.Meta):
        read_only_fields = ('id', 'full_name', 'contact_email', 'created_at', 'updated_at')


# ─────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────

class RegistrationSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source='participant.full_name', read_only=True)
    event_title      = serializers.CharField(source='event.title',          read_only=True)

    class Meta:
        model  = Registration
        fields = (
            'id',
            'participant', 'participant_name',
            'event',       'event_title',
            'status', 'notes', 'registered_at',
        )
        read_only_fields = ('id', 'registered_at', 'participant_name', 'event_title')

    def validate(self, data):
        participant = data.get('participant', getattr(self.instance, 'participant', None))
        event       = data.get('event',       getattr(self.instance, 'event',       None))

        if event:
            forbidden_statuses = (Event.Status.CANCELLED, Event.Status.COMPLETED)
            if event.status in forbidden_statuses:
                raise serializers.ValidationError(
                    {"event": f"Impossible de s'inscrire à un événement {event.get_status_display().lower()}."}
                )

        if participant and event:
            qs = Registration.objects.filter(participant=participant, event=event)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f"{participant.full_name} est déjà inscrit(e) à cet événement."
                )

        return data

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields['participant'].read_only = True
            fields['event'].read_only       = True
        return fields