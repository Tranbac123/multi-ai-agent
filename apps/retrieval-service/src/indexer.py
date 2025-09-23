from .models import IndexRequest, DeleteRequest, IndexResponse, DeleteResponse


def upsert(req: IndexRequest) -> IndexResponse:
    return IndexResponse(ok=True)


def delete(req: DeleteRequest) -> DeleteResponse:
    return DeleteResponse(ok=True)

