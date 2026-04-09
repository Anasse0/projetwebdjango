from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Gestionnaire d'erreurs global pour l'API.

    Garantit que TOUTES les erreurs retournent le même format JSON :
    {
        "error":   "Type d'erreur lisible",
        "detail":  "Message détaillé ou dict de champs"
    }

    Couvre :
    - Les erreurs DRF standard (ValidationError, NotFound, PermissionDenied...)
    - Les ValidationError Django (levées dans model.clean())
    - Les IntegrityError base de données (double inscription passée en force, etc.)
    """

    # 1. Laisser DRF traiter ce qu'il connaît
    response = drf_exception_handler(exc, context)

    if response is not None:
        # DRF a géré → on normalise juste le format
        response.data = _normalize(response)
        return response

    # 2. ValidationError Django (model.clean() appelé hors serializer)
    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "error":  "Erreur de validation",
                "detail": exc.message_dict if hasattr(exc, 'message_dict') else exc.messages,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. IntegrityError base de données
    #    (ex : UniqueConstraint violée via un .save() sans full_clean)
    if isinstance(exc, IntegrityError):
        msg = str(exc)
        # Détecte la contrainte d'unicité inscription
        if 'unique_participant_per_event' in msg:
            detail = "Ce participant est déjà inscrit à cet événement."
        else:
            detail = "Violation de contrainte base de données."
        return Response(
            {"error": "Conflit de données", "detail": detail},
            status=status.HTTP_409_CONFLICT,
        )

    # 4. Toute autre exception non gérée → 500 sans exposer la stack trace
    return Response(
        {"error": "Erreur serveur interne", "detail": "Une erreur inattendue s'est produite."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _normalize(response):
    """
    Transforme la réponse DRF en format uniforme {error, detail}.
    Exemples DRF bruts :
      {"detail": "Not found."}
      {"field": ["This field is required."]}
      ["This field is required."]
    """
    data = response.data

    error_labels = {
        400: "Erreur de validation",
        401: "Non authentifié",
        403: "Accès refusé",
        404: "Ressource introuvable",
        405: "Méthode non autorisée",
        409: "Conflit de données",
    }
    error = error_labels.get(response.status_code, "Erreur")

    # Déjà au bon format
    if isinstance(data, dict) and 'error' in data:
        return data

    # Format DRF standard {"detail": "..."} → on garde tel quel avec label
    if isinstance(data, dict) and 'detail' in data and len(data) == 1:
        return {"error": error, "detail": data['detail']}

    # Erreurs de champs {"field": ["msg"]} ou liste brute
    return {"error": error, "detail": data}
