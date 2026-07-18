from fastkit_accounts.normalizers import default_registry


def _has_normalizer(identifier_type: str) -> bool:
    try:
        default_registry().get(identifier_type)

        return True
    except KeyError:
        return False


def profile_summary(user, identifiers, identifier_types, avatar_url=None) -> dict:
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "preferred_locale": user.preferred_locale,
        "timezone": user.timezone,
        "avatar_file_id": str(user.profile.avatar_file_id)
        if user.profile and user.profile.avatar_file_id
        else None,
        "avatar_url": avatar_url,
        "identifier_types": identifier_types,
        "identifiers": [
            {
                "id": str(item.id),
                "type": item.type,
                "value": default_registry().get(item.type).mask(item.value)
                if _has_normalizer(item.type)
                else item.value,
            }
            for item in identifiers
        ],
    }
