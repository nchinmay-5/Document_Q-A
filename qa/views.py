"""Q&A endpoint."""
import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from generation.llm import LLMError
from qa.serializers import AskSerializer, serialize_answer
from qa.service import answer_question
from retrieval.retriever import RetrievalConfig

logger = logging.getLogger(__name__)


class AskView(APIView):
    def post(self, request: Request) -> Response:
        payload = AskSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        config = RetrievalConfig.from_settings(
            mode=data.get("mode"),
            final_k=data.get("final_k"),
            rerank=data.get("rerank"),
            rerank_k=data.get("rerank_k"),
        )
        try:
            result = answer_question(
                user=request.user,
                question=data["question"],
                config=config,
                history=data.get("history"),
                document_ids=data.get("document_ids"),
                content_types=data.get("content_types"),
                created_after=data.get("created_after"),
            )
        except LLMError as exc:
            # An unreachable or failing provider is an upstream problem, not a
            # server bug: report it as one so the client can show the reason.
            logger.error("Generation failed: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(serialize_answer(result, include_debug=data["debug"]))
