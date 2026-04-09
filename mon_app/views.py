from django.db.models import Count
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Event, Participant, Registration
from .serializers import (
    UserSerializer, UserCreateSerializer,
    EventSerializer,
    ParticipantSerializer, ParticipantWriteSerializer,
    RegistrationSerializer,
)
from .permissions import IsAdminOrReadOnly


# ─────────────────────────────────────────
# USER
# ─────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les utilisateurs.
    Seul un admin peut créer / modifier / supprimer.
    """
    queryset           = User.objects.all().order_by('id')
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['username', 'email', 'first_name', 'last_name']
    ordering_fields    = ['username', 'role']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer


# ─────────────────────────────────────────
# EVENT
# ─────────────────────────────────────────

class EventViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les événements.
    Filtres : ?status=published  ?start_date_after=2024-01-01
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class   = EventSerializer
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status']
    search_fields      = ['title', 'location', 'description']
    ordering_fields    = ['date', 'status', 'title']

    def get_queryset(self):
        qs = Event.objects.annotate(_nb_registrations=Count('registrations'))

        after  = self.request.query_params.get('date_after')
        before = self.request.query_params.get('date_before')

        if after:
            try:
                qs = qs.filter(date__gte=after)
            except (ValueError, DjangoValidationError):
                raise DRFValidationError({"date": "Format invalide pour date_after. Utilisez YYYY-MM-DD."})
        if before:
            try:
                qs = qs.filter(date__lte=before)
            except (ValueError, DjangoValidationError):
                raise DRFValidationError({"date": "Format invalide pour date_before. Utilisez YYYY-MM-DD."})

        return qs

    @action(detail=True, methods=['get'], url_path='registrations')
    def registrations(self, request, pk=None):
        """GET /events/{id}/registrations/ — liste des inscriptions d'un événement."""
        event = self.get_object()
        qs    = event.registrations.select_related('participant__user')
        serializer = RegistrationSerializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────
# PARTICIPANT
# ─────────────────────────────────────────

class ParticipantViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les participants.
    """
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.request.user.is_admin_or_editor and self.action in ('create', 'update', 'partial_update'):
            return ParticipantWriteSerializer
        return ParticipantSerializer
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['first_name', 'last_name', 'email', 'user__email', 'user__username']
    ordering_fields    = ['last_name', 'first_name']

    def get_queryset(self):
        return (
            Participant.objects
            .select_related('user')
            .annotate(_nb_registrations=Count('registrations'))
            .order_by('last_name', 'first_name')
        )

    @action(detail=True, methods=['get'], url_path='registrations')
    def registrations(self, request, pk=None):
        """GET /participants/{id}/registrations/ — liste des inscriptions d'un participant."""
        participant = self.get_object()
        qs          = participant.registrations.select_related('event')
        serializer  = RegistrationSerializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────

class RegistrationViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les inscriptions.
    Filtres : ?event=<id>  ?participant=<id>  ?status=confirmed
    """
    serializer_class   = RegistrationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['event', 'participant', 'status']
    ordering_fields    = ['registered_at', 'status']

    def get_queryset(self):
        return (
            Registration.objects
            .select_related('participant__user', 'event')
            .order_by('-registered_at')
        )