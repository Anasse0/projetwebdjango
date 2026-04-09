from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    - ADMIN / superuser : tous les verbes (GET, POST, PUT, PATCH, DELETE)
    - VIEWER            : lecture seule (GET, HEAD, OPTIONS)
    - Non authentifié   : refusé
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin_or_editor
