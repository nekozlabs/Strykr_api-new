from datetime import datetime
from typing import List
from ninja import Router
from .models import APIKey, Org, create_random_api_key
from .schemas import APIKeySchema, CreateAPIKeySchema, UpdateAPIKeySchema, GetAPIKeySchema

router = Router()

@router.post("/create-api-key", response=APIKeySchema)
def create_api_key(request, payload: CreateAPIKeySchema):
    org = Org.objects.get(id=payload.org_id)
    api_key = APIKey.objects.create(
        org=org,
        user_id=payload.user_id,  # To identify the user.
        name=payload.name,
        key=create_random_api_key(),
        client_side_key=create_random_api_key(),
        allowed_domains=payload.allowed_domains,
        is_revoked=payload.is_revoked,
        is_unlimited=payload.is_unlimited,
        expires_at=payload.expires_at,
        monthly_limit=payload.monthly_limit,
        permission_level=payload.permission_level
    )

    return {
        "id": api_key.id,
        "org_id": api_key.org.id,
        "user_id": api_key.user_id,
        "name": api_key.name,
        "key": api_key.key,
        "client_side_key": api_key.client_side_key,
        "allowed_domains": api_key.allowed_domains,
        "is_revoked": api_key.is_revoked,
        "is_unlimited": api_key.is_unlimited,
        "expires_at": api_key.expires_at,
        "monthly_limit": api_key.monthly_limit,
        "permission_level": api_key.permission_level,
        "created_at": api_key.created_at,
        "updated_at": api_key.updated_at,
    }

@router.post("/revoke-api-key", response={200: str})
def revoke_api_key(request, key: str, payload: GetAPIKeySchema):
    try:
        api_key = APIKey.objects.get(key=key, user_id=payload.user_id)
        api_key.is_revoked = True
        api_key.save()
        return "API key revoked successfully"
    except APIKey.DoesNotExist:
        return "API key not found"

@router.post("/update-api-key", response=APIKeySchema)
def update_api_key(request, key: str, payload: UpdateAPIKeySchema):
    try:
        api_key = APIKey.objects.get(key=key, user_id=payload.user_id)
        for attr, value in payload.dict().items():
            if attr != "user_id":
                setattr(api_key, attr, value)
        api_key.save()
        return api_key
    except APIKey.DoesNotExist:
        return "API key not found"

@router.post("/list-api-keys", response=List[APIKeySchema])
def list_api_keys(request, payload: GetAPIKeySchema):
    api_keys = list(APIKey.objects.filter(user_id=payload.user_id))
    return api_keys

@router.post("/get-api-key", response=APIKeySchema)
def get_api_key(request, key: str, payload: GetAPIKeySchema):
    try:
        api_key = APIKey.objects.get(key=key, user_id=payload.user_id)
        return api_key
    except APIKey.DoesNotExist:
        return "API key not found"