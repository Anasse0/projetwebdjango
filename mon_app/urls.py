from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .views import UserViewSet, EventViewSet, ParticipantViewSet, RegistrationViewSet


# ─────────────────────────────────────────
# JWT CUSTOM — retourne `token` au lieu de `access`
# pour compatibilité avec le frontend (localStorage.getItem('token'))
# ─────────────────────────────────────────

class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Renomme `access` → `token` et inclut les infos user
        return {
            'token':   data['access'],
            'refresh': data['refresh'],
            'user': {
                'id':       self.user.id,
                'username': self.user.username,
                'email':    self.user.email,
                'role':     self.user.role,
            }
        }

class CustomTokenView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


# ─────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────

router = DefaultRouter()
router.register('users',         UserViewSet,         basename='user')
router.register('events',        EventViewSet,        basename='event')
router.register('participants',  ParticipantViewSet,  basename='participant')
router.register('registrations', RegistrationViewSet, basename='registration')

urlpatterns = [
    # Auth JWT
    path('token/',   CustomTokenView.as_view(),  name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API CRUD
    path('', include(router.urls)),
]
