"""Document API: upload, list, inspect, delete. Scoped to the requesting user."""
from rest_framework import mixins, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from documents import services
from documents.models import Document
from documents.serializers import DocumentSerializer, DocumentUploadSerializer


class DocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        # The single rule that guarantees per-user isolation at the API layer.
        return Document.objects.filter(user=self.request.user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        upload = DocumentUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        document = services.create_document(request.user, upload.validated_data["file"])
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: Document) -> None:
        services.delete_document(instance)
